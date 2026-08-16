"""Real CVRP direct-v3 outer smoke with a multi-file no-op patch."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.core.campaign import CampaignManager
from scion.core.models import ChampionState, ExperimentStage
from scion.problem.bridge import bridge_problem_spec_v1
from scion.problem.loader import load_problem_adapter
from scion.problem.spec import ProblemSpecV1
from scion.proposal.mock_client import MockLLMClient
from scion.protocol.experiment import ExperimentProtocol, SeedLedger, SplitManager
from scion.runtime.runner import ResourceLimits
from scion.runtime.subprocess_runner import LocalSubprocessRunner
from scion.verification.gate import VerificationGate

CVRP_DIR = Path(__file__).resolve().parents[1] / "problems" / "cvrp"
CONTROLLED_DIR = CVRP_DIR / "controlled"
VRP_DIR = Path(
    os.environ.get(
        "SCION_CVRP_TEST_DATA_ROOT",
        "/home/clawd/research/or-autoresearch-agent/vrp",
    )
).resolve()


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
        (CVRP_DIR / "problem-v1.yaml").read_text(encoding="utf-8")
    )
    payload["root_dir"] = str(CVRP_DIR)
    payload["canary_case_path"] = "controlled/data/synthetic_controlled_canary_5.vrp"
    return ProblemSpecV1(**payload)


def _hypothesis_response() -> dict[str, object]:
    return {
        "hypothesis_text": (
            "Add and wire a no-op construction probe across the real CVRP module "
            "boundary solely to verify direct multi-file ownership and execution."
        ),
        "change_locus": "solver_design",
        "action": "modify",
        "target_file": "policies/baseline_modules/construction.py",
        "predicted_direction": "exploratory",
        "target_weakness": "The real CVRP direct outer multi-file path lacks an owning smoke test.",
        "expected_effect": "No solver behavior change; exercise multi-file direct-v3 wiring.",
        "suggested_weight": 0.1,
    }


def _patch_response() -> dict[str, object]:
    construction_path = CVRP_DIR / "policies" / "baseline_modules" / "construction.py"
    scheduler_path = CVRP_DIR / "policies" / "baseline_modules" / "scheduler.py"
    construction = construction_path.read_text(encoding="utf-8")
    scheduler = scheduler_path.read_text(encoding="utf-8")
    construction_old = (
        "from .state import _Route, _Solution, _demand, _node\n\n\n"
        "def _clarke_wright_savings(instance, target_routes=None):"
    )
    construction_new = (
        "from .state import _Route, _Solution, _demand, _node\n\n\n"
        "def _elite_seed_probe(instance):\n"
        "    del instance\n"
        "    return None\n\n\n"
        "def _clarke_wright_savings(instance, target_routes=None):"
    )
    scheduler_old = (
        "    def _initial_solution(self, instance, reserve):\n"
        "        phase_ms = self.context.elapsed_ms()"
    )
    scheduler_new = (
        "    def _initial_solution(self, instance, reserve):\n"
        "        from .construction import _elite_seed_probe\n\n"
        "        _elite_seed_probe(instance)\n"
        "        phase_ms = self.context.elapsed_ms()"
    )
    assert construction.count(construction_old) == 1
    assert scheduler.count(scheduler_old) == 1
    return {
        "file_path": "policies/baseline_modules/construction.py",
        "action": "modify",
        "edit_intent": "exact_replace",
        "old_string": construction_old,
        "new_string": construction_new,
        "replace_all": False,
        "test_hint": None,
        "additional_changes": [
            {
                "file_path": "policies/baseline_modules/scheduler.py",
                "action": "modify",
                "edit_intent": "exact_replace",
                "old_string": scheduler_old,
                "new_string": scheduler_new,
                "replace_all": False,
                "test_hint": None,
            }
        ],
    }


def _instrument(monkeypatch, owner, name, label, trace, counts) -> None:
    original = getattr(owner, name)

    def wrapped(*args, **kwargs):
        counts[label] = counts.get(label, 0) + 1
        trace.append(label)
        return original(*args, **kwargs)

    monkeypatch.setattr(owner, name, wrapped)


def test_real_cvrp_direct_outer_multi_file_path(tmp_path, monkeypatch) -> None:
    assert (VRP_DIR / "cvrplib").is_dir()
    monkeypatch.setenv("SCION_PROBLEM_DATA_ROOT", str(VRP_DIR))
    spec_v1 = _problem_v1()
    bridge = bridge_problem_spec_v1(spec_v1)
    adapter = load_problem_adapter(spec_v1)
    protocol_config = ProtocolConfig.from_yaml(CONTROLLED_DIR / "protocol.yaml")
    split_manifest = SplitManifest.from_yaml(CONTROLLED_DIR / "split_manifest.yaml")
    split_manifest = split_manifest.model_copy(
        update={"safe_data_roots": [str(VRP_DIR)]}
    )
    seed_ledger = SeedLedgerConfig.from_yaml(CONTROLLED_DIR / "seed_ledger.yaml")
    runner = LocalSubprocessRunner(ResourceLimits(timeout_sec=10, memory_mb=1024))
    protocol = ExperimentProtocol(
        protocol_config=protocol_config,
        split_manager=SplitManager(split_manifest),
        seed_ledger=SeedLedger(seed_ledger),
        runner=runner,
        time_limit_sec=1,
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
        runtime_time_limit_sec=1,
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
            code_snapshot_path=str(CVRP_DIR),
        ),
        campaign_dir=str(campaign_dir),
        verification_gate=gate,
        experiment_protocol=protocol,
        adapter=adapter,
        operator_execute_signature=bridge.operator_execute_signature,
    )

    trace: list[str] = []
    counts: dict[str, int] = {}
    _instrument(monkeypatch, campaign._contract_gate, "validate_hypothesis", "H", trace, counts)
    _instrument(monkeypatch, campaign._contract_gate, "validate_patch", "P", trace, counts)
    _instrument(monkeypatch, gate, "run", "V", trace, counts)
    _instrument(monkeypatch, protocol, "run_experiment", "protocol", trace, counts)
    _instrument(monkeypatch, campaign._decision_finalizer, "apply", "decision", trace, counts)

    campaign.run_one_step()

    assert llm.call_count == 2
    assert len(llm.required_fields) == 2
    assert "hypothesis_text" in llm.required_fields[0]
    assert "file_path" in llm.required_fields[1]
    assert counts == {"H": 1, "P": 1, "V": 1, "protocol": 1, "decision": 1}
    assert trace == ["H", "P", "V", "protocol", "decision"]

    step = next(item for item in campaign._step_history if item.protocol_result is not None)
    assert step.protocol_result.stage == ExperimentStage.SCREENING

    events = campaign._registry.query_by_branch(step.branch_id)

    experiment_events = [
        row for row in events if row["event_kind"] == "experiment"
    ]
    assert len(experiment_events) == 1
    assert experiment_events[0]["stage"] == "screening"
    assert experiment_events[0]["hypothesis_text"] == (
        _hypothesis_response()["hypothesis_text"]
    )

    # The active path retains the evaluated multi-file source directly in the
    # branch workspace; it does not emit a second identity/hash closure.
    assert not (campaign_dir / "artifacts" / "formal_candidates").exists()
    workspace = Path(campaign._branch_workspaces[step.branch_id])
    assert workspace.is_dir()
    assert "def _elite_seed_probe(instance):" in (
        workspace / "policies" / "baseline_modules" / "construction.py"
    ).read_text(encoding="utf-8")
    assert "_elite_seed_probe(instance)" in (
        workspace / "policies" / "baseline_modules" / "scheduler.py"
    ).read_text(encoding="utf-8")
