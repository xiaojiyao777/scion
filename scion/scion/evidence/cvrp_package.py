"""No-run CVRP final evidence package builder.

This service wires CVRP result CSV artifacts into the generic final-quality
writer. It opens only the provided CSV inputs and the requested output files;
instance paths inside CSV rows remain opaque strings.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from scion.evidence.cvrp_baseline_import import load_cvrp_quality_records
from scion.evidence.final_quality import (
    FinalQualityConfig,
    FinalQualityPackage,
    build_final_quality_package,
    write_final_quality_package,
)


__all__ = [
    "CvrpEvidencePackageConfig",
    "CvrpEvidencePackageResult",
    "build_cvrp_evidence_package_from_csv",
    "write_cvrp_evidence_package_from_csv",
]


@dataclass(frozen=True)
class CvrpEvidencePackageConfig:
    """Configuration for building a no-run CVRP evidence package."""

    campaign_id: str
    problem_id: str = "cvrp"
    baseline_label: str = "baseline"
    candidate_label: str = "candidate"
    runtime_regression_threshold: float = 2.0
    objective_tolerance: float = 1e-9
    output_dir: str | Path | None = None


@dataclass(frozen=True)
class CvrpEvidencePackageResult:
    """Built package plus any written artifact paths."""

    package: FinalQualityPackage
    artifacts: dict[str, Path] = field(default_factory=dict)


def build_cvrp_evidence_package_from_csv(
    baseline_csv: str | Path,
    candidate_csv: str | Path | None = None,
    *,
    config: CvrpEvidencePackageConfig,
) -> FinalQualityPackage:
    """Build an in-memory final-quality package from CVRP result CSV artifact(s)."""

    records = load_cvrp_quality_records(baseline_csv, candidate_csv)
    return build_final_quality_package(records, _final_quality_config(config))


def write_cvrp_evidence_package_from_csv(
    baseline_csv: str | Path,
    candidate_csv: str | Path | None = None,
    *,
    config: CvrpEvidencePackageConfig,
    output_dir: str | Path | None = None,
) -> CvrpEvidencePackageResult:
    """Build and write a final-quality package from CVRP result CSV artifact(s)."""

    resolved_output_dir = output_dir if output_dir is not None else config.output_dir
    if resolved_output_dir is None:
        raise ValueError("output_dir is required to write a CVRP evidence package")

    package = build_cvrp_evidence_package_from_csv(
        baseline_csv,
        candidate_csv,
        config=config,
    )
    artifacts = write_final_quality_package(package, resolved_output_dir)
    return CvrpEvidencePackageResult(package=package, artifacts=artifacts)


def _final_quality_config(config: CvrpEvidencePackageConfig) -> FinalQualityConfig:
    return FinalQualityConfig(
        problem_id=config.problem_id,
        campaign_id=config.campaign_id,
        baseline_label=config.baseline_label,
        candidate_label=config.candidate_label,
        runtime_regression_threshold=config.runtime_regression_threshold,
        objective_sense="minimize",
        primary_metric="cost",
        objective_tolerance=config.objective_tolerance,
    )
