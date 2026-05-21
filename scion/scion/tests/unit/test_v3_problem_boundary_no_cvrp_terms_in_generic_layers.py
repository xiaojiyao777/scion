from __future__ import annotations

import re
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
GENERIC_LAYER_DIRS = (
    "core",
    "proposal",
    "contract",
    "runtime",
    "protocol",
    "verification",
)

FORBIDDEN_PATTERNS = {
    "cvrp": re.compile(r"\bCVRP\b|\bCvrpSolution\b|from_cvrp_solution"),
    "alns": re.compile(r"\bALNS\b|\balns\b"),
    "vns": re.compile(r"\bVNS\b|\bvns\b"),
    "alns_vns_solver": re.compile(r"_ALNSVNSSolver"),
    "internal_solution_model": re.compile(r"_Solution|_Route"),
    "route": re.compile(r"(?<![A-Za-z0-9])routes?\b", re.IGNORECASE),
    "capacity": re.compile(r"(?<![A-Za-z0-9])capacity\b", re.IGNORECASE),
    "demand": re.compile(r"(?<![A-Za-z0-9])demands?\b", re.IGNORECASE),
    "customer": re.compile(r"(?<![A-Za-z0-9])customers?\b", re.IGNORECASE),
    "vehicle": re.compile(r"(?<![A-Za-z0-9])vehicles?\b", re.IGNORECASE),
    "depot": re.compile(r"(?<![A-Za-z0-9])depot\b", re.IGNORECASE),
    "solver_algorithm_fleet_violation": re.compile(
        r"solver_algorithm_fleet_violation"
    ),
    "solver_algorithm_total_distance": re.compile(
        r"solver_algorithm_total_distance"
    ),
}

# Keep this list intentionally small. Each entry is either non-domain wording
# that collides with a forbidden token, or documented legacy/P1 debt that has
# not yet been migrated behind provider declarations. Do not allowlist generic
# proposal prompt/schema files here; CVRP prompt semantics belong under
# scion/problems/cvrp.
LEGACY_ALLOWLIST: dict[tuple[str, str], str] = {
    ("core/campaign.py", "route"): "failure routing verb, not solution route",
    ("core/campaign_adapters.py", "capacity"): "branch scheduler capacity action",
    ("core/branch_step_runner.py", "capacity"): "branch scheduler capacity action",
    ("core/scheduler.py", "capacity"): "branch portfolio capacity, not problem capacity",
    ("core/failure_lifecycle.py", "route"): "FailureRouter.route method name",
    ("core/models.py", "vehicle"): "legacy SolverOutput compatibility field",
    (
        "runtime/subprocess_runner.py",
        "vehicle",
    ): "legacy SolverOutput compatibility adapter",
    (
        "verification/gate.py",
        "vehicle",
    ): "legacy pre-adapter solution consistency label",
    (
        "verification/state_mutation.py",
        "vehicle",
    ): "legacy pre-adapter solution consistency fallback",
    (
        "contract/gate.py",
        "route",
    ): "legacy complexity scale fallback for pre-v3 specs",
    (
        "contract/gate.py",
        "customer",
    ): "legacy complexity scale fallback for pre-v3 specs",
    (
        "contract/gate.py",
        "vehicle",
    ): "legacy complexity scale fallback for pre-v3 specs",
    (
        "runtime/workspace.py",
        "vns",
    ): "legacy default frozen-file compatibility pattern",
    (
        "proposal/solver_design_smoke/audit.py",
        "solver_algorithm_fleet_violation",
    ): "P1 smoke preview runtime diagnostics still use CVRP telemetry names",
    (
        "proposal/solver_design_smoke/audit.py",
        "solver_algorithm_total_distance",
    ): "P1 smoke preview runtime diagnostics still use CVRP telemetry names",
    (
        "proposal/tools/previews/algorithm_smoke_feedback_runtime.py",
        "solver_algorithm_fleet_violation",
    ): "P1 smoke preview runtime diagnostics still use CVRP telemetry names",
    (
        "proposal/tools/previews/algorithm_smoke_feedback_runtime.py",
        "solver_algorithm_total_distance",
    ): "P1 smoke preview runtime diagnostics still use CVRP telemetry names",
}


def test_generic_layers_do_not_contain_cvrp_solver_design_semantics() -> None:
    violations: list[str] = []
    for directory in GENERIC_LAYER_DIRS:
        for path in (PACKAGE_ROOT / directory).rglob("*.py"):
            relative = path.relative_to(PACKAGE_ROOT).as_posix()
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                for label, pattern in FORBIDDEN_PATTERNS.items():
                    if not pattern.search(line):
                        continue
                    if (relative, label) in LEGACY_ALLOWLIST:
                        continue
                    violations.append(
                        f"{relative}:{line_number}: {label}: {line.strip()}"
                    )

    assert not violations, (
        "Problem-specific solver-design semantics leaked into generic Scion "
        "layers. Move CVRP guidance to scion/problems/cvrp provider hooks or "
        "add a narrowly documented legacy allowlist entry if this is known "
        "compatibility debt.\n"
        + "\n".join(violations)
    )
