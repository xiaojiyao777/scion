from __future__ import annotations

import pytest

from scion.proposal.engine import ProposalValidationError, _parse_patch
from scion.proposal.schemas import PATCH_TOOL


def _context(target: str, scheduler: str) -> dict[str, object]:
    return {
        "editable_source_context": {
            "approved_target": "destroy_repair.py",
            "sources": [
                {
                    "path": "destroy_repair.py",
                    "content": target,
                    "roles": ["target"],
                    "visible": True,
                },
                {
                    "path": "scheduler.py",
                    "content": scheduler,
                    "roles": ["caller"],
                    "visible": True,
                },
            ],
            "public_tests": [],
            "target_api_guidance": "",
        }
    }


def _local_change(path: str, old: str, new: str) -> dict[str, object]:
    return {
        "file_path": path,
        "action": "modify",
        "edit_intent": "exact_replace",
        "old_string": old,
        "new_string": new,
        "replace_all": False,
        "evidence_refs": [],
    }


def test_provider_schema_has_one_explicit_intent_and_no_identity_fields() -> None:
    schema = PATCH_TOOL["input_schema"]
    nested = schema["properties"]["additional_changes"]["items"]

    assert "edit_intent" in schema["required"]
    assert "edit_intent" in nested["required"]
    for field in ("source_digest", "derived_diff_ref", "repair_attribution"):
        assert field not in schema["properties"]
        assert field not in nested["properties"]
        assert field not in PATCH_TOOL["description"]


def test_parser_materializes_two_distinct_explicit_file_values() -> None:
    target = "from .state import Route\n\n\ndef greedy():\n    return 1\n"
    scheduler = "from .destroy_repair import greedy\n"
    raw = _local_change(
        "destroy_repair.py",
        "from .state import Route\n",
        "from .state import Route, route_distance\n",
    )
    raw["additional_changes"] = [
        _local_change(
            "scheduler.py",
            "from .destroy_repair import greedy\n",
            "from .destroy_repair import route_distance, greedy\n",
        )
    ]

    patch = _parse_patch(raw, context=_context(target, scheduler))

    assert "Route, route_distance" in patch.code_content
    assert len(patch.additional_changes) == 1
    assert "route_distance, greedy" in patch.additional_changes[0].code_content
    assert not hasattr(patch, "repair_attribution")


def test_parser_rejects_duplicate_file_paths_instead_of_composing() -> None:
    target = "def solve():\n    return 1\n"
    scheduler = "def schedule():\n    return solve()\n"
    raw = _local_change("destroy_repair.py", "return 1", "return 2")
    raw["additional_changes"] = [
        _local_change("destroy_repair.py", "def solve():", "def solve(seed):")
    ]

    with pytest.raises(ProposalValidationError, match="duplicate file_path"):
        _parse_patch(raw, context=_context(target, scheduler))


def test_parser_rejects_missing_edit_intent() -> None:
    target = "def solve():\n    return 1\n"
    raw = {
        "file_path": "destroy_repair.py",
        "action": "modify",
        "content_after": target.replace("1", "2"),
    }

    with pytest.raises(ProposalValidationError, match="edit_intent is required"):
        _parse_patch(raw, context=_context(target, ""))


def test_parser_rejects_noop_local_and_full_file_changes() -> None:
    target = "def solve():\n    return 1\n"
    context = _context(target, "")

    with pytest.raises(ProposalValidationError, match="identical"):
        _parse_patch(
            _local_change("destroy_repair.py", "return 1", "return 1"),
            context=context,
        )
    with pytest.raises(ProposalValidationError, match="no-op"):
        _parse_patch(
            {
                "file_path": "destroy_repair.py",
                "action": "modify",
                "edit_intent": "full_file",
                "content_after": target,
            },
            context=context,
        )


def test_parser_rejects_duplicate_editable_source_paths() -> None:
    target = "def solve():\n    return 1\n"
    context = _context(target, "")
    editable = context["editable_source_context"]
    assert isinstance(editable, dict)
    sources = editable["sources"]
    assert isinstance(sources, list)
    sources.append(
        {
            "path": "destroy_repair.py",
            "content": target,
            "roles": ["target"],
            "visible": True,
        }
    )

    with pytest.raises(ValueError, match="duplicate editable source path"):
        _parse_patch(
            _local_change("destroy_repair.py", "return 1", "return 2"),
            context=context,
        )


def test_parser_rejects_removed_source_digest_field() -> None:
    target = "def solve():\n    return 1\n"
    raw = _local_change("destroy_repair.py", "return 1", "return 2")
    raw["source_digest"] = "0" * 64

    with pytest.raises(ProposalValidationError, match="source_digest"):
        _parse_patch(raw, context=_context(target, ""))
