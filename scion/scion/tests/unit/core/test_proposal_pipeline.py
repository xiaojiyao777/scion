from __future__ import annotations

import threading
from types import SimpleNamespace

from scion.core.models import (
    Branch,
    BranchState,
    ChampionState,
    CheckResult,
    FailureEvent,
    HypothesisProposal,
    PatchProposal,
    VerificationResult,
)
from scion.core.proposal_pipeline import ProposalPipeline
from scion.proposal.engine import ProposalValidationError
from scion.proposal.llm_client import LLMBalanceError, LLMRetryExhaustedError


class FakeProblemRuntime:
    def __init__(self) -> None:
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
        self.hypothesis = HypothesisProposal(
            hypothesis_text="Bounded route-pair search.",
            change_locus="local_search",
            action="create_new",
            target_file="operators/bounded.py",
            suggested_weight=0.5,
        )
        self.patch = PatchProposal(
            file_path="operators/bounded.py",
            action="create",
            code_content="class Bounded: pass\n",
        )
        self.fix = PatchProposal(
            file_path="operators/bounded.py",
            action="modify",
            code_content="class Bounded: pass\n",
        )

    def generate_hypothesis(self, context):
        return self.hypothesis

    def generate_code(self, context):
        if self.code_error is not None:
            raise self.code_error
        return self.patch

    def fix_code(self, context):
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


def _pipeline(*, creative: FakeCreative | None = None):
    branch = _branch()
    sibling = _branch("sibling")
    runtime = FakeProblemRuntime()
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
        branch_workspaces={branch.branch_id: "/tmp/branch"},
        champion_lock=threading.Lock(),
        get_champion=_champion,
        step_history=[],
        failure_streak={"proposal": 1},
        consume_forced_locus=lambda: "local_search",
        search_memory=SimpleNamespace(),
        get_saturation_analyzer=lambda: None,
        get_baseline_metrics=lambda: None,
        get_latest_weight_opt_result=lambda: {"weights": "latest"},
        research_log=SimpleNamespace(),
        handle_failure=lambda b, f: failures.append((b, f)),
        circuit_breaker=circuit,
        mark_balance_exhausted=lambda: balance_exhausted.__setitem__("value", True),
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
