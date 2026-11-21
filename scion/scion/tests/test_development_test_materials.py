"""P5c A / Q01–Q07: exact readback without changing test/ready authority."""
import base64
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from scion.core.code_research_limits import CodeResearchLimits
from scion.observation.config import PublicResearchStop
from scion.proposal.code_research_session import CodeResearchSession, CodeResearchAbandon
from scion.proposal.engine.exceptions import ProposalValidationError
from scion.tests.test_public_research_sessions import controller, opened
from scion.tests.test_research_continuity import make_controller, read
from scion.tests.test_observation_execution import budget
from scion.tests.unit.proposal import test_code_research_session as old


SCRIPT = "# 原始实验，不改空行\r\n\r\ndef test_counterexample():\r\n    assert False\r\n" + "# 可回读\n" * 400
REVISE = {"action": "revise", "patch": old._patch()}
TEST = {"action": "test_patch", "falsifier_source": SCRIPT}
ABANDON = {"outcome": "abandon", "reason": "counterexample remains"}


def failed(*args):
    return {**old._passing_development_test(*args), "falsifier_outcome": "failed",
            "falsifier_diagnostic": {"phase": "call", "exception_kind": "assertion_error", "probe_line": 4}}


class Scripted:
    def __init__(self, responses):
        self.responses = list(responses)
        self.snapshots = []

    def call_code_research_turn(self, snapshot):
        self.snapshots.append(snapshot)
        action = self.responses.pop(0)
        return action(snapshot) if callable(action) else deepcopy(action)

    call_code_research_finalize = call_code_research_turn


def session(c, responses, *, callback=failed, limits=None):
    creative = Scripted(responses)
    runner = CodeResearchSession(creative, limits or CodeResearchLimits(max_turns=len(responses) - 1),
                                 observation_session=c, test_patch=callback)
    return runner, creative


def body(c, name="result.json", number=1):
    ref = f"development-tests/session-{c.ordinal:06d}/{number:06d}/{name}"
    return json.loads(read(c, ref))


def test_q01_failed_test_is_readable_in_next_turn_and_exact_pages(tmp_path):
    c = opened(controller(tmp_path, limits=budget(max_read_bytes=65536, max_search_scan_bytes=65536)), "code")

    def read_script(snapshot):
        ctx = snapshot.structured_context
        previous = ctx["code_research"]["tool_results"][-1]
        assert previous["falsifier_diagnostic"]["probe_line"] == 4
        assert previous["request_ref"] in c.visible and previous["result_ref"] in c.visible
        assert SCRIPT not in snapshot.user_prompt
        entry = next(e for e in ctx["research_material_index"] if e["kind"] == "script")
        return {"action": "read_research", "ref": entry["ref"], "offset": 0, "length": 65536}

    def verify_read(snapshot):
        result = snapshot.structured_context["public_observation"]["tool_results"][-1]
        assert base64.b64decode(result["data"]) == SCRIPT.encode()
        assert result["data"] in snapshot.user_prompt
        assert result["data"] not in json.dumps(snapshot.system_blocks)
        return {"action": "ready"}

    runner, script = session(c, [REVISE, TEST, read_script, verify_read, ABANDON])
    assert isinstance(runner.run(old._snapshot()), CodeResearchAbandon)
    assert runner.provider_calls_used == 5 and runner._test_calls == 1
    assert "latest_draft_falsifier_failed" in json.dumps(script.snapshots[-1].structured_context)
    request = body(c, "request.json")
    ref = request["script_ref"]
    reconstructed, offset = b"", 0
    while offset < len(SCRIPT.encode()):
        result = c.execute({"action": "read_research", "ref": ref, "offset": offset, "length": 257})
        reconstructed += base64.b64decode(result["data"])
        offset = result["next_offset"]
    assert reconstructed == SCRIPT.encode()
    assert body(c)["feedback"]["falsifier_outcome"] == "failed"
    found = c.execute({"action": "search_research", "query": "test_counterexample", "max_matches": 10})
    assert any(m["ref"] == ref for m in found["matches"])


def test_q01_real_isolated_failed_probe_roundtrip(tmp_path):
    from scion.tests.unit.test_code_development import _spec
    from scion.core.code_development import CodeDevelopmentEvaluator
    from scion.runtime.workspace import WorkspaceMaterializer
    from scion.verification.development import DevelopmentSuiteManifest
    root = tmp_path / "problem"
    (root / "tests").mkdir(parents=True)
    (root / "tests/test_public.py").write_text("def test_host(): assert True\n")
    evaluator = CodeDevelopmentEvaluator(
        materializer=WorkspaceMaterializer(str(tmp_path / "work"), editable_patterns=("operators/*.py",)),
        problem_spec=_spec(root), suites=(DevelopmentSuiteManifest(
            check_name="D3_unit_tests", source_root=str(root), test_path="tests/test_public.py"),),
        workspace_paths=(), problem_package_paths=(), limits=CodeResearchLimits())
    def callback(patch, timeout, corpus, falsifier):
        return evaluator.evaluate(patch=patch, source_corpus=corpus, selected_surface=None,
            total_timeout_sec=timeout, falsifier_source=falsifier).provider_projection()
    c = opened(controller(tmp_path / "materials"), "code")
    runner, _ = session(c, [REVISE, TEST, {"action": "ready"}, ABANDON], callback=callback)
    assert isinstance(runner.run(old._snapshot()), CodeResearchAbandon)
    result = body(c)
    assert result["feedback"]["outcome"] == "passed"
    assert result["feedback"]["falsifier_outcome"] == "failed"
    assert result["feedback"]["falsifier_diagnostic"]["probe_line"] == 4
    assert read(c, body(c, "request.json")["script_ref"]) == SCRIPT.encode()
    assert result["capture_scope"] == "request_only" and result["tested_source_refs"] == []


def test_q02_old_draft_survives_hint_revision_and_weak_probe(tmp_path):
    c = opened(controller(tmp_path), "code")
    changed_hint = {**old._patch(), "test_hint": "new author hint"}
    results = iter([failed(None, 1, {}), old._passing_development_test(None, 1, {})])
    runner, script = session(c, [REVISE, TEST, {"action": "revise", "patch": changed_hint},
        {"action": "test_patch"}, {"action": "ready"}, ABANDON], callback=lambda *_: next(results))
    assert isinstance(runner.run(old._snapshot()), CodeResearchAbandon)
    first, second = body(c, "request.json"), body(c, "request.json", 2)
    assert (first["draft_revision"], second["draft_revision"]) == (1, 2)
    assert first["source_condition"] != second["source_condition"]
    assert read(c, first["draft_files"][0]["ref"]) == read(c, second["draft_files"][0]["ref"])
    assert "new author hint" not in json.dumps(second)
    assert "latest_draft_falsifier_failed" in json.dumps(script.snapshots[-1].structured_context)
    assert "frozen_ready_patch" not in script.snapshots[-1].structured_context["code_research"]


def test_q02_multifile_requested_source_is_exact_and_new_draft_can_ready(tmp_path):
    c = opened(controller(tmp_path), "code")
    patch = old._patch()
    patch["additional_changes"] = [old._patch(old._SUPPORT_PATH)]
    calls = iter([failed(None, 1, {}), old._passing_development_test(None, 1, {})])
    runner, _ = session(c, [{"action": "read_source", "path": old._SUPPORT_PATH}, REVISE, TEST,
        {"action": "revise", "patch": patch}, {"action": "test_patch"}, {"action": "ready"}],
        callback=lambda *_: next(calls), limits=CodeResearchLimits(max_turns=6))
    result = runner.run(old._snapshot())
    request = body(c, "request.json", 2)
    assert len(request["draft_files"]) == len(result.iter_file_changes()) == 2
    for entry, change in zip(request["draft_files"], result.iter_file_changes()):
        assert entry["file_path"] == change.file_path
        assert read(c, entry["ref"]) == change.code_content.encode()
    assert body(c)["feedback"]["falsifier_outcome"] == "failed"


@pytest.mark.parametrize("outcome", ["passed", "failed", "timeout", "preflight_rejected", "unavailable"])
def test_q03_finite_outcomes_are_not_observation_success(tmp_path, outcome):
    c = opened(controller(tmp_path), "code")
    runner, _ = session(c, [REVISE, {"action": "test_patch"}, ABANDON],
        callback=lambda *_: {"outcome": outcome, "checks": []})
    runner.run(old._snapshot())
    result = body(c)
    assert result["feedback"]["outcome"] == outcome
    assert "falsifier_outcome" not in result["feedback"]
    assert body(c, "request.json")["script_ref"] is None
    assert result["execution_state"] == "returned"  # Callback, not child execution.
    assert result["usage"]["child_cpu_seconds"] is None
    assert c.service.usage["started_subjects"] == 0


def test_q03_missing_callback_is_not_started(tmp_path):
    c = opened(controller(tmp_path), "code")
    runner, _ = session(c, [REVISE, TEST, ABANDON], callback=None)
    runner.run(old._snapshot())
    result = body(c)
    assert result["execution_state"] == "not_started"
    assert result["usage"]["callback_wall_seconds"] == 0
    assert result["feedback"]["outcome"] == "unavailable"


def test_q04_only_bounded_projection_is_retained(tmp_path):
    c = opened(controller(tmp_path), "code")
    secret = "/host/private/heldout.json SECRET_VALUE"
    def callback(*args):
        return {**failed(*args), "stdout": secret, "stderr": secret, "api_key": secret,
                "falsifier_diagnostic": {"phase": "call", "exception_kind": "assertion_error", "message": secret}}
    runner, _ = session(c, [REVISE, TEST, ABANDON], callback=callback)
    runner.run(old._snapshot())
    result = body(c)
    assert "falsifier_diagnostic" not in result["feedback"]
    assert all(secret.encode() not in (c.service.materials.root / ref).read_bytes() for ref in c.own_refs)
    assert set(result["feedback"]) == {"action", "ok", "draft_revision", "outcome", "checks", "counts", "falsifier_outcome"}


@pytest.mark.parametrize("observation,materials", [(False, False), (True, False), (False, True), (True, True)])
def test_q05_switches_permissions_and_closed_materials(tmp_path, observation, materials):
    ctrl = make_controller(tmp_path, observation=observation, materials=materials)
    c = opened(ctrl, "code") if ctrl else None
    runner, script = session(c, [REVISE, TEST, ABANDON])
    runner.run(old._snapshot())
    if c is None:
        assert all("public_observation" not in s.structured_context for s in script.snapshots)
        assert not (tmp_path / "research").exists()
        return
    request = body(c, "request.json")
    original_script = request["script_ref"]
    c.close()
    h = opened(ctrl)
    inherited = [e for e in h.entries if e.get("origin_ref") == original_script]
    assert bool(inherited) == materials
    if materials:
        assert read(h, inherited[0]["ref"]) == SCRIPT.encode()
        req = next(e for e in h.entries if e.get("origin_ref", "").endswith("request.json"))
        assert not req["missing_dependencies"]
        assert req["source_availability"] == "projection_only"
    other_c = opened(ctrl, "code")
    assert other_c.execute({"action": "read_research", "ref": original_script, "offset": 0, "length": 64})["reason_code"] == "REF_NOT_VISIBLE"
    assert not any(e["kind"] == "script" for e in other_c.entries)
    assert ctrl.service.usage["started_subjects"] == ctrl.service.usage["started_analyses"] == 0


def test_q05_fresh_import_preserves_bytes_and_source_limitations(tmp_path):
    ctrl = make_controller(tmp_path / "old")
    c = opened(ctrl, "code")
    runner, _ = session(c, [REVISE, TEST, ABANDON])
    runner.run(old._snapshot())
    original_result = body(c)
    c.close()
    fresh = make_controller(tmp_path / "new", imports=[ctrl.continuity.root])
    h = opened(fresh)
    scripts = [e for e in h.entries if e["kind"] == "script"]
    assert len(scripts) == 1 and read(h, scripts[0]["ref"]) == SCRIPT.encode()
    result = next(e for e in h.entries if e["kind"] == "output")
    assert json.loads(read(h, result["ref"])) == original_result
    assert not result["missing_dependencies"] and result["source_availability"] == "projection_only"
    assert fresh.service.usage["started_subjects"] == 0


@pytest.mark.parametrize("when", ["request", "result", "begin_index", "finish_index"])
def test_q06_write_failure_stops_without_retry_or_ready(tmp_path, monkeypatch, when):
    c = opened(controller(tmp_path), "code")
    calls = []
    def callback(*args):
        calls.append(1)
        return failed(*args)
    write = c.service._bytes
    def faulty(path, content):
        if ((when in {"request", "result"} and path.name == f"{when}.json")
                or (when.endswith("index") and path.name.endswith("-index.json")
                    and bool(calls) == (when == "finish_index"))):
            raise OSError("PRIVATE_HOST_ERROR")
        return write(path, content)
    monkeypatch.setattr(c.service, "_bytes", faulty)
    runner, script = session(c, [REVISE, TEST, {"action": "ready"}, ABANDON], callback=callback)
    with pytest.raises(PublicResearchStop, match="PERSISTENCE_ERROR") as error:
        runner.run(old._snapshot())
    assert error.value.record.outcome.value == "blocked_infra"
    assert len(calls) == (1 if when in {"result", "finish_index"} else 0)
    assert runner.provider_calls_used == len(script.snapshots) == 2
    assert c.controller.failure_reason == "PERSISTENCE_ERROR"
    with pytest.raises(PublicResearchStop):
        opened(c.controller)


@pytest.mark.parametrize("exception,state", [(KeyboardInterrupt, "interrupted"), (RuntimeError, "unknown")])
def test_q06_callback_error_preserves_request_and_cost(tmp_path, exception, state):
    c = opened(controller(tmp_path), "code")
    calls = []
    def callback(*args):
        calls.append(1)
        raise exception("PRIVATE_HOST_ERROR")
    runner, _ = session(c, [REVISE, TEST, ABANDON], callback=callback)
    with pytest.raises(exception):
        runner.run(old._snapshot())
    result = body(c)
    assert result["execution_state"] == state and result["feedback"] is None
    assert result["usage"]["callback_wall_seconds"] == runner._test_elapsed_sec
    assert runner.provider_calls_used == 2 and len(calls) == 1
    assert "PRIVATE_HOST_ERROR" not in json.dumps(result)


def test_q07_storage_reserved_before_callback_and_no_extra_turn(tmp_path):
    c = opened(controller(tmp_path), "code")
    cap = c.service.materials.used_bytes() + len(SCRIPT.encode())
    c.service.budget = replace(c.service.budget, max_storage_bytes=cap)
    runner, _ = session(c, [REVISE, TEST, ABANDON], callback=lambda *_: pytest.fail("must not execute"))
    with pytest.raises(PublicResearchStop, match="GLOBAL_RESEARCH_LIMIT"):
        runner.run(old._snapshot())
    assert runner._test_calls == 0 and runner.provider_calls_used == 2
    assert c.service.materials.used_bytes() <= cap
    assert not c.own_refs


def test_q07_callback_time_not_charged_as_material_cpu_or_wall(tmp_path, monkeypatch):
    import scion.proposal.code_research_session as module
    # Rebind this module's clock only; service accounting retains the real clock.
    from types import SimpleNamespace
    times = iter([100., 107.])
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: next(times)))
    c = opened(controller(tmp_path), "code")
    runner, _ = session(c, [REVISE, TEST, ABANDON])
    runner.run(old._snapshot())
    result = body(c)
    assert runner._test_elapsed_sec == result["usage"]["callback_wall_seconds"] == 7
    assert c.service.usage["wall_seconds"] < 7 and c.service.usage["cpu_seconds"] < 7
    assert c.service.session_actions == 1  # Our explicit result read only.
    assert result["usage"]["child_cpu_seconds"] is None


def test_q07_result_limit_keeps_request_but_cannot_ready(tmp_path):
    c = opened(controller(tmp_path), "code")
    runner, _ = session(c, [REVISE, TEST, {"action": "ready"}, ABANDON],
        limits=CodeResearchLimits(max_turns=3, max_test_result_chars=256))
    with pytest.raises(ProposalValidationError, match="max_test_result_chars"):
        runner.run(old._snapshot())
    assert runner.provider_calls_used == 2
    assert body(c)["feedback"] is None
    assert body(c, "request.json")["script_ref"] in c.visible


@pytest.mark.parametrize("command", [{"action": "test_patch"}, {**TEST, "falsifier_source": "bad\x00script"}])
def test_q07_invalid_request_does_not_create_materials(tmp_path, command):
    c = opened(controller(tmp_path), "code")
    responses = ([REVISE] if "falsifier_source" in command else []) + [command, ABANDON]
    runner, _ = session(c, responses)
    runner.run(old._snapshot())
    assert not c.own_refs and runner._test_calls == 0


@pytest.mark.parametrize("delta", [-1, 0])
def test_q07_feedback_size_boundary_keeps_original_cap(tmp_path, delta):
    c = opened(controller(tmp_path / "measure"), "code")
    runner, _ = session(c, [REVISE, TEST, ABANDON])
    runner.run(old._snapshot())
    exact_size = runner._test_result_chars
    other = opened(controller(tmp_path / "boundary"), "code")
    bounded, _ = session(other, [REVISE, TEST, ABANDON],
        limits=CodeResearchLimits(max_turns=2, max_test_result_chars=exact_size + delta))
    if delta < 0:
        with pytest.raises(ProposalValidationError, match="max_test_result_chars"):
            bounded.run(old._snapshot())
        assert bounded.provider_calls_used == 2
    else:
        assert isinstance(bounded.run(old._snapshot()), CodeResearchAbandon)
        assert bounded._test_result_chars == exact_size
        # Ref metadata costs are still included in the ordinary tool budget.
        from scion.proposal.bounded_research import bounded_json
        assert bounded._budget.tool_chars == sum(len(bounded_json(r)) for r in bounded._budget.results)
        assert bounded._budget.tool_chars > exact_size


@pytest.mark.parametrize("when", ["before", "after"])
def test_q07_shared_time_limit_stops_without_ready(tmp_path, when):
    c = opened(controller(tmp_path), "code")
    calls = []
    def callback(*args):
        calls.append(1)
        c.service.stopped = True
        return old._passing_development_test(*args)
    def test_action(snapshot):
        if when == "before":
            c.service.stopped = True
        return TEST
    runner, _ = session(c, [REVISE, test_action, {"action": "ready"}, ABANDON], callback=callback)
    with pytest.raises(PublicResearchStop, match="GLOBAL_RESEARCH_LIMIT") as error:
        runner.run(old._snapshot())
    assert error.value.record.outcome.value == "resource_exhausted"
    assert len(calls) == (when == "after") and runner.provider_calls_used == 2


def test_q06_secondary_write_failure_does_not_mask_callback_interrupt(tmp_path, monkeypatch):
    c = opened(controller(tmp_path), "code")
    def callback(*args):
        raise KeyboardInterrupt()
    write = c.service._bytes
    def faulty(path, value):
        if path.name == "result.json":
            raise OSError("unwritable")
        return write(path, value)
    monkeypatch.setattr(c.service, "_bytes", faulty)
    runner, _ = session(c, [REVISE, TEST, ABANDON], callback=callback)
    with pytest.raises(KeyboardInterrupt):
        runner.run(old._snapshot())
    assert c.controller.failure_reason == "PERSISTENCE_ERROR"
    assert runner.provider_calls_used == 2 and runner._test_calls == 1


@pytest.mark.parametrize("reason,expected", [("PERSISTENCE_ERROR", "blocked_infra"),
                                           ("GLOBAL_RESEARCH_LIMIT", "resource_exhausted")])
def test_q06_code_pipeline_propagates_material_stop(tmp_path, monkeypatch, reason, expected):
    from types import SimpleNamespace
    from scion.observation.source import ObservationError
    from scion.tests.unit.core.proposal_pipeline_test_support import _pipeline
    ctrl = controller(tmp_path)
    pipeline, branch, runtime, _ = _pipeline(branch_workspace=str(ctrl.source_roots[-1]))
    hypothesis = pipeline.creative.hypothesis
    h = opened(ctrl)
    handoff = h.freeze_handoff(hypothesis, [])
    pipeline.public_research = ctrl
    pipeline.code_research_limits = CodeResearchLimits(max_turns=3)
    runtime.build_code_context = lambda **_: old._snapshot().structured_context
    creative = Scripted([REVISE, TEST, {"action": "ready"}])
    pipeline.creative = creative
    calls = []
    def evaluate(**kwargs):
        calls.append(1)
        return SimpleNamespace(provider_projection=lambda: failed(None, 1, {}))
    pipeline.code_development_evaluator = SimpleNamespace(evaluate=evaluate)
    write = ctrl.service._bytes
    def faulty(path, content):
        if path.name == "result.json":
            raise ObservationError(reason)
        return write(path, content)
    monkeypatch.setattr(ctrl.service, "_bytes", faulty)
    attempt = pipeline.generate_code(branch, hypothesis, research_handoff=handoff)
    assert attempt.proposal is None and attempt.execution_outcome.outcome.value == expected
    assert attempt.execution_outcome.reason_code == reason
    assert len(calls) == 1 and len(creative.snapshots) == 2
