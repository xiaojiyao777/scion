from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import shutil

from scion.core.models import (
    Branch,
    BranchState,
    ChampionState,
    HypothesisProposal,
    PatchProposal,
    StepRecord,
)
from scion.problem.spec import ProblemSpecV1
from scion.proposal.edit_protocol import source_digest_for_content
from scion.proposal.context.branch_followup import branch_current_file_sources
from scion.proposal.tools import ProposalToolRegistry
from scion.proposal.tools.models import ContextExposurePolicy, ProposalToolContext
from scion.tests.unit.test_agentic_proposal_tools_helpers import (
    _CVRP_ROOT,
    _cvrp_context,
    _problem_spec,
    _valid_hypothesis_payload,
)


def test_contract_preview_resolves_solver_design_imports_against_branch_workspace(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    branch_workspace = _branch_workspace_with_noise_greedy_repair(tmp_path)
    context = replace(
        _cvrp_context(tmp_path),
        branch_workspace=str(branch_workspace),
    )
    observation = registry.call(
        "proposal.contract_preview",
        {
            "hypothesis": _valid_hypothesis_payload(
                change_locus="solver_design",
                target_file="policies/baseline_modules/scheduler.py",
            ),
            "patch": {
                **_scheduler_patch_with_noise_repair(
                    branch_workspace,
                    import_line="    _noise_greedy_repair,\n",
                    call_line="        best = _noise_greedy_repair(best)\n",
                ),
            },
        },
        context,
    )

    payload = observation.structured_payload
    assert observation.is_error is False
    assert payload["passed"] is True, json.dumps(payload, sort_keys=True)
    assert payload["patch"]["problem_preview"]["passed"] is True
    assert "_noise_greedy_repair" not in (
        _CVRP_ROOT / "policies" / "baseline_modules" / "destroy_repair.py"
    ).read_text(encoding="utf-8")


def test_contract_preview_resolves_same_patch_solver_design_imports(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    branch_workspace = _copy_cvrp_workspace(tmp_path)
    context = replace(
        _cvrp_context(tmp_path),
        branch_workspace=str(branch_workspace),
    )
    patch = _scheduler_patch_with_noise_repair(
        branch_workspace,
        import_block="from .noise_repair import _noise_greedy_repair\n",
        call_line="        best = _noise_greedy_repair(best)\n",
    )
    patch["additional_changes"] = [
        *patch["additional_changes"],
        {
            "file_path": "policies/baseline_modules/noise_repair.py",
            "action": "create",
            "code_content": (
                "def _noise_greedy_repair(solution):\n"
                "    return solution\n"
            ),
        },
    ]
    observation = registry.call(
        "proposal.contract_preview",
        {
            "hypothesis": _valid_hypothesis_payload(
                change_locus="solver_design",
                target_file="policies/baseline_modules/scheduler.py",
            ),
            "patch": patch,
        },
        context,
    )

    payload = observation.structured_payload
    assert observation.is_error is False
    assert payload["passed"] is True, json.dumps(payload, sort_keys=True)
    assert payload["patch"]["problem_preview"]["passed"] is True


def test_contract_and_surface_preview_use_branch_current_helper_source(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    branch = Branch(
        branch_id="branch-current-helper",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
    )
    champion = _generic_solver_design_champion(tmp_path)
    helper_path = "policies/helper.py"
    orchestrator_path = "policies/orchestrator.py"
    helper_source = (
        "def improve(solution):\n"
        "    marker = 'branch-current-helper-v2'\n"
        "    return solution\n"
    )
    first_patch = PatchProposal(
        file_path=helper_path,
        action="create",
        code_content=helper_source,
    )
    step = StepRecord(
        round_num=1,
        branch_id=branch.branch_id,
        hypothesis=HypothesisProposal(
            hypothesis_text="create branch helper",
            change_locus="solver_design",
            action="create_new",
            target_file=helper_path,
        ),
        patch=first_patch,
        contract_passed=True,
        verification_passed=True,
        protocol_result=None,
        decision=None,
        failure_stage=None,
        failure_detail=None,
    )
    sources = branch_current_file_sources(branch, [step])
    context = _generic_solver_design_context(
        tmp_path,
        branch=branch,
        champion=champion,
        branch_current_sources=sources,
    )

    surface_observation = registry.call(
        "context.read_surface",
        {
            "surface": "solver_design",
            "section": "target_preview",
            "target_file": helper_path,
            "include_code": True,
        },
        context,
    )
    surface_payload = surface_observation.structured_payload["current_artifact"]
    assert surface_payload["source"] == "branch_current_file_sources"
    assert surface_payload["source_digest"] == source_digest_for_content(helper_source)
    assert "branch-current-helper-v2" in surface_payload["content_preview"]

    contract_observation = registry.call(
        "proposal.contract_preview",
        {
            "hypothesis": _valid_hypothesis_payload(
                change_locus="solver_design",
                target_file=orchestrator_path,
            ),
            "patch": {
                "file_path": orchestrator_path,
                "action": "modify",
                "code_content": (
                    "from .helper import improve\n\n"
                    "def solve(solution):\n"
                    "    return improve(solution)\n"
                ),
            },
        },
        context,
    )

    payload = contract_observation.structured_payload
    assert contract_observation.is_error is False
    c8 = next(
        check for check in payload["patch"]["checks"] if check["name"] == "C8_import_whitelist"
    )
    assert c8["passed"] is True, json.dumps(payload, sort_keys=True)

    no_override_context = replace(context, branch_current_file_sources={})
    no_override_observation = registry.call(
        "proposal.contract_preview",
        {
            "hypothesis": _valid_hypothesis_payload(
                change_locus="solver_design",
                target_file=orchestrator_path,
            ),
            "patch": {
                "file_path": orchestrator_path,
                "action": "modify",
                "code_content": (
                    "from .helper import improve\n\n"
                    "def solve(solution):\n"
                    "    return improve(solution)\n"
                ),
            },
        },
        no_override_context,
    )
    no_override_checks = no_override_observation.structured_payload["patch"]["checks"]
    no_override_c8 = next(
        check for check in no_override_checks if check["name"] == "C8_import_whitelist"
    )
    assert no_override_c8["passed"] is False


def _generic_solver_design_champion(tmp_path: Path) -> ChampionState:
    root = tmp_path / "generic_champion"
    (root / "policies").mkdir(parents=True)
    (root / "policies" / "orchestrator.py").write_text(
        "def solve(solution):\n    return solution\n",
        encoding="utf-8",
    )
    return ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="solver-hash",
        code_snapshot_path=str(root),
        code_snapshot_hash="champion-hash",
    )


def _generic_solver_design_context(
    tmp_path: Path,
    *,
    branch: Branch,
    champion: ChampionState,
    branch_current_sources: dict[str, str],
) -> ProposalToolContext:
    spec_payload = _problem_spec(tmp_path).model_dump()
    spec_payload["search_space"]["editable"] = ["policies/*.py"]
    spec_payload["search_space"]["import_whitelist"] = ["math"]
    spec_payload["research_surfaces"] = [
        {
            "name": "solver_design",
            "kind": "solver_design",
            "description": "Generic solver-design surface for branch-current tests.",
            "targets": {
                "files": ["policies/*.py"],
                "create_new_allowed": True,
                "modify_allowed": True,
                "remove_allowed": False,
            },
            "bounds": {"complexity_scale_terms": ["item_count"]},
        }
    ]
    return ProposalToolContext(
        session_id="session-generic-branch-current",
        campaign_id="camp-generic-branch-current",
        branch=branch,
        champion=champion,
        problem_spec=ProblemSpecV1(**spec_payload),
        step_history=(),
        policy=ContextExposurePolicy(allow_contract_preview=True),
        problem_id="generic_solver_design",
        problem_spec_hash="generic-hash",
        branch_current_file_sources=branch_current_sources,
    )


def test_algorithm_smoke_resolves_solver_design_imports_against_branch_workspace(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    branch_workspace = _branch_workspace_with_noise_greedy_repair(tmp_path)
    context = replace(
        _cvrp_context(tmp_path),
        branch_workspace=str(branch_workspace),
    )
    observation = registry.call(
        "proposal.algorithm_smoke",
        {
            "hypothesis": _valid_hypothesis_payload(
                change_locus="solver_design",
                target_file="policies/baseline_modules/scheduler.py",
            ),
            "patch": {
                **_scheduler_patch_with_noise_repair(
                    branch_workspace,
                    import_line="    _noise_greedy_repair,\n",
                    call_line="        best = _noise_greedy_repair(best)\n",
                ),
            },
        },
        context,
    )

    payload = observation.structured_payload
    assert observation.is_error is False
    assert payload["passed"] is True, json.dumps(payload, sort_keys=True)
    assert payload["runtime_smoke"]["runtime_smoke_run"] is True


def _branch_workspace_with_noise_greedy_repair(tmp_path: Path) -> Path:
    workspace = _copy_cvrp_workspace(tmp_path)
    destroy_repair = (
        workspace / "policies" / "baseline_modules" / "destroy_repair.py"
    )
    destroy_repair.write_text(
        destroy_repair.read_text(encoding="utf-8")
        + "\n\n"
        "def _noise_greedy_repair(solution):\n"
        "    return solution\n",
        encoding="utf-8",
    )
    return workspace


def _copy_cvrp_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "branch_cvrp"
    shutil.copytree(
        _CVRP_ROOT,
        workspace,
        ignore=shutil.ignore_patterns(
            "__pycache__",
            "*.pyc",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
        ),
    )
    return workspace


def _scheduler_code_using(
    workspace: Path,
    *,
    call_line: str,
    import_line: str = "",
    import_block: str = "",
) -> str:
    code = (
        workspace / "policies" / "baseline_modules" / "scheduler.py"
    ).read_text(encoding="utf-8")
    if import_line:
        code = code.replace(
            "    _worst_removal,\n",
            "    _worst_removal,\n" + import_line,
            1,
        )
    if import_block:
        local_search_import = _scheduler_local_search_import_line(code)
        code = code.replace(
            local_search_import,
            local_search_import + import_block,
            1,
        )
    return code.replace(
        "        best = current.copy()\n",
        "        best = current.copy()\n" + call_line,
        1,
    )


def _scheduler_patch_with_noise_repair(
    workspace: Path,
    *,
    call_line: str,
    import_line: str = "",
    import_block: str = "",
) -> dict:
    scheduler_path = "policies/baseline_modules/scheduler.py"
    before = (workspace / scheduler_path).read_text(encoding="utf-8")
    local_search_import = _scheduler_local_search_import_line(before)
    first_old = (
        "    _worst_removal,\n"
        if import_line
        else local_search_import
    )
    first_new = (
        "    _worst_removal,\n" + import_line
        if import_line
        else local_search_import + import_block
    )
    return {
        "file_path": scheduler_path,
        "action": "modify",
        "edit_intent": "exact_replace",
        "source_digest": source_digest_for_content(before),
        "old_string": first_old,
        "new_string": first_new,
        "additional_changes": [
            {
                "file_path": scheduler_path,
                "action": "modify",
                "edit_intent": "exact_replace",
                "source_digest": source_digest_for_content(before),
                "old_string": "        best = current.copy()\n",
                "new_string": "        best = current.copy()\n" + call_line,
            }
        ],
    }


def _scheduler_local_search_import_line(code: str) -> str:
    for line in code.splitlines(keepends=True):
        if line.startswith("from .local_search import "):
            return line
    raise AssertionError("scheduler.py local_search import line not found")
