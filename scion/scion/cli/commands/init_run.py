"""`scion init` and `scion run` command registration."""

from __future__ import annotations

import json
import logging
import os
import signal
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Mapping, Optional

import typer

from scion.cli.commands.common import validate_cli_forced_surface
from scion.cli.commands.data_roots import (
    activate_declared_problem_data_root,
    validate_declared_problem_data_cases,
    with_declared_problem_data_roots,
)
from scion.core.research_surface_index import editable_identity_patterns

logger = logging.getLogger(__name__)


class _CampaignSignalStop(KeyboardInterrupt):
    """Raised by the CLI signal handler after recording stop intent."""

    def __init__(self, signum: int, reason: str) -> None:
        self.signum = signum
        self.reason = reason
        super().__init__(reason)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def _fd_target(fd: int) -> str:
    proc_fd = Path(f"/proc/self/fd/{fd}")
    try:
        return os.readlink(proc_fd)
    except OSError:
        return f"fd:{fd}"


def _pattern_set(patterns: Any) -> frozenset[str] | None:
    normalized = frozenset(
        pattern
        for pattern in (str(value).strip() for value in (patterns or ()))
        if pattern
    )
    return normalized or None


def _materializer_kwargs_from_problem_spec(problem_spec: Any) -> dict[str, Any]:
    search_space = getattr(problem_spec, "search_space", None)
    return {
        "frozen_patterns": _pattern_set(getattr(search_space, "frozen", ())),
        "editable_patterns": editable_identity_patterns(problem_spec),
    }


def _build_workspace_materializer(campaign_path: Path, problem_spec: Any) -> Any:
    from scion.runtime.workspace import WorkspaceMaterializer

    return WorkspaceMaterializer(
        str(campaign_path),
        **_materializer_kwargs_from_problem_spec(problem_spec),
    )


def _compute_initial_champion_snapshot_hash(
    campaign_path: Path,
    problem_spec: Any,
) -> str:
    materializer = _build_workspace_materializer(campaign_path, problem_spec)
    return materializer.compute_snapshot_hash(problem_spec.root_dir)


def _close_llm_client(llm_client: Any) -> None:
    close = getattr(llm_client, "close", None)
    if not callable(close):
        return
    try:
        close()
    except Exception:
        logger.warning("Failed to close LLM client resources", exc_info=True)


class _RunAudit:
    """Best-effort CLI wrapper audit files for detached/nohup launches."""

    def __init__(self, campaign_path: Path) -> None:
        self.campaign_path = campaign_path
        self.path = campaign_path / "run_status.json"
        self.exit_path = campaign_path / "exit.txt"
        self.started_at = _utc_now_iso()
        self.payload = {
            "schema": "scion.run_wrapper_audit.v1",
            "status": "running",
            "run_pid": os.getpid(),
            "started_at": self.started_at,
            "ended_at": None,
            "wrapper_exit_status": None,
            "wrapper_signal": None,
            "stdout": _fd_target(1),
            "stderr": _fd_target(2),
        }

    def start(self) -> None:
        self._write()

    def finish(
        self,
        *,
        exit_status: int,
        reason: str,
        signal_name: str | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> None:
        status = "signal" if signal_name else "finished"
        if (
            not signal_name
            and extra
            and extra.get("campaign_exit_status") == "incomplete_infra_stop"
        ):
            status = "incomplete"
        self.payload.update(
            {
                "status": status,
                "ended_at": _utc_now_iso(),
                "wrapper_exit_status": int(exit_status),
                "wrapper_signal": signal_name,
                "exit_reason": reason,
            }
        )
        if extra:
            self.payload.update(dict(extra))
        self._write()
        self._write_exit_txt()

    def _write(self) -> None:
        try:
            self.campaign_path.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps(self.payload, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            tmp.replace(self.path)
        except OSError:
            pass

    def _write_exit_txt(self) -> None:
        try:
            lines = [
                f"WRAPPER_EXIT_STATUS:{self.payload.get('wrapper_exit_status')}",
                f"WRAPPER_SIGNAL:{self.payload.get('wrapper_signal') or ''}",
                f"EXIT_REASON:{self.payload.get('exit_reason') or ''}",
                f"CAMPAIGN_EXIT_STATUS:{self.payload.get('campaign_exit_status') or ''}",
                f"RUN_VALIDITY_STATUS:{self.payload.get('run_validity_status') or ''}",
                f"RUN_COMPLETE:{self.payload.get('run_complete')}",
                "COMPLETED_REQUESTED_ROUNDS:"
                f"{self.payload.get('completed_requested_rounds')}",
                f"LAST_STOP_REASON:{self.payload.get('last_stop_reason') or ''}",
                f"RUN_PID:{self.payload.get('run_pid')}",
                f"STARTED_AT:{self.payload.get('started_at')}",
                f"ENDED_AT:{self.payload.get('ended_at')}",
                f"STDOUT:{self.payload.get('stdout') or ''}",
                f"STDERR:{self.payload.get('stderr') or ''}",
            ]
            self.exit_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError:
            pass


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


def _wrapper_completion_from_campaign(
    campaign_path: Path,
) -> tuple[int, str, dict[str, Any]]:
    for filename in ("campaign_summary.json", "status.json"):
        payload = _read_json_mapping(campaign_path / filename)
        if not payload:
            continue
        result = _wrapper_completion_from_payload(payload)
        if result is not None:
            return result
    return 0, "command_returned", {"campaign_exit_status": "complete_or_unknown"}


def _read_json_mapping(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _wrapper_completion_from_payload(
    payload: Mapping[str, Any],
) -> tuple[int, str, dict[str, Any]] | None:
    raw_validity = payload.get("run_validity")
    if not isinstance(raw_validity, Mapping):
        return None
    validity: Mapping[str, Any] = raw_validity
    completed = _bool_value(
        validity.get(
            "completed_requested_rounds",
            validity.get("complete", payload.get("run_complete")),
        ),
        default=False,
    )
    stopped_reason = str(
        payload.get("last_stop_reason")
        or payload.get("stopped_reason")
        or validity.get("stopped_reason")
        or ""
    )
    validity_reason = str(
        validity.get("reason") or payload.get("run_validity_status") or ""
    )
    run_fields = {
        "campaign_exit_status": "complete" if completed else "incomplete",
        "run_validity_status": validity_reason,
        "run_complete": completed,
        "completed_requested_rounds": completed,
        "last_stop_reason": stopped_reason,
        "run_completeness_status": validity.get("completeness_status"),
    }
    if completed:
        return 0, "command_returned", run_fields
    if _is_incomplete_infra_stop(payload, validity, stopped_reason=stopped_reason):
        run_fields["campaign_exit_status"] = "incomplete_infra_stop"
        return (
            _INCOMPLETE_INFRA_STOP_EXIT_STATUS,
            f"incomplete_infra_stop:{validity_reason or stopped_reason}",
            run_fields,
        )
    return 0, "command_returned", run_fields


def _is_incomplete_infra_stop(
    payload: Mapping[str, Any],
    validity: Mapping[str, Any],
    *,
    stopped_reason: str,
) -> bool:
    if stopped_reason == "api_balance_exhausted":
        return True
    if str(payload.get("stop_category") or "") == "provider_error":
        return True
    provider_error = payload.get("provider_error")
    if isinstance(provider_error, Mapping) and provider_error:
        return True
    try:
        if int(validity.get("infra_failure_attempts") or 0) > 0:
            return True
    except (TypeError, ValueError):
        pass
    return False


def _bool_value(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return default


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
        proposal_quality_loop_limit: Optional[int] = typer.Option(
            None,
            "--proposal-quality-loop-limit",
            help=(
                "Maximum proposal-quality blocks before stopping; defaults to "
                "rounds + max(6, rounds * 2), or SCION_PROPOSAL_QUALITY_LOOP_LIMIT"
            ),
        ),
        proposal_attempt_limit: Optional[int] = typer.Option(
            None,
            "--proposal-attempt-limit",
            help=(
                "Maximum user-visible LLM proposal attempts before stopping; "
                "defaults to rounds + max(6, rounds * 2), or "
                "SCION_PROPOSAL_ATTEMPT_LIMIT"
            ),
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
        measurement_governance: Literal["on", "record-only"] = typer.Option(
            "on",
            "--measurement-governance",
            help=(
                "Use problem measurement to govern protocol behavior, or "
                "record reduced readiness status only"
            ),
        ),
        proposal_context_ablation: Literal[
            "full",
            "no-measurement-diagnostics",
            "minimal-research-context",
        ] = typer.Option(
            "full",
            "--proposal-context-ablation",
            help=(
                "Ablate only proposal-prompt visible context; does not change "
                "protocol measurement governance or DecisionFeatures"
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
        allow_skeleton: bool = typer.Option(
            False,
            "--allow-skeleton",
            help=(
                "Explicitly allow legacy skeleton/demo fallback when production "
                "adapter/protocol evidence is incomplete"
            ),
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
        problem_v1 = None
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
            governance_mode=measurement_governance,
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

        from scion.protocol.experiment import ExperimentProtocol, SeedLedger, SplitManager
        from scion.runtime.subprocess_runner import LocalSubprocessRunner
        from scion.verification.gate import VerificationGate
        from scion.core.production_boundary import (
            is_adapter_backed_production_campaign,
            validate_production_campaign_boundary,
        )

        metrics_dir = str(campaign_path / "metrics")
        runner = LocalSubprocessRunner()
        split_manager = SplitManager(split_manifest)
        seed_ledger_obj = SeedLedger(seed_ledger)
        effective_time_limit = (
            time_limit_sec
            if time_limit_sec is not None
            else getattr(getattr(spec, "solver", None), "time_limit_sec", 300)
        )
        production_campaign = is_adapter_backed_production_campaign(
            problem_spec=spec,
            adapter=adapter,
            allow_skeleton=allow_skeleton,
        )
        require_metric_specs = production_campaign
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
                require_metric_specs=require_metric_specs,
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
            strict_runtime_checks=production_campaign,
            require_adapter_for_runtime=production_campaign,
            allow_adapter_runtime_fallback=allow_skeleton,
            operator_execute_signature=operator_execute_signature,
            max_runtime_ratio=proto_cfg.runtime.max_runtime_ratio,
        )
        try:
            validate_production_campaign_boundary(
                problem_spec=spec,
                experiment_protocol=experiment_protocol,
                adapter=adapter,
                split_manifest=split_manifest,
                seed_ledger=seed_ledger,
                verification_gate=verification_gate,
                allow_skeleton=allow_skeleton,
            )
        except ValueError as exc:
            typer.echo(f"ERROR: {exc}", err=True)
            raise typer.Exit(code=1)

        from scion.core.models import ChampionState
        from scion.runtime.pool_manager import read_registry

        code_hash = _compute_initial_champion_snapshot_hash(campaign_path, spec)

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

        resolved_agentic_artifact_dir = (
            str(Path(agentic_artifact_dir).resolve())
            if agentic_artifact_dir is not None
            else str(campaign_path / "agentic_sessions")
            if agentic_proposal
            else None
        )

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
                force_continue_early_stop=disable_early_stop,
                use_agentic_proposal=agentic_proposal,
                agentic_artifact_dir=resolved_agentic_artifact_dir,
                agentic_session_timeout_sec=agentic_session_timeout_sec,
                allow_skeleton_mode=allow_skeleton,
                force_surface=forced_request.surface if forced_request else None,
                force_action=forced_request.action if forced_request else None,
                force_target_file=forced_request.target_file if forced_request else None,
                proposal_quality_loop_limit=proposal_quality_loop_limit,
                proposal_attempt_limit=proposal_attempt_limit,
                proposal_context_ablation=proposal_context_ablation,
            )

            forced_surface_note = (
                f", force_surface={forced_request.surface}" if forced_request else ""
            )
            typer.echo(
                f"Starting campaign: {spec.name} "
                f"(max_rounds={rounds}, mock_llm={mock_llm}, "
                f"disable_early_stop={disable_early_stop}{forced_surface_note})"
            )
            run_audit = _RunAudit(campaign_path)
            run_audit.start()
            try:
                with _campaign_signal_handlers(mgr):
                    mgr.run(max_rounds=rounds)
            except _CampaignSignalStop as exc:
                mgr.finalize_requested_stop(exc.reason)
                run_audit.finish(
                    exit_status=128 + int(exc.signum),
                    reason=exc.reason,
                    signal_name=signal.Signals(exc.signum).name,
                )
                typer.echo(f"Campaign stopped: {exc.reason}", err=True)
                raise typer.Exit(code=128 + int(exc.signum))
            except Exception as exc:
                run_audit.finish(
                    exit_status=1,
                    reason=f"exception:{type(exc).__name__}",
                )
                raise
            else:
                exit_status, exit_reason, exit_extra = _wrapper_completion_from_campaign(
                    campaign_path
                )
                run_audit.finish(
                    exit_status=exit_status,
                    reason=exit_reason,
                    extra=exit_extra,
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


__all__ = ["register_init_run_commands"]
