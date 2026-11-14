"""`scion report` command registration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from scion.cli.commands.common import get_registry
from scion.core.public_refs import public_artifact_ref


def register_report_commands(report_app: typer.Typer) -> None:
    @report_app.command("champion-heldout-comparison")
    def report_champion_heldout_comparison(
        manifest: str = typer.Option(..., "--manifest"),
        output_dir: str = typer.Option(..., "--output-dir"),
    ) -> None:
        """Run independent frozen comparisons over ordinary champion copies."""
        from scion.evaluation.champion_holdout import (
            execute_champion_heldout_comparison,
        )
        try:
            summary_path = execute_champion_heldout_comparison(
                manifest, output_dir=output_dir
            )
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            typer.echo(f"ERROR: champion held-out comparison failed: {exc}", err=True)
            raise typer.Exit(code=1)
        keys = (
            "group_count", "completed_group_count", "execution_invalid_group_count",
            "error_group_count", "candidate_supported_group_count",
            "all_groups_supported", "schema_version",
        )
        brief = {key: summary[key] for key in keys}
        brief["summary_path"] = str(summary_path)
        typer.echo(json.dumps(brief, indent=2, sort_keys=True))

    @report_app.command("summary")
    def report_summary(
        campaign_dir: str = typer.Option(
            "campaign_out",
            "--campaign-dir",
            help="Campaign directory",
        ),
        output: Optional[str] = typer.Option(
            None,
            "--output",
            "-o",
            help="Write JSON report to file",
        ),
        markdown: bool = typer.Option(
            False,
            "--markdown",
            "-m",
            help="Output as markdown instead of JSON",
        ),
    ) -> None:
        """Campaign summary: rounds, champion version, and gate intercept rates."""
        campaign_path = Path(campaign_dir).resolve()
        db_path = campaign_path / "scion.db"
        summary_file = campaign_path / "campaign_summary.json"
        try:
            meta = json.loads(summary_file.read_text()) if summary_file.exists() else {}
        except (OSError, ValueError):
            meta = {}

        if db_path.exists():
            from scion.lineage.registry import LineageRegistry

            registry = LineageRegistry(str(db_path))
            db_summary = registry.get_campaign_summary()
            total_events = db_summary.get("total_events", 0)
            contract_failures = db_summary.get("contract_failures", 0)
            verification_failures = db_summary.get("verification_failures", 0)
            gate_outcome_events = db_summary.get("gate_outcome_events", total_events)
            contract_gate_outcome_events = db_summary.get(
                "contract_gate_outcome_events",
                gate_outcome_events,
            )
            verification_gate_outcome_events = db_summary.get(
                "verification_gate_outcome_events",
                gate_outcome_events,
            )
            by_decision = db_summary.get("by_decision", {})
            screening_rate_fields = {
                key: db_summary.get(key)
                for key in (
                    "screening_case_wins",
                    "screening_case_losses",
                    "screening_case_ties",
                    "screening_case_total",
                    "screening_case_win_rate",
                    "screening_pair_wins",
                    "screening_pair_losses",
                    "screening_pair_ties",
                    "screening_pair_total",
                    "screening_pair_win_rate",
                )
            }

            weight_opt_records = registry.query_weight_optimizations()
            weight_opt_summary = None
            if weight_opt_records:
                improved_count = sum(1 for r in weight_opt_records if r.get("improved"))
                latest = weight_opt_records[-1]
                weight_opt_summary = {
                    "total_runs": len(weight_opt_records),
                    "improved_count": improved_count,
                    "latest_baseline_score": latest.get("baseline_score"),
                    "latest_best_score": latest.get("best_score"),
                    "latest_improved": bool(latest.get("improved")),
                }

            vfail_breakdown: dict = {}
            all_failures = registry.query_failures()
            for evt in all_failures:
                if evt.get("event_kind") == "verification_fail":
                    stage = evt.get("reason_code") or "unknown"
                    vfail_breakdown[stage] = vfail_breakdown.get(stage, 0) + 1
        else:
            total_events = contract_failures = verification_failures = 0
            gate_outcome_events = 0
            contract_gate_outcome_events = 0
            verification_gate_outcome_events = 0
            by_decision = {}
            screening_rate_fields = {}
            weight_opt_summary = None
            vfail_breakdown = {}

        v_intercept = (
            round(verification_failures / verification_gate_outcome_events, 4)
            if verification_gate_outcome_events > 0
            else 0.0
        )
        c_intercept = (
            round(contract_failures / contract_gate_outcome_events, 4)
            if contract_gate_outcome_events > 0
            else 0.0
        )
        screening_pass = by_decision.get("queue_validate", 0)
        screening_total = sum(
            by_decision.get(d, 0)
            for d in ["continue_explore", "expand_screening", "queue_validate"]
        )
        screening_pass_rate = (
            round(screening_pass / screening_total, 4) if screening_total > 0 else 0.0
        )
        promoted = by_decision.get("promote", 0)
        latest_champion_version = 1 + promoted if db_path.exists() else 0

        report = {
            "campaign_dir": public_artifact_ref(
                campaign_path,
                base_dir=campaign_path.parent,
                kind="campaign",
            ),
            "problem_name": meta.get("problem_name", "unknown"),
            "total_experiments": total_events,
            "gate_outcome_events": gate_outcome_events,
            "contract_gate_outcome_events": contract_gate_outcome_events,
            "verification_gate_outcome_events": verification_gate_outcome_events,
            "champion_promotions": promoted,
            "latest_champion_version": latest_champion_version,
            "contract_intercept_rate": c_intercept,
            "verification_intercept_rate": v_intercept,
            "screening_pass_rate": screening_pass_rate,
            **screening_rate_fields,
            "by_decision": by_decision,
            "verification_failure_breakdown": vfail_breakdown,
            "weight_optimization": weight_opt_summary,
        }

        if markdown:
            report_text = _summary_report_markdown(
                meta=meta,
                total_events=total_events,
                promoted=promoted,
                latest_champion_version=latest_champion_version,
                c_intercept=c_intercept,
                v_intercept=v_intercept,
                contract_gate_outcome_events=contract_gate_outcome_events,
                verification_gate_outcome_events=verification_gate_outcome_events,
                screening_pass_rate=screening_pass_rate,
                screening_rate_fields=screening_rate_fields,
                vfail_breakdown=vfail_breakdown,
                weight_opt_summary=weight_opt_summary,
            )
            if output:
                Path(output).write_text(report_text)
                typer.echo(f"Report written to {output}")
            else:
                typer.echo(report_text)
            return

        report_json = json.dumps(report, indent=2)
        if output:
            Path(output).write_text(report_json)
            typer.echo(f"Report written to {output}")
        else:
            typer.echo(report_json)

    @report_app.command("failures")
    def report_failures(
        campaign_dir: str = typer.Option(
            "campaign_out",
            "--campaign-dir",
            help="Campaign directory",
        ),
        output: Optional[str] = typer.Option(
            None,
            "--output",
            "-o",
            help="Write JSON report to file",
        ),
    ) -> None:
        """Failure distribution: breakdown by failure type."""
        registry = get_registry(campaign_dir)
        all_failures = registry.query_failures()

        by_type: dict = {}
        for evt in all_failures:
            event_kind = evt.get("event_kind")
            reason_code = evt.get("reason_code") or ""

            if event_kind == "contract_fail":
                key = "contract"
            elif event_kind == "verification_fail":
                key = (
                    f"verification:{reason_code}"
                    if reason_code
                    else "verification"
                )
            else:
                key = "other"

            by_type[key] = by_type.get(key, 0) + 1

        report = {
            "total_failures": len(all_failures),
            "by_type": by_type,
            "recent_failures": [
                {
                    "event_id": e.get("event_id"),
                    "branch_id": e.get("branch_id"),
                    "timestamp": e.get("timestamp"),
                    "event_kind": e.get("event_kind"),
                    "outcome": e.get("outcome"),
                    "stage": e.get("stage"),
                    "reason_code": e.get("reason_code"),
                    "detail": e.get("detail"),
                }
                for e in all_failures
            ],
        }

        report_json = json.dumps(report, indent=2, default=str)
        if output:
            Path(output).write_text(report_json)
            typer.echo(f"Failure report written to {output}")
        else:
            typer.echo(report_json)


def _summary_report_markdown(
    *,
    meta: dict,
    total_events: int,
    promoted: int,
    latest_champion_version: int,
    c_intercept: float,
    v_intercept: float,
    contract_gate_outcome_events: int,
    verification_gate_outcome_events: int,
    screening_pass_rate: float,
    screening_rate_fields: dict,
    vfail_breakdown: dict,
    weight_opt_summary: dict | None,
) -> str:
    lines = [
        f"# Campaign Report: {meta.get('problem_name', 'unknown')}",
        "",
        "## Overview",
        f"- Total experiments: {total_events}",
        f"- Champion promotions: {promoted}",
        f"- Latest champion version: {latest_champion_version}",
        (
            f"- Contract intercept rate: {c_intercept:.1%} "
            f"({contract_gate_outcome_events} opportunities)"
        ),
        (
            f"- Verification intercept rate: {v_intercept:.1%} "
            f"({verification_gate_outcome_events} opportunities)"
        ),
        f"- Screening pass rate: {screening_pass_rate:.1%}",
        (
            "- Screening case/gate win rate: "
            f"{(screening_rate_fields.get('screening_case_win_rate') or 0.0):.1%}"
        ),
        (
            "- Screening pair win rate: "
            f"{(screening_rate_fields.get('screening_pair_win_rate') or 0.0):.1%} "
            f"({screening_rate_fields.get('screening_pair_wins') or 0}W/"
            f"{screening_rate_fields.get('screening_pair_losses') or 0}L/"
            f"{screening_rate_fields.get('screening_pair_ties') or 0}T)"
        ),
        "",
    ]
    if vfail_breakdown:
        lines.append("## Verification Failure Breakdown")
        for reason, cnt in sorted(vfail_breakdown.items(), key=lambda x: -x[1]):
            lines.append(f"- {reason}: {cnt}")
        lines.append("")
    if weight_opt_summary:
        lines.append("## Weight Optimization")
        lines.append(f"- Runs: {weight_opt_summary['total_runs']}")
        lines.append(f"- Improved: {weight_opt_summary['improved_count']}")
        lines.append(
            f"- Latest baseline score: {weight_opt_summary['latest_baseline_score']}"
        )
        lines.append(f"- Latest best score: {weight_opt_summary['latest_best_score']}")
        lines.append("")
    return "\n".join(lines)


__all__ = ["register_report_commands"]
