"""Lossless direct-v3 outer smoke over the real warehouse runtime."""
from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

import yaml

from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.core.campaign import CampaignManager
from scion.core.execution_outcome import ExecutionOutcome
from scion.core.models import ChampionState, DecisionFeatures, ExperimentStage
from scion.problem.bridge import bridge_problem_spec_v1
from scion.problem.loader import load_problem_adapter
from scion.problem.spec import ProblemSpecV1
from scion.proposal.edit_protocol.normalization import source_digest_for_content
from scion.proposal.mock_client import MockLLMClient
from scion.protocol.experiment import ExperimentProtocol, SeedLedger, SplitManager
from scion.runtime.runner import ResourceLimits
from scion.runtime.subprocess_runner import LocalSubprocessRunner
from scion.verification.gate import VerificationGate


REPO_ROOT = Path(__file__).resolve().parents[3]
WAREHOUSE_CONFIG_DIR = Path(__file__).resolve().parents[1] / "problems" / "warehouse_delivery"
WAREHOUSE_WORKSPACE = REPO_ROOT / "surrogate"
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "warehouse_direct_outer_smoke"


class _CountingMockLLM(MockLLMClient):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.required_fields: list[tuple[str, ...]] = []

    def call_with_tool(
        self,
        prompt,
        tool,
        model=None,
        system_blocks=None,
        request_kind=None,
    ):
        schema = tool.get("input_schema", {})
        self.required_fields.append(tuple(schema.get("required", ())))
        return super().call_with_tool(
            prompt,
            tool,
            model,
            system_blocks,
            request_kind,
        )


def _problem_v1() -> ProblemSpecV1:
    payload = yaml.safe_load(
        (WAREHOUSE_CONFIG_DIR / "problem-v1.yaml").read_text(encoding="utf-8")
    )
    payload["root_dir"] = str(WAREHOUSE_WORKSPACE)
    return ProblemSpecV1(**payload)


def _patch_response() -> dict[str, object]:
    target = WAREHOUSE_WORKSPACE / "operators" / "change_vehicle_type.py"
    source = target.read_text(encoding="utf-8")
    old = "\"\"\"随机选一辆非空车，尝试降级车型。\"\"\""
    new = "\"\"\"随机选一辆非空车，并尝试安全地降级车型。\"\"\""
    assert source.count(old) == 1
    return {
        "file_path": "operators/change_vehicle_type.py",
        "action": "modify",
        "edit_intent": "exact_replace",
        "source_digest": source_digest_for_content(source),
        "old_string": old,
        "new_string": new,
        "replace_all": False,
        "test_hint": None,
    }


def _hypothesis_response() -> dict[str, object]:
    return {
        "hypothesis_text": (
            "Clarify the existing safe vehicle-type downgrade operator without "
            "changing its executable behavior; this outer smoke isolates campaign wiring."
        ),
        "change_locus": "vehicle_level",
        "action": "modify",
        "target_file": "operators/change_vehicle_type.py",
        "predicted_direction": "exploratory",
        "target_weakness": "The real warehouse direct outer path lacks an owning smoke test.",
        "expected_effect": "No solver behavior change; exercise the real warehouse pipeline.",
        "suggested_weight": 0.1,
    }


def _instrument_once(
    monkeypatch,
    owner,
    method_name: str,
    label: str,
    trace: list[str],
    counts: dict[str, int],
) -> None:
    original = getattr(owner, method_name)

    def wrapped(*args, **kwargs):
        counts[label] = counts.get(label, 0) + 1
        trace.append(label)
        return original(*args, **kwargs)

    monkeypatch.setattr(owner, method_name, wrapped)


def test_outer_contract_rejects_invalid_locus_before_code_and_verification(
    tmp_path: Path,
    monkeypatch,
) -> None:
    spec_v1 = _problem_v1()
    bridge = bridge_problem_spec_v1(spec_v1)
    adapter = load_problem_adapter(spec_v1)
    protocol_config = ProtocolConfig.from_yaml(FIXTURE_DIR / "protocol.yaml")
    split_manifest = SplitManifest.from_yaml(FIXTURE_DIR / "split_manifest.yaml")
    seed_ledger = SeedLedgerConfig.from_yaml(FIXTURE_DIR / "seed_ledger.yaml")
    runner = LocalSubprocessRunner(ResourceLimits(timeout_sec=30, memory_mb=1024))
    protocol = ExperimentProtocol(
        protocol_config=protocol_config,
        split_manager=SplitManager(split_manifest),
        seed_ledger=SeedLedger(seed_ledger),
        runner=runner,
        time_limit_sec=2,
        metrics_dir=str(tmp_path / "metrics"),
        metric_specs=bridge.metric_specs,
        objective_policy=bridge.objective_policy,
        require_metric_specs=True,
        problem_spec=bridge.problem_spec,
    )
    gate = VerificationGate(
        problem_spec=bridge.problem_spec,
        runner=runner,
        metrics_dir=str(tmp_path / "metrics"),
        adapter=adapter,
        strict_runtime_checks=True,
        require_adapter_for_runtime=True,
        operator_execute_signature=bridge.operator_execute_signature,
        runtime_time_limit_sec=2,
    )
    response = {**_hypothesis_response(), "change_locus": "route_level"}
    llm = _CountingMockLLM(
        hypothesis_response=response,
        patch_response=_patch_response(),
    )
    campaign = CampaignManager(
        problem_spec=bridge.problem_spec,
        protocol_config=protocol_config,
        split_manifest=split_manifest,
        seed_ledger=seed_ledger,
        llm_client=llm,
        champion=ChampionState(
            version=1,
            operator_pool={},
            solver_config_hash="warehouse-direct-outer-reject",
            code_snapshot_path=str(WAREHOUSE_WORKSPACE),
            code_snapshot_hash="warehouse-baseline",
        ),
        campaign_dir=str(tmp_path / "campaign"),
        verification_gate=gate,
        experiment_protocol=protocol,
        adapter=adapter,
        operator_execute_signature=bridge.operator_execute_signature,
    )
    counts: dict[str, int] = {}
    trace: list[str] = []
    _instrument_once(
        monkeypatch,
        campaign._contract_gate,
        "validate_hypothesis",
        "contract_hypothesis",
        trace,
        counts,
    )
    _instrument_once(monkeypatch, gate, "run", "verification", trace, counts)

    result = campaign.run_one_step()

    assert result.reason == "hypothesis contract rejected"
    assert result.execution_outcome is ExecutionOutcome.RESEARCH_REJECTED
    assert result.execution_outcome_reason_code == "HYPOTHESIS_CONTRACT_REJECTED"
    assert result.decision is None
    assert llm.call_count == 1
    assert counts["contract_hypothesis"] == 1
    assert counts.get("verification", 0) == 0
    step = campaign._step_history[-1]
    assert step.failure_stage == "hypothesis_contract"
    assert step.contract_passed is False
    assert step.verification_passed is False
    assert step.execution_outcome is ExecutionOutcome.RESEARCH_REJECTED
    assert step.execution_outcome_reason_code == "HYPOTHESIS_CONTRACT_REJECTED"
    assert step.decision is None
    assert step.protocol_result is None
    assert "C2_change_locus" in (step.failure_detail or "")
    branch = campaign._branch_ctrl.get_branch(result.branch_id)
    assert "CONTRACT" not in branch.failure_codes
    records = campaign._hyp_store.get_by_branch(result.branch_id)
    assert len(records) == 1
    assert records[0].status == "research_rejected"
    outcome_events = [
        event
        for event in campaign._registry.query_by_branch(result.branch_id)
        if event["execution_outcome"] == "research_rejected"
    ]
    assert len(outcome_events) == 1
    assert outcome_events[0]["event_kind"] == "contract_fail"
    assert outcome_events[0]["decision"] is None
    durable = campaign._registry.get_latest_execution_outcome(
        branch_id=result.branch_id
    )
    assert durable is not None
    assert durable["provenance"]["owner"] == "outer_contract"
    assert durable["provenance"]["stage"] == "hypothesis_contract"
    assert any(
        check["name"] == "C0_governance_constraints"
        for check in durable["provenance"]["contract_checks"]
    )


def test_real_warehouse_campaign_direct_v3_outer_path_is_lossless(
    tmp_path: Path,
    monkeypatch,
) -> None:
    spec_v1 = _problem_v1()
    bridge = bridge_problem_spec_v1(spec_v1)
    adapter = load_problem_adapter(spec_v1)
    protocol_config = ProtocolConfig.from_yaml(FIXTURE_DIR / "protocol.yaml")
    split_manifest = SplitManifest.from_yaml(FIXTURE_DIR / "split_manifest.yaml")
    seed_ledger = SeedLedgerConfig.from_yaml(FIXTURE_DIR / "seed_ledger.yaml")
    runner = LocalSubprocessRunner(ResourceLimits(timeout_sec=30, memory_mb=1024))
    protocol = ExperimentProtocol(
        protocol_config=protocol_config,
        split_manager=SplitManager(split_manifest),
        seed_ledger=SeedLedger(seed_ledger),
        runner=runner,
        time_limit_sec=2,
        metrics_dir=str(tmp_path / "metrics"),
        metric_specs=bridge.metric_specs,
        objective_policy=bridge.objective_policy,
        require_metric_specs=True,
        problem_spec=bridge.problem_spec,
    )
    gate = VerificationGate(
        problem_spec=bridge.problem_spec,
        runner=runner,
        metrics_dir=str(tmp_path / "metrics"),
        adapter=adapter,
        strict_runtime_checks=True,
        require_adapter_for_runtime=True,
        operator_execute_signature=bridge.operator_execute_signature,
        runtime_time_limit_sec=2,
    )
    llm = _CountingMockLLM(
        hypothesis_response=_hypothesis_response(),
        patch_response=_patch_response(),
    )
    campaign_dir = tmp_path / "campaign"
    campaign = CampaignManager(
        problem_spec=bridge.problem_spec,
        protocol_config=protocol_config,
        split_manifest=split_manifest,
        seed_ledger=seed_ledger,
        llm_client=llm,
        champion=ChampionState(
            version=1,
            operator_pool={},
            solver_config_hash="warehouse-direct-outer-smoke",
            code_snapshot_path=str(WAREHOUSE_WORKSPACE),
            code_snapshot_hash="warehouse-baseline",
        ),
        campaign_dir=str(campaign_dir),
        verification_gate=gate,
        experiment_protocol=protocol,
        adapter=adapter,
        operator_execute_signature=bridge.operator_execute_signature,
    )

    trace: list[str] = []
    counts: dict[str, int] = {}
    _instrument_once(
        monkeypatch,
        campaign._contract_gate,
        "validate_hypothesis",
        "contract_hypothesis",
        trace,
        counts,
    )
    _instrument_once(
        monkeypatch,
        campaign._contract_gate,
        "validate_patch",
        "contract_patch",
        trace,
        counts,
    )
    _instrument_once(monkeypatch, gate, "run", "verification", trace, counts)
    _instrument_once(monkeypatch, protocol, "run_experiment", "protocol", trace, counts)
    _instrument_once(monkeypatch, campaign._decision_finalizer, "apply", "decision", trace, counts)

    first = campaign.run_one_step()
    assert first.action == "create_branch"

    assert llm.call_count == 2
    assert len(llm.required_fields) == 2
    assert "hypothesis_text" in llm.required_fields[0]
    assert "file_path" in llm.required_fields[1]
    assert counts["contract_hypothesis"] == 1
    assert counts["contract_patch"] == 1
    assert counts["verification"] == 1
    assert counts["protocol"] == 1
    assert counts["decision"] == 1
    assert trace.index("contract_hypothesis") < trace.index("contract_patch")
    assert trace.index("contract_patch") < trace.index("verification")
    assert trace.index("verification") < trace.index("protocol")
    assert trace.index("protocol") < trace.index("decision")

    step = next(item for item in campaign._step_history if item.protocol_result is not None)
    assert step.contract_passed is True
    assert step.verification_passed is True
    assert step.protocol_result.stage == ExperimentStage.SCREENING
    assert step.decision is not None

    attempt_ref = step.proposal_session_ref
    assert attempt_ref is not None
    assert attempt_ref["runtime_mode"] == "direct_v3"
    assert attempt_ref["phase"] == "code"
    assert attempt_ref["status"] == "generated"

    events = campaign._registry.query_by_branch(step.branch_id)
    transition_rows = [
        (row, json.loads(row["audit_payload_json"]))
        for row in reversed(events)
        if row["event_kind"] == "proposal_attempt_transition"
    ]
    transitions = [payload for _row, payload in transition_rows]
    assert [event["phase"] for event in transitions] == [
        "hypothesis",
        "hypothesis",
        "code",
        "code",
    ]
    assert [event["status"] for event in transitions] == [
        "started",
        "generated",
        "started",
        "generated",
    ]
    hypothesis_attempt_id = transitions[0]["attempt_id"]
    code_attempt_id = transitions[2]["attempt_id"]
    assert transitions[1]["attempt_id"] == hypothesis_attempt_id
    assert transitions[3]["attempt_id"] == code_attempt_id
    assert hypothesis_attempt_id != code_attempt_id
    assert transitions[2]["continuation_of_attempt_id"] == hypothesis_attempt_id
    assert transitions[3]["continuation_of_attempt_id"] == hypothesis_attempt_id
    assert code_attempt_id == attempt_ref["attempt_id"]
    assert transition_rows[3][0]["event_id"] == attempt_ref["lineage_event_id"]

    candidate_paths = list(
        (campaign_dir / "artifacts" / "formal_candidates").glob(
            "**/candidate.patch.json"
        )
    )
    assert len(candidate_paths) == 1
    candidate = json.loads(candidate_paths[0].read_text(encoding="utf-8"))
    assert candidate["proposal_attempt_id"] == attempt_ref["attempt_id"]
    assert candidate["proposal_attempt_event_id"] == attempt_ref["lineage_event_id"]
    assert candidate["proposal_hypothesis_attempt_id"] == hypothesis_attempt_id
    assert candidate["proposal_attempt_continuation_of_attempt_id"] == (
        hypothesis_attempt_id
    )
    assert candidate["proposal_runtime_mode"] == "direct_v3"
    index_rows = [
        json.loads(line)
        for line in (
            campaign_dir / "artifacts" / "formal_candidates" / "index.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(index_rows) == 1
    assert index_rows[0]["proposal_attempt_id"] == attempt_ref["attempt_id"]
    assert index_rows[0]["proposal_attempt_event_id"] == attempt_ref["lineage_event_id"]
    assert index_rows[0]["proposal_hypothesis_attempt_id"] == hypothesis_attempt_id
    assert index_rows[0]["proposal_attempt_continuation_of_attempt_id"] == (
        hypothesis_attempt_id
    )
    assert index_rows[0]["proposal_runtime_mode"] == "direct_v3"

    decision_field_names = {field.name for field in fields(DecisionFeatures)}
    assert all("proposal_attempt" not in name for name in decision_field_names)
    assert "proposal_runtime_mode" not in decision_field_names
    assert step.decision_features_snapshot is not None
    assert all(
        "proposal_attempt" not in key
        for key in vars(step.decision_features_snapshot)
    )
    decision_rows = [row for row in events if row["decision_features_json"]]
    assert decision_rows
    for row in decision_rows:
        persisted_decision_features = json.loads(row["decision_features_json"])
        assert all(
            "proposal_attempt" not in key for key in persisted_decision_features
        )
        assert "proposal_runtime_mode" not in persisted_decision_features

    # Verification's real warehouse V8 run retains the solver's full runtime
    # payload; protocol pair summaries intentionally project only declared fields.
    v8_metrics = list((tmp_path / "metrics").glob("v8_run1_*.json"))
    assert len(v8_metrics) == 1
    runtime = json.loads(v8_metrics[0].read_text(encoding="utf-8"))["runtime"]
    typed_events = runtime["typed_telemetry_events"]
    registry_events = [
        event
        for event in typed_events
        if event["mechanism_id"] == "warehouse_operator_registry"
    ]
    assert len(registry_events) == 1
    assert registry_events[0]["lane"] == "state_transition"
    assert registry_events[0]["before_ref"] == "operator_registry:unresolved"
    assert registry_events[0]["after_ref"].startswith("operator_registry:active:")
    assert all(event["lane"] != "direct_effect" for event in typed_events)
