from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.config.protocol_config import ScreeningConfig
from scion.core.models import ExperimentStage, RunResult, SolverOutput
from scion.protocol.experiment import (
    ExperimentProtocol,
    PairedExecutionSpec,
    SeedLedger,
    SplitManager,
    stages,
)
from scion.problem.spec import ObjectiveMetricSpec


def _result(score=1, *, success=True, feasible=True, runtime=None):
    return RunResult(
        success=success,
        exit_code=0 if success else 7,
        stdout="",
        stderr="failed" if not success else "",
        elapsed_ms=20 + score,
        output=(
            SolverOutput(
                objective={"score": score}, feasible=feasible,
                runtime={} if runtime is None else runtime,
            )
            if success
            else None
        ),
        error_category=None if success else "crash",
    )


class _Runner:
    def __init__(self, champion, candidate):
        self.champion = str(champion)
        self.candidate = str(candidate)
        self.calls = []
        self.results = {self.champion: _result(2), self.candidate: _result(1)}

    def run_solver(self, **kwargs):
        self.calls.append(dict(kwargs))
        value = self.results[kwargs["workdir"]]
        if isinstance(value, BaseException):
            raise value
        return value


def _protocol(tmp_path, *, cases=("case.json",), seeds=(7,), problem_spec=None):
    champion = tmp_path / "champion"
    candidate = tmp_path / "candidate"
    for workspace in (champion, candidate):
        workspace.mkdir()
        (workspace / "registry.yaml").write_text("version: test\n")
        for case in cases:
            (workspace / case).write_text("{}\n")
    runner = _Runner(champion, candidate)
    protocol = ExperimentProtocol(
        protocol_config=ProtocolConfig(
            screening=ScreeningConfig(
                n_cases_modify=len(cases), n_cases_create=len(cases)
            )
        ),
        split_manager=SplitManager(
            SplitManifest(
                version="test",
                screening=list(cases),
                validation=["validation.json"],
                frozen=["frozen.json"],
                canary=["canary.json"],
            )
        ),
        seed_ledger=SeedLedger(
            SeedLedgerConfig(
                version="test",
                screening=list(seeds),
                validation=[11],
                frozen=[13],
                canary=[17],
            )
        ),
        runner=runner,
        time_limit_sec=10,
        metrics_dir=str(tmp_path / "metrics"),
        metric_specs=(
            ObjectiveMetricSpec(name="score", direction="minimize", priority=1),
        ),
        problem_spec=problem_spec,
    )
    return protocol, runner, candidate, champion


def _spec(*, candidate=0, block=0, cases=None, seeds=None):
    return PairedExecutionSpec(
        candidate_ordinal=candidate,
        block_id="quality",
        block_ordinal=block,
        case_ordinals=cases or {"case.json": 0},
        seed_ordinals=seeds or {7: 0},
    )


def _run(protocol, candidate, champion, spec=None, *, selected_surface=None):
    return protocol.run_experiment(
        ExperimentStage.SCREENING,
        str(candidate),
        str(champion),
        "modify",
        selected_surface=selected_surface,
        paired_execution=spec,
    )


def test_spec_copies_freezes_and_preflights_before_runner(tmp_path):
    case_ordinals = {"case.json": 0}
    spec = _spec(cases=case_ordinals)
    case_ordinals["case.json"] = 9
    assert spec.case_ordinals["case.json"] == 0
    with pytest.raises(TypeError):
        spec.case_ordinals["case.json"] = 1

    protocol, runner, candidate, champion = _protocol(tmp_path)
    invalid = _spec(cases={"case.json": True})
    with pytest.raises(ValueError, match="non-negative integer"):
        _run(protocol, candidate, champion, invalid)
    assert runner.calls == []
    assert list((tmp_path / "metrics").glob("*.json")) == []


def test_preflight_rejects_duplicate_selected_ordinals(tmp_path):
    cases = ("one.json", "two.json")
    protocol, runner, candidate, champion = _protocol(tmp_path, cases=cases)
    spec = _spec(cases={"one.json": 0, "two.json": 0})
    with pytest.raises(ValueError, match="case ordinals must be unique"):
        _run(protocol, candidate, champion, spec)
    assert runner.calls == []


def test_paired_order_is_global_fresh_and_records_complete_a_b_raw(tmp_path):
    protocol, runner, candidate, champion = _protocol(tmp_path)
    ab = _run(protocol, candidate, champion, _spec(candidate=0))
    ba = _run(protocol, candidate, champion, _spec(candidate=1))

    assert [call["workdir"] for call in runner.calls] == [
        str(champion), str(candidate), str(candidate), str(champion)
    ]
    for result, expected in ((ab, "AB"), (ba, "BA")):
        raw = json.loads(Path(result.raw_metrics_ref).read_text())
        assert "paired_execution" not in raw
        pair = raw["pairs"][0]["paired_execution"]
        assert pair["scheduled_order"] == pair["actual_order"] == expected
        assert pair["block_ordinal"] == 0
        assert pair["A"]["objective"] == {"score": 2}
        assert pair["B"]["objective"] == {"score": 1}
        assert pair["A"]["time_limit_sec"] == pair["B"]["time_limit_sec"] == 10
        assert pair["A"]["success"] is pair["B"]["success"] is True
        assert "candidate_ordinal" not in pair
        assert "decision_excluded" not in pair


@pytest.mark.parametrize("failure_mode", ["process", "infeasible", "audit"])
def test_paired_invalid_b_is_counted_and_excluded_from_statistics(
    tmp_path, monkeypatch, failure_mode
):
    protocol, runner, candidate, champion = _protocol(tmp_path)
    if failure_mode == "process":
        runner.results[str(candidate)] = _result(1, success=False)
    elif failure_mode == "infeasible":
        runner.results[str(candidate)] = _result(1, feasible=False)
    else:
        monkeypatch.setattr(
            stages,
            "runtime_audit_failure_from_result",
            lambda result, **_kwargs: (
                {"error_category": "test_audit_failure"}
                if result.output and result.output.objective == {"score": 1}
                else None
            ),
        )

    result = _run(protocol, candidate, champion, _spec(candidate=1))
    assert len(runner.calls) == 2
    assert [call["workdir"] for call in runner.calls] == [
        str(candidate), str(champion)
    ]
    assert result.stats.valid_pairs == 0
    assert result.stats.failed_pairs == 1
    assert result.stats.candidate_failed_pairs == 1
    assert result.stats.champion_failed_pairs == 0
    assert result.stats.runtime_pairs == 0
    assert result.pair_feedback == ()
    pair = json.loads(Path(result.raw_metrics_ref).read_text())["pairs"][0]
    assert pair["comparison"] == "invalid"
    assert pair["delta"] is None
    assert pair["paired_execution"]["B"]["failure"]


@pytest.mark.parametrize(
    ("mode", "candidate_failures", "champion_failures", "shared", "bilateral"),
    (
        ("candidate", 1, 0, 0, 0),
        ("champion", 0, 1, 0, 0),
        ("shared", 0, 1, 1, 0),
        ("bilateral", 1, 1, 0, 1),
    ),
)
def test_paired_runtime_audit_failure_attribution_preserves_both_sides(
    tmp_path,
    monkeypatch,
    mode,
    candidate_failures,
    champion_failures,
    shared,
    bilateral,
):
    protocol, _runner, candidate, champion = _protocol(tmp_path)
    champion_issue = {
        "error_category": "solver_runtime_error",
        "runtime_error_field": "solver_errors",
        "detail": "solver runtime audit reported solver_errors=1",
    }
    candidate_issue = dict(champion_issue)
    if mode == "bilateral":
        candidate_issue = {
            **candidate_issue,
            "runtime_error_field": "candidate_errors",
            "detail": "solver runtime audit reported candidate_errors=1",
        }

    def audit(result, **_kwargs):
        is_candidate = result.output.objective == {"score": 1}
        if mode == "candidate":
            return candidate_issue if is_candidate else None
        if mode == "champion":
            return None if is_candidate else champion_issue
        return candidate_issue if is_candidate else champion_issue

    monkeypatch.setattr(stages, "runtime_audit_failure_from_result", audit)
    result = _run(protocol, candidate, champion, _spec(candidate=1))

    assert result.stats.failed_pairs == 1
    assert result.stats.candidate_failed_pairs == candidate_failures
    assert result.stats.champion_failed_pairs == champion_failures
    assert result.stats.shared_failed_pairs == shared
    assert result.stats.bilateral_failed_pairs == bilateral
    raw = json.loads(Path(result.raw_metrics_ref).read_text())
    failure = raw["failures"][0]
    expected_side = mode if mode in ("candidate", "champion") else "both"
    assert failure["side"] == expected_side
    assert failure["failure_attribution"] == mode
    if mode in ("shared", "bilateral"):
        assert failure["champion_runtime_audit"] == champion_issue
        assert failure["candidate_runtime_audit"] == candidate_issue
        assert failure["error_category"] == f"{mode}_runtime_audit_failure"
    assert raw["pairs"][0]["comparison"] == "invalid"
    assert result.pair_feedback == ()


def test_base_exception_keeps_original_without_partial_metrics(tmp_path):
    protocol, runner, candidate, champion = _protocol(tmp_path)
    error = KeyboardInterrupt("stop")
    runner.results[str(candidate)] = error
    with pytest.raises(KeyboardInterrupt) as raised:
        _run(protocol, candidate, champion, _spec())
    assert raised.value is error
    assert list((tmp_path / "metrics").iterdir()) == []


@pytest.mark.parametrize("runtime", [{}, {"surface_loaded": False}])
def test_paired_telemetry_diagnostics_do_not_reenter_legacy_champion_audit(
    tmp_path, monkeypatch, runtime
):
    problem_spec = SimpleNamespace(
        research_surfaces=[SimpleNamespace(
            name="surface", evidence=SimpleNamespace(
                required_runtime_fields=["surface_loaded"]
            ),
        )]
    )
    protocol, runner, candidate, champion = _protocol(
        tmp_path, problem_spec=problem_spec
    )
    runner.results[str(champion)] = _result(2, runtime=runtime)
    runner.results[str(candidate)] = _result(1, runtime=runtime)
    original = stages.runtime_audit_failure_from_result
    calls = []

    def audited(result, **kwargs):
        calls.append(kwargs)
        return original(result, **kwargs)

    monkeypatch.setattr(stages, "runtime_audit_failure_from_result", audited)
    result = _run(
        protocol, candidate, champion, _spec(), selected_surface="surface"
    )
    assert result.stats.valid_pairs == 1
    assert result.stats.failed_pairs == 0
    assert len(calls) == 2
    assert all(call == {
        "problem_spec": problem_spec, "selected_surface": "surface"
    } for call in calls)


def test_default_path_executes_both_sides_fresh_and_reports_progress(tmp_path):
    protocol, runner, candidate, champion = _protocol(tmp_path)
    events = []
    protocol.set_progress_callback(lambda **payload: events.append(payload))
    first = _run(protocol, candidate, champion)
    _run(protocol, candidate, champion)

    assert [call["workdir"] for call in runner.calls] == [
        str(champion), str(candidate), str(champion), str(candidate)
    ]
    raw = json.loads(Path(first.raw_metrics_ref).read_text())
    assert "paired_execution" not in raw
    assert "paired_execution" not in raw["pairs"][0]
    assert events[0]["case"] is None and events[0]["seed"] is None
    assert "raw_metrics_ref" not in events[0]
    pair_start = next(event for event in events if "time_limit_sec" in event)
    assert pair_start["case"] == "case.json" and pair_start["seed"] == 7
    assert pair_start["attempted_pairs"] == 1
    assert pair_start["valid_pairs"] == 0
    final = next(event for event in events if event.get("complete") is True)
    assert "case" not in final and "seed" not in final
    assert final["raw_metrics_ref"] == first.raw_metrics_ref
