from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import shutil

from scion.proposal.edit_protocol import source_digest_for_content
from scion.proposal.tools import ProposalToolRegistry
from scion.tests.unit.test_agentic_proposal_tools_helpers import (
    _CVRP_ROOT,
    _cvrp_context,
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
        code = code.replace(
            "from .local_search import _default_vns_operators, _vns\n",
            "from .local_search import _default_vns_operators, _vns\n"
            + import_block,
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
    first_old = (
        "    _worst_removal,\n"
        if import_line
        else "from .local_search import _default_vns_operators, _vns\n"
    )
    first_new = (
        "    _worst_removal,\n" + import_line
        if import_line
        else "from .local_search import _default_vns_operators, _vns\n"
        + import_block
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
