"""Shared CLI helpers."""

from __future__ import annotations

from pathlib import Path

import typer


def get_registry(campaign_dir: str):
    """Open LineageRegistry from scion.db in campaign_dir."""
    from scion.lineage.registry import LineageRegistry

    db_path = Path(campaign_dir).resolve() / "scion.db"
    if not db_path.exists():
        typer.echo(f"ERROR: scion.db not found at {db_path}", err=True)
        raise typer.Exit(code=1)
    return LineageRegistry(str(db_path))


__all__ = ["get_registry"]
