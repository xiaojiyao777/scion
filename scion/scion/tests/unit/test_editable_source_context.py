from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

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
        selected_surface=None,
        source_root=str(source_root or champion_root),
        target_file="solver.py",
        target_action=action,
        provider=_SourceProvider(),
        editable_patterns=("*.py", "operators/*.py"),
        frozen_patterns=(),
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

    assert "helper.py" not in _by_path(source_context)
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
    assert absent["sources"][0] == {
        "path": "solver.py",
        "content": None,
        "roles": ["target"],
        "visible": True,
    }

    (champion / "solver.py").write_text("")
    existing_empty = _build(champion, action="create_new")
    assert existing_empty["sources"][0] == {
        "path": "solver.py",
        "content": "",
        "roles": ["target"],
        "visible": True,
    }

    (champion / "solver.py").write_text("VALUE = 1\n")
    existing = _build(champion, action="create_new")
    assert existing["sources"][0] == {
        "path": "solver.py",
        "content": "VALUE = 1\n",
        "roles": ["target"],
        "visible": True,
    }


def test_modify_target_without_current_source_is_rejected(tmp_path: Path) -> None:
    champion = tmp_path / "champion"
    champion.mkdir()
    (champion / "helper.py").write_text("HELPER = 1\n")

    with pytest.raises(ValueError, match="modify target has no current source"):
        _build(champion)


def test_selected_surface_symlink_source_is_rejected(tmp_path: Path) -> None:
    champion = tmp_path / "champion"
    champion.mkdir()
    (champion / "solver.py").write_text("VALUE = 1\n")
    outside = tmp_path / "outside.py"
    outside.write_text("SECRET = True\n")
    (champion / "helper.py").symlink_to(outside)

    with pytest.raises(ValueError, match="unreadable"):
        _build(champion)


def test_public_test_is_visible_but_support_is_execution_only(
    tmp_path: Path,
) -> None:
    champion = tmp_path / "champion"
    tests_root = tmp_path / "problem"
    champion.mkdir()
    (champion / "solver.py").write_text("VALUE = 1\n")
    (tests_root / "tests").mkdir(parents=True)
    (tests_root / "data").mkdir()
    (tests_root / "tests/test_public.py").write_text(
        "PUBLIC_TEST_SENTINEL = True\n",
        encoding="utf-8",
    )
    (tests_root / "data/support.json").write_text(
        '"EXECUTION_ONLY_SUPPORT_SENTINEL"\n',
        encoding="utf-8",
    )

    source_context = _build_editable_source_context(
        champion=_champion(champion),
        selected_surface=None,
        source_root=str(champion),
        target_file="solver.py",
        target_action="modify",
        provider=_SourceProvider(),
        editable_patterns=("*.py",),
        frozen_patterns=(),
        development_suites=(
            SimpleNamespace(
                check_name="D3_unit_tests",
                source_root=str(tests_root),
                test_path="tests/test_public.py",
                support_paths=("data/support.json",),
            ),
        ),
    )

    assert source_context["public_tests"] == [
        {
            "path": "tests/test_public.py",
            "content": "PUBLIC_TEST_SENTINEL = True\n",
            "check_name": "D3_unit_tests",
            "visible": True,
        }
    ]
    assert "EXECUTION_ONLY_SUPPORT_SENTINEL" not in str(source_context)


def test_hidden_peer_cannot_bind_a_direct_one_shot_patch() -> None:
    context = _source_context("VALUE = 1\n")
    context["editable_source_context"]["sources"].append(
        {
            "path": "helper.py",
            "content": "HELPER = 1\n",
            "roles": ["peer"],
            "visible": False,
        }
    )

    with pytest.raises(ProposalValidationError, match="source unavailable"):
        _parse_patch(
            {
                "file_path": "helper.py",
                "action": "modify",
                "edit_intent": "exact_replace",
                "old_string": "HELPER = 1",
                "new_string": "HELPER = 2",
                "replace_all": False,
                "evidence_refs": [],
            },
            context=context,
        )


def test_direct_one_shot_patch_cannot_modify_public_test() -> None:
    context = _source_context("VALUE = 1\n")
    context["editable_source_context"]["public_tests"] = [
        {
            "path": "tests/test_public.py",
            "content": "def test_public(): pass\n",
            "check_name": "D3_unit_tests",
            "visible": True,
        }
    ]

    with pytest.raises(ProposalValidationError, match="read-only public"):
        _parse_patch(
            {
                "file_path": "tests/test_public.py",
                "action": "create",
                "edit_intent": "full_file",
                "content_after": "def test_rewritten(): pass\n",
                "full_file_reason": "Try to replace a public test.",
                "evidence_refs": [],
            },
            context=context,
        )


def _source_context(content: str | None):
    return {
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
