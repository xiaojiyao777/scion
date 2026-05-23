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
