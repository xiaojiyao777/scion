from __future__ import annotations

import inspect
import json
import signal
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
import run_fixed_candidate_funnel as driver
from scion.core.models import CanaryResult, Decision, ExperimentStage, RunResult


def _write_source(root: Path, *, local_search: str) -> None:
    (root / "policies" / "baseline_modules").mkdir(parents=True)
    (root / "policies" / "baseline_algorithm.py").write_text("BASE = 1\n")
    (root / "policies" / "baseline_modules" / "local_search.py").write_text(
        local_search
    )
    (root / "problem-v1.yaml").write_text("spec_version: problem-v1\n")


def _manifest() -> SimpleNamespace:
    return SimpleNamespace(
        screening=["screen-a", "screen-b"],
        validation=["validate"],
        frozen=["frozen"],
        canary=["canary"],
        safe_data_roots=[],
    )


def _seeds() -> SimpleNamespace:
    return SimpleNamespace(screening=[3, 5], validation=[7], frozen=[11], canary=[13])


def _envelope() -> driver.ResourceEnvelope:
    return driver.ResourceEnvelope(
        max_solver_subprocesses=12,
        nominal_subject_seconds=120,
        guarded_subject_seconds=300,
        max_time_limit_sec=20,
        timeout_guard_sec=15,
        outer_hardwall_sec=600,
        fallback_time_limit_sec=10,
        memory_mb=4096,
    )


def _prepared(tmp_path: Path) -> driver.Prepared:
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    _write_source(baseline, local_search="VALUE = 1\n")
    _write_source(candidate, local_search="VALUE = 2\n")
    retained_manifest = SimpleNamespace(
        screening=[],
        validation=[],
        frozen=["retained"],
        canary=[],
        safe_data_roots=[],
    )
    retained_seeds = SimpleNamespace(
        screening=[], validation=[], frozen=[17], canary=[]
    )
    return driver.Prepared(
        label="fixed-funnel-test",
        baseline=baseline,
        candidate=candidate,
        problem_spec_path=baseline / "problem-v1.yaml",
        protocol_path=tmp_path / "protocol.yaml",
        split_path=tmp_path / "split.yaml",
        seeds_path=tmp_path / "seeds.yaml",
        retained_split_path=tmp_path / "retained-split.yaml",
        retained_seeds_path=tmp_path / "retained-seeds.yaml",
        changed_files=("policies/baseline_modules/local_search.py",),
        selected_surface="solver_design",
        protocol_config=SimpleNamespace(),
        split_manifest=_manifest(),
        seed_config=_seeds(),
        retained_split_manifest=retained_manifest,
        retained_seed_config=retained_seeds,
        bridge=SimpleNamespace(),
        adapter=SimpleNamespace(),
        envelope=_envelope(),
    )


def _stats(
    *,
    failed_pairs: int = 0,
    candidate_failed: int = 0,
    champion_failed: int = 0,
    shared: int = 0,
    bilateral: int = 0,
):
    values = {name: 0 for name in driver.SUMMARY_FIELDS}
    values.update(
        n_cases=2,
        wins=2,
        win_rate=1.0,
        median_delta=3.0,
        ci_low=1.0,
        ci_high=4.0,
        attempted_pairs=2,
        valid_pairs=2 - failed_pairs,
        failed_pairs=failed_pairs,
        candidate_failed_pairs=candidate_failed,
        champion_failed_pairs=champion_failed,
        shared_failed_pairs=shared,
        bilateral_failed_pairs=bilateral,
    )
    return SimpleNamespace(**values)


def _result(stage: ExperimentStage, *, gate: str = "pass", **stats):
    return SimpleNamespace(
        stage=stage,
        gate_outcome=gate,
        reason_codes=(f"{stage.value.upper()}_{gate.upper()}",),
        case_ids=(f"{stage.value}-case",),
        seed_set=(1,),
        raw_metrics_ref=f"metrics/{stage.value}.json",
        stats=_stats(**stats),
    )


class _Protocol:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def run_canary(self, candidate, baseline, **kwargs):
        self.calls.append(("canary", candidate, baseline, kwargs))
        return CanaryResult(True, details={"passed": True})

    def run_experiment(self, stage, candidate, baseline, action, **kwargs):
        self.calls.append((stage, candidate, baseline, action, kwargs))
        return self.results.pop(0)


class _Runner:
    def __init__(self, counters=None):
        self._counters = counters or {
            "solver_subprocesses": 12,
            "nominal_subject_seconds": 120,
            "guarded_subject_seconds": 300,
        }

    def counters(self):
        return dict(self._counters)

    def terminate_active_processes(self, *, reason="shutdown"):
        del reason
        return 0


def _install_decisions(monkeypatch, *decisions):
    pending = list(decisions)

    def decide(*_args, **_kwargs):
        return SimpleNamespace(decision=pending.pop(0), reason_codes=())

    monkeypatch.setattr(driver, "_decide", decide)


def test_direct_source_diff_uses_paths_and_bytes_without_hashes(tmp_path):
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    _write_source(baseline, local_search="VALUE = 1\n")
    _write_source(candidate, local_search="VALUE = 2\n")
    cache = candidate / "policies" / "baseline_modules" / "__pycache__"
    cache.mkdir()
    (cache / "local_search.pyc").write_bytes(b"generated")

    changed = ("policies/baseline_modules/local_search.py",)
    assert driver.validate_source_difference(baseline, candidate, changed) == changed

    (candidate / "problem-v1.yaml").write_text("different\n")
    with pytest.raises(driver.PrepError, match="changed-file set"):
        driver.validate_source_difference(baseline, candidate, changed)

    source = inspect.getsource(driver)
    assert "import hashlib" not in source
    assert "git rev-parse" not in source


def test_direct_source_diff_rejects_symlinks(tmp_path):
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    _write_source(baseline, local_search="VALUE = 1\n")
    _write_source(candidate, local_search="VALUE = 2\n")
    outside = tmp_path / "outside"
    outside.write_text("outside\n")
    (candidate / "alias").symlink_to(outside)

    with pytest.raises(driver.PrepError, match="symlink"):
        driver.validate_source_difference(
            baseline,
            candidate,
            ("policies/baseline_modules/local_search.py",),
        )


def test_private_source_snapshots_isolate_the_live_run_from_external_mutation(
    tmp_path,
):
    prepared = _prepared(tmp_path)
    output = tmp_path / "output"
    output.mkdir()

    snapshotted = driver._snapshot_prepared_sources(prepared, output)
    original_candidate = prepared.candidate / prepared.changed_files[0]
    snapshot_candidate = snapshotted.candidate / prepared.changed_files[0]
    original_candidate.write_text("VALUE = 999\n")

    assert snapshot_candidate.read_text() == "VALUE = 2\n"
    assert snapshotted.baseline.parent == output / "input_snapshots"
    assert snapshotted.candidate.parent == output / "input_snapshots"
    assert not bool(snapshot_candidate.stat().st_mode & 0o200)
    driver._make_dirs_writable(output / "input_snapshots")


def test_output_must_not_be_created_inside_a_source_tree(tmp_path):
    prepared = _prepared(tmp_path)
    output = prepared.candidate / "experiment-output"

    with pytest.raises(driver.PrepError, match="outside both source trees"):
        driver._validate_output_location(output, prepared)
    assert not output.exists()


def test_candidate_scope_rejects_files_outside_selected_surface():
    spec = SimpleNamespace(
        research_surfaces=[
            SimpleNamespace(
                name="solver_design",
                kind="solver_design",
                target_files=["policies/*.py"],
                modify_allowed=True,
            )
        ],
        search_space=SimpleNamespace(
            editable=["policies/*.py"],
            frozen=["policies/frozen.py"],
        ),
    )
    driver.validate_candidate_scope(
        spec,
        selected_surface="solver_design",
        changed_files=("policies/local_search.py",),
    )

    with pytest.raises(driver.PrepError, match="selected research surface"):
        driver.validate_candidate_scope(
            spec,
            selected_surface="solver_design",
            changed_files=("core/decision.py",),
        )
    with pytest.raises(driver.PrepError, match="frozen"):
        driver.validate_candidate_scope(
            spec,
            selected_surface="solver_design",
            changed_files=("policies/frozen.py",),
        )


def test_success_reuses_candidate_then_retains_one_promoted_copy(tmp_path, monkeypatch):
    prepared = _prepared(tmp_path)
    main = _Protocol(
        [
            _result(ExperimentStage.SCREENING),
            _result(ExperimentStage.VALIDATION),
            _result(ExperimentStage.FROZEN),
        ]
    )
    retained = _Protocol([_result(ExperimentStage.FROZEN)])
    monkeypatch.setattr(driver, "_make_protocols", lambda *_args: (main, retained))
    _install_decisions(
        monkeypatch,
        Decision.QUEUE_VALIDATE,
        Decision.QUEUE_FROZEN,
        Decision.PROMOTE,
    )

    output = tmp_path / "output"
    output.mkdir()
    payload = driver.execute(prepared, output, _Runner())

    assert payload["terminal_type"] == "PROMOTED_RETAINED"
    assert [call[0] for call in main.calls] == [
        "canary",
        ExperimentStage.SCREENING,
        ExperimentStage.VALIDATION,
        ExperimentStage.FROZEN,
    ]
    assert main.calls[0][3]["require_complete_pairs"] is True
    main_candidates = [call[1] for call in main.calls[1:]]
    assert main_candidates == [str(prepared.candidate)] * 3
    snapshot = output / "promoted_candidate"
    assert snapshot.is_dir()
    assert retained.calls[0][1] == str(snapshot)
    assert driver.sources_equal(prepared.candidate, snapshot)
    assert "champion_version" not in payload["promotion"]


def test_retained_comparator_failure_is_incomplete_not_failed_retention(
    tmp_path, monkeypatch
):
    prepared = _prepared(tmp_path)
    main = _Protocol(
        [
            _result(ExperimentStage.SCREENING),
            _result(ExperimentStage.VALIDATION),
            _result(ExperimentStage.FROZEN),
        ]
    )
    retained = _Protocol(
        [
            _result(
                ExperimentStage.FROZEN,
                gate="fail",
                failed_pairs=1,
                champion_failed=1,
            )
        ]
    )
    monkeypatch.setattr(driver, "_make_protocols", lambda *_args: (main, retained))
    _install_decisions(
        monkeypatch,
        Decision.QUEUE_VALIDATE,
        Decision.QUEUE_FROZEN,
        Decision.PROMOTE,
    )
    output = tmp_path / "output"
    output.mkdir()

    payload = driver.execute(prepared, output, _Runner())

    assert payload["status"] == "completed_incomplete"
    assert payload["terminal_type"] == "INCOMPLETE_COMPARATOR_EVIDENCE"
    assert payload["stop_stage"] == "retained"


def test_bilateral_protocol_failure_is_recorded_and_stops_later_stages(
    tmp_path, monkeypatch
):
    prepared = _prepared(tmp_path)
    main = _Protocol(
        [
            _result(
                ExperimentStage.SCREENING,
                gate="fail",
                failed_pairs=1,
                candidate_failed=1,
                champion_failed=1,
                shared=1,
                bilateral=1,
            )
        ]
    )
    retained = _Protocol([])
    monkeypatch.setattr(driver, "_make_protocols", lambda *_args: (main, retained))
    _install_decisions(monkeypatch, Decision.CONTINUE_EXPLORE)

    output = tmp_path / "output"
    output.mkdir()
    payload = driver.execute(prepared, output, _Runner())

    assert payload["terminal_type"] == "INCOMPLETE_COMPARATOR_EVIDENCE"
    assert payload["status"] == "completed_incomplete"
    assert payload["stop_stage"] == "expanded_screening"
    assert payload["stages"][0]["protocol"]["stats"]["shared_failed_pairs"] == 1
    assert payload["stages"][0]["protocol"]["stats"]["bilateral_failed_pairs"] == 1
    assert len(main.calls) == 2  # canary plus one formal Protocol call
    assert retained.calls == []
    assert not (output / "promoted_candidate").exists()


@pytest.mark.parametrize(
    ("stats", "scope"),
    [
        ({"failed_pairs": 1, "champion_failed": 1}, "champion"),
        ({"failed_pairs": 1, "champion_failed": 1, "shared": 1}, "shared"),
        (
            {
                "failed_pairs": 1,
                "candidate_failed": 1,
                "champion_failed": 1,
                "bilateral": 1,
            },
            "bilateral",
        ),
    ],
)
def test_comparator_failure_stops_before_decision(tmp_path, monkeypatch, stats, scope):
    prepared = _prepared(tmp_path)
    main = _Protocol([_result(ExperimentStage.SCREENING, gate="fail", **stats)])
    monkeypatch.setattr(driver, "_make_protocols", lambda *_args: (main, _Protocol([])))
    monkeypatch.setattr(
        driver,
        "_decide",
        lambda *_args, **_kwargs: pytest.fail(
            "Decision must not consume incomplete evidence"
        ),
    )
    output = tmp_path / f"output-{scope}"
    output.mkdir()

    payload = driver.execute(prepared, output, _Runner())

    assert payload["status"] == "completed_incomplete"
    assert payload["terminal_type"] == "INCOMPLETE_COMPARATOR_EVIDENCE"
    assert payload["stages"][0]["decision"] is None


def test_candidate_only_failure_remains_candidate_evidence_for_decision(
    tmp_path, monkeypatch
):
    prepared = _prepared(tmp_path)
    main = _Protocol(
        [
            _result(
                ExperimentStage.SCREENING,
                gate="fail",
                failed_pairs=1,
                candidate_failed=1,
            )
        ]
    )
    monkeypatch.setattr(driver, "_make_protocols", lambda *_args: (main, _Protocol([])))
    _install_decisions(monkeypatch, Decision.ABANDON)
    output = tmp_path / "output"
    output.mkdir()

    payload = driver.execute(prepared, output, _Runner())

    assert payload["status"] == "completed"
    assert payload["terminal_type"] == "NOT_CONFIRMED"
    assert payload["stages"][0]["decision"] == Decision.ABANDON.value


def test_strict_canary_comparator_failure_is_incomplete_not_candidate_negative(
    tmp_path, monkeypatch
):
    prepared = _prepared(tmp_path)

    class IncompleteCanaryProtocol(_Protocol):
        def run_canary(self, *_args, **_kwargs):
            return CanaryResult(
                False,
                reason="champion failed",
                failure_category="incomplete_evidence",
                details={"pair_failure_scope": "champion"},
            )

    main = IncompleteCanaryProtocol([])
    monkeypatch.setattr(driver, "_make_protocols", lambda *_args: (main, _Protocol([])))
    monkeypatch.setattr(
        driver,
        "_decide",
        lambda *_args, **_kwargs: pytest.fail("Decision must not run after canary"),
    )
    output = tmp_path / "output"
    output.mkdir()

    payload = driver.execute(prepared, output, _Runner())

    assert payload["status"] == "completed_incomplete"
    assert payload["terminal_type"] == "INCOMPLETE_COMPARATOR_EVIDENCE"


def test_fresh_copy_runner_returns_single_arm_failure_to_protocol(tmp_path):
    source = tmp_path / "source"
    _write_source(source, local_search="VALUE = 1\n")
    instance = source / "case.json"
    instance.write_text("{}\n")
    failure = RunResult(
        success=False,
        exit_code=1,
        stdout="",
        stderr="failed",
        elapsed_ms=2,
        error_category="crash",
    )

    class Delegate:
        def run_solver(self, **kwargs):
            assert Path(kwargs["workdir"]) != source
            return failure

        def terminate_active_processes(self, *, reason="shutdown"):
            del reason
            return 0

    output = tmp_path / "output"
    output.mkdir()
    runner = driver.FreshCopyRunner(
        output,
        _envelope(),
        delegate=Delegate(),
    )
    result = runner.run_solver(
        workdir=str(source),
        instance_path=str(instance),
        seed=1,
        time_limit_sec=10,
        registry_path=str(source / "registry.yaml"),
        selected_surface="solver_design",
    )

    assert result is failure
    assert list((output / "subject_workspaces").iterdir()) == []


def test_expanded_shape_and_all_stage_disjointness_are_preflight_requirements():
    protocol = SimpleNamespace(
        screening=SimpleNamespace(
            n_cases_modify=1,
            n_cases_create=1,
            n_seeds=1,
            expand_to_modify=2,
            expand_to_create=2,
            expand_n_seeds=2,
            require_expanded_for_pass=True,
        ),
        validation=SimpleNamespace(n_cases=1, n_seeds=1, expand_to=1),
        frozen=SimpleNamespace(n_cases=1, n_seeds=1),
    )
    driver.validate_population_shape(
        protocol,
        _manifest(),
        _seeds(),
        SimpleNamespace(screening=[], validation=[], frozen=["retained"], canary=[]),
        SimpleNamespace(screening=[], validation=[], frozen=[17], canary=[]),
    )

    protocol.screening.n_cases_modify = 2
    with pytest.raises(driver.PrepError, match="strictly grow"):
        driver.validate_population_shape(
            protocol,
            _manifest(),
            _seeds(),
            SimpleNamespace(
                screening=[], validation=[], frozen=["retained"], canary=[]
            ),
            SimpleNamespace(screening=[], validation=[], frozen=[17], canary=[]),
        )


def test_resource_envelope_is_derived_from_the_declared_matrix():
    policy = SimpleNamespace(
        resolve=lambda **kwargs: 20 if "screen" in kwargs["case_path"] else 10
    )
    config = SimpleNamespace(runtime=SimpleNamespace(time_limits=policy))
    envelope = driver.build_resource_envelope(
        config,
        _manifest(),
        _seeds(),
        SimpleNamespace(frozen=["retained"]),
        SimpleNamespace(frozen=[17]),
        fallback_time_limit_sec=10,
        timeout_guard_sec=5,
        outer_hardwall_sec=400,
        memory_mb=2048,
    )

    assert envelope.max_solver_subprocesses == 16
    assert envelope.nominal_subject_seconds == 240
    assert envelope.guarded_subject_seconds == 320
    assert envelope.max_time_limit_sec == 20
    assert envelope.fallback_time_limit_sec == 10
    assert envelope.memory_mb == 2048


def test_protocol_uses_the_same_nondefault_fallback_as_the_resource_envelope(
    tmp_path, monkeypatch
):
    prepared = _prepared(tmp_path)
    prepared = driver.replace(
        prepared,
        envelope=driver.replace(prepared.envelope, fallback_time_limit_sec=17),
        protocol_config=SimpleNamespace(
            with_problem_measurement=lambda *_args, **_kwargs: "config"
        ),
        bridge=SimpleNamespace(
            problem_spec="problem",
            metric_specs="metrics",
            objective_policy="objective",
        ),
    )
    captured = {}

    class Protocol:
        def __init__(self, *_args, **kwargs):
            captured.update(kwargs)

        def set_problem_adapter(self, adapter):
            captured["adapter"] = adapter

    monkeypatch.setattr(driver, "ExperimentProtocol", Protocol)
    monkeypatch.setattr(driver, "SplitManager", lambda value: value)
    monkeypatch.setattr(driver, "SeedLedger", lambda value: value)

    driver._make_protocol(prepared, _Runner(), tmp_path, retained=False)

    assert captured["time_limit_sec"] == 17


def test_runner_budget_stops_before_an_extra_delegate_dispatch(tmp_path):
    source = tmp_path / "source"
    _write_source(source, local_search="VALUE = 1\n")
    instance = source / "case.json"
    instance.write_text("{}\n")
    calls = 0

    class Delegate:
        def run_solver(self, **_kwargs):
            nonlocal calls
            calls += 1
            return RunResult(True, 0, "", "", 1)

        def terminate_active_processes(self, *, reason="shutdown"):
            del reason
            return 0

    envelope = driver.ResourceEnvelope(1, 10, 25, 10, 15, 100, 10, 4096)
    output = tmp_path / "output"
    output.mkdir()
    runner = driver.FreshCopyRunner(output, envelope, delegate=Delegate())
    kwargs = {
        "workdir": str(source),
        "instance_path": str(instance),
        "seed": 1,
        "time_limit_sec": 10,
        "registry_path": str(source / "registry.yaml"),
    }
    runner.run_solver(**kwargs)
    with pytest.raises(driver.ScientificTerminal, match="resource envelope"):
        runner.run_solver(**kwargs)
    assert calls == 1


def test_hardwall_maps_alarm_to_typed_interrupt(monkeypatch):
    handlers = {}
    monkeypatch.setattr(signal, "getsignal", lambda _signum: "previous")
    monkeypatch.setattr(
        signal,
        "signal",
        lambda signum, handler: handlers.__setitem__(signum, handler),
    )
    monkeypatch.setattr(signal, "setitimer", lambda *_args: None)

    with pytest.raises(driver.Interrupted) as caught, driver.hardwall(5):
        handlers[signal.SIGALRM](signal.SIGALRM, None)
    assert caught.value.code == "OUTER_HARDWALL"


def test_runner_cleans_private_copy_when_interrupted(tmp_path):
    source = tmp_path / "source"
    _write_source(source, local_search="VALUE = 1\n")
    instance = source / "case.json"
    instance.write_text("{}\n")

    class Delegate:
        def run_solver(self, **_kwargs):
            raise driver.Interrupted("INTERRUPTED")

        def terminate_active_processes(self, *, reason="shutdown"):
            del reason
            return 0

    output = tmp_path / "output"
    output.mkdir()
    runner = driver.FreshCopyRunner(output, _envelope(), delegate=Delegate())
    with pytest.raises(driver.Interrupted):
        runner.run_solver(
            workdir=str(source),
            instance_path=str(instance),
            seed=1,
            time_limit_sec=10,
            registry_path=str(source / "registry.yaml"),
        )
    assert list((output / "subject_workspaces").iterdir()) == []


def test_main_writes_typed_terminal_and_never_reuses_output(tmp_path, monkeypatch):
    prepared = _prepared(tmp_path)
    monkeypatch.setattr(driver, "prepare", lambda **_kwargs: prepared)
    monkeypatch.setattr(driver, "FreshCopyRunner", lambda *_args, **_kwargs: _Runner())

    @contextmanager
    def no_hardwall(_seconds):
        yield

    monkeypatch.setattr(driver, "hardwall", no_hardwall)
    monkeypatch.setattr(
        driver,
        "execute",
        lambda *_args: (_ for _ in ()).throw(
            driver.ScientificTerminal("LOCAL_TYPED_STOP", "stopped")
        ),
    )
    output = tmp_path / "fresh-output"
    argv = [
        "--label",
        "test",
        "--baseline-source",
        "baseline",
        "--candidate-source",
        "candidate",
        "--problem-spec",
        "problem.yaml",
        "--protocol",
        "protocol.yaml",
        "--split",
        "split.yaml",
        "--seeds",
        "seeds.yaml",
        "--retained-split",
        "retained-split.yaml",
        "--retained-seeds",
        "retained-seeds.yaml",
        "--changed-file",
        "one.py",
        "--selected-surface",
        "solver_design",
        "--outer-hardwall-sec",
        "600",
        "--output-dir",
        str(output),
    ]

    assert driver.main(argv) == 2
    terminal = json.loads((output / "terminal.json").read_text())
    assert terminal["terminal_type"] == "LOCAL_TYPED_STOP"
    assert driver.main(argv) == 2
    assert json.loads((output / "terminal.json").read_text()) == terminal


def test_input_write_failure_after_output_creation_gets_typed_terminal(
    tmp_path, monkeypatch
):
    prepared = _prepared(tmp_path)
    monkeypatch.setattr(driver, "prepare", lambda **_kwargs: prepared)
    original_dump = driver.json.dump
    writes = 0

    def fail_input_once(payload, handle, **kwargs):
        nonlocal writes
        writes += 1
        if writes == 1:
            raise OSError("input write failed")
        return original_dump(payload, handle, **kwargs)

    monkeypatch.setattr(driver.json, "dump", fail_input_once)
    output = tmp_path / "fresh-output"
    argv = [
        "--label",
        "test",
        "--baseline-source",
        "baseline",
        "--candidate-source",
        "candidate",
        "--problem-spec",
        "problem.yaml",
        "--protocol",
        "protocol.yaml",
        "--split",
        "split.yaml",
        "--seeds",
        "seeds.yaml",
        "--retained-split",
        "retained-split.yaml",
        "--retained-seeds",
        "retained-seeds.yaml",
        "--changed-file",
        "one.py",
        "--selected-surface",
        "solver_design",
        "--outer-hardwall-sec",
        "600",
        "--output-dir",
        str(output),
    ]

    assert driver.main(argv) == 2
    terminal = json.loads((output / "terminal.json").read_text())
    assert terminal["terminal_type"] == "UNHANDLED_EXCEPTION"
    assert writes == 2
    assert not (output / ".input.json.tmp").exists()
    driver._make_dirs_writable(output / "input_snapshots")


def test_hardwall_covers_private_source_snapshot(tmp_path, monkeypatch):
    prepared = _prepared(tmp_path)
    monkeypatch.setattr(driver, "prepare", lambda **_kwargs: prepared)
    monkeypatch.setattr(
        driver,
        "_snapshot_prepared_sources",
        lambda *_args: (_ for _ in ()).throw(driver.Interrupted("OUTER_HARDWALL")),
    )
    output = tmp_path / "fresh-output"
    argv = [
        "--label",
        "test",
        "--baseline-source",
        "baseline",
        "--candidate-source",
        "candidate",
        "--problem-spec",
        "problem.yaml",
        "--protocol",
        "protocol.yaml",
        "--split",
        "split.yaml",
        "--seeds",
        "seeds.yaml",
        "--retained-split",
        "retained-split.yaml",
        "--retained-seeds",
        "retained-seeds.yaml",
        "--changed-file",
        "one.py",
        "--selected-surface",
        "solver_design",
        "--outer-hardwall-sec",
        "600",
        "--output-dir",
        str(output),
    ]

    assert driver.main(argv) == 130
    terminal = json.loads((output / "terminal.json").read_text())
    assert terminal["status"] == "interrupted"
    assert terminal["terminal_type"] == "OUTER_HARDWALL"
