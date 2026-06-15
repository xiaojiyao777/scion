"""`scion report` command registration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from scion.cli.commands.common import get_registry
from scion.core.public_refs import public_artifact_ref


def register_report_commands(report_app: typer.Typer) -> None:
    @report_app.command("proposal-trajectory-manifest")
    def report_proposal_trajectory_manifest(
        campaign_dir: str = typer.Option(
            ...,
            "--campaign-dir",
            help="Campaign directory containing agentic session artifacts",
        ),
        observed_control_arm: str = typer.Option(
            ...,
            "--observed-control-arm",
            help="Observed measurement-control arm: on or record_only",
        ),
        output: str = typer.Option(
            ...,
            "--output",
            "-o",
            help="Write proposal trajectory manifest JSON to this path",
        ),
        control_pair_key: Optional[str] = typer.Option(
            None,
            "--control-pair-key",
            help="Optional report-only key linking comparable control-pair manifests",
        ),
    ) -> None:
        """Build a report-only proposal trajectory manifest."""
        from scion.core.proposal_trajectory_artifacts import (
            write_proposal_trajectory_manifest,
        )

        try:
            manifest_path = write_proposal_trajectory_manifest(
                campaign_dir,
                observed_control_arm=observed_control_arm,
                control_pair_key=control_pair_key,
                output_path=output,
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            typer.echo(
                f"ERROR: failed to build proposal trajectory manifest: {exc}",
                err=True,
            )
            raise typer.Exit(code=1)

        counts = manifest["counts"]
        context_arm = manifest.get("context_arm_fingerprint", {})
        typer.echo(
            json.dumps(
                {
                    "manifest_path": str(manifest_path),
                    "schema_version": manifest["schema_version"],
                    "session_count": counts["session_count"],
                    "trace_count": counts["trace_count"],
                    "formal_candidate_count": counts["formal_candidate_count"],
                    "observed_control_arm": manifest["observed_control_arm"],
                    "control_pair_key": manifest.get("control_pair_key", ""),
                    "proposal_context_ablation": context_arm.get(
                        "proposal_context_ablation", ""
                    ),
                },
                indent=2,
                sort_keys=True,
            )
        )

    @report_app.command("proposal-trajectory-compare")
    def report_proposal_trajectory_compare(
        left: str = typer.Option(
            ...,
            "--left",
            help="Left proposal trajectory manifest JSON path",
        ),
        right: str = typer.Option(
            ...,
            "--right",
            help="Right proposal trajectory manifest JSON path",
        ),
        output: str = typer.Option(
            ...,
            "--output",
            "-o",
            help="Write proposal trajectory comparison JSON to this path",
        ),
    ) -> None:
        """Compare two report-only proposal trajectory manifests."""
        from scion.core.proposal_trajectory_artifacts import (
            write_proposal_trajectory_comparison,
        )

        try:
            comparison_path = write_proposal_trajectory_comparison(
                left,
                right,
                output_path=output,
            )
            comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            typer.echo(
                f"ERROR: failed to compare proposal trajectory manifests: {exc}",
                err=True,
            )
            raise typer.Exit(code=1)

        summary = comparison["summary"]
        typer.echo(
            json.dumps(
                {
                    "comparison_path": str(comparison_path),
                    "schema_version": comparison["schema_version"],
                    "observational_only": comparison["observational_only"],
                    "left_session_count": summary["left"]["session_count"],
                    "right_session_count": summary["right"]["session_count"],
                    "left_trace_count": summary["left"]["trace_count"],
                    "right_trace_count": summary["right"]["trace_count"],
                },
                indent=2,
                sort_keys=True,
            )
        )

    @report_app.command("fixed-candidate-replay-manifest")
    def report_fixed_candidate_replay_manifest(
        source: str = typer.Option(
            ...,
            "--source",
            help="Source campaign directory or formal_candidates/index.jsonl",
        ),
        source_arm: str = typer.Option(
            ...,
            "--source-arm",
            help="Measurement governance arm that produced the source candidates",
        ),
        comparison_id: str = typer.Option(
            ...,
            "--comparison-id",
            help="Stable identifier for the ON vs record_only comparison",
        ),
        output: Optional[str] = typer.Option(
            None,
            "--output",
            "-o",
            help="Write manifest to this path",
        ),
        max_candidates: Optional[int] = typer.Option(
            None,
            "--max-candidates",
            help="Maximum number of eligible candidates to include",
        ),
        candidate_id: Optional[list[str]] = typer.Option(
            None,
            "--candidate-id",
            help="Candidate id to include; may be supplied multiple times",
        ),
        hypothesis_id: Optional[list[str]] = typer.Option(
            None,
            "--hypothesis-id",
            help="Hypothesis id to include; may be supplied multiple times",
        ),
        stage: Optional[list[str]] = typer.Option(
            None,
            "--stage",
            help=(
                "Replay stage to include: screening, validation, or frozen; "
                "may be supplied multiple times. Defaults to screening."
            ),
        ),
        external_candidate_artifact: Optional[list[str]] = typer.Option(
            None,
            "--external-candidate-artifact",
            help=(
                "External full-file candidate.patch.json artifact to include; "
                "may be supplied multiple times"
            ),
        ),
    ) -> None:
        """Build a fixed-candidate replay manifest from formal artifacts."""
        from scion.core.fixed_candidate_replay import (
            write_fixed_candidate_replay_manifest,
        )

        try:
            manifest_path = write_fixed_candidate_replay_manifest(
                source,
                source_arm=source_arm,
                comparison_id=comparison_id,
                output_path=output,
                max_candidates=max_candidates,
                candidate_ids=candidate_id,
                hypothesis_ids=hypothesis_id,
                stages=stage,
                external_candidate_artifacts=external_candidate_artifact,
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            typer.echo(
                f"ERROR: failed to build fixed-candidate replay manifest: {exc}",
                err=True,
            )
            raise typer.Exit(code=1)

        typer.echo(
            json.dumps(
                {
                    "manifest_path": str(manifest_path),
                    "candidate_count": manifest["candidate_count"],
                    "filtered_out_row_count": manifest.get(
                        "filtered_out_row_count", 0
                    ),
                    "omitted_row_count": len(manifest["omitted_rows"]),
                    "stage_filter": manifest.get("stage_filter", []),
                    "external_candidate_artifact_count": manifest.get(
                        "external_candidate_artifact_count", 0
                    ),
                    "schema_version": manifest["schema_version"],
                },
                indent=2,
                sort_keys=True,
            )
        )

    @report_app.command("fixed-candidate-replay")
    def report_fixed_candidate_replay(
        manifest: str = typer.Option(
            ...,
            "--manifest",
            help="fixed_candidate_replay_manifest.v1 JSON path",
        ),
        problem: str = typer.Option(
            ...,
            "--problem",
            help="ProblemSpecV1 YAML path",
        ),
        output_dir: str = typer.Option(
            ...,
            "--output-dir",
            help="Directory for materialized workspaces, metrics, and comparison JSON",
        ),
        protocol: Optional[str] = typer.Option(
            None,
            "--protocol",
            help="protocol.yaml path; defaults to problem directory protocol.yaml",
        ),
        split: Optional[str] = typer.Option(
            None,
            "--split",
            help="split_manifest.yaml path; defaults to problem directory split_manifest.yaml",
        ),
        seeds: Optional[str] = typer.Option(
            None,
            "--seeds",
            help="seed_ledger.yaml path; defaults to problem directory seed_ledger.yaml",
        ),
        max_candidates: Optional[int] = typer.Option(
            None,
            "--max-candidates",
            help="Maximum number of manifest candidates to replay",
        ),
        time_limit_sec: Optional[int] = typer.Option(
            None,
            "--time-limit-sec",
            help="Solver subprocess time limit in seconds",
        ),
        output: Optional[str] = typer.Option(
            None,
            "--output",
            "-o",
            help="Comparison JSON path; defaults under output-dir",
        ),
    ) -> None:
        """Run posthoc fixed-candidate replay for manifest stages and arms."""
        from scion.core.fixed_candidate_replay import execute_fixed_candidate_replay

        try:
            comparison_path = execute_fixed_candidate_replay(
                manifest,
                problem_yaml_path=problem,
                output_dir=output_dir,
                protocol_path=protocol,
                split_path=split,
                seeds_path=seeds,
                max_candidates=max_candidates,
                time_limit_sec=time_limit_sec,
                comparison_output_path=output,
            )
            comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            typer.echo(
                f"ERROR: failed to execute fixed-candidate replay: {exc}",
                err=True,
            )
            raise typer.Exit(code=1)

        error_count = sum(
            1 for row in comparison.get("rows", []) if row.get("status") == "error"
        )
        typer.echo(
            json.dumps(
                {
                    "comparison_path": str(comparison_path),
                    "candidate_count": comparison["candidate_count"],
                    "row_count": comparison["row_count"],
                    "error_count": error_count,
                    "schema_version": comparison["schema_version"],
                },
                indent=2,
                sort_keys=True,
            )
        )

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
        state_file = campaign_path / ".scion_state.json"
        meta = json.loads(state_file.read_text()) if state_file.exists() else {}

        if db_path.exists():
            from scion.lineage.registry import LineageRegistry

            registry = LineageRegistry(str(db_path))
            db_summary = registry.get_campaign_summary()
            total_events = db_summary.get("total_events", 0)
            n_champions = db_summary.get("n_champions", 0)
            contract_failures = db_summary.get("contract_failures", 0)
            verification_failures = db_summary.get("verification_failures", 0)
            by_decision = db_summary.get("by_decision", {})
            screening_rate_fields = {
                key: db_summary.get(key)
                for key in (
                    "screening_win_rate_scope",
                    "screening_case_wins",
                    "screening_case_losses",
                    "screening_case_ties",
                    "screening_case_total",
                    "screening_case_win_rate",
                    "screening_gate_win_rate",
                    "screening_pair_wins",
                    "screening_pair_losses",
                    "screening_pair_ties",
                    "screening_pair_total",
                    "screening_pair_win_rate",
                )
            }

            import sqlite3 as _sqlite3

            family_dist: dict = {}
            with _sqlite3.connect(str(db_path)) as conn:
                for row in conn.execute(
                    "SELECT change_locus, COUNT(*) FROM hypotheses "
                    "WHERE change_locus IS NOT NULL "
                    "GROUP BY change_locus ORDER BY 2 DESC"
                ).fetchall():
                    family_dist[row[0]] = row[1]

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

            stagnation_signals: list = []
            summary_file = campaign_path / "campaign_summary.json"
            if summary_file.exists():
                try:
                    cs = json.loads(summary_file.read_text())
                    stagnation_signals = cs.get("stagnation_signals", [])
                except Exception:
                    pass

            vfail_breakdown: dict = {}
            all_failures = registry.query_failures()
            for evt in all_failures:
                if evt.get("verification_result") == "failed":
                    stage = evt.get("decision_reason") or "unknown"
                    vfail_breakdown[stage] = vfail_breakdown.get(stage, 0) + 1
        else:
            total_events = n_champions = contract_failures = verification_failures = 0
            by_decision = {}
            screening_rate_fields = {}
            family_dist = {}
            weight_opt_summary = None
            stagnation_signals = []
            vfail_breakdown = {}

        v_intercept = (
            round(verification_failures / total_events, 4)
            if total_events > 0
            else 0.0
        )
        c_intercept = (
            round(contract_failures / total_events, 4)
            if total_events > 0
            else 0.0
        )
        screening_pass = by_decision.get("queue_validate", 0)
        screening_total = sum(
            by_decision.get(d, 0)
            for d in ["continue_explore", "expand_screening", "queue_validate"]
        )
        screening_pass_rate = (
            round(screening_pass / screening_total, 4)
            if screening_total > 0
            else 0.0
        )
        promoted = by_decision.get("promote", 0)

        report = {
            "campaign_dir": public_artifact_ref(
                campaign_path,
                base_dir=campaign_path.parent,
                kind="campaign",
            ),
            "problem_name": meta.get("problem_name", "unknown"),
            "total_experiments": total_events,
            "champion_promotions": promoted,
            "latest_champion_version": n_champions,
            "contract_intercept_rate": c_intercept,
            "verification_intercept_rate": v_intercept,
            "screening_pass_rate": screening_pass_rate,
            **screening_rate_fields,
            "by_decision": by_decision,
            "family_distribution": family_dist,
            "verification_failure_breakdown": vfail_breakdown,
            "weight_optimization": weight_opt_summary,
            "stagnation_signals": stagnation_signals,
        }

        if markdown:
            report_text = _summary_report_markdown(
                meta=meta,
                total_events=total_events,
                promoted=promoted,
                n_champions=n_champions,
                c_intercept=c_intercept,
                v_intercept=v_intercept,
                screening_pass_rate=screening_pass_rate,
                screening_rate_fields=screening_rate_fields,
                family_dist=family_dist,
                vfail_breakdown=vfail_breakdown,
                weight_opt_summary=weight_opt_summary,
                stagnation_signals=stagnation_signals,
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

    @report_app.command("research-efficiency")
    def report_research_efficiency(
        campaign_dir: str = typer.Option(
            "campaign_out",
            "--campaign-dir",
            help="Campaign directory, or a run cell directory containing campaign/",
        ),
        output: Optional[str] = typer.Option(
            None,
            "--output",
            "-o",
            help="Write JSON report to file",
        ),
    ) -> None:
        """Postrun research-efficiency accounting and failure taxonomy."""
        from scion.core.research_efficiency_report import (
            build_research_efficiency_report,
            write_research_efficiency_report,
        )

        try:
            if output:
                report_path = write_research_efficiency_report(
                    campaign_dir,
                    output_path=output,
                )
                report = json.loads(report_path.read_text(encoding="utf-8"))
            else:
                report = build_research_efficiency_report(campaign_dir)
        except (OSError, ValueError) as exc:
            typer.echo(
                f"ERROR: failed to build research-efficiency report: {exc}",
                err=True,
            )
            raise typer.Exit(code=1)

        report_json = json.dumps(report, indent=2, sort_keys=True, default=str)
        if output:
            typer.echo(f"Research-efficiency report written to {output}")
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
            contract_failed = evt.get("contract_result") == "failed"
            verification_failed = evt.get("verification_result") == "failed"
            v_check = evt.get("verification_result", "")

            if contract_failed:
                key = "contract"
            elif verification_failed:
                key = (
                    f"verification:{v_check}"
                    if v_check and v_check != "failed"
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
                    "contract_result": e.get("contract_result"),
                    "verification_result": e.get("verification_result"),
                    "decision": e.get("decision"),
                }
                for e in all_failures[:20]
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
    n_champions: int,
    c_intercept: float,
    v_intercept: float,
    screening_pass_rate: float,
    screening_rate_fields: dict,
    family_dist: dict,
    vfail_breakdown: dict,
    weight_opt_summary: dict | None,
    stagnation_signals: list,
) -> str:
    lines = [
        f"# Campaign Report: {meta.get('problem_name', 'unknown')}",
        "",
        "## Overview",
        f"- Total experiments: {total_events}",
        f"- Champion promotions: {promoted}",
        f"- Latest champion version: {n_champions}",
        f"- Contract intercept rate: {c_intercept:.1%}",
        f"- Verification intercept rate: {v_intercept:.1%}",
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
    if family_dist:
        lines.append("## Hypothesis Family Distribution")
        for fam, cnt in family_dist.items():
            lines.append(f"- {fam}: {cnt}")
        lines.append("")
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
    if stagnation_signals:
        lines.append("## Stagnation Signals")
        for sig in stagnation_signals:
            lines.append(
                f"- [{sig.get('severity', '?').upper()}] {sig.get('kind', '?')}: "
                f"{sig.get('detail', '')}"
            )
        lines.append("")
    return "\n".join(lines)


__all__ = ["register_report_commands"]
