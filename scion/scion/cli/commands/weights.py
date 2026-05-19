"""`scion optimize-weights` command registration."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import typer


def register_weight_commands(app: typer.Typer) -> None:
    @app.command("optimize-weights")
    def optimize_weights(
        campaign_dir: str = typer.Option(
            "campaign_out",
            "--campaign-dir",
            help="Campaign directory",
        ),
        problem: Optional[str] = typer.Option(
            None,
            "--problem",
            help="Path to problem.yaml (overrides state file)",
        ),
        protocol: Optional[str] = typer.Option(
            None,
            "--protocol",
            help="Path to protocol.yaml",
        ),
        split: Optional[str] = typer.Option(
            None,
            "--split",
            help="Path to split_manifest.yaml",
        ),
        seeds: Optional[str] = typer.Option(
            None,
            "--seeds",
            help="Path to seed_ledger.yaml",
        ),
    ) -> None:
        """Manually trigger weight optimisation on the latest champion snapshot."""
        campaign_path = Path(campaign_dir).resolve()
        state_file = campaign_path / ".scion_state.json"

        if problem:
            problem_yaml = Path(problem).resolve()
        elif state_file.exists():
            state = json.loads(state_file.read_text())
            problem_yaml = Path(state["problem_yaml"])
        else:
            typer.echo(
                "ERROR: no campaign state found - run 'scion init' first",
                err=True,
            )
            raise typer.Exit(code=1)

        if not problem_yaml.exists():
            typer.echo(f"ERROR: problem.yaml not found: {problem_yaml}", err=True)
            raise typer.Exit(code=1)

        from scion.config.problem import (
            ProblemSpec,
            ProtocolConfig,
            SeedLedgerConfig,
            SplitManifest,
        )
        from scion.parameter.evaluator import collect_baseline, evaluate_weights
        from scion.parameter.optimizer import RandomLocalWeightOptimizer
        from scion.parameter.search_space import ParameterSearchSpace
        from scion.runtime.pool_manager import read_weights
        from scion.runtime.subprocess_runner import LocalSubprocessRunner

        spec = ProblemSpec.from_yaml(str(problem_yaml))
        problem_dir = problem_yaml.parent
        metric_specs = None
        problem_v1_path = problem_dir / "problem-v1.yaml"
        if problem_v1_path.exists():
            try:
                from scion.problem.bridge import (
                    bridge_problem_spec_v1,
                    load_problem_spec_v1_from_yaml,
                )

                problem_v1 = load_problem_spec_v1_from_yaml(problem_v1_path)
                bridge = bridge_problem_spec_v1(problem_v1)
                spec = bridge.problem_spec
                metric_specs = bridge.metric_specs
            except Exception as exc:
                typer.echo(
                    f"ERROR: failed to load problem-v1 objective specs: {exc}",
                    err=True,
                )
                raise typer.Exit(code=1)

        if protocol:
            proto_cfg = ProtocolConfig.from_yaml(protocol)
        else:
            proto_path = problem_dir / "protocol.yaml"
            proto_cfg = (
                ProtocolConfig.from_yaml(str(proto_path))
                if proto_path.exists()
                else ProtocolConfig()
            )

        if split:
            split_manifest = SplitManifest.from_yaml(split)
        else:
            split_path = problem_dir / "split_manifest.yaml"
            split_manifest = (
                SplitManifest.from_yaml(str(split_path))
                if split_path.exists()
                else SplitManifest(screening=[], validation=[], frozen=[])
            )

        if seeds:
            seed_ledger = SeedLedgerConfig.from_yaml(seeds)
        else:
            seed_path = problem_dir / "seed_ledger.yaml"
            seed_ledger = (
                SeedLedgerConfig.from_yaml(str(seed_path))
                if seed_path.exists()
                else SeedLedgerConfig(screening=[42], validation=[1, 2], frozen=[10])
            )

        db_path = campaign_path / "scion.db"
        snapshot_path: Optional[Path] = None
        champion_version = 0
        if db_path.exists():
            import sqlite3 as _sqlite3

            try:
                with _sqlite3.connect(str(db_path)) as conn:
                    row = conn.execute(
                        "SELECT version, code_snapshot_path FROM champions "
                        "ORDER BY version DESC, weight_revision DESC LIMIT 1"
                    ).fetchone()
                    if row:
                        champion_version = row[0]
                        snapshot_path = Path(row[1]) if row[1] else None
            except Exception:
                pass

        if snapshot_path is None:
            snapshot_path = Path(spec.root_dir)
            typer.echo(
                f"WARNING: no champion in DB; using root_dir as snapshot: {snapshot_path}",
                err=True,
            )

        registry_path = snapshot_path / "registry.yaml"
        if not registry_path.exists():
            typer.echo(f"ERROR: registry.yaml not found at {registry_path}", err=True)
            raise typer.Exit(code=1)

        try:
            current_weights = read_weights(str(registry_path))
        except Exception as exc:
            typer.echo(f"ERROR: failed to read weights: {exc}", err=True)
            raise typer.Exit(code=1)

        if not current_weights:
            typer.echo(
                "ERROR: no operators in registry - nothing to optimise",
                err=True,
            )
            raise typer.Exit(code=1)

        typer.echo(f"Optimising weights for champion v{champion_version} at {snapshot_path}")
        typer.echo(f"  Operators: {list(current_weights.keys())}")

        param_cfg = spec.parameter_search
        runner = LocalSubprocessRunner()

        eval_cases = list(param_cfg.eval_cases)
        if not eval_cases:
            eval_cases = list(split_manifest.screening)
        resolved_cases = [
            os.path.join(spec.root_dir, c) if not os.path.isabs(c) else c
            for c in eval_cases
        ]
        if not resolved_cases:
            typer.echo(
                "WARNING: no eval cases configured; using registry-only optimisation skipped",
                err=True,
            )
            raise typer.Exit(code=1)

        eval_seeds = list(seed_ledger.screening)[: param_cfg.n_eval_seeds]
        time_limit = getattr(getattr(spec, "solver", None), "time_limit_sec", 300)
        artifacts_dir = str(campaign_path / "artifacts")
        os.makedirs(artifacts_dir, exist_ok=True)

        import shutil

        eval_ws = str(campaign_path / f"weight_opt_manual_v{champion_version}")
        if os.path.exists(eval_ws):
            shutil.rmtree(eval_ws)
        shutil.copytree(str(snapshot_path), eval_ws)
        for root, dirs, files in os.walk(eval_ws):
            for d in dirs:
                os.chmod(os.path.join(root, d), 0o755)
            for f in files:
                os.chmod(os.path.join(root, f), 0o644)

        typer.echo(f"  Eval cases: {resolved_cases}")
        typer.echo(f"  Eval seeds: {eval_seeds}")

        baseline = collect_baseline(eval_ws, resolved_cases, eval_seeds, runner, time_limit)
        operator_names = tuple(current_weights.keys())

        search_space = ParameterSearchSpace(
            operator_names=operator_names,
            weight_bounds=param_cfg.weight_bounds,
            n_initial_random=param_cfg.n_initial_random,
            n_iterations=param_cfg.n_iterations,
            n_eval_seeds=param_cfg.n_eval_seeds,
            eval_cases=tuple(resolved_cases),
        )

        def _eval_fn(weights):
            return evaluate_weights(
                weights=weights,
                workspace=eval_ws,
                cases=resolved_cases,
                seeds=eval_seeds,
                runner=runner,
                time_limit_sec=time_limit,
                baseline_objectives=baseline,
                metric_specs=metric_specs,
            )

        optimizer = RandomLocalWeightOptimizer(
            search_space,
            _eval_fn,
            seed=champion_version,
        )
        result = optimizer.optimize(current_weights, artifacts_dir=artifacts_dir)

        typer.echo("\nOptimisation complete:")
        typer.echo(f"  baseline_score : {result.baseline_score:.6f}")
        typer.echo(f"  best_score     : {result.best_score:.6f}")
        typer.echo(f"  improved       : {result.improved}")
        typer.echo(f"  n_evaluations  : {result.n_evaluations}")

        if result.improved:
            typer.echo("\nBest weights:")
            for name, w in result.best_weights.items():
                typer.echo(f"  {name}: {w:.6f}")
            typer.echo(
                "\nTo apply: manually update registry.yaml in the champion "
                "snapshot with the above weights."
            )
        else:
            typer.echo("\nNo improvement found over baseline - champion weights unchanged.")

        try:
            shutil.rmtree(eval_ws)
        except Exception:
            pass


__all__ = ["register_weight_commands"]
