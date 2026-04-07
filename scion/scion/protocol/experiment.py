from __future__ import annotations
import json
import os
import uuid as _uuid_mod
from typing import List, Optional

from scion.core.models import (
    ExperimentStage, CanaryResult, ProtocolResult, EvalStats,
)
from scion.config.problem import ProtocolConfig, SplitManifest, SeedLedgerConfig
from scion.runtime.runner import Runner
from scion.protocol.evaluation import lexicographic_compare, compute_delta
from scion.protocol.stats import compute_eval_stats
from scion.protocol.gates import (
    GateResult, screening_gate, validation_gate, frozen_gate,
)


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

    def run_canary(self, candidate_ws: str, champion_ws: str) -> CanaryResult:
        """
        Canary regression check: runs a small subset of screening cases.
        Veto-only — blocks if candidate produces infeasible solutions or crashes.
        """
        cases = self.split_manager.get_cases(ExperimentStage.SCREENING)[:2]
        seeds = self.seed_ledger.get_seeds(ExperimentStage.SCREENING)[:1]

        for case in cases:
            for seed in seeds:
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

    def run_experiment(
        self,
        stage: ExperimentStage,
        candidate_ws: str,
        champion_ws: str,
        hypothesis_action: str,
        expand: bool = False,
    ) -> ProtocolResult:
        """Execute paired A/B evaluation for the given stage."""
        cases = self.split_manager.get_cases(stage)
        seeds = list(self.seed_ledger.get_seeds(stage))

        # Expand: add extra seeds for more statistical power
        if expand:
            extra_seeds = [s + 1000 for s in seeds]  # deterministic extra seeds
            seeds = seeds + extra_seeds

        comparisons: List[str] = []
        deltas: List[float] = []
        raw_pairs: List[dict] = []

        for case in cases:
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

                cmp = lexicographic_compare(
                    cand_r.output.objective,
                    champ_r.output.objective,
                )
                delta = compute_delta(cand_r.output.objective, champ_r.output.objective)
                comparisons.append(cmp)
                deltas.append(delta)
                raw_pairs.append(
                    {"case": case, "seed": seed, "comparison": cmp, "delta": delta}
                )

        if not comparisons:
            stats = EvalStats(
                n_cases=0, wins=0, losses=0, ties=0,
                win_rate=0.0, median_delta=0.0, ci_low=-1.0, ci_high=-1.0,
            )
            gate = GateResult(outcome="fail", reason_codes=("NO_VALID_RUNS",))
        else:
            stats = compute_eval_stats(comparisons, deltas)
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

        return ProtocolResult(
            stage=stage,
            stats=stats,
            gate_outcome=gate.outcome,
            reason_codes=gate.reason_codes,
            exposed_summary=exposed,
            raw_metrics_ref=raw_ref,
        )
