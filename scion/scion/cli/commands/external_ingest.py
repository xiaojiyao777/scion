"""CLI command for externally supplied proposal/workspace ingestion."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from scion.config.problem import ProblemSpec
from scion.config.split_manifest import SplitManifest
from scion.external_ingest import (
    ExternalProposalIngestor,
    load_external_manifest,
    run_mock_smoke,
)


def register_external_ingest_command(app: typer.Typer) -> None:
    @app.command("external-ingest")
    def external_ingest(
        manifest: str = typer.Argument(
            ...,
            help="Path to an external proposal manifest YAML/JSON file.",
        ),
        problem: str = typer.Option(
            ...,
            "--problem",
            help="Path to problem.yaml used for Scion ContractGate validation.",
        ),
        output_dir: str = typer.Option(
            "external_ingest_out",
            "--output-dir",
            help="Directory for host-materialized workspace and audit artifacts.",
        ),
        base_workspace: Optional[str] = typer.Option(
            None,
            "--base-workspace",
            help="Override base champion/workspace path from the manifest.",
        ),
        split: Optional[str] = typer.Option(
            None,
            "--split",
            help="Optional split_manifest.yaml; safe_data_roots are resolved absolutely.",
        ),
        selected_surface: Optional[str] = typer.Option(
            None,
            "--selected-surface",
            help="Optional explicit research surface for ContractGate patch checks.",
        ),
        campaign_dir: Optional[str] = typer.Option(
            None,
            "--campaign-dir",
            help="Optional campaign directory; used when --record-lineage is set.",
        ),
        record_lineage: bool = typer.Option(
            False,
            "--record-lineage",
            help="Append an external_proposal_ingest event to campaign_dir/scion.db.",
        ),
        mock_smoke: bool = typer.Option(
            False,
            "--mock-smoke",
            help="Run generic materialization smoke after ContractGate.",
        ),
    ) -> None:
        """Ingest an external hypothesis plus patch/workspace into Scion gates."""

        manifest_path = Path(manifest).expanduser().resolve(strict=False)
        problem_path = Path(problem).expanduser().resolve(strict=False)
        if not manifest_path.exists():
            typer.echo(f"ERROR: manifest not found: {manifest_path}", err=True)
            raise typer.Exit(code=1)
        if not problem_path.exists():
            typer.echo(f"ERROR: problem.yaml not found: {problem_path}", err=True)
            raise typer.Exit(code=1)
        if record_lineage and campaign_dir is None:
            typer.echo(
                "ERROR: --record-lineage requires --campaign-dir",
                err=True,
            )
            raise typer.Exit(code=1)

        try:
            spec = ProblemSpec.from_yaml(str(problem_path))
            external_manifest = load_external_manifest(manifest_path)
            split_manifest = SplitManifest.from_yaml(split) if split else None
            ingestor = ExternalProposalIngestor(
                problem_spec=spec,
                output_dir=output_dir,
                base_workspace=base_workspace,
                split_manifest=split_manifest,
                selected_surface=selected_surface,
                campaign_dir=campaign_dir,
                record_lineage=record_lineage,
            )
            result = ingestor.ingest(
                external_manifest,
                manifest_path=manifest_path,
                smoke_runner=run_mock_smoke if mock_smoke else None,
            )
        except Exception as exc:
            typer.echo(f"ERROR: external ingest failed: {exc}", err=True)
            raise typer.Exit(code=1)

        typer.echo(f"External ingest: {result.ingest_id}")
        typer.echo(f"  passed: {result.passed}")
        typer.echo(f"  workspace: {result.workspace_path}")
        typer.echo(f"  audit: {result.audit_manifest_path}")
        typer.echo(f"  canonical_diff: {result.canonical_diff_path}")
        typer.echo(f"  result: {result.result_path}")
        if result.lineage_event_id:
            typer.echo(f"  lineage_event_id: {result.lineage_event_id}")

        if not result.passed:
            raise typer.Exit(code=2)


__all__ = ["register_external_ingest_command"]
