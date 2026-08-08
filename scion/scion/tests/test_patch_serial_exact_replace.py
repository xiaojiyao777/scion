from __future__ import annotations

import pytest

from scion.proposal.edit_protocol import source_digest_for_content
from scion.proposal.engine import ProposalValidationError, _parse_patch
from scion.proposal.schemas import PATCH_TOOL


def _source_ledger(target: str, scheduler: str) -> dict[str, object]:
    return {
        "schema_version": "proposal-source-ledger.v2",
        "approved_target": "destroy_repair.py",
        "entries": [
            {
                "path": "destroy_repair.py",
                "content": target,
                "digest": source_digest_for_content(target),
                "owner": "approved_target",
                "provenance": "champion_snapshot",
                "visibility": "full_current",
                "reason": "ok",
            },
            {
                "path": "scheduler.py",
                "content": scheduler,
                "digest": source_digest_for_content(scheduler),
                "owner": "champion_api_support",
                "provenance": "champion_snapshot",
                "visibility": "full_current",
                "reason": "ok",
            },
        ],
        "views": {
            "champion_research": ["destroy_repair.py", "scheduler.py"],
            "reference": [],
            "api_reference": ["destroy_repair.py", "scheduler.py"],
            "integration_full": ["destroy_repair.py", "scheduler.py"],
            "integration_summary": [],
            "branch_current": [],
            "required_full": [],
        },
        "target_api_guidance": "",
    }


def _serial_patch(target: str, scheduler: str) -> dict[str, object]:
    return {
        "file_path": "destroy_repair.py",
        "action": "modify",
        "edit_intent": "exact_replace",
        "old_string": "from .state import Route\n\n\n",
        "new_string": (
            "from .state import Route, route_distance\n\n\n"
            "CHAIN_LIMIT = 10\n\n\n"
        ),
        "replace_all": False,
        "evidence_refs": [],
        "additional_changes": [
            {
                "file_path": "destroy_repair.py",
                "action": "modify",
                "edit_intent": "exact_replace",
                "old_string": "CHAIN_LIMIT = 10\n\n\ndef greedy():\n    return 1\n",
                "new_string": (
                    "CHAIN_LIMIT = 10\n\n\n"
                    "def ejection_chain():\n    return CHAIN_LIMIT\n\n\n"
                    "def greedy():\n    return 1\n"
                ),
                "replace_all": False,
                "evidence_refs": [],
            },
            {
                "file_path": "scheduler.py",
                "action": "modify",
                "edit_intent": "exact_replace",
                "old_string": "from .destroy_repair import greedy\n",
                "new_string": (
                    "from .destroy_repair import ejection_chain, greedy\n"
                ),
                "replace_all": False,
                "evidence_refs": [],
            },
            {
                "file_path": "scheduler.py",
                "action": "modify",
                "edit_intent": "exact_replace",
                "old_string": "repair_ops = [greedy]\n",
                "new_string": "repair_ops = [greedy, ejection_chain]\n",
                "replace_all": False,
                "evidence_refs": [],
            },
        ],
    }


def test_provider_schema_omits_host_source_binding_fields() -> None:
    schema = PATCH_TOOL["input_schema"]

    assert "source_digest" not in schema["properties"]
    assert "source_digest" not in schema["properties"]["additional_changes"][
        "items"
    ]["properties"]
    assert "source_digest" not in PATCH_TOOL["description"]
    assert "provenance" not in PATCH_TOOL["description"]


def test_parser_derives_source_bindings_for_digest_free_provider_edits() -> None:
    target = "from .state import Route\n\n\ndef greedy():\n    return 1\n"
    scheduler = (
        "from .destroy_repair import greedy\n\n\n"
        "repair_ops = [greedy]\n"
    )

    patch = _parse_patch(
        _serial_patch(target, scheduler),
        context={"proposal_source_ledger": _source_ledger(target, scheduler)},
    )

    bindings = {
        (
            item["file_path"],
            item["source_digest"],
            item["source_owner"],
            item["source_provenance"],
        )
        for item in patch.repair_attribution
        if item.get("action") == "normalized_to_canonical_full_content"
    }
    assert bindings == {
        (
            "destroy_repair.py",
            source_digest_for_content(target),
            "approved_target",
            "champion_snapshot",
        ),
        (
            "scheduler.py",
            source_digest_for_content(scheduler),
            "champion_api_support",
            "champion_snapshot",
        ),
    }


def test_parser_derives_source_binding_for_full_file_modify() -> None:
    target = "from .state import Route\n\n\ndef greedy():\n    return 1\n"
    scheduler = "from .destroy_repair import greedy\n"

    patch = _parse_patch(
        {
            "file_path": "destroy_repair.py",
            "action": "modify",
            "edit_intent": "full_file",
            "content_after": target.replace("return 1", "return 2"),
            "full_file_reason": "Implement the approved algorithm change.",
            "evidence_refs": [],
        },
        context={"proposal_source_ledger": _source_ledger(target, scheduler)},
    )

    binding = next(
        item
        for item in patch.repair_attribution
        if item.get("action") == "normalized_to_canonical_full_content"
    )
    assert binding["source_digest"] == source_digest_for_content(target)
    assert binding["source_owner"] == "approved_target"


def test_parser_rejects_tampered_host_source_ledger() -> None:
    target = "from .state import Route\n\n\ndef greedy():\n    return 1\n"
    scheduler = "from .destroy_repair import greedy\n"
    ledger = _source_ledger(target, scheduler)
    entries = ledger["entries"]
    assert isinstance(entries, list)
    entries[0]["digest"] = "0" * 64

    with pytest.raises(ValueError, match="source ledger digest mismatch"):
        _parse_patch(
            _serial_patch(target, scheduler),
            context={"proposal_source_ledger": ledger},
        )


def test_parser_serially_composes_ordered_same_file_exact_replaces() -> None:
    target = "from .state import Route\n\n\ndef greedy():\n    return 1\n"
    scheduler = (
        "from .destroy_repair import greedy\n\n\n"
        "repair_ops = [greedy]\n"
    )

    patch = _parse_patch(
        _serial_patch(target, scheduler),
        context={"proposal_source_ledger": _source_ledger(target, scheduler)},
    )

    assert patch.file_path == "destroy_repair.py"
    assert "def ejection_chain" in patch.code_content
    assert "Route, route_distance" in patch.code_content
    assert len(patch.additional_changes) == 1
    assert patch.additional_changes[0].file_path == "scheduler.py"
    assert (
        "import ejection_chain, greedy"
        in patch.additional_changes[0].code_content
    )
    assert "[greedy, ejection_chain]" in patch.additional_changes[0].code_content
    compositions = [
        item
        for item in patch.repair_attribution
        if item.get("action") == "composed_serial_exact_replace_changes"
    ]
    assert {item["file_path"] for item in compositions} == {
        "destroy_repair.py",
        "scheduler.py",
    }
    assert {item["merged_change_count"] for item in compositions} == {2}
    assert {item["repair_kind"] for item in compositions} == {
        "typed_edit_normalization"
    }
    assert {item["root_cause"] for item in compositions} == {
        "serial_same_file_exact_replace"
    }


def test_local_exact_replaces_preserve_unmentioned_terminal_return() -> None:
    target = (
        "def improve(solution):\n"
        "    best = solution\n"
        "    operators = [two_opt]\n"
        "    for operator in operators:\n"
        "        best = operator(best)\n"
        "    return best\n"
    )
    scheduler = "from .destroy_repair import improve\n"

    patch = _parse_patch(
        {
            "file_path": "destroy_repair.py",
            "action": "modify",
            "edit_intent": "exact_replace",
            "old_string": "    operators = [two_opt]\n",
            "new_string": "    operators = [two_opt, relocate]\n",
            "replace_all": False,
            "evidence_refs": [],
            "additional_changes": [
                {
                    "file_path": "destroy_repair.py",
                    "action": "modify",
                    "edit_intent": "exact_replace",
                    "old_string": (
                        "    operators = [two_opt, relocate]\n"
                        "    for operator in operators:\n"
                    ),
                    "new_string": (
                        "    operators = [two_opt, relocate, swap]\n"
                        "    for operator in operators:\n"
                    ),
                    "replace_all": False,
                    "evidence_refs": [],
                }
            ],
        },
        context={"proposal_source_ledger": _source_ledger(target, scheduler)},
    )

    assert "operators = [two_opt, relocate, swap]" in patch.code_content
    assert patch.code_content.endswith("    return best\n")
    assert patch.code_content.count("    return best\n") == 1


def test_parser_rejects_serial_exact_replaces_in_the_wrong_order() -> None:
    target = "from .state import Route\n\n\ndef greedy():\n    return 1\n"
    scheduler = (
        "from .destroy_repair import greedy\n\n\n"
        "repair_ops = [greedy]\n"
    )
    raw = _serial_patch(target, scheduler)
    additional = raw["additional_changes"]
    assert isinstance(additional, list)
    first = {key: value for key, value in raw.items() if key != "additional_changes"}
    second = additional[0]
    assert isinstance(second, dict)
    raw.update(second)
    raw["additional_changes"] = [first, *additional[1:]]

    with pytest.raises(
        ProposalValidationError,
        match="old_string_not_found",
    ):
        _parse_patch(
            raw,
            context={"proposal_source_ledger": _source_ledger(target, scheduler)},
        )


def test_parser_rejects_stale_digest_in_later_same_file_edit() -> None:
    target = "from .state import Route\n\n\ndef greedy():\n    return 1\n"
    scheduler = (
        "from .destroy_repair import greedy\n\n\n"
        "repair_ops = [greedy]\n"
    )
    raw = _serial_patch(target, scheduler)
    additional = raw["additional_changes"]
    assert isinstance(additional, list)
    second = additional[0]
    assert isinstance(second, dict)
    second["source_digest"] = "0" * 64

    with pytest.raises(ProposalValidationError, match="stale_source"):
        _parse_patch(
            raw,
            context={"proposal_source_ledger": _source_ledger(target, scheduler)},
        )


def test_parser_rejects_same_file_exact_replace_mixed_with_full_file() -> None:
    target = "from .state import Route\n\n\ndef greedy():\n    return 1\n"
    scheduler = (
        "from .destroy_repair import greedy\n\n\n"
        "repair_ops = [greedy]\n"
    )
    raw = _serial_patch(target, scheduler)
    additional = raw["additional_changes"]
    assert isinstance(additional, list)
    additional[0] = {
        "file_path": "destroy_repair.py",
        "action": "modify",
        "edit_intent": "full_file",
        "source_digest": source_digest_for_content(target),
        "content_after": target + "\n# conflicting rewrite\n",
        "full_file_reason": "conflicting same-file rewrite",
        "evidence_refs": [],
    }

    with pytest.raises(
        ProposalValidationError,
        match="mixed_same_file_edit_intents",
    ):
        _parse_patch(
            raw,
            context={"proposal_source_ledger": _source_ledger(target, scheduler)},
        )


def test_parser_rejects_matching_full_file_after_same_file_exact_replace() -> None:
    target = "from .state import Route\n\n\ndef greedy():\n    return 1\n"
    scheduler = (
        "from .destroy_repair import greedy\n\n\n"
        "repair_ops = [greedy]\n"
    )
    raw = _serial_patch(target, scheduler)
    additional = raw["additional_changes"]
    assert isinstance(additional, list)
    content_after_first = (
        "from .state import Route, route_distance\n\n\n"
        "CHAIN_LIMIT = 10\n\n\n"
        "def greedy():\n    return 1\n"
    )
    additional[0] = {
        "file_path": "destroy_repair.py",
        "action": "modify",
        "edit_intent": "full_file",
        "source_digest": source_digest_for_content(target),
        "content_after": content_after_first,
        "full_file_reason": "redundant matching full-file rewrite",
        "evidence_refs": [],
    }

    with pytest.raises(
        ProposalValidationError,
        match="mixed_same_file_edit_intents",
    ):
        _parse_patch(
            raw,
            context={"proposal_source_ledger": _source_ledger(target, scheduler)},
        )
