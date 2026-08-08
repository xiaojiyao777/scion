"""Proposal-only CVRP search-allocation evidence from existing observations.

CVRP/ALNS/VNS semantics stay in this problem-owned module.  The projection
consumes a fixed runtime allowlist and never copies a raw runtime, trace row,
case identity, seed, path, or load error into proposal context.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from statistics import median
from typing import Any

from scion.problems.cvrp.cvrplib import load_cvrplib_instance


SCHEMA_VERSION = "scion.cvrp.search_allocation_evidence.v1"
_PAIR_KEY_ENCODING = "component:%=>%25,__=>%5F%5F;join:__"

_ELAPSED = "solver_algorithm_elapsed_ms"
_PHASE_RUNTIME = "solver_algorithm_phase_runtime_ms"
_TRACE = "solver_algorithm_alns_iteration_trace"
_ACCEPTANCE_REASONS = frozenset(
    {
        "destroy_empty",
        "repair_error",
        "infeasible",
        "route_limit",
        "new_best",
        "improves_current",
        "annealing_accept",
        "rejected",
    }
)
_NO_POLISH_REASONS = frozenset({"destroy_empty", "repair_error"})
_MOVE_FIELDS = {
    "attempted": ("solver_algorithm_phase_move_attempts", "int"),
    "accepted": ("solver_algorithm_phase_accepted_moves", "int"),
    "improvement_count": (
        "solver_algorithm_phase_improvement_counts",
        "int",
    ),
    "delta_sum": ("solver_algorithm_phase_delta_sum", "float"),
    "best_delta": ("solver_algorithm_phase_best_delta", "float"),
}


@dataclass(frozen=True)
class _ObservedMap:
    values: dict[str, int | float]
    complete: bool

    @property
    def usable(self) -> bool:
        return self.complete or bool(self.values)


@dataclass(frozen=True)
class _RuntimeObservation:
    elapsed_ms: int | None
    phase_runtime_ms: _ObservedMap | None
    trace: tuple[Mapping[str, Any], ...] | None
    malformed_trace_events: int
    trace_field_malformed: bool
    move_fields: dict[str, _ObservedMap | None]

    @property
    def observed_field_count(self) -> int:
        return sum(
            (
                self.elapsed_ms is not None,
                self.phase_runtime_ms is not None
                and self.phase_runtime_ms.usable,
                self.trace is not None,
                *(
                    value is not None and value.usable
                    for value in self.move_fields.values()
                ),
            )
        )

    @property
    def usable(self) -> bool:
        return self.observed_field_count > 0


@dataclass
class _Lifecycle:
    selected: int = 0
    nonempty: int = 0
    empty: int = 0
    invoked: int = 0
    completed: int = 0
    accepted: int = 0
    best_updates: int = 0
    outcome_observed: int = 0
    accepted_observed: int = 0
    best_observed: int = 0
    elapsed_observed: int = 0
    elapsed_total: int = 0

    def observe(
        self,
        *,
        reason: str | None,
        accepted: bool | None,
        best: bool | None,
        elapsed: int | None,
    ) -> None:
        self.selected += 1
        if reason is not None:
            self.outcome_observed += 1
            if reason == "destroy_empty":
                self.empty += 1
            else:
                self.nonempty += 1
                self.invoked += 1
                if reason != "repair_error":
                    self.completed += 1
        repair_invoked = reason is not None and reason != "destroy_empty"
        if accepted is not None and repair_invoked:
            self.accepted_observed += 1
            self.accepted += int(accepted)
        if best is not None and repair_invoked:
            self.best_observed += 1
            self.best_updates += int(best)
        if elapsed is not None:
            self.elapsed_observed += 1
            self.elapsed_total += elapsed

    def render(self, kind: str) -> dict[str, Any]:
        fields = {"selected": self.selected}
        coverage: dict[str, int] = {}
        if kind in {"destroy", "pair"}:
            fields.update(
                nonempty=(
                    self.nonempty
                    if self.outcome_observed == self.selected
                    else None
                ),
                empty=(
                    self.empty if self.outcome_observed == self.selected else None
                ),
            )
            coverage["destroy_outcome"] = self.outcome_observed
        if kind in {"repair", "pair"}:
            fields.update(
                invoked=(
                    self.invoked
                    if self.outcome_observed == self.selected
                    else None
                ),
                completed=(
                    self.completed
                    if self.outcome_observed == self.selected
                    else None
                ),
                accepted=(
                    self.accepted
                    if self.outcome_observed == self.selected
                    and self.accepted_observed == self.invoked
                    else None
                ),
                best_updates=(
                    self.best_updates
                    if self.outcome_observed == self.selected
                    and self.best_observed == self.invoked
                    else None
                ),
            )
            coverage.update(
                repair_lifecycle=self.outcome_observed,
                accepted=self.accepted_observed,
                best_updates=self.best_observed,
            )
        fields["selected_iteration_elapsed_ms"] = {
            "observed": self.elapsed_observed,
            "total": (
                self.elapsed_total
                if self.elapsed_observed == self.selected
                else None
            ),
            "mean": (
                _rounded(self.elapsed_total / self.elapsed_observed)
                if self.elapsed_observed == self.selected and self.elapsed_observed
                else None
            ),
        }
        fields["coverage"] = coverage
        return fields


@dataclass
class _TraceState:
    iterations: int = 0
    accepted: int = 0
    best_updates: int = 0
    route_limit: int = 0
    repair_error: int = 0
    reason_observed: int = 0
    accepted_observed: int = 0
    best_observed: int = 0
    elapsed_observed: int = 0
    polish_observed: int = 0
    polish_improved: int = 0
    polish_unchanged: int = 0
    polish_worsened: int = 0
    polish_delta_sum: float = 0.0
    polish_classified: int = 0
    destroy_identity_observed: int = 0
    repair_identity_observed: int = 0
    pair_identity_observed: int = 0
    destroys: dict[str, _Lifecycle] = field(default_factory=dict)
    repairs: dict[str, _Lifecycle] = field(default_factory=dict)
    pairs: dict[str, _Lifecycle] = field(default_factory=dict)

    def observe(self, event: Mapping[str, Any]) -> None:
        self.iterations += 1
        reason = _acceptance_reason(event.get("acceptance_reason"))
        accepted = _explicit_bool(event.get("accepted"))
        best = _explicit_bool(event.get("best_improved"))
        elapsed = _iteration_elapsed_ms(event)
        destroy = _nonempty_string(event.get("destroy_operator"))
        repair = _nonempty_string(event.get("repair_operator"))

        if reason is not None:
            self.reason_observed += 1
            self.route_limit += int(reason == "route_limit")
            self.repair_error += int(reason == "repair_error")
        if accepted is not None:
            self.accepted_observed += 1
            self.accepted += int(accepted)
        if best is not None:
            self.best_observed += 1
            self.best_updates += int(best)
        self.elapsed_observed += int(elapsed is not None)

        if destroy is not None:
            self.destroy_identity_observed += 1
            self.destroys.setdefault(destroy, _Lifecycle()).observe(
                reason=reason,
                accepted=accepted,
                best=best,
                elapsed=elapsed,
            )
        if repair is not None:
            self.repair_identity_observed += 1
            self.repairs.setdefault(repair, _Lifecycle()).observe(
                reason=reason,
                accepted=accepted,
                best=best,
                elapsed=elapsed,
            )
        if destroy is not None and repair is not None:
            self.pair_identity_observed += 1
            self.pairs.setdefault(
                _pair_identity_key(destroy, repair),
                _Lifecycle(),
            ).observe(
                reason=reason,
                accepted=accepted,
                best=best,
                elapsed=elapsed,
            )

        before = _nonnegative_float(event.get("candidate_after_repair_distance"))
        after = _nonnegative_float(event.get("candidate_after_polish_distance"))
        if before is None or after is None:
            self.polish_classified += int(reason in _NO_POLISH_REASONS)
            return
        self.polish_classified += 1
        self.polish_observed += 1
        delta = before - after
        self.polish_delta_sum += delta
        self.polish_improved += int(delta > 0.0)
        self.polish_unchanged += int(delta == 0.0)
        self.polish_worsened += int(delta < 0.0)

    def render(
        self,
        *,
        trace_observed: bool,
        malformed_events: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if not trace_observed:
            return (
                {
                    "alns": {
                        "iterations": None,
                        "accepted": None,
                        "best_updates": None,
                        "route_limit": None,
                        "repair_error": None,
                    },
                    "post_repair_polish": {
                        "observed": None,
                        "improved": None,
                        "unchanged": None,
                        "worsened": None,
                        "delta_sum": None,
                    },
                    "destroy_operators": {},
                    "repair_operators": {},
                    "destroy_repair_pairs": {},
                },
                _empty_trace_coverage(),
            )
        fields_complete = malformed_events == 0
        return (
            {
                "alns": {
                    "iterations": self.iterations,
                    "accepted": (
                        self.accepted
                        if fields_complete
                        and self.accepted_observed == self.iterations
                        else None
                    ),
                    "best_updates": (
                        self.best_updates
                        if fields_complete and self.best_observed == self.iterations
                        else None
                    ),
                    "route_limit": (
                        self.route_limit
                        if fields_complete and self.reason_observed == self.iterations
                        else None
                    ),
                    "repair_error": (
                        self.repair_error
                        if fields_complete and self.reason_observed == self.iterations
                        else None
                    ),
                },
                "post_repair_polish": {
                    "observed": (
                        self.polish_observed
                        if fields_complete
                        and self.polish_classified == self.iterations
                        else None
                    ),
                    "improved": (
                        self.polish_improved
                        if fields_complete
                        and self.polish_classified == self.iterations
                        else None
                    ),
                    "unchanged": (
                        self.polish_unchanged
                        if fields_complete
                        and self.polish_classified == self.iterations
                        else None
                    ),
                    "worsened": (
                        self.polish_worsened
                        if fields_complete
                        and self.polish_classified == self.iterations
                        else None
                    ),
                    "delta_sum": (
                        _rounded(self.polish_delta_sum)
                        if fields_complete
                        and self.polish_classified == self.iterations
                        else None
                    ),
                },
                "destroy_operators": _render_lifecycles(self.destroys, "destroy"),
                "repair_operators": _render_lifecycles(self.repairs, "repair"),
                "destroy_repair_pairs": _render_lifecycles(self.pairs, "pair"),
            },
            {
                "acceptance_reason_events": self.reason_observed,
                "accepted_events": self.accepted_observed,
                "best_improved_events": self.best_observed,
                "selected_iteration_elapsed_events": self.elapsed_observed,
                "post_repair_polish_events": self.polish_observed,
                "post_repair_polish_classified_events": self.polish_classified,
                "destroy_operator_events": self.destroy_identity_observed,
                "repair_operator_events": self.repair_identity_observed,
                "pair_operator_events": self.pair_identity_observed,
            },
        )


def build_search_allocation_evidence(
    runtime_pairs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build one screening-only, association-only CVRP evidence packet."""

    pairs = [pair for pair in runtime_pairs if isinstance(pair, Mapping)]
    observations = [
        (
            _runtime_observation(pair.get("candidate_runtime")),
            _runtime_observation(pair.get("champion_runtime")),
        )
        for pair in pairs
    ]
    candidate, candidate_coverage = _side_summary(
        [candidate for candidate, _ in observations if candidate is not None]
    )
    champion, champion_coverage = _side_summary(
        [champion for _, champion in observations if champion is not None]
    )
    comparison, paired_coverage = _paired_comparison(observations)
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_scope": "screening_search_allocation",
        "hypothesis_attribution": "unbound",
        "interpretation_constraint": "association_only",
        "gate_influence": False,
        "coverage": {
            "provider_inputs": len(pairs),
            "runtime_pairs": sum(
                bool(
                    (candidate is not None and candidate.usable)
                    or (champion is not None and champion.usable)
                )
                for candidate, champion in observations
            ),
            "missing_semantics": "unavailable_not_zero",
            "destroy_repair_pair_key_encoding": _PAIR_KEY_ENCODING,
            "runtime_accounting": {
                "phase_share_denominator": "solver_algorithm_elapsed_ms",
                "runtime_residual": (
                    "solver_algorithm_elapsed_ms_minus_explicit_phase_runtime_ms"
                ),
                "move_phase_counters_are_additive_phase_runtime": False,
            },
            "candidate": candidate_coverage,
            "champion": champion_coverage,
            "paired": paired_coverage,
        },
        "candidate": candidate,
        "champion": champion,
        "comparison": comparison,
        "instance_feasibility": _instance_feasibility(pairs),
    }


def has_search_allocation_observations(packet: Mapping[str, Any]) -> bool:
    """Return whether a packet contains runtime or instance observations."""

    coverage = packet.get("coverage")
    if isinstance(coverage, Mapping):
        for side in ("candidate", "champion"):
            side_coverage = coverage.get(side)
            if isinstance(side_coverage, Mapping) and _nonnegative_int(
                side_coverage.get("observed_runtime_fields")
            ):
                return True
    feasibility = packet.get("instance_feasibility")
    if isinstance(feasibility, Mapping):
        instance_coverage = feasibility.get("coverage")
        if isinstance(instance_coverage, Mapping):
            requested = _nonnegative_int(instance_coverage.get("requested_cases"))
            if requested:
                return True
    return False


def _runtime_observation(value: Any) -> _RuntimeObservation | None:
    if not isinstance(value, Mapping):
        return None
    allowlist_fields = {_ELAPSED, _PHASE_RUNTIME, _TRACE} | {
        runtime_field for runtime_field, _kind in _MOVE_FIELDS.values()
    }
    if not any(field in value for field in allowlist_fields):
        return None
    trace_value = value.get(_TRACE)
    trace = (
        tuple(event for event in trace_value if _valid_trace_event(event))
        if isinstance(trace_value, list)
        else None
    )
    return _RuntimeObservation(
        elapsed_ms=_nonnegative_int(value.get(_ELAPSED)),
        phase_runtime_ms=_observed_map(value.get(_PHASE_RUNTIME), "int"),
        trace=trace,
        malformed_trace_events=(
            len(trace_value) - len(trace)
            if isinstance(trace_value, list) and trace is not None
            else 0
        ),
        trace_field_malformed=(_TRACE in value and not isinstance(trace_value, list)),
        move_fields={
            metric: _observed_map(value.get(runtime_field), kind)
            for metric, (runtime_field, kind) in _MOVE_FIELDS.items()
        },
    )


def _side_summary(
    observations: Sequence[_RuntimeObservation],
) -> tuple[dict[str, Any], dict[str, Any]]:
    elapsed_values = [
        obs.elapsed_ms for obs in observations if obs.elapsed_ms is not None
    ]
    phase_maps = [
        obs.phase_runtime_ms
        for obs in observations
        if obs.phase_runtime_ms is not None and obs.phase_runtime_ms.usable
    ]
    trace_observations = [obs for obs in observations if obs.trace is not None]
    trace_summary, trace_coverage = _trace_summary(trace_observations)
    shares, residual, accounting_pairs = _phase_accounting(observations)
    throughput, throughput_pairs = _throughput(observations)
    move_phases, move_coverage = _move_phase_summary(observations)
    return (
        {
            "solver_algorithm_elapsed_ms": (
                sum(elapsed_values) if elapsed_values else None
            ),
            "phase_runtime_ms": _sum_maps(phase_maps),
            "phase_runtime_share": shares,
            "runtime_residual_ms": residual,
            "alns": {
                **trace_summary["alns"],
                "iterations_per_second": throughput,
            },
            "post_repair_polish": trace_summary["post_repair_polish"],
            "destroy_operators": trace_summary["destroy_operators"],
            "repair_operators": trace_summary["repair_operators"],
            "destroy_repair_pairs": trace_summary["destroy_repair_pairs"],
            "move_phases": move_phases,
        },
        {
            "runtime_mapping_inputs": len(observations),
            "runtime_mapping_pairs": sum(obs.usable for obs in observations),
            "observed_runtime_fields": sum(
                obs.observed_field_count for obs in observations
            ),
            "solver_algorithm_elapsed_ms_pairs": len(elapsed_values),
            "phase_runtime_ms_pairs": len(phase_maps),
            "phase_runtime_ms_mapping_coverage": _mapping_coverage(
                [obs.phase_runtime_ms for obs in observations]
            ),
            "phase_accounting_pairs": accounting_pairs,
            "alns_throughput_pairs": throughput_pairs,
            "trace_pairs": len(trace_observations),
            "trace_events": sum(
                len(obs.trace or ()) for obs in trace_observations
            ),
            "malformed_trace_events": sum(
                obs.malformed_trace_events for obs in observations
            ),
            "malformed_trace_fields": sum(
                obs.trace_field_malformed for obs in observations
            ),
            **trace_coverage,
            "trace_field_complete_pairs": _trace_field_complete_pairs(
                trace_observations
            ),
            "move_field_mapping_coverage": {
                metric: _mapping_coverage(
                    [obs.move_fields[metric] for obs in observations]
                )
                for metric in _MOVE_FIELDS
            },
            "move_phases": move_coverage,
        },
    )


def _trace_summary(
    observations: Sequence[_RuntimeObservation],
) -> tuple[dict[str, Any], dict[str, Any]]:
    state = _TraceState()
    for observation in observations:
        for event in observation.trace or ():
            state.observe(event)
    return state.render(
        trace_observed=bool(observations),
        malformed_events=sum(obs.malformed_trace_events for obs in observations),
    )


def _empty_trace_coverage() -> dict[str, Any]:
    return {
        "acceptance_reason_events": 0,
        "accepted_events": 0,
        "best_improved_events": 0,
        "selected_iteration_elapsed_events": 0,
        "post_repair_polish_events": 0,
        "post_repair_polish_classified_events": 0,
        "destroy_operator_events": 0,
        "repair_operator_events": 0,
        "pair_operator_events": 0,
    }


def _render_lifecycles(
    values: Mapping[str, _Lifecycle],
    kind: str,
) -> dict[str, Any]:
    return {name: values[name].render(kind) for name in sorted(values)}


def _phase_accounting(
    observations: Sequence[_RuntimeObservation],
) -> tuple[dict[str, float | None], int | None, int]:
    usable = [
        obs
        for obs in observations
        if obs.elapsed_ms is not None
        and obs.phase_runtime_ms is not None
        and obs.phase_runtime_ms.complete
    ]
    if not usable:
        return {}, None, 0
    elapsed = sum(obs.elapsed_ms or 0 for obs in usable)
    phases = _sum_maps([obs.phase_runtime_ms for obs in usable if obs.phase_runtime_ms])
    shares = {
        phase: (_rounded(value / elapsed) if elapsed > 0 else None)
        for phase, value in phases.items()
    }
    return shares, elapsed - int(sum(phases.values())), len(usable)


def _throughput(
    observations: Sequence[_RuntimeObservation],
) -> tuple[float | None, int]:
    usable = [
        obs
        for obs in observations
        if obs.elapsed_ms is not None
        and obs.trace is not None
        and obs.malformed_trace_events == 0
    ]
    elapsed = sum(obs.elapsed_ms or 0 for obs in usable)
    iterations = sum(len(obs.trace or ()) for obs in usable)
    value = _rounded(iterations * 1000.0 / elapsed) if elapsed > 0 else None
    return value, len(usable)


def _move_phase_summary(
    observations: Sequence[_RuntimeObservation],
) -> tuple[dict[str, Any], dict[str, Any]]:
    phases = sorted(
        {
            phase
            for obs in observations
            for observed in obs.move_fields.values()
            if observed is not None
            for phase in observed.values
        }
    )
    summary: dict[str, Any] = {}
    coverage: dict[str, Any] = {}
    for phase in phases:
        values: dict[str, Any] = {}
        observed_counts: dict[str, int] = {}
        for metric in _MOVE_FIELDS:
            total: int | float = 0
            observed_count = 0
            for obs in observations:
                observed = obs.move_fields[metric]
                if observed is None:
                    continue
                if phase in observed.values:
                    total += observed.values[phase]
                    observed_count += 1
                elif observed.complete:
                    observed_count += 1
            values[metric] = _rounded(total) if observed_count else None
            observed_counts[metric] = observed_count
        values["coverage"] = observed_counts
        summary[phase] = values
        coverage[phase] = observed_counts
    return summary, coverage


def _paired_comparison(
    observations: Sequence[
        tuple[_RuntimeObservation | None, _RuntimeObservation | None]
    ],
) -> tuple[dict[str, Any], dict[str, Any]]:
    paired = [
        (candidate, champion)
        for candidate, champion in observations
        if candidate is not None and champion is not None
    ]
    elapsed = _paired_scalar(
        paired,
        lambda obs: obs.elapsed_ms,
    )
    residual = _paired_scalar(paired, _observation_residual)
    phase_runtime, phase_runtime_pairs = _paired_observed_maps(
        paired,
        lambda obs: obs.phase_runtime_ms,
    )

    accounting_pairs = [
        (candidate, champion)
        for candidate, champion in paired
        if _has_phase_accounting(candidate) and _has_phase_accounting(champion)
    ]
    candidate_shares, _, _ = _phase_accounting(
        [candidate for candidate, _ in accounting_pairs]
    )
    champion_shares, _, _ = _phase_accounting(
        [champion for _, champion in accounting_pairs]
    )
    phase_share = _compare_flat_maps(
        candidate_shares,
        champion_shares,
        len(accounting_pairs),
    )

    trace_pairs = [
        (candidate, champion)
        for candidate, champion in paired
        if candidate.trace is not None and champion.trace is not None
    ]
    trace_records = [
        (
            candidate,
            champion,
            _trace_summary([candidate])[0],
            _trace_summary([champion])[0],
        )
        for candidate, champion in trace_pairs
    ]
    trace_count = len(trace_pairs)
    alns = {
        field: _paired_rendered_metric(trace_records, "alns", field)
        for field in (
            "iterations",
            "accepted",
            "best_updates",
            "route_limit",
            "repair_error",
        )
    }
    throughput_pairs = [
        (candidate, champion)
        for candidate, champion in trace_pairs
        if candidate.elapsed_ms is not None and champion.elapsed_ms is not None
        and candidate.malformed_trace_events == 0
        and champion.malformed_trace_events == 0
    ]
    candidate_throughput, _ = _throughput(
        [candidate for candidate, _ in throughput_pairs]
    )
    champion_throughput, _ = _throughput(
        [champion for _, champion in throughput_pairs]
    )
    alns["iterations_per_second"] = _metric_delta(
        candidate_throughput,
        champion_throughput,
        len(throughput_pairs),
    )
    polish = {
        field: _paired_rendered_metric(
            trace_records,
            "post_repair_polish",
            field,
        )
        for field in ("observed", "improved", "unchanged", "worsened", "delta_sum")
    }
    operator_tables = {
        key: _compare_operator_table_pairs(
            trace_records,
            key,
        )
        for key in ("destroy_operators", "repair_operators", "destroy_repair_pairs")
    }

    move_phases: dict[str, Any] = {}
    move_coverage: dict[str, Any] = {}
    for metric in _MOVE_FIELDS:
        comparison, metric_coverage = _paired_observed_maps(
            paired,
            lambda obs, name=metric: obs.move_fields[name],
        )
        for phase, value in comparison.items():
            move_phases.setdefault(phase, {})[metric] = value
            move_coverage.setdefault(phase, {})[metric] = metric_coverage.get(
                phase, 0
            )

    return (
        {
            "solver_algorithm_elapsed_ms": elapsed,
            "phase_runtime_ms": phase_runtime,
            "phase_runtime_share": phase_share,
            "runtime_residual_ms": residual,
            "alns": alns,
            "post_repair_polish": polish,
            **operator_tables,
            "move_phases": {
                phase: move_phases[phase] for phase in sorted(move_phases)
            },
        },
        {
            "solver_algorithm_elapsed_ms_pairs": elapsed["observed_pairs"],
            "phase_runtime_ms_pairs": max(phase_runtime_pairs.values(), default=0),
            "phase_accounting_pairs": len(accounting_pairs),
            "runtime_residual_ms_pairs": residual["observed_pairs"],
            "trace_pairs": trace_count,
            "alns_throughput_pairs": len(throughput_pairs),
            "move_phases": move_coverage,
        },
    )


def _paired_scalar(
    paired: Sequence[tuple[_RuntimeObservation, _RuntimeObservation]],
    getter: Any,
) -> dict[str, Any]:
    candidate_total: int | float = 0
    champion_total: int | float = 0
    observed = 0
    for candidate, champion in paired:
        candidate_value = getter(candidate)
        champion_value = getter(champion)
        if candidate_value is None or champion_value is None:
            continue
        candidate_total += candidate_value
        champion_total += champion_value
        observed += 1
    return _metric_delta(
        candidate_total if observed else None,
        champion_total if observed else None,
        observed,
    )


def _paired_observed_maps(
    paired: Sequence[tuple[_RuntimeObservation, _RuntimeObservation]],
    getter: Any,
) -> tuple[dict[str, Any], dict[str, int]]:
    maps = [
        (candidate_map, champion_map)
        for candidate, champion in paired
        if (candidate_map := getter(candidate)) is not None
        and (champion_map := getter(champion)) is not None
    ]
    keys = sorted(
        {
            key
            for candidate, champion in maps
            for observed in (candidate, champion)
            for key in observed.values
        }
    )
    comparison: dict[str, Any] = {}
    coverage: dict[str, int] = {}
    for key in keys:
        candidate_total: int | float = 0
        champion_total: int | float = 0
        observed_count = 0
        for candidate, champion in maps:
            if not _map_key_observed(candidate, key) or not _map_key_observed(
                champion, key
            ):
                continue
            candidate_total += candidate.values.get(key, 0)
            champion_total += champion.values.get(key, 0)
            observed_count += 1
        comparison[key] = _metric_delta(
            candidate_total if observed_count else None,
            champion_total if observed_count else None,
            observed_count,
        )
        coverage[key] = observed_count
    return comparison, coverage


def _compare_flat_maps(
    candidate: Mapping[str, int | float | None],
    champion: Mapping[str, int | float | None],
    observed_pairs: int,
) -> dict[str, Any]:
    return {
        key: _metric_delta(
            candidate.get(key, 0),
            champion.get(key, 0),
            observed_pairs,
        )
        for key in sorted(set(candidate) | set(champion))
    }


def _paired_rendered_metric(
    records: Sequence[tuple[Any, Any, Mapping[str, Any], Mapping[str, Any]]],
    section: str,
    field_name: str,
) -> dict[str, Any]:
    candidate_total: int | float = 0
    champion_total: int | float = 0
    observed = 0
    for candidate_obs, champion_obs, candidate, champion in records:
        if not _trace_metric_complete(candidate_obs, section, field_name) or not (
            _trace_metric_complete(champion_obs, section, field_name)
        ):
            continue
        candidate_value = candidate[section].get(field_name)
        champion_value = champion[section].get(field_name)
        if candidate_value is None or champion_value is None:
            continue
        candidate_total += candidate_value
        champion_total += champion_value
        observed += 1
    return _metric_delta(
        candidate_total if observed else None,
        champion_total if observed else None,
        observed,
    )


def _trace_metric_complete(
    observation: _RuntimeObservation,
    section: str,
    field_name: str,
) -> bool:
    if section == "post_repair_polish":
        return _trace_field_complete(observation, "post_repair_polish")
    trace_field = {
        "iterations": "iteration",
        "accepted": "accepted",
        "best_updates": "best_improved",
        "route_limit": "acceptance_reason",
        "repair_error": "acceptance_reason",
    }[field_name]
    return _trace_field_complete(observation, trace_field)


def _compare_operator_table_pairs(
    records: Sequence[tuple[Any, Any, Mapping[str, Any], Mapping[str, Any]]],
    table_name: str,
) -> dict[str, Any]:
    names = sorted(
        {
            name
            for _candidate_obs, _champion_obs, candidate, champion in records
            for table in (candidate[table_name], champion[table_name])
            for name in table
        }
    )
    comparison: dict[str, Any] = {}
    for name in names:
        fields = sorted(
            {
                field_name
                for _candidate_obs, _champion_obs, candidate, champion in records
                for table in (candidate[table_name], champion[table_name])
                for field_name in table.get(name, {})
                if field_name not in {"coverage", "selected_iteration_elapsed_ms"}
            }
        )
        record = {
            field_name: _paired_operator_metric(
                records,
                table_name,
                name,
                field_name,
            )
            for field_name in fields
        }
        record["selected_iteration_elapsed_ms"] = _paired_operator_timing(
            records,
            table_name,
            name,
        )
        comparison[name] = record
    return comparison


def _paired_operator_metric(
    records: Sequence[tuple[Any, Any, Mapping[str, Any], Mapping[str, Any]]],
    table_name: str,
    operator_name: str,
    field_name: str,
) -> dict[str, Any]:
    candidate_total: int | float = 0
    champion_total: int | float = 0
    observed = 0
    for candidate_obs, champion_obs, candidate, champion in records:
        candidate_value = _operator_field_value(
            candidate_obs,
            candidate[table_name],
            table_name,
            operator_name,
            field_name,
        )
        champion_value = _operator_field_value(
            champion_obs,
            champion[table_name],
            table_name,
            operator_name,
            field_name,
        )
        if candidate_value is None or champion_value is None:
            continue
        candidate_total += candidate_value
        champion_total += champion_value
        observed += 1
    return _metric_delta(
        candidate_total if observed else None,
        champion_total if observed else None,
        observed,
    )


def _operator_field_value(
    observation: _RuntimeObservation,
    table: Mapping[str, Mapping[str, Any]],
    table_name: str,
    operator_name: str,
    field_name: str,
) -> int | float | None:
    if not _operator_field_complete(observation, table_name, field_name):
        return None
    record = table.get(operator_name)
    if record is not None:
        value = record.get(field_name)
        return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None
    return 0


def _paired_operator_timing(
    records: Sequence[tuple[Any, Any, Mapping[str, Any], Mapping[str, Any]]],
    table_name: str,
    operator_name: str,
) -> dict[str, Any]:
    candidate_observed = champion_observed = 0
    candidate_total = champion_total = 0
    observed_pairs = 0
    for candidate_obs, champion_obs, candidate, champion in records:
        candidate_values = _operator_timing_values(
            candidate_obs,
            candidate[table_name],
            table_name,
            operator_name,
        )
        champion_values = _operator_timing_values(
            champion_obs,
            champion[table_name],
            table_name,
            operator_name,
        )
        if candidate_values is None or champion_values is None:
            continue
        candidate_observed += candidate_values[0]
        candidate_total += candidate_values[1]
        champion_observed += champion_values[0]
        champion_total += champion_values[1]
        observed_pairs += 1
    candidate_mean = (
        _rounded(candidate_total / candidate_observed)
        if candidate_observed
        else None
    )
    champion_mean = (
        _rounded(champion_total / champion_observed)
        if champion_observed
        else None
    )
    return {
        "observed": _metric_delta(
            candidate_observed if observed_pairs else None,
            champion_observed if observed_pairs else None,
            observed_pairs,
        ),
        "total": _metric_delta(
            candidate_total if observed_pairs else None,
            champion_total if observed_pairs else None,
            observed_pairs,
        ),
        "mean": _metric_delta(candidate_mean, champion_mean, observed_pairs),
    }


def _operator_timing_values(
    observation: _RuntimeObservation,
    table: Mapping[str, Mapping[str, Any]],
    table_name: str,
    operator_name: str,
) -> tuple[int, int] | None:
    if not _operator_field_complete(
        observation,
        table_name,
        "selected_iteration_elapsed_ms",
    ):
        return None
    record = table.get(operator_name)
    if record is None:
        return 0, 0
    timing = record["selected_iteration_elapsed_ms"]
    total = timing.get("total")
    observed = timing.get("observed")
    if not isinstance(total, int) or not isinstance(observed, int):
        return None
    return observed, total


def _operator_identity_complete(
    observation: _RuntimeObservation,
    table_name: str,
) -> bool:
    field_name = {
        "destroy_operators": "destroy_operator",
        "repair_operators": "repair_operator",
        "destroy_repair_pairs": "pair_operator",
    }[table_name]
    return _trace_field_complete(observation, field_name)


def _pair_identity_key(destroy: str, repair: str) -> str:
    def escape(component: str) -> str:
        return component.replace("%", "%25").replace("__", "%5F%5F")

    return f"{escape(destroy)}__{escape(repair)}"


def _operator_field_complete(
    observation: _RuntimeObservation,
    table_name: str,
    field_name: str,
) -> bool:
    if not _operator_identity_complete(observation, table_name):
        return False
    required_trace_fields = {
        "selected": (),
        "nonempty": ("acceptance_reason",),
        "empty": ("acceptance_reason",),
        "invoked": ("acceptance_reason",),
        "completed": ("acceptance_reason",),
        "accepted": ("acceptance_reason", "accepted"),
        "best_updates": ("acceptance_reason", "best_improved"),
        "selected_iteration_elapsed_ms": ("selected_iteration_elapsed_ms",),
    }[field_name]
    return all(
        _trace_field_complete(observation, trace_field)
        for trace_field in required_trace_fields
    )


def _instance_feasibility(
    pairs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    case_paths = sorted(
        {
            path
            for pair in pairs
            if (path := _nonempty_string(pair.get("case_path"))) is not None
        }
    )
    values: dict[str, list[int]] = {
        "customer_count": [],
        "total_demand": [],
        "vehicle_capacity": [],
        "capacity_lower_bound_routes": [],
        "reference_route_count": [],
        "min_route_slack": [],
    }
    observed = unavailable = reference_cases = feasible = infeasible = 0
    source_counts = {"allowed_routes": 0, "benchmark_reference_routes": 0}
    for case_path in case_paths:
        try:
            instance = load_cvrplib_instance(case_path)
            capacity = _positive_int(instance.capacity)
            if capacity is None:
                raise ValueError("non-positive capacity")
            customers = instance.customer_ids
            total_demand = sum(instance.demand(customer) for customer in customers)
            if total_demand < 0:
                raise ValueError("negative total demand")
            lower_bound = math.ceil(total_demand / capacity)
        except Exception:
            unavailable += 1
            continue

        observed += 1
        values["customer_count"].append(len(customers))
        values["total_demand"].append(total_demand)
        values["vehicle_capacity"].append(capacity)
        values["capacity_lower_bound_routes"].append(lower_bound)
        allowed_routes = _positive_int(getattr(instance, "allowed_routes", None))
        bks_routes = _positive_int(getattr(instance, "bks_routes", None))
        if allowed_routes is not None:
            reference = allowed_routes
            source_counts["allowed_routes"] += 1
        elif bks_routes is not None:
            reference = bks_routes
            source_counts["benchmark_reference_routes"] += 1
        else:
            continue

        reference_cases += 1
        slack = reference - lower_bound
        values["reference_route_count"].append(reference)
        values["min_route_slack"].append(slack)
        feasible += int(slack >= 1)
        infeasible += int(slack < 1)

    return {
        "coverage": {
            "requested_cases": len(case_paths),
            "observed_cases": observed,
            "unavailable_cases": unavailable,
            "reference_route_cases": reference_cases,
            "reference_route_source_counts": source_counts,
        },
        "summary": {
            name: _numeric_summary(samples) for name, samples in values.items()
        },
        "one_route_reduction": {
            "evaluated_cases": reference_cases,
            "capacity_feasible_cases": feasible,
            "capacity_infeasible_cases": infeasible,
        },
        "interpretation_constraint": (
            "capacity_lower_bound_only_not_route_elimination_proof"
        ),
    }


def _observed_map(value: Any, kind: str) -> _ObservedMap | None:
    if not isinstance(value, Mapping):
        return None
    converter = _nonnegative_int if kind == "int" else _finite_float
    parsed: dict[str, int | float] = {}
    complete = True
    for raw_key, raw_value in value.items():
        key = _nonempty_string(raw_key)
        number = converter(raw_value)
        if key is None or number is None:
            complete = False
        else:
            parsed[key] = number
    return _ObservedMap(parsed, complete)


def _mapping_coverage(
    values: Sequence[_ObservedMap | None],
) -> dict[str, int]:
    observed = [value for value in values if value is not None]
    complete = sum(value.complete for value in observed)
    return {
        "observed": len(observed),
        "complete": complete,
        "malformed": len(observed) - complete,
    }


def _trace_field_complete_pairs(
    observations: Sequence[_RuntimeObservation],
) -> dict[str, int]:
    fields = (
        "iteration",
        "acceptance_reason",
        "accepted",
        "best_improved",
        "destroy_operator",
        "repair_operator",
        "pair_operator",
        "selected_iteration_elapsed_ms",
        "post_repair_polish",
    )
    return {
        field_name: sum(
            _trace_field_complete(observation, field_name)
            for observation in observations
        )
        for field_name in fields
    }


def _trace_field_complete(
    observation: _RuntimeObservation,
    field_name: str,
) -> bool:
    if observation.trace is None or observation.malformed_trace_events:
        return False
    predicates = {
        "iteration": lambda event: _positive_int(event.get("iteration")) is not None,
        "acceptance_reason": lambda event: _acceptance_reason(
            event.get("acceptance_reason")
        )
        is not None,
        "accepted": lambda event: _explicit_bool(event.get("accepted")) is not None,
        "best_improved": lambda event: _explicit_bool(
            event.get("best_improved")
        )
        is not None,
        "destroy_operator": lambda event: _nonempty_string(
            event.get("destroy_operator")
        )
        is not None,
        "repair_operator": lambda event: _nonempty_string(
            event.get("repair_operator")
        )
        is not None,
        "pair_operator": lambda event: (
            _nonempty_string(event.get("destroy_operator")) is not None
            and _nonempty_string(event.get("repair_operator")) is not None
        ),
        "selected_iteration_elapsed_ms": lambda event: (
            _iteration_elapsed_ms(event) is not None
        ),
        "post_repair_polish": _polish_classified,
    }
    return all(predicates[field_name](event) for event in observation.trace)


def _polish_classified(event: Mapping[str, Any]) -> bool:
    before = _nonnegative_float(event.get("candidate_after_repair_distance"))
    after = _nonnegative_float(event.get("candidate_after_polish_distance"))
    return bool(
        (before is not None and after is not None)
        or _acceptance_reason(event.get("acceptance_reason"))
        in _NO_POLISH_REASONS
    )


def _valid_trace_event(value: Any) -> bool:
    return bool(
        isinstance(value, Mapping)
        and _positive_int(value.get("iteration")) is not None
    )


def _sum_maps(values: Sequence[_ObservedMap]) -> dict[str, int | float]:
    totals: dict[str, int | float] = {}
    for observed in values:
        for key, value in observed.values.items():
            totals[key] = totals.get(key, 0) + value
    return {key: _rounded(totals[key]) for key in sorted(totals)}


def _map_key_observed(value: _ObservedMap, key: str) -> bool:
    return key in value.values or value.complete


def _has_phase_accounting(value: _RuntimeObservation) -> bool:
    return bool(
        value.elapsed_ms is not None
        and value.phase_runtime_ms is not None
        and value.phase_runtime_ms.complete
    )


def _observation_residual(value: _RuntimeObservation) -> int | None:
    if not _has_phase_accounting(value):
        return None
    assert value.elapsed_ms is not None and value.phase_runtime_ms is not None
    return value.elapsed_ms - int(sum(value.phase_runtime_ms.values.values()))


def _iteration_elapsed_ms(event: Mapping[str, Any]) -> int | None:
    before = _nonnegative_int(event.get("elapsed_ms_before"))
    after = _nonnegative_int(event.get("elapsed_ms_after"))
    if before is None or after is None or after < before:
        return None
    return after - before


def _numeric_summary(values: Sequence[int | float]) -> dict[str, int | float | None]:
    if not values:
        return {"min": None, "median": None, "max": None}
    return {"min": min(values), "median": median(values), "max": max(values)}


def _metric_delta(
    candidate: int | float | None,
    champion: int | float | None,
    observed_pairs: int,
) -> dict[str, Any]:
    return {
        "candidate": _rounded(candidate),
        "champion": _rounded(champion),
        "candidate_minus_champion": (
            _rounded(candidate - champion)
            if candidate is not None and champion is not None
            else None
        ),
        "observed_pairs": observed_pairs,
    }


def _explicit_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _acceptance_reason(value: Any) -> str | None:
    rendered = _nonempty_string(value)
    return rendered if rendered in _ACCEPTANCE_REASONS else None


def _nonempty_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    rendered = value.strip()
    return rendered or None


def _positive_int(value: Any) -> int | None:
    number = _nonnegative_int(value)
    return number if number is not None and number > 0 else None


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value >= 0 else None


def _nonnegative_float(value: Any) -> float | None:
    number = _finite_float(value)
    return number if number is not None and number >= 0.0 else None


def _finite_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _rounded(value: int | float | None) -> int | float | None:
    if value is None or isinstance(value, int):
        return value
    return round(float(value), 6)


__all__ = [
    "SCHEMA_VERSION",
    "build_search_allocation_evidence",
    "has_search_allocation_observations",
]
