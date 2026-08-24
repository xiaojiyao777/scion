"""Read-only postrun command for a frozen qualification predicate."""

from __future__ import annotations

from pathlib import Path

import typer

from scion.postrun.handoff import (
    QUALIFIED_TOKEN,
    UNAVAILABLE_TOKEN,
    QualificationAuditUnavailable,
    audit_qualification_campaign,
    load_qualification_audit_expectation,
)


def register_qualification_audit_command(app: typer.Typer) -> None:
    @app.command("audit-qualification-campaign")
    def audit_qualification_campaign_command(
        campaign_dir: str = typer.Argument(
            ...,
            help="Completed campaign directory to audit read-only",
        ),
        expectations: str = typer.Option(
            ..., "--expectations", help="Strict audit expectation JSON"
        ),
        repo_root: str = typer.Option(
            ..., "--repo-root", help="Repository containing the tracked source base"
        ),
        base_commit: str = typer.Option(
            ..., "--base-commit", help="Exact source revision expected by the JSON"
        ),
    ) -> None:
        """Return the sole qualification token or a uniform unavailable result."""

        try:
            expected = load_qualification_audit_expectation(Path(expectations))
            result = audit_qualification_campaign(
                Path(campaign_dir),
                expectation=expected,
                repository=Path(repo_root),
                base_revision=base_commit,
            )
        except QualificationAuditUnavailable:
            typer.echo(UNAVAILABLE_TOKEN, err=True)
            raise typer.Exit(code=1)
        typer.echo(QUALIFIED_TOKEN if result == QUALIFIED_TOKEN else UNAVAILABLE_TOKEN)
        if result != QUALIFIED_TOKEN:  # defensive: never expose a third state
            raise typer.Exit(code=1)


__all__ = ["register_qualification_audit_command"]
