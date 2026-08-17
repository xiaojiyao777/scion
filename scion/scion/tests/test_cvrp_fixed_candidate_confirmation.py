from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
from pathlib import Path
from types import SimpleNamespace

import pytest
import run_cvrp_fixed_candidate_confirmation as driver
from scion.config.problem import ProtocolConfig
from scion.core.decision import DecisionEngine
from scion.core.features import SafeFeatureExtractor
from scion.core.models import (
    CanaryResult,
    EvalStats,
    ExperimentStage,
    ProtocolResult,
    RunResult,
    SolverOutput,
)


def _run_result(*, success: bool = True, fleet: float = 0.0) -> RunResult:
    return RunResult(
        success=success,
        exit_code=0 if success else 1,
        stdout="",
        stderr="" if success else "failed",
        elapsed_ms=1,
        output=(
            SolverOutput(
                objective={"fleet_violation": fleet, "total_distance": 10.0},
                feasible=True,
                runtime={},
            )
            if success
            else None
        ),
        error_category=None if success else "crash",
    )


def _population() -> dict:
    limits = (30, 30, 45, 45, 60, 90, 30, 30, 30, 60, 90, 120)
    stages = {}
    for stage_index, stage in enumerate(
        ("screening", "validation", "frozen", "retained")
    ):
        stages[stage] = {
            "cases": [
                {"path": f"{stage}/case-{index}.vrp", "time_limit_sec": limit}
                for index, limit in enumerate(limits)
            ],
            "seeds": list(range(100 + stage_index * 8, 108 + stage_index * 8)),
        }
    stages["canary"] = {
        "cases": [{"path": "controlled/data/synthetic_controlled_canary_5.vrp"}],
        "seeds": [2267],
        "time_limit_sec": 10,
    }
    return stages


def _prepared(tmp_path: Path) -> driver.Prepared:
    b0 = tmp_path / "b0"
    candidate = tmp_path / "candidate"
    for root, marker in ((b0, "a"), (candidate, "b")):
        (root / "controlled" / "data").mkdir(parents=True)
        (root / "controlled" / "data" / "synthetic_controlled_canary_5.vrp").write_text(
            marker
        )
        (root / "solver.py").write_text(marker)
    config = {
        "schema_version": driver.SCHEMA,
        "label": "test",
        "selected_surface": "solver_design",
        "population": _population(),
        "order": {
            "block_ordinals": {
                "initial_screening": 0,
                "expanded_screening": 1,
                "validation": 2,
                "frozen": 3,
                "retained": 4,
            }
        },
        "claim_boundary": {"execution_replication_independent": None},
        "historical_validation": {
            "contract": True,
            "verification": True,
            "current_contract_calls": 0,
            "current_verification_calls": 0,
        },
    }
    return driver.Prepared(
        config=config,
        config_path=tmp_path / "population.json",
        b0=b0,
        candidate=candidate,
        data_root=tmp_path / "data",
        protocol_path=tmp_path / "protocol.yaml",
        sources={
            "b0": {"sha256": "0" * 64, "file_count": 2, "total_bytes": 2},
            "candidate": {"sha256": "1" * 64, "file_count": 2, "total_bytes": 2},
        },
        bridge=SimpleNamespace(problem_spec=None),
        adapter=None,
    )


def _protocol_result(stage: ExperimentStage, gate: str, reason: str) -> ProtocolResult:
    n_cases = 8 if gate == "expand" else 12
    pairs = n_cases * (4 if gate == "expand" else 8)
    return ProtocolResult(
        stage=stage,
        stats=EvalStats(
            n_cases=n_cases,
            wins=n_cases,
            losses=0,
            ties=0,
            win_rate=1.0,
            median_delta=1.0,
            ci_low=0.5,
            ci_high=1.5,
            total_pairs=pairs,
            attempted_pairs=pairs,
            valid_pairs=pairs,
        ),
        gate_outcome=gate,
        reason_codes=(reason,),
        exposed_summary="",
        raw_metrics_ref=f"/{stage.value}.json",
        case_ids=tuple(f"case-{index}" for index in range(n_cases)),
        seed_set=(1,),
    )


class _Protocol:
    def __init__(self, results: list[ProtocolResult]) -> None:
        self.results = list(results)
        self.calls = []

    def run_experiment(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.results.pop(0)


class _CountedRunner:
    def __init__(self) -> None:
        self.snapshots = []
        self.terminated = []

    def counters(self):
        return {
            "solver_subprocesses": 840,
            "nominal_subject_seconds": 45_200,
            "positive_hard_timeout_seconds": 57_800,
        }

    def register_snapshot(self, path):
        self.snapshots.append(Path(path))

    def terminate_active_processes(self, *, reason="shutdown"):
        self.terminated.append(reason)
        return 0


class _Decisions:
    def __init__(self) -> None:
        self.delegate = DecisionEngine(ProtocolConfig())
        self.calls = 0

    def decide(self, features):
        self.calls += 1
        return self.delegate.decide(features)


def _runtime() -> driver.Runtime:
    protocol = _Protocol(
        [
            _protocol_result(ExperimentStage.SCREENING, "expand", "SCREENING_EXPAND"),
            _protocol_result(ExperimentStage.SCREENING, "pass", "SCREENING_PASS"),
            _protocol_result(ExperimentStage.VALIDATION, "pass", "VALIDATION_PASS"),
            _protocol_result(ExperimentStage.FROZEN, "pass", "FROZEN_PASS"),
        ]
    )
    retained = _Protocol(
        [_protocol_result(ExperimentStage.FROZEN, "pass", "FROZEN_PASS")]
    )
    return driver.Runtime(
        protocol,
        retained,
        _CountedRunner(),
        SafeFeatureExtractor(),
        _Decisions(),
    )


def test_source_summary_uses_literal_backslash_framing(tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "a.txt").write_bytes(b"abc")
    file_sha = hashlib.sha256(b"abc").hexdigest()
    expected = hashlib.sha256(f"a.txt\\0{file_sha}\\03\\n".encode("ascii")).hexdigest()

    assert driver.source_summary(root) == {
        "sha256": expected,
        "file_count": 1,
        "total_bytes": 3,
    }


def test_check_mode_creates_no_output_or_runtime(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    prepared = _prepared(tmp_path)
    output = tmp_path / "must-not-exist"
    monkeypatch.setattr(driver, "prepare", lambda *_: prepared)
    monkeypatch.setattr(
        driver,
        "build_runtime",
        lambda *_: pytest.fail("--check must not build a runtime"),
    )

    code = driver.main(
        [
            "--config",
            str(tmp_path / "config.json"),
            "--input-root",
            str(tmp_path),
            "--output-dir",
            str(output),
            "--check",
        ]
    )

    assert code == 0
    assert not output.exists()
    assert json.loads(capsys.readouterr().out)["solver_subprocesses"] == 0


def test_preparse_uses_adapter_once_per_formal_case(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path)

    class Adapter:
        def __init__(self):
            self.paths = []

        def load_instance(self, path):
            self.paths.append(path)
            return object()

    adapter = Adapter()
    driver.preparse_formal_cases(adapter, prepared.config, tmp_path)

    assert len(adapter.paths) == 48
    assert len(set(adapter.paths)) == 48


def test_strict_canary_is_b0_first_and_stops_before_candidate(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path)
    temp_root = tmp_path / "work"
    temp_root.mkdir()

    class Delegate:
        def __init__(self):
            self.calls = []

        def run_solver(self, **kwargs):
            self.calls.append(kwargs)
            return _run_result(success=False)

        def terminate_active_processes(self, **_kwargs):
            return 0

    delegate = Delegate()
    runner = driver.FreshRunner(delegate, temp_root, prepared)
    protocol = SimpleNamespace(runner=runner)

    with pytest.raises(driver.Terminal, match="b0 subject failed"):
        driver.strict_canary(protocol, prepared)

    assert len(delegate.calls) == 1
    assert not list(temp_root.iterdir())


def test_strict_canary_compares_fleet_only_after_both_valid_arms(
    tmp_path: Path,
) -> None:
    prepared = _prepared(tmp_path)

    class Runner:
        def __init__(self):
            self.workdirs = []

        def run_solver(self, **kwargs):
            self.workdirs.append(Path(kwargs["workdir"]))
            return _run_result(fleet=0.0 if len(self.workdirs) == 1 else 1.0)

    runner = Runner()
    with pytest.raises(driver.Terminal, match="regressed fleet_violation"):
        driver.strict_canary(SimpleNamespace(runner=runner), prepared)

    assert runner.workdirs == [prepared.b0, prepared.candidate]


def test_formal_failure_stops_next_subject_and_cleans_readonly_copies(
    tmp_path: Path,
) -> None:
    prepared = _prepared(tmp_path)
    case = tmp_path / "case.vrp"
    case.write_text("case")
    temp_root = tmp_path / "work"
    temp_root.mkdir()
    original_modes = {}
    for root in (prepared.b0, prepared.candidate):
        for path in root.rglob("*"):
            if path.is_file():
                os.chmod(path, 0o400)
        os.chmod(root, 0o500)
        original_modes[root] = root.stat().st_mode & 0o777

    class Delegate:
        def __init__(self):
            self.count = 0

        def run_solver(self, **_kwargs):
            self.count += 1
            return _run_result(success=self.count == 1)

        def terminate_active_processes(self, **_kwargs):
            return 0

    delegate = Delegate()
    runner = driver.FreshRunner(delegate, temp_root, prepared)

    def formal_loop():
        for workspace in (prepared.b0, prepared.candidate, prepared.b0):
            runner.run_solver(
                str(workspace), str(case), 1, 30, str(workspace / "registry.yaml")
            )

    try:
        with pytest.raises(driver.Terminal, match="candidate subject failed"):
            formal_loop()
        assert delegate.count == 2
        assert not list(temp_root.iterdir())
        assert all(
            (root.stat().st_mode & 0o777) == mode
            for root, mode in original_modes.items()
        )
    finally:
        for root in (prepared.b0, prepared.candidate):
            os.chmod(root, 0o700)
            for path in root.rglob("*"):
                if path.is_dir():
                    os.chmod(path, 0o700)
                else:
                    os.chmod(path, 0o600)


def test_execute_uses_four_decisions_then_snapshot_and_retained(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path)
    runtime = _runtime()
    output = tmp_path / "output"
    output.mkdir()
    canary_calls = []

    def canary(_protocol, _prepared):
        assert not (output / "promoted_candidate_snapshot").exists()
        canary_calls.append("b0_then_candidate")
        return CanaryResult(True, details={"order": "b0_then_candidate"})

    terminal = driver.execute(prepared, output, runtime, canary=canary)

    assert terminal["terminal_type"] == "PROMOTED_RETAINED"
    assert terminal["claims"]["execution_replication_independent"] is None
    assert canary_calls == ["b0_then_candidate"] * 4
    assert len(runtime.protocol.calls) == 4
    assert len(runtime.retained_protocol.calls) == 1
    assert runtime.decisions.calls == 4
    specs = [call[1]["paired_execution"] for call in runtime.protocol.calls]
    specs.append(runtime.retained_protocol.calls[0][1]["paired_execution"])
    assert [spec.block_ordinal for spec in specs] == [0, 1, 2, 3, 4]
    assert [call[1]["expand"] for call in runtime.protocol.calls] == [
        False,
        True,
        False,
        False,
    ]
    assert all(call[1]["expand_round"] == 1 for call in runtime.protocol.calls)
    assert all(
        call[1]["selected_surface"] == "solver_design"
        for call in runtime.protocol.calls
    )
    for block, spec in zip(
        ("initial_screening", "expanded_screening", "validation", "frozen", "retained"),
        specs,
        strict=True,
    ):
        population_name = "screening" if "screening" in block else block
        population = prepared.stage(population_name)
        assert spec.block_id == block
        assert spec.candidate_ordinal == 0
        assert spec.case_ordinals == {
            case["path"]: index for index, case in enumerate(population["cases"])
        }
        assert spec.seed_ordinals == {
            seed: index for index, seed in enumerate(population["seeds"])
        }
    assert ["AB" if spec.block_ordinal % 2 == 0 else "BA" for spec in specs] == [
        "AB",
        "BA",
        "AB",
        "BA",
        "AB",
    ]
    snapshot = output / "promoted_candidate_snapshot"
    assert runtime.runner.snapshots == [snapshot]
    assert (snapshot / "solver.py").read_bytes() == (
        prepared.candidate / "solver.py"
    ).read_bytes()


@pytest.mark.parametrize(
    ("position", "gate", "reason"),
    [
        (0, "fail", "SCREENING_FAIL_WIN_RATE"),
        (1, "fail", "SCREENING_FAIL_WIN_RATE"),
        (2, "fail", "VALIDATION_FAIL_WIN_RATE"),
        (3, "fail", "FROZEN_FAIL_UNCLEAR"),
    ],
)
def test_each_unexpected_decision_stops_all_later_work(
    tmp_path: Path,
    position: int,
    gate: str,
    reason: str,
) -> None:
    prepared = _prepared(tmp_path)
    runtime = _runtime()
    stage = runtime.protocol.results[position].stage
    runtime.protocol.results[position] = _protocol_result(stage, gate, reason)
    output = tmp_path / "output"
    output.mkdir()
    canary_calls = []

    with pytest.raises(driver.Terminal):
        driver.execute(
            prepared,
            output,
            runtime,
            canary=lambda *_: (
                canary_calls.append(True)
                or CanaryResult(True, details={"order": "b0_then_candidate"})
            ),
        )

    assert len(runtime.protocol.calls) == position + 1
    assert len(canary_calls) == position + 1
    assert runtime.decisions.calls == position + 1
    assert not runtime.retained_protocol.calls
    assert not (output / "promoted_candidate_snapshot").exists()


def test_mid_subject_terminal_preserves_only_completed_block_trace(
    tmp_path: Path,
) -> None:
    prepared = _prepared(tmp_path)
    runtime = _runtime()
    original = runtime.protocol.run_experiment

    def fail_second(*args, **kwargs):
        if len(runtime.protocol.calls) == 1:
            raise driver.Terminal("CANDIDATE_SUBJECT_VETO", "failed subject")
        return original(*args, **kwargs)

    runtime.protocol.run_experiment = fail_second
    output = tmp_path / "output"
    output.mkdir()

    with pytest.raises(driver.Terminal) as caught:
        driver.execute(
            prepared,
            output,
            runtime,
            canary=lambda *_: CanaryResult(True, details={}),
        )

    completed = caught.value.details["completed_trace"]
    assert [item["block"] for item in completed] == ["initial_screening"]


def test_retained_failure_is_terminal_after_snapshot_without_fifth_decision(
    tmp_path: Path,
) -> None:
    prepared = _prepared(tmp_path)
    runtime = _runtime()
    runtime.retained_protocol.results[0] = _protocol_result(
        ExperimentStage.FROZEN,
        "fail",
        "FROZEN_FAIL_UNCLEAR",
    )
    output = tmp_path / "output"
    output.mkdir()

    with pytest.raises(driver.Terminal, match="retained comparison did not pass"):
        driver.execute(
            prepared,
            output,
            runtime,
            canary=lambda *_: CanaryResult(True, details={}),
        )

    assert (output / "promoted_candidate_snapshot").is_dir()
    assert len(runtime.retained_protocol.calls) == 1
    assert runtime.decisions.calls == 4


def test_snapshot_one_byte_corruption_is_terminal(tmp_path: Path) -> None:
    source = tmp_path / "source"
    copied = tmp_path / "copied"
    source.mkdir()
    (source / "value.py").write_bytes(b"abc")
    shutil.copytree(source, copied)
    (copied / "value.py").write_bytes(b"abd")

    with pytest.raises(driver.Terminal, match="snapshot differs"):
        driver._exact_copy(source, copied)


def test_budget_and_population_mutations_reject_before_runtime(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path)
    budget_config = {
        "schema_version": driver.SCHEMA,
        "label": driver.LABEL,
        "selection_salt": f"{driver.LABEL}|population-v1",
        "source_digest_framing": driver.DIGEST_FRAMING,
        "selected_surface": "solver_design",
        "sources": driver.EXACT_SOURCES,
        "protocol_config": "subjects/b0/formal/protocol.yaml",
        "problem_spec": "subjects/b0/problem-v1.yaml",
        "data_root": "data",
        "order": driver.EXPECTED_ORDER,
        "claim_boundary": driver.EXPECTED_CLAIM_BOUNDARY,
        "historical_validation": {
            "contract": True,
            "verification": True,
            "source_relation": "same_exact_source",
            "current_contract_calls": 0,
            "current_verification_calls": 0,
        },
        "budgets": {**driver.EXPECTED_BUDGETS, "max_solver_subprocesses": 839},
    }
    with pytest.raises(driver.PrepError, match="execution budgets"):
        driver._validate_science(budget_config)

    budget_config["budgets"]["max_solver_subprocesses"] = 840
    budget_config["historical_validation"]["source_relation"] = "different_source"
    with pytest.raises(driver.PrepError, match="same exact source"):
        driver._validate_science(budget_config)

    budget_config["historical_validation"]["source_relation"] = "same_exact_source"
    budget_config["sources"] = {
        **driver.EXACT_SOURCES,
        "candidate": {**driver.EXACT_SOURCES["candidate"], "total_bytes": 1},
    }
    with pytest.raises(driver.PrepError, match="historically validated"):
        driver._validate_science(budget_config)

    budget_config["sources"] = driver.EXACT_SOURCES
    budget_config["order"] = {
        **driver.EXPECTED_ORDER,
        "block_ordinals": {**driver.EXPECTED_ORDER["block_ordinals"], "frozen": 4},
    }
    with pytest.raises(driver.PrepError, match="pair order"):
        driver._validate_science(budget_config)

    budget_config["order"] = driver.EXPECTED_ORDER
    budget_config["claim_boundary"] = {
        **driver.EXPECTED_CLAIM_BOUNDARY,
        "globally_case_unseen": True,
    }
    with pytest.raises(driver.PrepError, match="claim boundary"):
        driver._validate_science(budget_config)

    prepared.stage("screening")["cases"].pop()
    with pytest.raises(driver.PrepError, match="12 cases"):
        driver._validate_population(
            prepared.config,
            prepared.data_root,
            prepared.b0,
            prepared.candidate,
        )


def test_typed_decision_terminal_writes_atomic_terminal_without_snapshot(
    tmp_path: Path,
) -> None:
    prepared = _prepared(tmp_path)
    runtime = _runtime()
    runtime.protocol.results[0] = _protocol_result(
        ExperimentStage.SCREENING,
        "fail",
        "SCREENING_FAIL_WIN_RATE",
    )
    output = tmp_path / "one-shot-output"

    code, terminal = driver.run_once(
        prepared,
        output,
        runtime_builder=lambda *_: runtime,
        canary=lambda *_: CanaryResult(True, details={"order": "b0_then_candidate"}),
    )

    assert code == 2
    assert terminal["terminal_type"] == "INITIAL_SCREENING_CONTINUE_EXPLORE"
    assert json.loads((output / "terminal.json").read_text()) == terminal
    assert not (output / ".terminal.json.tmp").exists()
    assert not (output / "promoted_candidate_snapshot").exists()


def test_driver_has_no_current_gate_or_resume_path() -> None:
    source = Path(driver.__file__).read_text()
    assert "ContractGate" not in source
    assert "VerificationGate" not in source
    assert "PatchProposal" not in source
    assert "--resume" not in source


def test_hardwall_signal_uses_baseexception_and_keeps_typed_terminal() -> None:
    runner = _CountedRunner()

    with pytest.raises(driver.Interrupted) as caught, driver.hardwall(runner):
        signal.raise_signal(signal.SIGALRM)

    assert caught.value.args == ("OUTER_HARDWALL", "received SIGALRM")
    # A Python signal may arrive while LocalSubprocessRunner holds its ordinary
    # active-process lock.  The handler only unwinds; the runner kills its
    # current child on BaseException and run_once performs the outer cleanup.
    assert runner.terminated == []
    assert not issubclass(driver.Interrupted, Exception)


def test_interrupted_run_unwinds_before_outer_process_cleanup(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path)
    runtime = _runtime()

    code, terminal = driver.run_once(
        prepared,
        tmp_path / "interrupted-output",
        runtime_builder=lambda *_: runtime,
        canary=lambda *_: (_ for _ in ()).throw(
            driver.Interrupted("OUTER_HARDWALL", "received SIGALRM")
        ),
    )

    assert code == 130
    assert terminal["terminal_type"] == "OUTER_HARDWALL"
    assert runtime.runner.terminated == ["interrupted"]
