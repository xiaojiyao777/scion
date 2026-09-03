from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from scion.cli.commands.init_run import _load_research_histories
from scion.config.problem import ProblemSpec, SearchSpace
from scion.core.evidence_recording import EvidenceRecorder
from scion.core.execution_outcome import (
    PROVIDER_TRANSIENT_RETRIES_EXHAUSTED,
    ExecutionOutcome,
    ExecutionOutcomeRecord,
    disposition_failure_record,
)
from scion.core.models import (
    Branch,
    BranchState,
    CanaryResult,
    ChampionState,
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    PatchProposal,
    ProtocolResult,
    StepRecord,
)
from scion.core.problem_runtime import ProblemRuntime
from scion.core.research_history import (
    RESEARCH_HISTORY_SCHEMA,
    ResearchHistoryWriter,
    load_research_histories,
    normalize_research_history_record,
    project_research_history_step,
)
from scion.proposal.context_manager import ContextManager
from scion.proposal.context_snapshot import freeze_proposal_context
from scion.proposal.hypothesis_research_corpus import (
    build_hypothesis_research_corpus,
)


def _hypothesis(text: str = "Try a bounded mechanism.") -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text=text,
        change_locus="local_search",
        action="modify",
        target_file="operators/local_search.py",
        target_weakness="weak local improvement",
        expected_effect="better solutions",
    )


def _patch() -> PatchProposal:
    return PatchProposal(
        file_path="operators/local_search.py",
        action="modify",
        code_content="def improve(solution, rng):\n    return solution\n",
        test_hint="PRIVATE provider prose",
    )


def _verification_rejection(text: str = "Try a bounded mechanism.") -> StepRecord:
    return StepRecord(
        round_num=1,
        branch_id="private-branch",
        hypothesis=_hypothesis(text),
        patch=_patch(),
        contract_passed=True,
        verification_passed=False,
        protocol_result=None,
        decision=None,
        failure_stage="verification",
        failure_detail="PRIVATE failure detail",
        base_champion_version=1,
        base_source_ref="champion:v1",
        changed_files=("operators/local_search.py",),
        execution_outcome=ExecutionOutcomeRecord(
            outcome=ExecutionOutcome.RESEARCH_REJECTED,
            reason_code="VERIFICATION_LIGHT_REJECTED",
            detail="PRIVATE execution detail",
            provenance={
                "stage": "verification",
                "severity": "light",
                "verification_checks": [
                    {
                        "name": "unit_tests",
                        "passed": False,
                        "severity": "light",
                        "detail": "PRIVATE check detail",
                        "elapsed_ms": 12,
                        "metadata": {"raw_prompt": "PRIVATE provider payload"},
                    }
                ],
            },
        ),
    )


def _hypothesis_failure() -> StepRecord:
    return StepRecord(
        round_num=1,
        branch_id="private-branch",
        hypothesis=None,
        patch=None,
        contract_passed=None,
        verification_passed=None,
        protocol_result=None,
        decision=None,
        failure_stage="proposal_hypothesis",
        failure_detail="HYPOTHESIS_RESEARCH_ABSTAINED",
        base_champion_version=1,
        base_source_ref="champion:v1",
        changed_files=(),
        execution_outcome=ExecutionOutcomeRecord(
            outcome=ExecutionOutcome.RESEARCH_REJECTED,
            reason_code="HYPOTHESIS_RESEARCH_ABSTAINED",
            provenance={"stage": "proposal_hypothesis"},
        ),
    )


def _provider_transient_failure() -> StepRecord:
    return StepRecord(
        round_num=2,
        branch_id="private-branch",
        hypothesis=_hypothesis("Provider-independent algorithm hypothesis."),
        patch=None,
        contract_passed=True,
        verification_passed=False,
        protocol_result=None,
        decision=None,
        failure_stage="proposal_code",
        failure_detail="PRIVATE provider outage detail",
        base_champion_version=1,
        base_source_ref="champion:v1",
        changed_files=(),
        execution_outcome=ExecutionOutcomeRecord(
            outcome=ExecutionOutcome.RESEARCH_REJECTED,
            reason_code=PROVIDER_TRANSIENT_RETRIES_EXHAUSTED,
            detail="PRIVATE provider outage detail",
            provenance={
                "stage": "proposal_code",
                "exception_type": "LLMTransportError",
            },
        ),
    )


def _protocol(stage: ExperimentStage = ExperimentStage.SCREENING) -> ProtocolResult:
    return ProtocolResult(
        stage=stage,
        stats=EvalStats(
            n_cases=0,
            wins=0,
            losses=0,
            ties=0,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
            total_pairs=0,
            attempted_pairs=0,
            valid_pairs=0,
            failed_pairs=0,
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL",),
        exposed_summary="PRIVATE summary",
        raw_metrics_ref="private/raw_metrics.json",
        case_ids=("private-case",),
        seed_set=(42,),
    )


def _evaluated(stage: ExperimentStage = ExperimentStage.SCREENING) -> StepRecord:
    return StepRecord(
        round_num=2,
        branch_id="private-branch",
        hypothesis=_hypothesis(),
        patch=_patch(),
        contract_passed=True,
        verification_passed=True,
        protocol_result=_protocol(stage),
        decision=Decision.CONTINUE_EXPLORE,
        failure_stage="screening" if stage is ExperimentStage.SCREENING else None,
        failure_detail="PRIVATE protocol prose",
        base_champion_version=1,
        base_source_ref="champion:v1",
        changed_files=("operators/local_search.py",),
        decision_reason_codes=("SCREENING_FAIL",),
        execution_outcome=ExecutionOutcomeRecord(
            outcome=ExecutionOutcome.EVALUATED,
            reason_code="EVALUATED",
            provenance={"stage": stage.value},
        ),
    )


def _record(step: StepRecord, *, problem_id: str = "generic_demo") -> dict:
    record = project_research_history_step(step, problem_id=problem_id)
    assert record is not None
    return record


def _spec(tmp_path: Path, *, name: str = "generic_demo") -> ProblemSpec:
    root = tmp_path / "source"
    operators = root / "operators"
    operators.mkdir(parents=True, exist_ok=True)
    (operators / "local_search.py").write_text(
        "def improve(solution, rng):\n    return 'CURRENT'\n",
        encoding="utf-8",
    )
    return ProblemSpec(
        name=name,
        root_dir=str(root),
        operator_categories=["local_search"],
        search_space=SearchSpace(
            editable=["operators/*.py"],
            frozen=["solver.py"],
            import_whitelist=["math"],
        ),
    )


def test_writer_persists_only_ordinary_failure_before_memory_append(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(
        campaign_id="campaign",
        campaign_dir=tmp_path,
        problem_id="generic_demo",
    )
    history: list[StepRecord] = []

    recorder.record_step(_verification_rejection(), history)

    assert len(history) == 1
    raw = (tmp_path / "research_history.jsonl").read_text(encoding="utf-8")
    record = json.loads(raw)
    assert record["schema_version"] == RESEARCH_HISTORY_SCHEMA
    assert record["patch"]["changes"][0]["source"].endswith("return solution\n")
    assert record["outcome"] == {
        "outcome": "research_rejected",
        "stage": "verification",
        "reason_code": "VERIFICATION_LIGHT_REJECTED",
        "severity": "light",
        "checks": [{"name": "unit_tests", "passed": False, "severity": "light"}],
    }
    for forbidden in (
        "private-branch",
        "PRIVATE failure detail",
        "PRIVATE execution detail",
        "PRIVATE provider prose",
        "raw_prompt",
        "elapsed_ms",
        "metadata",
    ):
        assert forbidden not in raw


def test_provider_transient_step_remains_auditable_but_not_scientific_history(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(
        campaign_id="campaign",
        campaign_dir=tmp_path,
        problem_id="generic_demo",
    )
    history: list[StepRecord] = []
    ordinary = _verification_rejection()
    transient = _provider_transient_failure()

    recorder.record_step(ordinary, history)
    before = (tmp_path / "research_history.jsonl").read_bytes()
    recorder.record_step(transient, history)

    assert history == [ordinary, transient]
    assert history[-1].execution_outcome is not None
    assert history[-1].execution_outcome.reason_code == (
        PROVIDER_TRANSIENT_RETRIES_EXHAUSTED
    )
    assert project_research_history_step(
        transient,
        problem_id="generic_demo",
    ) is None
    assert (tmp_path / "research_history.jsonl").read_bytes() == before
    assert PROVIDER_TRANSIENT_RETRIES_EXHAUSTED.encode() not in before


def test_hypothesis_free_attempt_round_trips_as_one_redacted_history_row(
    tmp_path: Path,
) -> None:
    writer = ResearchHistoryWriter(tmp_path, problem_id="generic_demo")

    writer.append_step(_hypothesis_failure())

    raw = writer.path.read_text(encoding="utf-8")
    loaded = load_research_histories(
        [writer.path],
        expected_problem_id="generic_demo",
    )
    assert len(loaded) == 1
    assert loaded[0] == json.loads(raw)
    assert loaded[0] == {
        "schema_version": RESEARCH_HISTORY_SCHEMA,
        "problem_id": "generic_demo",
        "hypothesis": None,
        "selected_hypothesis_research_basis": None,
        "patch": None,
        "outcome": {
            "outcome": "research_rejected",
            "stage": "proposal_hypothesis",
            "reason_code": "HYPOTHESIS_RESEARCH_ABSTAINED",
        },
        "protocol": None,
        "decision": None,
    }
    for marker in (
        "private-branch",
        "RAW_SENTINEL",
        "H_BASIS_SENTINEL",
        "PROBE_SENTINEL",
        "RESERVED_SENTINEL",
    ):
        assert marker not in raw


def test_hypothesis_free_history_has_no_nearest_ranking_headline(
    tmp_path: Path,
) -> None:
    spec = _spec(tmp_path)
    record = _record(_hypothesis_failure(), problem_id=spec.name)
    manager = ContextManager(research_history=(record,))
    branch = Branch(
        branch_id="branch",
        state=BranchState.EXPLORE,
        base_champion_id=1,
    )
    champion = ChampionState(
        version=1,
        operator_pool={},
        code_snapshot_path=spec.root_dir,
    )

    context = manager.build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=spec,
    )
    _, histories, _ = build_hypothesis_research_corpus(context)

    assert context["prior_research_history"][0]["hypothesis"] is None
    assert len(histories) == 1
    assert "hypothesis" not in histories[0]["index"]


@pytest.mark.parametrize(
    ("field", "value"),
    (
        (
            "patch",
            {"changes": [{"file_path": "x.py", "action": "modify", "source": "x"}]},
        ),
        ("protocol", _record(_evaluated())["protocol"]),
        ("decision", _record(_evaluated())["decision"]),
    ),
)
def test_external_hypothesis_free_history_rejects_scientific_payloads(
    field: str,
    value: object,
) -> None:
    record = _record(_hypothesis_failure())
    record[field] = value

    with pytest.raises(ValueError, match="hypothesis-free"):
        normalize_research_history_record(
            record,
            expected_problem_id="generic_demo",
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ({"outcome": None}, "requires an outcome"),
        ({"stage": "proposal_code"}, "proposal_hypothesis"),
        ({"outcome_value": "evaluated"}, "cannot be evaluated"),
        ({"checks": []}, "only typed terminal fields"),
    ),
)
def test_external_hypothesis_free_history_rejects_nonterminal_shapes(
    mutation: dict[str, object],
    message: str,
) -> None:
    record = _record(_hypothesis_failure())
    if "outcome" in mutation:
        record["outcome"] = mutation["outcome"]
    else:
        outcome = record["outcome"]
        assert isinstance(outcome, dict)
        if "stage" in mutation:
            outcome["stage"] = mutation["stage"]
        if "outcome_value" in mutation:
            outcome["outcome"] = mutation["outcome_value"]
        if "checks" in mutation:
            outcome["checks"] = mutation["checks"]

    with pytest.raises(ValueError, match=message):
        normalize_research_history_record(
            record,
            expected_problem_id="generic_demo",
        )


def test_all_tracked_v04_histories_satisfy_cross_field_contracts() -> None:
    inputs = (
        Path(__file__).resolve().parents[4] / "docs" / "experiments" / "v0.4" / "inputs"
    )
    paths = sorted(inputs.glob("*research-history.jsonl"))

    assert len(paths) == 16
    structural_shapes: set[tuple[bool, str, bool, bool]] = set()
    for path in paths:
        records = load_research_histories([path], expected_problem_id="cvrp")
        for record in records:
            outcome = record["outcome"]
            assert isinstance(outcome, dict)
            structural_shapes.add(
                (
                    record["patch"] is not None,
                    outcome["stage"],
                    record["protocol"] is not None,
                    record["decision"] is not None,
                )
            )

    assert structural_shapes == {
        (False, "proposal_code", False, False),
        (True, "proposal_code", False, False),
        (True, "verification", False, False),
        (True, "evaluation", False, False),
        (True, "screening", True, True),
    }


def test_history_with_hypothesis_requires_typed_outcome() -> None:
    record = _record(_verification_rejection())
    record["outcome"] = None

    with pytest.raises(ValueError, match="requires an outcome"):
        normalize_research_history_record(
            record,
            expected_problem_id="generic_demo",
        )


def test_proposal_hypothesis_stage_rejects_nonempty_hypothesis() -> None:
    record = _record(_verification_rejection())
    record["outcome"]["stage"] = "proposal_hypothesis"

    with pytest.raises(ValueError, match="cannot carry a hypothesis"):
        normalize_research_history_record(
            record,
            expected_problem_id="generic_demo",
        )


@pytest.mark.parametrize(
    "missing_field",
    ("protocol", "decision"),
)
def test_screening_protocol_and_decision_must_be_present_together(
    missing_field: str,
) -> None:
    record = _record(_evaluated())
    record[missing_field] = None

    with pytest.raises(ValueError, match="Protocol and Decision"):
        normalize_research_history_record(
            record,
            expected_problem_id="generic_demo",
        )


def test_evaluated_canary_abandonment_is_the_only_decision_without_protocol() -> None:
    record = _record(_evaluated())
    record["protocol"] = None
    record["outcome"] = {
        "outcome": "evaluated",
        "stage": "canary",
        "reason_code": "EVALUATION_COMPLETED",
    }
    record["decision"]["value"] = "abandon"

    normalized = normalize_research_history_record(
        record,
        expected_problem_id="generic_demo",
    )

    assert normalized["protocol"] is None
    assert normalized["decision"]["value"] == "abandon"
    assert normalized["outcome"]["stage"] == "canary"


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("patch", None),
        (
            "outcome",
            {
                "outcome": "research_rejected",
                "stage": "canary",
                "reason_code": "CANARY_FAILED",
            },
        ),
        (
            "outcome",
            {
                "outcome": "evaluated",
                "stage": "screening",
                "reason_code": "EVALUATION_COMPLETED",
            },
        ),
        (
            "decision",
            {
                "value": "continue_explore",
                "reason_codes": [],
                "engine_reason_codes": [],
                "diagnostic_reason_codes": [],
                "bypass_reason_codes": [],
            },
        ),
    ),
)
def test_other_decision_without_protocol_shapes_fail_closed(
    field: str,
    value: object,
) -> None:
    record = _record(_evaluated())
    record["protocol"] = None
    record["outcome"] = {
        "outcome": "evaluated",
        "stage": "canary",
        "reason_code": "EVALUATION_COMPLETED",
    }
    record["decision"]["value"] = "abandon"
    record[field] = value

    with pytest.raises(ValueError, match="Protocol and Decision"):
        normalize_research_history_record(
            record,
            expected_problem_id="generic_demo",
        )


def test_evaluated_outcome_without_protocol_is_rejected() -> None:
    record = _record(_verification_rejection())
    record["outcome"]["outcome"] = "evaluated"
    record["outcome"]["stage"] = "screening"

    with pytest.raises(ValueError, match="evaluated outcome requires"):
        normalize_research_history_record(
            record,
            expected_problem_id="generic_demo",
        )


def test_protocol_requires_patch_and_evaluated_matching_outcome() -> None:
    without_patch = _record(_evaluated())
    without_patch["patch"] = None
    with pytest.raises(ValueError, match="Protocol requires a patch"):
        normalize_research_history_record(
            without_patch,
            expected_problem_id="generic_demo",
        )

    non_evaluated = _record(_evaluated())
    non_evaluated["outcome"]["outcome"] = "not_evaluated"
    with pytest.raises(ValueError, match="evaluated outcome requires"):
        normalize_research_history_record(
            non_evaluated,
            expected_problem_id="generic_demo",
        )

    mismatched_stage = _record(_evaluated())
    mismatched_stage["outcome"]["stage"] = "evaluation"
    with pytest.raises(ValueError, match="must match Protocol evidence stage"):
        normalize_research_history_record(
            mismatched_stage,
            expected_problem_id="generic_demo",
        )


def test_writer_failure_preserves_atomic_prefix_and_memory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scion.core.research_history as module

    recorder = EvidenceRecorder(
        campaign_id="campaign",
        campaign_dir=tmp_path,
        problem_id="generic_demo",
    )
    history: list[StepRecord] = []
    recorder.record_step(_verification_rejection("first"), history)
    before = (tmp_path / "research_history.jsonl").read_bytes()

    monkeypatch.setattr(
        module,
        "_write_bytes_atomically",
        lambda _path, _content: (_ for _ in ()).throw(OSError("disk full")),
    )
    with pytest.raises(OSError, match="disk full"):
        recorder.record_step(_verification_rejection("second"), history)

    assert (tmp_path / "research_history.jsonl").read_bytes() == before
    assert [step.hypothesis.hypothesis_text for step in history] == ["first"]


def test_writer_record_limit_is_nonfatal_and_stops_future_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import scion.core.research_history as module

    monkeypatch.setattr(module, "MAX_RESEARCH_HISTORY_RECORDS", 1)
    writer = ResearchHistoryWriter(tmp_path, problem_id="generic_demo")
    writer.append_step(_verification_rejection("first"))
    before = writer.path.read_bytes()

    writer.append_step(_verification_rejection("second"))
    monkeypatch.setattr(
        module,
        "project_research_history_step",
        lambda _step, *, problem_id: (_ for _ in ()).throw(
            AssertionError(f"unexpected projection for {problem_id}")
        ),
    )
    writer.append_step(_verification_rejection("third"))

    assert writer.path.read_bytes() == before
    assert "record limit 1 reached" in caplog.text


def test_writer_skips_oversized_line_and_keeps_projecting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import scion.core.research_history as module

    small = _verification_rejection("small")
    small_line = (
        json.dumps(
            _record(small),
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    monkeypatch.setattr(module, "MAX_RESEARCH_HISTORY_LINE_BYTES", len(small_line))
    writer = ResearchHistoryWriter(tmp_path, problem_id="generic_demo")

    writer.append_step(_verification_rejection("x" * (len(small_line) + 1)))
    writer.append_step(small)

    assert writer.path.read_bytes() == small_line
    assert "Skipping research history record" in caplog.text
    assert f"{len(small_line)}-byte line limit" in caplog.text


def test_recorder_keeps_steps_after_history_file_limit_and_preserves_prefix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import scion.core.research_history as module

    recorder = EvidenceRecorder(
        campaign_id="campaign",
        campaign_dir=tmp_path,
        problem_id="generic_demo",
    )
    history: list[StepRecord] = []
    first = _verification_rejection("first")
    second = _verification_rejection("second")
    third = _verification_rejection("third")
    recorder.record_step(first, history)
    path = tmp_path / "research_history.jsonl"
    before = path.read_bytes()
    monkeypatch.setattr(module, "MAX_RESEARCH_HISTORY_FILE_BYTES", len(before))

    recorder.record_step(second, history)
    monkeypatch.setattr(
        module,
        "project_research_history_step",
        lambda _step, *, problem_id: (_ for _ in ()).throw(
            AssertionError(f"unexpected projection for {problem_id}")
        ),
    )
    recorder.record_step(third, history)

    assert history == [first, second, third]
    assert path.read_bytes() == before
    assert load_research_histories(
        [path], expected_problem_id="generic_demo"
    ) == (_record(first),)
    assert "file limit" in caplog.text


@pytest.mark.parametrize("stage", (ExperimentStage.VALIDATION, ExperimentStage.FROZEN))
def test_later_stage_step_is_wholly_excluded(
    tmp_path: Path, stage: ExperimentStage
) -> None:
    writer = ResearchHistoryWriter(tmp_path, problem_id="generic_demo")

    writer.append_step(_evaluated(stage))

    assert not writer.path.exists()


def test_any_heldout_stage_marker_excludes_the_whole_step(tmp_path: Path) -> None:
    step = _verification_rejection()
    step.execution_outcome = replace(
        step.execution_outcome,
        provenance={"stage": "validation"},
    )
    writer = ResearchHistoryWriter(tmp_path, problem_id="generic_demo")

    writer.append_step(step)

    assert not writer.path.exists()


@pytest.mark.parametrize("stage", (ExperimentStage.VALIDATION, ExperimentStage.FROZEN))
def test_disposition_failure_after_heldout_protocol_is_wholly_excluded(
    tmp_path: Path,
    stage: ExperimentStage,
) -> None:
    step = _evaluated(stage)
    completed_protocol = step.protocol_result
    assert completed_protocol is not None
    step.protocol_result = None
    step.decision = None
    step.failure_stage = "candidate_disposition"
    step.failure_detail = "cleanup unavailable"
    step.execution_outcome = disposition_failure_record(
        reason_code="BRANCH_WORKSPACE_DISCARD_FAILED",
        error=OSError("cleanup unavailable"),
        operation="discard_branch_workspace",
        completed_protocol=completed_protocol,
        unapplied_decision=Decision.ABANDON,
    )
    writer = ResearchHistoryWriter(tmp_path, problem_id="generic_demo")

    writer.append_step(step)

    assert not writer.path.exists()


def test_validation_canary_abandonment_remains_wholly_excluded(
    tmp_path: Path,
) -> None:
    step = _evaluated(ExperimentStage.VALIDATION)
    step.protocol_result = None
    step.decision = Decision.ABANDON
    step.failure_stage = "canary"
    step.failure_detail = "CANARY_FAILED"
    step.canary_result = CanaryResult(
        passed=False,
        failure_category="candidate_failure",
        reason_codes=("CANARY_FAILED",),
    )
    step.execution_outcome = ExecutionOutcomeRecord(
        outcome=ExecutionOutcome.EVALUATED,
        reason_code="EVALUATION_COMPLETED",
        provenance={"stage": "validation"},
    )
    writer = ResearchHistoryWriter(tmp_path, problem_id="generic_demo")

    writer.append_step(step)

    assert not writer.path.exists()


def test_screening_reuses_canonical_h_projection_without_raw_evidence() -> None:
    record = _record(_evaluated())

    assert record["protocol"]["evidence"]["stage"] == "screening"
    assert record["decision"]["value"] == "continue_explore"
    rendered = json.dumps(record)
    assert "raw_metrics" not in rendered
    assert "private-case" not in rendered
    assert "PRIVATE summary" not in rendered
    assert "decision_outcome" not in record["protocol"]["evidence"]


def test_selected_basis_is_strictly_normalized_and_old_rows_remain_loadable(
    tmp_path: Path,
) -> None:
    basis = {
        "read_refs": ("source-0001", "history-0002"),
        "nearest_prior_refs": ("history-0002",),
        "material_delta": "  Change the selected mechanism.  ",
        "alternatives_considered": ("  Keep the current mechanism.  ",),
        "observable_prediction": "  Screening should improve.  ",
        "falsification_condition": "  Reject if screening does not improve.  ",
    }
    step = _verification_rejection()
    step.selected_hypothesis_research_basis = basis

    projected = project_research_history_step(step, problem_id="generic_demo")
    assert projected is not None
    assert projected["selected_hypothesis_research_basis"] == {
        "read_refs": ["source-0001", "history-0002"],
        "nearest_prior_refs": ["history-0002"],
        "material_delta": "Change the selected mechanism.",
        "alternatives_considered": ["Keep the current mechanism."],
        "observable_prediction": "Screening should improve.",
        "falsification_condition": "Reject if screening does not improve.",
    }

    legacy = dict(projected)
    legacy.pop("selected_hypothesis_research_basis")
    path = tmp_path / "legacy.jsonl"
    path.write_text(json.dumps(legacy) + "\n", encoding="utf-8")
    loaded = load_research_histories([path], expected_problem_id="generic_demo")
    assert loaded[0]["selected_hypothesis_research_basis"] is None


def test_selected_basis_rejects_noncanonical_or_nonprimitive_shapes() -> None:
    record = _record(_verification_rejection())
    record["selected_hypothesis_research_basis"] = {
        "read_refs": ["source-0001"],
        "nearest_prior_refs": [],
        "material_delta": "Change the selected mechanism.",
        "alternatives_considered": ["Keep the current mechanism."],
        "observable_prediction": "Screening should improve.",
        "falsification_condition": "Reject if screening does not improve.",
        "unexpected": "must fail closed",
    }

    with pytest.raises(ValueError, match="six required fields"):
        normalize_research_history_record(record, expected_problem_id="generic_demo")


def test_selected_basis_preserves_optional_ordered_history_review() -> None:
    record = _record(_verification_rejection())
    record["selected_hypothesis_research_basis"] = {
        "read_refs": ["source-0001", "history-0002", "history-0003"],
        "nearest_prior_refs": ["history-0002", "history-0003"],
        "material_delta": "Change the selected mechanism.",
        "alternatives_considered": ["Keep the current mechanism."],
        "observable_prediction": "Screening should improve.",
        "falsification_condition": "Reject if screening does not improve.",
        "history_review": [
            {"ref": "history-0003", "disposition": "used"},
            {
                "ref": "history-0004",
                "disposition": "rejected",
                "reason": "Its failure mechanism does not apply.",
            },
        ],
    }

    normalized = normalize_research_history_record(
        record, expected_problem_id="generic_demo"
    )

    assert (
        normalized["selected_hypothesis_research_basis"]["history_review"]
        == record["selected_hypothesis_research_basis"]["history_review"]
    )


@pytest.mark.parametrize(
    ("review", "nearest", "message"),
    [
        (
            [{"ref": "history-0003", "disposition": "used"}],
            ["history-0002"],
            "used history_review refs",
        ),
        (
            [
                {
                    "ref": "history-0003",
                    "disposition": "rejected",
                    "reason": "Different mechanism.",
                }
            ],
            ["history-0002", "history-0003"],
            "rejected history_review refs",
        ),
    ],
)
def test_selected_basis_history_review_matches_citations(
    review: list[dict[str, str]],
    nearest: list[str],
    message: str,
) -> None:
    record = _record(_verification_rejection())
    record["selected_hypothesis_research_basis"] = {
        "read_refs": ["source-0001", "history-0002", "history-0003"],
        "nearest_prior_refs": nearest,
        "material_delta": "Change the selected mechanism.",
        "alternatives_considered": ["Keep the current mechanism."],
        "observable_prediction": "Screening should improve.",
        "falsification_condition": "Reject if screening does not improve.",
        "history_review": review,
    }

    with pytest.raises(ValueError, match=message):
        normalize_research_history_record(
            record,
            expected_problem_id="generic_demo",
        )


def test_real_cvrp_mechanism_envelope_round_trips_safe_aggregates(
    tmp_path: Path,
) -> None:
    from scion.problems.cvrp.proposal_mechanism_evidence import (
        CvrpProposalMechanismEvidenceProvider,
    )

    evidence = (
        CvrpProposalMechanismEvidenceProvider().summarize_proposal_mechanism_evidence(
            stage="screening",
            selected_surface="solver_design",
            runtime_pairs=(),
        )
    )
    step = _evaluated()
    step.protocol_result = replace(
        step.protocol_result,
        mechanism_evidence={
            "schema_version": "scion.problem_proposal_mechanism_evidence.v1",
            "problem_family": "cvrp",
            "producer": "problem_provider",
            "evidence": evidence,
        },
    )
    record = _record(step, problem_id="cvrp")
    path = tmp_path / "cvrp.jsonl"
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    loaded = load_research_histories([path], expected_problem_id="cvrp")

    assert (
        loaded[0]["protocol"]["evidence"]["mechanism_evidence"]["evidence"] == evidence
    )


def test_writer_round_trips_safe_problem_owned_family_attribution(
    tmp_path: Path,
) -> None:
    from scion.problems.cvrp.proposal_mechanism_evidence import (
        CvrpProposalMechanismEvidenceProvider,
    )

    subject = {
        "schema_version": "scion.problem_proposal_subject.v1",
        "changes": [
            {
                "file_path": "policies/baseline_modules/local_search.py",
                "action": "modify",
                "before_source": ("def _default_vns_operators():\n    return ()\n"),
                "after_source": (
                    "def _default_vns_operators():\n    return ('swap',)\n"
                ),
            }
        ],
    }
    provider = CvrpProposalMechanismEvidenceProvider()
    evidence = provider.summarize_proposal_mechanism_evidence(
        stage="screening",
        selected_surface="solver_design",
        proposal_subject=subject,
        runtime_pairs=[
            {
                "candidate_runtime": {
                    "solver_algorithm_elapsed_ms": 10,
                    "solver_algorithm_solution_progress": {
                        "initial_total_distance": 90.0,
                        "initial_route_count": 2,
                        "final_total_distance": 80.0,
                    },
                    "solver_algorithm_phase_accepted_moves": {"vns": 1},
                    "solver_algorithm_phase_improvement_counts": {"vns": 1},
                    "solver_algorithm_phase_delta_sum": {"vns": 10.0},
                },
                "champion_runtime": {
                    "solver_algorithm_elapsed_ms": 10,
                    "solver_algorithm_solution_progress": {
                        "initial_total_distance": 100.0,
                        "initial_route_count": 2,
                        "final_total_distance": 90.0,
                    },
                    "solver_algorithm_phase_accepted_moves": {"vns": 0},
                    "solver_algorithm_phase_improvement_counts": {"vns": 0},
                    "solver_algorithm_phase_delta_sum": {"vns": 0.0},
                },
            }
        ],
    )
    step = _evaluated()
    step.protocol_result = replace(
        step.protocol_result,
        mechanism_evidence={
            "schema_version": "scion.problem_proposal_mechanism_evidence.v1",
            "problem_family": "cvrp",
            "producer": "problem_provider",
            "evidence": evidence,
        },
    )
    writer = ResearchHistoryWriter(tmp_path, problem_id="cvrp")

    writer.append_step(step)
    loaded = load_research_histories(
        [writer.path],
        expected_problem_id="cvrp",
    )

    attribution = loaded[0]["protocol"]["evidence"]["mechanism_evidence"]["evidence"][
        "mechanism_attribution"
    ]
    assert attribution["attribution_status"] == "family_observable_changed"
    assert attribution["attribution_resolution"] == "family_association"
    assert attribution["exact_mechanism_activation"] is False
    assert attribution["changed_source_roles"] == ["local_search"]
    assert attribution["changed_symbol_names"] == ["_default_vns_operators"]
    assert {
        observation["signal"] for observation in attribution["activation_observations"]
    } >= {
        "vns_move_attempts",
        "vns_accepted_moves",
        "vns_improvement_count",
        "vns_delta_sum",
    }


def test_explicit_multi_history_loader_preserves_file_and_line_order(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    first.write_text(
        json.dumps(_record(_verification_rejection("first"))) + "\n",
        encoding="utf-8",
    )
    second.write_text(
        json.dumps(_record(_verification_rejection("second"))) + "\n",
        encoding="utf-8",
    )

    loaded = load_research_histories(
        [first, second], expected_problem_id="generic_demo"
    )

    assert [item["hypothesis"]["text"] for item in loaded] == ["first", "second"]
    with pytest.raises(ValueError, match="problem_id mismatch"):
        load_research_histories([first], expected_problem_id="another_problem")


@pytest.mark.parametrize(
    "key",
    (
        "path",
        "detail",
        "failure_detail",
        "workspace_path",
        "case_id",
        "seed",
        "branch_id",
        "campaign_id",
        "run_id",
        "observation_id",
    ),
)
def test_loader_rejects_sensitive_nested_mechanism_fields(
    tmp_path: Path, key: str
) -> None:
    record = _record(_evaluated())
    record["protocol"]["evidence"]["mechanism_evidence"] = {
        "schema_version": "scion.problem_proposal_mechanism_evidence.v1",
        "problem_family": "generic_demo",
        "producer": "problem_provider",
        "evidence": {"nested": {key: "SENTINEL"}},
    }
    path = tmp_path / f"{key}.jsonl"
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="forbidden research history field"):
        load_research_histories([path], expected_problem_id="generic_demo")


def test_loader_rejects_noncanonical_protocol_field(tmp_path: Path) -> None:
    record = _record(_evaluated())
    record["protocol"]["evidence"]["arbitrary_evidence"] = "SENTINEL"
    path = tmp_path / "extra.jsonl"
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="canonical projection"):
        load_research_histories([path], expected_problem_id="generic_demo")


@pytest.mark.parametrize("stage", ("validation", "frozen"))
def test_external_heldout_outcome_is_rejected(stage: str) -> None:
    record = _record(_verification_rejection())
    record["outcome"]["stage"] = stage

    with pytest.raises(ValueError, match="held-out"):
        normalize_research_history_record(
            record,
            expected_problem_id="generic_demo",
        )


def test_programmatic_runtime_rejects_malformed_history(tmp_path: Path) -> None:
    record = _record(_verification_rejection())
    record["outcome"]["stage"] = "validation"

    with pytest.raises(ValueError, match="held-out"):
        ProblemRuntime(
            adapter=type("Adapter", (), {"spec": _spec(tmp_path)})(),
            research_history=(record,),
        )


def test_loader_enforces_bounded_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scion.core.research_history as module

    path = tmp_path / "large.jsonl"
    path.write_bytes(b"x" * 65)
    monkeypatch.setattr(module, "MAX_RESEARCH_HISTORY_FILE_BYTES", 64)

    with pytest.raises(ValueError, match="file is too large"):
        load_research_histories([path], expected_problem_id="generic_demo")


def test_invalid_hypothesis_target_is_never_persisted() -> None:
    step = _verification_rejection()
    step.hypothesis.target_file = "/PRIVATE/../../target.py"

    record = _record(step)

    assert record["hypothesis"]["target_file"] is None
    assert "PRIVATE" not in json.dumps(record)


def test_cli_history_loader_uses_declared_problem_id(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    path = tmp_path / "history.jsonl"
    path.write_text(
        json.dumps(_record(_verification_rejection(), problem_id=spec.name)) + "\n",
        encoding="utf-8",
    )

    loaded = _load_research_histories([path], problem_spec=spec)

    assert len(loaded) == 1


def test_imported_history_is_h_only_and_current_source_is_authoritative(
    tmp_path: Path,
) -> None:
    spec = _spec(tmp_path)
    record = _record(_verification_rejection(), problem_id=spec.name)
    manager = ContextManager(research_history=(record,))
    branch = Branch(branch_id="branch", state=BranchState.EXPLORE, base_champion_id=1)
    champion = ChampionState(
        version=1,
        operator_pool={},
        code_snapshot_path=spec.root_dir,
    )

    h_context = manager.build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=spec,
    )
    assert h_context["prior_research_history"][0]["hypothesis"]["text"]
    assert "return 'CURRENT'" in h_context["champion_operators_code"]
    freeze_proposal_context("hypothesis", h_context)

    c_context = manager.build_code_context(
        branch=branch,
        hypothesis=_hypothesis(),
        champion=champion,
        problem_spec=spec,
    )
    assert "prior_research_history" not in c_context
