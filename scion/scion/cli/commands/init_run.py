"""`scion run` command registration."""

from __future__ import annotations

import json
import logging
import os
import signal
import threading
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional, Self

import typer
import yaml

from scion.cli.commands.data_roots import (
    activate_declared_problem_data_root,
    validate_declared_problem_data_cases,
    with_declared_problem_data_roots,
)
from scion.problem.contracts import ProblemAdapter

logger = logging.getLogger(__name__)


def _load_cli_problem_adapter(problem_yaml: Path) -> ProblemAdapter:
    """Load the adapter that owns the CLI campaign's sole problem spec."""

    try:
        payload = yaml.safe_load(problem_yaml.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(
            f"cannot read problem definition: {problem_yaml}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise TypeError(f"problem definition must be a YAML mapping: {problem_yaml}")
    problem_v1_path = (
        problem_yaml
        if payload.get("spec_version") == "problem-v1"
        else problem_yaml.parent / "problem-v1.yaml"
    )
    if not problem_v1_path.exists():
        raise ValueError(
            "adapter-backed problem-v1 definition is required; expected "
            f"{problem_v1_path}"
        )

    from scion.problem.loader import (
        load_problem_adapter,
        load_problem_spec_v1_from_yaml,
    )

    return load_problem_adapter(load_problem_spec_v1_from_yaml(problem_v1_path))


def _load_research_input(path: Path) -> dict[str, Any]:
    """Load one bounded ordinary research input before campaign construction."""

    from scion.core.research_input import (
        MAX_RESEARCH_INPUT_BYTES,
        normalize_research_input,
    )

    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ValueError(f"cannot read research input: {path}: {exc}") from exc
    if size > MAX_RESEARCH_INPUT_BYTES:
        raise ValueError(
            "research input file is too large: "
            f"{size} bytes > {MAX_RESEARCH_INPUT_BYTES}"
        )
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read research input: {path}: {exc}") from exc
    if len(raw) > MAX_RESEARCH_INPUT_BYTES:
        raise ValueError(
            "research input file is too large: "
            f"{len(raw)} bytes > {MAX_RESEARCH_INPUT_BYTES}"
        )
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid research input JSON: {exc}") from exc
    return normalize_research_input(decoded)


def _load_code_research_limits(path: Path):
    """Load one explicit ordinary JSON value enabling bounded C research."""

    from scion.core.code_research_limits import load_code_research_limits

    return load_code_research_limits(path)


def _load_research_histories(
    paths: list[Path],
    *,
    problem_spec: Any,
) -> tuple[dict[str, Any], ...]:
    """Load only explicitly named ordinary history files."""

    from scion.core.research_history import (
        load_research_histories,
        problem_id_from_spec,
    )

    return load_research_histories(
        paths,
        expected_problem_id=problem_id_from_spec(problem_spec),
    )


class _CampaignSignalStop(KeyboardInterrupt):
    """Raised by the CLI signal handler to stop the active campaign."""

    def __init__(
        self,
        signum: int,
        reason: str,
        *,
        interrupted_override: bool | None = None,
    ) -> None:
        self.signum = signum
        self.reason = reason
        self.interrupted_override = interrupted_override
        self.exit_status = (
            _OUTER_HARDWALL_EXIT_STATUS
            if reason == _OUTER_HARDWALL_REASON
            else 128 + int(signum)
        )
        super().__init__(reason)


_OUTER_HARDWALL_REASON = "OUTER_HARDWALL_EXCEEDED"
_OUTER_HARDWALL_EXIT_STATUS = 124


class _CampaignOuterHardwall:
    """One watchdog that interrupts the main thread through SIGTERM."""

    def __init__(
        self,
        seconds: float | None,
        *,
        kill_process: Callable[[int, int], None] = os.kill,
        process_id: Callable[[], int] = os.getpid,
    ) -> None:
        self.seconds = seconds
        self.expired = threading.Event()
        self._cancelled = threading.Event()
        self._kill_process = kill_process
        self._process_id = process_id
        self._thread: threading.Thread | None = None

    def __enter__(self) -> Self:
        if self.seconds is None:
            return self
        if self.seconds <= 0:
            raise ValueError("outer hardwall seconds must be greater than zero")
        self._thread = threading.Thread(
            target=self._watch,
            name="scion-outer-hardwall",
            daemon=True,
        )
        self._thread.start()
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self._cancelled.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def _watch(self) -> None:
        if self._cancelled.wait(float(self.seconds)):
            return
        self.expired.set()
        try:
            self._kill_process(self._process_id(), signal.SIGTERM)
        except OSError:
            logger.exception("Failed to deliver outer hardwall SIGTERM")


def _close_llm_client(llm_client: Any) -> None:
    close = getattr(llm_client, "close", None)
    if not callable(close):
        return
    try:
        close()
    except Exception:
        logger.warning("Failed to close LLM client resources", exc_info=True)


@contextmanager
def _campaign_signal_handlers(
    manager,
    *,
    hardwall: _CampaignOuterHardwall | None = None,
):
    """Install minimal terminal-signal handlers for a running campaign."""
    previous: dict[int, object] = {}
    stop_raised = False

    def _handler(signum: int, _frame) -> None:
        nonlocal stop_raised
        if stop_raised:
            return
        stop_raised = True
        if hardwall is not None and hardwall.expired.is_set():
            reason = _OUTER_HARDWALL_REASON
        else:
            signame = signal.Signals(signum).name
            reason = f"signal:{signame}"
        manager.request_stop(reason)
        interrupted_override = (
            True if reason == _OUTER_HARDWALL_REASON else None
        )
        raise _CampaignSignalStop(
            signum,
            reason,
            interrupted_override=interrupted_override,
        )

    handled_signals = [signal.SIGTERM, signal.SIGINT]
    if hasattr(signal, "SIGHUP"):
        handled_signals.append(signal.SIGHUP)
    for signum in handled_signals:
        previous[signum] = signal.getsignal(signum)
        signal.signal(signum, _handler)
    try:
        yield
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def _run_campaign_with_signal_finalization(
    manager: Any,
    *,
    requested_rounds: int,
    hardwall: _CampaignOuterHardwall,
) -> Any:
    """Keep terminal handlers installed until a caught stop is durable."""

    with _campaign_signal_handlers(manager, hardwall=hardwall), hardwall:
        try:
            return manager.run(requested_rounds=requested_rounds)
        except _CampaignSignalStop as exc:
            manager.finalize_requested_stop(
                exc.reason,
                interrupted_override=exc.interrupted_override,
            )
            raise


_INCOMPLETE_INFRA_STOP_EXIT_STATUS = 20
_RESOURCE_EXHAUSTED_EXIT_STATUS = 21


def _completion_from_run_result(result: Any) -> tuple[int, str]:
    completed = bool(getattr(result, "completed", False))
    stopped_reason = str(getattr(result, "stop_reason", "") or "")
    failure_categories = dict(getattr(result, "failure_categories", {}) or {})
    if completed:
        return 0, "command_returned"
    last_execution_outcome = dict(getattr(result, "last_execution_outcome", None) or {})
    if last_execution_outcome.get("outcome") == "resource_exhausted":
        return (
            _RESOURCE_EXHAUSTED_EXIT_STATUS,
            "incomplete_resource_stop:resource_exhausted",
        )
    if (
        last_execution_outcome.get("outcome") == "blocked_infra"
        or stopped_reason == "api_balance_exhausted"
        or any(
            "infra" in str(category).lower()
            or "provider" in str(category).lower()
            for category in failure_categories
        )
    ):
        return (
            _INCOMPLETE_INFRA_STOP_EXIT_STATUS,
            f"incomplete_infra_stop:{stopped_reason}",
        )
    return 0, "command_returned"


def _campaign_start_message(
    *,
    problem_name: str,
    requested_rounds: int,
    mock_llm: bool,
) -> str:
    """Render the ordinary direct-campaign start line."""

    return (
        f"Starting campaign: {problem_name} "
        f"(requested_rounds={requested_rounds}, mock_llm={mock_llm})"
    )


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
        research_input: Optional[str] = typer.Option(
            None,
            "--research-input",
            help=(
                "Path to bounded JSON containing the current research question "
                "and ordered prior observations"
            ),
        ),
        research_history: list[str] | None = typer.Option(
            None,
            "--research-history",
            help=(
                "Explicit prior research_history.jsonl path; repeat in desired "
                "campaign order"
            ),
        ),
        code_research_limits: Optional[str] = typer.Option(
            None,
            "--code-research-limits",
            help=(
                "Path to strict JSON limits enabling bounded read/search/ready "
                "turns before the independent code final decision"
            ),
        ),
        provider_call_cap: int | None = typer.Option(
            None,
            "--provider-call-cap",
            min=1,
            help="Maximum actual proposal provider requests for this invocation",
        ),
        provider_transient_retries: int = typer.Option(
            0,
            "--provider-transient-retries",
            min=0,
            max=2,
            help=(
                "Bounded Scion redispatches per frozen request for typed transient "
                "provider failures (0 to 2, with short deterministic backoff; "
                "SDK retries remain disabled)"
            ),
        ),
        outer_hardwall_sec: int | None = typer.Option(
            None,
            "--outer-hardwall-sec",
            min=1,
            help="Outer wall-clock limit for the complete invocation",
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
                "Per solver run time limit; defaults to problem solver.time_limit_sec"
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
        research_input_value = None
        if research_input is not None:
            try:
                research_input_value = _load_research_input(
                    Path(research_input).resolve()
                )
            except (TypeError, ValueError) as exc:
                typer.echo(f"ERROR: {exc}", err=True)
                raise typer.Exit(code=1)
        code_research_limits_value = None
        if code_research_limits is not None:
            try:
                code_research_limits_value = _load_code_research_limits(
                    Path(code_research_limits).resolve()
                )
            except (TypeError, ValueError) as exc:
                typer.echo(f"ERROR: {exc}", err=True)
                raise typer.Exit(code=1)
        from scion.core.resource_envelope import ResourceEnvelope

        try:
            resource_envelope = ResourceEnvelope(
                provider_call_cap=provider_call_cap,
                outer_hardwall_sec=outer_hardwall_sec,
                provider_transient_retries=provider_transient_retries,
            )
        except (TypeError, ValueError) as exc:
            typer.echo(f"ERROR: {exc}", err=True)
            raise typer.Exit(code=1)
        from scion.config.problem import (
            ProtocolConfig,
            SeedLedgerConfig,
            SplitManifest,
        )

        problem_dir = problem_yaml.parent
        try:
            adapter = _load_cli_problem_adapter(problem_yaml)
        except Exception as exc:
            typer.echo(
                f"ERROR: failed to load problem-v1 adapter: {exc}",
                err=True,
            )
            raise typer.Exit(code=1)
        spec = adapter.spec
        problem_v1 = spec
        try:
            research_history_value = _load_research_histories(
                [Path(path) for path in (research_history or [])],
                problem_spec=spec,
            )
        except (TypeError, ValueError) as exc:
            typer.echo(f"ERROR: {exc}", err=True)
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
            validate_requested_screening_expansion,
        )
        from scion.runtime.subprocess_runner import LocalSubprocessRunner

        try:
            validate_requested_screening_expansion(
                config=proto_cfg,
                split_manifest=split_manifest,
                requested_rounds=rounds,
            )
        except ValueError as exc:
            typer.echo(f"ERROR: {exc}", err=True)
            raise typer.Exit(code=1)

        metrics_dir = str(campaign_path / "metrics")
        runner = LocalSubprocessRunner()
        split_manager = SplitManager(split_manifest)
        seed_ledger_obj = SeedLedger(seed_ledger)
        effective_time_limit = (
            time_limit_sec
            if time_limit_sec is not None
            else getattr(getattr(spec, "solver", None), "time_limit_sec", 300)
        )
        try:
            experiment_protocol = ExperimentProtocol(
                proto_cfg,
                split_manager,
                seed_ledger_obj,
                runner,
                time_limit_sec=effective_time_limit,
                metrics_dir=metrics_dir,
                adapter=adapter,
            )
        except ValueError as exc:
            typer.echo(f"ERROR: {exc}", err=True)
            raise typer.Exit(code=1)
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
                protocol_config=proto_cfg,
                split_manifest=split_manifest,
                seed_ledger=seed_ledger,
                llm_client=llm_client,
                champion=champion,
                campaign_dir=str(campaign_path),
                experiment_protocol=experiment_protocol,
                adapter=adapter,
                research_input=research_input_value,
                research_history=research_history_value,
                resource_envelope=resource_envelope,
                code_research_limits=code_research_limits_value,
            )

            requested_rounds = rounds
            typer.echo(
                _campaign_start_message(
                    problem_name=(
                        getattr(spec, "display_name", None)
                        or getattr(spec, "name", None)
                        or getattr(spec, "id", "problem")
                    ),
                    requested_rounds=requested_rounds,
                    mock_llm=mock_llm,
                )
            )
            try:
                hardwall = _CampaignOuterHardwall(resource_envelope.outer_hardwall_sec)
                run_result = _run_campaign_with_signal_finalization(
                    mgr,
                    requested_rounds=requested_rounds,
                    hardwall=hardwall,
                )
            except _CampaignSignalStop as exc:
                typer.echo(f"Campaign stopped: {exc.reason}", err=True)
                raise typer.Exit(code=exc.exit_status)
            else:
                exit_status, exit_reason = _completion_from_run_result(run_result)
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


__all__ = [
    "_CampaignOuterHardwall",
    "_load_code_research_limits",
    "_load_research_histories",
    "_load_research_input",
    "_run_campaign_with_signal_finalization",
    "register_run_command",
]
