from __future__ import annotations

import pytest

from scion.proposal.engine import ProposalValidationError, _parse_patch


def _editable_sources(content: str) -> dict[str, object]:
    return {
        "approved_target": "solver.py",
        "sources": [{"path": "solver.py", "content": content}],
        "target_api_guidance": "",
    }


def _patch(old_string: str, new_string: str, *, replace_all: bool = False):
    return {
        "file_path": "solver.py",
        "action": "modify",
        "edit_intent": "exact_replace",
        "old_string": old_string,
        "new_string": new_string,
        "replace_all": replace_all,
        "evidence_refs": [],
    }


def _parse(content: str, old_string: str, new_string: str, *, replace_all=False):
    return _parse_patch(
        _patch(old_string, new_string, replace_all=replace_all),
        context={"editable_source_context": _editable_sources(content)},
    )


def test_unique_internal_blank_line_run_drift_is_repaired_and_attributed() -> None:
    content = (
        "def solve():\n    pending.append(customer)\n\n\ndef helper():\n    return 1\n"
    )
    old_string = "    pending.append(customer)\n\ndef helper():\n    return 1\n"
    new_string = (
        "    pending.append(customer)\n\n\ndef helper(value=0):\n    return value + 1\n"
    )

    patch = _parse(content, old_string, new_string)

    assert "def helper(value=0):" in patch.code_content
    assert patch.code_content.startswith("def solve():\n")
    normalization = next(
        item
        for item in patch.repair_attribution
        if item.get("action") == "normalized_to_canonical_full_content"
    )
    assert normalization["repair_kind"] == "typed_edit_normalization"
    assert normalization["selector_repair"] == "blank_line_run_count_drift_tolerated"
    assert normalization["blank_line_run_count_tolerated"] is True


def test_exact_match_wins_without_selector_repair() -> None:
    exact = "def target():\n\n    return 1\n"
    tolerant_only = "def target():\n\n\n    return 1\n"
    content = exact + "\n" + tolerant_only

    patch = _parse(
        content,
        exact,
        "def target():\n\n    return 2\n",
    )

    assert patch.code_content.count("return 2") == 1
    assert tolerant_only in patch.code_content
    assert all("selector_repair" not in item for item in patch.repair_attribution)


def test_blank_line_run_repair_is_disabled_for_replace_all() -> None:
    content = "def target():\n\n\n    return 1\n"
    old_string = "def target():\n\n    return 1\n"

    with pytest.raises(ProposalValidationError, match="old_string_not_found"):
        _parse(content, old_string, old_string.replace("1", "2"), replace_all=True)


def test_ambiguous_blank_line_run_candidates_fail_closed() -> None:
    content = "def target():\n\n    return 1\n\ndef target():\n\n\n\n    return 1\n"
    old_string = "def target():\n\n\n    return 1\n"

    with pytest.raises(ProposalValidationError, match="old_string_not_found"):
        _parse(content, old_string, old_string.replace("1", "2"))


@pytest.mark.parametrize(
    ("content", "old_string"),
    [
        (
            "def target():\n\n\n    value = 'a b'\n",
            "def target():\n\n    value = 'a  b'\n",
        ),
        (
            "def target():\n\n\n    return 1\n",
            "def target():\n\n  return 1\n",
        ),
        (
            "def target():\n    return 1\n",
            "def target():\n\n    return 1\n",
        ),
        (
            "def target():\n   \n\n    return 1\n",
            "def target():\n\n    return 1\n",
        ),
    ],
)
def test_non_blank_or_non_run_drift_is_not_repaired(
    content: str,
    old_string: str,
) -> None:
    with pytest.raises(ProposalValidationError, match="old_string_not_found"):
        _parse(content, old_string, old_string.replace("return 1", "return 2"))
