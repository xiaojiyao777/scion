from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from scion.cli.commands.init_run import _load_research_histories
from scion.config.problem import ProblemSpec, SearchSpace
from scion.core.evidence_recording import EvidenceRecorder
from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.models import (
    Branch,
    BranchState,
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


@pytest.mark.parametrize("stage", (ExperimentStage.VALIDATION, ExperimentStage.FROZEN))
def test_later_stage_step_is_wholly_excluded(tmp_path: Path, stage: ExperimentStage) -> None:
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


def test_screening_reuses_canonical_h_projection_without_raw_evidence() -> None:
    record = _record(_evaluated())

    assert record["protocol"]["evidence"]["stage"] == "screening"
    assert record["decision"]["value"] == "continue_explore"
    rendered = json.dumps(record)
    assert "raw_metrics" not in rendered
    assert "private-case" not in rendered
    assert "PRIVATE summary" not in rendered
    assert "decision_outcome" not in record["protocol"]["evidence"]


def test_real_cvrp_mechanism_envelope_round_trips_safe_aggregates(
    tmp_path: Path,
) -> None:
    from scion.problems.cvrp.proposal_mechanism_evidence import (
        CvrpProposalMechanismEvidenceProvider,
    )

    evidence = CvrpProposalMechanismEvidenceProvider().summarize_proposal_mechanism_evidence(
        stage="screening",
        selected_surface="solver_design",
        runtime_pairs=(),
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

    assert loaded[0]["protocol"]["evidence"]["mechanism_evidence"]["evidence"] == evidence


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
        ProblemRuntime(problem_spec=_spec(tmp_path), research_history=(record,))


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
