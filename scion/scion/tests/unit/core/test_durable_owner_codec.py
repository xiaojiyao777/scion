from __future__ import annotations

import ast
import copy
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

import pytest

from scion.core import decision_completion_transaction, durable_owner_codec
from scion.core.durable_owner_codec import (
    STABLE_SOURCE_HYPOTHESIS_SCHEMA,
    branch_from_payload,
    branch_payload_from_row,
    branch_to_payload,
    hypothesis_payload_from_row,
    hypothesis_to_payload,
    stable_source_hypothesis_payload,
    stable_source_hypothesis_payload_from_row,
)
from scion.core.models import Branch, BranchState, HypothesisRecord


def _sqlite_row(values: Mapping[str, Any]) -> sqlite3.Row:
    aliases = ", ".join(f"? AS {name}" for name in values)
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(f"SELECT {aliases}", tuple(values.values())).fetchone()
    finally:
        conn.close()
    assert row is not None
    return row


def _branch() -> Branch:
    return Branch(
        branch_id="branch-1",
        state=BranchState.VALIDATING,
        base_champion_id=7,
        base_champion_hash="a" * 64,
        lineage_id="lineage-1",
        current_code_hash="b" * 64,
        last_clean_code_hash="c" * 64,
        screening_expand_count=2,
        validation_expand_count=1,
        failure_codes=["known-failure"],
        created_at=datetime(2026, 1, 2, 3, 4, 5),
        updated_at=datetime(2026, 1, 2, 3, 4, 6),
        direction="local_search: deterministic",
        weight_revision=3,
        branch_code_status="candidate",
        branch_evidence_summary={"nested": {"values": (1, 2)}},
        infra_block_count=4,
    )


def _hypothesis() -> HypothesisRecord:
    return HypothesisRecord(
        hypothesis_id="hypothesis-1",
        branch_id="branch-1",
        change_locus="local_search",
        action="modify",
        status="active",
        target_file="operators/local_search.py",
        parent_hypothesis_id="hypothesis-0",
        suggested_weight=0.25,
        hypothesis_text="Use a deterministic neighborhood.",
        family_id="local-search",
        family_source="manual",
        taxonomy_version="v1",
        created_at=datetime(2026, 1, 2, 3, 4, 7),
        base_champion_version=7,
        predicted_direction="improve",
        proposal_digest="d" * 64,
    )


def test_frozen_v1_payloads_and_row_decoders_are_exact() -> None:
    branch = _branch()
    hypothesis = _hypothesis()
    branch_payload = branch_to_payload(branch)
    hypothesis_payload = hypothesis_to_payload(hypothesis)

    assert branch_to_payload(branch_from_payload(branch_payload)) == branch_payload
    assert "proposal_digest" not in hypothesis_payload
    assert (
        branch_payload_from_row(
            _sqlite_row(
                {
                    "branch_id": branch.branch_id,
                    "state": branch.state.value,
                    "base_champion_id": branch.base_champion_id,
                    "base_champion_hash": branch.base_champion_hash,
                    "lineage_id": branch.lineage_id,
                    "current_code_hash": branch.current_code_hash,
                    "last_clean_code_hash": branch.last_clean_code_hash,
                    "screening_expand_count": branch.screening_expand_count,
                    "validation_expand_count": branch.validation_expand_count,
                    "failure_codes": json.dumps(branch.failure_codes),
                    "created_at": branch.created_at.isoformat(),
                    "updated_at": branch.updated_at.isoformat(),
                    "direction": branch.direction,
                    "weight_revision": branch.weight_revision,
                    "branch_code_status": branch.branch_code_status,
                    "branch_evidence_summary_json": json.dumps(
                        branch.branch_evidence_summary
                    ),
                    "infra_block_count": branch.infra_block_count,
                }
            )
        )
        == branch_payload
    )
    assert (
        hypothesis_payload_from_row(
            _sqlite_row(
                {
                    "hypothesis_id": hypothesis.hypothesis_id,
                    "branch_id": hypothesis.branch_id,
                    "change_locus": hypothesis.change_locus,
                    "action": hypothesis.action,
                    "status": hypothesis.status,
                    "target_file": hypothesis.target_file,
                    "parent_hypothesis_id": hypothesis.parent_hypothesis_id,
                    "suggested_weight": hypothesis.suggested_weight,
                    "hypothesis_text": hypothesis.hypothesis_text,
                    "created_at": hypothesis.created_at.isoformat(),
                    "base_champion_version": hypothesis.base_champion_version,
                    "family_id": hypothesis.family_id,
                    "family_source": hypothesis.family_source,
                    "taxonomy_version": hypothesis.taxonomy_version,
                    "predicted_direction": hypothesis.predicted_direction,
                }
            )
        )
        == hypothesis_payload
    )


def test_row_decoders_preserve_historical_fallbacks() -> None:
    branch_payload = branch_payload_from_row(
        _sqlite_row(
            {
                "branch_id": "legacy-branch",
                "state": BranchState.EXPLORE.value,
                "base_champion_id": 1,
                "base_champion_hash": "a" * 64,
                "lineage_id": None,
                "current_code_hash": None,
                "last_clean_code_hash": None,
                "screening_expand_count": None,
                "validation_expand_count": None,
                "failure_codes": None,
                "created_at": "2026-01-02T03:04:05",
                "updated_at": "2026-01-02T03:04:06",
                "direction": None,
                "weight_revision": None,
                "branch_code_status": None,
                "branch_evidence_summary_json": None,
                "infra_block_count": None,
            }
        )
    )
    hypothesis_payload = hypothesis_payload_from_row(
        _sqlite_row(
            {
                "hypothesis_id": "legacy-h",
                "branch_id": None,
                "change_locus": None,
                "action": None,
                "status": None,
                "target_file": None,
                "parent_hypothesis_id": None,
                "suggested_weight": None,
                "hypothesis_text": None,
                "created_at": "2026-01-02T03:04:07",
                "base_champion_version": None,
                "family_id": None,
                "family_source": None,
                "taxonomy_version": None,
                "predicted_direction": None,
            }
        )
    )

    assert branch_payload["lineage_id"] == "legacy-branch"
    assert branch_payload["screening_expand_count"] == 0
    assert branch_payload["validation_expand_count"] == 0
    assert branch_payload["failure_codes"] == []
    assert branch_payload["weight_revision"] == 0
    assert branch_payload["branch_code_status"] == "clean"
    assert branch_payload["branch_evidence_summary"] == {}
    assert branch_payload["infra_block_count"] == 0
    assert hypothesis_payload["branch_id"] == ""
    assert hypothesis_payload["change_locus"] == ""
    assert hypothesis_payload["action"] == "modify"
    assert hypothesis_payload["status"] == "active"
    assert hypothesis_payload["base_champion_version"] == 0
    assert hypothesis_payload["predicted_direction"] == "exploratory"


@pytest.mark.parametrize(
    ("column", "value"),
    (
        ("failure_codes", "not-json"),
        ("branch_evidence_summary_json", "not-json"),
    ),
)
def test_branch_row_decoder_preserves_strict_malformed_json_failure(
    column: str,
    value: str,
) -> None:
    branch = _branch()
    row = {
        "branch_id": branch.branch_id,
        "state": branch.state.value,
        "base_champion_id": branch.base_champion_id,
        "base_champion_hash": branch.base_champion_hash,
        "lineage_id": branch.lineage_id,
        "current_code_hash": branch.current_code_hash,
        "last_clean_code_hash": branch.last_clean_code_hash,
        "screening_expand_count": branch.screening_expand_count,
        "validation_expand_count": branch.validation_expand_count,
        "failure_codes": json.dumps(branch.failure_codes),
        "created_at": branch.created_at.isoformat(),
        "updated_at": branch.updated_at.isoformat(),
        "direction": branch.direction,
        "weight_revision": branch.weight_revision,
        "branch_code_status": branch.branch_code_status,
        "branch_evidence_summary_json": json.dumps(branch.branch_evidence_summary),
        "infra_block_count": branch.infra_block_count,
    }
    row[column] = value

    with pytest.raises(json.JSONDecodeError):
        branch_payload_from_row(_sqlite_row(row))


def test_decision_module_does_not_reexport_moved_codec_functions() -> None:
    for name in (
        "branch_to_payload",
        "branch_from_payload",
        "hypothesis_to_payload",
        "_branch_payload_from_row",
        "_hypothesis_payload_from_row",
    ):
        assert not hasattr(decision_completion_transaction, name)


def test_durable_owner_codec_exports_only_owned_public_values() -> None:
    assert set(durable_owner_codec.__all__) == {
        "STABLE_SOURCE_HYPOTHESIS_SCHEMA",
        "branch_from_payload",
        "branch_payload_from_row",
        "branch_to_payload",
        "hypothesis_payload_from_row",
        "hypothesis_to_payload",
        "stable_source_hypothesis_payload",
        "stable_source_hypothesis_payload_from_row",
    }


def test_production_modules_do_not_import_moved_decision_codecs() -> None:
    forbidden = {
        "branch_from_payload",
        "branch_payload_from_row",
        "branch_to_payload",
        "hypothesis_payload_from_row",
        "hypothesis_to_payload",
        "_branch_payload_from_row",
        "_hypothesis_payload_from_row",
    }
    core_root = Path(__file__).parents[3] / "core"
    offenders: list[str] = []
    for source_path in sorted(core_root.rglob("*.py")):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or (
                node.module != "scion.core.decision_completion_transaction"
            ):
                continue
            moved = forbidden.intersection(alias.name for alias in node.names)
            if moved:
                offenders.append(
                    f"{source_path.relative_to(core_root)}:{node.lineno}:"
                    f"{','.join(sorted(moved))}"
                )
    assert offenders == []


def test_stable_source_hypothesis_projection_includes_only_frozen_identity() -> None:
    hypothesis = _hypothesis()

    assert stable_source_hypothesis_payload(hypothesis) == {
        "schema_version": STABLE_SOURCE_HYPOTHESIS_SCHEMA,
        "hypothesis_id": "hypothesis-1",
        "branch_id": "branch-1",
        "parent_hypothesis_id": "hypothesis-0",
        "proposal_digest": "d" * 64,
        "base_champion_version": 7,
        "change_locus": "local_search",
        "action": "modify",
        "target_file": "operators/local_search.py",
        "suggested_weight": 0.25,
        "predicted_direction": "improve",
        "family_id": "local-search",
        "family_source": "manual",
        "taxonomy_version": "v1",
    }


def test_stable_source_hypothesis_row_projection_is_exact_and_has_no_fallbacks() -> (
    None
):
    hypothesis = _hypothesis()
    row = _sqlite_row(
        {
            "hypothesis_id": hypothesis.hypothesis_id,
            "branch_id": hypothesis.branch_id,
            "parent_hypothesis_id": hypothesis.parent_hypothesis_id,
            "proposal_digest": hypothesis.proposal_digest,
            "base_champion_version": hypothesis.base_champion_version,
            "change_locus": hypothesis.change_locus,
            "action": hypothesis.action,
            "target_file": hypothesis.target_file,
            "suggested_weight": hypothesis.suggested_weight,
            "predicted_direction": hypothesis.predicted_direction,
            "family_id": hypothesis.family_id,
            "family_source": hypothesis.family_source,
            "taxonomy_version": hypothesis.taxonomy_version,
            "status": "advanced",
            "created_at": "2030-01-01T00:00:00",
            "owner_revision": 99,
            "diagnostics_json": '{"ignored":true}',
        }
    )

    assert stable_source_hypothesis_payload_from_row(row) == (
        stable_source_hypothesis_payload(hypothesis)
    )

    invalid = dict(row)
    invalid["branch_id"] = None
    with pytest.raises(ValueError, match="Branch ID must be a non-empty string"):
        stable_source_hypothesis_payload_from_row(_sqlite_row(invalid))


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("hypothesis_id", "hypothesis-2"),
        ("branch_id", "branch-2"),
        ("parent_hypothesis_id", "hypothesis-parent-2"),
        ("proposal_digest", "e" * 64),
        ("base_champion_version", 8),
        ("change_locus", "construction"),
        ("action", "create_new"),
        ("target_file", "operators/construction.py"),
        ("suggested_weight", 0.5),
        ("predicted_direction", "tradeoff"),
        ("family_id", "construction"),
        ("family_source", "classifier"),
        ("taxonomy_version", "v2"),
    ),
)
def test_stable_source_hypothesis_projection_binds_each_identity_field(
    field: str,
    replacement: Any,
) -> None:
    source = _hypothesis()
    mutated = copy.deepcopy(source)
    setattr(mutated, field, replacement)

    assert stable_source_hypothesis_payload(mutated) != (
        stable_source_hypothesis_payload(source)
    )


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("status", "advanced"),
        ("created_at", datetime(2026, 1, 2, 3, 4, 7) + timedelta(days=1)),
        ("hypothesis_text", "Changed public hypothesis prose."),
        ("owner_revision", 99),
        ("diagnostics", {"warning": "changed"}),
        ("runtime_facts", {"seconds": 12}),
        ("public_summary", "changed"),
    ),
)
def test_stable_source_hypothesis_projection_excludes_mutable_fields(
    field: str,
    replacement: Any,
) -> None:
    source = _hypothesis()
    mutated = copy.deepcopy(source)
    setattr(mutated, field, replacement)

    assert stable_source_hypothesis_payload(mutated) == (
        stable_source_hypothesis_payload(source)
    )


@pytest.mark.parametrize(
    "proposal_digest",
    (None, "", "d" * 63, "D" * 64, 7),
)
def test_stable_source_hypothesis_projection_rejects_invalid_proposal_digest(
    proposal_digest: Any,
) -> None:
    hypothesis = _hypothesis()
    hypothesis.proposal_digest = proposal_digest

    with pytest.raises(ValueError, match="proposal digest must be a full SHA-256"):
        stable_source_hypothesis_payload(hypothesis)


@pytest.mark.parametrize(
    ("weight", "expected"),
    ((0, 0.0), (1, 1.0), (0.0, 0.0), (-0.0, 0.0), (1.0, 1.0)),
)
def test_stable_source_hypothesis_weight_is_canonical_across_sqlite_real(
    weight: int | float,
    expected: float,
) -> None:
    hypothesis = _hypothesis()
    hypothesis.suggested_weight = weight
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            """
            CREATE TABLE source_h (
                hypothesis_id TEXT, branch_id TEXT, parent_hypothesis_id TEXT,
                proposal_digest TEXT, base_champion_version INTEGER,
                change_locus TEXT, action TEXT, target_file TEXT,
                suggested_weight REAL, predicted_direction TEXT,
                family_id TEXT, family_source TEXT, taxonomy_version TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO source_h VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                hypothesis.hypothesis_id,
                hypothesis.branch_id,
                hypothesis.parent_hypothesis_id,
                hypothesis.proposal_digest,
                hypothesis.base_champion_version,
                hypothesis.change_locus,
                hypothesis.action,
                hypothesis.target_file,
                weight,
                hypothesis.predicted_direction,
                hypothesis.family_id,
                hypothesis.family_source,
                hypothesis.taxonomy_version,
            ),
        )
        row = conn.execute("SELECT * FROM source_h").fetchone()
    finally:
        conn.close()
    assert row is not None

    object_payload = stable_source_hypothesis_payload(hypothesis)
    row_payload = stable_source_hypothesis_payload_from_row(row)
    assert object_payload["suggested_weight"] == expected
    assert row_payload == object_payload
    assert json.dumps(
        row_payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8") == json.dumps(
        object_payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode(
        "utf-8"
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("hypothesis_id", "", "hypothesis ID must be a non-empty string"),
        ("branch_id", None, "Branch ID must be a non-empty string"),
        ("change_locus", 7, "change locus must be a non-empty string"),
        ("action", "", "action must be a non-empty string"),
        ("action", "replace", "action is invalid"),
        ("action", " modify", "action must be a non-empty string"),
        (
            "parent_hypothesis_id",
            7,
            "parent ID must be a string or null",
        ),
        (
            "base_champion_version",
            True,
            "base champion version must be nonnegative",
        ),
        (
            "base_champion_version",
            1.0,
            "base champion version must be nonnegative",
        ),
        (
            "base_champion_version",
            -1,
            "base champion version must be nonnegative",
        ),
        ("suggested_weight", True, "suggested weight must be finite"),
        ("suggested_weight", float("inf"), "suggested weight must be finite"),
        ("suggested_weight", float("nan"), "suggested weight must be finite"),
        ("suggested_weight", "0.25", "suggested weight must be finite"),
        ("predicted_direction", [], "predicted direction is invalid"),
        ("target_file", "", "target file must be a string or null"),
        ("family_id", " ", "family ID must be a string or null"),
    ),
)
def test_stable_source_hypothesis_projection_rejects_noncanonical_types(
    field: str,
    value: Any,
    message: str,
) -> None:
    hypothesis = _hypothesis()
    setattr(hypothesis, field, value)

    with pytest.raises(ValueError, match=message):
        stable_source_hypothesis_payload(hypothesis)
