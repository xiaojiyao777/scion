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
    VerificationResult,
)
from scion.core.proposal_pipeline import ProposalPipeline
from scion.core.public_refs import contains_absolute_path
from scion.proposal.agentic_session import (
    AgenticEvidenceRef,
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


def test_generate_hypothesis_builds_context_and_record() -> None:
    pipeline, branch, runtime, circuit, failures, _ = _pipeline()

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis is not None
    assert record is not None
    assert record.branch_id == branch.branch_id
    assert record.family_id == "bounded-local"
    assert record.suggested_weight == 0.5
    assert circuit.successes == 1
    assert failures == []
    assert runtime.hypothesis_kwargs["branch_workspace"] == "/tmp/branch"
    assert runtime.hypothesis_kwargs["forced_locus"] == "local_search"
    assert runtime.hypothesis_kwargs["weight_opt_result"] == {"weights": "latest"}
    assert [b.branch_id for b in runtime.hypothesis_kwargs["sibling_branches"]] == [
        "sibling"
    ]
    assert pipeline.agentic_outputs == {}


def test_generate_hypothesis_threads_diagnostic_forced_surface_controls() -> None:
    creative = FakeCreative()
    creative.hypothesis = HypothesisProposal(
        hypothesis_text="Modify the forced blueprint surface.",
        change_locus="algorithm_blueprint",
        action="modify",
        target_file="policies/algorithm_blueprint.py",
    )
    pipeline, branch, runtime, _, _, _ = _pipeline(
        creative=creative,
        forced_locus="algorithm_blueprint",
        forced_surface_action="modify",
        forced_surface_target_file="policies/algorithm_blueprint.py",
        forced_surface_diagnostic=True,
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis is not None
    assert record is not None
    assert runtime.hypothesis_kwargs["forced_locus"] == "algorithm_blueprint"
    assert runtime.hypothesis_kwargs["forced_action"] == "modify"
    assert (
        runtime.hypothesis_kwargs["forced_target_file"]
        == "policies/algorithm_blueprint.py"
    )
    assert runtime.hypothesis_kwargs["forced_surface_diagnostic"] is True
    assert pipeline.forced_surface_action is None
    assert pipeline.forced_surface_target_file is None
    assert pipeline.forced_surface_diagnostic is False


def test_generate_hypothesis_keeps_launch_forced_surface_across_rounds() -> None:
    creative = FakeCreative()
    creative.hypothesis = HypothesisProposal(
        hypothesis_text="Modify the forced blueprint surface.",
        change_locus="algorithm_blueprint",
        action="modify",
        target_file="policies/algorithm_blueprint.py",
    )
    pipeline, branch, runtime, _, _, _ = _pipeline(
        creative=creative,
        forced_locus=None,
        persistent_forced_locus="algorithm_blueprint",
        forced_surface_action="modify",
        forced_surface_target_file="policies/algorithm_blueprint.py",
        forced_surface_diagnostic=True,
    )

    first_hypothesis, first_record = pipeline.generate_hypothesis(branch)

    assert first_hypothesis is not None
    assert first_record is not None
    assert runtime.hypothesis_kwargs["forced_locus"] == "algorithm_blueprint"
    assert runtime.hypothesis_kwargs["forced_action"] == "modify"
    assert (
        runtime.hypothesis_kwargs["forced_target_file"]
        == "policies/algorithm_blueprint.py"
    )
    assert runtime.hypothesis_kwargs["forced_surface_diagnostic"] is True

    next_branch = _branch("round-2")
    second_hypothesis, second_record = pipeline.generate_hypothesis(next_branch)

    assert second_hypothesis is not None
    assert second_record is not None
    assert second_record.branch_id == "round-2"
    assert runtime.hypothesis_kwargs["forced_locus"] == "algorithm_blueprint"
    assert runtime.hypothesis_kwargs["forced_action"] == "modify"
    assert (
        runtime.hypothesis_kwargs["forced_target_file"]
        == "policies/algorithm_blueprint.py"
    )
    assert runtime.hypothesis_kwargs["forced_surface_diagnostic"] is True
    assert pipeline.persistent_forced_locus == "algorithm_blueprint"
    assert pipeline.forced_surface_action == "modify"
    assert (
        pipeline.forced_surface_target_file
        == "policies/algorithm_blueprint.py"
    )
    assert pipeline.forced_surface_diagnostic is True


def test_generate_code_failure_routes_proposal_failure() -> None:
    creative = FakeCreative(code_error=LLMRetryExhaustedError("code failed"))
    pipeline, branch, _, circuit, failures, _ = _pipeline(creative=creative)

    patch = pipeline.generate_code(branch, creative.hypothesis, prior_failure="first")

    assert patch is None
    assert circuit.failures == ["code failed"]
    assert len(failures) == 1
    failed_branch, failure = failures[0]
    assert failed_branch is branch
    assert failure.category == "proposal"
    assert failure.detail == "code failed"


def test_default_agentic_session_has_registry_and_requests_get_tool_context() -> None:
    captured: list[AgenticProposalRequest] = []

    class CapturingSession:
        def run(self, request: AgenticProposalRequest) -> AgenticProposalOutput:
            captured.append(request)
            return AgenticProposalOutput(
                status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
                session_id="session-1",
                campaign_id=request.campaign_id,
                branch_id=request.branch.branch_id,
                champion_version=request.champion.version if request.champion else None,
                problem_id=request.problem_id,
                problem_spec_hash=request.problem_spec_hash,
                hypothesis=FakeCreative().hypothesis,
                termination_reason=AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL,
            )

    pipeline, branch, _, _, _, _ = _pipeline(
        use_agentic_proposal=True,
        agentic_session=CapturingSession(),
    )

    default_session = _pipeline(use_agentic_proposal=True)[0]._get_agentic_session()
    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert isinstance(default_session, AgenticProposalSession)
    assert isinstance(default_session.tool_registry, ProposalToolRegistry)
    assert "context.list_surfaces" in default_session.tool_registry.list_tools()
    assert hypothesis is not None
    assert record is not None
    assert len(captured) == 1
    assert isinstance(captured[0].tool_context, ProposalToolContext)
    assert captured[0].tool_context.branch is branch
    assert captured[0].tool_context.problem_id == "toy"


def test_default_agentic_session_uses_configured_timeout() -> None:
    pipeline, _, _, _, _, _ = _pipeline(
        use_agentic_proposal=True,
        agentic_session_timeout_sec=7.5,
    )

    session = pipeline._get_agentic_session()

    assert isinstance(session, AgenticProposalSession)
    assert session._tool_loop_config.max_wall_time_sec == 7.5


def test_agentic_session_invalid_target_does_not_build_code_context_or_patch(
    tmp_path: Path,
) -> None:
    creative = FakeCreative()
    creative.hypothesis = HypothesisProposal(
        hypothesis_text="Try an invalid target.",
        change_locus="local_search",
        action="modify",
        target_file="secret/forbidden.py",
    )
    champion_root = tmp_path / "champion"
    target = champion_root / "secret" / "forbidden.py"
    target.parent.mkdir(parents=True)
    target.write_text("SECRET_TARGET_CONTENT = True\n", encoding="utf-8")
    build_calls = 0

    def build_code_context(_hypothesis):
        nonlocal build_calls
        build_calls += 1
        target.read_text(encoding="utf-8")
        raise AssertionError("code context must not be built before approval")

    session = AgenticProposalSession(creative)
    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=_branch(),
            champion=_champion(),
            hypothesis_context={"kind": "hypothesis"},
            build_code_context=build_code_context,
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=False,
                failure_reason="C3_action_target: invalid target_file",
            ),
        )
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert (
        output.termination_reason
        == AgenticTerminationReason.HYPOTHESIS_APPROVAL_FAILED
    )
    assert output.hypothesis == creative.hypothesis
    assert output.patch is None
    assert build_calls == 0
    assert creative.code_calls == 0
    assert "SECRET_TARGET_CONTENT" not in str(output)


def test_agentic_pipeline_hypothesis_request_denies_custom_code_context_read(
    tmp_path: Path,
) -> None:
    creative = FakeCreative()
    target = tmp_path / "champion" / "operators" / "bounded.py"
    target.parent.mkdir(parents=True)
    target.write_text("SECRET_TARGET_CONTENT = True\n", encoding="utf-8")
    target_reads = 0

    class MaliciousSession:
        attempted = False

        def run(self, request: AgenticProposalRequest) -> AgenticProposalOutput:
            self.attempted = True
            request.build_code_context(creative.hypothesis)
            raise AssertionError("unapproved code context was available")

    session = MaliciousSession()
    pipeline, branch, runtime, circuit, failures, _ = _pipeline(
        creative=creative,
        agentic_session=session,
    )

    def forbidden_build_code_context(**kwargs):
        nonlocal target_reads
        target_reads += 1
        target.read_text(encoding="utf-8")
        return {"kind": "code", **kwargs}

    runtime.build_code_context = forbidden_build_code_context

    hypothesis, record = pipeline.generate_hypothesis(branch)
    detail = pipeline.pop_hypothesis_failure_detail(branch.branch_id)

    assert hypothesis is None
    assert record is None
    assert session.attempted is True
    assert detail is not None
    assert "ContractGate-approved hypothesis" in detail
    assert runtime.code_kwargs is None
    assert target_reads == 0
    assert "SECRET_TARGET_CONTENT" not in str(pipeline.agentic_outputs)
    assert len(failures) == 1
    assert circuit.failures == [detail]


def test_agentic_session_builds_code_context_only_after_hypothesis_contract_pass() -> None:
    creative = FakeCreative()
    events: list[str] = []

    def approve_hypothesis(_hypothesis):
        events.append("approve")
        return SimpleNamespace(passed=True, failure_reason=None)

    def build_code_context(hypothesis):
        events.append("build_code_context")
        assert hypothesis == creative.hypothesis
        return {"kind": "code"}

    session = AgenticProposalSession(creative)
    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=_branch(),
            champion=_champion(),
            hypothesis_context={"kind": "hypothesis"},
            build_code_context=build_code_context,
            approve_hypothesis=approve_hypothesis,
        )
    )

    assert events == ["approve", "build_code_context"]
    assert output.is_completed
    assert isinstance(output.hypothesis, HypothesisProposal)
    assert isinstance(output.patch, PatchProposal)


def test_agentic_completed_patch_before_approval_is_downgraded_and_cleared() -> None:
    creative = FakeCreative()
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.COMPLETED,
        session_id="session-1",
        campaign_id="camp-1",
        branch_id="branch-1",
        champion_version=1,
        champion_weight_revision=0,
        problem_id="toy",
        problem_spec_hash="spec-hash",
        hypothesis=creative.hypothesis,
        patch=creative.patch,
        termination_reason=AgenticTerminationReason.COMPLETED,
    )
    pipeline, branch, runtime, _, failures, _ = _pipeline(
        creative=creative,
        agentic_session=AgenticProposalSession(injected_output=output),
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)
    stored = pipeline.agentic_outputs[branch.branch_id]

    assert hypothesis == creative.hypothesis
    assert record is not None
    assert stored.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert (
        stored.termination_reason
        == AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL
    )
    assert stored.patch is None
    assert "before ContractGate-approved hypothesis" in (stored.failure_detail or "")
    assert runtime.code_kwargs is None
    assert creative.code_calls == 0
    assert failures == []


def test_agentic_forced_surface_rejects_off_surface_hypothesis_before_code() -> None:
    creative = FakeCreative()
    off_surface = HypothesisProposal(
        hypothesis_text="Try route-local work despite a forced policy surface.",
        change_locus="route_local",
        action="create_new",
        target_file="operators/local_new.py",
    )
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
        session_id="session-1",
        campaign_id="camp-1",
        branch_id="branch-1",
        champion_version=1,
        champion_weight_revision=0,
        problem_id="toy",
        problem_spec_hash="spec-hash",
        hypothesis=off_surface,
        termination_reason=AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL,
    )
    pipeline, branch, runtime, circuit, failures, _ = _pipeline(
        creative=creative,
        agentic_session=AgenticProposalSession(injected_output=output),
        forced_locus=None,
        persistent_forced_locus="solver_design",
        forced_surface_action="modify",
        forced_surface_target_file="policies/solver_algorithm.py",
        forced_surface_diagnostic=True,
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis is None
    assert record is None
    detail = pipeline.pop_hypothesis_failure_detail(branch.branch_id)
    assert detail is not None
    assert "forced_surface_constraint" in detail
    assert "solver_design" in detail
    assert len(failures) == 1
    assert circuit.failures == [detail]
    assert runtime.code_kwargs is None
    assert creative.code_calls == 0


def test_agentic_active_problem_boundary_rejects_component_hypothesis() -> None:
    creative = FakeCreative()
    component = HypothesisProposal(
        hypothesis_text="Tune a component policy outside the active boundary.",
        change_locus="baseline_policy",
        action="modify",
        target_file="policies/baseline_policy.py",
    )
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
        session_id="session-1",
        campaign_id="camp-1",
        branch_id="branch-1",
        champion_version=1,
        champion_weight_revision=0,
        problem_id="toy",
        problem_spec_hash="spec-hash",
        hypothesis=component,
        termination_reason=AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL,
    )
    solver_design_spec = SimpleNamespace(
        research_surfaces=[
            SimpleNamespace(
                name="solver_design",
                kind="solver_design",
                algorithm=SimpleNamespace(role="problem_object_solver_algorithm"),
            ),
            SimpleNamespace(
                name="baseline_policy",
                kind="policy",
                algorithm=SimpleNamespace(role="component_policy"),
            ),
        ]
    )
    pipeline, branch, runtime, circuit, failures, _ = _pipeline(
        creative=creative,
        agentic_session=AgenticProposalSession(injected_output=output),
        forced_locus=None,
        problem_spec=solver_design_spec,
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis is None
    assert record is None
    detail = pipeline.pop_hypothesis_failure_detail(branch.branch_id)
    assert detail is not None
    assert "active_problem_boundary_constraint" in detail
    assert "solver_design" in detail
    assert len(failures) == 1
    assert circuit.failures == [detail]
    assert runtime.code_kwargs is None
    assert creative.code_calls == 0


def test_agentic_approved_continuation_can_build_code_context_and_patch() -> None:
    creative = FakeCreative()
    events: list[str] = []

    class ContinuationSession:
        def run(self, request: AgenticProposalRequest) -> AgenticProposalOutput:
            if request.approved_hypothesis is None:
                events.append("hypothesis")
                return AgenticProposalOutput(
                    status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
                    session_id="session-hyp",
                    campaign_id=request.campaign_id,
                    branch_id=request.branch.branch_id,
                    champion_version=(
                        request.champion.version if request.champion else None
                    ),
                    problem_id=request.problem_id,
                    problem_spec_hash=request.problem_spec_hash,
                    hypothesis=creative.hypothesis,
                    termination_reason=(
                        AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL
                    ),
                )

            events.append("continuation")
            code_context = request.build_code_context(request.approved_hypothesis)
            assert code_context["kind"] == "code"
            events.append("code_context")
            return AgenticProposalOutput(
                status=AgenticProposalStatus.COMPLETED,
                session_id="session-code",
                campaign_id=request.campaign_id,
                branch_id=request.branch.branch_id,
                champion_version=request.champion.version if request.champion else None,
                problem_id=request.problem_id,
                problem_spec_hash=request.problem_spec_hash,
                hypothesis=request.approved_hypothesis,
                patch=creative.patch,
                termination_reason=AgenticTerminationReason.COMPLETED,
            )

    pipeline, branch, runtime, _, failures, _ = _pipeline(
        creative=creative,
        agentic_session=ContinuationSession(),
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)
    patch = pipeline.generate_code(branch, hypothesis)

    assert hypothesis == creative.hypothesis
    assert record is not None
    assert patch == creative.patch
    assert events == ["hypothesis", "continuation", "code_context"]
    assert runtime.code_kwargs["hypothesis"] == creative.hypothesis
    assert failures == []


def test_agentic_completed_output_failed_self_check_rejected_before_patch_use() -> None:
    creative = FakeCreative()
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.COMPLETED,
        session_id="session-code",
        campaign_id="camp-1",
        branch_id="branch-1",
        champion_version=1,
        champion_weight_revision=0,
        problem_id="toy",
        problem_spec_hash="spec-hash",
        hypothesis=creative.hypothesis,
        patch=creative.patch,
        transcript=(
            AgenticTranscriptEvent(
                phase="self_check",
                message="preview failed",
                metadata={"tool_name": "proposal.contract_preview"},
            ),
        ),
        self_check=AgenticSelfCheck(
            schema_valid=False,
            contract_preview_passed=False,
            contract_preview_codes=("result_too_large", "tool_skipped"),
        ),
        tool_budget_used={"tool_calls": 8, "tool_steps": 8},
        termination_reason=AgenticTerminationReason.COMPLETED,
    )
    pipeline, branch, _, circuit, failures, _ = _pipeline(
        creative=creative,
        agentic_session=AgenticProposalSession(injected_output=output),
    )

    patch = pipeline.generate_code(branch, creative.hypothesis)

    assert patch is None
    assert len(failures) == 1
    assert "agentic_self_check_failed" in failures[0][1].detail
    assert circuit.failures == [failures[0][1].detail]


def test_agentic_completed_output_produces_existing_hypothesis_and_patch_shapes(
    tmp_path: Path,
) -> None:
    creative = FakeCreative()
    artifact_dir = tmp_path / "artifacts" / "agentic_proposal_sessions"
    pipeline, branch, runtime, circuit, failures, _ = _pipeline(
        creative=creative,
        use_agentic_proposal=True,
        agentic_artifact_dir=str(artifact_dir),
        branch_workspace=str(tmp_path / "candidate-workspace"),
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)
    patch = pipeline.generate_code(branch, hypothesis)

    assert hypothesis == creative.hypothesis
    assert record is not None
    assert patch == creative.patch
    assert creative.hypothesis_calls == 1
    assert creative.code_calls == 1
    assert circuit.successes == 2
    assert failures == []
    assert runtime.code_kwargs["hypothesis"] == creative.hypothesis
    assert not (tmp_path / "candidate-workspace").exists()

    artifact_refs = sorted(
        str(p)
        for p in artifact_dir.rglob("*.json")
        if p.name in {"output.json", "transcript.json"}
    )
    assert len(artifact_refs) == 4
    for ref in artifact_refs:
        path = Path(ref).resolve()
        assert artifact_dir.resolve() in path.parents


def test_agentic_partial_session_returns_no_patch_and_routes_proposal_failure() -> None:
    creative = FakeCreative(code_error=LLMRetryExhaustedError("code failed"))
    pipeline, branch, _, circuit, failures, _ = _pipeline(
        creative=creative,
        use_agentic_proposal=True,
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis == creative.hypothesis
    assert record is not None
    output = pipeline.agentic_outputs[branch.branch_id]
    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert (
        output.termination_reason
        == AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL
    )
    assert output.patch is None
    assert creative.code_calls == 0

    patch = pipeline.generate_code(branch, hypothesis)

    assert patch is None
    assert len(failures) == 1
    assert failures[0][1].category == "proposal"
    assert "agentic_proposal:code_generation_failed" in failures[0][1].detail
    assert circuit.failures == [failures[0][1].detail]


def test_agentic_premise_contradiction_is_quality_block_not_infra_streak() -> None:
    creative = FakeCreative()
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
        session_id="premise-session",
        campaign_id="camp-1",
        branch_id="branch-1",
        champion_version=1,
        problem_id="toy",
        problem_spec_hash="spec-hash",
        hypothesis=creative.hypothesis,
        termination_reason=AgenticTerminationReason.PREMISE_CONTRADICTED,
        failure_detail="active solver already contains the claimed missing move",
        failure_category="agent_grounding_failure",
        structured_rejection={
            "premise_check": "contradicted",
            "failure_category": "agent_grounding_failure",
            "failure_code": "proposal_premise_contradicted",
            "agent_block_reason": "agent_quality_blocked",
        },
    )
    failure_streak = {"proposal": 2}
    pipeline, branch, _, circuit, failures, _ = _pipeline(
        creative=creative,
        agentic_session=AgenticProposalSession(injected_output=output),
    )
    pipeline.failure_streak = failure_streak

    patch = pipeline.generate_code(branch, creative.hypothesis)
    detail = pipeline.pop_hypothesis_failure_detail(branch.branch_id)
    session_ref = pipeline.pop_agentic_session_ref(branch.branch_id)

    assert patch is None
    assert failures == []
    assert failure_streak == {"proposal": 2}
    assert detail is not None
    assert "agent_quality_blocked" in detail
    assert "proposal_premise_contradicted" in detail
    assert "agent_grounding_failure" in detail
    assert circuit.failures == [detail]
    assert session_ref is not None
    assert session_ref["failure_category"] == "agent_grounding_failure"
    assert session_ref["failure_code"] == "proposal_premise_contradicted"
    assert session_ref["agent_block_reason"] == "agent_quality_blocked"


def test_agentic_pipeline_passes_compact_resume_context_from_failed_artifact(
    tmp_path: Path,
) -> None:
    artifact_dir = tmp_path / "agentic"
    captured: list[AgenticProposalRequest] = []
    creative = FakeCreative()

    class CapturingSession:
        def run(self, request: AgenticProposalRequest) -> AgenticProposalOutput:
            captured.append(request)
            return AgenticProposalOutput(
                status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
                session_id="next-session",
                campaign_id=request.campaign_id,
                branch_id=request.branch.branch_id,
                champion_version=request.champion.version if request.champion else None,
                problem_id=request.problem_id,
                problem_spec_hash=request.problem_spec_hash,
                hypothesis=creative.hypothesis,
                termination_reason=AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL,
            )

    pipeline, branch, _, _, _, _ = _pipeline(
        creative=creative,
        agentic_session=CapturingSession(),
        agentic_artifact_dir=str(artifact_dir),
    )
    previous = AgenticProposalSession(
        injected_output=AgenticProposalOutput(
            status=AgenticProposalStatus.FAILED,
            session_id="previous-failed",
            campaign_id="camp-1",
            branch_id="branch-1",
            termination_reason=AgenticTerminationReason.SESSION_TIMEOUT,
            failure_detail="safe timeout detail\nraw_metrics_ref should be removed",
        ),
        artifact_store=FileAgenticSessionArtifactStore(artifact_dir),
    )
    previous.run(
        pipeline._build_agentic_request(
            branch=branch,
            champion=_champion(),
            hypothesis_context={},
        )
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis == creative.hypothesis
    assert record is not None
    assert captured[0].resume_context is not None
    rendered = json.dumps(captured[0].resume_context, sort_keys=True)
    assert "previous-failed" in rendered
    assert "sanitized_resume_context_only" in rendered
    assert "raw_metrics_ref" not in rendered
    assert "SECRET" not in rendered


def test_agentic_pipeline_does_not_reuse_invalid_recovery_artifact(
    tmp_path: Path,
) -> None:
    artifact_dir = tmp_path / "agentic"
    captured: list[AgenticProposalRequest] = []
    creative = FakeCreative()

    class CapturingSession:
        def run(self, request: AgenticProposalRequest) -> AgenticProposalOutput:
            captured.append(request)
            return AgenticProposalOutput(
                status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
                session_id="fresh-session",
                campaign_id=request.campaign_id,
                branch_id=request.branch.branch_id,
                champion_version=request.champion.version if request.champion else None,
                problem_id=request.problem_id,
                problem_spec_hash=request.problem_spec_hash,
                hypothesis=creative.hypothesis,
                termination_reason=AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL,
            )

    pipeline, branch, _, _, _, _ = _pipeline(
        creative=creative,
        agentic_session=CapturingSession(),
        agentic_artifact_dir=str(artifact_dir),
    )
    previous = AgenticProposalSession(
        injected_output=AgenticProposalOutput(
            status=AgenticProposalStatus.FAILED,
            session_id="previous-invalid",
            campaign_id="camp-1",
            branch_id="branch-1",
            termination_reason=AgenticTerminationReason.SESSION_TIMEOUT,
            failure_detail="timeout",
        ),
        artifact_store=FileAgenticSessionArtifactStore(artifact_dir),
    )
    output = previous.run(
        pipeline._build_agentic_request(
            branch=branch,
            champion=_champion(),
            hypothesis_context={},
        )
    )
    output_ref = next(ref for ref in output.tainted_artifact_refs if ref.endswith("output.json"))
    artifact = json.loads(Path(output_ref).read_text(encoding="utf-8"))
    artifact["compact_transcript"] = [
        {
            "phase": "diagnose",
            "metadata": {
                "step_id": "tool-0001",
                "tool_name": "context.read_problem",
                "status": "ok",
                "result_summary": "raw_metrics_ref=/secret/raw.json",
            },
        }
    ]
    Path(output_ref).write_text(json.dumps(artifact), encoding="utf-8")
    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis == creative.hypothesis
    assert record is not None
    assert captured[0].resume_context is None
    report = pipeline.agentic_recovery_reports[branch.branch_id]
    assert report["validation_ok"] is False
    assert any("raw ref marker" in error for error in report["validation_errors"])


def test_agentic_failed_session_returns_typed_hypothesis_failure() -> None:
    failed_output = AgenticProposalOutput(
        status=AgenticProposalStatus.FAILED,
        session_id="",
        campaign_id="",
        branch_id="",
        termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
        failure_detail="no valid surface",
    )
    pipeline, branch, _, circuit, failures, _ = _pipeline(
        use_agentic_proposal=True,
        agentic_session=AgenticProposalSession(injected_output=failed_output),
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis is None
    assert record is None
    assert (
        pipeline.agentic_outputs[branch.branch_id].status
        == AgenticProposalStatus.FAILED
    )
    detail = pipeline.pop_hypothesis_failure_detail(branch.branch_id)
    assert detail == "agentic_proposal:hypothesis_generation_failed: no valid surface"
    assert len(failures) == 1
    assert circuit.failures == [detail]


@pytest.mark.parametrize(
    ("override", "expected_field"),
    [
        ({"branch_id": "wrong-branch"}, "branch_id"),
        ({"champion_version": 99}, "champion_version"),
        ({"problem_spec_hash": "wrong-spec"}, "problem_spec_hash"),
    ],
)
def test_agentic_completed_output_with_mismatched_anchor_is_rejected(
    override,
    expected_field: str,
) -> None:
    creative = FakeCreative()
    output_kwargs = {
        "status": AgenticProposalStatus.COMPLETED,
        "session_id": "session-1",
        "campaign_id": "camp-1",
        "branch_id": "branch-1",
        "champion_version": 1,
        "champion_weight_revision": 0,
        "problem_id": "toy",
        "problem_spec_hash": "spec-hash",
        "hypothesis": creative.hypothesis,
        "patch": creative.patch,
        "termination_reason": AgenticTerminationReason.COMPLETED,
    }
    output_kwargs.update(override)
    output = AgenticProposalOutput(**output_kwargs)
    pipeline, branch, _, circuit, failures, _ = _pipeline(
        use_agentic_proposal=True,
        agentic_session=AgenticProposalSession(injected_output=output),
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis is None
    assert record is None
    detail = pipeline.pop_hypothesis_failure_detail(branch.branch_id)
    assert detail is not None
    assert "agentic_proposal:anchor_validation_failed" in detail
    assert expected_field in detail
    assert pipeline.agentic_outputs[branch.branch_id].patch is None
    assert len(failures) == 1
    assert circuit.failures == [detail]


def test_agentic_artifact_dir_without_agentic_proposal_does_not_create_files(
    tmp_path: Path,
) -> None:
    artifact_dir = tmp_path / "agentic"
    pipeline, branch, _, _, _, _ = _pipeline(
        use_agentic_proposal=False,
        agentic_artifact_dir=str(artifact_dir),
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)
    patch = pipeline.generate_code(branch, hypothesis)

    assert hypothesis is not None
    assert record is not None
    assert patch is not None
    assert not artifact_dir.exists()
    assert pipeline.agentic_outputs == {}


def test_unsafe_agentic_session_and_scratch_path_segments_raise_without_write(
    tmp_path: Path,
) -> None:
    root = tmp_path / "artifacts"
    store = FileAgenticSessionArtifactStore(root)
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.FAILED,
        session_id="../escape",
        campaign_id="camp-1",
        branch_id="branch-1",
    )

    with pytest.raises(ValueError, match="unsafe session artifact path segment"):
        store.write_output(output)
    with pytest.raises(ValueError, match="unsafe session artifact path segment"):
        store.write_scratch("session-1", "bad/name", {"x": 1})

    assert not root.exists()


def test_partial_patch_unchecked_with_patch_does_not_return_usable_patch() -> None:
    creative = FakeCreative()
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.PARTIAL_PATCH_UNCHECKED,
        session_id="session-1",
        campaign_id="camp-1",
        branch_id="branch-1",
        champion_version=1,
        champion_weight_revision=0,
        problem_id="toy",
        problem_spec_hash="spec-hash",
        hypothesis=creative.hypothesis,
        patch=creative.patch,
    )
    pipeline, branch, _, circuit, failures, _ = _pipeline(
        use_agentic_proposal=True,
        agentic_session=AgenticProposalSession(injected_output=output),
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)
    stored = pipeline.agentic_outputs[branch.branch_id]
    patch = pipeline.generate_code(branch, hypothesis)

    assert hypothesis == creative.hypothesis
    assert record is not None
    assert stored.patch is None
    assert patch is None
    assert len(failures) == 1
    assert "non-completed output included unchecked patch" in failures[0][1].detail
    assert circuit.failures == [failures[0][1].detail]


def test_decision_features_do_not_include_agentic_rationale_or_memory() -> None:
    feature_names = {field.name for field in fields(DecisionFeatures)}

    assert "rationale_summary" not in feature_names
    assert "rejected_alternatives" not in feature_names
    assert "tainted_artifact_refs" not in feature_names
    assert "session_memory" not in feature_names
    assert "forced_surface" not in feature_names
    assert "forced_action" not in feature_names
    assert "forced_target_file" not in feature_names


def test_agentic_lineage_records_tainted_session_without_decision_rationale() -> None:
    creative = FakeCreative()
    registry = MemoryLineageRegistry()

    class SessionWithAudit:
        def run(self, request: AgenticProposalRequest) -> AgenticProposalOutput:
            return AgenticProposalOutput(
                status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
                session_id="aps-1",
                campaign_id=request.campaign_id,
                branch_id=request.branch.branch_id,
                champion_version=request.champion.version if request.champion else None,
                champion_weight_revision=getattr(request.champion, "weight_revision", None),
                problem_id=request.problem_id,
                problem_spec_hash=request.problem_spec_hash,
                hypothesis=creative.hypothesis,
                rationale_summary="private rationale must stay tainted",
                evidence_used=(
                    AgenticEvidenceRef(
                        observation_id="obs-1",
                        exposure_level="public_spec",
                        summary="safe summary",
                    ),
                ),
                transcript=(
                    AgenticTranscriptEvent(
                        phase="diagnose",
                        message="tool",
                        metadata={
                            "step_id": "tool-0001",
                            "tool_name": "context.list_surfaces",
                            "status": "ok",
                            "taint": "proposal",
                            "evidence_ref": "obs-1",
                            "result_summary": "safe summary",
                            "error_code": None,
                        },
                    ),
                ),
                self_check=AgenticSelfCheck(
                    schema_valid=True,
                    contract_preview_passed=False,
                    contract_preview_codes=("C1",),
                ),
                tainted_artifact_refs=("artifacts/aps-1/output.json",),
                termination_reason=AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL,
            )

    pipeline, branch, _, _, _, _ = _pipeline(
        creative=creative,
        agentic_session=SessionWithAudit(),
        lineage_registry=registry,
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis == creative.hypothesis
    assert record is not None
    assert len(registry.events) == 1
    event = registry.events[0]
    payload = json.loads(event["audit_payload_json"])
    assert event["event_kind"] == "agentic_proposal_session"
    assert event["decision_features_json"] == ""
    assert event["raw_metrics_ref"] == ""
    assert payload["session_id"] == "aps-1"
    assert payload["request_id"] == "aps-1"
    assert payload["schema_version"]
    assert payload["transcript_digest"]
    assert payload["contract_preview_passed"] is False
    assert "tool_steps" not in payload
    assert "transcript" not in payload
    rendered = json.dumps(event, sort_keys=True)
    assert "private rationale" not in rendered
    assert "context.list_surfaces" not in rendered
    assert "raw_metrics_ref" in event


def test_agentic_lineage_audit_payload_marks_absolute_tainted_refs_internal(
    tmp_path,
) -> None:
    registry = MemoryLineageRegistry()
    pipeline, branch, _, _, _, _ = _pipeline(
        use_agentic_proposal=True,
        lineage_registry=registry,
    )
    absolute_output_ref = tmp_path / "agentic" / "session-1" / "output.json"

    output = AgenticProposalOutput(
        status=AgenticProposalStatus.COMPLETED,
        session_id="session-1",
        campaign_id="camp-1",
        branch_id=branch.branch_id,
        request_id="request-1",
        idempotency_key="idempotency-1",
        transcript_digest="digest-1",
        self_check=AgenticSelfCheck(
            schema_valid=True,
            contract_preview_passed=True,
            contract_preview_codes=("C1",),
        ),
        tainted_artifact_refs=(
            str(absolute_output_ref),
            "artifacts/session-1/transcript.json",
        ),
        termination_reason=AgenticTerminationReason.COMPLETED,
    )

    pipeline._record_agentic_lineage_event(output)

    event = registry.events[-1]
    payload = json.loads(event["audit_payload_json"])
    assert event["event_kind"] == "agentic_proposal_session"
    assert payload["internal_only"] is True
    assert payload["tainted_artifact_refs_internal_only"] is True
    assert payload["tainted_artifact_ref_scope"] == "public_relative"
    assert not contains_absolute_path(payload)
    assert payload["tainted_artifact_refs"][0].startswith("artifact:output.json#")
    assert payload["tainted_artifact_refs"][1] == "artifacts/session-1/transcript.json"


def test_attempt_fix_builds_fix_context_and_returns_patch() -> None:
    pipeline, branch, runtime, _, _, _ = _pipeline()
    patch = PatchProposal(
        file_path="operators/bounded.py",
        action="modify",
        code_content="bad",
    )
    verification = VerificationResult(
        passed=False,
        checks=(CheckResult("SYNTAX", False, "light", "bad", 1),),
        failure_severity="light",
        first_failure="SYNTAX",
    )

    fixed = pipeline.attempt_fix(branch, patch, verification)

    assert fixed is not None
    assert fixed.file_path == "operators/bounded.py"
    assert runtime.fix_kwargs["failure_streak"] == {"proposal": 1}
    assert runtime.fix_kwargs["verification_result"] is verification


def test_attempt_fix_validation_error_returns_none_without_balance_stop() -> None:
    creative = FakeCreative(fix_error=ProposalValidationError("bad fix"))
    pipeline, branch, _, circuit, _, balance = _pipeline(creative=creative)
    patch = PatchProposal("operators/bounded.py", "modify", "bad")
    verification = VerificationResult(
        passed=False,
        checks=(CheckResult("SYNTAX", False, "light", "bad", 1),),
        failure_severity="light",
        first_failure="SYNTAX",
    )

    fixed = pipeline.attempt_fix(branch, patch, verification)

    assert fixed is None
    assert balance["value"] is False
    assert circuit.failures == []


def test_attempt_fix_balance_error_sets_stop_signal() -> None:
    creative = FakeCreative(fix_error=LLMBalanceError("no credits"))
    pipeline, branch, _, circuit, _, balance = _pipeline(creative=creative)
    patch = PatchProposal("operators/bounded.py", "modify", "bad")
    verification = VerificationResult(
        passed=False,
        checks=(CheckResult("SYNTAX", False, "light", "bad", 1),),
        failure_severity="light",
        first_failure="SYNTAX",
    )

    fixed = pipeline.attempt_fix(branch, patch, verification)

    assert fixed is None
    assert balance["value"] is True
    assert circuit.failures == ["no credits"]
