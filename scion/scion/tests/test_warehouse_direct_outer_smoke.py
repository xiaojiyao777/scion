"""Lossless direct-v3 outer smoke over the real warehouse runtime."""
from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import yaml
from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.core.campaign import CampaignManager
from scion.core.execution_outcome import ExecutionOutcome
from scion.core.models import (
    BranchState,
    ChampionState,
    DecisionFeatures,
    ExperimentStage,
)
from scion.problem.bridge import bridge_problem_spec_v1
from scion.problem.loader import load_problem_adapter
from scion.problem.spec import ProblemSpecV1
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


def test_provider_surface_enum_rejects_invalid_locus_before_outer_contract(
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
            code_snapshot_path=str(WAREHOUSE_WORKSPACE),
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

    assert "must exactly match one provider-visible research surface" in result.reason
    assert result.execution_outcome.outcome is ExecutionOutcome.RESEARCH_REJECTED
    assert result.execution_outcome.reason_code == "HYPOTHESIS_PROPOSAL_INVALID"
    assert result.decision is None
    assert llm.call_count == 1
    assert counts.get("contract_hypothesis", 0) == 0
    assert counts.get("verification", 0) == 0
    assert len(campaign._step_history) == 1
    step = campaign._step_history[0]
    assert step.hypothesis is None
    assert step.failure_stage == "proposal_hypothesis"
    assert step.failure_detail == result.execution_outcome.reason_code
    assert step.execution_outcome.detail == ""
    assert step.execution_outcome.provenance == {
        "stage": "proposal_hypothesis"
    }
    branch = campaign._branch_ctrl.get_branch(result.branch_id)
    assert branch.state is not BranchState.BLOCKED_INFRA
    assert "CONTRACT" not in branch.failure_codes
    assert branch.hypothesis is None
    outcome_events = [
        event
        for event in campaign._registry.query_by_branch(result.branch_id)
        if event["execution_outcome"] == "research_rejected"
    ]
    assert len(outcome_events) == 1
    assert outcome_events[0]["event_kind"] == "proposal_execution_outcome"
    assert outcome_events[0]["decision"] is None
    durable = campaign._registry.query_execution_outcomes(
        branch_id=result.branch_id
    )[0]
    assert durable["reason_code"] == "HYPOTHESIS_PROPOSAL_INVALID"
    assert "owner" not in durable["provenance"]
    assert durable["provenance"]["stage"] == "proposal_hypothesis"


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
            code_snapshot_path=str(WAREHOUSE_WORKSPACE),
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

    events = campaign._registry.query_by_branch(step.branch_id)
    experiment_events = [
        row for row in events if row["event_kind"] == "experiment"
    ]
    assert len(experiment_events) == 1
    assert experiment_events[0]["stage"] == "screening"
    assert experiment_events[0]["hypothesis_text"] == (
        _hypothesis_response()["hypothesis_text"]
    )

    # Active research keeps the evaluated source in the branch workspace and
    # the result in ordinary step/protocol evidence. It does not build a
    # parallel replay-identity/hash closure for every screening candidate.
    assert not (campaign_dir / "artifacts" / "formal_candidates").exists()
    workspace = Path(campaign._branch_workspaces[step.branch_id])
    assert workspace.is_dir()
    changed_source = (workspace / "operators" / "change_vehicle_type.py").read_text(
        encoding="utf-8"
    )
    assert "并尝试安全地降级车型" in changed_source

    decision_field_names = {field.name for field in fields(DecisionFeatures)}
    assert all("proposal_attempt" not in name for name in decision_field_names)
    assert "proposal_runtime_mode" not in decision_field_names

    # Successful same-seed Verification keeps comparison data in memory and
    # writes no V8 telemetry artifacts.
    assert not list((tmp_path / "metrics").glob("v8_*.json"))
