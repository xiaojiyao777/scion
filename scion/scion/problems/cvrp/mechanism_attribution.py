"""CVRP-owned binding from changed solver symbols to ordinary observations.

This module is proposal-facing diagnostics only.  It does not participate in
Protocol gates or DecisionFeatures.  Generic Scion supplies an opaque
before/after source packet and paired runtime mappings; CVRP owns every symbol,
probe, and interpretation below.  The first vertical intentionally supports
only initial-solution selection and the VNS neighborhood family, for which the
current solver already emits direct ordinary observations.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

ATTRIBUTION_SCHEMA = "scion.cvrp.mechanism_attribution.v1"
_SUBJECT_SCHEMA = "scion.problem_proposal_subject.v1"
_MISSING = object()
_SOURCE_ROLES = {
    "construction.py": "construction",
    "local_search.py": "local_search",
    "scheduler.py": "scheduler",
}
_VNS_OWNED_SYMBOLS = frozenset(
    {
        "_default_vns_operators",
        "_or_opt",
        "_or_opt_1",
        "_or_opt_2",
        "_or_opt_3",
        "_relocate",
        "_swap",
        "_two_opt_intra",
        "_two_opt_star",
        "_vns",
    }
)


@dataclass(frozen=True)
class _Probe:
    signal: str
    observation_kind: str
    extractor: Callable[[Mapping[str, Any]], Any]


@dataclass(frozen=True)
class _MechanismFamily:
    family: str
    activation_probes: tuple[_Probe, ...]
    intermediate_probes: tuple[_Probe, ...]


def summarize_cvrp_mechanism_attribution(
    *,
    proposal_subject: Mapping[str, Any] | None,
    runtime_pairs: Sequence[Mapping[str, Any]],
    runtime_pairs_complete: bool = True,
) -> dict[str, Any]:
    """Bind changed CVRP symbols to declared safe runtime observations."""

    binding = _changed_symbol_binding(proposal_subject)
    if binding["status"] != "available":
        return _unavailable_attribution(
            status=str(binding["status"]),
            binding=binding,
        )
    if not runtime_pairs_complete:
        return _unavailable_attribution(
            status="unavailable_incomplete",
            binding=binding,
        )
    families = _matched_families(binding)
    if not families:
        return _unavailable_attribution(
            status="unavailable_unsupported",
            binding=binding,
        )

    activation = _summarize_probes(
        tuple(
            dict.fromkeys(
                probe for family in families for probe in family.activation_probes
            )
        ),
        runtime_pairs,
    )
    intermediate = _summarize_probes(
        tuple(
            dict.fromkeys(
                probe for family in families for probe in family.intermediate_probes
            )
        ),
        runtime_pairs,
    )
    if any(
        not any(
            item["observed_pairs"] > 0
            for item in _summarize_probes(
                family.activation_probes,
                runtime_pairs,
            )
        )
        for family in families
    ):
        status = "unavailable_legacy"
    elif any(item["different_pairs"] > 0 for item in activation):
        status = "family_observable_changed"
    else:
        status = "family_observable_unchanged"

    return {
        "schema_version": ATTRIBUTION_SCHEMA,
        "attribution_status": status,
        "attribution_resolution": "family_association",
        "exact_mechanism_activation": False,
        "interpretation_constraint": (
            "problem_owned_association_not_protocol_or_decision_evidence"
        ),
        "changed_source_roles": _changed_source_roles(binding),
        "changed_symbol_names": _changed_symbol_names(binding),
        "mechanism_families": [family.family for family in families],
        "activation_observations": activation,
        "intermediate_observations": intermediate,
    }


def _changed_symbol_binding(
    proposal_subject: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if (
        not isinstance(proposal_subject, Mapping)
        or proposal_subject.get("schema_version") != _SUBJECT_SCHEMA
    ):
        return {
            "status": "unavailable_legacy",
            "source_files": [],
            "symbol_changes": {},
        }
    raw_changes = proposal_subject.get("changes")
    if not isinstance(raw_changes, Sequence) or isinstance(raw_changes, (str, bytes)):
        return {
            "status": "unavailable_legacy",
            "source_files": [],
            "symbol_changes": {},
        }

    paths: list[str] = []
    symbols_by_path: dict[str, list[str]] = {}
    for raw_change in raw_changes:
        if not isinstance(raw_change, Mapping):
            return {
                "status": "unavailable_legacy",
                "source_files": [],
                "symbol_changes": {},
            }
        path = str(raw_change.get("file_path") or "").strip()
        action = str(raw_change.get("action") or "").strip()
        before = raw_change.get("before_source")
        after = raw_change.get("after_source")
        if not path or action not in {"modify", "create", "delete"}:
            return {
                "status": "unavailable_legacy",
                "source_files": [],
                "symbol_changes": {},
            }
        if action == "modify" and not isinstance(before, str):
            return {
                "status": "unavailable_legacy",
                "source_files": sorted(paths + [path]),
                "symbol_changes": symbols_by_path,
            }
        if action != "delete" and not isinstance(after, str):
            return {
                "status": "unavailable_legacy",
                "source_files": [],
                "symbol_changes": {},
            }
        try:
            changed = _changed_symbols(
                before if isinstance(before, str) else "",
                after if isinstance(after, str) else "",
            )
        except SyntaxError:
            return {
                "status": "unavailable_legacy",
                "source_files": sorted(paths + [path]),
                "symbol_changes": symbols_by_path,
            }
        if changed:
            paths.append(path)
            symbols_by_path[path] = list(changed)
    if not symbols_by_path:
        return {
            "status": "unavailable_current_source",
            "source_files": [],
            "symbol_changes": {},
        }
    return {
        "status": "available",
        "source_files": sorted(dict.fromkeys(paths)),
        "symbol_changes": {
            path: symbols_by_path[path] for path in sorted(symbols_by_path)
        },
    }


def _changed_symbols(before: str, after: str) -> tuple[str, ...]:
    before_tree = ast.parse(before)
    after_tree = ast.parse(after)
    before_symbols = _symbol_fingerprints(before_tree)
    after_symbols = _symbol_fingerprints(after_tree)
    changed = {
        symbol
        for symbol in before_symbols.keys() | after_symbols.keys()
        if before_symbols.get(symbol) != after_symbols.get(symbol)
    }
    if not changed and ast.dump(before_tree) != ast.dump(after_tree):
        changed.add("<module>")
    return tuple(sorted(changed))


def _symbol_fingerprints(tree: ast.AST) -> dict[str, str]:
    result: dict[str, str] = {}

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.scope: list[str] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

        def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            name = ".".join((*self.scope, node.name))
            result[name] = ast.dump(node, include_attributes=False)
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._visit_function(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._visit_function(node)

    Visitor().visit(tree)
    return result


def _matched_families(binding: Mapping[str, Any]) -> tuple[_MechanismFamily, ...]:
    changed_symbols = binding.get("symbol_changes")
    if not isinstance(changed_symbols, Mapping):
        return ()
    selected: list[_MechanismFamily] = []
    for path, raw_symbols in changed_symbols.items():
        symbols = {str(symbol) for symbol in raw_symbols or ()}
        if not symbols:
            continue
        path_text = str(path)
        if path_text.endswith("/scheduler.py"):
            if any(symbol.endswith("._initial_solution") for symbol in symbols):
                selected.append(_INITIAL_SOLUTION_FAMILY)
        elif path_text.endswith("/construction.py"):
            selected.append(_INITIAL_SOLUTION_FAMILY)
        elif path_text.endswith("/local_search.py") and (symbols & _VNS_OWNED_SYMBOLS):
            selected.append(_VNS_NEIGHBORHOOD_FAMILY)
    return tuple(dict.fromkeys(selected))


def _summarize_probes(
    probes: Sequence[_Probe],
    runtime_pairs: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    pairs = [pair for pair in runtime_pairs if isinstance(pair, Mapping)]
    for probe in probes:
        observed = 0
        different = 0
        for pair in pairs:
            candidate = pair.get("candidate_runtime")
            champion = pair.get("champion_runtime")
            if not isinstance(candidate, Mapping) or not isinstance(champion, Mapping):
                continue
            candidate_value = probe.extractor(candidate)
            champion_value = probe.extractor(champion)
            if candidate_value is _MISSING or champion_value is _MISSING:
                continue
            observed += 1
            different += int(not _observation_equal(candidate_value, champion_value))
        summaries.append(
            {
                "signal": probe.signal,
                "observation_kind": probe.observation_kind,
                "observed_pairs": observed,
                "different_pairs": different,
                "same_pairs": observed - different,
            }
        )
    return summaries


def _path(*parts: str) -> Callable[[Mapping[str, Any]], Any]:
    def extract(runtime: Mapping[str, Any]) -> Any:
        value: Any = runtime
        for part in parts:
            if not isinstance(value, Mapping) or part not in value:
                return _MISSING
            value = value[part]
        return value

    return extract


def _phase_runtime(*phases: str) -> Callable[[Mapping[str, Any]], Any]:
    def extract(runtime: Mapping[str, Any]) -> Any:
        values = runtime.get("solver_algorithm_phase_runtime_ms")
        if not isinstance(values, Mapping):
            return _MISSING
        present = [values[phase] for phase in phases if phase in values]
        if not present:
            return _MISSING
        try:
            return sum(float(value) for value in present)
        except (TypeError, ValueError):
            return _MISSING

    return extract


def _observation_equal(left: Any, right: Any) -> bool:
    if isinstance(left, (int, float)) and not isinstance(left, bool):
        if isinstance(right, (int, float)) and not isinstance(right, bool):
            return abs(float(left) - float(right)) <= 1e-12
    return left == right


def _unavailable_attribution(
    *,
    status: str,
    binding: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": ATTRIBUTION_SCHEMA,
        "attribution_status": status,
        "attribution_resolution": "family_association",
        "exact_mechanism_activation": False,
        "interpretation_constraint": (
            "problem_owned_association_not_protocol_or_decision_evidence"
        ),
        "changed_source_roles": _changed_source_roles(binding),
        "changed_symbol_names": _changed_symbol_names(binding),
        "mechanism_families": [],
        "activation_observations": [],
        "intermediate_observations": [],
    }


def _changed_source_roles(binding: Mapping[str, Any]) -> list[str]:
    return sorted(
        {
            _source_role(str(path))
            for path in binding.get("source_files") or ()
            if _source_role(str(path))
        }
    )


def _changed_symbol_names(binding: Mapping[str, Any]) -> list[str]:
    raw = binding.get("symbol_changes")
    if not isinstance(raw, Mapping):
        return []
    return sorted(
        {
            str(symbol)
            for symbols in raw.values()
            for symbol in symbols or ()
            if str(symbol)
        }
    )


def _source_role(path: str) -> str:
    normalized = str(path or "").replace("\\", "/").strip("/")
    filename = normalized.rsplit("/", 1)[-1]
    return _SOURCE_ROLES.get(filename, "")


_INITIAL_STATE_DISTANCE = _Probe(
    "initial_solution_selected_distance",
    "selected_initial_state",
    _path("solver_algorithm_solution_progress", "initial_total_distance"),
)
_INITIAL_STATE_ROUTES = _Probe(
    "initial_solution_selected_route_count",
    "selected_initial_state",
    _path("solver_algorithm_solution_progress", "initial_route_count"),
)
_FINAL_DISTANCE = _Probe(
    "final_solution_distance",
    "downstream_search_state",
    _path("solver_algorithm_solution_progress", "final_total_distance"),
)
_VNS_ATTEMPTS = _Probe(
    "vns_move_attempts",
    "search_work",
    _path("solver_algorithm_phase_move_attempts", "vns"),
)
_VNS_ACCEPTED = _Probe(
    "vns_accepted_moves",
    "accepted_route_state_transition",
    _path("solver_algorithm_phase_accepted_moves", "vns"),
)
_VNS_IMPROVEMENTS = _Probe(
    "vns_improvement_count",
    "direct_intermediate_effect",
    _path("solver_algorithm_phase_improvement_counts", "vns"),
)
_VNS_DELTA = _Probe(
    "vns_delta_sum",
    "direct_intermediate_effect",
    _path("solver_algorithm_phase_delta_sum", "vns"),
)
_VNS_RUNTIME = _Probe(
    "vns_phase_runtime_ms",
    "search_cost",
    _phase_runtime("vns_initial", "vns_embedded"),
)
_INITIAL_SOLUTION_FAMILY = _MechanismFamily(
    family="initial_solution_selection",
    activation_probes=(_INITIAL_STATE_DISTANCE, _INITIAL_STATE_ROUTES),
    intermediate_probes=(_FINAL_DISTANCE,),
)
_VNS_NEIGHBORHOOD_FAMILY = _MechanismFamily(
    family="vns_neighborhood",
    activation_probes=(
        _VNS_ATTEMPTS,
        _VNS_ACCEPTED,
        _VNS_IMPROVEMENTS,
        _VNS_DELTA,
    ),
    intermediate_probes=(_VNS_ATTEMPTS, _VNS_RUNTIME, _FINAL_DISTANCE),
)


__all__ = [
    "ATTRIBUTION_SCHEMA",
    "summarize_cvrp_mechanism_attribution",
]
