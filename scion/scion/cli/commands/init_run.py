"""`scion init` and `scion run` command registration."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import typer

from scion.cli.commands.common import validate_cli_forced_surface


def register_init_run_commands(app: typer.Typer) -> None:
    @app.command()
    def init(
        problem: str = typer.Option(..., "--problem", help="Path to problem.yaml"),
        campaign_dir: str = typer.Option(
            "campaign_out",
            "--campaign-dir",
            help="Output directory for campaign artefacts",
        ),
    ) -> None:
        """Initialise a Scion campaign from a problem.yaml specification."""
        problem_path = Path(problem).resolve()
        if not problem_path.exists():
            typer.echo(f"ERROR: problem file not found: {problem_path}", err=True)
            raise typer.Exit(code=1)

        campaign_path = Path(campaign_dir).resolve()
        campaign_path.mkdir(parents=True, exist_ok=True)

        try:
            from scion.config.problem import ProblemSpec

            spec = ProblemSpec.from_yaml(str(problem_path))
        except Exception as exc:
            typer.echo(f"ERROR: failed to parse problem.yaml: {exc}", err=True)
            raise typer.Exit(code=1)

        state = {
            "problem_yaml": str(problem_path),
            "campaign_dir": str(campaign_path),
            "problem_name": spec.name,
        }
        state_file = campaign_path / ".scion_state.json"
        state_file.write_text(json.dumps(state, indent=2))

        typer.echo(f"Campaign initialised: {campaign_path}")
        typer.echo(f"  problem : {spec.name}")
        typer.echo(f"  root_dir: {spec.root_dir}")

    @app.command()
    def run(
        mock_llm: bool = typer.Option(
            False,
            "--mock-llm",
            help="Use MockLLMClient (no real API calls)",
        ),
        rounds: int = typer.Option(
            10,
            "--rounds",
            help="Maximum number of campaign rounds",
        ),
        campaign_dir: str = typer.Option(
            "campaign_out",
            "--campaign-dir",
            help="Campaign directory (from scion init)",
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
        time_limit_sec: Optional[int] = typer.Option(
            None,
            "--time-limit-sec",
            help=(
                "Per solver run time limit; defaults to problem "
                "solver.time_limit_sec"
            ),
        ),
        disable_early_stop: bool = typer.Option(
            False,
            "--disable-early-stop",
            help="Diagnostic mode: do not stop early on idle/stagnation signals",
        ),
        force_surface: Optional[str] = typer.Option(
            None,
            "--force-surface",
            help="Diagnostic mode: force the next hypothesis to a declared research surface",
        ),
        force_action: Optional[str] = typer.Option(
            None,
            "--force-action",
            help="Diagnostic mode: force the hypothesis action for --force-surface",
        ),
        force_target_file: Optional[str] = typer.Option(
            None,
            "--force-target-file",
            help="Diagnostic mode: force the target_file for --force-surface",
        ),
        agentic_proposal: bool = typer.Option(
            False,
            "--agentic-proposal",
            help="Enable AgenticProposalSession for proposal generation",
        ),
        agentic_artifact_dir: Optional[str] = typer.Option(
            None,
            "--agentic-artifact-dir",
            help=(
                "APS artifact directory; defaults to campaign_dir/agentic_sessions "
                "when --agentic-proposal is enabled"
            ),
        ),
        agentic_session_timeout_sec: Optional[float] = typer.Option(
            None,
            "--agentic-session-timeout-sec",
            help="APS max wall time per session in seconds",
        ),
    ) -> None:
        """Run the Scion main loop.

        Use --mock-llm for local testing (no API key required).
        """
        campaign_path = Path(campaign_dir).resolve()
        state_file = campaign_path / ".scion_state.json"

        if problem:
            problem_yaml = Path(problem).resolve()
        elif state_file.exists():
            state = json.loads(state_file.read_text())
            problem_yaml = Path(state["problem_yaml"])
        else:
            typer.echo(
                "ERROR: no campaign state found - run 'scion init --problem <yaml>' first",
                err=True,
            )
            raise typer.Exit(code=1)

        if not problem_yaml.exists():
            typer.echo(f"ERROR: problem.yaml not found: {problem_yaml}", err=True)
            raise typer.Exit(code=1)
        if force_surface is None and (
            force_action is not None or force_target_file is not None
        ):
            typer.echo(
                "ERROR: --force-action and --force-target-file require --force-surface",
                err=True,
            )
            raise typer.Exit(code=1)

        from scion.config.problem import (
            ProblemSpec,
            ProtocolConfig,
            SeedLedgerConfig,
            SplitManifest,
        )

        spec = ProblemSpec.from_yaml(str(problem_yaml))
        problem_dir = problem_yaml.parent
        adapter = None
        metric_specs = None
        objective_policy = None
        operator_execute_signature = None
        forced_request = None
        problem_v1_path = problem_dir / "problem-v1.yaml"
        if problem_v1_path.exists():
            from scion.problem.preflight import (
                RuntimeDependencyPreflightError,
                run_runtime_preflight,
            )

            try:
                from scion.problem.bridge import (
                    bridge_problem_spec_v1,
                    load_problem_spec_v1_from_yaml,
                )
                from scion.problem.loader import load_problem_adapter

                problem_v1 = load_problem_spec_v1_from_yaml(problem_v1_path)
                run_runtime_preflight(problem_v1)
                bridge = bridge_problem_spec_v1(problem_v1)
                spec = bridge.problem_spec
                forced_request = validate_cli_forced_surface(
                    spec,
                    force_surface=force_surface,
                    force_action=force_action,
                    force_target_file=force_target_file,
                )
                adapter = load_problem_adapter(problem_v1)
                run_runtime_preflight(problem_v1, adapter=adapter)
                metric_specs = bridge.metric_specs
                objective_policy = bridge.objective_policy
                operator_execute_signature = bridge.operator_execute_signature
            except typer.Exit:
                raise
            except RuntimeDependencyPreflightError as exc:
                typer.echo(f"ERROR: {exc}", err=True)
                raise typer.Exit(code=1)
            except Exception as exc:
                typer.echo(
                    f"ERROR: failed to load problem-v1 adapter: {exc}",
                    err=True,
                )
                raise typer.Exit(code=1)
        if forced_request is None:
            forced_request = validate_cli_forced_surface(
                spec,
                force_surface=force_surface,
                force_action=force_action,
                force_target_file=force_target_file,
            )

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

        if mock_llm:
            from scion.proposal.mock_client import MockLLMClient

            llm_client = MockLLMClient(mode="success")
        else:
            try:
                from scion.proposal.llm_client import LLMClient

                llm_client = LLMClient()
            except Exception as exc:
                typer.echo(f"ERROR: failed to create LLMClient: {exc}", err=True)
                raise typer.Exit(code=1)

        from scion.protocol.experiment import ExperimentProtocol, SeedLedger, SplitManager
        from scion.runtime.subprocess_runner import LocalSubprocessRunner
        from scion.verification.gate import VerificationGate

        metrics_dir = str(campaign_path / "metrics")
        runner = LocalSubprocessRunner()
        split_manager = SplitManager(split_manifest)
        seed_ledger_obj = SeedLedger(seed_ledger)
        effective_time_limit = (
            time_limit_sec
            if time_limit_sec is not None
            else getattr(getattr(spec, "solver", None), "time_limit_sec", 300)
        )
        experiment_protocol = ExperimentProtocol(
            proto_cfg,
            split_manager,
            seed_ledger_obj,
            runner,
            time_limit_sec=effective_time_limit,
            metrics_dir=metrics_dir,
            metric_specs=metric_specs,
            objective_policy=objective_policy,
            require_metric_specs=metric_specs is not None,
            problem_spec=spec,
        )
        verification_gate = VerificationGate(
            spec,
            runner,
            metrics_dir=metrics_dir,
            adapter=adapter,
            strict_runtime_checks=adapter is not None,
            require_adapter_for_runtime=adapter is not None,
            operator_execute_signature=operator_execute_signature,
            max_runtime_ratio=proto_cfg.runtime.max_runtime_ratio,
        )

        from scion.core.models import ChampionState
        from scion.runtime.pool_manager import read_registry
        from scion.runtime.workspace import WorkspaceMaterializer

        materializer = WorkspaceMaterializer(
            str(campaign_path),
            frozen_patterns=(
                frozenset(spec.search_space.frozen)
                if spec.search_space.frozen
                else None
            ),
        )
        code_hash = materializer.compute_snapshot_hash(spec.root_dir)

        registry_path = os.path.join(spec.root_dir, "registry.yaml")
        if os.path.exists(registry_path):
            try:
                operator_pool = read_registry(registry_path)
            except Exception as exc:
                typer.echo(
                    f"WARNING: could not load registry.yaml: {exc}",
                    err=True,
                )
                operator_pool = {}
        else:
            operator_pool = {}

        champion = ChampionState(
            version=1,
            operator_pool=operator_pool,
            solver_config_hash="initial",
            code_snapshot_path=spec.root_dir,
            code_snapshot_hash=code_hash,
        )

        from scion.core.campaign import CampaignManager

        resolved_agentic_artifact_dir = (
            str(Path(agentic_artifact_dir).resolve())
            if agentic_artifact_dir is not None
            else str(campaign_path / "agentic_sessions")
            if agentic_proposal
            else None
        )

        mgr = CampaignManager(
            problem_spec=spec,
            protocol_config=proto_cfg,
            split_manifest=split_manifest,
            seed_ledger=seed_ledger,
            llm_client=llm_client,
            champion=champion,
            campaign_dir=str(campaign_path),
            verification_gate=verification_gate,
            experiment_protocol=experiment_protocol,
            adapter=adapter,
            operator_execute_signature=operator_execute_signature,
            force_continue_early_stop=disable_early_stop,
            use_agentic_proposal=agentic_proposal,
            agentic_artifact_dir=resolved_agentic_artifact_dir,
            agentic_session_timeout_sec=agentic_session_timeout_sec,
            force_surface=forced_request.surface if forced_request else None,
            force_action=forced_request.action if forced_request else None,
            force_target_file=forced_request.target_file if forced_request else None,
        )

        forced_surface_note = (
            f", force_surface={forced_request.surface}" if forced_request else ""
        )
        typer.echo(
            f"Starting campaign: {spec.name} "
            f"(max_rounds={rounds}, mock_llm={mock_llm}, "
            f"disable_early_stop={disable_early_stop}{forced_surface_note})"
        )
        mgr.run(max_rounds=rounds)

        state_data = mgr.get_state()
        typer.echo("Campaign finished.")
        typer.echo(f"  experiments  : {state_data['n_experiments']}")
        typer.echo(f"  champion ver : {state_data['champion_version']}")
        typer.echo(f"  active branches: {state_data['n_active_branches']}")


__all__ = ["register_init_run_commands"]
