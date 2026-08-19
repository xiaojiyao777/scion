"""Independent adversarial tests for ordinary cross-campaign history."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.models import ExperimentStage, HypothesisProposal, StepRecord
from scion.core.research_history import (
    RESEARCH_HISTORY_SCHEMA,
    ResearchHistoryWriter,
    load_research_histories,
    normalize_research_history_record,
)


def _base_record() -> dict:
    return {
        "schema_version": RESEARCH_HISTORY_SCHEMA,
        "problem_id": "generic_demo",
        "hypothesis": {
            "text": "Try one bounded mechanism.",
            "change_locus": "local_search",
            "action": "modify",
            "target_file": "operators/local_search.py",
            "predicted_direction": "improve",
            "target_weakness": "weak moves",
            "expected_effect": "better solutions",
            "suggested_weight": None,
        },
        "patch": None,
        "outcome": {
            "outcome": "evaluated",
            "stage": "screening",
            "reason_code": "EVALUATED",
        },
        "protocol": {
            "candidate_composition": {
                "attribution_scope": "current_step_candidate",
                "protocol_comparison_scope": "candidate_vs_champion",
                "evaluation_candidate": "branch_state_after_current_step_patch",
                "current_step_change_scope": "incremental_patch",
                "incremental_effect_isolated": True,
                "current_step": {"target_files": ["operators/local_search.py"]},
            },
            "evidence": {
                "stage": "screening",
                "protocol_outcome": {"gate_outcome": "pass"},
                "objective_outcome": {
                    "semantics": "minimize",
                    "aggregate": {},
                    "aggregation": {
                        "statistical_unit": "case",
                        "method": "case_median",
                        "equivalence_band": 0.0,
                        "win_rate_scope": "case_level_gate",
                        "median_delta_scope": "case_medians",
                        "ci_scope": "case_medians",
                    },
                },
                "case_outcomes": {"case_feedback": []},
            },
        },
        "decision": {
            "value": "continue_explore",
            "reason_codes": [],
            "engine_reason_codes": [],
            "diagnostic_reason_codes": [],
            "bypass_reason_codes": [],
        },
    }


@pytest.mark.parametrize(
    ("location", "key"),
    (
        ("composition", "totally_new"),
        ("evidence", "totally_new"),
        ("mechanism", "failure_detail"),
        ("mechanism", "workspace_path"),
        ("mechanism", "run_id"),
    ),
)
def test_import_rejects_protocol_injection(location: str, key: str) -> None:
    record = _base_record()
    if location == "composition":
        record["protocol"]["candidate_composition"][key] = "SENTINEL"
    elif location == "evidence":
        record["protocol"]["evidence"][key] = "SENTINEL"
    else:
        record["protocol"]["evidence"]["mechanism_evidence"] = {
            "schema_version": "scion.problem_proposal_mechanism_evidence.v1",
            "problem_family": "generic_demo",
            "producer": "problem_provider",
            "evidence": {"nested": {key: "SENTINEL"}},
        }

    with pytest.raises(ValueError):
        normalize_research_history_record(
            record,
            expected_problem_id="generic_demo",
        )


def test_safe_aggregate_case_counts_remain_ordinary_evidence() -> None:
    record = _base_record()
    coverage = {"requested_cases": 3, "observed_cases": 2, "unavailable_cases": 1}
    record["protocol"]["evidence"]["mechanism_evidence"] = {
        "schema_version": "scion.problem_proposal_mechanism_evidence.v1",
        "problem_family": "cvrp",
        "producer": "problem_provider",
        "evidence": {"instance_feasibility": {"coverage": coverage}},
    }

    normalized = normalize_research_history_record(
        record,
        expected_problem_id="generic_demo",
    )

    assert normalized["protocol"]["evidence"]["mechanism_evidence"]["evidence"][
        "instance_feasibility"
    ]["coverage"] == coverage


def test_nested_payload_depth_is_bounded() -> None:
    record = _base_record()
    nested: dict = {}
    record["protocol"]["evidence"]["mechanism_evidence"] = {
        "schema_version": "scion.problem_proposal_mechanism_evidence.v1",
        "problem_family": "generic_demo",
        "producer": "problem_provider",
        "evidence": nested,
    }
    for index in range(32):
        child: dict = {}
        nested[f"level_{index}"] = child
        nested = child

    with pytest.raises(ValueError, match="maximum depth"):
        normalize_research_history_record(
            record,
            expected_problem_id="generic_demo",
        )


def test_empty_explicit_inputs_do_not_discover_campaign_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "research_history.jsonl").write_text("not-json\n", encoding="utf-8")
    (tmp_path / "campaign_summary.json").write_text("not-json\n", encoding="utf-8")
    (tmp_path / "scion.db").write_bytes(b"not-a-database")
    monkeypatch.chdir(tmp_path)

    assert load_research_histories([], expected_problem_id="generic_demo") == ()


def test_explicit_duplicate_path_is_not_deduplicated(tmp_path: Path) -> None:
    path = tmp_path / "history.jsonl"
    path.write_text(json.dumps(_base_record()) + "\n", encoding="utf-8")

    loaded = load_research_histories(
        [path, path],
        expected_problem_id="generic_demo",
    )

    assert len(loaded) == 2


def test_duplicate_json_key_is_rejected(tmp_path: Path) -> None:
    rendered = json.dumps(_base_record())
    path = tmp_path / "duplicate.jsonl"
    path.write_text(
        rendered.replace('"problem_id":', '"problem_id":"shadow","problem_id":', 1)
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate research history JSON key"):
        load_research_histories([path], expected_problem_id="generic_demo")


def test_writer_refuses_existing_history_instead_of_overwriting(tmp_path: Path) -> None:
    path = tmp_path / "research_history.jsonl"
    path.write_bytes(b"EXISTING-SENTINEL\n")

    with pytest.raises(FileExistsError, match="already exists"):
        ResearchHistoryWriter(tmp_path, problem_id="generic_demo")

    assert path.read_bytes() == b"EXISTING-SENTINEL\n"


def _visible_step(round_num: int) -> StepRecord:
    return StepRecord(
        round_num=round_num,
        branch_id="host-only-branch",
        hypothesis=HypothesisProposal(
            hypothesis_text=f"ordinary-{round_num}",
            change_locus="local_search",
            action="modify",
            target_file="operators/local_search.py",
        ),
        patch=None,
        contract_passed=False,
        verification_passed=None,
        protocol_result=None,
        decision=None,
        failure_stage="hypothesis_contract",
        failure_detail="host-only detail",
        execution_outcome=ExecutionOutcomeRecord(
            outcome=ExecutionOutcome.RESEARCH_REJECTED,
            reason_code="HYPOTHESIS_CONTRACT_REJECTED",
            provenance={"stage": "hypothesis_contract"},
        ),
    )


def test_heldout_steps_never_enter_ordered_visible_prefix(tmp_path: Path) -> None:
    writer = ResearchHistoryWriter(tmp_path, problem_id="generic_demo")
    writer.append_step(_visible_step(1))
    for round_num, stage in (
        (2, ExperimentStage.VALIDATION),
        (3, ExperimentStage.FROZEN),
    ):
        heldout = _visible_step(round_num)
        heldout.protocol_result = SimpleNamespace(stage=stage)
        writer.append_step(heldout)
    writer.append_step(_visible_step(4))

    records = [
        json.loads(line)
        for line in writer.path.read_text(encoding="utf-8").splitlines()
    ]
    assert [record["hypothesis"]["text"] for record in records] == [
        "ordinary-1",
        "ordinary-4",
    ]
