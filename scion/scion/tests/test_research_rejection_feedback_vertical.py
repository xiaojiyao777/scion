"""Vertical durable rejection feedback from candidate runtime to the next H."""
from __future__ import annotations

import random
import time
from pathlib import Path
from types import SimpleNamespace

from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.models import (
    Branch,
    BranchState,
    ChampionState,
    HypothesisRecord,
    PatchProposal,
)
from scion.core.problem_runtime import ProblemRuntime
from scion.core.proposal_pipeline import ProposalPipeline
from scion.core.research_rejection_finalizer import ResearchRejectionFinalizer
from scion.lineage.branch_store import BranchStore, HypothesisStore
from scion.lineage.registry import LineageRegistry
from scion.problem.bridge import (
    legacy_problem_spec_from_v1,
    load_problem_spec_v1_from_yaml,
)
from scion.problem.loader import load_problem_adapter
from scion.problems.cvrp.models import CvrpInstance, CvrpNode
from scion.problems.cvrp.solver_runtime.algorithm_runtime import (
    load_baseline_algorithm,
)
from scion.verification.candidate_canary import CandidateCanaryExecution
from scion.verification.state_mutation import check_state_mutation

_CVRP_ROOT = Path(__file__).resolve().parents[1] / "problems" / "cvrp"


def test_missing_method_rejection_reaches_fresh_sibling_h_after_restart(
    tmp_path: Path,
) -> None:
    problem_v1 = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    problem_spec = legacy_problem_spec_from_v1(problem_v1)
    adapter = load_problem_adapter(problem_v1)
    candidate_workspace = tmp_path / "candidate"
    (candidate_workspace / "policies").mkdir(parents=True)
    (candidate_workspace / "policies" / "baseline_algorithm.py").write_text(
        "class _SimulatedAnnealing:\n"
        "    def run(self):\n"
        "        self.cool()\n\n"
        "def solve(instance, rng, time_limit_sec, context):\n"
        "    return _SimulatedAnnealing().run()\n",
        encoding="utf-8",
    )
    instance = CvrpInstance(
        name="vertical",
        capacity=2,
        depot=0,
        nodes=(
            CvrpNode(id=0, x=0.0, y=0.0, demand=0),
            CvrpNode(id=1, x=1.0, y=0.0, demand=1),
        ),
        allowed_routes=1,
    )
    solution, runtime = load_baseline_algorithm(
        workspace_root=candidate_workspace,
        instance=instance,
        instance_path="vertical.json",
        seed=77,
        rng=random.Random(77),
        time_limit_sec=2.0,
        start_time=time.perf_counter(),
        adapter=adapter,
    )
    assert solution is None

    canary = tmp_path / "canary.json"
    canary.write_text("{}\n", encoding="utf-8")
    v5 = check_state_mutation(
        problem_spec,
        SimpleNamespace(),
        str(candidate_workspace),
        adapter=adapter,
        selected_surface="solver_design",
        canary_execution=CandidateCanaryExecution(
            case_path=str(canary),
            seed=77,
            result=None,
            raw_output={"runtime": runtime},
        ),
    )
    assert v5.passed is False
    assert v5.metadata == {
        "failing_symbol": "_SimulatedAnnealing.cool",
        "callsite": "policies/baseline_algorithm.py:3",
    }

    db_path = str(tmp_path / "scion.db")
    registry = LineageRegistry(db_path)
    branch_store = BranchStore(registry)
    hypothesis_store = HypothesisStore(registry)
    rejected_branch = Branch(
        branch_id="rejected-branch",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-code",
    )
    branch_store.save(rejected_branch)
    hypothesis = HypothesisRecord(
        hypothesis_id="rejected-hypothesis",
        branch_id=rejected_branch.branch_id,
        change_locus="solver_design",
        action="modify",
        status="active",
        target_file="policies/baseline_algorithm.py",
        hypothesis_text="Repair the annealing lifecycle.",
    )
    hypothesis_store.save(hypothesis)
    check = {
        "name": v5.name,
        "passed": v5.passed,
        "severity": v5.severity,
        "detail": v5.detail,
        "elapsed_ms": v5.elapsed_ms,
        "metadata": dict(v5.metadata),
    }
    outcome = ExecutionOutcomeRecord(
        outcome=ExecutionOutcome.RESEARCH_REJECTED,
        reason_code="VERIFICATION_HEAVY_REJECTED",
        detail=v5.detail,
        provenance={
            "owner": "verification_gate",
            "stage": "verification",
            "verification_checks": [check],
        },
    )
    finalizer = ResearchRejectionFinalizer(
        campaign_id="campaign-vertical",
        registry=registry,
        branch_store=branch_store,
        hypothesis_store=hypothesis_store,
        workspace_lifecycle=SimpleNamespace(
            reject_candidate=lambda _branch, workspace: SimpleNamespace(
                workspace=workspace,
                cleaned=True,
                cleanup_error=None,
            )
        ),
        branch_hypotheses={rejected_branch.branch_id: hypothesis},
        branch_patches={rejected_branch.branch_id: object()},
        branch_current_hypothesis={rejected_branch.branch_id: hypothesis},
        discard_approved_hypothesis_binding=lambda _branch_id: None,
    )
    finalizer.finalize(
        branch=rejected_branch,
        hypothesis_record=hypothesis,
        proposal_attempt_ref={},
        rejection_phase="verification",
        outcome=outcome,
        checks=(check,),
        rejected_candidate_workspace=str(candidate_workspace),
        patch=PatchProposal(
            file_path="policies/baseline_algorithm.py",
            action="modify",
            code_content="candidate source must not enter H",
        ),
    )

    reopened = LineageRegistry(db_path)
    fresh_branch = Branch(
        branch_id="fresh-sibling",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-code",
    )
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="solver",
        code_snapshot_path=problem_spec.root_dir,
        code_snapshot_hash="champion-code",
    )
    pipeline = ProposalPipeline(
        creative=SimpleNamespace(),
        problem_runtime=ProblemRuntime(problem_spec=problem_spec, adapter=adapter),
        classifier=SimpleNamespace(),
        branch_controller=SimpleNamespace(),
        hypothesis_store=HypothesisStore(reopened),
        branch_workspaces={},
        champion_lock=SimpleNamespace(),
        get_champion=lambda: champion,
        step_history=[],
        handle_failure=lambda _branch, _failure: None,
        mark_balance_exhausted=lambda: None,
        campaign_branches_provider=lambda: (fresh_branch,),
        lineage_registry=reopened,
        campaign_id="campaign-vertical",
        problem_id="cvrp",
    )

    snapshot, _prompt = pipeline._hypothesis_snapshots(fresh_branch, champion)
    provider_context = snapshot.inputs.provider_context(
        include_renderer_inputs=True
    )

    assert provider_context["last_research_rejection"] == {
        "failure_stage": "verification",
        "failure_detail": "V5_solution_consistency",
        "failing_symbol": "_SimulatedAnnealing.cool",
        "callsite": "policies/baseline_algorithm.py:3",
    }
    serialized = str(provider_context)
    assert "rejected-branch" not in serialized
    assert "rejected-hypothesis" not in serialized
    assert str(candidate_workspace) not in serialized
    assert "candidate source must not enter H" not in serialized
