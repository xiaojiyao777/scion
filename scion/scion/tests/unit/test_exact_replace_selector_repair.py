from __future__ import annotations

import pytest

from scion.proposal.engine import ProposalValidationError, _parse_patch


def _parse(content: str, old_string: str, new_string: str):
    return _parse_patch(
        {
            "file_path": "solver.py",
            "action": "modify",
            "edit_intent": "exact_replace",
            "old_string": old_string,
            "new_string": new_string,
            "replace_all": False,
        },
        context={
            "editable_source_context": {
                "approved_target": "solver.py",
                "sources": [
                    {
                        "path": "solver.py",
                        "content": content,
                        "roles": ["target"],
                        "visible": True,
                    }
                ],
                "public_tests": [],
                "target_api_guidance": "",
            }
        },
    )


def test_blank_line_count_drift_is_not_repaired() -> None:
    content = "def solve():\n    pending.append(customer)\n\n\ndef helper():\n    return 1\n"
    old = "    pending.append(customer)\n\ndef helper():\n    return 1\n"

    with pytest.raises(ProposalValidationError, match="old_string_not_found"):
        _parse(content, old, old.replace("return 1", "return 2"))


def test_terminal_newline_drift_is_not_repaired() -> None:
    content = "def target():\n    return 1"
    old = "def target():\n    return 1\n"

    with pytest.raises(ProposalValidationError, match="old_string_not_found"):
        _parse(content, old, old.replace("1", "2"))


def test_one_exact_value_is_applied_without_attribution() -> None:
    content = "def target():\n\n    return 1\n"

    patch = _parse(content, content, content.replace("1", "2"))

    assert patch.code_content == content.replace("1", "2")
    assert not hasattr(patch, "repair_attribution")
