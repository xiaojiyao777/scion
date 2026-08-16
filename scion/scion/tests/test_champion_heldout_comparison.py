from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.core.models import (
    CanaryResult,
    EvalStats,
    ExperimentStage,
    ProtocolResult,
    RunResult,
    SolverOutput,
)
from scion.evaluation.champion_holdout import (
    MANIFEST_SCHEMA_VERSION,
    InfeasibleAsFailureRunner,
    build_champion_heldout_protocol,
    execute_champion_heldout_comparison,
)
from scion.problem.spec import ObjectiveMetricSpec
from scion.protocol.experiment import ExperimentProtocol, SeedLedger, SplitManager
from scion.runtime.subprocess_runner import LocalSubprocessRunner


def _run(
    objective: dict[str, Any] | None = None,
    *,
    feasible: bool = True,
    output: bool = True,
) -> RunResult:
    parsed = (
        SolverOutput(objective=objective or {}, feasible=feasible) if output else None
    )
    return RunResult(True, 0, "", "", 1, parsed)


class _SequenceRunner:
    def __init__(self, results: list[RunResult]) -> None:
        self.results = list(results)

    def run_solver(self, **_: Any) -> RunResult:
        return self.results.pop(0)


class _FakeProtocol:
    def __init__(
        self,
        metrics_dir: Path,
        *,
        canary: tuple[bool | BaseException, bool | BaseException] = (True, True),
        stats_mode: str = "valid",
    ) -> None:
        self.metrics_dir = Path(metrics_dir)
        self.canary = list(canary)
        self.stats_mode = stats_mode
        self.calls: list[str] = []

    def run_canary(self, candidate: str, champion: str) -> CanaryResult:
        assert candidate != champion
        self.calls.append("canary")
        outcome = self.canary.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return CanaryResult(outcome, None if outcome else "unsafe", {"passed": outcome})

    def run_experiment(
        self, stage: ExperimentStage, candidate: str, champion: str, action: str
    ) -> ProtocolResult:
        assert stage is ExperimentStage.FROZEN and candidate != champion
        assert action == "modify"
        self.calls.append("formal")
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        raw = self.metrics_dir / "frozen.json"
        raw.write_text("{}\n", encoding="utf-8")
        mode = self.stats_mode
        stats = EvalStats(
            n_cases=2 if mode == "wrong_n_cases" else 1,
            wins=0 if mode == "wrong_case_sum" else 1,
            losses=0,
            ties=0,
            win_rate=1.0,
            median_delta=1.0,
            ci_low=0.5,
            ci_high=1.5,
            total_pairs=1,
            attempted_pairs=0 if mode == "incomplete" else 1,
            valid_pairs=0 if mode == "incomplete" else 1,
            failed_pairs=0,
            pair_wins=0 if mode == "wrong_pair_sum" else 1,
        )
        return ProtocolResult(
            stage,
            stats,
            "pass",
            ("FROZEN_PASS",),
            "pass",
            str(raw),
            "declared_objectives_lexicographic",
            ("heldout.json",),
            (1,),
        )


def test_summary_embeds_complete_group_from_ordinary_copies(tmp_path: Path) -> None:
    manifest, sources = _manifest(tmp_path, ["v2-v1"])
    protocols: list[_FakeProtocol] = []

    def factory(**kwargs: Any) -> _FakeProtocol:
        protocols.append(_FakeProtocol(kwargs["metrics_dir"]))
        return protocols[-1]

    path = execute_champion_heldout_comparison(
        manifest, output_dir=tmp_path / "out", protocol_factory=factory
    )
    summary = json.loads(path.read_text(encoding="utf-8"))
    group = summary["groups"][0]

    assert summary["status"] == "completed"
    assert summary["all_groups_supported"] is True
    assert summary["candidate_supported_group_count"] == 1
    assert "result_path" not in group and not (tmp_path / "out/groups").exists()
    assert group["formal"]["stats"]["valid_pairs"] == 1
    assert protocols[0].calls == ["canary", "canary", "formal"]
    candidate_copy = Path(group["candidate_workspace"])
    assert candidate_copy != sources[0][0]
    assert candidate_copy.joinpath("marker.txt").read_text() == "candidate"
    assert sources[0][0].joinpath("marker.txt").read_text() == "candidate"


@pytest.mark.parametrize("outcome", [False, RuntimeError("canary error")])
def test_canary_veto_is_execution_invalid_and_skips_formal(
    tmp_path: Path, outcome: bool | BaseException
) -> None:
    manifest, _ = _manifest(tmp_path, ["v2-v1"])
    protocol = _FakeProtocol(tmp_path / "metrics", canary=(outcome, True))
    path = execute_champion_heldout_comparison(
        manifest, output_dir=tmp_path / "out", protocol_factory=lambda **_: protocol
    )
    summary = json.loads(path.read_text())
    group = summary["groups"][0]
    assert group["status"] == "execution-invalid"
    assert group["formal"]["reason_code"] == "CANARY_SAFETY_VETO"
    assert group["supports_candidate"] is False
    assert protocol.calls == ["canary", "canary"]


def test_summary_retains_completed_group_on_later_interruption(tmp_path: Path) -> None:
    manifest, _ = _manifest(tmp_path, ["v2-v1", "v3-v2"])
    protocols = iter(
        [
            _FakeProtocol(tmp_path / "metrics-1"),
            _FakeProtocol(tmp_path / "metrics-2", canary=(KeyboardInterrupt(), True)),
        ]
    )
    output = tmp_path / "out"
    with pytest.raises(KeyboardInterrupt):
        execute_champion_heldout_comparison(
            manifest, output_dir=output, protocol_factory=lambda **_: next(protocols)
        )
    summary = json.loads(
        output.joinpath("champion_heldout_comparison_summary.v1.json").read_text()
    )
    assert summary["status"] == "running"
    assert [group["comparison_id"] for group in summary["groups"]] == ["v2-v1"]


@pytest.mark.parametrize(
    "mode", ["incomplete", "wrong_n_cases", "wrong_case_sum", "wrong_pair_sum"]
)
def test_incomplete_or_inconsistent_stats_cannot_support(
    tmp_path: Path, mode: str
) -> None:
    manifest, _ = _manifest(tmp_path, ["v2-v1"])
    protocol = _FakeProtocol(tmp_path / "metrics", stats_mode=mode)
    path = execute_champion_heldout_comparison(
        manifest, output_dir=tmp_path / "out", protocol_factory=lambda **_: protocol
    )
    group = json.loads(path.read_text())["groups"][0]
    assert group["formal"]["gate_outcome"] == "pass"
    assert group["supports_candidate"] is False


@pytest.mark.parametrize(
    ("result", "category"),
    [
        (_run({"cost": 1.0}), None),
        (_run(output=False), "missing_solver_output"),
        (_run(feasible=False), "infeasible_solution"),
        (_run({}), "missing_objective_metric"),
        (_run({"cost": "bad"}), "invalid_objective_metric"),
        (_run({"cost": True}), "invalid_objective_metric"),
        (_run({"cost": float("nan")}), "nonfinite_objective_metric"),
        (_run({"cost": float("inf")}), "nonfinite_objective_metric"),
    ],
)
def test_declared_output_is_finite_and_feasible(
    result: RunResult, category: str | None
) -> None:
    runner = InfeasibleAsFailureRunner(
        _SequenceRunner([result]), metric_names=("cost",)
    )
    checked = runner.run_solver("/w", "case", 1, 1, "/w/registry.yaml")
    assert checked.success is (category is None)
    assert checked.error_category == category


@pytest.mark.parametrize("side", ["candidate", "champion"])
@pytest.mark.parametrize(
    "invalid", [_run(feasible=False), _run({"cost": float("nan")})]
)
def test_formal_counts_invalid_output_on_its_arm(
    tmp_path: Path, side: str, invalid: RunResult
) -> None:
    candidate, champion = (
        _formal_workspace(tmp_path / "candidate"),
        _formal_workspace(tmp_path / "champion"),
    )
    valid = _run({"cost": 1.0})
    results = [invalid, valid] if side == "champion" else [valid, invalid]
    protocol = ExperimentProtocol(
        ProtocolConfig(frozen={"n_cases": 1, "n_seeds": 1}),
        SplitManager(SplitManifest(frozen=["case.json"])),
        SeedLedger(SeedLedgerConfig(frozen=[3])),
        InfeasibleAsFailureRunner(_SequenceRunner(results), metric_names=("cost",)),
        1,
        str(tmp_path / "metrics"),
        metric_specs=(
            ObjectiveMetricSpec(name="cost", direction="minimize", priority=1),
        ),
    )
    result = protocol.run_experiment(
        ExperimentStage.FROZEN, str(candidate), str(champion), "modify"
    )
    assert result.stats.candidate_failed_pairs == (side == "candidate")
    assert result.stats.champion_failed_pairs == (side == "champion")
    assert result.gate_outcome == "fail"


def test_builder_selects_exact_12_by_3(tmp_path: Path) -> None:
    protocol_path, split_path, seeds_path, cases, seeds = _matrix(tmp_path)
    protocol = build_champion_heldout_protocol(
        problem_yaml_path=_warehouse_problem(),
        protocol_path=protocol_path,
        split_path=split_path,
        seeds_path=seeds_path,
        metrics_dir=tmp_path / "metrics",
        time_limit_sec=3,
    )
    assert isinstance(protocol.runner.delegate, LocalSubprocessRunner)
    assert protocol.runner.metric_names == ("subcategory_splits", "total_cost")
    assert protocol._select_cases(ExperimentStage.FROZEN, "modify", 0) == cases
    assert protocol._select_seeds(ExperimentStage.FROZEN) == seeds


@pytest.mark.parametrize("shape", [(4, 3), (12, 2)])
def test_builder_rejects_truncated_matrix(
    tmp_path: Path, shape: tuple[int, int]
) -> None:
    protocol_path, split_path, seeds_path, _, _ = _matrix(tmp_path, shape)
    with pytest.raises(ValueError, match="complete frozen matrix"):
        build_champion_heldout_protocol(
            problem_yaml_path=_warehouse_problem(),
            protocol_path=protocol_path,
            split_path=split_path,
            seeds_path=seeds_path,
            metrics_dir=tmp_path / "metrics",
            time_limit_sec=3,
        )


def _workspace(path: Path, marker: str) -> Path:
    path.mkdir(parents=True)
    path.joinpath("marker.txt").write_text(marker)
    path.joinpath("registry.yaml").write_text("operators: {}\n")
    return path


def _formal_workspace(path: Path) -> Path:
    _workspace(path, path.name)
    path.joinpath("case.json").write_text("{}\n")
    return path


def _manifest(tmp_path: Path, ids: list[str]) -> tuple[Path, list[tuple[Path, Path]]]:
    for name in ("problem-v1.yaml", "protocol.yaml", "split.yaml", "seeds.yaml"):
        tmp_path.joinpath(name).write_text("placeholder: true\n")
    sources, groups = [], []
    for index, comparison_id in enumerate(ids):
        candidate = _workspace(tmp_path / f"candidate-{index}", "candidate")
        champion = _workspace(tmp_path / f"champion-{index}", "champion")
        sources.append((candidate, champion))
        groups.append(
            {
                "comparison_id": comparison_id,
                "candidate_workspace": str(candidate),
                "champion_workspace": str(champion),
            }
        )
    manifest = tmp_path / "comparison.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": MANIFEST_SCHEMA_VERSION,
                "problem_yaml": "problem-v1.yaml",
                "protocol": "protocol.yaml",
                "split_manifest": "split.yaml",
                "seed_ledger": "seeds.yaml",
                "time_limit_sec": 1,
                "groups": groups,
            }
        )
    )
    return manifest, sources


def _warehouse_problem() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "problems/warehouse_delivery/problem-v1.yaml"
    )


def _matrix(
    tmp_path: Path, shape: tuple[int, int] = (12, 3)
) -> tuple[Path, Path, Path, list[str], list[int]]:
    cases, seeds = [f"data/heldout_{i}.json" for i in range(12)], [11, 73, 509]
    protocol, split, ledger = (
        tmp_path / "formal-protocol.yaml",
        tmp_path / "formal-split.yaml",
        tmp_path / "formal-seeds.yaml",
    )
    protocol.write_text(
        yaml.safe_dump(
            ProtocolConfig(
                frozen={"n_cases": shape[0], "n_seeds": shape[1]}
            ).model_dump()
        )
    )
    split.write_text(
        yaml.safe_dump(
            SplitManifest(frozen=cases, canary=["data/canary.json"]).model_dump()
        )
    )
    ledger.write_text(
        yaml.safe_dump(SeedLedgerConfig(frozen=seeds, canary=[1009]).model_dump())
    )
    return protocol, split, ledger, cases, seeds
