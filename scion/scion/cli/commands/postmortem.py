"""`scion postmortem` command registration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer


def register_postmortem_command(app: typer.Typer) -> None:
    @app.command()
    def postmortem(
        campaign_dir: str = typer.Argument(
            ...,
            help="Campaign directory containing campaign_summary.json",
        ),
        output: Optional[str] = typer.Option(
            None,
            "--output",
            "-o",
            help="Write report to file",
        ),
        json_output: bool = typer.Option(
            False,
            "--json",
            help="Output machine-readable JSON instead of markdown",
        ),
    ) -> None:
        """Generate a postmortem analysis report from campaign artifacts."""
        campaign_path = Path(campaign_dir).resolve()
        summary_file = campaign_path / "campaign_summary.json"

        if not summary_file.exists():
            typer.echo(
                f"ERROR: campaign_summary.json not found at {summary_file}",
                err=True,
            )
            raise typer.Exit(code=1)

        try:
            summary = json.loads(summary_file.read_text())
        except Exception as exc:
            typer.echo(
                f"ERROR: failed to read campaign_summary.json: {exc}",
                err=True,
            )
            raise typer.Exit(code=1)

        report = build_postmortem(summary, campaign_path)
        report_text = (
            json.dumps(report.to_json(), indent=2)
            if json_output
            else report.to_markdown()
        )

        if output:
            Path(output).write_text(report_text)
            suffix = "JSON" if json_output else "report"
            typer.echo(f"Postmortem {suffix} written to {output}")
        else:
            typer.echo(report_text)


class PostmortemReport:
    def __init__(
        self,
        *,
        summary: dict,
        campaign_path: Path,
        total_steps: int,
        n_failed: int,
        n_promoted: int,
        failure_stages: dict,
        sibling_summaries: list[tuple[str, dict]],
    ) -> None:
        self.summary = summary
        self.campaign_path = campaign_path
        self.total_steps = total_steps
        self.n_failed = n_failed
        self.n_promoted = n_promoted
        self.failure_stages = failure_stages
        self.sibling_summaries = sibling_summaries

    def to_json(self) -> dict:
        summary = self.summary
        return {
            "campaign_id": summary.get("campaign_id", "unknown"),
            "campaign_dir": str(self.campaign_path),
            "total_rounds": summary.get("total_rounds", 0),
            "champion_version": summary.get("champion_version", 0),
            "budget_utilization": summary.get("budget_utilization", 0.0),
            "total_steps": self.total_steps,
            "n_failed": self.n_failed,
            "n_promoted": self.n_promoted,
            "family_coverage": summary.get("family_coverage", {}),
            "verification_failure_breakdown": summary.get(
                "verification_failure_breakdown",
                {},
            ),
            "failure_stages": self.failure_stages,
            "action_locus_coverage": summary.get("action_locus_coverage", {}),
            "stagnation_signals": summary.get("stagnation_signals", []),
            "diagnostics": summary.get("diagnostics", []),
            "cache_stats": summary.get("cache_stats", {}),
            "comparisons": [
                {
                    "name": name,
                    "total_rounds": sibling.get("total_rounds", 0),
                    "champion_version": sibling.get("champion_version", 0),
                    "budget_utilization": sibling.get("budget_utilization", 0.0),
                }
                for name, sibling in self.sibling_summaries
            ],
        }

    def to_markdown(self) -> str:
        summary = self.summary
        lines = [
            "# Scion Campaign Postmortem",
            "",
            "## Campaign Summary",
            f"- Campaign ID: {summary.get('campaign_id', 'unknown')}",
            f"- Total rounds: {summary.get('total_rounds', 0)}",
            f"- Champion version: {summary.get('champion_version', 0)}",
            f"- Budget utilization: {summary.get('budget_utilization', 0.0):.1%}",
            "",
        ]
        lines.extend(self._family_lines())
        lines.extend(self._failure_lines())
        lines.extend(self._action_locus_lines())
        lines.extend(self._cache_lines())
        lines.extend(self._stagnation_lines())
        lines.extend(self._diagnostic_lines())
        lines.extend(self._promoted_lines())
        lines.extend(self._recommendation_lines())
        lines.extend(self._comparison_lines())
        return "\n".join(lines)

    def _family_lines(self) -> list[str]:
        family_coverage = self.summary.get("family_coverage", {})
        if not family_coverage:
            return []
        lines = ["## Hypothesis Family Distribution"]
        for family, count in sorted(family_coverage.items(), key=lambda x: -x[1]):
            lines.append(f"- {family}: {count} hypothesis(es)")
        return lines + [""]

    def _failure_lines(self) -> list[str]:
        lines = [
            "## Failure Breakdown",
            f"- Total steps: {self.total_steps}",
            f"- Failures: {self.n_failed}",
            f"- Promotions: {self.n_promoted}",
        ]
        vfail = self.summary.get("verification_failure_breakdown", {})
        if vfail:
            lines.append("- Verification failures by type:")
            for vtype, count in sorted(vfail.items(), key=lambda x: -x[1]):
                lines.append(f"  - {vtype}: {count}")
        if self.failure_stages:
            lines.append("- Failure stages:")
            for stage, count in sorted(self.failure_stages.items(), key=lambda x: -x[1]):
                lines.append(f"  - {stage}: {count}")
        return lines + [""]

    def _action_locus_lines(self) -> list[str]:
        action_locus = self.summary.get("action_locus_coverage", {})
        if not action_locus:
            return []
        lines = ["## Action/Locus Coverage"]
        for combo, count in sorted(action_locus.items(), key=lambda x: -x[1]):
            lines.append(f"- {combo}: {count}")
        return lines + [""]

    def _cache_lines(self) -> list[str]:
        cache_stats = self.summary.get("cache_stats", {})
        if not cache_stats:
            return []
        return [
            "## LLM Cache Statistics",
            f"- Total tokens: {cache_stats.get('total_tokens', 0)}",
            f"- Cache read tokens: {cache_stats.get('cache_read_tokens', 0)}",
            f"- Cache hit rate: {cache_stats.get('cache_hit_rate', 0.0):.1%}",
            "",
        ]

    def _stagnation_lines(self) -> list[str]:
        signals = self.summary.get("stagnation_signals", [])
        if not signals:
            return []
        lines = ["## Stagnation Signals"]
        for sig in signals:
            lines.append(
                f"- [{sig.get('severity', '?').upper()}] "
                f"{sig.get('kind', '?')}: {sig.get('detail', '')}"
            )
            lines.append(f"  Suggested action: {sig.get('suggested_action', '')}")
        return lines + [""]

    def _diagnostic_lines(self) -> list[str]:
        diagnostics = self.summary.get("diagnostics", [])
        if not diagnostics:
            return []
        lines = ["## Campaign Diagnostics"]
        for diag in diagnostics:
            lines.append(
                f"- Round {diag.get('round_num', '?')}: "
                f"{diag.get('recommendation', '?')}"
            )
        return lines + [""]

    def _promoted_lines(self) -> list[str]:
        promoted_steps = [
            step
            for step in self.summary.get("steps", [])
            if step.get("decision") == "promote"
        ]
        if not promoted_steps:
            return []
        lines = ["## Promoted Operators"]
        for step in promoted_steps:
            hyp = step.get("hypothesis", {})
            protocol_result = step.get("protocol_result", {})
            win_rate = (
                protocol_result.get("screening_case_win_rate")
                or protocol_result.get("case_win_rate")
                or protocol_result.get("win_rate", "?")
                if protocol_result
                else "?"
            )
            lines.append(
                f"- Round {step.get('round', '?')}: "
                f"{hyp.get('action', '?')} {hyp.get('target_file', '?')} "
                f"(case_win_rate={win_rate})"
            )
            lines.append(f"  Hypothesis: {(hyp.get('text') or '')[:120]}")
        return lines + [""]

    def _recommendation_lines(self) -> list[str]:
        diagnostics = self.summary.get("diagnostics", [])
        diagnostics_recs = [diag.get("recommendation", "") for diag in diagnostics]
        family_coverage = self.summary.get("family_coverage", {})
        lines = ["## Recommendations for Next Campaign"]
        if "check_environment" in diagnostics_recs:
            lines.append(
                "- **Critical**: Check execution environment - "
                "cascading failures detected."
            )
        if "diversify_locus" in diagnostics_recs:
            lines.append(
                "- Diversify operator locus - oscillation pattern suggests current "
                "locus is stale."
            )
        if "switch_action" in diagnostics_recs:
            lines.append("- Switch mechanism family - plateau detected with same approach.")
        if not diagnostics_recs:
            if self.n_promoted == 0:
                lines.append(
                    "- No operators promoted. Consider increasing max_rounds or "
                    "exploring new mechanism families."
                )
            else:
                lines.append(
                    f"- {self.n_promoted} operator(s) promoted. Continue refining "
                    "promoted mechanisms."
                )
        if family_coverage:
            dominant_family = max(family_coverage, key=lambda k: family_coverage[k])
            lines.append(f"- Dominant family was '{dominant_family}' - consider diversifying.")
        return lines + [""]

    def _comparison_lines(self) -> list[str]:
        if not self.sibling_summaries:
            return []
        summary = self.summary
        lines = [
            "## Comparison with Other Campaigns",
            "| Campaign | Rounds | Champion | Promotions | Budget |",
            "|---|---|---|---|---|",
        ]
        lines.append(
            f"| **{self.campaign_path.name}** | {summary.get('total_rounds', 0)} | "
            f"{summary.get('champion_version', 0)} | {self.n_promoted} | "
            f"{summary.get('budget_utilization', 0.0):.1%} |"
        )
        for sibling_name, sibling in self.sibling_summaries:
            sibling_steps = sibling.get("steps", [])
            sibling_promoted = sum(
                1 for step in sibling_steps if step.get("decision") == "promote"
            )
            lines.append(
                f"| {sibling_name} | {sibling.get('total_rounds', 0)} | "
                f"{sibling.get('champion_version', 0)} | {sibling_promoted} | "
                f"{sibling.get('budget_utilization', 0.0):.1%} |"
            )
        return lines + [""]


def build_postmortem(summary: dict, campaign_path: Path) -> PostmortemReport:
    steps = summary.get("steps", [])
    failure_stages: dict = {}
    for step in steps:
        failure_stage = step.get("failure_stage")
        if failure_stage:
            failure_stages[failure_stage] = failure_stages.get(failure_stage, 0) + 1

    return PostmortemReport(
        summary=summary,
        campaign_path=campaign_path,
        total_steps=len(steps),
        n_failed=sum(1 for step in steps if step.get("failure_stage")),
        n_promoted=sum(1 for step in steps if step.get("decision") == "promote"),
        failure_stages=failure_stages,
        sibling_summaries=_load_sibling_summaries(campaign_path),
    )


def _load_sibling_summaries(campaign_path: Path) -> list[tuple[str, dict]]:
    parent = campaign_path.parent
    sibling_summaries = []
    for sibling in sorted(parent.iterdir()):
        if sibling == campaign_path or not sibling.is_dir():
            continue
        summary_file = sibling / "campaign_summary.json"
        if not summary_file.exists():
            continue
        try:
            sibling_summaries.append((sibling.name, json.loads(summary_file.read_text())))
        except Exception:
            pass
    return sibling_summaries


__all__ = ["build_postmortem", "register_postmortem_command"]
