from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from scion.core.code_research_limits import CodeResearchLimits
from scion.core.models import Branch, BranchState, ChampionState, HypothesisProposal
from scion.proposal.code_research_session import CodeResearchSession
from scion.proposal.context_manager import ContextManager
from scion.proposal.context_manager.code_context import (
    _build_editable_source_context,
)
from scion.proposal.context_manager.source_graph import source_graph_roles
from scion.proposal.engine import (
    CreativeLayer,
    ProposalValidationError,
    build_prompt_turn_snapshot,
)
from scion.proposal.engine.code_prompts import _split_code_context
from scion.verification.development import (
    declared_development_suites,
    validate_development_closure_boundary,
)


def _champion(root: Path) -> ChampionState:
    return ChampionState(version=1, operator_pool={}, code_snapshot_path=str(root))


def test_initial_graph_prompt_is_selected_current_source_plus_public_tests_only(
    tmp_path: Path,
) -> None:
    root = tmp_path / "current"
    (root / "pkg").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "support").mkdir()
    (root / "data").mkdir()
    (root / "history").mkdir()
    (root / "pkg/main.py").write_text(
        "from pkg.dep import DEP\nTARGET_MARKER = DEP\n", encoding="utf-8"
    )
    (root / "pkg/dep.py").write_text("DEP = 'DEPENDENCY_MARKER'\n", encoding="utf-8")
    (root / "pkg/caller.py").write_text(
        "from pkg.main import TARGET_MARKER\nCALLER_MARKER = TARGET_MARKER\n",
        encoding="utf-8",
    )
    (root / "pkg/peer.py").write_text("PEER_SECRET_MARKER = True\n", encoding="utf-8")
    (root / "pkg/frozen.py").write_text(
        "FROZEN_SECRET_MARKER = True\n", encoding="utf-8"
    )
    (root / "tests/public.py").write_text(
        "PUBLIC_DEVELOPMENT_MARKER = True\n", encoding="utf-8"
    )
    (root / "support/runtime.py").write_text(
        "HOST_ONLY_SUPPORT_MARKER = True\n", encoding="utf-8"
    )
    (root / "data/canary.json").write_text(
        '{"CANARY_SECRET_MARKER": true}\n', encoding="utf-8"
    )
    (root / "history/patch.py").write_text(
        "HISTORY_PATCH_SECRET_MARKER = True\n", encoding="utf-8"
    )

    class _LegacyManifestProvider:
        def solver_design_api_manifest_files(self) -> tuple[str, ...]:
            return ("support/runtime.py",)

        def solver_design_target_api_guidance(self, _target: str) -> str:
            return "PUBLIC_TARGET_GUIDANCE"

    surface = SimpleNamespace(targets=SimpleNamespace(files=["pkg/*.py"]))
    suite = SimpleNamespace(
        check_name="D3_unit_tests",
        source_root=str(root),
        test_path="tests/public.py",
        support_paths=("support/runtime.py",),
    )
    source_context = _build_editable_source_context(
        champion=_champion(root),
        selected_surface=surface,
        source_root=str(root),
        target_file="pkg/main.py",
        target_action="modify",
        provider=_LegacyManifestProvider(),
        editable_patterns=("pkg/*.py",),
        frozen_patterns=("pkg/frozen.py",),
        development_suites=(suite,),
    )

    records = {record["path"]: record for record in source_context["sources"]}
    assert records["pkg/main.py"]["roles"] == ["target"]
    assert records["pkg/dep.py"]["roles"] == ["dependency"]
    assert records["pkg/caller.py"]["roles"] == ["caller"]
    assert records["pkg/peer.py"]["roles"] == ["peer"]
    assert records["pkg/peer.py"]["visible"] is False
    assert "pkg/frozen.py" not in records

    blocks, prompt = _split_code_context(
        {
            "approved_hypothesis": {"hypothesis_text": "bounded change"},
            "editable_source_context": source_context,
        }
    )
    rendered = "\n".join(str(block.get("text") or "") for block in blocks) + prompt
    for marker in (
        "TARGET_MARKER",
        "DEPENDENCY_MARKER",
        "CALLER_MARKER",
        "PUBLIC_DEVELOPMENT_MARKER",
        "PUBLIC_TARGET_GUIDANCE",
    ):
        assert marker in rendered
    for marker in (
        "PEER_SECRET_MARKER",
        "FROZEN_SECRET_MARKER",
        "HOST_ONLY_SUPPORT_MARKER",
        "CANARY_SECRET_MARKER",
        "HISTORY_PATCH_SECRET_MARKER",
    ):
        assert marker not in rendered


@pytest.mark.parametrize(
    "sources, error",
    [
        (
            {"pkg/main.py": "def broken(:\n"},
            "cannot parse current editable source",
        ),
        (
            {"pkg/main.py": "from ...escape import value\n"},
            "relative import escapes",
        ),
        (
            {"pkg.py": "VALUE = 1\n", "pkg/__init__.py": "VALUE = 2\n"},
            "duplicate local source module",
        ),
    ],
)
def test_source_graph_invalid_or_ambiguous_inputs_fail_closed(
    sources: dict[str, str], error: str
) -> None:
    target = next(iter(sources))
    with pytest.raises(ValueError, match=error):
        source_graph_roles(sources, target=target)


@pytest.mark.parametrize("workspace_kind", ["missing", "symlink"])
def test_branch_current_never_falls_back_to_champion(
    tmp_path: Path, workspace_kind: str
) -> None:
    champion_root = tmp_path / "champion"
    champion_root.mkdir()
    (champion_root / "target.py").write_text(
        "CHAMPION_SECRET_MARKER = True\n", encoding="utf-8"
    )
    workspace = tmp_path / "branch"
    if workspace_kind == "symlink":
        workspace.symlink_to(champion_root, target_is_directory=True)

    branch = Branch(
        branch_id="branch",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        current_code_hash="accepted-current",
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="create a current target",
        change_locus="surface",
        action="create_new",
        target_file="new.py",
    )
    problem_spec = SimpleNamespace(
        research_surfaces=[],
        search_space=SimpleNamespace(editable=["*.py"], frozen=[]),
    )

    with pytest.raises(ValueError):
        ContextManager().build_code_context(
            branch=branch,
            hypothesis=hypothesis,
            champion=_champion(champion_root),
            problem_spec=problem_spec,
            branch_workspace=str(workspace),
        )


class _SequenceClient:
    model = "fake-stage5-redteam"

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = list(responses)

    def call_with_tool(
        self,
        _prompt: str,
        _tool: dict[str, Any],
        _model: str,
        *,
        system_blocks: list[dict[str, Any]],
        request_kind: str,
    ) -> dict[str, Any]:
        del system_blocks, request_kind
        return deepcopy(self._responses.pop(0))


def _research_snapshot():
    return build_prompt_turn_snapshot(
        "code",
        {
            "problem_summary": "Generic optimization subject.",
            "branch_id": "stage5-redteam",
            "approved_hypothesis": {"hypothesis_text": "revise one peer"},
            "editable_source_context": {
                "approved_target": "pkg/main.py",
                "sources": [
                    {
                        "path": "pkg/main.py",
                        "content": "MAIN = True\n",
                        "roles": ["target"],
                        "visible": True,
                    },
                    {
                        "path": "pkg/peer.py",
                        "content": "VALUE = 1\n",
                        "roles": ["peer"],
                        "visible": False,
                    },
                ],
                "public_tests": [
                    {
                        "path": "tests/public.py",
                        "content": "def test_public():\n    assert True\n",
                        "check_name": "D3_unit_tests",
                        "visible": True,
                    }
                ],
                "target_api_guidance": "",
            },
            "operator_interface_spec": "",
            "editable_patterns": ["pkg/*.py"],
            "frozen_patterns": [],
        },
    )


def test_peer_becomes_editable_only_after_read_and_public_test_stays_read_only() -> None:
    peer_patch = {
        "file_path": "pkg/peer.py",
        "action": "modify",
        "edit_intent": "exact_replace",
        "old_string": "VALUE = 1",
        "new_string": "VALUE = 2",
        "replace_all": False,
        "evidence_refs": [],
    }
    client = _SequenceClient(
        [
            {"action": "read_source", "path": "pkg/peer.py"},
            {"action": "revise", "patch": peer_patch},
            {"action": "test_patch"},
            {"action": "ready"},
            {"outcome": "finalize_patch"},
        ]
    )
    session = CodeResearchSession(
        CreativeLayer(client),
        CodeResearchLimits(max_turns=4),
        test_patch=lambda _patch, _remaining, _corpus: {
            "outcome": "passed",
            "checks": [{"name": "D3_unit_tests", "outcome": "passed"}],
            "counts": {"total": 1, "passed": 1, "failed": 0},
        },
    )
    result = session.run(_research_snapshot())
    assert result.file_path == "pkg/peer.py"
    assert result.code_content == "VALUE = 2\n"

    public_patch = {
        **peer_patch,
        "file_path": "tests/public.py",
        "old_string": "assert True",
        "new_string": "assert False",
    }
    public_client = _SequenceClient([{"action": "revise", "patch": public_patch}])
    public_session = CodeResearchSession(
        CreativeLayer(public_client), CodeResearchLimits(max_turns=1)
    )
    with pytest.raises(ProposalValidationError, match="read-only public"):
        public_session.run(_research_snapshot())


def test_development_manifest_has_no_formal_fallback_and_rejects_case_alias(
    tmp_path: Path,
) -> None:
    (tmp_path / "formal.py").write_text("FORMAL_MARKER = True\n", encoding="utf-8")
    (tmp_path / "case.json").write_text("{}\n", encoding="utf-8")
    formal_only = SimpleNamespace(
        root_dir=str(tmp_path),
        unit_test_path="formal.py",
        regression_test_path="formal.py",
    )
    assert declared_development_suites(formal_only) == ()

    development = SimpleNamespace(
        root_dir=str(tmp_path),
        development_unit_test_path="case.json",
        development_unit_test_support_paths=(),
        development_regression_test_path="",
        development_regression_test_support_paths=(),
        canary_case_path="case.json",
    )
    suites = declared_development_suites(development)
    with pytest.raises(ValueError, match="overlaps Protocol/canary"):
        validate_development_closure_boundary(
            problem_spec=development,
            suites=suites,
            workspace_paths=(),
            problem_package_paths=(),
            split_manifest=SimpleNamespace(
                screening=(), validation=(), frozen=(), canary=("case.json",)
            ),
            champion_root=None,
        )
