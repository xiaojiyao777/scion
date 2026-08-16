"""`scion run` command registration."""

from __future__ import annotations

import logging
import os
import signal
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

import typer

from scion.cli.commands.data_roots import (
    activate_declared_problem_data_root,
    validate_declared_problem_data_cases,
    with_declared_problem_data_roots,
)

logger = logging.getLogger(__name__)


class _CampaignSignalStop(KeyboardInterrupt):
    """Raised by the CLI signal handler to stop the active campaign."""

    def __init__(self, signum: int, reason: str) -> None:
        self.signum = signum
        self.reason = reason
        super().__init__(reason)


def _close_llm_client(llm_client: Any) -> None:
    close = getattr(llm_client, "close", None)
    if not callable(close):
        return
    try:
        close()
    except Exception:
        logger.warning("Failed to close LLM client resources", exc_info=True)


@contextmanager
def _campaign_signal_handlers(manager):
    """Install minimal SIGTERM/SIGINT handlers for a running campaign."""
    previous: dict[int, object] = {}

    def _handler(signum: int, _frame) -> None:
        signame = signal.Signals(signum).name
        reason = f"signal:{signame}"
        manager.request_stop(reason)
        raise _CampaignSignalStop(signum, reason)

    for signum in (signal.SIGTERM, signal.SIGINT):
        previous[signum] = signal.getsignal(signum)
        signal.signal(signum, _handler)
    try:
        yield
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


_INCOMPLETE_INFRA_STOP_EXIT_STATUS = 20


def _completion_from_run_result(result: Any) -> tuple[int, str]:
    completed = bool(getattr(result, "completed", False))
    stopped_reason = str(getattr(result, "stop_reason", "") or "")
    failure_categories = dict(getattr(result, "failure_categories", {}) or {})
    if completed:
        return 0, "command_returned"
    if stopped_reason == "api_balance_exhausted" or any(
        "infra" in str(category).lower()
        or "provider" in str(category).lower()
        for category in failure_categories
    ):
        return (
            _INCOMPLETE_INFRA_STOP_EXIT_STATUS,
            f"incomplete_infra_stop:{stopped_reason}",
        )
    return 0, "command_returned"


def register_run_command(app: typer.Typer) -> None:
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
            help="Target number of typed formal protocol evaluated rounds",
        ),
        campaign_dir: str = typer.Option(
            "campaign_out",
            "--campaign-dir",
            help="Fresh output directory for this campaign",
        ),
        problem: str = typer.Option(
            ...,
            "--problem",
            help="Path to problem.yaml",
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
    ) -> None:
        """Run the Scion main loop.

        Use --mock-llm for local testing (no API key required).
        """
        campaign_path = Path(campaign_dir).resolve()

        problem_yaml = Path(problem).resolve()
        if not problem_yaml.exists():
            typer.echo(f"ERROR: problem.yaml not found: {problem_yaml}", err=True)
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
        problem_v1 = None
        problem_v1_path = problem_dir / "problem-v1.yaml"
        if problem_v1_path.exists():
            try:
                from scion.problem.bridge import (
                    bridge_problem_spec_v1,
                    load_problem_spec_v1_from_yaml,
                )
                from scion.problem.loader import load_problem_adapter

                problem_v1 = load_problem_spec_v1_from_yaml(problem_v1_path)
                bridge = bridge_problem_spec_v1(problem_v1)
                spec = bridge.problem_spec
                adapter = load_problem_adapter(problem_v1)
                metric_specs = bridge.metric_specs
                objective_policy = bridge.objective_policy
                operator_execute_signature = bridge.operator_execute_signature
            except typer.Exit:
                raise
            except Exception as exc:
                typer.echo(
                    f"ERROR: failed to load problem-v1 adapter: {exc}",
                    err=True,
                )
                raise typer.Exit(code=1)
        if protocol:
            protocol_path = Path(protocol)
            proto_cfg = ProtocolConfig.from_yaml(protocol_path)
        else:
            proto_path = problem_dir / "protocol.yaml"
            protocol_path = proto_path if proto_path.exists() else None
            proto_cfg = (
                ProtocolConfig.from_yaml(str(proto_path))
                if proto_path.exists()
                else ProtocolConfig()
            )
        proto_cfg = proto_cfg.with_problem_measurement(
            problem_v1 or spec,
            governance_mode="on",
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

        try:
            data_root_activation = activate_declared_problem_data_root(
                problem_yaml=problem_yaml,
                protocol_path=protocol_path,
            )
            validate_declared_problem_data_cases(
                activation=data_root_activation,
                problem_yaml=problem_yaml,
                split_manifest=split_manifest,
            )
            split_manifest = with_declared_problem_data_roots(
                activation=data_root_activation,
                split_manifest=split_manifest,
            )
            if data_root_activation is not None and data_root_activation.activated:
                typer.echo(
                    "INFO: activated problem data root "
                    f"{data_root_activation.env_name}={data_root_activation.data_root}"
                )
        except ValueError as exc:
            typer.echo(f"ERROR: {exc}", err=True)
            raise typer.Exit(code=1)

        if seeds:
            seed_ledger = SeedLedgerConfig.from_yaml(seeds)
        else:
            seed_path = problem_dir / "seed_ledger.yaml"
            seed_ledger = (
                SeedLedgerConfig.from_yaml(str(seed_path))
                if seed_path.exists()
                else SeedLedgerConfig(screening=[42], validation=[1, 2], frozen=[10])
            )

        from scion.protocol.experiment import (
            ExperimentProtocol,
            SeedLedger,
            SplitManager,
        )
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
        effective_metric_specs = metric_specs if metric_specs else None
        try:
            experiment_protocol = ExperimentProtocol(
                proto_cfg,
                split_manager,
                seed_ledger_obj,
                runner,
                time_limit_sec=effective_time_limit,
                metrics_dir=metrics_dir,
                metric_specs=effective_metric_specs,
                objective_policy=objective_policy,
                problem_spec=spec,
            )
        except ValueError as exc:
            typer.echo(f"ERROR: {exc}", err=True)
            raise typer.Exit(code=1)
        verification_gate = VerificationGate(
            spec,
            runner,
            metrics_dir=metrics_dir,
            adapter=adapter,
            strict_runtime_checks=True,
            require_adapter_for_runtime=True,
            allow_adapter_runtime_fallback=False,
            operator_execute_signature=operator_execute_signature,
            max_runtime_ratio=proto_cfg.runtime.max_runtime_ratio,
        )
        from scion.core.models import ChampionState
        from scion.runtime.pool_manager import read_registry

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
            code_snapshot_path=spec.root_dir,
        )

        from scion.core.campaign import CampaignManager

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

        try:
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
            )

            requested_rounds = rounds
            typer.echo(
                f"Starting campaign: {spec.name} "
                f"(requested_rounds={requested_rounds}, mock_llm={mock_llm})"
            )
            try:
                with _campaign_signal_handlers(mgr):
                    run_result = mgr.run(requested_rounds=requested_rounds)
            except _CampaignSignalStop as exc:
                mgr.finalize_requested_stop(exc.reason)
                typer.echo(f"Campaign stopped: {exc.reason}", err=True)
                raise typer.Exit(code=128 + int(exc.signum))
            else:
                exit_status, exit_reason = _completion_from_run_result(
                    run_result
                )
                if exit_status != 0:
                    typer.echo(f"Campaign incomplete: {exit_reason}", err=True)
                    raise typer.Exit(code=exit_status)

            state_data = mgr.get_state()
            typer.echo("Campaign finished.")
            typer.echo(f"  experiments  : {state_data['n_experiments']}")
            typer.echo(f"  champion ver : {state_data['champion_version']}")
            typer.echo(f"  active branches: {state_data['n_active_branches']}")
        finally:
            _close_llm_client(llm_client)


__all__ = ["register_run_command"]
