"""Typed code-edit protocol normalization tests."""

from __future__ import annotations

import pytest

from scion.proposal.edit_protocol import (
    normalize_patch_typed_edits,
    source_digest_for_content,
)
from scion.proposal.engine import ProposalValidationError, _parse_patch
from scion.proposal.engine.code_prompts import _split_code_context


def test_exact_replace_normalizes_to_content_after_and_patch_content() -> None:
    before = "def value():\n    return 1\n"
    digest = source_digest_for_content(before)
    raw = {
        "file_path": "policies/example.py",
        "action": "modify",
        "edit_intent": "exact_replace",
        "source_digest": digest,
        "old_string": "return 1",
        "new_string": "return 2",
        "replace_all": False,
        "evidence_refs": ["obs-target"],
    }
    context = {
        "target_file": "policies/example.py",
        "target_file_code": before,
    }

    normalized, attribution = normalize_patch_typed_edits(raw, context=context)
    patch = _parse_patch(raw, context=context)

    assert normalized["content_after"] == "def value():\n    return 2\n"
    assert normalized["code_content"] == normalized["content_after"]
    assert patch.code_content == normalized["content_after"]
    assert attribution[0]["edit_intent"] == "exact_replace"
    assert attribution[0]["derived_diff_ref"].startswith("typed-edit-diff:")
    assert attribution[0]["evidence_refs"] == ["obs-target"]


def test_exact_replace_rejects_stale_source_digest() -> None:
    before = "VALUE = 1\n"
    stale_digest = source_digest_for_content("VALUE = 0\n")

    with pytest.raises(ProposalValidationError, match="stale_source"):
        _parse_patch(
            {
                "file_path": "policies/example.py",
                "action": "modify",
                "edit_intent": "exact_replace",
                "source_digest": stale_digest,
                "old_string": "VALUE = 1",
                "new_string": "VALUE = 2",
            },
            context={
                "target_file": "policies/example.py",
                "target_file_code": before,
            },
        )


def test_additional_changes_accept_typed_exact_replace() -> None:
    helper_before = "def helper():\n    return 'old'\n"
    raw = {
        "file_path": "policies/main.py",
        "action": "modify",
        "code_content": "def solve():\n    return helper()\n",
        "additional_changes": [
            {
                "file_path": "policies/helper.py",
                "action": "modify",
                "edit_intent": "exact_replace",
                "source_digest": source_digest_for_content(helper_before),
                "old_string": "return 'old'",
                "new_string": "return 'new'",
            }
        ],
    }

    patch = _parse_patch(
        raw,
        context={
            "target_file": "policies/main.py",
            "target_file_code": "def solve():\n    return None\n",
            "patch_source_files": {"policies/helper.py": helper_before},
        },
    )

    assert len(patch.additional_changes) == 1
    assert patch.additional_changes[0].code_content == (
        "def helper():\n    return 'new'\n"
    )
    assert any(
        item.get("json_pointer") == "/additional_changes/0"
        and item.get("edit_intent") == "exact_replace"
        for item in patch.repair_attribution
    )


def test_duplicate_additional_exact_replace_changes_are_composed() -> None:
    scheduler_before = "def schedule():\n    window = 4\n    penalty = 1\n"
    scheduler_path = "policies/baseline_modules/scheduler.py"
    digest = source_digest_for_content(scheduler_before)
    raw = {
        "file_path": "policies/main.py",
        "action": "modify",
        "code_content": "def solve():\n    return None\n",
        "additional_changes": [
            {
                "file_path": scheduler_path,
                "action": "modify",
                "edit_intent": "exact_replace",
                "source_digest": digest,
                "old_string": "window = 4",
                "new_string": "window = 5",
                "evidence_refs": ["scheduler-window"],
            },
            {
                "file_path": scheduler_path,
                "action": "modify",
                "edit_intent": "exact_replace",
                "source_digest": digest,
                "old_string": "penalty = 1",
                "new_string": "penalty = 2",
                "evidence_refs": ["scheduler-penalty"],
            },
        ],
    }

    patch = _parse_patch(
        raw,
        context={"patch_source_files": {scheduler_path: scheduler_before}},
    )

    assert len(patch.additional_changes) == 1
    assert patch.additional_changes[0].file_path == scheduler_path
    assert patch.additional_changes[0].code_content == (
        "def schedule():\n    window = 5\n    penalty = 2\n"
    )
    assert any(
        item.get("repair_kind") == "patch_set_composition"
        and item.get("file_path") == scheduler_path
        and item.get("source_json_pointers")
        == ["/additional_changes/0", "/additional_changes/1"]
        for item in patch.repair_attribution
    )


def test_duplicate_full_file_conflict_is_rejected_before_schema_loop() -> None:
    helper_path = "policies/baseline_modules/helper.py"
    raw = {
        "file_path": "policies/main.py",
        "action": "modify",
        "code_content": "def solve():\n    return None\n",
        "additional_changes": [
            {
                "file_path": helper_path,
                "action": "modify",
                "edit_intent": "full_file",
                "content_after": "VALUE = 1\n",
            },
            {
                "file_path": helper_path,
                "action": "modify",
                "edit_intent": "full_file",
                "content_after": "VALUE = 2\n",
            },
        ],
    }

    with pytest.raises(ProposalValidationError) as excinfo:
        _parse_patch(raw)

    message = str(excinfo.value)
    assert "patch_edit_protocol" in message
    assert "full_file_conflict" in message
    assert "/additional_changes/1" in message
    assert "additional_changes must not repeat file_path" not in message


def test_primary_and_additional_same_file_exact_replace_are_composed() -> None:
    target_before = "VALUE = 1\nLIMIT = 3\n"
    digest = source_digest_for_content(target_before)
    target_path = "policies/baseline_modules/scheduler.py"
    raw = {
        "file_path": target_path,
        "action": "modify",
        "edit_intent": "exact_replace",
        "source_digest": digest,
        "old_string": "VALUE = 1",
        "new_string": "VALUE = 2",
        "additional_changes": [
            {
                "file_path": target_path,
                "action": "modify",
                "edit_intent": "exact_replace",
                "source_digest": digest,
                "old_string": "LIMIT = 3",
                "new_string": "LIMIT = 4",
            }
        ],
    }

    patch = _parse_patch(
        raw,
        context={
            "target_file": target_path,
            "target_file_code": target_before,
        },
    )

    assert patch.file_path == target_path
    assert patch.additional_changes == ()
    assert patch.code_content == "VALUE = 2\nLIMIT = 4\n"
    assert any(
        item.get("repair_kind") == "patch_set_composition"
        and item.get("canonical_json_pointer") == "/"
        and item.get("source_json_pointers") == ["/", "/additional_changes/0"]
        for item in patch.repair_attribution
    )


def test_full_file_fallback_remains_compatible() -> None:
    legacy = _parse_patch(
        {
            "file_path": "policies/example.py",
            "action": "modify",
            "code_content": "VALUE = 3\n",
        }
    )
    typed = _parse_patch(
        {
            "file_path": "policies/example.py",
            "action": "modify",
            "edit_intent": "full_file",
            "content_after": "VALUE = 4\n",
        }
    )

    assert legacy.code_content == "VALUE = 3\n"
    assert legacy.repair_attribution == ()
    assert typed.code_content == "VALUE = 4\n"


def test_rendered_code_prompt_prefers_typed_edits_not_mandatory_full_file() -> None:
    _, prompt = _split_code_context(
        {
            "problem_summary": "Example problem",
            "hypothesis_detail": "Change one constant.",
            "target_file": "policies/example.py",
            "target_file_code": "VALUE = 1\n",
            "operator_interface_spec": "Expose module constants.",
            "import_whitelist": "- math",
            "editable_patterns": "policies/*.py",
            "frozen_patterns": "data/**",
        }
    )

    assert "Prefer `edit_intent: exact_replace`" in prompt
    assert "Do not emit unified diffs" in prompt
    assert '"code_content": "<complete file contents>"' not in prompt
    assert "code_content" not in prompt or "Legacy `code_content`" in prompt
