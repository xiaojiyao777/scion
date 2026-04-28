"""AsyncWeightOptCoordinator — background weight optimization lifecycle.

Extracted from CampaignManager (v0.3 §B2 per optimization-design doc).
Owns thread lifecycle + the optimization loop body that was previously part
of the CampaignManager god-object:

  - ``_pending_threads`` — background thread registry
  - ``_latest_result`` — last drained optimization result (for LLM feedback)
  - ``_completed_events`` — worker results awaiting CampaignManager commit
  - ``spawn_for_promoted_champion`` — entry point from ``_on_promote`` tail
  - ``run_optimization`` — the optimization loop body (formerly
    ``CampaignManager._run_weight_optimization``)
  - ``wait_all`` — shutdown join

The coordinator holds a reference to ``CampaignManager`` (v0.3 minimum
extraction — dependency injection is for v1.0) and reads manager services via
``self._mgr._xxx``. It intentionally does NOT own champion or branch state.
The bg thread delegates the optimization call through
``self._mgr._run_weight_optimization(...)`` so that existing tests which
monkey-patch that method continue to work, then enqueues a completion event
for CampaignManager to commit on the main loop boundary.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, List, Optional

if TYPE_CHECKING:  # pragma: no cover - import only for type checking
    from scion.core.campaign import CampaignManager
    from scion.core.models import OperatorConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WeightOptCompletionEvent:
    """Completed weight optimization work ready for main-thread commit."""

    version: int
    base_weight_revision: int
    result: Any
    elapsed_minutes: float
    improved: bool
    new_revision: Optional[int] = None
    snapshot_path: Optional[str] = None
    snapshot_hash: Optional[str] = None
    operator_pool: Optional[dict[str, "OperatorConfig"]] = None


class AsyncWeightOptCoordinator:
    """Owns async weight-optimization thread lifecycle and the opt loop body."""

    def __init__(self, manager: "CampaignManager") -> None:
        self._mgr = manager
        self._pending_threads: List[threading.Thread] = []
        self._completed_events: List[WeightOptCompletionEvent] = []
        self._events_lock = threading.Lock()
        self._status_lock = threading.Lock()
        self._active_status: dict[int, dict] = {}
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

    def status_snapshot(self) -> dict:
        """Return lightweight weight-optimization status for status.json."""
        with self._status_lock:
            runs = [dict(v) for v in self._active_status.values()]
        return {
            "pending_threads": sum(1 for t in self._pending_threads if t.is_alive()),
            "active": [r for r in runs if r.get("active")],
            "runs": runs,
        }

    def _set_status(self, version: int, **updates) -> None:
        with self._status_lock:
            current = dict(self._active_status.get(version, {}))
            current.update(updates)
            current["version"] = version
            self._active_status[version] = current
        self._publish_status()

    def _finish_status(self, version: int, **updates) -> None:
        with self._status_lock:
            current = dict(self._active_status.get(version, {}))
            current.update(updates)
            current["version"] = version
            current["active"] = False
            current["finished_at"] = time.time()
            self._active_status[version] = current
        self._publish_status()

    def _publish_status(self) -> None:
        """Best-effort status.json refresh while sync/async optimization runs."""
        writer = getattr(self._mgr, "_write_status", None)
        if not callable(writer):
            return
        try:
            writer()
        except Exception as exc:
            logger.debug("Weight opt status refresh failed: %s", exc)

    def spawn_for_promoted_champion(
        self,
        staging_path: str,
        version: int,
        current_weights: dict,
        base_weight_revision: int = 0,
    ) -> None:
        """Launch bg weight optimization for a freshly promoted champion.

        Called from ``CampaignManager._on_promote`` tail. No-op if weight opt
        is disabled or no experiment_protocol is available.
        """
        param_cfg = self._mgr._spec.parameter_search
        if not (param_cfg.enabled and self._mgr._experiment_protocol is not None):
            return
        self._set_status(
            version,
            mode="async",
            phase="queued",
            active=True,
            started_at=time.time(),
            base_weight_revision=base_weight_revision,
        )
        t = threading.Thread(
            target=self._bg_weight_opt_task,
            args=(staging_path, version, current_weights, base_weight_revision),
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
        still_alive = [t for t in self._pending_threads if t.is_alive()]
        if still_alive:
            logger.warning(
                "%d background weight opt thread(s) still running after wait timeout",
                len(still_alive),
            )

    def run_for_promoted_champion_sync(
        self,
        staging_path: str,
        version: int,
        current_weights: dict,
        base_weight_revision: int = 0,
    ) -> None:
        """Run weight optimization inline for resource-constrained campaigns."""
        param_cfg = self._mgr._spec.parameter_search
        if not (param_cfg.enabled and self._mgr._experiment_protocol is not None):
            return
        self._set_status(
            version,
            mode="sync",
            phase="queued",
            active=True,
            started_at=time.time(),
            base_weight_revision=base_weight_revision,
        )
        self._run_weight_opt_task(
            staging_path,
            version,
            current_weights,
            base_weight_revision=base_weight_revision,
            mode="sync",
        )

    def drain_completed_events(self) -> List[WeightOptCompletionEvent]:
        """Return and clear completed optimization events.

        CampaignManager owns applying these events. Keeping this explicit
        prevents the background worker from mutating champion or branch state.
        """
        with self._events_lock:
            events = list(self._completed_events)
            self._completed_events.clear()
        return events

    # ------------------------------------------------------------------
    # Internal: background thread body
    # ------------------------------------------------------------------

    def _bg_weight_opt_task(
        self,
        staging_path: str,
        version: int,
        current_weights: dict,
        base_weight_revision: int = 0,
    ) -> None:
        """Background thread: run weight opt and prepare an event on success.

        The worker may create immutable snapshot artifacts, but campaign state
        changes are committed later by CampaignManager on the main loop boundary.
        """
        self._run_weight_opt_task(
            staging_path,
            version,
            current_weights,
            base_weight_revision=base_weight_revision,
            mode="async",
        )

    def _run_weight_opt_task(
        self,
        staging_path: str,
        version: int,
        current_weights: dict,
        base_weight_revision: int = 0,
        mode: str = "async",
    ) -> None:
        """Run optimization and enqueue a main-thread commit event."""
        import os as _os
        import shutil as _shutil
        import time as _time
        from scion.runtime.workspace import _make_tree_writable
        from pathlib import Path as _Path

        label = "Background" if mode == "async" else "Synchronous"
        self._set_status(
            version,
            mode=mode,
            phase="running",
            active=True,
            started_at=time.time(),
            base_weight_revision=base_weight_revision,
        )
        t0 = _time.monotonic()
        try:
            # Call through the manager so that test monkey-patches of
            # ``cm._run_weight_optimization`` still take effect.
            opt_result = self._mgr._run_weight_optimization(
                staging_path, version, current_weights
            )
        except Exception as exc:
            logger.error("%s weight opt failed for champion v%d: %s", label, version, exc)
            self._finish_status(version, phase="failed", error=str(exc))
            return

        elapsed_min = (_time.monotonic() - t0) / 60.0

        if opt_result is None:
            self._finish_status(version, phase="skipped", elapsed_minutes=elapsed_min)
            return

        if not opt_result.improved:
            logger.info(
                "%s weight opt complete for champion v%d (%.1f min) — no improvement",
                label, version, elapsed_min,
            )
            self._enqueue_event(WeightOptCompletionEvent(
                version=version,
                base_weight_revision=base_weight_revision,
                result=opt_result,
                elapsed_minutes=elapsed_min,
                improved=False,
            ))
            self._finish_status(
                version,
                phase="completed",
                improved=False,
                elapsed_minutes=elapsed_min,
                n_evaluations=opt_result.n_evaluations,
            )
            return

        new_revision = base_weight_revision + 1

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
                "%s weight opt: failed to create snapshot for champion v%d_r%d: %s",
                label, version, new_revision, exc,
            )
            self._finish_status(version, phase="failed", error=str(exc))
            return

        # Recompute hash and read updated pool
        try:
            registry_path = _os.path.join(new_snapshot_path, "registry.yaml")
            new_pool = read_registry(registry_path)
            new_hash = self._mgr._materializer.compute_snapshot_hash(new_snapshot_path)
        except Exception as exc:
            logger.error(
                "%s weight opt: failed to recompute hash for champion v%d_r%d: %s",
                label, version, new_revision, exc,
            )
            self._finish_status(version, phase="failed", error=str(exc))
            return

        logger.info(
            "%s weight opt prepared champion v%d_r%d (%.1f min)",
            label, version, new_revision, elapsed_min,
        )
        self._enqueue_event(WeightOptCompletionEvent(
            version=version,
            base_weight_revision=base_weight_revision,
            result=opt_result,
            elapsed_minutes=elapsed_min,
            improved=True,
            new_revision=new_revision,
            snapshot_path=new_snapshot_path,
            snapshot_hash=new_hash,
            operator_pool=new_pool,
        ))
        self._finish_status(
            version,
            phase="completed",
            improved=True,
            elapsed_minutes=elapsed_min,
            n_evaluations=opt_result.n_evaluations,
            new_revision=new_revision,
        )

    def _enqueue_event(self, event: WeightOptCompletionEvent) -> None:
        with self._events_lock:
            self._completed_events.append(event)

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
        self._set_status(version, phase="preparing_workspace")

        # Locate runner
        runner = getattr(self._mgr._experiment_protocol, 'runner',
                         getattr(self._mgr._experiment_protocol, '_runner', None))
        if runner is None:
            logger.warning("No runner available for weight optimization")
            self._finish_status(version, phase="skipped", reason="missing_runner")
            return None

        # Require a registry.yaml in the snapshot
        registry_path = _os.path.join(champion_snapshot, "registry.yaml")
        if not _os.path.exists(registry_path):
            logger.warning("No registry.yaml in snapshot %s; skipping weight opt", champion_snapshot)
            self._finish_status(version, phase="skipped", reason="missing_registry")
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
        total_evaluations = 1 + param_cfg.n_initial_random + param_cfg.n_iterations
        self._set_status(
            version,
            phase="baseline",
            n_cases=len(resolved_cases),
            n_seeds=len(seeds),
            n_operators=len(operator_names),
            total_evaluations=total_evaluations,
            completed_evaluations=0,
            estimated_solver_runs=len(resolved_cases) * len(seeds) * (1 + total_evaluations),
        )

        # Collect baseline objectives for evaluate_weights comparisons
        baseline = collect_baseline(eval_ws, resolved_cases, seeds, runner, time_limit)
        metric_specs = getattr(self._mgr._experiment_protocol, "_metric_specs", None)
        if metric_specs is None:
            metric_specs = getattr(self._mgr._experiment_protocol, "metric_specs", None)

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
            self._set_status(version, phase="evaluating_weights")
            score = evaluate_weights(
                weights=weights,
                workspace=eval_ws,
                cases=resolved_cases,
                seeds=seeds,
                runner=runner,
                time_limit_sec=time_limit,
                baseline_objectives=baseline,
                metric_specs=metric_specs,
            )
            with self._status_lock:
                current = dict(self._active_status.get(version, {}))
                current["completed_evaluations"] = current.get("completed_evaluations", 0) + 1
                current["last_score"] = score
                current["last_progress_at"] = time.time()
                self._active_status[version] = current
            self._publish_status()
            return score

        optimizer = RandomLocalWeightOptimizer(search_space, eval_fn, seed=version)
        if getattr(param_cfg, 'strategy', 'random_local') == 'bayesian':
            optimizer = BayesianWeightOptimizer(search_space, eval_fn, seed=version)

        # T2: artifacts dir for saving observations JSON
        artifacts_dir = _os.path.join(self._mgr._campaign_dir, "artifacts")
        _os.makedirs(artifacts_dir, exist_ok=True)

        # T1: pass current_weights so optimizer evaluates true baseline first
        self._set_status(version, phase="optimizing")
        result = optimizer.optimize(current_weights, artifacts_dir=artifacts_dir)

        try:
            shutil.rmtree(eval_ws)
        except Exception:
            pass

        return result
