from __future__ import annotations
import json
import logging
import os
import statistics
import uuid as _uuid_mod
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, TYPE_CHECKING

logger = logging.getLogger(__name__)

from scion.core.models import (
    ExperimentStage, CanaryResult, ProtocolResult, EvalStats,
    PairwiseCaseFeedback, CaseAggregateFeedback,
    ScreeningPatternSummary,
)
from scion.config.problem import ProtocolConfig, SplitManifest, SeedLedgerConfig
from scion.runtime.runner import Runner
from scion.protocol.evaluation import (
    lexicographic_compare, compute_delta,
)
from scion.protocol.stats import compute_eval_stats
from scion.protocol.gates import (
    GateResult, screening_gate, validation_gate, frozen_gate,
)

if TYPE_CHECKING:
    from scion.problem.spec import ObjectiveMetricSpec


# ---------------------------------------------------------------------------
# Case-level result (T2)
# ---------------------------------------------------------------------------

@dataclass
class CaseLevelResult:
    """Aggregated result for a single case across all seeds."""
    case_id: str
    comparison: str   # majority vote: "win" / "loss" / "tie"
    delta: float      # median delta across seeds
    metric_deltas: Dict[str, float] | None = None


# ---------------------------------------------------------------------------
# SplitManager and SeedLedger wrappers
# ---------------------------------------------------------------------------

class SplitManager:
    def __init__(self, manifest: SplitManifest) -> None:
        self._manifest = manifest

    def get_cases(self, stage: ExperimentStage) -> List[str]:
        if stage == ExperimentStage.SCREENING:
            return list(self._manifest.screening)
        elif stage == ExperimentStage.VALIDATION:
            return list(self._manifest.validation)
        elif stage == ExperimentStage.FROZEN:
            return list(self._manifest.frozen)
        raise ValueError(f"Unknown stage: {stage}")

    def get_canary_cases(self) -> List[str]:
        """Return the dedicated canary case list."""
        return list(self._manifest.canary)

    def validate_disjoint(self) -> bool:
        self._manifest.validate_disjoint()
        return True


class SeedLedger:
    def __init__(self, ledger: SeedLedgerConfig) -> None:
        self._ledger = ledger

    def get_seeds(self, stage: ExperimentStage) -> List[int]:
        if stage == ExperimentStage.SCREENING:
            return list(self._ledger.screening)
        elif stage == ExperimentStage.VALIDATION:
            return list(self._ledger.validation)
        elif stage == ExperimentStage.FROZEN:
            return list(self._ledger.frozen)
        raise ValueError(f"Unknown stage: {stage}")

    def get_canary_seeds(self) -> List[int]:
        """Return the dedicated canary seed list."""
        return list(self._ledger.canary)


# ---------------------------------------------------------------------------
# ExperimentProtocol
# ---------------------------------------------------------------------------

class ExperimentProtocol:
    def __init__(
        self,
        protocol_config: ProtocolConfig,
        split_manager: SplitManager,
        seed_ledger: SeedLedger,
        runner: Runner,
        time_limit_sec: int = 300,
        metrics_dir: str = "/tmp/scion_metrics",
        *,
        metric_specs: Optional[Sequence[ObjectiveMetricSpec]] = None,
        require_metric_specs: bool = False,
    ) -> None:
        self.config = protocol_config
        self.split_manager = split_manager
        self.seed_ledger = seed_ledger
        self.runner = runner
        self.time_limit_sec = time_limit_sec
        self.metrics_dir = metrics_dir
        self._metric_specs = metric_specs
        self._require_metric_specs = require_metric_specs
        self._progress_callback: Optional[Callable[..., None]] = None
        if self._require_metric_specs and self._metric_specs is None:
            raise ValueError("metric_specs are required for production ExperimentProtocol")
        if self._metric_specs is None:
            logger.warning(
                "ExperimentProtocol initialized without metric_specs; using legacy "
                "warehouse objective fallback"
            )
        os.makedirs(metrics_dir, exist_ok=True)

    def set_progress_callback(self, callback: Optional[Callable[..., None]]) -> None:
        """Register a lightweight progress hook for long validation/frozen runs."""
        self._progress_callback = callback

    def _emit_progress(self, **payload: object) -> None:
        if self._progress_callback is None:
            return
        try:
            self._progress_callback(**payload)
        except Exception:
            logger.debug("Experiment progress callback failed", exc_info=True)

    # ------------------------------------------------------------------
    # Comparison dispatch: generic (v0.3+) or legacy
    # ------------------------------------------------------------------

    def _compare_objectives(
        self,
        candidate_objective: dict,
        champion_objective: dict,
    ) -> tuple:
        """Return (comparison_str, ObjectiveComparison)."""
        if self._metric_specs is not None:
            from scion.problem.objectives import compare_lexicographic
            result = compare_lexicographic(
                self._metric_specs, candidate_objective, champion_objective,
            )
            return result.outcome, result
        if self._require_metric_specs:
            raise RuntimeError("metric_specs are required for objective comparison")
        # Legacy compatibility path: build an ObjectiveComparison from the
        # hardcoded warehouse comparator.
        from scion.problem.objectives import ObjectiveComparison, MetricComparison
        cmp = lexicographic_compare(candidate_objective, champion_objective)
        metrics = []
        for name in ["subcategory_splits", "total_cost"]:
            cv = candidate_objective.get(name, 0)
            hv = champion_objective.get(name, 0)
            sd = float(hv) - float(cv)
            metrics.append(MetricComparison(
                name=name, candidate_value=cv, champion_value=hv,
                signed_delta=sd, relation="candidate" if sd > 0 else ("champion" if sd < 0 else "tie"),
                decisive=(
                    (name == "subcategory_splits" and cv != hv)
                    or (
                        name == "total_cost"
                        and candidate_objective.get("subcategory_splits", 0)
                        == champion_objective.get("subcategory_splits", 0)
                        and cv != hv
                    )
                ),
            ))
        decisive_metric = next((m.name for m in metrics if m.decisive), None)
        result = ObjectiveComparison(
            outcome=cmp,
            decisive_metric=decisive_metric,
            scalar_delta=sum(m.signed_delta for m in metrics),
            metrics=tuple(metrics),
        )
        return cmp, result

    def _compute_delta(
        self,
        candidate_objective: dict,
        champion_objective: dict,
    ) -> float:
        if self._metric_specs is not None:
            from scion.problem.objectives import compare_lexicographic
            result = compare_lexicographic(
                self._metric_specs, candidate_objective, champion_objective,
            )
            return result.scalar_delta
        if self._require_metric_specs:
            raise RuntimeError("metric_specs are required for objective delta")
        return compute_delta(candidate_objective, champion_objective)

    # ------------------------------------------------------------------
    # T3: Canary — uses independent canary split + canary seeds
    # ------------------------------------------------------------------

    def run_canary(self, candidate_ws: str, champion_ws: str) -> CanaryResult:
        """
        Canary regression check using the dedicated canary split and seeds.
        Veto-only — blocks if candidate produces infeasible solutions or crashes.

        Raises ValueError if canary split/seeds are not configured.
        """
        canary_cases = self.split_manager.get_canary_cases()
        canary_seeds = self.seed_ledger.get_canary_seeds()

        if not canary_cases:
            raise ValueError(
                "Canary split not configured: split_manifest.canary is empty. "
                "Add canary cases to split_manifest.yaml."
            )
        if not canary_seeds:
            raise ValueError(
                "Canary seeds not configured: seed_ledger.canary is empty. "
                "Add canary seeds to seed_ledger.yaml."
            )

        for case in canary_cases:
            for seed in canary_seeds:
                cand_result = self.runner.run_solver(
                    workdir=candidate_ws,
                    instance_path=case,
                    seed=seed,
                    time_limit_sec=self.time_limit_sec,
                    registry_path=os.path.join(candidate_ws, "registry.yaml"),
                )
                if not cand_result.success:
                    return CanaryResult(
                        passed=False,
                        reason=f"Candidate solver failed on {case}: {cand_result.error_category}",
                    )

                champ_result = self.runner.run_solver(
                    workdir=champion_ws,
                    instance_path=case,
                    seed=seed,
                    time_limit_sec=self.time_limit_sec,
                    registry_path=os.path.join(champion_ws, "registry.yaml"),
                )
                if not champ_result.success:
                    # Infra issue on champion side — skip veto
                    continue

                if (
                    cand_result.output is not None
                    and champ_result.output is not None
                    and champ_result.output.feasible
                    and not cand_result.output.feasible
                ):
                    return CanaryResult(
                        passed=False,
                        reason=f"Candidate infeasible on {case} (champion was feasible)",
                    )

        return CanaryResult(passed=True, reason=None)

    # ------------------------------------------------------------------
    # T4 + T5: Case selection helpers
    # ------------------------------------------------------------------

    def _select_cases(
        self,
        stage: ExperimentStage,
        hypothesis_action: str,
        expand_round: int,
    ) -> List[str]:
        """Select cases based on stage, action type, and whether we're in expand mode.

        T5: screening selects n_cases_modify or n_cases_create based on action.
        T4: expand increases the case count, seed set stays fixed.
        """
        all_cases = self.split_manager.get_cases(stage)

        if stage == ExperimentStage.SCREENING:
            if expand_round > 0:
                # T4: expand adds cases, not seeds
                n = (
                    self.config.screening.expand_to_create
                    if hypothesis_action == "create_new"
                    else self.config.screening.expand_to_modify
                )
            else:
                n = (
                    self.config.screening.n_cases_create
                    if hypothesis_action == "create_new"
                    else self.config.screening.n_cases_modify
                )
        elif stage == ExperimentStage.VALIDATION:
            n = (
                self.config.validation.expand_to
                if expand_round > 0
                else self.config.validation.n_cases
            )
        elif stage == ExperimentStage.FROZEN:
            n = self.config.frozen.n_cases
        else:
            return all_cases

        return all_cases[:n]

    def _select_seeds(self, stage: ExperimentStage) -> List[int]:
        """Return the fixed seed list for the stage (T4: seeds never expanded)."""
        return self.seed_ledger.get_seeds(stage)

    # ------------------------------------------------------------------
    # T2: run_experiment — case-level aggregation
    # ------------------------------------------------------------------

    def run_experiment(
        self,
        stage: ExperimentStage,
        candidate_ws: str,
        champion_ws: str,
        hypothesis_action: str,
        expand: bool = False,
        expand_round: int = 1,
    ) -> ProtocolResult:
        """Execute paired A/B evaluation for the given stage.

        T2: Statistical unit is case (not pair). Each case is evaluated across
        all seeds, then majority-voted to a case-level win/loss/tie and median delta.
        T4: expand increases case count; seed set is unchanged.
        T5: case count depends on stage + hypothesis_action + expand flag.
        """
        cases = self._select_cases(
            stage, hypothesis_action, expand_round if expand else 0
        )
        seeds = self._select_seeds(stage)
        total_pairs = len(cases) * len(seeds)
        attempted_pairs = 0
        valid_pairs = 0

        # Persist a partial metrics file from the start of the stage, then update
        # it after every attempted pair. Long validation/frozen stages remain
        # inspectable even if the campaign is interrupted.
        raw_ref = os.path.join(self.metrics_dir, f"{_uuid_mod.uuid4()}.json")

        # Collect pair feedback grouped by case
        pairs_by_case: Dict[str, List[PairwiseCaseFeedback]] = defaultdict(list)
        raw_pairs: List[dict] = []

        def _write_metrics_snapshot(*, complete: bool) -> None:
            with open(raw_ref, "w") as f:
                json.dump(
                    {
                        "stage": stage.value,
                        "case_ids": cases,
                        "seed_set": seeds,
                        "total_pairs": total_pairs,
                        "attempted_pairs": attempted_pairs,
                        "valid_pairs": valid_pairs,
                        "complete": complete,
                        "pairs": raw_pairs,
                    },
                    f,
                )

        _write_metrics_snapshot(complete=False)
        self._emit_progress(
            stage=stage.value,
            case=None,
            seed=None,
            attempted_pairs=attempted_pairs,
            completed_pairs=valid_pairs,
            total_pairs=total_pairs,
            raw_metrics_ref=raw_ref,
        )

        for case in cases:
            case_features = _extract_case_features(case)
            for seed in seeds:
                attempted_pairs += 1
                self._emit_progress(
                    stage=stage.value,
                    case=case,
                    seed=seed,
                    attempted_pairs=attempted_pairs,
                    completed_pairs=valid_pairs,
                    total_pairs=total_pairs,
                    raw_metrics_ref=raw_ref,
                )
                champ_r = self.runner.run_solver(
                    workdir=champion_ws,
                    instance_path=case,
                    seed=seed,
                    time_limit_sec=self.time_limit_sec,
                    registry_path=os.path.join(champion_ws, "registry.yaml"),
                )
                cand_r = self.runner.run_solver(
                    workdir=candidate_ws,
                    instance_path=case,
                    seed=seed,
                    time_limit_sec=self.time_limit_sec,
                    registry_path=os.path.join(candidate_ws, "registry.yaml"),
                )

                if not cand_r.success or not champ_r.success:
                    _write_metrics_snapshot(complete=False)
                    continue  # Infra failure — skip pair

                if cand_r.output is None or champ_r.output is None:
                    _write_metrics_snapshot(complete=False)
                    continue

                cmp, breakdown = self._compare_objectives(
                    cand_r.output.objective,
                    champ_r.output.objective,
                )
                delta = self._compute_delta(cand_r.output.objective, champ_r.output.objective)

                raw_pairs.append(
                    {
                        "case": case,
                        "seed": seed,
                        "comparison": cmp,
                        "delta": delta,
                        "decisive_metric": breakdown.decisive_metric,
                        "metric_deltas": {
                            m.name: m.signed_delta for m in breakdown.metrics
                        } if breakdown.metrics else {},
                    }
                )
                valid_pairs += 1
                pair_fb = PairwiseCaseFeedback(
                    case_id=os.path.basename(case),
                    seed=seed,
                    comparison=cmp,
                    delta=delta,
                    objective_comparison=breakdown,
                    case_features=case_features,
                )
                pairs_by_case[os.path.basename(case)].append(pair_fb)
                # Log per-pair result with generic metric values
                _mc = {m.name: m for m in breakdown.metrics} if breakdown.metrics else {}
                _cand_vals = " ".join(f"{m.name}={m.candidate_value}" for m in breakdown.metrics) if breakdown.metrics else ""
                _chmp_vals = " ".join(f"{m.name}={m.champion_value}" for m in breakdown.metrics) if breakdown.metrics else ""
                logger.info(
                    "Pair %s seed=%d: cmp=%s delta=%.4f decisive=%s cand(%s) champ(%s)",
                    os.path.basename(case), seed, cmp, delta,
                    breakdown.decisive_metric,
                    _cand_vals, _chmp_vals,
                )
                _write_metrics_snapshot(complete=False)
                self._emit_progress(
                    stage=stage.value,
                    case=case,
                    seed=seed,
                    attempted_pairs=attempted_pairs,
                    completed_pairs=valid_pairs,
                    total_pairs=total_pairs,
                    raw_metrics_ref=raw_ref,
                )

        # T2: Aggregate pairs → case-level results
        all_pair_feedback = [fb for fbs in pairs_by_case.values() for fb in fbs]
        case_level_results = _aggregate_pairs_to_case_level(all_pair_feedback)

        case_comparisons = [r.comparison for r in case_level_results]
        case_deltas = [r.delta for r in case_level_results]

        if not case_comparisons:
            stats = EvalStats(
                n_cases=0, wins=0, losses=0, ties=0,
                win_rate=0.0, median_delta=0.0, ci_low=-1.0, ci_high=-1.0,
            )
            gate = GateResult(outcome="fail", reason_codes=("NO_VALID_RUNS",))
        else:
            # T2: stats computed on case-level comparisons/deltas.
            # F3: when metric_specs are present, gate CI is computed
            # hierarchically by objective priority instead of one raw scalar.
            metric_order = (
                [m.name for m in sorted(self._metric_specs, key=lambda s: s.priority)]
                if self._metric_specs is not None else None
            )
            stats = compute_eval_stats(
                case_comparisons,
                case_deltas,
                metric_deltas=[r.metric_deltas or {} for r in case_level_results],
                metric_order=metric_order,
            )
            if stage == ExperimentStage.SCREENING:
                gate = screening_gate(stats, self.config)
            elif stage == ExperimentStage.VALIDATION:
                gate = validation_gate(stats, self.config)
            else:
                gate = frozen_gate(stats, self.config)

        # Persist final raw metrics snapshot.
        _write_metrics_snapshot(complete=True)

        # Exposure control
        if stage == ExperimentStage.SCREENING:
            exposed = (
                f"stage={stage.value} win_rate={stats.win_rate:.2f} "
                f"median_delta={stats.median_delta:.4f} outcome={gate.outcome}"
            )
        else:
            # Validation / Frozen: aggregate summary only, no per-case data
            exposed = (
                f"stage={stage.value} outcome={gate.outcome} "
                f"stat={stats.statistical_status or 'legacy'} "
                f"metric={stats.statistical_metric or 'scalar'}"
            )

        # Build case-level feedback for screening only
        case_fb: tuple = ()
        pattern: "ScreeningPatternSummary | None" = None
        if stage == ExperimentStage.SCREENING and all_pair_feedback:
            case_fb = tuple(_aggregate_case_feedback(all_pair_feedback))
            pattern = _build_pattern_summary(case_fb)

        return ProtocolResult(
            stage=stage,
            stats=stats,
            gate_outcome=gate.outcome,
            reason_codes=gate.reason_codes,
            exposed_summary=exposed,
            raw_metrics_ref=raw_ref,
            case_ids=tuple(cases),
            seed_set=tuple(seeds),
            pair_feedback=tuple(all_pair_feedback) if stage == ExperimentStage.SCREENING else (),
            case_feedback=case_fb,
            pattern_summary=pattern,
        )


# ---------------------------------------------------------------------------
# T2: Case-level aggregation helper
# ---------------------------------------------------------------------------

def _aggregate_pairs_to_case_level(
    pairs: List[PairwiseCaseFeedback],
) -> List[CaseLevelResult]:
    """For each case, aggregate across seeds: majority vote → win/loss/tie, median delta.

    T2: This is the core of the case-level statistical unit change.
    """
    by_case: Dict[str, List[PairwiseCaseFeedback]] = defaultdict(list)
    for p in pairs:
        by_case[p.case_id].append(p)

    result = []
    for case_id, case_pairs in by_case.items():
        wins = sum(1 for p in case_pairs if p.comparison == "win")
        losses = sum(1 for p in case_pairs if p.comparison == "loss")
        ties = len(case_pairs) - wins - losses

        # Majority vote across seeds
        if wins > losses and wins > ties:
            majority = "win"
        elif losses > wins and losses > ties:
            majority = "loss"
        else:
            # True tie in vote count (or ties dominate)
            majority = "tie"

        med_delta = statistics.median(p.delta for p in case_pairs)
        metric_deltas: dict[str, float] = {}
        metric_values: dict[str, list[float]] = defaultdict(list)
        for p in case_pairs:
            oc = p.objective_comparison
            if oc is not None and hasattr(oc, "metrics"):
                for m in oc.metrics:
                    metric_values[m.name].append(float(m.signed_delta))
        metric_deltas = {
            name: statistics.median(vals)
            for name, vals in metric_values.items()
            if vals
        }
        result.append(CaseLevelResult(
            case_id=case_id,
            comparison=majority,
            delta=med_delta,
            metric_deltas=metric_deltas,
        ))

    return result


# ---------------------------------------------------------------------------
# Case feedback helpers (unchanged from original)
# ---------------------------------------------------------------------------

def _extract_case_features(case_path: str) -> dict:
    """Extract lightweight features from instance path (MVP: path-level only)."""
    stem = os.path.splitext(os.path.basename(case_path))[0]
    size_bucket = "unknown"
    for tag in ("xlarge", "large", "medium", "small"):
        if tag in stem.lower():
            size_bucket = tag
            break
    return {"path_stem": stem, "size_bucket": size_bucket}


def _aggregate_case_feedback(
    pairs: List[PairwiseCaseFeedback],
) -> List[CaseAggregateFeedback]:
    """Group pair feedback by case_id and compute per-case aggregates."""
    by_case: dict[str, list[PairwiseCaseFeedback]] = defaultdict(list)
    for p in pairs:
        by_case[p.case_id].append(p)

    result = []
    for case_id, case_pairs in by_case.items():
        n = len(case_pairs)
        wins = sum(1 for p in case_pairs if p.comparison == "win")
        losses = sum(1 for p in case_pairs if p.comparison == "loss")
        ties = n - wins - losses
        wr = wins / n if n > 0 else 0.0

        # Dominant result
        mx = max(wins, losses, ties)
        if wins == losses and wins > 0:
            dominant = "mixed"
        elif mx == wins:
            dominant = "win"
        elif mx == losses:
            dominant = "loss"
        else:
            dominant = "tie"

        # Dominant decisive metric (generic)
        decisive_counts: dict[str, int] = defaultdict(int)
        for p in case_pairs:
            oc = p.objective_comparison
            dm = (oc.decisive_metric if oc and hasattr(oc, 'decisive_metric') else None) or "tie"
            decisive_counts[dm] += 1
        dominant_decisive = max(decisive_counts, key=decisive_counts.get)  # type: ignore
        if len(set(decisive_counts.values())) == 1 and len(decisive_counts) > 1:
            dominant_decisive = "mixed"

        # Median deltas per metric (generic)
        metric_deltas: dict[str, list[float]] = defaultdict(list)
        for p in case_pairs:
            oc = p.objective_comparison
            if oc and hasattr(oc, 'metrics'):
                for m in oc.metrics:
                    metric_deltas[m.name].append(m.signed_delta)
        median_deltas = {
            name: statistics.median(vals) for name, vals in metric_deltas.items() if vals
        }

        result.append(CaseAggregateFeedback(
            case_id=case_id,
            n_pairs=n,
            wins=wins,
            losses=losses,
            ties=ties,
            win_rate=wr,
            dominant_result=dominant,
            decisive_metric=dominant_decisive,
            median_deltas=median_deltas,
            seed_consistency=mx / n if n > 0 else 0.0,
            case_features=case_pairs[0].case_features if case_pairs else {},
        ))
    return result


def _build_pattern_summary(
    case_feedback: tuple[CaseAggregateFeedback, ...],
) -> ScreeningPatternSummary:
    """Build code-generated pattern summary from case-level feedback."""
    winning = [c for c in case_feedback if c.dominant_result == "win"]
    losing = [c for c in case_feedback if c.dominant_result == "loss"]
    mixed = [c for c in case_feedback if c.dominant_result == "mixed"]

    wins_by_obj: dict[str, int] = defaultdict(int)
    losses_by_obj: dict[str, int] = defaultdict(int)
    wins_by_size: dict[str, int] = defaultdict(int)
    losses_by_size: dict[str, int] = defaultdict(int)

    for c in winning:
        wins_by_obj[c.decisive_metric] += 1
        wins_by_size[c.case_features.get("size_bucket", "unknown")] += 1
    for c in losing:
        losses_by_obj[c.decisive_metric] += 1
        losses_by_size[c.case_features.get("size_bucket", "unknown")] += 1

    # Generate key observations (rule-based, generic metric names)
    observations: list[str] = []
    for metric, count in losses_by_obj.items():
        if count >= 2 and metric != "tie":
            observations.append(
                f"Most losses decided by {metric}: candidate often worsened this objective."
            )

    # Size pattern
    win_sizes = set(wins_by_size.keys())
    loss_sizes = set(losses_by_size.keys())
    if win_sizes and loss_sizes and not win_sizes.intersection(loss_sizes):
        observations.append(
            f"Candidate wins on {', '.join(sorted(win_sizes))} but loses on {', '.join(sorted(loss_sizes))}."
        )

    if mixed:
        observations.append(
            f"{len(mixed)} case(s) showed seed-sensitive behavior; treat gains there as unstable."
        )

    consistent_wins = tuple(c.case_id for c in winning if c.seed_consistency >= 0.99)
    consistent_losses = tuple(c.case_id for c in losing if c.seed_consistency >= 0.99)
    if consistent_wins:
        observations.append(f"Consistent wins: {', '.join(consistent_wins)}.")
    if consistent_losses:
        observations.append(f"Consistent losses: {', '.join(consistent_losses)}.")

    return ScreeningPatternSummary(
        total_cases=len(case_feedback),
        winning_cases=len(winning),
        losing_cases=len(losing),
        mixed_cases=len(mixed),
        wins_by_decisive_objective=dict(wins_by_obj),
        losses_by_decisive_objective=dict(losses_by_obj),
        wins_by_size_bucket=dict(wins_by_size),
        losses_by_size_bucket=dict(losses_by_size),
        consistent_win_cases=consistent_wins,
        consistent_loss_cases=consistent_losses,
        key_observations=tuple(observations),
    )


# ObjectiveComparison from problem/objectives.py is now used directly.
