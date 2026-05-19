"""Shared CLI helpers."""

from __future__ import annotations

from pathlib import Path

import typer


def validate_cli_forced_surface(
    spec: object,
    *,
    force_surface: str | None,
    force_action: str | None,
    force_target_file: str | None,
):
    if force_surface is None:
        return None
    from scion.core.forced_surface import validate_forced_surface_request

    try:
        return validate_forced_surface_request(
            spec,
            force_surface,
            action=force_action,
            target_file=force_target_file,
        )
    except ValueError as exc:
        typer.echo(f"ERROR: invalid --force-surface: {exc}", err=True)
        raise typer.Exit(code=1)


def get_registry(campaign_dir: str):
    """Open LineageRegistry from scion.db in campaign_dir."""
    from scion.lineage.registry import LineageRegistry

    db_path = Path(campaign_dir).resolve() / "scion.db"
    if not db_path.exists():
        typer.echo(f"ERROR: scion.db not found at {db_path}", err=True)
        raise typer.Exit(code=1)
    return LineageRegistry(str(db_path))


__all__ = ["get_registry", "validate_cli_forced_surface"]
