from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest

from scion.core.models import (
    Branch,
    BranchState,
    ChampionState,
    CheckResult,
    DecisionFeatures,
    FailureEvent,
    HypothesisProposal,
    PatchProposal,
    StepRecord,
    VerificationResult,
)
from scion.core.proposal_pipeline import ProposalPipeline
from scion.core.public_refs import contains_absolute_path
from scion.proposal.search_memory import CampaignSearchMemory
from scion.proposal.agentic_session import (
    AgenticEvidenceRef,
    AgenticFailureCategory,
    AgenticProposalOutput,
    AgenticProposalRequest,
    AgenticProposalSession,
    AgenticProposalStatus,
    AgenticSelfCheck,
    AgenticTerminationReason,
    AgenticTranscriptEvent,
    FileAgenticSessionArtifactStore,
)
from scion.proposal.engine import ProposalValidationError
from scion.proposal.llm_client import LLMBalanceError, LLMRetryExhaustedError
from scion.proposal.tools import ProposalToolContext, ProposalToolRegistry


class FakeProblemRuntime:
    def __init__(self, spec=None) -> None:
        self.spec = spec
        self.hypothesis_kwargs = None
        self.code_kwargs = None
        self.fix_kwargs = None

    def build_hypothesis_context(self, **kwargs):
        self.hypothesis_kwargs = kwargs
        return {"kind": "hypothesis"}

    def build_code_context(self, **kwargs):
        self.code_kwargs = kwargs
        return {"kind": "code"}

    def build_fix_context(self, **kwargs):
        self.fix_kwargs = kwargs
        return {"kind": "fix"}


class FakeCreative:
    def __init__(
        self,
        *,
        code_error: Exception | None = None,
        fix_error: Exception | None = None,
    ) -> None:
        self.code_error = code_error
        self.fix_error = fix_error
        self.hypothesis_calls = 0
        self.code_calls = 0
        self.fix_calls = 0
        self.hypothesis = HypothesisProposal(
            hypothesis_text="Bounded route-pair search.",
            change_locus="local_search",
            action="create_new",
            target_file="operators/bounded.py",
            suggested_weight=0.5,
            predicted_direction="improve",
            target_weakness="The current search lacks a bounded route-pair move.",
            expected_effect="Improve distance on screening cases without changing feasibility.",
            target_objectives=("distance",),
            protected_objectives=("feasibility",),
            objective_tradeoff_policy="Protect feasibility before distance.",
            no_op_condition="Do nothing when no improving route-pair move exists.",
            risk_to_higher_priority="May spend budget without finding an improving move.",
            target_runtime_effect="neutral",
            complexity_claim="O(k) candidate route-pair checks.",
            runtime_budget_strategy="Use a fixed top-k candidate cap.",
        )
        self.patch = PatchProposal(
            file_path="operators/bounded.py",
            action="create",
            code_content=(
                "class Bounded:\n"
                "    def execute(self, solution, rng):\n"
                "        return solution\n"
            ),
        )
        self.fix = PatchProposal(
            file_path="operators/bounded.py",
            action="modify",
            code_content="class Bounded: pass\n",
        )

    def generate_hypothesis(self, context):
        self.hypothesis_calls += 1
        return self.hypothesis

    def generate_code(self, context):
        self.code_calls += 1
        if self.code_error is not None:
            raise self.code_error
        return self.patch

    def fix_code(self, context):
        self.fix_calls += 1
        if self.fix_error is not None:
            raise self.fix_error
        return self.fix


class FakeBranchController:
    def __init__(self, branches):
        self._branches = list(branches)

    def get_active_branches(self):
        return list(self._branches)


class FakeHypothesisStore:
    def get_by_status(self, status):
        return [f"{status}-record"]


class FakeCircuitBreaker:
    def __init__(self) -> None:
        self.successes = 0
        self.failures: list[str] = []

    def record_success(self) -> None:
        self.successes += 1

    def record_failure(self, detail: str) -> bool:
        self.failures.append(detail)
        return False


class MemoryLineageRegistry:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def record_event(self, event: dict):
        self.events.append(dict(event))
        return event.get("event_id", "event-1")


def _branch(branch_id: str = "branch-1") -> Branch:
    return Branch(
        branch_id=branch_id,
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="hash-1",
    )


def _champion() -> ChampionState:
    return ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="solver",
        code_snapshot_path="/tmp/champion",
        code_snapshot_hash="hash",
    )


def _pipeline(
    *,
    creative: FakeCreative | None = None,
    use_agentic_proposal: bool = False,
    agentic_session=None,
    agentic_artifact_dir: str | None = None,
    agentic_session_timeout_sec: float | None = None,
    lineage_registry=None,
    branch_workspace: str = "/tmp/branch",
    forced_locus: str | None = "local_search",
    persistent_forced_locus: str | None = None,
    forced_surface_action: str | None = None,
    forced_surface_target_file: str | None = None,
    forced_surface_diagnostic: bool = False,
    problem_spec=None,
):
    branch = _branch()
    sibling = _branch("sibling")
    if problem_spec is None:
        problem_spec = SimpleNamespace(
            operator_categories=["local_search"],
            search_space=SimpleNamespace(
                editable=["operators/*.py"],
                frozen=[],
                import_whitelist=[],
            ),
            research_surfaces=[
                SimpleNamespace(
                    name="local_search",
                    kind="operator",
                    target_files=["operators/*.py"],
                    create_new_allowed=True,
                    modify_allowed=True,
                    remove_allowed=False,
                )
            ]
        )
    runtime = FakeProblemRuntime(spec=problem_spec)
    circuit = FakeCircuitBreaker()
    failures: list[tuple[Branch, FailureEvent]] = []
    balance_exhausted = {"value": False}
    pipeline = ProposalPipeline(
        creative=creative or FakeCreative(),
        problem_runtime=runtime,
        classifier=SimpleNamespace(
            classify=lambda text: SimpleNamespace(
                family_id="bounded-local",
                source="test",
                taxonomy_version="v1",
            )
        ),
        branch_controller=FakeBranchController([branch, sibling]),
        hypothesis_store=FakeHypothesisStore(),
        branch_workspaces={branch.branch_id: branch_workspace},
        champion_lock=threading.Lock(),
        get_champion=_champion,
        step_history=[],
        failure_streak={"proposal": 1},
        consume_forced_locus=lambda: forced_locus,
        search_memory=SimpleNamespace(),
        get_saturation_analyzer=lambda: None,
        get_baseline_metrics=lambda: None,
        get_latest_weight_opt_result=lambda: {"weights": "latest"},
        research_log=SimpleNamespace(),
        handle_failure=lambda b, f: failures.append((b, f)),
        circuit_breaker=circuit,
        mark_balance_exhausted=lambda: balance_exhausted.__setitem__("value", True),
        use_agentic_proposal=use_agentic_proposal,
        agentic_session=agentic_session,
        agentic_artifact_dir=agentic_artifact_dir,
        agentic_session_timeout_sec=agentic_session_timeout_sec,
        lineage_registry=lineage_registry,
        campaign_id="camp-1",
        problem_id="toy",
        problem_spec_hash="spec-hash",
        persistent_forced_locus=persistent_forced_locus,
        forced_surface_action=forced_surface_action,
        forced_surface_target_file=forced_surface_target_file,
        forced_surface_diagnostic=forced_surface_diagnostic,
    )
    return pipeline, branch, runtime, circuit, failures, balance_exhausted


__all__ = [
    name
    for name in globals()
    if not (name.startswith("__") and name.endswith("__"))
]
