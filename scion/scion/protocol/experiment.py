from __future__ import annotations
import json
import logging
import os
import statistics
import uuid as _uuid_mod
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

from scion.core.models import (
    ExperimentStage, CanaryResult, ProtocolResult, EvalStats,
    ObjectiveBreakdown, PairwiseCaseFeedback, CaseAggregateFeedback,
    ScreeningPatternSummary,
)
from scion.config.problem import ProtocolConfig, SplitManifest, SeedLedgerConfig
from scion.runtime.runner import Runner
from scion.protocol.evaluation import (
    lexicographic_compare, compute_delta, compare_with_breakdown,
)
from scion.protocol.stats import compute_eval_stats
from scion.protocol.gates import (
    GateResult, screening_gate, validation_gate, frozen_gate,
)


# ---------------------------------------------------------------------------
# Case-level result (T2)
# ---------------------------------------------------------------------------

@dataclass
class CaseLevelResult:
    """Aggregated result for a single case across all seeds."""
    case_id: str
    comparison: str   # majority vote: "win" / "loss" / "tie"
    delta: float      # median delta across seeds


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
    ) -> None:
        self.config = protocol_config
        self.split_manager = split_manager
        self.seed_ledger = seed_ledger
        self.runner = runner
        self.time_limit_sec = time_limit_sec
        self.metrics_dir = metrics_dir
        os.makedirs(metrics_dir, exist_ok=True)

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

        # Collect pair feedback grouped by case
        pairs_by_case: Dict[str, List[PairwiseCaseFeedback]] = defaultdict(list)
        raw_pairs: List[dict] = []

        for case in cases:
            case_features = _extract_case_features(case)
            for seed in seeds:
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
                    continue  # Infra failure — skip pair

                if cand_r.output is None or champ_r.output is None:
                    continue

                cmp, breakdown = compare_with_breakdown(
                    cand_r.output.objective,
                    champ_r.output.objective,
                )
                delta = compute_delta(cand_r.output.objective, champ_r.output.objective)

                raw_pairs.append(
                    {"case": case, "seed": seed, "comparison": cmp, "delta": delta}
                )
                pair_fb = PairwiseCaseFeedback(
                    case_id=os.path.basename(case),
                    seed=seed,
                    comparison=cmp,
                    delta=delta,
                    objective_breakdown=breakdown,
                    case_features=case_features,
                )
                pairs_by_case[os.path.basename(case)].append(pair_fb)
                logger.info(
                    "Pair %s seed=%d: cmp=%s delta=%.4f decisive=%s "
                    "cand(splits=%s cost=%s) champ(splits=%s cost=%s)",
                    os.path.basename(case), seed, cmp, delta,
                    breakdown.decisive_objective,
                    breakdown.candidate_subcategory_splits,
                    breakdown.candidate_total_cost,
                    breakdown.champion_subcategory_splits,
                    breakdown.champion_total_cost,
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
            # T2: stats computed on case-level comparisons/deltas
            stats = compute_eval_stats(case_comparisons, case_deltas)
            if stage == ExperimentStage.SCREENING:
                gate = screening_gate(stats, self.config)
            elif stage == ExperimentStage.VALIDATION:
                gate = validation_gate(stats, self.config)
            else:
                gate = frozen_gate(stats, self.config)

        # Persist raw metrics
        raw_ref = os.path.join(self.metrics_dir, f"{_uuid_mod.uuid4()}.json")
        with open(raw_ref, "w") as f:
            json.dump({"stage": stage.value, "pairs": raw_pairs}, f)

        # Exposure control
        if stage == ExperimentStage.SCREENING:
            exposed = (
                f"stage={stage.value} win_rate={stats.win_rate:.2f} "
                f"median_delta={stats.median_delta:.4f} outcome={gate.outcome}"
            )
        else:
            # Validation / Frozen: aggregate summary only, no per-case data
            exposed = f"stage={stage.value} outcome={gate.outcome}"

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
        result.append(CaseLevelResult(case_id=case_id, comparison=majority, delta=med_delta))

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

        # Dominant decisive objective
        decisive_counts: dict[str, int] = defaultdict(int)
        for p in case_pairs:
            decisive_counts[p.objective_breakdown.decisive_objective] += 1
        dominant_decisive = max(decisive_counts, key=decisive_counts.get)  # type: ignore
        if len(set(decisive_counts.values())) == 1 and len(decisive_counts) > 1:
            dominant_decisive = "mixed"

        # Median deltas
        cost_deltas = [p.objective_breakdown.delta_total_cost for p in case_pairs
                       if p.objective_breakdown.delta_total_cost is not None]
        splits_deltas = [p.objective_breakdown.delta_subcategory_splits for p in case_pairs
                         if p.objective_breakdown.delta_subcategory_splits is not None]

        result.append(CaseAggregateFeedback(
            case_id=case_id,
            n_pairs=n,
            wins=wins,
            losses=losses,
            ties=ties,
            win_rate=wr,
            dominant_result=dominant,
            dominant_decisive_objective=dominant_decisive,
            median_delta_total_cost=statistics.median(cost_deltas) if cost_deltas else None,
            median_delta_subcategory_splits=statistics.median(splits_deltas) if splits_deltas else None,
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
        wins_by_obj[c.dominant_decisive_objective] += 1
        wins_by_size[c.case_features.get("size_bucket", "unknown")] += 1
    for c in losing:
        losses_by_obj[c.dominant_decisive_objective] += 1
        losses_by_size[c.case_features.get("size_bucket", "unknown")] += 1

    # Generate key observations (rule-based)
    observations: list[str] = []
    if losses_by_obj.get("business_aggregation", 0) >= 2:
        observations.append(
            "Most losses decided at business_aggregation: candidate often harmed split quality."
        )
    if losses_by_obj.get("cost", 0) >= 2:
        observations.append(
            "Most losses decided at cost: candidate preserved splits but increased cost."
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
