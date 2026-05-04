from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import pytest

from scion.core.models import RunResult
from scion.evidence import (
    CvrpCaseEntry,
    CvrpCaseManifest,
    CvrpManifestEvaluationConfig,
    build_cvrp_final_evaluation_config_from_manifest,
    build_cvrp_manifest_final_evidence_package,
    write_cvrp_manifest_final_evidence_package,
)
from scion.problems.cvrp.adapter import CvrpAdapter


CVRP_DIR = Path(__file__).resolve().parents[3] / "problems" / "cvrp"
TINY_5 = CVRP_DIR / "data" / "tiny_5.json"

_MISSING = object()
_ARTIFACT_KEYS = {
    "manifest",
    "final_quality_json",
    "final_quality_csv",
    "per_case_quality_csv",
    "runtime_summary",
    "failure_summary",
}
_ARTIFACT_NAMES = {
    "evidence_manifest.json",
    "final_quality.json",
    "final_quality.csv",
    "per_case_quality.csv",
    "runtime_summary.json",
    "failure_summary.json",
}


class _Spec:
    pass


class _RecordingAdapter:
    def __init__(self) -> None:
        self._delegate = CvrpAdapter(_Spec())  # type: ignore[arg-type]
        self.load_calls: list[str] = []

    def load_instance(self, instance_path: str) -> object:
        self.load_calls.append(instance_path)
        return self._delegate.load_instance(instance_path)

    def __getattr__(self, name: str) -> object:
        return getattr(self._delegate, name)


@dataclass(frozen=True)
class _FakeRun:
    raw: Mapping[str, object] | None = None
    success: bool = True
    elapsed_ms: int = 100
    exit_code: int = 0
    error_category: str | None = None
    stderr: str = ""


class _FakeRunner:
    def __init__(
        self,
        responses: Mapping[tuple[str, str, int], _FakeRun],
    ) -> None:
        self._responses = dict(responses)
        self.calls: list[dict[str, object]] = []

    def run_solver(
        self,
        workdir: str,
        instance_path: str,
        seed: int,
        time_limit_sec: int,
        registry_path: str,
    ) -> RunResult:
        self.calls.append(
            {
                "workdir": workdir,
                "instance_path": instance_path,
                "seed": seed,
                "time_limit_sec": time_limit_sec,
                "registry_path": registry_path,
            }
        )
        key = (workdir, instance_path, seed)
        if key not in self._responses:
            raise AssertionError(f"unexpected runner call: {key!r}")
        response = self._responses[key]
        return RunResult(
            success=response.success,
            exit_code=response.exit_code if not response.success else 0,
            stdout="",
            stderr=response.stderr,
            elapsed_ms=response.elapsed_ms,
            output=response.raw,  # type: ignore[arg-type]
            output_path=None,
            error_category=response.error_category,  # type: ignore[arg-type]
        )


def _manifest(
    case_paths: list[str | Path],
    *,
    config_seeds: object = (11,),
    metadata_seeds: object = _MISSING,
    problem_id: str = "cvrp",
) -> CvrpCaseManifest:
    config: dict[str, object] = {}
    metadata: dict[str, object] = {}
    if config_seeds is not _MISSING:
        config["seeds"] = _seed_payload(config_seeds)
    if metadata_seeds is not _MISSING:
        metadata["seed_list"] = _seed_payload(metadata_seeds)
    return CvrpCaseManifest(
        schema="scion.cvrp_case_manifest.v1",
        problem_id=problem_id,
        cases=tuple(
            CvrpCaseEntry(
                case_id=f"case-{index}",
                source_path=str(case_path),
            )
            for index, case_path in enumerate(case_paths)
        ),
        config=config,
        metadata=metadata,
    )


def _seed_payload(value: object) -> object:
    if isinstance(value, str):
        return value
    try:
        return list(value)  # type: ignore[arg-type]
    except TypeError:
        return value


def _config(tmp_path: Path, **overrides: object) -> CvrpManifestEvaluationConfig:
    values: dict[str, object] = {
        "campaign_id": "cvrp-manifest-final",
        "baseline_workspace": tmp_path / "baseline",
        "candidate_workspace": tmp_path / "candidate",
        "time_limit_sec": 30,
        "baseline_label": "baseline-v0",
        "candidate_label": "champion-v1",
    }
    values.update(overrides)
    return CvrpManifestEvaluationConfig(**values)  # type: ignore[arg-type]


def _raw(
    routes: list[list[int]],
    *,
    reported_distance: float = 999.0,
    feasible: bool = True,
) -> dict[str, object]:
    return {
        "routes": routes,
        "objective": {
            "fleet_violation": 0,
            "total_distance": reported_distance,
            "routes": len(routes),
        },
        "feasible": feasible,
    }


def _runner_for_seed_pairs(
    config: CvrpManifestEvaluationConfig,
    case_path: str | Path,
    runs_by_seed: Mapping[int, tuple[_FakeRun, _FakeRun]],
) -> _FakeRunner:
    responses: dict[tuple[str, str, int], _FakeRun] = {}
    for seed, (baseline, candidate) in runs_by_seed.items():
        responses[(str(config.baseline_workspace), str(case_path), seed)] = baseline
        responses[(str(config.candidate_workspace), str(case_path), seed)] = candidate
    return _FakeRunner(responses)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_config_builder_extracts_source_paths_and_manifest_seeds(
    tmp_path: Path,
) -> None:
    manifest = _manifest(
        ["opaque/A.json", "opaque/B.json"],
        config_seeds=[11, "29"],
        metadata_seeds=[47],
    )
    output_dir = tmp_path / "evidence"
    config = _config(
        tmp_path,
        problem_id="cvrp-custom",
        runtime_regression_threshold=1.5,
        objective_tolerance=1e-6,
        baseline_registry_path=tmp_path / "baseline-registry.json",
        candidate_registry_path=tmp_path / "candidate-registry.json",
        output_dir=output_dir,
    )

    final_config = build_cvrp_final_evaluation_config_from_manifest(
        manifest,
        config=config,
    )

    assert final_config.case_paths == ("opaque/A.json", "opaque/B.json")
    assert final_config.seeds == (11, 29)
    assert final_config.problem_id == "cvrp-custom"
    assert final_config.campaign_id == "cvrp-manifest-final"
    assert final_config.baseline_workspace == tmp_path / "baseline"
    assert final_config.candidate_workspace == tmp_path / "candidate"
    assert final_config.time_limit_sec == 30
    assert final_config.baseline_label == "baseline-v0"
    assert final_config.candidate_label == "champion-v1"
    assert final_config.runtime_regression_threshold == 1.5
    assert final_config.objective_tolerance == 1e-6
    assert final_config.baseline_registry_path == tmp_path / "baseline-registry.json"
    assert final_config.candidate_registry_path == tmp_path / "candidate-registry.json"
    assert final_config.output_dir == output_dir

    metadata_manifest = _manifest(
        ["opaque/C.json"],
        config_seeds=_MISSING,
        metadata_seeds=["47"],
    )
    metadata_config = build_cvrp_final_evaluation_config_from_manifest(
        metadata_manifest,
        config=_config(tmp_path),
    )
    assert metadata_config.case_paths == ("opaque/C.json",)
    assert metadata_config.seeds == (47,)
    assert metadata_config.problem_id == "cvrp"


def test_explicit_seed_override_wins_over_manifest_seeds(tmp_path: Path) -> None:
    manifest = _manifest([TINY_5], config_seeds=[11])
    config = _config(tmp_path, seeds=["101"])

    config_override = build_cvrp_final_evaluation_config_from_manifest(
        manifest,
        config=config,
    )
    call_override = build_cvrp_final_evaluation_config_from_manifest(
        manifest,
        config=config,
        seeds=[202],
    )

    assert config_override.seeds == (101,)
    assert call_override.seeds == (202,)


def test_empty_cases_and_empty_seeds_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="cases"):
        build_cvrp_final_evaluation_config_from_manifest(
            _manifest([], config_seeds=[11]),
            config=_config(tmp_path),
        )

    with pytest.raises(ValueError, match="seeds"):
        build_cvrp_final_evaluation_config_from_manifest(
            _manifest([TINY_5], config_seeds=_MISSING, metadata_seeds=_MISSING),
            config=_config(tmp_path),
        )

    with pytest.raises(ValueError, match="seeds"):
        build_cvrp_final_evaluation_config_from_manifest(
            _manifest([TINY_5], config_seeds=[11]),
            config=_config(tmp_path, seeds=[]),
        )


def test_build_manifest_final_evidence_uses_runner_backed_path_and_compares(
    tmp_path: Path,
) -> None:
    manifest = _manifest([TINY_5], config_seeds=[11, 29, 47])
    config = _config(
        tmp_path,
        time_limit_sec=17,
        baseline_registry_path="baseline-registry.json",
        candidate_registry_path="candidate-registry.json",
    )
    runner = _runner_for_seed_pairs(
        config,
        TINY_5,
        {
            11: (
                _FakeRun(raw=_raw([[1, 3], [2, 4]])),
                _FakeRun(raw=_raw([[1, 2], [3, 4]])),
            ),
            29: (
                _FakeRun(raw=_raw([[1, 2], [3, 4]])),
                _FakeRun(raw=_raw([[1, 2], [3, 4]])),
            ),
            47: (
                _FakeRun(raw=_raw([[1, 2], [3, 4]])),
                _FakeRun(raw=_raw([[1, 3], [2, 4]])),
            ),
        },
    )

    package = build_cvrp_manifest_final_evidence_package(
        manifest,
        config=config,
        runner=runner,
        adapter=CvrpAdapter(_Spec()),  # type: ignore[arg-type]
    )

    assert package.final_quality["better_vs_baseline"] == 1
    assert package.final_quality["equal_vs_baseline"] == 1
    assert package.final_quality["worse_vs_baseline"] == 1
    assert package.final_quality["n_cases"] == 3
    assert {
        row["seed"]: row["comparison"]
        for row in package.per_case_quality
    } == {
        11: "better",
        29: "equal",
        47: "worse",
    }
    assert len(runner.calls) == 6
    assert {
        (call["instance_path"], call["seed"], call["time_limit_sec"])
        for call in runner.calls
    } == {
        (str(TINY_5), 11, 17),
        (str(TINY_5), 29, 17),
        (str(TINY_5), 47, 17),
    }
    assert {call["registry_path"] for call in runner.calls} == {
        "baseline-registry.json",
        "candidate-registry.json",
    }


def test_write_manifest_final_evidence_writes_six_artifacts_and_refs(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "evidence"
    manifest = _manifest([TINY_5], config_seeds=[11])
    config = _config(tmp_path, output_dir=output_dir)
    runner = _runner_for_seed_pairs(
        config,
        TINY_5,
        {
            11: (
                _FakeRun(raw=_raw([[1, 3], [2, 4]])),
                _FakeRun(raw=_raw([[1, 2], [3, 4]])),
            ),
        },
    )

    result = write_cvrp_manifest_final_evidence_package(
        manifest,
        config=config,
        runner=runner,
        adapter=CvrpAdapter(_Spec()),  # type: ignore[arg-type]
    )

    assert set(result.artifacts) == _ARTIFACT_KEYS
    assert {path.name for path in result.artifacts.values()} == _ARTIFACT_NAMES
    assert all(path.exists() for path in result.artifacts.values())
    assert result.artifacts["manifest"] == output_dir / "evidence_manifest.json"
    assert result.artifacts["final_quality_json"] == output_dir / "final_quality.json"
    assert result.artifacts["final_quality_csv"] == output_dir / "final_quality.csv"
    assert result.artifacts["per_case_quality_csv"] == output_dir / "per_case_quality.csv"
    assert result.artifacts["runtime_summary"] == output_dir / "runtime_summary.json"
    assert result.artifacts["failure_summary"] == output_dir / "failure_summary.json"
    assert _read_json(output_dir / "final_quality.json")["better_vs_baseline"] == 1


def test_manifest_source_paths_are_only_loaded_through_adapter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_path = tmp_path / "manifest_case.json"
    case_path.write_text(TINY_5.read_text(encoding="utf-8"), encoding="utf-8")
    manifest = _manifest([case_path], config_seeds=[11])
    config = _config(tmp_path)
    runner = _runner_for_seed_pairs(
        config,
        case_path,
        {
            11: (
                _FakeRun(raw=_raw([[1, 3], [2, 4]])),
                _FakeRun(raw=_raw([[1, 2], [3, 4]])),
            ),
        },
    )
    adapter = _RecordingAdapter()
    original_open = Path.open

    def guarded_open(self: Path, *args: object, **kwargs: object):
        if self == case_path:
            raise AssertionError(f"manifest case path opened via Path.open: {self}")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)

    package = build_cvrp_manifest_final_evidence_package(
        manifest,
        config=config,
        runner=runner,
        adapter=adapter,  # type: ignore[arg-type]
    )

    assert package.final_quality["better_vs_baseline"] == 1
    assert adapter.load_calls == [str(case_path)]
    assert [call["instance_path"] for call in runner.calls] == [
        str(case_path),
        str(case_path),
    ]


def test_relative_manifest_case_paths_resolve_for_adapter_but_not_runner(
    tmp_path: Path,
) -> None:
    baseline_workspace = tmp_path / "baseline"
    candidate_workspace = tmp_path / "candidate"
    relative_case = Path("cases") / "relative_case.json"
    absolute_case = baseline_workspace / relative_case
    absolute_case.parent.mkdir(parents=True)
    candidate_workspace.mkdir()
    absolute_case.write_text(TINY_5.read_text(encoding="utf-8"), encoding="utf-8")

    manifest = _manifest([str(relative_case)], config_seeds=[11])
    config = _config(
        tmp_path,
        baseline_workspace=baseline_workspace,
        candidate_workspace=candidate_workspace,
    )
    runner = _runner_for_seed_pairs(
        config,
        str(relative_case),
        {
            11: (
                _FakeRun(raw=_raw([[1, 3], [2, 4]])),
                _FakeRun(raw=_raw([[1, 2], [3, 4]])),
            ),
        },
    )
    adapter = _RecordingAdapter()

    package = build_cvrp_manifest_final_evidence_package(
        manifest,
        config=config,
        runner=runner,
        adapter=adapter,  # type: ignore[arg-type]
    )

    assert package.final_quality["better_vs_baseline"] == 1
    assert adapter.load_calls == [str(absolute_case)]
    assert [call["instance_path"] for call in runner.calls] == [
        str(relative_case),
        str(relative_case),
    ]
