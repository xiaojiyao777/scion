"""Prepared-handoff inventory ports."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

from scion.postrun.inventory.utils import _normalize_problem_family

CoverageItemFactory = Callable[[int, str], dict[str, Any]]


class PreparedHandoffReviewPort(Protocol):
    """Problem-owned prepared-handoff checks consumed by the inventory loader."""

    problem_family: str

    def prepared_contract_checks(
        self,
        manifest: Mapping[str, Any],
        *,
        manifest_run_root: str = "",
        local_run_root: Path | None = None,
        repo_dir: Path,
        scion_project_dir: Path,
    ) -> dict[str, dict[str, Any]]:
        """Return report-only prepared contract checks for this problem family."""

    def phase4_requirements(
        self,
        manifest: Mapping[str, Any],
        coverage_item: CoverageItemFactory,
    ) -> dict[str, Any]:
        """Return report-only phase-4 coverage requirements for this problem family."""


PreparedHandoffPortCollection = (
    Mapping[str, PreparedHandoffReviewPort] | Sequence[PreparedHandoffReviewPort]
)


def _prepared_handoff_ports_by_family(
    ports: PreparedHandoffPortCollection | None,
) -> dict[str, PreparedHandoffReviewPort]:
    if ports is None:
        return {}
    if isinstance(ports, Mapping):
        return {
            _normalize_problem_family(family): port
            for family, port in ports.items()
            if _normalize_problem_family(family)
        }
    by_family: dict[str, PreparedHandoffReviewPort] = {}
    for port in ports:
        family = _normalize_problem_family(getattr(port, "problem_family", ""))
        if family:
            by_family[family] = port
    return by_family
