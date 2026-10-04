from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from scion.core.models import Branch, BranchState, ChampionState, HypothesisProposal
from scion.core.problem_runtime import ProblemRuntime
from scion.problem.bridge import legacy_problem_spec_from_v1
from scion.problem.loader import load_problem_adapter, load_problem_spec_v1_from_yaml
from scion.proposal.context_manager import ContextManager
from scion.proposal.context_manager.public_sources import public_support_sources
from scion.proposal.context_snapshot import freeze_proposal_context
from scion.proposal.edit_protocol.source_discovery import (
    all_source_files_from_context,
    read_only_files_from_context,
    research_files_from_context,
)
from scion.proposal.engine import ProposalValidationError, _parse_patch
from scion.proposal.engine.code_prompts import _split_code_context
from scion.proposal.engine.hypothesis_prompts import _split_direct_v3_hypothesis_context
from scion.proposal.hypothesis_research_corpus import build_hypothesis_research_corpus
from scion.verification.development import declared_development_suites

_REPO = Path(__file__).resolve().parents[4]


def _spec(root: Path, *, workspace=(), package=(), frozen=()) -> SimpleNamespace:
    return SimpleNamespace(
        root_dir=str(root),
        development_workspace_paths=list(workspace),
        development_problem_package_paths=list(package),
        canary_case_path="data/private.json",
        search_space=SimpleNamespace(editable=["algorithm/*.py"], frozen=list(frozen)),
    )


def test_public_dependency_roots_follow_development_execution(tmp_path: Path) -> None:
    root, branch = tmp_path / "problem", tmp_path / "branch"
    root.mkdir()
    branch.mkdir()
    (root / "models.py").write_text("WORKSPACE = 'old'\n")
    (branch / "models.py").write_text("WORKSPACE = 'current'\n")
    (root / "runtime.py").write_text("PACKAGE = 'frozen'\n")
    (branch / "runtime.py").write_text("PACKAGE = 'not-used'\n")
    (root / "undeclared.py").write_text("UNDECLARED_SECRET = 1\n")
    spec = _spec(root, workspace=("models.py",), package=("runtime.py",))

    sources = public_support_sources(spec, source_root=str(branch))

    assert sources == [
        {"path": "models.py", "content": "WORKSPACE = 'current'\n", "visible": True},
        {"path": "runtime.py", "content": "PACKAGE = 'frozen'\n", "visible": True},
    ]
    assert "UNDECLARED_SECRET" not in str(sources)


@pytest.mark.parametrize("kind", ["missing", "symlink", "directory", "parent_symlink"])
def test_current_dependency_never_falls_back_or_follows_links(
    tmp_path: Path, kind: str
) -> None:
    root, branch = tmp_path / "problem", tmp_path / "branch"
    (root / "pkg").mkdir(parents=True)
    branch.mkdir()
    (root / "pkg/models.py").write_text("OLD = True\n")
    if kind == "parent_symlink":
        (branch / "pkg").symlink_to(root / "pkg", target_is_directory=True)
    else:
        (branch / "pkg").mkdir()
        if kind == "symlink":
            (branch / "pkg/models.py").symlink_to(root / "pkg/models.py")
        elif kind == "directory":
            (branch / "pkg/models.py").mkdir()
    spec = _spec(root, workspace=("pkg/models.py",))
    with pytest.raises(ValueError, match="unreadable"):
        public_support_sources(spec, source_root=str(branch))


@pytest.mark.parametrize(
    "path", ["../models.py", "/models.py", "pkg/../models.py", "*.py"]
)
def test_public_dependency_requires_exact_canonical_path(
    tmp_path: Path, path: str
) -> None:
    with pytest.raises(ValueError):
        public_support_sources(
            _spec(tmp_path, workspace=(path,)), source_root=str(tmp_path)
        )


@pytest.mark.parametrize("stage", ["screening", "validation", "frozen", "canary"])
@pytest.mark.parametrize("absolute_branch", [False, True])
def test_public_dependency_cannot_alias_formal_case(
    tmp_path: Path, stage: str, absolute_branch: bool
) -> None:
    root, branch = tmp_path / "problem", tmp_path / "branch"
    root.mkdir()
    branch.mkdir()
    for parent in (root, branch):
        (parent / "support.py").write_text("PRIVATE_FORMAL = True\n")
    case = str(branch / "support.py") if absolute_branch else "support.py"
    split = SimpleNamespace(**{stage: [case]})
    with pytest.raises(ValueError, match="overlaps Protocol"):
        public_support_sources(
            _spec(root, workspace=("support.py",)),
            source_root=str(branch),
            split_manifest=split,
        )


def test_dependency_inventory_cannot_alias_editable_or_other_origin(
    tmp_path: Path,
) -> None:
    (tmp_path / "algorithm").mkdir()
    (tmp_path / "algorithm/main.py").write_text("VALUE = 1\n")
    with pytest.raises(ValueError, match="overlaps editable"):
        public_support_sources(
            _spec(tmp_path, workspace=("algorithm/main.py",)), source_root=str(tmp_path)
        )
    with pytest.raises(ValueError, match="alias workspace"):
        public_support_sources(
            _spec(
                tmp_path,
                workspace=("algorithm/main.py",),
                package=("algorithm/main.py",),
            ),
            source_root=str(tmp_path),
        )


@pytest.mark.parametrize("problem", ["warehouse", "cvrp"])
def test_real_problem_direct_and_bounded_context_include_only_declared_dependencies(
    problem: str,
) -> None:
    if problem == "warehouse":
        spec_path = _REPO / "scion/problems/warehouse_delivery/problem-v1.yaml"
        target = "operators/merge_vehicles.py"
    else:
        spec_path = _REPO / "scion/scion/problems/cvrp/problem-v1.yaml"
        target = "policies/baseline_modules/local_search.py"
    spec = load_problem_spec_v1_from_yaml(spec_path)
    adapter = load_problem_adapter(spec)
    legacy = legacy_problem_spec_from_v1(spec)
    champion = ChampionState(
        version=1, operator_pool={}, code_snapshot_path=spec.root_dir
    )
    branch = Branch(
        branch_id="dependency-context", state=BranchState.EXPLORE, base_champion_id=1
    )
    manager = ContextManager(adapter=adapter)
    hypothesis = HypothesisProposal(
        hypothesis_text="Inspect a source-grounded algorithm change.",
        change_locus=spec.research_surfaces[0].name,
        action="modify",
        target_file=target,
    )
    suites = declared_development_suites(spec)
    h = manager.build_hypothesis_context(branch, champion, legacy)
    c = manager.build_code_context(
        branch, hypothesis, champion, legacy, development_suites=suites
    )
    expected = set(
        spec.development_workspace_paths + spec.development_problem_package_paths
    )
    assert {entry["path"] for entry in h["public_support_sources"]} == expected
    assert set(read_only_files_from_context(c)) == expected | {
        suite.test_path for suite in suites
    }
    assert not set(all_source_files_from_context(c)) & expected
    assert expected <= set(research_files_from_context(c))
    assert "models.py" in expected
    assert "models.py" not in h["existing_target_files"]
    for phase, context in (("hypothesis", h), ("code", c)):
        freeze_proposal_context(phase, context)
    direct_h, _ = _split_direct_v3_hypothesis_context(h)
    direct_c, _ = _split_code_context(c)
    for rendered in (str(direct_h), str(direct_c)):
        assert "class " in rendered and "models.py" in rendered
        assert 'tiny_development.json"' not in rendered  # support body is not exposed
    sources, _, compact = build_hypothesis_research_corpus(h)
    dependency = next(entry for entry in sources if entry["path"] == "models.py")
    assert dependency["body"] == (Path(spec.root_dir) / "models.py").read_text()
    assert dependency["index"]["roles"] == ["public_dependency"]
    assert dependency["index"]["owner"] == "development"
    assert compact["public_support_sources"]["indexed"] is True
    assert "class " not in str(compact["public_support_sources"])
    assert len([entry for entry in sources if entry["path"] == "models.py"]) == 1


@pytest.mark.parametrize("action", ["modify", "create", "delete"])
def test_direct_patch_cannot_touch_readonly_dependency_even_if_redacted(
    action: str,
) -> None:
    context = {
        "editable_source_context": {
            "approved_target": "main.py",
            "sources": [
                {
                    "path": "main.py",
                    "content": "VALUE = 1\n",
                    "roles": ["target"],
                    "visible": True,
                }
            ],
            "public_tests": [],
            "read_only_sources": [
                {"path": "models.py", "content": None, "visible": False}
            ],
            "target_api_guidance": "",
        },
    }
    change = {
        "file_path": "models.py",
        "action": action,
        "edit_intent": "full_file",
        "evidence_refs": [],
    }
    if action != "delete":
        change.update(content_after="VALUE = 2\n", full_file_reason="Replace module.")
    with pytest.raises(ProposalValidationError, match="read-only public dependency"):
        _parse_patch(change, context=context)
    assert "models.py" not in research_files_from_context(context)


def test_readonly_inventory_rejects_colliding_or_noncanonical_paths() -> None:
    context = {
        "editable_source_context": {
            "approved_target": "main.py",
            "sources": [
                {
                    "path": "main.py",
                    "content": "VALUE = 1\n",
                    "roles": ["target"],
                    "visible": True,
                }
            ],
            "public_tests": [],
            "read_only_sources": [
                {"path": "models.py", "content": "VALUE = 2\n", "visible": True}
            ],
            "target_api_guidance": "",
        }
    }
    for invalid_path in ("main.py", "../models.py", "./models.py"):
        invalid = deepcopy(context)
        invalid["editable_source_context"]["read_only_sources"][0]["path"] = (
            invalid_path
        )
        with pytest.raises(ValueError):
            research_files_from_context(invalid)
    invalid = deepcopy(context)
    invalid["editable_source_context"]["public_tests"] = [
        {
            "path": "models.py",
            "content": "test",
            "visible": True,
            "check_name": "D3_unit_tests",
        }
    ]
    with pytest.raises(ValueError, match="duplicate"):
        research_files_from_context(invalid)


def test_problem_runtime_threads_split_to_both_context_phases() -> None:
    spec_path = _REPO / "scion/problems/warehouse_delivery/problem-v1.yaml"
    spec = load_problem_spec_v1_from_yaml(spec_path)
    runtime = ProblemRuntime(
        adapter=load_problem_adapter(spec),
        split_manifest=SimpleNamespace(validation=["models.py"]),
    )
    champion = ChampionState(
        version=1, operator_pool={}, code_snapshot_path=spec.root_dir
    )
    branch = Branch(branch_id="private", state=BranchState.EXPLORE, base_champion_id=1)
    h = HypothesisProposal(
        hypothesis_text="Change",
        change_locus=spec.research_surfaces[0].name,
        action="modify",
        target_file="operators/merge_vehicles.py",
    )
    with pytest.raises(ValueError, match="overlaps Protocol"):
        runtime.build_hypothesis_context(branch=branch, champion=champion)
    with pytest.raises(ValueError, match="overlaps Protocol"):
        runtime.build_code_context(branch=branch, hypothesis=h, champion=champion)
