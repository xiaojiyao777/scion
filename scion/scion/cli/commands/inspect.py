"""`scion inspect` command registration."""

from __future__ import annotations

import json
from pathlib import Path
import typer

from scion.cli.commands.common import get_registry


def register_inspect_commands(inspect_app: typer.Typer) -> None:
    @inspect_app.command("weights")
    def inspect_weights(
        registry: str = typer.Option(
            ...,
            "--registry",
            help="Exact registry.yaml to inspect",
        ),
    ) -> None:
        """Show operator weights from one explicit registry value."""
        registry_path = Path(registry).resolve()
        if not registry_path.is_file():
            typer.echo(f"ERROR: registry.yaml not found: {registry_path}", err=True)
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

    @inspect_app.command("campaign")
    def inspect_campaign(
        campaign_dir: str = typer.Option(
            "campaign_out",
            "--campaign-dir",
            help="Campaign directory",
        ),
    ) -> None:
        """Campaign overview from ordinary experiment events."""
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
        """Branch details and ordinary experiment events for a branch."""
        registry = get_registry(campaign_dir)
        events = [
            event
            for event in registry.query_by_branch(branch_id)
            if str(event.get("event_kind") or "experiment") == "experiment"
        ]
        if not events:
            typer.echo(
                f"WARNING: no experiment events for branch {branch_id!r}",
                err=True,
            )

        output = {
            "branch_id": branch_id,
            "experiment_events": events,
        }
        typer.echo(json.dumps(output, indent=2, default=str))


__all__ = ["register_inspect_commands"]
