"""Manifest-driven CVRP final evidence builder.

This module connects a fixed CVRP case manifest to the runner-backed final
evaluation service. It treats manifest case paths as opaque strings until the
adapter is asked to load them.
"""
from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral, Real
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

from scion.evidence.cvrp_case_manifest import CvrpCaseManifest
from scion.evidence.cvrp_final_evaluation import (
    CvrpFinalEvaluationConfig,
    build_cvrp_final_evidence_package,
    write_cvrp_final_evidence_package,
)
from scion.evidence.cvrp_package import CvrpEvidencePackageResult
from scion.evidence.final_quality import FinalQualityPackage

if TYPE_CHECKING:
    from scion.problem.contracts import ProblemAdapter
    from scion.runtime.runner import Runner


__all__ = [
    "CvrpManifestEvaluationConfig",
    "build_cvrp_final_evaluation_config_from_manifest",
    "build_cvrp_manifest_final_evidence_package",
    "write_cvrp_manifest_final_evidence_package",
]


@dataclass(frozen=True)
class CvrpManifestEvaluationConfig:
    """Configuration for evaluating a CVRP final case manifest."""

    campaign_id: str
    baseline_workspace: str | Path
    candidate_workspace: str | Path
    time_limit_sec: int
    problem_id: str | None = None
    baseline_label: str = "baseline"
    candidate_label: str = "candidate"
    seeds: Sequence[int | str] | None = None
    runtime_regression_threshold: float = 2.0
    objective_tolerance: float = 1e-9
    baseline_registry_path: str | Path | None = None
    candidate_registry_path: str | Path | None = None
    output_dir: str | Path | None = None


def build_cvrp_final_evaluation_config_from_manifest(
    manifest: CvrpCaseManifest,
    *,
    config: CvrpManifestEvaluationConfig,
    seeds: Sequence[int | str] | None = None,
) -> CvrpFinalEvaluationConfig:
    """Build a runner-backed final evaluation config from a case manifest."""

    case_paths = _case_paths_from_manifest(manifest)
    resolved_seeds = _resolve_seeds(manifest, config=config, seeds=seeds)
    problem_id = config.problem_id or manifest.problem_id or "cvrp"

    return CvrpFinalEvaluationConfig(
        campaign_id=config.campaign_id,
        problem_id=str(problem_id),
        baseline_workspace=config.baseline_workspace,
        candidate_workspace=config.candidate_workspace,
        case_paths=case_paths,
        seeds=resolved_seeds,
        time_limit_sec=config.time_limit_sec,
        baseline_label=config.baseline_label,
        candidate_label=config.candidate_label,
        runtime_regression_threshold=config.runtime_regression_threshold,
        objective_tolerance=config.objective_tolerance,
        baseline_registry_path=config.baseline_registry_path,
        candidate_registry_path=config.candidate_registry_path,
        output_dir=config.output_dir,
    )


def build_cvrp_manifest_final_evidence_package(
    manifest: CvrpCaseManifest,
    *,
    config: CvrpManifestEvaluationConfig,
    runner: "Runner",
    adapter: "ProblemAdapter",
    seeds: Sequence[int | str] | None = None,
) -> FinalQualityPackage:
    """Run manifest-driven final evaluation and build an evidence package."""

    final_config = build_cvrp_final_evaluation_config_from_manifest(
        manifest,
        config=config,
        seeds=seeds,
    )
    return build_cvrp_final_evidence_package(
        config=final_config,
        runner=runner,
        adapter=_adapter_with_manifest_path_resolution(
            adapter,
            base_workspace=config.baseline_workspace,
        ),
    )


def write_cvrp_manifest_final_evidence_package(
    manifest: CvrpCaseManifest,
    *,
    config: CvrpManifestEvaluationConfig,
    runner: "Runner",
    adapter: "ProblemAdapter",
    output_dir: str | Path | None = None,
    seeds: Sequence[int | str] | None = None,
) -> CvrpEvidencePackageResult:
    """Run manifest-driven final evaluation and write evidence artifacts."""

    final_config = build_cvrp_final_evaluation_config_from_manifest(
        manifest,
        config=config,
        seeds=seeds,
    )
    return write_cvrp_final_evidence_package(
        config=final_config,
        runner=runner,
        adapter=_adapter_with_manifest_path_resolution(
            adapter,
            base_workspace=config.baseline_workspace,
        ),
        output_dir=output_dir,
    )


class _ManifestPathResolvingAdapter:
    """Resolve relative manifest paths for adapter loads only.

    Runner calls keep the original manifest path so each workspace executes
    against its own copied fixture tree.
    """

    def __init__(self, delegate: "ProblemAdapter", base_workspace: str | Path) -> None:
        self._delegate = delegate
        self._base_workspace = Path(base_workspace)

    def load_instance(self, instance_path: str) -> Any:
        path = Path(str(instance_path))
        if not path.is_absolute():
            path = self._base_workspace / path
        return self._delegate.load_instance(str(path))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)


def _adapter_with_manifest_path_resolution(
    adapter: "ProblemAdapter",
    *,
    base_workspace: str | Path,
) -> "ProblemAdapter":
    return _ManifestPathResolvingAdapter(
        adapter,
        base_workspace=base_workspace,
    )  # type: ignore[return-value]


def _case_paths_from_manifest(manifest: CvrpCaseManifest) -> tuple[str, ...]:
    if not manifest.cases:
        raise ValueError("manifest cases must not be empty")

    case_paths: list[str] = []
    for case in manifest.cases:
        source_path = str(case.source_path).strip()
        if not source_path:
            raise ValueError("manifest case source_path must be non-empty")
        case_paths.append(source_path)
    return tuple(case_paths)


def _resolve_seeds(
    manifest: CvrpCaseManifest,
    *,
    config: CvrpManifestEvaluationConfig,
    seeds: Sequence[int | str] | None,
) -> tuple[int, ...]:
    seed_source: object
    if seeds is not None:
        seed_source = seeds
    elif config.seeds is not None:
        seed_source = config.seeds
    else:
        seed_source = _manifest_seed_source(manifest)

    resolved = _coerce_seed_sequence(seed_source)
    if not resolved:
        raise ValueError("seeds must not be empty")
    return resolved


def _manifest_seed_source(manifest: CvrpCaseManifest) -> object:
    config_seeds = manifest.config.get("seeds")
    if _sequence_items(config_seeds):
        return config_seeds
    return manifest.metadata.get("seed_list")


def _coerce_seed_sequence(value: object) -> tuple[int, ...]:
    seeds: list[int] = []
    for item in _sequence_items(value):
        seeds.append(_coerce_seed(item))
    return tuple(seeds)


def _sequence_items(value: object) -> tuple[object, ...]:
    if value is None:
        return tuple()
    if isinstance(value, (str, bytes)):
        return (value,)
    try:
        return tuple(value)  # type: ignore[arg-type]
    except TypeError:
        return (value,)


def _coerce_seed(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("seed values must be integers, not booleans")
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError("seed values must be non-empty")
        try:
            return int(text)
        except ValueError as exc:
            raise ValueError(f"invalid seed value: {value!r}") from exc
    if isinstance(value, Real) and float(value).is_integer():
        return int(value)
    raise ValueError(f"invalid seed value: {value!r}")
