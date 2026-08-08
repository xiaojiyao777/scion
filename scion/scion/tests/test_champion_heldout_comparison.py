from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.core.champion_heldout_comparison import (
    MANIFEST_SCHEMA_VERSION,
    InfeasibleAsFailureRunner,
    build_champion_heldout_protocol,
    execute_champion_heldout_comparison,
)
from scion.core.models import (
    CanaryResult,
    EvalStats,
    ExperimentStage,
    ProtocolResult,
    RunResult,
    SolverOutput,
)
from scion.problem.spec import ObjectiveMetricSpec
from scion.protocol.experiment import ExperimentProtocol, SeedLedger, SplitManager
from scion.runtime.subprocess_runner import LocalSubprocessRunner


def test_manifest_runs_frozen_on_ordinary_copies_and_writes_group_and_summary(
    tmp_path: Path,
) -> None:
    candidate = _workspace(tmp_path / "source-candidate", marker="candidate")
    champion = _workspace(tmp_path / "source-champion", marker="champion")
    manifest = _manifest(tmp_path, candidate=candidate, champion=champion)
    protocols: list[_FakeProtocol] = []

    def factory(**kwargs: Any) -> _FakeProtocol:
        protocol = _FakeProtocol(metrics_dir=kwargs["metrics_dir"])
        protocols.append(protocol)
        return protocol

    summary_path = execute_champion_heldout_comparison(
        manifest,
        output_dir=tmp_path / "result",
        protocol_factory=factory,
    )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    group_path = Path(summary["groups"][0]["result_path"])
    group = json.loads(group_path.read_text(encoding="utf-8"))
    protocol = protocols[0]

    assert summary["group_count"] == 1
    assert summary["completed_group_count"] == 1
    assert summary["candidate_supported_group_count"] == 1
    assert summary["all_groups_supported"] is True
    assert group["workspace_mode"] == "ordinary_copy"
    assert group["canary_safety_diagnostic"]["passed"] is True
    assert group["formal"]["stage"] == "frozen"
    assert group["formal"]["stats"]["valid_pairs"] == 1
    assert group["supports_candidate"] is True
    assert [call[0] for call in protocol.calls] == ["canary", "canary", "formal"]
    assert protocol.calls[-1][1] is ExperimentStage.FROZEN
    candidate_copy = Path(group["candidate_workspace"])
    champion_copy = Path(group["champion_workspace"])
    assert candidate_copy != candidate
    assert champion_copy != champion
    assert (candidate_copy / "marker.txt").read_text(encoding="utf-8") == "candidate"
    assert (champion_copy / "marker.txt").read_text(encoding="utf-8") == "champion"
    assert candidate.joinpath("marker.txt").read_text(encoding="utf-8") == "candidate"


def test_canary_failure_marks_execution_invalid_and_skips_frozen(
    tmp_path: Path,
) -> None:
    candidate = _workspace(tmp_path / "candidate", marker="candidate")
    champion = _workspace(tmp_path / "champion", marker="champion")
    manifest = _manifest(tmp_path, candidate=candidate, champion=champion)
    protocol = _FakeProtocol(
        metrics_dir=tmp_path / "unused",
        canary_results=(False, True),
    )

    summary_path = execute_champion_heldout_comparison(
        manifest,
        output_dir=tmp_path / "result",
        protocol_factory=lambda **_: protocol,
    )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    group = json.loads(
        Path(summary["groups"][0]["result_path"]).read_text(encoding="utf-8")
    )
    assert [call[0] for call in protocol.calls] == ["canary", "canary"]
    assert group["status"] == "execution-invalid"
    assert group["canary_safety_diagnostic"]["passed"] is False
    assert group["formal"] == {
        "status": "not-run",
        "reason_code": "CANARY_SAFETY_VETO",
    }
    assert group["supports_candidate"] is False
    assert summary["execution_invalid_group_count"] == 1
    assert summary["completed_group_count"] == 0


def test_canary_error_marks_execution_invalid_and_skips_frozen(
    tmp_path: Path,
) -> None:
    candidate = _workspace(tmp_path / "candidate", marker="candidate")
    champion = _workspace(tmp_path / "champion", marker="champion")
    manifest = _manifest(tmp_path, candidate=candidate, champion=champion)
    protocol = _FakeProtocol(
        metrics_dir=tmp_path / "unused",
        canary_results=(RuntimeError("canary unavailable"), True),
    )

    summary_path = execute_champion_heldout_comparison(
        manifest,
        output_dir=tmp_path / "result",
        protocol_factory=lambda **_: protocol,
    )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    group = json.loads(
        Path(summary["groups"][0]["result_path"]).read_text(encoding="utf-8")
    )
    assert [call[0] for call in protocol.calls] == ["canary", "canary"]
    assert group["status"] == "execution-invalid"
    assert group["canary_safety_diagnostic"]["candidate"]["status"] == "error"
    assert group["formal"]["status"] == "not-run"
    assert group["supports_candidate"] is False


def test_incomplete_frozen_pairs_cannot_support_candidate(tmp_path: Path) -> None:
    candidate = _workspace(tmp_path / "candidate", marker="candidate")
    champion = _workspace(tmp_path / "champion", marker="champion")
    manifest = _manifest(tmp_path, candidate=candidate, champion=champion)
    protocol = _FakeProtocol(
        metrics_dir=tmp_path / "unused",
        incomplete_formal=True,
    )

    summary_path = execute_champion_heldout_comparison(
        manifest,
        output_dir=tmp_path / "result",
        protocol_factory=lambda **_: protocol,
    )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    group = json.loads(
        Path(summary["groups"][0]["result_path"]).read_text(encoding="utf-8")
    )
    assert group["formal"]["gate_outcome"] == "pass"
    assert group["formal"]["stats"]["attempted_pairs"] == 0
    assert group["supports_candidate"] is False
    assert summary["all_groups_supported"] is False


@pytest.mark.parametrize(
    "forged_formal",
    ["wrong_n_cases", "wrong_case_sum", "wrong_pair_sum"],
)
def test_forged_frozen_statistics_cannot_support_candidate(
    tmp_path: Path,
    forged_formal: str,
) -> None:
    candidate = _workspace(tmp_path / "candidate", marker="candidate")
    champion = _workspace(tmp_path / "champion", marker="champion")
    manifest = _manifest(tmp_path, candidate=candidate, champion=champion)
    protocol = _FakeProtocol(
        metrics_dir=tmp_path / "unused",
        forged_formal=forged_formal,
    )

    summary_path = execute_champion_heldout_comparison(
        manifest,
        output_dir=tmp_path / "result",
        protocol_factory=lambda **_: protocol,
    )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    group = json.loads(
        Path(summary["groups"][0]["result_path"]).read_text(encoding="utf-8")
    )
    assert group["formal"]["gate_outcome"] == "pass"
    assert group["supports_candidate"] is False
    assert summary["all_groups_supported"] is False


def test_infeasible_output_becomes_explicit_failure_of_the_executed_side() -> None:
    infeasible = RunResult(
        success=True,
        exit_code=0,
        stdout="",
        stderr="",
        elapsed_ms=3,
        output=SolverOutput(objective={"cost": 1}, feasible=False),
    )
    runner = InfeasibleAsFailureRunner(_ResultRunner(infeasible))

    result = runner.run_solver(
        workdir="/candidate",
        instance_path="case.json",
        seed=7,
        time_limit_sec=1,
        registry_path="/candidate/registry.yaml",
    )

    assert result.success is False
    assert result.error_category == "infeasible_solution"
    assert result.output is not None
    assert result.output.feasible is False


def _objective_run(objective: dict[str, Any]) -> RunResult:
    return RunResult(
        success=True,
        exit_code=0,
        stdout="",
        stderr="",
        elapsed_ms=1,
        output=SolverOutput(objective=objective, feasible=True),
    )


@pytest.mark.parametrize(
    ("run_result", "error_category"),
    [
        (
            RunResult(
                success=True,
                exit_code=0,
                stdout="",
                stderr="",
                elapsed_ms=1,
                output=None,
            ),
            "missing_solver_output",
        ),
        (_objective_run({}), "missing_objective_metric"),
        (_objective_run({"cost": "bad"}), "invalid_objective_metric"),
        (_objective_run({"cost": True}), "invalid_objective_metric"),
        (_objective_run({"cost": float("nan")}), "nonfinite_objective_metric"),
        (_objective_run({"cost": float("inf")}), "nonfinite_objective_metric"),
    ],
)
def test_declared_objective_output_failures_are_explicit(
    run_result: RunResult,
    error_category: str,
) -> None:
    runner = InfeasibleAsFailureRunner(
        _ResultRunner(run_result),
        metric_names=("cost",),
    )

    result = runner.run_solver(
        workdir="/candidate",
        instance_path="case.json",
        seed=7,
        time_limit_sec=1,
        registry_path="/candidate/registry.yaml",
    )

    assert result.success is False
    assert result.error_category == error_category


@pytest.mark.parametrize(
    ("results", "candidate_failures", "champion_failures"),
    [
        ((True, False), 1, 0),
        ((False, True), 0, 1),
    ],
)
def test_frozen_protocol_counts_infeasible_as_failure_of_that_side(
    tmp_path: Path,
    results: tuple[bool, bool],
    candidate_failures: int,
    champion_failures: int,
) -> None:
    candidate = _formal_workspace(tmp_path / "candidate")
    champion = _formal_workspace(tmp_path / "champion")
    delegate = _SequenceRunner([_run(feasible=value) for value in results])
    protocol = ExperimentProtocol(
        protocol_config=ProtocolConfig(
            frozen={"n_cases": 1, "n_seeds": 1},
        ),
        split_manager=SplitManager(
            SplitManifest(frozen=["case.json"]),
        ),
        seed_ledger=SeedLedger(
            SeedLedgerConfig(frozen=[3]),
        ),
        runner=InfeasibleAsFailureRunner(delegate),
        time_limit_sec=1,
        metrics_dir=str(tmp_path / "metrics"),
        metric_specs=(
            ObjectiveMetricSpec(
                name="cost",
                direction="minimize",
                priority=1,
            ),
        ),
        require_metric_specs=True,
        champion_result_cache_enabled=False,
    )

    result = protocol.run_experiment(
        ExperimentStage.FROZEN,
        str(candidate),
        str(champion),
        "modify",
    )

    assert result.stats.failed_pairs == 1
    assert result.stats.candidate_failed_pairs == candidate_failures
    assert result.stats.champion_failed_pairs == champion_failures
    assert result.gate_outcome == "fail"


@pytest.mark.parametrize("invalid_side", ["candidate", "champion"])
@pytest.mark.parametrize(
    "invalid_result",
    [
        _objective_run({}),
        _objective_run({"cost": "bad"}),
        _objective_run({"cost": float("nan")}),
    ],
)
def test_frozen_protocol_counts_declared_output_failure_on_that_side(
    tmp_path: Path,
    invalid_side: str,
    invalid_result: RunResult,
) -> None:
    candidate = _formal_workspace(tmp_path / "candidate")
    champion = _formal_workspace(tmp_path / "champion")
    valid = _objective_run({"cost": 1.0})
    results = (
        [invalid_result, valid]
        if invalid_side == "champion"
        else [valid, invalid_result]
    )
    protocol = ExperimentProtocol(
        protocol_config=ProtocolConfig(frozen={"n_cases": 1, "n_seeds": 1}),
        split_manager=SplitManager(SplitManifest(frozen=["case.json"])),
        seed_ledger=SeedLedger(SeedLedgerConfig(frozen=[3])),
        runner=InfeasibleAsFailureRunner(
            _SequenceRunner(results),
            metric_names=("cost",),
        ),
        time_limit_sec=1,
        metrics_dir=str(tmp_path / "metrics"),
        metric_specs=(
            ObjectiveMetricSpec(name="cost", direction="minimize", priority=1),
        ),
        require_metric_specs=True,
        champion_result_cache_enabled=False,
    )

    result = protocol.run_experiment(
        ExperimentStage.FROZEN,
        str(candidate),
        str(champion),
        "modify",
    )

    assert result.stats.failed_pairs == 1
    assert result.stats.candidate_failed_pairs == (invalid_side == "candidate")
    assert result.stats.champion_failed_pairs == (invalid_side == "champion")
    assert result.gate_outcome == "fail"


def test_production_builder_requires_and_selects_exact_12_by_3_frozen_matrix(
    tmp_path: Path,
) -> None:
    repository = Path(__file__).resolve().parents[2]
    problem_dir = repository / "problems" / "warehouse_delivery"
    protocol_path, split_path, seeds_path, cases, seeds = _matrix_configs(tmp_path)

    protocol = build_champion_heldout_protocol(
        problem_yaml_path=problem_dir / "problem-v1.yaml",
        protocol_path=protocol_path,
        split_path=split_path,
        seeds_path=seeds_path,
        metrics_dir=tmp_path / "metrics",
        time_limit_sec=3,
    )

    assert isinstance(protocol, ExperimentProtocol)
    assert protocol._champion_result_cache_enabled is False
    assert protocol._champion_result_cache is None
    assert isinstance(protocol.runner, InfeasibleAsFailureRunner)
    assert isinstance(protocol.runner.delegate, LocalSubprocessRunner)
    assert protocol.runner.metric_names == ("subcategory_splits", "total_cost")
    assert protocol.config.frozen.n_cases == 12
    assert protocol.config.frozen.n_seeds == 3
    assert protocol._select_cases(ExperimentStage.FROZEN, "modify", 0) == cases
    assert protocol._select_seeds(ExperimentStage.FROZEN) == seeds


@pytest.mark.parametrize(
    ("configured_cases", "configured_seeds"),
    [(4, 3), (12, 2)],
)
def test_production_builder_rejects_truncated_frozen_matrix(
    tmp_path: Path,
    configured_cases: int,
    configured_seeds: int,
) -> None:
    repository = Path(__file__).resolve().parents[2]
    problem_dir = repository / "problems" / "warehouse_delivery"
    protocol_path, split_path, seeds_path, _, _ = _matrix_configs(
        tmp_path,
        configured_cases=configured_cases,
        configured_seeds=configured_seeds,
    )

    with pytest.raises(ValueError, match="complete frozen matrix"):
        build_champion_heldout_protocol(
            problem_yaml_path=problem_dir / "problem-v1.yaml",
            protocol_path=protocol_path,
            split_path=split_path,
            seeds_path=seeds_path,
            metrics_dir=tmp_path / "metrics",
            time_limit_sec=3,
        )


class _FakeProtocol:
    def __init__(
        self,
        *,
        metrics_dir: Path,
        canary_results: tuple[bool | Exception, bool | Exception] = (True, True),
        incomplete_formal: bool = False,
        forged_formal: str | None = None,
    ) -> None:
        self.metrics_dir = Path(metrics_dir)
        self.canary_results = list(canary_results)
        self.incomplete_formal = incomplete_formal
        self.forged_formal = forged_formal
        self.calls: list[tuple[str, Any, str, str]] = []

    def run_canary(
        self,
        candidate_workspace: str,
        champion_workspace: str,
        *,
        selected_surface: str | None,
    ) -> CanaryResult:
        del selected_surface
        self.calls.append(
            ("canary", None, candidate_workspace, champion_workspace)
        )
        outcome = self.canary_results.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        passed = outcome
        return CanaryResult(
            passed=passed,
            reason=None if passed else "unsafe subject",
            details={"passed": passed},
        )

    def run_experiment(
        self,
        stage: ExperimentStage,
        candidate_workspace: str,
        champion_workspace: str,
        hypothesis_action: str,
        *,
        selected_surface: str | None,
    ) -> ProtocolResult:
        del hypothesis_action, selected_surface
        self.calls.append(
            ("formal", stage, candidate_workspace, champion_workspace)
        )
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        raw_metrics = self.metrics_dir / "frozen.json"
        raw_metrics.write_text("{}\n", encoding="utf-8")
        completed_pairs = 0 if self.incomplete_formal else 1
        n_cases = 2 if self.forged_formal == "wrong_n_cases" else 1
        case_wins = 0 if self.forged_formal == "wrong_case_sum" else 1
        pair_wins = 0 if self.forged_formal == "wrong_pair_sum" else 1
        stats = EvalStats(
            n_cases=n_cases,
            wins=case_wins,
            losses=0,
            ties=0,
            win_rate=1.0,
            median_delta=1.0,
            ci_low=0.5,
            ci_high=1.5,
            total_pairs=1,
            attempted_pairs=completed_pairs,
            valid_pairs=completed_pairs,
            failed_pairs=0,
            pair_wins=pair_wins,
        )
        return ProtocolResult(
            stage=stage,
            stats=stats,
            gate_outcome="pass",
            reason_codes=("FROZEN_PASS_HIERARCHICAL",),
            exposed_summary="held-out pass",
            raw_metrics_ref=str(raw_metrics),
            objective_semantics="declared_objectives_lexicographic",
            case_ids=("heldout.json",),
            seed_set=(1,),
        )


class _ResultRunner:
    def __init__(self, result: RunResult) -> None:
        self.result = result

    def run_solver(self, **_: Any) -> RunResult:
        return self.result


class _SequenceRunner:
    def __init__(self, results: list[RunResult]) -> None:
        self.results = list(results)

    def run_solver(self, **_: Any) -> RunResult:
        return self.results.pop(0)


def _run(*, feasible: bool) -> RunResult:
    return RunResult(
        success=True,
        exit_code=0,
        stdout="",
        stderr="",
        elapsed_ms=1,
        output=SolverOutput(objective={"cost": 1}, feasible=feasible),
    )


def _formal_workspace(path: Path) -> Path:
    path.mkdir()
    (path / "case.json").write_text("{}\n", encoding="utf-8")
    (path / "registry.yaml").write_text("operators: {}\n", encoding="utf-8")
    return path


def _workspace(path: Path, *, marker: str) -> Path:
    path.mkdir()
    (path / "marker.txt").write_text(marker, encoding="utf-8")
    (path / "solver.py").write_text("# solver\n", encoding="utf-8")
    (path / "registry.yaml").write_text("operators: {}\n", encoding="utf-8")
    return path


def _manifest(tmp_path: Path, *, candidate: Path, champion: Path) -> Path:
    for name in ("problem-v1.yaml", "protocol.yaml", "split_manifest.yaml", "seed_ledger.yaml"):
        (tmp_path / name).write_text("placeholder: true\n", encoding="utf-8")
    manifest = tmp_path / "comparison.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": MANIFEST_SCHEMA_VERSION,
                "problem_yaml": "problem-v1.yaml",
                "protocol": "protocol.yaml",
                "split_manifest": "split_manifest.yaml",
                "seed_ledger": "seed_ledger.yaml",
                "time_limit_sec": 1,
                "groups": [
                    {
                        "comparison_id": "v2-vs-v1",
                        "candidate_workspace": str(candidate),
                        "champion_workspace": str(champion),
                        "candidate_label": "champion_v2",
                        "champion_label": "champion_v1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return manifest


def _matrix_configs(
    tmp_path: Path,
    *,
    configured_cases: int = 12,
    configured_seeds: int = 3,
) -> tuple[Path, Path, Path, list[str], list[int]]:
    cases = [f"data/heldout_{index:02d}.json" for index in range(12)]
    seeds = [11, 73, 509]
    protocol_path = tmp_path / "formal-protocol.yaml"
    split_path = tmp_path / "formal-split.yaml"
    seeds_path = tmp_path / "formal-seeds.yaml"
    protocol_path.write_text(
        yaml.safe_dump(
            ProtocolConfig(
                frozen={
                    "n_cases": configured_cases,
                    "n_seeds": configured_seeds,
                }
            ).model_dump()
        ),
        encoding="utf-8",
    )
    split_path.write_text(
        yaml.safe_dump(
            SplitManifest(
                frozen=cases,
                canary=["data/canary.json"],
            ).model_dump()
        ),
        encoding="utf-8",
    )
    seeds_path.write_text(
        yaml.safe_dump(
            SeedLedgerConfig(
                frozen=seeds,
                canary=[1009],
            ).model_dump()
        ),
        encoding="utf-8",
    )
    return protocol_path, split_path, seeds_path, cases, seeds
