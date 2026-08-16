from __future__ import annotations

from pathlib import Path

import pytest

from scion.core.models import ChampionState
from scion.proposal.context_manager.code_context import (
    _build_editable_source_context,
)
from scion.proposal.edit_protocol.source_discovery import (
    source_files_from_context,
)
from scion.proposal.engine import ProposalValidationError, _parse_patch


class _SourceProvider:
    def solver_design_api_manifest_files(self):
        return ("solver.py", "helper.py")

    def solver_design_integration_full_files(self):
        return ("solver.py", "helper.py")

    def solver_design_integration_summary_files(self):
        return ()

    def solver_design_target_api_guidance(self, target_file: str):
        return f"Keep {target_file} callable."


def _champion(root: Path) -> ChampionState:
    return ChampionState(
        version=1,
        operator_pool={},
        code_snapshot_path=str(root),
    )


def _build(
    champion_root: Path,
    *,
    source_root: Path | None = None,
    action: str = "modify",
):
    return _build_editable_source_context(
        champion=_champion(champion_root),
        research_surfaces=[],
        source_root=str(source_root or champion_root),
        target_file="solver.py",
        target_action=action,
        provider=_SourceProvider(),
    )


def _by_path(source_context):
    return {source["path"]: source["content"] for source in source_context["sources"]}


def test_editable_source_context_prefers_branch_workspace_over_champion(
    tmp_path: Path,
) -> None:
    champion = tmp_path / "champion"
    branch = tmp_path / "branch"
    champion.mkdir()
    branch.mkdir()
    (champion / "solver.py").write_text("VALUE = 'champion'\n")
    (champion / "helper.py").write_text("HELPER = 'champion'\n")
    (branch / "solver.py").write_text("VALUE = 'branch'\n")
    (branch / "helper.py").write_text("HELPER = 'branch'\n")

    source_context = _build(
        champion,
        source_root=branch,
    )

    assert _by_path(source_context) == {
        "solver.py": "VALUE = 'branch'\n",
        "helper.py": "HELPER = 'branch'\n",
    }
    assert [source["path"] for source in source_context["sources"]] == [
        "solver.py",
        "helper.py",
    ]


def test_current_source_tree_never_falls_back_to_champion(
    tmp_path: Path,
) -> None:
    champion = tmp_path / "champion"
    branch = tmp_path / "branch"
    champion.mkdir()
    branch.mkdir()
    (champion / "solver.py").write_text("VALUE = 1\n")
    (champion / "helper.py").write_text("STALE = True\n")
    (branch / "solver.py").write_text("VALUE = 2\n")

    source_context = _build(
        champion,
        source_root=branch,
    )

    assert _by_path(source_context)["helper.py"] is None
    assert source_files_from_context({"editable_source_context": source_context}) == {
        "solver.py": "VALUE = 2\n"
    }

    champion_context = _build(champion)
    assert _by_path(champion_context)["helper.py"] == "STALE = True\n"


def test_current_workspace_created_operator_is_discovered_without_history(
    tmp_path: Path,
) -> None:
    champion = tmp_path / "champion"
    branch = tmp_path / "branch"
    champion.mkdir()
    branch.mkdir()
    (champion / "solver.py").write_text("VALUE = 'champion'\n")
    (champion / "helper.py").write_text("HELPER = 'champion'\n")
    (branch / "solver.py").write_text("VALUE = 'branch'\n")
    (branch / "helper.py").write_text("HELPER = 'branch'\n")
    (branch / "operators").mkdir()
    (branch / "operators" / "new_operator.py").write_text("ENABLED = True\n")

    source_context = _build(champion, source_root=branch)

    assert _by_path(source_context)["operators/new_operator.py"] == "ENABLED = True\n"


def test_create_target_distinguishes_absent_existing_and_empty(
    tmp_path: Path,
) -> None:
    champion = tmp_path / "champion"
    champion.mkdir()
    (champion / "helper.py").write_text("HELPER = 1\n")

    absent = _build(champion, action="create_new")
    assert absent["sources"][0] == {"path": "solver.py", "content": None}

    (champion / "solver.py").write_text("")
    existing_empty = _build(champion, action="create_new")
    assert existing_empty["sources"][0] == {"path": "solver.py", "content": ""}

    (champion / "solver.py").write_text("VALUE = 1\n")
    existing = _build(champion, action="create_new")
    assert existing["sources"][0] == {
        "path": "solver.py",
        "content": "VALUE = 1\n",
    }


def test_modify_target_without_current_source_is_rejected(tmp_path: Path) -> None:
    champion = tmp_path / "champion"
    champion.mkdir()
    (champion / "helper.py").write_text("HELPER = 1\n")

    with pytest.raises(ValueError, match="modify target has no current source"):
        _build(champion)


def _source_context(content: str | None):
    return {
        "editable_source_context": {
            "approved_target": "solver.py",
            "sources": [{"path": "solver.py", "content": content}],
            "target_api_guidance": "",
        }
    }


def test_full_file_create_succeeds_for_absent_target() -> None:
    patch = _parse_patch(
        {
            "file_path": "solver.py",
            "action": "create",
            "edit_intent": "full_file",
            "content_after": "VALUE = 1\n",
            "full_file_reason": "Create the approved research target.",
            "evidence_refs": [],
        },
        context=_source_context(None),
    )

    assert patch.action == "create"
    assert patch.code_content == "VALUE = 1\n"


@pytest.mark.parametrize("content", ["", "VALUE = 1\n"])
def test_create_rejects_existing_current_source(content: str) -> None:
    with pytest.raises(ProposalValidationError, match="already exists"):
        _parse_patch(
            {
                "file_path": "solver.py",
                "action": "create",
                "edit_intent": "full_file",
                "content_after": "VALUE = 2\n",
                "full_file_reason": "Create the approved research target.",
                "evidence_refs": [],
            },
            context=_source_context(content),
        )


@pytest.mark.parametrize("edit_intent", ["exact_replace", "full_file"])
def test_modify_rejects_absent_source(edit_intent: str) -> None:
    change = {
        "file_path": "solver.py",
        "action": "modify",
        "edit_intent": edit_intent,
        "evidence_refs": [],
    }
    if edit_intent == "exact_replace":
        change.update(
            {
                "old_string": "VALUE = 1\n",
                "new_string": "VALUE = 2\n",
                "replace_all": False,
            }
        )
        error = "source unavailable"
    else:
        change.update(
            {
                "content_after": "VALUE = 2\n",
                "full_file_reason": "Implement the approved research change.",
            }
        )
        error = "source unavailable"

    with pytest.raises(ProposalValidationError, match=error):
        _parse_patch(change, context=_source_context(None))
