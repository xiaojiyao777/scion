from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest

from scion.lineage import proposal_attempt_codec as codec
from scion.lineage import proposal_attempt_owner as owner


_DIGEST_A = "a" * 64
_DIGEST_B = "b" * 64
_DIGEST_C = "c" * 64
_DIGEST_D = "d" * 64


class _NamedRow:
    def __init__(self, columns: tuple[str, ...], values: tuple[object, ...]) -> None:
        self._columns = columns
        self._values = values

    def keys(self) -> tuple[str, ...]:
        return self._columns

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self._values)


def _binding_row(**overrides: object) -> _NamedRow:
    values: dict[str, object] = {
        "campaign_id": "campaign-a",
        "provider_attempt_id": "attempt-a",
        "started_event_id": "event-start",
        "generated_event_id": "event-generated",
        "branch_id": "branch-a",
        "branch_owner_revision": 3,
        "branch_storage_sha256": _DIGEST_A,
        "hypothesis_id": "hypothesis-a",
        "parent_hypothesis_id": None,
        "parent_owner_revision": None,
        "parent_storage_sha256": None,
        "proposal_digest": _DIGEST_B,
        "hypothesis_storage_sha256": _DIGEST_C,
        "transition_group_sha256": _DIGEST_D,
        "binding_protocol_generation": "proposal-h-binding.v1",
        "created_at": "2026-07-17T01:02:03.000004+00:00",
    }
    values.update(overrides)
    columns = codec._PROPOSAL_HYPOTHESIS_BINDING_COLUMNS
    return _NamedRow(columns, tuple(values[column] for column in columns))


def test_owner_reexports_exact_codec_tokens() -> None:
    assert owner.StoredProposalAttemptEvent is codec.StoredProposalAttemptEvent
    assert (
        owner.StoredProposalHypothesisBinding
        is codec.StoredProposalHypothesisBinding
    )


def test_binding_codec_accepts_exact_empty_and_nonempty_parent_triples() -> None:
    empty_parent = codec.decode_stored_proposal_hypothesis_binding(
        _binding_row(),
        authority_campaign_id="campaign-a",
    )
    assert empty_parent.parent_hypothesis_id is None
    assert empty_parent.parent_owner_revision is None
    assert empty_parent.parent_storage_sha256 is None

    with_parent = codec.decode_stored_proposal_hypothesis_binding(
        _binding_row(
            parent_hypothesis_id="hypothesis-parent",
            parent_owner_revision=2,
            parent_storage_sha256=_DIGEST_A,
        ),
        authority_campaign_id="campaign-a",
    )
    assert with_parent.parent_hypothesis_id == "hypothesis-parent"
    assert with_parent.parent_owner_revision == 2
    assert with_parent.parent_storage_sha256 == _DIGEST_A


@pytest.mark.parametrize(
    "overrides",
    [
        {"branch_owner_revision": True},
        {"branch_owner_revision": 3.0},
        {"branch_storage_sha256": "A" * 64},
        {"proposal_digest": "b" * 63},
        {"started_event_id": "event-generated"},
        {"binding_protocol_generation": "proposal-h-binding.v2"},
        {"created_at": "2026-07-17T01:02:03.000004Z"},
        {"created_at": "2026-07-17T01:02:03+00:00"},
        {"created_at": "2026-07-17T02:02:03.000004+01:00"},
        {"parent_hypothesis_id": "hypothesis-parent"},
        {"parent_owner_revision": 2},
        {"parent_storage_sha256": _DIGEST_A},
    ],
)
def test_binding_codec_rejects_noncanonical_storage(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(codec.InvalidStartedHypothesisAttemptError):
        codec.decode_stored_proposal_hypothesis_binding(_binding_row(**overrides))


def test_binding_codec_rejects_campaign_and_column_drift() -> None:
    with pytest.raises(
        codec.InvalidStartedHypothesisAttemptError,
        match="another campaign",
    ):
        codec.decode_stored_proposal_hypothesis_binding(
            _binding_row(),
            authority_campaign_id="campaign-b",
        )

    row = _binding_row()
    with pytest.raises(
        codec.InvalidStartedHypothesisAttemptError,
        match="unexpected columns",
    ):
        codec.decode_stored_proposal_hypothesis_binding(
            _NamedRow((*row.keys(), "extra"), (*tuple(row), "extra"))
        )


def test_transition_group_digest_uses_exact_unicode_ids_and_storage() -> None:
    canonical = (
        '{"binding_protocol_generation":"proposal-h-binding.v1",'
        '"generated_event_id":"生成-event",'
        f'"generated_event_storage_sha256":"{_DIGEST_B}",'
        '"schema_version":"proposal-h-transition-group.v1",'
        '"started_event_id":"开始-event",'
        f'"started_event_storage_sha256":"{_DIGEST_A}"}}'
    ).encode("utf-8")

    digest = codec.proposal_hypothesis_transition_group_sha256(
        started_event_id="开始-event",
        started_event_storage_sha256=_DIGEST_A,
        generated_event_id="生成-event",
        generated_event_storage_sha256=_DIGEST_B,
    )

    assert digest == hashlib.sha256(canonical).hexdigest()
    assert digest != codec.proposal_hypothesis_transition_group_sha256(
        started_event_id="开始-event",
        started_event_storage_sha256=_DIGEST_C,
        generated_event_id="生成-event",
        generated_event_storage_sha256=_DIGEST_B,
    )


def test_codec_has_one_production_importer_and_no_forbidden_responsibilities() -> None:
    package_root = Path(codec.__file__).resolve().parents[1]
    codec_path = Path(codec.__file__).resolve()
    codec_module = "scion.lineage.proposal_attempt_codec"
    importers: set[str] = set()
    for path in package_root.rglob("*.py"):
        relative = path.relative_to(package_root)
        if "tests" in relative.parts or path.resolve() == codec_path:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(
                alias.name == codec_module for alias in node.names
            ):
                importers.add(relative.as_posix())
            elif isinstance(node, ast.ImportFrom) and node.module == codec_module:
                importers.add(relative.as_posix())
    assert importers == {"lineage/proposal_attempt_owner.py"}

    source = codec_path.read_text(encoding="utf-8")
    assert "sqlite_connection" not in source
    assert "hypothesis_generation_authority" not in source
    assert "CampaignOwnerRegistry" not in source
    assert "execute(" not in source
    assert "callback" not in source
