"""`scion inspect` command registration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from scion.cli.commands.common import get_registry


def register_inspect_commands(inspect_app: typer.Typer) -> None:
    @inspect_app.command("weights")
    def inspect_weights(
        campaign_dir: str = typer.Option(
            "campaign_out",
            "--campaign-dir",
            help="Campaign directory",
        ),
    ) -> None:
        """Show current champion operator weights from registry.yaml."""
        campaign_path = Path(campaign_dir).resolve()
        state_file = campaign_path / ".scion_state.json"
        registry_path: Optional[Path] = None

        db_path = campaign_path / "scion.db"
        if db_path.exists():
            import sqlite3 as _sqlite3

            try:
                with _sqlite3.connect(str(db_path)) as conn:
                    row = conn.execute(
                        "SELECT code_snapshot_path FROM champions "
                        "ORDER BY version DESC LIMIT 1"
                    ).fetchone()
                    if row and row[0]:
                        candidate = Path(row[0]) / "registry.yaml"
                        if candidate.exists():
                            registry_path = candidate
            except Exception:
                pass

        if registry_path is None and state_file.exists():
            try:
                state = json.loads(state_file.read_text())
                problem_yaml = state.get("problem_yaml", "")
                if problem_yaml:
                    candidate = Path(problem_yaml).parent / "registry.yaml"
                    if candidate.exists():
                        registry_path = candidate
            except Exception:
                pass

        if registry_path is None:
            typer.echo(
                "ERROR: no registry.yaml found "
                "(run 'scion init' and ensure registry.yaml exists)",
                err=True,
            )
            raise typer.Exit(code=1)

        try:
            from scion.runtime.pool_manager import read_registry

            pool = read_registry(str(registry_path))
        except Exception as exc:
            typer.echo(f"ERROR: failed to read registry.yaml: {exc}", err=True)
            raise typer.Exit(code=1)

        typer.echo(f"Operator weights ({registry_path}):")
        typer.echo(f"  {'Name':<30} {'Weight':>8}  {'Category':<20}  File")
        typer.echo(f"  {'-'*30} {'-'*8}  {'-'*20}  {'-'*40}")
        for name, op in sorted(pool.items(), key=lambda x: -x[1].weight):
            typer.echo(
                f"  {name:<30} {op.weight:>8.4f}  "
                f"{(op.category or ''):<20}  {op.file_path}"
            )

    @inspect_app.command("agentic-session")
    def inspect_agentic_session(
        artifact: str = typer.Option(
            ...,
            "--artifact",
            help="Path to APS output artifact JSON",
        ),
    ) -> None:
        """Validate and summarize a compact agentic proposal-session artifact."""
        from scion.proposal.agentic_session import inspect_agentic_session_artifact

        try:
            summary = inspect_agentic_session_artifact(Path(artifact).resolve())
        except Exception as exc:
            typer.echo(
                f"ERROR: failed to inspect agentic session artifact: {exc}",
                err=True,
            )
            raise typer.Exit(code=1)

        typer.echo(json.dumps(summary, indent=2, sort_keys=True))
        if not summary.get("validation", {}).get("ok"):
            raise typer.Exit(code=1)

    @inspect_app.command("agentic-sessions")
    def inspect_agentic_sessions(
        campaign_dir: str = typer.Option(
            "campaign_out",
            "--campaign-dir",
            help="Campaign directory",
        ),
        artifact_dir: Optional[str] = typer.Option(
            None,
            "--artifact-dir",
            help=(
                "APS artifact directory; defaults to "
                "campaign_dir/artifacts/agentic_proposal_sessions"
            ),
        ),
    ) -> None:
        """List persisted agentic proposal sessions from the recovery index."""
        from scion.proposal.agentic_session import AgenticSessionStore

        root = (
            Path(artifact_dir).resolve()
            if artifact_dir
            else Path(campaign_dir).resolve() / "artifacts" / "agentic_proposal_sessions"
        )
        store = AgenticSessionStore(root)
        sessions = store.list_sessions()

        def _ops_validation_errors(errors):
            cleaned = []
            for error in errors:
                text = str(error)
                if text.startswith("raw ref marker found:"):
                    cleaned.append("raw ref marker found")
                else:
                    cleaned.append(text)
            return cleaned

        output = {
            "artifact_dir": str(root),
            "index_path": str(store.index_path),
            "sessions": [
                {
                    "session_id": stored.entry.session_id,
                    "request_id": stored.entry.request_id,
                    "idempotency_key": stored.entry.idempotency_key,
                    "status": stored.entry.status,
                    "termination_reason": stored.entry.termination_reason,
                    "tool_budget_used": dict(stored.entry.tool_budget_used),
                    "tool_loop_config": dict(stored.entry.tool_loop_config),
                    "transcript_digest": stored.entry.transcript_digest,
                    "artifact_ref": stored.entry.artifact_ref,
                    "schema_version": stored.entry.schema_version,
                    "tainted": stored.entry.tainted,
                    "updated_at": stored.entry.updated_at,
                    "validation": {
                        "ok": stored.validation.ok,
                        "errors": _ops_validation_errors(stored.validation.errors),
                    },
                }
                for stored in sessions
            ],
        }
        typer.echo(json.dumps(output, indent=2, sort_keys=True))

    @inspect_app.command("campaign")
    def inspect_campaign(
        campaign_dir: str = typer.Option(
            "campaign_out",
            "--campaign-dir",
            help="Campaign directory",
        ),
    ) -> None:
        """Campaign overview: total events, branches, champions, gate stats."""
        registry = get_registry(campaign_dir)
        summary = registry.get_campaign_summary()

        weight_opts = registry.query_weight_optimizations()
        if weight_opts:
            latest = weight_opts[-1]
            best_weights = {}
            try:
                best_weights = json.loads(latest.get("best_weights_json") or "{}")
            except Exception:
                pass
            summary["weight_optimization"] = {
                "total_runs": len(weight_opts),
                "latest_champion_version": latest.get("champion_version"),
                "latest_improved": bool(latest.get("improved")),
                "latest_baseline_score": latest.get("baseline_score"),
                "latest_best_score": latest.get("best_score"),
                "latest_best_weights": best_weights,
            }
        else:
            summary["weight_optimization"] = None

        typer.echo(json.dumps(summary, indent=2))

    @inspect_app.command("branch")
    def inspect_branch(
        branch_id: str = typer.Argument(..., help="Branch ID to inspect"),
        campaign_dir: str = typer.Option(
            "campaign_out",
            "--campaign-dir",
            help="Campaign directory",
        ),
    ) -> None:
        """Branch details: all experiment events and hypotheses for a branch."""
        registry = get_registry(campaign_dir)
        from scion.lineage.branch_store import BranchStore, HypothesisStore

        branch_store = BranchStore(registry)
        hyp_store = HypothesisStore(registry)

        branch = branch_store.load(branch_id)
        if branch is None:
            typer.echo(
                f"WARNING: branch {branch_id!r} not found in branches table",
                err=True,
            )

        events = registry.query_by_branch(branch_id)
        hypotheses = hyp_store.get_by_branch(branch_id)

        output = {
            "branch_id": branch_id,
            "branch": {
                "state": branch.state.value if branch else None,
                "base_champion_id": branch.base_champion_id if branch else None,
                "retry_count": branch.retry_count if branch else None,
                "created_at": branch.created_at.isoformat() if branch else None,
            },
            "experiment_events": events,
            "hypotheses": [
                {
                    "hypothesis_id": h.hypothesis_id,
                    "action": h.action,
                    "change_locus": h.change_locus,
                    "target_file": h.target_file,
                    "status": h.status,
                    "hypothesis_text": (h.hypothesis_text or "")[:300],
                    "created_at": h.created_at.isoformat(),
                }
                for h in hypotheses
            ],
        }
        typer.echo(json.dumps(output, indent=2, default=str))

    @inspect_app.command("hypothesis")
    def inspect_hypothesis(
        hyp_id: str = typer.Argument(..., help="Hypothesis ID to inspect"),
        campaign_dir: str = typer.Option(
            "campaign_out",
            "--campaign-dir",
            help="Campaign directory",
        ),
    ) -> None:
        """Hypothesis details: full record for a single hypothesis."""
        registry = get_registry(campaign_dir)
        from scion.lineage.branch_store import HypothesisStore

        store = HypothesisStore(registry)
        hyp = store.get_one(hyp_id)
        if hyp is None:
            typer.echo(f"ERROR: hypothesis {hyp_id!r} not found", err=True)
            raise typer.Exit(code=1)

        output = {
            "hypothesis_id": hyp.hypothesis_id,
            "branch_id": hyp.branch_id,
            "action": hyp.action,
            "change_locus": hyp.change_locus,
            "target_file": hyp.target_file,
            "status": hyp.status,
            "hypothesis_text": hyp.hypothesis_text,
            "suggested_weight": hyp.suggested_weight,
            "parent_hypothesis_id": hyp.parent_hypothesis_id,
            "created_at": hyp.created_at.isoformat(),
        }
        typer.echo(json.dumps(output, indent=2))

        events = registry.query_by_branch(hyp.branch_id)
        hyp_events = [e for e in events if e.get("hypothesis_id") == hyp_id]
        if hyp_events:
            typer.echo("\nRelated experiment events:")
            typer.echo(json.dumps(hyp_events, indent=2, default=str))


__all__ = ["register_inspect_commands"]
