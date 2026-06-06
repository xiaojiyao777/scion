from __future__ import annotations

import ast
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
    "evidence",
)
GENERIC_PREVIEW_DIR = PACKAGE_ROOT / "proposal" / "tools" / "previews"

FORBIDDEN_PATTERNS = {
    "cvrp": re.compile(
        r"\bCVRP\b|\bcvrp\b|\bCvrpSolution\b|from_cvrp_solution"
    ),
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
    "fleet_violation": re.compile(r"\bfleet_violation\b"),
    "total_distance": re.compile(r"\btotal_distance\b"),
    "route_gap": re.compile(r"route_gap"),
    "bks_routes": re.compile(r"bks_routes"),
    "baseline_routes": re.compile(r"baseline_routes"),
    "candidate_routes": re.compile(r"candidate_routes"),
    "baseline_candidate_route_fields": re.compile(
        r"baseline_route_|candidate_route_"
    ),
    "cvrp_active_entrypoint_path": re.compile(r"policies/baseline_algorithm\.py"),
    "cvrp_active_support_package": re.compile(r"policies/baseline_modules"),
    "cvrp_legacy_solver_path": re.compile(r"policies/solver_algorithm\.py"),
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


def test_generic_preview_tools_do_not_hardcode_solver_algorithm_fields() -> None:
    violations: list[str] = []
    for path in GENERIC_PREVIEW_DIR.rglob("*.py"):
        relative = path.relative_to(PACKAGE_ROOT).as_posix()
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if "solver_algorithm_" not in line:
                continue
            violations.append(f"{relative}:{line_number}: {line.strip()}")

    assert not violations, (
        "Generic proposal preview tools must consume declared telemetry fields "
        "from problem/surface providers instead of hardcoding CVRP-shaped "
        "solver_algorithm_* names.\n"
        + "\n".join(violations)
    )


TAXONOMY_BOUNDARY_FILES = (
    "proposal/mechanism_novelty.py",
    "proposal/agentic_session_patch_flow.py",
    "proposal/agentic_session_hypothesis.py",
    "proposal/context_manager/guidance.py",
    "proposal/engine/solver_design_prompts.py",
    "proposal/agentic_code_context.py",
    "proposal/solver_design_smoke/constants.py",
    "runtime/audit.py",
)
FORBIDDEN_TAXONOMY_LITERALS = {
    "local_search",
    "destroy_repair",
    "construction",
    "acceptance",
    "construction_errors",
    "portfolio_errors",
    "policy_errors",
}
FORBIDDEN_TAXONOMY_SUBSTRINGS = (
    "construction.py",
    "destroy_repair.py",
    "local_search.py",
    "acceptance.py",
    "record_phase('construction'",
    'record_phase("construction"',
)


def test_generic_identity_paths_use_provider_declared_taxonomy() -> None:
    violations: list[str] = []
    for relative in TAXONOMY_BOUNDARY_FILES:
        path = PACKAGE_ROOT / relative
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            value = node.value
            stripped = value.strip()
            if stripped in FORBIDDEN_TAXONOMY_LITERALS or any(
                token in value for token in FORBIDDEN_TAXONOMY_SUBSTRINGS
            ):
                violations.append(
                    f"{relative}:{node.lineno}: {stripped[:120]}"
                )

    assert not violations, (
        "Generic identity/runtime paths must consume problem/provider-declared "
        "taxonomy instead of hardcoding CVRP solver phase, module, or counter "
        "names.\n"
        + "\n".join(violations)
    )
