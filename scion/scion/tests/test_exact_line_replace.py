from __future__ import annotations

import pytest
from scion.proposal.engine import ProposalValidationError, _parse_patch
from scion.proposal.schemas import PATCH_TOOL


def _context(source: str) -> dict[str, object]:
    return {
        "editable_source_context": {
            "approved_target": "solver.py",
            "sources": [
                {
                    "path": "solver.py",
                    "content": source,
                    "roles": ["target"],
                    "visible": True,
                }
            ],
            "public_tests": [],
            "target_api_guidance": "",
        }
    }


def _change(
    *,
    old_string: str = "annealing.cool()",
    new_string: str = "annealing.update(elapsed_fraction)",
    replace_all: bool = False,
) -> dict[str, object]:
    return {
        "file_path": "solver.py",
        "action": "modify",
        "edit_intent": "exact_line_replace",
        "old_string": old_string,
        "new_string": new_string,
        "replace_all": replace_all,
        "evidence_refs": [],
    }


def test_exact_line_replace_replays_relative_block_at_every_outer_indent() -> None:
    source = "def solve():\n    annealing.cool()\n    if retry:\n\t\tannealing.cool()\n"

    patch = _parse_patch(
        _change(
            new_string=(
                "elapsed = budget.fraction()\n"
                "if elapsed < 1.0:\n"
                "    annealing.update(elapsed)"
            ),
            replace_all=True,
        ),
        context=_context(source),
    )

    assert patch.code_content == (
        "def solve():\n"
        "    elapsed = budget.fraction()\n"
        "    if elapsed < 1.0:\n"
        "        annealing.update(elapsed)\n"
        "    if retry:\n"
        "\t\telapsed = budget.fraction()\n"
        "\t\tif elapsed < 1.0:\n"
        "\t\t    annealing.update(elapsed)\n"
    )
    assert not hasattr(patch, "repair_attribution")


def test_exact_line_replace_requires_unique_match_unless_replace_all() -> None:
    source = "    annealing.cool()\n        annealing.cool()\n"

    with pytest.raises(ProposalValidationError, match="old_line_not_unique"):
        _parse_patch(_change(), context=_context(source))


def test_exact_line_replace_fails_when_complete_line_is_absent() -> None:
    source = "    before_annealing.cool()\n    annealing.cool()  \n"

    with pytest.raises(ProposalValidationError, match="old_line_not_found"):
        _parse_patch(_change(replace_all=True), context=_context(source))


@pytest.mark.parametrize(
    ("old_string", "new_string", "reason"),
    [
        (
            "    annealing.cool()",
            "annealing.update(elapsed)",
            "exact_line_replace_indented_old_string",
        ),
        (
            "annealing.cool()\n",
            "annealing.update(elapsed)",
            "exact_line_replace_multiline_old_string",
        ),
        (
            "annealing.cool()",
            "first()\r\nsecond()",
            "exact_line_replace_cr_in_new_string",
        ),
        (
            "annealing.cool()",
            "annealing.update(elapsed)\n",
            "exact_line_replace_terminal_lf_in_new_string",
        ),
    ],
)
def test_exact_line_replace_rejects_noncanonical_wire_shapes(
    old_string: str,
    new_string: str,
    reason: str,
) -> None:
    with pytest.raises(ProposalValidationError, match=reason):
        _parse_patch(
            _change(old_string=old_string, new_string=new_string),
            context=_context("    annealing.cool()\n"),
        )


def test_exact_line_replace_preserves_each_source_eol_and_blanks_whitespace() -> None:
    source = "  annealing.cool()\r\n\tannealing.cool()\n    annealing.cool()\r"

    patch = _parse_patch(
        _change(new_string="first()\n   \n\tsecond()", replace_all=True),
        context=_context(source),
    )

    assert patch.code_content == (
        "  first()\r\n\r\n  \tsecond()\r\n"
        "\tfirst()\n\n\t\tsecond()\n"
        "    first()\r\r    \tsecond()\r"
    )


def test_exact_line_replace_supports_single_line_unterminated_eof() -> None:
    source = "def solve():\n    annealing.cool()"

    patch = _parse_patch(_change(), context=_context(source))

    assert patch.code_content == (
        "def solve():\n    annealing.update(elapsed_fraction)"
    )


def test_exact_line_replace_rejects_multiline_replacement_at_unterminated_eof() -> None:
    source = "def solve():\n    annealing.cool()"

    with pytest.raises(ProposalValidationError, match="unterminated EOF line"):
        _parse_patch(
            _change(new_string="first()\nsecond()"),
            context=_context(source),
        )


def test_exact_line_replace_deletes_the_matched_line_including_its_eol() -> None:
    source = "def solve():\n    annealing.cool()\n    return best\n"

    patch = _parse_patch(
        _change(new_string=""),
        context=_context(source),
    )

    assert patch.code_content == "def solve():\n    return best\n"


def test_exact_line_replace_rejects_empty_whole_file_modify() -> None:
    with pytest.raises(
        ProposalValidationError,
        match="use action='delete' to delete the file",
    ):
        _parse_patch(
            _change(new_string=""),
            context=_context("annealing.cool()\n"),
        )


def test_exact_line_replace_rejects_whitespace_only_whole_file_modify() -> None:
    with pytest.raises(
        ProposalValidationError,
        match="use action='delete' to delete the file",
    ):
        _parse_patch(
            _change(new_string=""),
            context=_context("\nannealing.cool()\n"),
        )


def test_exact_line_replace_matches_snapshot_without_recursing_into_replacement() -> (
    None
):
    patch = _parse_patch(
        _change(new_string="annealing.cool()\nrecord_update()", replace_all=True),
        context=_context("annealing.cool()\n"),
    )

    assert patch.code_content == "annealing.cool()\nrecord_update()\n"
    assert patch.code_content.count("annealing.cool()") == 1


def test_exact_line_replace_rejects_duplicate_same_file_change() -> None:
    source = "def solve():\n    annealing.cool()\n    return best\n"
    raw = _change(new_string="annealing.update(elapsed)")
    raw["additional_changes"] = [
        {
            "file_path": "solver.py",
            "action": "modify",
            "edit_intent": "exact_replace",
            "old_string": ("    annealing.update(elapsed)\n    return best\n"),
            "new_string": ("    annealing.update(elapsed)\n    return incumbent\n"),
            "replace_all": False,
            "evidence_refs": [],
        }
    ]

    with pytest.raises(ProposalValidationError, match="duplicate file_path"):
        _parse_patch(raw, context=_context(source))


def test_three_same_file_changes_are_rejected_instead_of_composed() -> None:
    source = "def solve():\n    annealing.cool()\n    return best\n"
    raw: dict[str, object] = {
        "file_path": "solver.py",
        "action": "modify",
        "edit_intent": "exact_replace",
        "old_string": "def solve():\n",
        "new_string": "def solve(budget):\n",
        "replace_all": False,
        "evidence_refs": [],
        "additional_changes": [
            _change(new_string="annealing.update(budget.fraction())"),
            {
                "file_path": "solver.py",
                "action": "modify",
                "edit_intent": "exact_replace",
                "old_string": "    return best\n",
                "new_string": "    return incumbent\n",
                "replace_all": False,
                "evidence_refs": [],
            },
        ],
    }

    with pytest.raises(ProposalValidationError, match="duplicate file_path"):
        _parse_patch(raw, context=_context(source))


def test_duplicate_path_fails_before_second_selector_is_considered() -> None:
    source = "def solve():\n    annealing.cool()\n"
    raw: dict[str, object] = {
        "file_path": "solver.py",
        "action": "modify",
        "edit_intent": "exact_replace",
        "old_string": "    annealing.cool()\n",
        "new_string": "    annealing.update(elapsed)\n",
        "replace_all": False,
        "additional_changes": [_change()],
    }

    with pytest.raises(
        ProposalValidationError,
        match="duplicate file_path",
    ):
        _parse_patch(raw, context=_context(source))


def test_exact_line_replace_does_not_match_substrings_or_trailing_drift() -> None:
    source = (
        '    message = "annealing.cool()"\n'
        "    # annealing.cool()\n"
        "    prefix_annealing.cool()\n    annealing.cool()  \n    annealing.cool()\n"
    )

    patch = _parse_patch(_change(), context=_context(source))

    assert patch.code_content == (
        '    message = "annealing.cool()"\n'
        "    # annealing.cool()\n"
        "    prefix_annealing.cool()\n"
        "    annealing.cool()  \n"
        "    annealing.update(elapsed_fraction)\n"
    )


def test_patch_tool_exposes_exact_line_replace_contract() -> None:
    schema = PATCH_TOOL["input_schema"]

    assert "exact_line_replace" in schema["properties"]["edit_intent"]["enum"]
    assert (
        "exact_line_replace"
        in (
            schema["properties"]["additional_changes"]["items"]["properties"][
                "edit_intent"
            ]["enum"]
        )
    )
    for phrase in (
        "complete logical-line body",
        "unindented",
        "relative-indentation block",
        "without a terminal newline",
    ):
        assert phrase in PATCH_TOOL["description"]
