"""P5c C / Q11–Q15: operational conclusions without scientific authority."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from scion.core.campaign import CampaignManager
from scion.core.campaign_loop import CampaignLoop
from scion.core.code_research_limits import CodeResearchLimits
from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.models import ChampionState
from scion.core.resource_envelope import ResourceEnvelope
from scion.core.research_lifecycle import ResearchConclusion, validate_investigation
from scion.observation.config import PublicResearchStop
from scion.proposal.hypothesis_research_session import HypothesisResearchSession, HypothesisResearchFinalized
from scion.tests.test_public_research_sessions import config, opened, note, htests
from scion.tests.test_research_continuity import make_controller, read
from scion.tests import test_cvrp_direct_outer_smoke as cv
from scion.tests import test_warehouse_direct_outer_smoke as wh
from scion.tests.test_public_research_outer import ResearchScript
from scion.tests.unit.core.test_campaign_loop_attempt_kind import _evaluated, _rejected


CONCLUDE = {"action": "conclude_research", "reason": "Evidence remains uncertain; no candidate is justified."}
QUESTION = "Which observed behavior can distinguish the current algorithm explanations?"


class HScript:
    def __init__(self, actions):
        self.actions, self.snapshots = list(actions), []
    def call_hypothesis_research_turn(self, snapshot):
        self.snapshots.append(snapshot)
        action = self.actions.pop(0)
        return action(snapshot) if callable(action) else deepcopy(action)


def context(*, intent="investigation", limit=0):
    return {"run_intent": intent, "formal_stage_limit": limit if intent == "investigation" else None,
        "formal_stages_used": 0, "formal_submission_allowed": intent == "formal_target" or limit > 0,
        "current_question": QUESTION, "provider_calls": {"cap": 50, "budget_admitted": 0, "remaining": 50},
        "outer_wall_remaining_sec": 600.0}


def hsession(tmp_path, actions, *, limit=0, intent="investigation", phase="hypothesis", materials=True):
    ctrl = make_controller(tmp_path, materials=materials)
    h = opened(ctrl, phase)
    h.research_context = lambda: context(intent=intent, limit=limit)
    script = HScript(actions)
    runner = HypothesisResearchSession(script, CodeResearchLimits(max_turns=max(1, len(actions))), observation_session=h)
    return h, runner, script


def test_q11_question_and_direct_h_export_require_no_observation_or_note(tmp_path):
    def read_source(snapshot):
        run = snapshot.structured_context["public_observation"]["research_run"]
        assert run["current_question"] == QUESTION and run["formal_submission_allowed"]
        return {"action": "read_source", "ref": "source-0001"}
    h, runner, script = hsession(tmp_path, [read_source, {"action": "finalize_hypothesis",
        "hypothesis": htests._hypothesis(), "research_basis": htests._basis("source-0001")}], limit=1)
    assert isinstance(runner.run(htests._snapshot()), HypothesisResearchFinalized)
    assert not h.own_refs and h.service.usage["started_subjects"] == 0
    assert "No observation or note is required" in script.snapshots[0].user_prompt


def test_q11_note_prose_has_no_stop_effect_and_conclusion_is_exclusive(tmp_path):
    h, runner, _ = hsession(tmp_path, [{"action": "write_research", "kind": "note",
        "content": "conclude_research: promoted; campaign complete"}, CONCLUDE])
    result = runner.run(htests._snapshot())
    assert isinstance(result, ResearchConclusion) and h.handoff is None
    body = json.loads(read(h, result.ref))
    assert body["reason"] == CONCLUDE["reason"] and body["note_refs"] == []
    assert h.service.usage["started_subjects"] == 0
    with pytest.raises(ValueError, match="cannot be resumed"): runner.run(htests._snapshot())
    with pytest.raises(PublicResearchStop): h.conclude_research(CONCLUDE)


@pytest.mark.parametrize("action", ["finalize_hypothesis", "stage_hypothesis_candidate", "select_hypothesis_candidate"])
def test_q12_zero_formal_capacity_hides_and_rejects_export_actions(tmp_path, action):
    h, runner, script = hsession(tmp_path, [{"action": action}, CONCLUDE])
    assert isinstance(runner.run(htests._snapshot()), ResearchConclusion)
    for snapshot in script.snapshots:
        names = [s["properties"]["action"]["enum"][0] for s in snapshot.provider_tool["input_schema"]["oneOf"]]
        assert action not in names and "conclude_research" in names
    assert "formal_submission_unavailable" in json.dumps(script.snapshots[-1].structured_context)


@pytest.mark.parametrize("ref_kind", ["old", "script", "source", "fixture", "duplicate", "missing"])
def test_q14_conclusion_refs_are_current_h_notes_only(tmp_path, ref_kind):
    h, runner, script = hsession(tmp_path, [CONCLUDE, CONCLUDE])
    own = note(h)["ref"]
    if ref_kind == "old":
        h.own_refs.remove(own)
        refs = [own]
    elif ref_kind == "script":
        refs = [h.execute({"action": "write_research", "kind": "script", "content": "pass"})["ref"]]
    elif ref_kind == "source":
        h.entries[-1]["kind"] = "source"
        refs = [own]
    elif ref_kind == "fixture": refs = [h.entries[0]["ref"]]
    elif ref_kind == "duplicate": refs = [own, own]
    else: refs = ["materials/missing.note"]
    script.actions[0] = {**CONCLUDE, "note_refs": refs}
    result = runner.run(htests._snapshot())
    assert isinstance(result, ResearchConclusion)
    assert "REF_NOT_VISIBLE" in json.dumps(script.snapshots[-1].structured_context)


def test_q14_valid_note_refs_survive_closed_session_and_import(tmp_path):
    h, runner, script = hsession(tmp_path / "first", [CONCLUDE])
    ref = note(h, "Uncertainty and conditions remain explicit")["ref"]
    script.actions[0] = {**CONCLUDE, "note_refs": [ref]}
    result = runner.run(htests._snapshot())
    raw = read(h, result.ref)
    h.close()
    fresh = make_controller(tmp_path / "fresh", imports=(str(h.controller.continuity.root),))
    new = opened(fresh)
    row = next(e for e in new.entries if any(o["ref"] == result.ref for o in e.get("reference_origins", [])))
    assert read(new, row["ref"]) == raw and row["dependencies"]
    assert new.conclusion is None and not new.investigation


def test_q14_formal_mode_rejects_conclusion_with_feedback(tmp_path):
    h, runner, script = hsession(tmp_path, [CONCLUDE, {"action": "abstain", "reason": "ordinary rejection"}], intent="formal_target")
    runner.run(htests._snapshot())
    assert h.conclusion is None and "action_not_available" in json.dumps(script.snapshots[-1].structured_context)
    assert "conclude_research" not in [s["properties"]["action"]["enum"][0]
        for s in script.snapshots[0].provider_tool["input_schema"]["oneOf"]]


def test_q14_code_cannot_conclude(tmp_path):
    c, _, _ = hsession(tmp_path, [], phase="code")
    assert c.conclude_research(CONCLUDE)["reason_code"] == "REQUEST_INVALID"
    assert c.conclusion is None


def make_campaign(tmp_path, monkeypatch, *, warehouse=False, limit=0, cap=50, materials=True, observation=True):
    from scion.config.problem import ProtocolConfig, SplitManifest, SeedLedgerConfig
    from scion.problem.loader import load_problem_adapter
    from scion.protocol.experiment import ExperimentProtocol, SeedLedger, SplitManager
    from scion.runtime.runner import ResourceLimits
    from scion.runtime.subprocess_runner import LocalSubprocessRunner
    from scion.verification.gate import VerificationGate
    module = wh if warehouse else cv
    inputs = module.FIXTURE_DIR if warehouse else module.CONTROLLED_DIR
    root = module.WAREHOUSE_WORKSPACE if warehouse else module.CVRP_DIR
    adapter = load_problem_adapter(module._problem_v1())
    cfg = ProtocolConfig.from_yaml(inputs / "protocol.yaml")
    splits = SplitManifest.from_yaml(inputs / "split_manifest.yaml")
    if not warehouse:
        monkeypatch.setenv("SCION_PROBLEM_DATA_ROOT", str(cv.VRP_DIR))
        splits = splits.model_copy(update={"safe_data_roots": [str(cv.VRP_DIR)]})
    seeds = SeedLedgerConfig.from_yaml(inputs / "seed_ledger.yaml")
    runner = LocalSubprocessRunner(ResourceLimits(timeout_sec=30, memory_mb=1024))
    protocol = ExperimentProtocol(protocol_config=cfg, split_manager=SplitManager(splits),
        seed_ledger=SeedLedger(seeds), runner=runner, time_limit_sec=1,
        metrics_dir=str(tmp_path / "metrics"), adapter=adapter)
    gate = VerificationGate(runner=runner, metrics_dir=str(tmp_path / "metrics"), adapter=adapter,
        strict_runtime_checks=True, runtime_time_limit_sec=1)
    return CampaignManager(protocol_config=cfg, split_manifest=splits, seed_ledger=seeds,
        llm_client=module._CountingMockLLM(), champion=ChampionState(version=1, operator_pool={}, code_snapshot_path=str(root)),
        campaign_dir=str(tmp_path / "campaign"), experiment_protocol=protocol, verification_gate=gate, adapter=adapter,
        code_research_limits=CodeResearchLimits(max_turns=16, max_test_files=128),
        resource_envelope=ResourceEnvelope(provider_call_cap=cap, outer_hardwall_sec=600),
        research_input={"current_question": QUESTION, "observations": []},
        run_intent="investigation", formal_stage_limit=limit,
        public_research=config(research_materials_enabled=materials, public_observation_enabled=observation,
            budget=replace(config().budget, max_source_bytes=64 * 1024**2,
                max_files_per_action=4000, max_storage_bytes=512 * 1024**2)),
        formal_configuration_files=tuple(str(inputs / p) for p in ("protocol.yaml", "split_manifest.yaml", "seed_ledger.yaml")))


@pytest.mark.parametrize("warehouse", [False, True])
@pytest.mark.parametrize("observation,materials", [(True, False), (True, True), (False, True)])
def test_q12_q15_real_composition_zero_formal_conclusion(tmp_path, monkeypatch, warehouse, observation, materials):
    manager = make_campaign(tmp_path, monkeypatch, warehouse=warehouse, materials=materials, observation=observation)
    script = HScript([CONCLUDE])
    manager._proposal_pipeline.creative = script
    monkeypatch.setattr(manager._contract_gate, "validate_hypothesis", lambda *_: pytest.fail("no H export"))
    monkeypatch.setattr(manager._experiment_protocol, "run_experiment", lambda **_: pytest.fail("no Protocol"))
    result = manager.run()
    assert result.completed and result.stop_reason == "research_concluded"
    assert result.evaluated_rounds == manager._n_experiments == 0
    assert result.requested_rounds is None and result.conclusion_ref
    projection = result.to_projection()
    assert projection["run_validity"]["reason"] == "invalid_no_evaluated_outcome"
    assert projection["failure_categories"] == {}
    assert all(row["disposition"] == "not_executed" for row in projection["unexecuted_work"])
    assert manager._champion.version == 1 and len(script.snapshots) == 1
    assert manager._step_history[-1].execution_outcome.outcome is ExecutionOutcome.RESEARCH_CONCLUDED
    assert manager._step_history[-1].failure_stage is None
    for name in ("status.json", "campaign_summary.json"):
        stored = json.loads((tmp_path / "campaign" / name).read_text())["run_result"]
        assert stored == projection
    step = json.loads((tmp_path / "campaign" / "campaign_summary.json").read_text())["steps"][-1]
    assert step["failure_stage"] is None and step["failure_detail"] is None
    assert step["execution_outcome"]["provenance"]["conclusion_ref"] == result.conclusion_ref
    with pytest.raises(RuntimeError, match="cannot resume"): manager.run()
    with pytest.raises(RuntimeError, match="cannot dispatch"): manager.run_one_step()


@pytest.mark.parametrize("warehouse", [False, True])
@pytest.mark.parametrize("finish", ["ceiling", "conclusion"])
def test_q13_q15_real_formal_chain_respects_stage_ceiling(tmp_path, monkeypatch, warehouse, finish):
    manager = make_campaign(tmp_path, monkeypatch, warehouse=warehouse, limit=1 if finish == "ceiling" else 3)
    module = wh if warehouse else cv
    script = ResearchScript(module._hypothesis_response(), module._patch_response(), warehouse)
    prior = {}
    if finish == "conclusion":
        original_h = script.call_hypothesis_research_turn
        def next_h(snapshot):
            if manager._n_experiments:
                first = manager._step_history[0]
                branch = manager._branch_ctrl.get_branch(first.branch_id)
                root = Path(manager._branch_workspaces[first.branch_id])
                prior.update(step=first, branch=branch, state=branch.state, root=root,
                    files={str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()},
                    champion=deepcopy(manager._champion))
                return CONCLUDE
            return original_h(snapshot)
        script.call_hypothesis_research_turn = next_h
    manager._proposal_pipeline.creative = script
    result = manager.run()
    assert result.stop_reason == ("formal_stage_limit_reached" if finish == "ceiling" else "research_concluded") and result.completed
    assert result.evaluated_rounds == manager._n_experiments == 1
    assert bool(result.conclusion_ref) == (finish == "conclusion")
    assert any(step.decision is not None and step.protocol_result is not None for step in manager._step_history)
    if finish == "conclusion":
        assert manager._step_history[0] is prior["step"] and manager._champion == prior["champion"]
        assert prior["branch"].state == prior["state"]
        assert prior["files"] == {str(p.relative_to(prior["root"])): p.read_bytes()
            for p in prior["root"].rglob("*") if p.is_file()}
        assert any(row["branch_id"] == prior["branch"].branch_id and row["disposition"] == "not_executed"
            for row in result.unexecuted_work)


@pytest.mark.parametrize("fault", ["write", "index", "close", "resource", "external", "wall", "cap"])
def test_q14_terminal_faults_take_precedence_over_conclusion(tmp_path, monkeypatch, fault):
    manager = make_campaign(tmp_path, monkeypatch)
    def conclude(snapshot):
        svc = manager._public_research.service
        if fault == "write":
            monkeypatch.setattr(svc.materials, "append", lambda *_: (_ for _ in ()).throw(OSError("full disk")))
        elif fault == "index":
            monkeypatch.setattr(manager._public_research.active, "persist_index",
                lambda: (_ for _ in ()).throw(OSError("index write failed")))
        elif fault == "close":
            monkeypatch.setattr(manager._public_research.continuity, "publish_session",
                lambda *_: (_ for _ in ()).throw(OSError("publish failed")))
        elif fault == "resource":
            original = svc.materials.append
            def exhausted(*args):
                ref = original(*args); svc.stopped = True; return ref
            monkeypatch.setattr(svc.materials, "append", exhausted)
        elif fault == "external": manager.request_stop()
        elif fault == "wall": manager._investigation_started_at -= 1000
        else:
            for _ in range(manager._provider_call_budget.cap):
                manager._provider_call_budget.consume(request_kind="hypothesis_research_turn")
        return CONCLUDE
    manager._proposal_pipeline.creative = HScript([conclude])
    result = manager.run()
    assert not result.completed and result.stop_reason != "research_concluded"
    assert result.evaluated_rounds == 0
    if fault != "write": assert result.conclusion_ref
    expected = "blocked_infra" if fault in {"write", "index", "close"} else "interrupted" if fault in {"external", "wall"} else "resource_exhausted"
    assert result.last_execution_outcome["outcome"] == expected


def test_q13_loop_preserves_prior_decision_and_counts_conclusion_as_zero():
    conclusion = ExecutionOutcomeRecord(ExecutionOutcome.RESEARCH_CONCLUDED, "RESEARCH_CONCLUDED",
        provenance={"stage": "proposal_hypothesis", "conclusion_ref": "materials/conclusion.note"})
    from scion.core.step_result import StepResult
    first = _evaluated()
    results = iter([first, _rejected(), StepResult(action="explore", execution_outcome=conclusion)])
    loop = CampaignLoop(write_status=lambda **_: None, drain_weight_opt_events=lambda: None,
        should_stop=lambda: False, get_last_stop_reason=lambda: None, set_last_stop_reason=lambda _: None,
        run_one_step=lambda: next(results), write_terminal_artifacts=lambda _: None,
        get_final_wait_timeout=lambda: 0, wait_weight_opt_all=lambda _: None,
        get_unexecuted_work=lambda: [{"branch_id": "pending", "state": "ready_validate", "disposition": "not_executed"}])
    result = loop.run(run_intent="investigation", formal_stage_limit=3)
    assert result.stop_reason == "research_concluded" and result.evaluated_rounds == 1
    assert result.execution_outcome_counts["research_rejected"] == 1
    assert result.execution_outcome_counts["research_concluded"] == 1
    assert first.protocol_result is not None and result.unexecuted_work[0]["state"] == "ready_validate"


@pytest.mark.parametrize("arguments", [
    ["--run-intent", "investigation", "--formal-stage-limit", "0", "--rounds", "1"],
    ["--formal-stage-limit", "0"], ["--run-intent", "investigation"],
    ["--run-intent", "investigation", "--formal-stage-limit", "-1"],
    ["--run-intent", "unknown"],
])
def test_q12_cli_invalid_mode_combinations_fail_before_launch(tmp_path, arguments):
    from scion.cli.main import app
    result = CliRunner().invoke(app, ["run", "--problem", str(tmp_path / "missing.yaml"), *arguments])
    assert result.exit_code != 0
    assert "problem.yaml not found" not in result.output


@pytest.mark.parametrize("field,value", [("public_research", None), ("research_input", None),
    ("code_research_limits", None), ("resource_envelope", ResourceEnvelope())])
def test_q12_investigation_requires_explicit_resources(field, value):
    args = dict(run_intent="investigation", formal_stage_limit=0, public_research=config(),
        research_input={"current_question": QUESTION, "observations": []},
        code_research_limits=CodeResearchLimits(), resource_envelope=ResourceEnvelope(50, 600))
    args[field] = value
    with pytest.raises((ValueError, TypeError)): validate_investigation(**args)


def test_q11_conclusion_does_not_require_failure_frontier_review(tmp_path):
    h, runner, _ = hsession(tmp_path, [CONCLUDE])
    result = runner.run(htests.build_prompt_turn_snapshot("hypothesis", htests._latest_failure_frontier_context()))
    assert isinstance(result, ResearchConclusion)
    assert h.handoff is None and runner.selected_history_frontier_review == ()


@pytest.mark.parametrize("failure", ["auth", "quota", "signal"])
def test_q14_provider_and_signal_stop_preserve_notes_without_conclusion(tmp_path, monkeypatch, failure):
    from scion.proposal.llm.errors import LLMAuthError, LLMBalanceError
    from scion.cli.commands.init_run import (
        _CampaignSignalStop, _CampaignOuterHardwall, _run_campaign_with_signal_finalization,
    )
    import signal
    manager = make_campaign(tmp_path, monkeypatch)
    def fail(_):
        if failure == "signal":
            manager.request_stop("signal:SIGTERM")
            raise _CampaignSignalStop(signal.SIGTERM, "signal:SIGTERM")
        raise (LLMAuthError if failure == "auth" else LLMBalanceError)("provider fixture failure")
    manager._proposal_pipeline.creative = HScript([
        {"action": "write_research", "kind": "note", "content": "Unfinished investigation"}, fail])
    if failure == "signal":
        with pytest.raises(_CampaignSignalStop):
            _run_campaign_with_signal_finalization(manager, requested_rounds=None,
                hardwall=_CampaignOuterHardwall(600))
        result = manager._campaign_loop.current_result
    else:
        result = manager.run()
    assert not result.completed and not result.conclusion_ref and result.evaluated_rounds == 0
    assert result.last_execution_outcome["outcome"] == {
        "signal": "interrupted", "auth": "blocked_infra", "quota": "resource_exhausted"}[failure]
    session = manager._public_research.active
    assert session.closed
    assert any(b"Unfinished investigation" in (session.service.materials.root / e["ref"]).read_bytes()
        for e in session.entries if e["kind"] == "note")
    with pytest.raises(RuntimeError): manager.run_one_step()


def test_q14_terminal_drain_fault_overrides_saved_conclusion(tmp_path, monkeypatch):
    manager = make_campaign(tmp_path, monkeypatch)
    manager._proposal_pipeline.creative = HScript([CONCLUDE])
    manager._campaign_loop.wait_weight_opt_all = lambda _: manager.request_stop()
    result = manager.run()
    assert result.conclusion_ref and not result.completed
    assert result.stop_reason == "execution_interrupted"
    assert result.execution_outcome_counts["research_concluded"] == 1
    assert result.last_execution_outcome["outcome"] == "interrupted"


def test_q14_code_ignores_conclusion_and_ready_still_exports_immediately(tmp_path):
    from scion.tests.test_public_research_sessions import ctests
    c, _, _ = hsession(tmp_path, [], phase="code", limit=1)
    session, client = ctests._run([CONCLUDE, {"action": "revise", "patch": ctests._patch()},
        {"action": "test_patch"}, {"action": "ready"}, CONCLUDE],
        limits=CodeResearchLimits(max_turns=5))
    session._observation = c
    session._test_patch = ctests._passing_development_test
    result = session.run(ctests._snapshot())
    assert isinstance(result, ctests.PatchProposal)
    assert c.conclusion is None and len(client.calls) == 4
    c.close()
    with pytest.raises(PublicResearchStop): c.conclude_research(CONCLUDE)


def test_q12_cli_investigation_returns_zero_without_scientific_completion(tmp_path, monkeypatch):
    from dataclasses import asdict
    from scion.cli.main import app
    from scion.proposal.engine import CreativeLayer
    problem = tmp_path / "problem-v1.yaml"
    problem.write_text((cv.CVRP_DIR / "problem-v1.yaml").read_text().replace("PLACEHOLDER", str(cv.CVRP_DIR)))
    configs = {"input": {"current_question": QUESTION, "observations": []},
        "limits": asdict(CodeResearchLimits()),
        "public": asdict(config(budget=replace(config().budget,
            max_source_bytes=64 * 1024**2, max_files_per_action=4000, max_storage_bytes=512 * 1024**2)))}
    for name, value in configs.items(): (tmp_path / (name + ".json")).write_text(json.dumps(value))
    monkeypatch.setenv("SCION_PROBLEM_DATA_ROOT", str(cv.VRP_DIR))
    monkeypatch.setattr(CreativeLayer, "call_hypothesis_research_turn", lambda *_: deepcopy(CONCLUDE))
    result = CliRunner().invoke(app, ["run", "--problem", str(problem), "--mock-llm",
        "--campaign-dir", str(tmp_path / "campaign"), "--run-intent", "investigation", "--formal-stage-limit", "0",
        "--research-input", str(tmp_path / "input.json"), "--code-research-limits", str(tmp_path / "limits.json"),
        "--public-research", str(tmp_path / "public.json"), "--provider-call-cap", "50", "--outer-hardwall-sec", "600",
        "--protocol", str(cv.CONTROLLED_DIR / "protocol.yaml"), "--split", str(cv.CONTROLLED_DIR / "split_manifest.yaml"),
        "--seeds", str(cv.CONTROLLED_DIR / "seed_ledger.yaml")])
    assert result.exit_code == 0, (result.output, result.exception)
    terminal = json.loads((tmp_path / "campaign" / "status.json").read_text())["run_result"]
    assert terminal["stop_reason"] == "research_concluded" and terminal["requested_rounds"] is None
    assert terminal["run_validity"]["reason"] == "invalid_no_evaluated_outcome"


@pytest.mark.parametrize("fault", ["signal", "exception"])
def test_q14_post_close_interruption_keeps_saved_reference(tmp_path, monkeypatch, fault):
    from scion.cli.commands.init_run import (
        _CampaignSignalStop, _CampaignOuterHardwall, _run_campaign_with_signal_finalization,
    )
    import signal
    manager = make_campaign(tmp_path, monkeypatch)
    manager._proposal_pipeline.creative = HScript([CONCLUDE])
    def stop_after_close(_):
        session = manager._public_research.active
        if session.closed and session.conclusion:
            if fault == "signal":
                raise _CampaignSignalStop(signal.SIGTERM, "signal:SIGTERM")
            raise RuntimeError("terminal transition interrupted")
    manager._proposal_pipeline.check_research_stop = stop_after_close
    with pytest.raises(_CampaignSignalStop if fault == "signal" else RuntimeError):
        _run_campaign_with_signal_finalization(manager, requested_rounds=None,
            hardwall=_CampaignOuterHardwall(600))
    terminal = json.loads((tmp_path / "campaign" / "status.json").read_text())["run_result"]
    assert terminal["conclusion_ref"] and terminal["status"] == "stopped"
    assert terminal["unexecuted_work"] and terminal["evaluated_rounds"] == 0
    assert (manager._public_research.service.materials.root / terminal["conclusion_ref"]).exists()


@pytest.mark.parametrize("action,reason", [
    ("reconcile", "RECONCILE_NO_ACCEPTED_CHANGES"), ("explore", "BRANCH_STALE_DURING_EXPLORE"),
])
def test_q14_existing_stale_housekeeping_remains_nonterminal(tmp_path, monkeypatch, action, reason):
    from scion.core.step_result import StepResult
    manager = make_campaign(tmp_path, monkeypatch)
    manager._proposal_pipeline.creative = HScript([CONCLUDE])
    original_step = manager._run_scheduled_step
    pending = [StepResult(action=action,
        execution_outcome=ExecutionOutcomeRecord(ExecutionOutcome.NOT_EVALUATED, reason))]
    monkeypatch.setattr(manager, "_run_scheduled_step", lambda: pending.pop() if pending else original_step())
    result = manager.run()
    assert result.completed and result.stop_reason == "research_concluded"
    assert result.evaluated_rounds == 0 and result.execution_outcome_counts["research_concluded"] == 1
