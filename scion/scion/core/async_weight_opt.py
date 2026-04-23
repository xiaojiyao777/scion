"""AsyncWeightOptCoordinator — background weight optimization lifecycle.

Extracted from CampaignManager (v0.3 §B2 per optimization-design doc).
Owns thread lifecycle + the optimization loop body that was previously part
of the CampaignManager god-object:

  - ``_pending_threads`` — background thread registry
  - ``_latest_result`` — last completed optimization result (for LLM feedback)
  - ``spawn_for_promoted_champion`` — entry point from ``_on_promote`` tail
  - ``run_optimization`` — the optimization loop body (formerly
    ``CampaignManager._run_weight_optimization``)
  - ``wait_all`` — shutdown join

The coordinator holds a reference to ``CampaignManager`` (v0.3 minimum
extraction — dependency injection is for v1.0) and reads manager state via
``self._mgr._xxx``. It intentionally does NOT own champion state or
materialization — those remain with the manager. The bg thread delegates
the optimization call through ``self._mgr._run_weight_optimization(...)``
so that existing tests which monkey-patch that method continue to work.
"""
from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any, List, Optional

if TYPE_CHECKING:  # pragma: no cover - import only for type checking
    from scion.core.campaign import CampaignManager

logger = logging.getLogger(__name__)


class AsyncWeightOptCoordinator:
    """Owns async weight-optimization thread lifecycle and the opt loop body."""

    def __init__(self, manager: "CampaignManager") -> None:
        self._mgr = manager
        self._pending_threads: List[threading.Thread] = []
        self._latest_result: Optional[Any] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def latest_result(self) -> Optional[Any]:
        return self._latest_result

    @latest_result.setter
    def latest_result(self, value: Optional[Any]) -> None:
        self._latest_result = value

    @property
    def pending_threads(self) -> List[threading.Thread]:
        """Direct access to the pending thread list (for backward-compat)."""
        return self._pending_threads

    @property
    def pending_count(self) -> int:
        return len(self._pending_threads)

    def spawn_for_promoted_champion(
        self, staging_path: str, version: int, current_weights: dict
    ) -> None:
        """Launch bg weight optimization for a freshly promoted champion.

        Called from ``CampaignManager._on_promote`` tail. No-op if weight opt
        is disabled or no experiment_protocol is available.
        """
        param_cfg = self._mgr._spec.parameter_search
        if not (param_cfg.enabled and self._mgr._experiment_protocol is not None):
            return
        t = threading.Thread(
            target=self._bg_weight_opt_task,
            args=(staging_path, version, current_weights),
            daemon=True,
            name=f"weight-opt-v{version}",
        )
        self._pending_threads.append(t)
        t.start()

    def wait_all(self, timeout: Optional[float] = 600) -> None:
        """Join all pending bg threads (called from campaign shutdown).

        Preserves the previous semantics: log once when any are still alive,
        then join each with the given timeout.
        """
        pending = [t for t in self._pending_threads if t.is_alive()]
        if pending:
            logger.info(
                "Waiting for %d background weight opt thread(s) to complete...",
                len(pending),
            )
        for t in self._pending_threads:
            t.join(timeout=timeout)

    # ------------------------------------------------------------------
    # Internal: background thread body
    # ------------------------------------------------------------------

    def _bg_weight_opt_task(
        self, staging_path: str, version: int, current_weights: dict
    ) -> None:
        """Background thread: run weight opt and update champion on success.

        Creates a NEW immutable snapshot rather than modifying the original.
        Atomic pointer switch under champion_lock.
        """
        import os as _os
        import shutil as _shutil
        import time as _time
        from scion.runtime.workspace import _make_tree_writable
        from pathlib import Path as _Path

        t0 = _time.monotonic()
        try:
            # Call through the manager so that test monkey-patches of
            # ``cm._run_weight_optimization`` still take effect.
            opt_result = self._mgr._run_weight_optimization(
                staging_path, version, current_weights
            )
        except Exception as exc:
            logger.error("Background weight opt failed for champion v%d: %s", version, exc)
            return

        elapsed_min = (_time.monotonic() - t0) / 60.0

        if opt_result is None:
            return

        self._latest_result = opt_result
        try:
            self._mgr._registry.record_weight_optimization(
                campaign_id=self._mgr._campaign_id,
                champion_version=version,
                result=opt_result,
            )
        except Exception as exc:
            logger.warning("Background weight opt: failed to record result: %s", exc)

        if not opt_result.improved:
            logger.info(
                "Background weight opt complete for champion v%d (%.1f min) — no improvement",
                version, elapsed_min,
            )
            return

        # Determine new revision number
        with self._mgr._champion_lock:
            if self._mgr._champion.version != version:
                logger.warning(
                    "Background weight opt for champion v%d discarded — "
                    "champion has advanced to v%d",
                    version, self._mgr._champion.version,
                )
                return
            new_revision = self._mgr._champion.weight_revision + 1

        # Create NEW immutable snapshot with optimized weights (never modify original)
        new_snapshot_path = str(
            self._mgr._materializer._champions_dir / f"champion_v{version}_r{new_revision}"
        )
        try:
            if _os.path.exists(new_snapshot_path):
                _make_tree_writable(_Path(new_snapshot_path))
                _shutil.rmtree(new_snapshot_path)
            _shutil.copytree(staging_path, new_snapshot_path)
            _make_tree_writable(_Path(new_snapshot_path))

            from scion.runtime.pool_manager import update_weights, read_registry
            registry_path = _os.path.join(new_snapshot_path, "registry.yaml")
            if _os.path.exists(registry_path):
                update_weights(registry_path, opt_result.best_weights)
            self._mgr._materializer.freeze_snapshot(new_snapshot_path)
        except Exception as exc:
            logger.error(
                "Background weight opt: failed to create snapshot for champion v%d_r%d: %s",
                version, new_revision, exc,
            )
            return

        # Recompute hash and read updated pool
        try:
            registry_path = _os.path.join(new_snapshot_path, "registry.yaml")
            new_pool = read_registry(registry_path)
            new_hash = self._mgr._materializer.compute_snapshot_hash(new_snapshot_path)
        except Exception as exc:
            logger.error(
                "Background weight opt: failed to recompute hash for champion v%d_r%d: %s",
                version, new_revision, exc,
            )
            return

        # Atomic pointer switch
        from scion.core.models import ChampionState
        with self._mgr._champion_lock:
            if self._mgr._champion.version != version:
                logger.warning(
                    "Background weight opt for champion v%d discarded — "
                    "champion has advanced to v%d",
                    version, self._mgr._champion.version,
                )
                return
            self._mgr._champion = ChampionState(
                version=self._mgr._champion.version,
                operator_pool=new_pool,
                solver_config_hash=self._mgr._champion.solver_config_hash,
                code_snapshot_path=new_snapshot_path,
                code_snapshot_hash=new_hash,
                promoted_at=self._mgr._champion.promoted_at,
                weight_revision=new_revision,
            )

        logger.info(
            "Background weight opt complete for champion v%d_r%d (%.1f min)",
            version, new_revision, elapsed_min,
        )

        # Stage-aware stale: only mark screening/explore branches
        try:
            stale_weight_ids = self._mgr._branch_ctrl.mark_stale_for_weight_update(version)
            if stale_weight_ids:
                logger.info(
                    "Background weight opt: marked %d screening branches stale for re-screening",
                    len(stale_weight_ids),
                )
        except Exception as exc:
            logger.warning("Background weight opt: failed to mark branches stale: %s", exc)

    # ------------------------------------------------------------------
    # Optimization loop body (formerly CampaignManager._run_weight_optimization)
    # ------------------------------------------------------------------

    def run_optimization(
        self, champion_snapshot: str, version: int, current_weights: dict
    ):
        """Run weight optimization on a copy of the champion snapshot.

        Args:
            champion_snapshot: Path to the mutable staging snapshot directory.
            version: Champion version number (used for eval_ws naming and seed).
            current_weights: Current champion weights — passed to optimizer as
                true baseline (T1).

        Returns WeightOptimizationResult or None if prerequisites are missing.
        """
        import os as _os
        import shutil
        from scion.parameter.optimizer import RandomLocalWeightOptimizer, BayesianWeightOptimizer
        from scion.parameter.evaluator import collect_baseline, evaluate_weights
        from scion.parameter.search_space import ParameterSearchSpace

        param_cfg = self._mgr._spec.parameter_search

        # Locate runner
        runner = getattr(self._mgr._experiment_protocol, 'runner',
                         getattr(self._mgr._experiment_protocol, '_runner', None))
        if runner is None:
            logger.warning("No runner available for weight optimization")
            return None

        # Require a registry.yaml in the snapshot
        registry_path = _os.path.join(champion_snapshot, "registry.yaml")
        if not _os.path.exists(registry_path):
            logger.warning("No registry.yaml in snapshot %s; skipping weight opt", champion_snapshot)
            return None

        # Create evaluation workspace (isolated copy of champion snapshot)
        eval_ws = _os.path.join(self._mgr._campaign_dir, f"weight_opt_v{version}")
        if _os.path.exists(eval_ws):
            shutil.rmtree(eval_ws)
        shutil.copytree(champion_snapshot, eval_ws)
        # Ensure eval workspace is writable
        for _root, _dirs, _files in _os.walk(eval_ws):
            for _d in _dirs:
                _os.chmod(_os.path.join(_root, _d), 0o755)
            for _f in _files:
                _os.chmod(_os.path.join(_root, _f), 0o644)

        # Determine eval cases (fall back to screening split)
        eval_cases = list(param_cfg.eval_cases)
        if not eval_cases:
            eval_cases = list(self._mgr._split_manifest.screening)
        resolved_cases = [
            _os.path.join(self._mgr._spec.root_dir, c) if not _os.path.isabs(c) else c
            for c in eval_cases
        ]

        seeds = list(self._mgr._seed_ledger.screening)[:param_cfg.n_eval_seeds]
        time_limit = getattr(getattr(self._mgr._spec, 'solver', None), 'time_limit_sec', 300)

        operator_names = tuple(current_weights.keys())

        # Collect baseline objectives for evaluate_weights comparisons
        baseline = collect_baseline(eval_ws, resolved_cases, seeds, runner, time_limit)

        # Build search space
        search_space = ParameterSearchSpace(
            operator_names=operator_names,
            weight_bounds=param_cfg.weight_bounds,
            n_initial_random=param_cfg.n_initial_random,
            n_iterations=param_cfg.n_iterations,
            n_eval_seeds=param_cfg.n_eval_seeds,
            eval_cases=tuple(resolved_cases),
        )

        def eval_fn(weights):
            return evaluate_weights(
                weights=weights,
                workspace=eval_ws,
                cases=resolved_cases,
                seeds=seeds,
                runner=runner,
                time_limit_sec=time_limit,
                baseline_objectives=baseline,
            )

        optimizer = RandomLocalWeightOptimizer(search_space, eval_fn, seed=version)
        if getattr(param_cfg, 'strategy', 'random_local') == 'bayesian':
            optimizer = BayesianWeightOptimizer(search_space, eval_fn, seed=version)

        # T2: artifacts dir for saving observations JSON
        artifacts_dir = _os.path.join(self._mgr._campaign_dir, "artifacts")
        _os.makedirs(artifacts_dir, exist_ok=True)

        # T1: pass current_weights so optimizer evaluates true baseline first
        result = optimizer.optimize(current_weights, artifacts_dir=artifacts_dir)

        try:
            shutil.rmtree(eval_ws)
        except Exception:
            pass

        return result
