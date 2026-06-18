#!/usr/bin/env python3
"""Build a report-only post-run analysis brief for delegated review."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from postrun_artifact_inventory import HANDOFF_DOC, build_inventory  # noqa: E402


SCHEMA_VERSION = "scion.postrun_analysis_brief.v1"
ARCHITECTURE_DOC = "scion/design/scion-architecture-v3.md"
CURRENT_STATE_DOC = "scion/docs/status/current-state.md"

REQUIRED_QUESTIONS = (
    "Did the run complete enough formal candidates to be valid for its requested effective budget?",
    "Did the agent perform effective research, or only satisfy framework controls?",
    "Were branch hypotheses and code changes internally coherent?",
    "Did branch-local follow-up and rollback/checkpoint behavior make sense?",
    "Did the agent see enough of the declared problem object and selected surface before writing outputs?",
    "Were LLM tool calls relevant, non-looping, and useful?",
    "Did preview/smoke evidence and later prompts line up?",
    "Did sibling and historical lessons transfer without entering DecisionFeatures?",
    "Did research_continuity show same-mechanism follow-up, "
    "branch-lesson satisfaction or semantic gaps, and weak-positive transfer?",
    "Did runtime_feedback_summary show fresh replay drain, stage-transition drain, "
    "and budget diagnostics consistent with the declared runtime model?",
    "Did failure_taxonomy_summary distinguish provider/infra, framework/control, "
    "proposal/codegen/tool, and algorithm-quality failures?",
    "Were repeated near-duplicate branches avoided or correctly diagnosed?",
    "Are failures framework/control regressions, provider/infra failures, or algorithm-quality failures?",
    "Is the next step repair, same-round rerun, or ladder advancement?",
)


def build_brief(run_root: Path | str) -> dict[str, Any]:
    inventory = build_inventory(run_root)
    run_root_path = Path(inventory["run_root"])
    campaign_dir = Path(inventory["campaign_dir"])
    return {
        "schema_version": SCHEMA_VERSION,
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
        "run_root": str(run_root_path),
        "campaign_dir": str(campaign_dir),
        "handoff_doc": HANDOFF_DOC,
        "architecture_doc": ARCHITECTURE_DOC,
        "current_state_doc": CURRENT_STATE_DOC,
        "lifecycle": inventory["lifecycle"],
        "validity": inventory["validity"],
        "counters": inventory["counters"],
        "llm_traces": inventory["llm_traces"],
        "branches": {
            "count": len(inventory["branches"]),
            "ids": [branch["branch_id"] for branch in inventory["branches"]],
        },
        "resume_snapshot": inventory.get("resume_snapshot", {"present": False}),
        "artifact_checklist": _artifact_checklist(run_root_path, campaign_dir),
        "prepared_run_contract": inventory["launcher"]["prepared_run_contract"],
        "postrun_reports": inventory["postrun_reports"],
        "phase4_evidence_coverage": inventory["phase4_evidence_coverage"],
        "measurement_effect_summary": _measurement_effect_summary(
            run_root_path,
            inventory,
        ),
        "runtime_feedback_summary": _runtime_feedback_summary(
            run_root_path,
            inventory,
        ),
        "failure_taxonomy_summary": _failure_taxonomy_summary(
            run_root_path,
            inventory,
        ),
        "prompt_context_visibility_summary": _prompt_context_visibility_summary(
            run_root_path,
            inventory,
        ),
        "research_continuity_summary": _research_continuity_summary(
            run_root_path,
            inventory,
        ),
        "stop_conditions": _stop_conditions(inventory),
        "required_questions": list(REQUIRED_QUESTIONS),
    }


def render_markdown(brief: dict[str, Any]) -> str:
    validity = brief["validity"]
    counters = brief["counters"]
    lifecycle = brief.get("lifecycle") or {}
    prepared_only = lifecycle.get("prepared_only") is True
    title = "Prepared Analysis Brief" if prepared_only else "Post-Run Analysis Brief"
    lines = [
        f"# {title}: {Path(brief['run_root']).name}",
        "",
        "- Schema: `scion.postrun_analysis_brief.v1`",
        "- Scope: report-only delegated analysis input.",
        "- Boundary: tainted LLM traces and postrun diagnostics may guide analysis, "
        "but must not become `DecisionFeatures` or promotion input.",
        f"- Handoff doc: `{brief['handoff_doc']}`",
        f"- Architecture doc: `{brief['architecture_doc']}`",
        f"- Current state doc: `{brief['current_state_doc']}`",
        "",
        "## Inputs",
        f"- RUN_ROOT: `{brief['run_root']}`",
        f"- CAMPAIGN_DIR: `{brief['campaign_dir']}`",
        "",
        "## Lifecycle",
        f"- Prepared only: `{_display(lifecycle.get('prepared_only'))}`",
        f"- Evidence scope: `{_display(lifecycle.get('evidence_scope'))}`",
        "- Resume from campaign: "
        f"`{_display(lifecycle.get('resume_from_campaign'))}`",
        "",
        "## Stop Conditions",
    ]
    stop_conditions = brief.get("stop_conditions") or []
    if stop_conditions:
        lines.extend(f"- {condition}" for condition in stop_conditions)
    else:
        lines.append("- None from the inventory. Continue with branch-centric analysis.")

    resume_snapshot = brief.get("resume_snapshot")
    if isinstance(resume_snapshot, dict) and resume_snapshot.get("present") is True:
        lines.extend(
            [
                "",
                "## Resume Snapshot",
                "- Copied campaign artifacts are launch input, not current-run evidence.",
                "- Current-run evidence: "
                f"`{_display(resume_snapshot.get('current_run_evidence'))}`",
                "- Evidence scope: "
                f"`{_display(resume_snapshot.get('evidence_scope'))}`",
                "- Source campaign: "
                f"`{_display(resume_snapshot.get('resume_from_campaign'))}`",
                f"- Branches: {_display(resume_snapshot.get('branch_count'))}",
                f"- LLM traces: {_display(resume_snapshot.get('llm_trace_count'))}",
                "- Indexed LLM traces/sessions: "
                f"{_display(resume_snapshot.get('llm_index_trace_count'))} / "
                f"{_display(resume_snapshot.get('llm_index_session_count'))}",
                f"- LLM kinds: {_mapping_text(resume_snapshot.get('llm_by_kind'))}",
                f"- LLM statuses: {_mapping_text(resume_snapshot.get('llm_by_status'))}",
                f"- Events by kind: {_mapping_text(resume_snapshot.get('events_by_kind'))}",
                "- Events by decision: "
                f"{_mapping_text(resume_snapshot.get('events_by_decision'))}",
                f"- Events by stage: {_mapping_text(resume_snapshot.get('events_by_stage'))}",
                f"- Hypotheses: {_display(resume_snapshot.get('hypothesis_count'))}",
                "- Hypotheses by status: "
                f"{_mapping_text(resume_snapshot.get('hypotheses_by_status'))}",
            ]
        )

    lines.extend(
        [
            "",
            "## Validity And Counters",
            f"- Validity: `{validity.get('run_validity_status') or 'unknown'}`",
            f"- Completeness: `{validity.get('run_completeness_status') or 'unknown'}`",
            f"- Last stop reason: `{validity.get('last_stop_reason') or 'unknown'}`",
            "| Counter | Value |",
            "|---|---:|",
        ]
    )
    for key, value in counters.items():
        lines.append(f"| {key} | {_display(value)} |")

    lines.extend(
        [
            "",
            "## Artifact Checklist",
            "| Artifact | Present | Path |",
            "|---|---:|---|",
        ]
    )
    for item in brief["artifact_checklist"]:
        lines.append(
            "| {name} | {present} | `{path}` |".format(
                name=item["name"],
                present=_display(item["present"]),
                path=item["path"],
            )
        )

    prepared_contract = brief.get("prepared_run_contract") or {}
    lines.extend(
        [
            "",
            "## Prepared Run Contract",
            f"- Complete: `{_display(prepared_contract.get('contract_complete'))}`",
            "- Problem/model: "
            f"`{_display(prepared_contract.get('problem_family'))}` / "
            f"`{_display(prepared_contract.get('model'))}`",
            "- Control pair: "
            f"`{_display(prepared_contract.get('control_pair_key'))}`",
            "- Resume from campaign: "
            f"`{_display(prepared_contract.get('resume_from_campaign'))}`",
            f"- Analysis intent: {_display(prepared_contract.get('analysis_intent'))}",
            "- Acceptance focus:",
        ]
    )
    acceptance_focus = prepared_contract.get("acceptance_focus")
    if isinstance(acceptance_focus, list) and acceptance_focus:
        lines.extend(f"  - {_display(item)}" for item in acceptance_focus)
    else:
        lines.append("  - None recorded in the prepared manifest.")

    research_focus = prepared_contract.get("research_focus")
    if isinstance(research_focus, dict) and research_focus:
        lines.extend(
            [
                "- Current research focus:",
                f"  - Accepted checkpoint: {_display(research_focus.get('accepted_checkpoint'))}",
                f"  - Question: {_display(research_focus.get('current_question'))}",
                "  - Required evidence:",
            ]
        )
        required = research_focus.get("required_evidence")
        if isinstance(required, list) and required:
            lines.extend(f"    - {_display(item)}" for item in required)
        else:
            lines.append("    - None recorded in the prepared manifest.")
        lines.extend(
            [
                "  - Default-avoid directions:",
            ]
        )
        avoid = research_focus.get("default_avoid_directions")
        if isinstance(avoid, list) and avoid:
            lines.extend(f"    - {_display(item)}" for item in avoid)
        else:
            lines.append("    - None recorded in the prepared manifest.")
        for key, label in (
            ("route_merge_exception_rule", "Route-merge exception"),
            ("construction_seed_rule", "Construction-seed rule"),
            ("decision_boundary", "Decision boundary"),
        ):
            value = research_focus.get(key)
            if value:
                lines.append(f"  - {label}: {_display(value)}")

    lines.extend(
        [
            "| Check | Passed | Detail |",
            "|---|---:|---|",
        ]
    )
    checks = prepared_contract.get("checks")
    if isinstance(checks, dict):
        for key, item in sorted(checks.items()):
            if not isinstance(item, dict):
                continue
            lines.append(
                "| {key} | {passed} | {detail} |".format(
                    key=key,
                    passed=_display(item.get("passed")),
                    detail=_display(item.get("detail")),
                )
            )

    phase4 = brief["phase4_evidence_coverage"]
    lines.extend(
        [
            "",
            "## Phase 4 Evidence Coverage",
            f"- Evidence scope: `{_display(phase4.get('evidence_scope'))}`",
            f"- Prepared only: `{_display(phase4.get('prepared_only'))}`",
            "| Requirement | Available | Count | Source |",
            "|---|---:|---:|---|",
        ]
    )
    requirements = phase4.get("requirements") if isinstance(phase4, dict) else {}
    if isinstance(requirements, dict):
        for key, item in sorted(requirements.items()):
            if not isinstance(item, dict):
                continue
            lines.append(
                "| {key} | {available} | {count} | {source} |".format(
                    key=key,
                    available=_display(item.get("available")),
                    count=_display(item.get("count")),
                    source=_display(item.get("source")),
                )
            )

    effect_summary = brief.get("measurement_effect_summary") or {}
    effect_aggregate = _mapping_or_empty(effect_summary.get("aggregate"))
    lines.extend(
        [
            "",
            "## Measurement Effect Summary",
            "- Source: current-run research-efficiency `measurement_readiness` "
            "and `protocol_effects_vs_mde` reports.",
            f"- Available: `{_display(effect_summary.get('available'))}`",
            "- Current-run evidence: "
            f"`{_display(effect_summary.get('current_run_evidence'))}`",
            "- Reports with effect-vs-MDE: "
            f"`{_display(effect_summary.get('effect_report_count'))}`",
            "- Readiness statuses: "
            f"{_mapping_text(effect_aggregate.get('measurement_readiness_status_counts'))}",
            "- Effect interpretations: "
            f"{_mapping_text(effect_aggregate.get('interpretation_counts'))}",
            "- Protocol rows / rows at-or-above MDE / ci-high below MDE: "
            f"{_display(effect_aggregate.get('protocol_row_count'))} / "
            f"{_display(effect_aggregate.get('rows_at_or_above_mde'))} / "
            f"{_display(effect_aggregate.get('rows_with_ci_high_below_mde'))}",
            "- Max effect/MDE ratio: "
            f"{_display(effect_aggregate.get('max_effect_to_mde_ratio'))}",
        ]
    )
    effect_entries = effect_summary.get("entries")
    if isinstance(effect_entries, list) and effect_entries:
        lines.extend(
            [
                "| Report | Readiness | MDE | Interpretation | Rows | At/Above MDE | CI High Below MDE | Max Effect/MDE |",
                "|---|---|---:|---|---:|---:|---:|---:|",
            ]
        )
        for entry in effect_entries:
            if not isinstance(entry, dict):
                continue
            readiness = _mapping_or_empty(entry.get("measurement_readiness"))
            effect = _mapping_or_empty(entry.get("protocol_effects_vs_mde"))
            lines.append(
                "| {report} | {status} | {mde} | {interpretation} | "
                "{rows} | {above} | {below} | {ratio} |".format(
                    report=_display(entry.get("report")),
                    status=_display(readiness.get("status")),
                    mde=_display(effect.get("mde_at_power_80")),
                    interpretation=_display(effect.get("interpretation")),
                    rows=_display(effect.get("protocol_row_count")),
                    above=_display(effect.get("rows_at_or_above_mde")),
                    below=_display(effect.get("rows_with_ci_high_below_mde")),
                    ratio=_display(effect.get("max_effect_to_mde_ratio")),
                )
            )

    runtime_feedback = brief.get("runtime_feedback_summary") or {}
    runtime_aggregate = _mapping_or_empty(runtime_feedback.get("aggregate"))
    fresh_runtime = _mapping_or_empty(
        runtime_aggregate.get("fresh_runtime_replay_drain")
    )
    stage_drain = _mapping_or_empty(runtime_aggregate.get("stage_transition_drain"))
    budget = _mapping_or_empty(runtime_aggregate.get("runtime_budget_diagnostics"))
    lines.extend(
        [
            "",
            "## Runtime Feedback Summary",
            "- Source: current-run research-efficiency reports plus campaign "
            "summary/status runtime budget diagnostics.",
            f"- Available: `{_display(runtime_feedback.get('available'))}`",
            "- Current-run evidence: "
            f"`{_display(runtime_feedback.get('current_run_evidence'))}`",
            "- Runtime reports / budget diagnostic sources: "
            f"{_display(runtime_feedback.get('runtime_report_count'))} / "
            f"{_display(runtime_feedback.get('budget_diagnostic_source_count'))}",
            "- Fresh replay drain attempts/executed/skipped/blocked/protocol rows: "
            f"{_display(fresh_runtime.get('attempts'))} / "
            f"{_display(fresh_runtime.get('executed'))} / "
            f"{_display(fresh_runtime.get('skipped'))} / "
            f"{_display(fresh_runtime.get('blocked'))} / "
            f"{_display(fresh_runtime.get('protocol_results'))}",
            "- Fresh replay drain statuses: "
            f"{_mapping_text(fresh_runtime.get('status_counts'))}",
            "- Fresh replay drain stop reasons: "
            f"{_mapping_text(fresh_runtime.get('stopped_reason_counts'))}",
            "- Stage-transition drain attempts/executed/skipped: "
            f"{_display(stage_drain.get('attempts'))} / "
            f"{_display(stage_drain.get('executed'))} / "
            f"{_display(stage_drain.get('skipped'))}",
            "- Runtime budget diagnostics: "
            f"{_display(budget.get('diagnostic_count'))}",
            "- Runtime budget diagnostic codes: "
            f"{_mapping_text(budget.get('code_counts'))}",
            "- Runtime budget diagnostic severities: "
            f"{_mapping_text(budget.get('severity_counts'))}",
            "- Runtime budget diagnostic stages: "
            f"{_mapping_text(budget.get('stage_counts'))}",
        ]
    )
    runtime_entries = runtime_feedback.get("entries")
    if isinstance(runtime_entries, list) and runtime_entries:
        lines.extend(
            [
                "| Report | Fresh drain status | Attempts | Executed | Skipped | "
                "Blocked | Protocol rows | Stage drain status |",
                "|---|---|---:|---:|---:|---:|---:|---|",
            ]
        )
        for entry in runtime_entries:
            if not isinstance(entry, dict):
                continue
            fresh = _mapping_or_empty(entry.get("fresh_runtime_replay_drain"))
            stage = _mapping_or_empty(entry.get("stage_transition_drain"))
            lines.append(
                "| {report} | {status} | {attempts} | {executed} | {skipped} | "
                "{blocked} | {protocol_rows} | {stage_status} |".format(
                    report=_display(entry.get("report")),
                    status=_display(fresh.get("status")),
                    attempts=_display(fresh.get("attempts")),
                    executed=_display(fresh.get("executed")),
                    skipped=_display(fresh.get("skipped")),
                    blocked=_display(fresh.get("blocked")),
                    protocol_rows=_display(fresh.get("protocol_results")),
                    stage_status=_display(stage.get("status")),
                )
            )

    failure_summary = brief.get("failure_taxonomy_summary") or {}
    failure_aggregate = _mapping_or_empty(failure_summary.get("aggregate"))
    failure_proposal = _mapping_or_empty(failure_aggregate.get("proposal_quality"))
    lines.extend(
        [
            "",
            "## Failure Taxonomy Summary",
            "- Source: current-run research-efficiency `proposal_quality`, "
            "`failure_taxonomy`, and run-status fields.",
            f"- Available: `{_display(failure_summary.get('available'))}`",
            "- Current-run evidence: "
            f"`{_display(failure_summary.get('current_run_evidence'))}`",
            "- Reports with failure taxonomy: "
            f"`{_display(failure_summary.get('failure_report_count'))}`",
            "- Proposal attempts total/consumed: "
            f"{_display(failure_proposal.get('proposal_attempts_total'))} / "
            f"{_display(failure_proposal.get('proposal_attempts_consumed'))}",
            "- Proposal quality blocks / ledger entries / reports with blocks: "
            f"{_display(failure_proposal.get('proposal_quality_blocks'))} / "
            f"{_display(failure_proposal.get('quality_block_ledger_count'))} / "
            f"{_display(failure_proposal.get('reports_with_quality_blocks'))}",
            "- Quality block reasons: "
            f"{_mapping_text(failure_proposal.get('quality_block_reason_counts'))}",
            "- Failure observations: "
            f"{_mapping_text(failure_aggregate.get('failure_observation_counts'))}",
            "- Failure source counts: "
            f"{_mapping_text(failure_aggregate.get('failure_source_counts'))}",
            "- Run validity statuses: "
            f"{_mapping_text(failure_aggregate.get('run_validity_status_counts'))}",
            "- Stop reasons: "
            f"{_mapping_text(failure_aggregate.get('stopped_reason_counts'))}",
        ]
    )
    failure_entries = failure_summary.get("entries")
    if isinstance(failure_entries, list) and failure_entries:
        lines.extend(
            [
                "| Report | Quality blocks | Failure observations | Top failure keys | Run validity | Stop reason |",
                "|---|---:|---:|---|---|---|",
            ]
        )
        for entry in failure_entries:
            if not isinstance(entry, dict):
                continue
            proposal = _mapping_or_empty(entry.get("proposal_quality"))
            run_status = _mapping_or_empty(entry.get("run_status"))
            lines.append(
                "| {report} | {quality_blocks} | {observations} | {top_keys} | "
                "{validity} | {stop_reason} |".format(
                    report=_display(entry.get("report")),
                    quality_blocks=_display(proposal.get("proposal_quality_blocks")),
                    observations=_display(entry.get("failure_observations_total")),
                    top_keys=_list_text(entry.get("top_failure_keys") or []),
                    validity=_display(run_status.get("run_validity_status")),
                    stop_reason=_display(run_status.get("stopped_reason")),
                )
            )

    context_summary = brief.get("prompt_context_visibility_summary") or {}
    aggregate = _mapping_or_empty(context_summary.get("aggregate"))
    lines.extend(
        [
            "",
            "## Prompt Context Visibility Summary",
            "- Source: current-run proposal trajectory manifests and "
            "prompt-manifest fingerprints.",
            f"- Available: `{_display(context_summary.get('available'))}`",
            "- Current-run evidence: "
            f"`{_display(context_summary.get('current_run_evidence'))}`",
            "- Manifest reports with context: "
            f"`{_display(context_summary.get('context_report_count'))}`",
            "- Prompt manifests loaded/ref: "
            f"{_display(aggregate.get('prompt_manifest_loaded_count'))} / "
            f"{_display(aggregate.get('prompt_manifest_ref_count'))}",
            "- Visibility digests: "
            f"{_display(aggregate.get('visibility_digest_count'))}",
            "- Traces with block-family accounting: "
            f"{_display(aggregate.get('block_family_trace_count'))}",
            "- Omitted/truncated traces: "
            f"{_display(aggregate.get('omitted_section_trace_count'))} / "
            f"{_display(aggregate.get('truncated_section_trace_count'))}",
            f"- Call kinds: {_mapping_text(aggregate.get('call_kind_counts'))}",
        ]
    )
    density = _mapping_or_empty(aggregate.get("signal_density"))
    if density:
        lines.extend(
            [
                "- Signal density: "
                f"research/source/cross-branch/governance tokens "
                f"{_display(density.get('research_signal_tokens'))} / "
                f"{_display(density.get('source_code_tokens'))} / "
                f"{_display(density.get('cross_branch_tokens'))} / "
                f"{_display(density.get('governance_tokens'))}",
                "- Signal density shares: "
                f"{_display(density.get('research_signal_share'))} / "
                f"{_display(density.get('source_code_share'))} / "
                f"{_display(density.get('cross_branch_share'))} / "
                f"{_display(density.get('governance_share'))}",
                "- Research+source/governance ratio: "
                f"{_display(density.get('research_plus_source_to_governance_ratio'))}",
                f"- Signal density interpretation: {_display(density.get('interpretation'))}",
            ]
        )
    families = aggregate.get("block_family_totals")
    if isinstance(families, dict) and families:
        lines.extend(
            [
                "| Prompt family | Traces | Tokens | Chars |",
                "|---|---:|---:|---:|",
            ]
        )
        for family, item in sorted(families.items()):
            if not isinstance(item, dict):
                continue
            lines.append(
                "| {family} | {traces} | {tokens} | {chars} |".format(
                    family=family,
                    traces=_display(item.get("trace_count")),
                    tokens=_display(item.get("token_estimate")),
                    chars=_display(item.get("char_count")),
                )
            )

    continuity = brief.get("research_continuity_summary") or {}
    lines.extend(
        [
            "",
            "## Research Continuity Summary",
            "- Source: current-run research-efficiency `research_continuity` reports.",
            f"- Available: `{_display(continuity.get('available'))}`",
            "- Current-run evidence: "
            f"`{_display(continuity.get('current_run_evidence'))}`",
            "- Reports with continuity: "
            f"`{_display(continuity.get('continuity_report_count'))}`",
        ]
    )
    entries = continuity.get("entries")
    if isinstance(entries, list) and entries:
        lines.extend(
            [
                "| Report | Same-mechanism selected/observed | "
                "Branch lessons satisfied/required | Semantic gaps | "
                "Weak-positive accepted/observed | Max depth | Families |",
                "|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            same_mechanism = _mapping_or_empty(
                entry.get("same_mechanism_followup")
            )
            lessons = _mapping_or_empty(entry.get("branch_lesson_usage"))
            transfer = _mapping_or_empty(entry.get("weak_positive_transfer"))
            shape = _mapping_or_empty(entry.get("research_shape_summary"))
            lines.append(
                "| {report} | {same_selected}/{same_observed} | "
                "{lesson_satisfied}/{lesson_required} | {semantic_gap} | "
                "{transfer_accepted}/{transfer_observed} | {max_depth} | "
                "{families} |".format(
                    report=_display(entry.get("report")),
                    same_selected=_display(
                        same_mechanism.get(
                            "selected_same_branch_refinement_count"
                        )
                    ),
                    same_observed=_display(
                        same_mechanism.get("observed_opportunity_count")
                    ),
                    lesson_satisfied=_display(lessons.get("satisfied_count")),
                    lesson_required=_display(lessons.get("requirement_count")),
                    semantic_gap=_display(lessons.get("semantic_gap_count")),
                    transfer_accepted=_display(transfer.get("accepted_count")),
                    transfer_observed=_display(
                        transfer.get("observed_opportunity_count")
                    ),
                    max_depth=_display(shape.get("max_branch_depth")),
                    families=_display(shape.get("mechanism_family_count")),
                )
            )
    else:
        lines.append(
            "- No current-run research_continuity block is available for delegated analysis."
        )

    llm = brief["llm_traces"]
    branches = brief["branches"]
    lines.extend(
        [
            "",
            "## Inventory Summary",
            f"- Branch count: {branches['count']}",
            f"- Branch ids: {_list_text(branches['ids'])}",
            f"- LLM trace files: {llm['trace_count']}",
            f"- LLM trace index entries: {llm['index_trace_count']}",
            f"- LLM sessions: {llm['index_session_count']}",
            f"- LLM trace kinds: {_mapping_text(llm['by_kind'])}",
            f"- LLM trace statuses: {_mapping_text(llm['by_status'])}",
            "",
            "## Minimum Delegated Analysis",
            "- Start branch-centric, then round/LLM-call centric.",
            "- For prepared-only roots, stop at launcher contract/readiness review; do not make research-quality conclusions until the root has been launched and postrun reports exist.",
            "- Cite artifact paths, branch ids, trace ids, SQL rows, or JSON fields for every conclusion.",
            "- For invalid infra-only runs, stop after proving the infra status.",
            "- For valid runs, inspect target intent, hypothesis, code, tool calls, formal candidates, Protocol/Decision, branch lessons, runtime feedback, and source visibility.",
            "- Decide whether the next action is repair, same-round rerun, or ladder advancement.",
            "",
            "## Required Answers",
        ]
    )
    for index, question in enumerate(brief["required_questions"], start=1):
        lines.append(f"{index}. {question}")

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_root")
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Output format.",
    )
    args = parser.parse_args(argv)

    brief = build_brief(Path(args.run_root))
    if args.format == "json":
        print(json.dumps(brief, indent=2, sort_keys=True))
    else:
        print(render_markdown(brief), end="")
    return 0


def _artifact_checklist(run_root: Path, campaign_dir: Path) -> list[dict[str, Any]]:
    paths = {
        "outer_run_status": run_root / "run_status.json",
        "outer_run_log": run_root / "run.log",
        "outer_exit": run_root / "exit.txt",
        "outer_command": run_root / "command.txt",
        "outer_launch_env": run_root / "launch.env",
        "prepared_run_manifest_json": run_root / "prepared_run_manifest.v1.json",
        "prepared_run_manifest_markdown": run_root / "prepared_run_manifest.md",
        "prepared_handoff": run_root / "prepared_handoff",
        "campaign_status": campaign_dir / "status.json",
        "campaign_run_status": campaign_dir / "run_status.json",
        "campaign_summary": campaign_dir / "campaign_summary.json",
        "campaign_database": campaign_dir / "scion.db",
        "agentic_session_index": campaign_dir
        / "agentic_sessions"
        / "agentic_session_index.json",
        "agentic_trace_index": campaign_dir
        / "agentic_sessions"
        / "agentic_session_trace_index.json",
        "llm_traces_dir": campaign_dir / "llm_traces",
        "metrics_dir": campaign_dir / "metrics",
        "postrun_acceptance": run_root / "postrun_acceptance",
    }
    return [
        {"name": name, "path": str(path), "present": path.exists()}
        for name, path in paths.items()
    ]


def _measurement_effect_summary(
    run_root: Path,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    phase4 = _mapping_or_empty(inventory.get("phase4_evidence_coverage"))
    current_run_evidence = phase4.get("current_run_evidence") is True
    base = {
        "schema_version": "scion.postrun_measurement_effect_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "current_run_evidence": current_run_evidence,
        "available": False,
        "report_count": 0,
        "effect_report_count": 0,
        "aggregate": _empty_measurement_effect_aggregate(),
        "entries": [],
    }
    if not current_run_evidence:
        return base

    report_paths = _research_efficiency_report_paths(run_root, inventory)
    entries: list[dict[str, Any]] = []
    aggregate = _empty_measurement_effect_aggregate()
    for path in report_paths:
        entry = _measurement_effect_entry(path)
        if not entry:
            continue
        entries.append(entry)
        _merge_measurement_effect_aggregate(aggregate, entry)

    return {
        **base,
        "available": bool(entries),
        "report_count": len(report_paths),
        "effect_report_count": len(entries),
        "aggregate": aggregate,
        "entries": entries,
    }


def _empty_measurement_effect_aggregate() -> dict[str, Any]:
    return {
        "measurement_readiness_status_counts": {},
        "interpretation_counts": {},
        "protocol_row_count": 0,
        "rows_at_or_above_mde": 0,
        "rows_with_ci_high_below_mde": 0,
        "positive_rows": 0,
        "nonpositive_rows": 0,
        "max_effect_to_mde_ratio": None,
    }


def _measurement_effect_entry(path: Path) -> dict[str, Any]:
    doc = _read_json_object(path)
    readiness = _mapping_or_empty(doc.get("measurement_readiness"))
    effect = _mapping_or_empty(doc.get("protocol_effects_vs_mde"))
    if not readiness and not effect:
        return {}
    compact_effect = _compact_protocol_effect(effect)
    return {
        "report": path.name,
        "path": str(path),
        "measurement_readiness": _drop_empty(
            {
                "status": readiness.get("status"),
                "reason_code": readiness.get("reason_code"),
                "mde_at_power_80": readiness.get("mde_at_power_80"),
                "signal_to_noise_tier": readiness.get("signal_to_noise_tier"),
                "effect_to_mde_ratio": readiness.get("effect_to_mde_ratio"),
            }
        ),
        "measurement_readiness_source": doc.get("measurement_readiness_source"),
        "protocol_effects_vs_mde": compact_effect,
    }


def _compact_protocol_effect(effect: Mapping[str, Any]) -> dict[str, Any]:
    compact = _drop_empty(
        {
            "schema_version": effect.get("schema_version"),
            "report_only": effect.get("report_only"),
            "decision_features_excluded": effect.get(
                "decision_features_excluded"
            ),
            "measurement_readiness_status": effect.get(
                "measurement_readiness_status"
            ),
            "measurement_readiness_reason_code": effect.get(
                "measurement_readiness_reason_code"
            ),
            "mde_at_power_80": effect.get("mde_at_power_80"),
            "mde_source": effect.get("mde_source"),
            "interpretation": effect.get("interpretation"),
            "protocol_row_count": effect.get("protocol_row_count"),
            "rows_at_or_above_mde": effect.get("rows_at_or_above_mde"),
            "rows_with_ci_high_below_mde": effect.get(
                "rows_with_ci_high_below_mde"
            ),
            "positive_rows": effect.get("positive_rows"),
            "nonpositive_rows": effect.get("nonpositive_rows"),
            "max_effect_to_mde_ratio": effect.get("max_effect_to_mde_ratio"),
            "by_stage": _mapping_or_empty(effect.get("by_stage")),
        }
    )
    top_rows = effect.get("top_rows_by_effect_to_mde")
    if isinstance(top_rows, list):
        compact["top_rows_by_effect_to_mde"] = [
            _compact_effect_row(row) for row in top_rows if isinstance(row, Mapping)
        ][:3]
    return compact


def _compact_effect_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "round": row.get("round"),
            "branch_id": row.get("branch_id"),
            "stage": row.get("stage"),
            "decision": row.get("decision"),
            "gate_outcome": row.get("gate_outcome"),
            "median_delta": row.get("median_delta"),
            "ci_high": row.get("ci_high"),
            "win_rate": row.get("win_rate"),
            "effect_to_mde_ratio": row.get("effect_to_mde_ratio"),
            "positive_effect_at_or_above_mde": row.get(
                "positive_effect_at_or_above_mde"
            ),
            "ci_high_below_mde": row.get("ci_high_below_mde"),
            "reason_codes": row.get("reason_codes"),
        }
    )


def _merge_measurement_effect_aggregate(
    aggregate: dict[str, Any],
    entry: Mapping[str, Any],
) -> None:
    readiness = _mapping_or_empty(entry.get("measurement_readiness"))
    effect = _mapping_or_empty(entry.get("protocol_effects_vs_mde"))
    _increment_count(
        aggregate["measurement_readiness_status_counts"],
        str(readiness.get("status") or "unknown"),
    )
    _increment_count(
        aggregate["interpretation_counts"],
        str(effect.get("interpretation") or "unknown"),
    )
    for key in (
        "protocol_row_count",
        "rows_at_or_above_mde",
        "rows_with_ci_high_below_mde",
        "positive_rows",
        "nonpositive_rows",
    ):
        aggregate[key] = _int_or_zero(aggregate.get(key)) + _int_or_zero(
            effect.get(key)
        )
    ratio = _float_or_none(effect.get("max_effect_to_mde_ratio"))
    current = _float_or_none(aggregate.get("max_effect_to_mde_ratio"))
    if ratio is not None and (current is None or ratio > current):
        aggregate["max_effect_to_mde_ratio"] = ratio


def _runtime_feedback_summary(
    run_root: Path,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    phase4 = _mapping_or_empty(inventory.get("phase4_evidence_coverage"))
    current_run_evidence = phase4.get("current_run_evidence") is True
    base = {
        "schema_version": "scion.postrun_runtime_feedback_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "current_run_evidence": current_run_evidence,
        "available": False,
        "report_count": 0,
        "runtime_report_count": 0,
        "budget_diagnostic_source_count": 0,
        "aggregate": _empty_runtime_feedback_aggregate(),
        "entries": [],
        "runtime_budget_diagnostics": {
            "source_count": 0,
            "diagnostic_count": 0,
            "code_counts": {},
            "severity_counts": {},
            "stage_counts": {},
            "runtime_model_counts": {},
            "top_diagnostics": [],
        },
    }
    if not current_run_evidence:
        return base

    report_paths = _research_efficiency_report_paths(run_root, inventory)
    entries: list[dict[str, Any]] = []
    aggregate = _empty_runtime_feedback_aggregate()
    for path in report_paths:
        entry = _runtime_feedback_entry(path)
        if not entry:
            continue
        entries.append(entry)
        _merge_runtime_feedback_aggregate(aggregate, entry)

    budget_diagnostics = _runtime_budget_diagnostics_summary(
        run_root,
        inventory,
    )
    aggregate["runtime_budget_diagnostics"] = budget_diagnostics
    available = bool(entries) or _int_or_zero(
        budget_diagnostics.get("diagnostic_count")
    ) > 0
    return {
        **base,
        "available": available,
        "report_count": len(report_paths),
        "runtime_report_count": len(entries),
        "budget_diagnostic_source_count": budget_diagnostics["source_count"],
        "aggregate": aggregate,
        "entries": entries,
        "runtime_budget_diagnostics": budget_diagnostics,
    }


def _empty_runtime_feedback_aggregate() -> dict[str, Any]:
    return {
        "fresh_runtime_replay_drain": {
            "status_counts": {},
            "stopped_reason_counts": {},
            "attempts": 0,
            "executed": 0,
            "skipped": 0,
            "blocked": 0,
            "protocol_results": 0,
            "counts_toward_max_rounds_true": 0,
            "counts_toward_max_rounds_false": 0,
            "reports_with_unresolved_closures": 0,
        },
        "stage_transition_drain": {
            "status_counts": {},
            "stopped_reason_counts": {},
            "attempts": 0,
            "executed": 0,
            "skipped": 0,
            "counts_toward_max_rounds_true": 0,
            "counts_toward_max_rounds_false": 0,
            "generates_new_hypothesis_true": 0,
            "generates_new_hypothesis_false": 0,
        },
        "runtime_budget_diagnostics": {
            "source_count": 0,
            "diagnostic_count": 0,
            "code_counts": {},
            "severity_counts": {},
            "stage_counts": {},
            "runtime_model_counts": {},
            "top_diagnostics": [],
        },
    }


def _runtime_feedback_entry(path: Path) -> dict[str, Any]:
    doc = _read_json_object(path)
    fresh = _compact_fresh_runtime_replay_drain(
        _mapping_or_empty(doc.get("fresh_runtime_replay_drain"))
    )
    stage = _compact_stage_transition_drain(
        _mapping_or_empty(doc.get("stage_transition_drain"))
    )
    if not fresh and not stage:
        return {}
    return {
        "report": path.name,
        "path": str(path),
        "fresh_runtime_replay_drain": fresh,
        "stage_transition_drain": stage,
    }


def _compact_fresh_runtime_replay_drain(raw: Mapping[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "status": raw.get("status"),
            "attempts": raw.get("attempts"),
            "executed": raw.get("executed"),
            "skipped": raw.get("skipped"),
            "blocked": raw.get("blocked"),
            "protocol_results": raw.get("protocol_results"),
            "stopped_reason": raw.get("stopped_reason"),
            "counts_toward_max_rounds": raw.get("counts_toward_max_rounds"),
        }
    )


def _compact_stage_transition_drain(raw: Mapping[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "status": raw.get("status"),
            "attempts": raw.get("attempts"),
            "executed": raw.get("executed"),
            "skipped": raw.get("skipped"),
            "limit": raw.get("limit"),
            "stopped_reason": raw.get("stopped_reason"),
            "counts_toward_max_rounds": raw.get("counts_toward_max_rounds"),
            "generates_new_hypothesis": raw.get("generates_new_hypothesis"),
        }
    )


def _merge_runtime_feedback_aggregate(
    aggregate: dict[str, Any],
    entry: Mapping[str, Any],
) -> None:
    fresh = _mapping_or_empty(entry.get("fresh_runtime_replay_drain"))
    stage = _mapping_or_empty(entry.get("stage_transition_drain"))
    if fresh:
        target = aggregate["fresh_runtime_replay_drain"]
        _increment_count(
            target["status_counts"],
            str(fresh.get("status") or "unknown"),
        )
        _increment_count(
            target["stopped_reason_counts"],
            str(fresh.get("stopped_reason") or "none"),
        )
        for key in (
            "attempts",
            "executed",
            "skipped",
            "blocked",
            "protocol_results",
        ):
            target[key] = _int_or_zero(target.get(key)) + _int_or_zero(fresh.get(key))
        if fresh.get("counts_toward_max_rounds") is True:
            target["counts_toward_max_rounds_true"] += 1
        elif fresh.get("counts_toward_max_rounds") is False:
            target["counts_toward_max_rounds_false"] += 1
    if stage:
        target = aggregate["stage_transition_drain"]
        _increment_count(
            target["status_counts"],
            str(stage.get("status") or "unknown"),
        )
        _increment_count(
            target["stopped_reason_counts"],
            str(stage.get("stopped_reason") or "none"),
        )
        for key in ("attempts", "executed", "skipped"):
            target[key] = _int_or_zero(target.get(key)) + _int_or_zero(stage.get(key))
        if stage.get("counts_toward_max_rounds") is True:
            target["counts_toward_max_rounds_true"] += 1
        elif stage.get("counts_toward_max_rounds") is False:
            target["counts_toward_max_rounds_false"] += 1
        if stage.get("generates_new_hypothesis") is True:
            target["generates_new_hypothesis_true"] += 1
        elif stage.get("generates_new_hypothesis") is False:
            target["generates_new_hypothesis_false"] += 1


def _runtime_budget_diagnostics_summary(
    run_root: Path,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    campaign_dir = Path(str(inventory.get("campaign_dir") or run_root / "campaign"))
    source_docs = (
        _read_json_object(campaign_dir / "campaign_summary.json"),
        _read_json_object(campaign_dir / "status.json"),
    )
    summary: dict[str, Any] = {
        "source_count": 0,
        "diagnostic_count": 0,
        "code_counts": {},
        "severity_counts": {},
        "stage_counts": {},
        "runtime_model_counts": {},
        "top_diagnostics": [],
    }
    for doc in source_docs:
        diagnostics = doc.get("runtime_budget_diagnostics")
        if not isinstance(diagnostics, list):
            continue
        summary["source_count"] += 1
        for raw in diagnostics:
            if not isinstance(raw, Mapping):
                continue
            summary["diagnostic_count"] += 1
            _increment_count(summary["code_counts"], str(raw.get("code") or "unknown"))
            _increment_count(
                summary["severity_counts"],
                str(raw.get("severity") or "unknown"),
            )
            _increment_count(
                summary["stage_counts"],
                str(raw.get("stage") or "unknown"),
            )
            runtime_model = raw.get("runtime_model")
            if runtime_model:
                _increment_count(summary["runtime_model_counts"], str(runtime_model))
            if len(summary["top_diagnostics"]) < 3:
                summary["top_diagnostics"].append(
                    _compact_runtime_budget_diagnostic(raw)
                )
    return summary


def _compact_runtime_budget_diagnostic(raw: Mapping[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "branch_id": raw.get("branch_id"),
            "stage": raw.get("stage"),
            "code": raw.get("code"),
            "severity": raw.get("severity"),
            "runtime_model": raw.get("runtime_model"),
            "saturation_ratio": raw.get("saturation_ratio"),
            "threshold_ratio": raw.get("threshold_ratio"),
            "total_pairs": raw.get("total_pairs"),
        }
    )


def _failure_taxonomy_summary(
    run_root: Path,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    phase4 = _mapping_or_empty(inventory.get("phase4_evidence_coverage"))
    current_run_evidence = phase4.get("current_run_evidence") is True
    base = {
        "schema_version": "scion.postrun_failure_taxonomy_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "raw_logs_excluded": True,
        "current_run_evidence": current_run_evidence,
        "available": False,
        "report_count": 0,
        "failure_report_count": 0,
        "aggregate": _empty_failure_taxonomy_aggregate(),
        "entries": [],
    }
    if not current_run_evidence:
        return base

    report_paths = _research_efficiency_report_paths(run_root, inventory)
    entries: list[dict[str, Any]] = []
    aggregate = _empty_failure_taxonomy_aggregate()
    for path in report_paths:
        entry = _failure_taxonomy_entry(path)
        if not entry:
            continue
        entries.append(entry)
        _merge_failure_taxonomy_aggregate(aggregate, entry)

    return {
        **base,
        "available": bool(entries),
        "report_count": len(report_paths),
        "failure_report_count": len(entries),
        "aggregate": aggregate,
        "entries": entries,
    }


def _empty_failure_taxonomy_aggregate() -> dict[str, Any]:
    return {
        "failure_count_maxima": {},
        "failure_observation_counts": {},
        "failure_source_counts": {},
        "run_validity_status_counts": {},
        "stopped_reason_counts": {},
        "proposal_quality": {
            "proposal_attempts_total": 0,
            "proposal_attempts_consumed": 0,
            "proposal_quality_blocks": 0,
            "quality_blocks": 0,
            "quality_block_ledger_count": 0,
            "reports_with_quality_blocks": 0,
            "quality_block_reason_counts": {},
        },
        "top_examples": [],
    }


def _failure_taxonomy_entry(path: Path) -> dict[str, Any]:
    doc = _read_json_object(path)
    proposal = _compact_proposal_quality(
        _mapping_or_empty(doc.get("proposal_quality"))
    )
    taxonomy = _compact_failure_taxonomy(
        _mapping_or_empty(doc.get("failure_taxonomy"))
    )
    run_status = _compact_failure_run_status(
        _mapping_or_empty(doc.get("run_status"))
    )
    failures = _compact_failure_taxonomy(_mapping_or_empty(doc.get("failures")))
    if not proposal and not taxonomy and not failures and not run_status:
        return {}
    taxonomy_source = taxonomy or failures
    top_failure_keys = _top_failure_keys(taxonomy_source)
    examples = _failure_examples(path.name, taxonomy_source)
    return {
        "report": path.name,
        "path": str(path),
        "proposal_quality": proposal,
        "failure_taxonomy": taxonomy_source,
        "failure_observations_total": sum(
            _int_or_zero(item.get("observations"))
            for item in taxonomy_source.values()
            if isinstance(item, Mapping)
        ),
        "top_failure_keys": top_failure_keys,
        "top_examples": examples[:5],
        "run_status": run_status,
    }


def _compact_proposal_quality(raw: Mapping[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "proposal_attempts_total": raw.get("proposal_attempts_total"),
            "proposal_attempts_consumed": raw.get("proposal_attempts_consumed"),
            "proposal_quality_blocks": raw.get("proposal_quality_blocks"),
            "quality_blocks": raw.get("quality_blocks"),
            "quality_block_ledger_count": raw.get("quality_block_ledger_count"),
            "quality_block_reasons": _string_items(raw.get("quality_block_reasons")),
            "semantics": raw.get("semantics"),
        }
    )


def _compact_failure_taxonomy(raw: Mapping[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key, value in sorted(raw.items()):
        if not isinstance(value, Mapping):
            continue
        bucket = _drop_empty(
            {
                "count": value.get("count"),
                "observations": value.get("observations"),
                "source_counts": _mapping_or_empty(value.get("source_counts")),
                "examples": _string_items(value.get("examples"))[:3],
            }
        )
        if bucket:
            compact[str(key)] = bucket
    return compact


def _compact_failure_run_status(raw: Mapping[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "run_validity_status": raw.get("run_validity_status"),
            "stopped_reason": raw.get("stopped_reason"),
            "run_complete": raw.get("run_complete"),
            "run_completeness_status": raw.get("run_completeness_status"),
            "wrapper_exit_status": raw.get("wrapper_exit_status"),
            "campaign_exit_status": raw.get("campaign_exit_status"),
        }
    )


def _top_failure_keys(taxonomy: Mapping[str, Any]) -> list[str]:
    scored: list[tuple[int, int, str]] = []
    for key, value in taxonomy.items():
        if not isinstance(value, Mapping):
            continue
        observations = _int_or_zero(value.get("observations"))
        count = _int_or_zero(value.get("count"))
        if observations > 0 or count > 0:
            scored.append((observations, count, str(key)))
    scored.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return [key for _, _, key in scored[:5]]


def _failure_examples(report: str, taxonomy: Mapping[str, Any]) -> list[dict[str, str]]:
    examples: list[dict[str, str]] = []
    for key in _top_failure_keys(taxonomy):
        bucket = _mapping_or_empty(taxonomy.get(key))
        for example in _string_items(bucket.get("examples"))[:2]:
            examples.append(
                {
                    "report": report,
                    "failure_key": key,
                    "example": example,
                }
            )
            if len(examples) >= 5:
                return examples
    return examples


def _merge_failure_taxonomy_aggregate(
    aggregate: dict[str, Any],
    entry: Mapping[str, Any],
) -> None:
    proposal = _mapping_or_empty(entry.get("proposal_quality"))
    proposal_target = aggregate["proposal_quality"]
    for key in (
        "proposal_attempts_total",
        "proposal_attempts_consumed",
        "proposal_quality_blocks",
        "quality_blocks",
        "quality_block_ledger_count",
    ):
        proposal_target[key] = _int_or_zero(proposal_target.get(key)) + _int_or_zero(
            proposal.get(key)
        )
    if (
        _int_or_zero(proposal.get("proposal_quality_blocks")) > 0
        or _int_or_zero(proposal.get("quality_blocks")) > 0
        or _int_or_zero(proposal.get("quality_block_ledger_count")) > 0
    ):
        proposal_target["reports_with_quality_blocks"] += 1
    for reason in _string_items(proposal.get("quality_block_reasons")):
        _increment_count(proposal_target["quality_block_reason_counts"], reason)

    taxonomy = _mapping_or_empty(entry.get("failure_taxonomy"))
    for key, raw_bucket in taxonomy.items():
        if not isinstance(raw_bucket, Mapping):
            continue
        bucket = _mapping_or_empty(raw_bucket)
        aggregate["failure_count_maxima"][key] = max(
            _int_or_zero(aggregate["failure_count_maxima"].get(key)),
            _int_or_zero(bucket.get("count")),
        )
        observations = _int_or_zero(bucket.get("observations"))
        if observations:
            _increment_count(
                aggregate["failure_observation_counts"],
                str(key),
                observations,
            )
        source_counts = bucket.get("source_counts")
        if isinstance(source_counts, Mapping):
            for source, count in sorted(source_counts.items()):
                _increment_count(
                    aggregate["failure_source_counts"],
                    str(source),
                    _int_or_zero(count),
                )
    run_status = _mapping_or_empty(entry.get("run_status"))
    _increment_count(
        aggregate["run_validity_status_counts"],
        str(run_status.get("run_validity_status") or "unknown"),
    )
    _increment_count(
        aggregate["stopped_reason_counts"],
        str(run_status.get("stopped_reason") or "unknown"),
    )
    for example in entry.get("top_examples") or []:
        if isinstance(example, Mapping) and len(aggregate["top_examples"]) < 5:
            aggregate["top_examples"].append(dict(example))


def _prompt_context_visibility_summary(
    run_root: Path,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    phase4 = _mapping_or_empty(inventory.get("phase4_evidence_coverage"))
    current_run_evidence = phase4.get("current_run_evidence") is True
    base = {
        "schema_version": "scion.postrun_prompt_context_visibility_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "raw_prompt_excluded": True,
        "raw_response_excluded": True,
        "patch_body_excluded": True,
        "current_run_evidence": current_run_evidence,
        "available": False,
        "manifest_report_count": 0,
        "context_report_count": 0,
        "aggregate": _empty_prompt_context_aggregate(),
        "entries": [],
    }
    if not current_run_evidence:
        return base

    report_paths = _proposal_trajectory_manifest_paths(run_root, inventory)
    entries: list[dict[str, Any]] = []
    aggregate = _empty_prompt_context_aggregate()
    for path in report_paths:
        entry = _proposal_trajectory_context_entry(path)
        if not entry:
            continue
        entries.append(entry)
        _merge_prompt_context_aggregate(aggregate, entry)

    return {
        **base,
        "available": any(
            _int_or_zero(entry.get("visibility_digest_count")) > 0
            or _int_or_zero(entry.get("block_family_trace_count")) > 0
            for entry in entries
        ),
        "manifest_report_count": len(report_paths),
        "context_report_count": len(entries),
        "aggregate": _with_prompt_signal_density(aggregate),
        "entries": entries,
    }


def _empty_prompt_context_aggregate() -> dict[str, Any]:
    return {
        "prompt_manifest_ref_count": 0,
        "prompt_manifest_loaded_count": 0,
        "trace_count": 0,
        "visibility_digest_count": 0,
        "block_family_trace_count": 0,
        "omitted_section_trace_count": 0,
        "truncated_section_trace_count": 0,
        "call_kind_counts": {},
        "block_family_totals": {},
        "omitted_section_counts": {},
        "truncated_section_counts": {},
        "signal_density": {},
    }


def _proposal_trajectory_manifest_paths(
    run_root: Path,
    inventory: Mapping[str, Any],
) -> list[Path]:
    reports = _mapping_or_empty(inventory.get("postrun_reports"))
    files = reports.get("files")
    if isinstance(files, Mapping):
        manifest_files = files.get("manifests")
        if isinstance(manifest_files, list):
            report_dir = run_root / "postrun_acceptance"
            return sorted(
                report_dir / str(path)
                for path in manifest_files
                if str(path).endswith(".json")
            )
    return sorted(
        path
        for path in (run_root / "postrun_acceptance" / "manifests").glob("*.json")
        if path.is_file()
    )


def _proposal_trajectory_context_entry(path: Path) -> dict[str, Any]:
    doc = _read_json_object(path)
    sessions = doc.get("sessions")
    if not isinstance(sessions, list):
        return {}
    counts = _mapping_or_empty(doc.get("counts"))
    entry = {
        "report": path.name,
        "path": str(path),
        "prompt_manifest_ref_count": _int_or_zero(
            counts.get("prompt_manifest_ref_count")
        ),
        "prompt_manifest_loaded_count": _int_or_zero(
            counts.get("prompt_manifest_loaded_count")
        ),
        "trace_count": 0,
        "visibility_digest_count": 0,
        "block_family_trace_count": 0,
        "omitted_section_trace_count": 0,
        "truncated_section_trace_count": 0,
        "call_kind_counts": {},
        "block_family_totals": {},
        "omitted_section_counts": {},
        "truncated_section_counts": {},
    }
    for session in sessions:
        if not isinstance(session, Mapping):
            continue
        traces = session.get("trace_fingerprints")
        if not isinstance(traces, list):
            continue
        for trace in traces:
            if not isinstance(trace, Mapping):
                continue
            _add_prompt_trace_context(entry, trace)
    return entry


def _add_prompt_trace_context(entry: dict[str, Any], trace: Mapping[str, Any]) -> None:
    entry["trace_count"] = _int_or_zero(entry.get("trace_count")) + 1
    call_kind = str(trace.get("call_kind") or "unknown")
    _increment_count(entry["call_kind_counts"], call_kind)
    if trace.get("visibility_ledger_digest"):
        entry["visibility_digest_count"] += 1

    block_summary = _mapping_or_empty(trace.get("block_family_summary"))
    families = _mapping_or_empty(block_summary.get("families"))
    if families:
        entry["block_family_trace_count"] += 1
    for family, raw in sorted(families.items()):
        if isinstance(raw, Mapping):
            _add_block_family(entry["block_family_totals"], str(family), raw)

    omitted = _string_items(trace.get("omitted_sections"))
    if omitted:
        entry["omitted_section_trace_count"] += 1
        for section in omitted:
            _increment_count(entry["omitted_section_counts"], section)
    truncated = _string_items(trace.get("truncated_sections"))
    if truncated:
        entry["truncated_section_trace_count"] += 1
        for section in truncated:
            _increment_count(entry["truncated_section_counts"], section)


def _merge_prompt_context_aggregate(
    aggregate: dict[str, Any],
    entry: Mapping[str, Any],
) -> None:
    for key in (
        "prompt_manifest_ref_count",
        "prompt_manifest_loaded_count",
        "trace_count",
        "visibility_digest_count",
        "block_family_trace_count",
        "omitted_section_trace_count",
        "truncated_section_trace_count",
    ):
        aggregate[key] = _int_or_zero(aggregate.get(key)) + _int_or_zero(
            entry.get(key)
        )
    for key in ("call_kind_counts", "omitted_section_counts", "truncated_section_counts"):
        target = aggregate[key]
        source = entry.get(key)
        if not isinstance(source, Mapping):
            continue
        for item_key, value in sorted(source.items()):
            _increment_count(target, str(item_key), _int_or_zero(value))
    families = entry.get("block_family_totals")
    if isinstance(families, Mapping):
        for family, raw in sorted(families.items()):
            if isinstance(raw, Mapping):
                _add_block_family(aggregate["block_family_totals"], str(family), raw)


def _with_prompt_signal_density(aggregate: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(aggregate)
    enriched["signal_density"] = _prompt_signal_density(
        _mapping_or_empty(enriched.get("block_family_totals"))
    )
    return enriched


def _prompt_signal_density(families: Mapping[str, Any]) -> dict[str, Any]:
    token_by_family: dict[str, int] = {
        str(family): _int_or_zero(_mapping_or_empty(raw).get("token_estimate"))
        for family, raw in families.items()
    }
    total_tokens = sum(token_by_family.values())
    research_tokens = _family_token_sum(token_by_family, ("research", "problem"))
    source_tokens = _family_token_sum(token_by_family, ("source", "code"))
    cross_branch_tokens = _family_token_sum(
        token_by_family,
        ("cross_branch", "branch_lesson", "lesson"),
    )
    governance_tokens = _family_token_sum(
        token_by_family,
        ("governance", "contract", "decision", "protocol", "compliance"),
    )
    research_plus_source = research_tokens + source_tokens
    return {
        "schema_version": "scion.postrun_prompt_signal_density.v1",
        "report_only": True,
        "decision_features_excluded": True,
        "total_token_estimate": total_tokens,
        "research_signal_tokens": research_tokens,
        "source_code_tokens": source_tokens,
        "cross_branch_tokens": cross_branch_tokens,
        "governance_tokens": governance_tokens,
        "research_signal_share": _safe_ratio(research_tokens, total_tokens),
        "source_code_share": _safe_ratio(source_tokens, total_tokens),
        "cross_branch_share": _safe_ratio(cross_branch_tokens, total_tokens),
        "governance_share": _safe_ratio(governance_tokens, total_tokens),
        "research_plus_source_to_governance_ratio": _safe_ratio(
            research_plus_source,
            governance_tokens,
        ),
        "interpretation": _prompt_signal_density_interpretation(
            research_plus_source=research_plus_source,
            governance_tokens=governance_tokens,
            total_tokens=total_tokens,
        ),
    }


def _family_token_sum(
    token_by_family: Mapping[str, int],
    needles: tuple[str, ...],
) -> int:
    total = 0
    for family, tokens in token_by_family.items():
        normalized = family.lower().replace("-", "_")
        if any(needle in normalized for needle in needles):
            total += _int_or_zero(tokens)
    return total


def _prompt_signal_density_interpretation(
    *,
    research_plus_source: int,
    governance_tokens: int,
    total_tokens: int,
) -> str:
    if total_tokens <= 0:
        return "no_prompt_family_token_accounting_available"
    if research_plus_source <= 0:
        return "research_and_source_signal_absent"
    if governance_tokens > research_plus_source:
        return "governance_tokens_exceed_research_and_source_signal"
    if governance_tokens > 0:
        return "research_and_source_signal_at_least_governance"
    return "research_and_source_signal_without_governance_token_load"


def _add_block_family(
    totals: dict[str, dict[str, int]],
    family: str,
    raw: Mapping[str, Any],
) -> None:
    item = totals.setdefault(
        family,
        {"trace_count": 0, "char_count": 0, "token_estimate": 0},
    )
    item["trace_count"] += _int_or_zero(raw.get("trace_count")) or 1
    item["char_count"] += _int_or_zero(raw.get("char_count"))
    item["token_estimate"] += _int_or_zero(raw.get("token_estimate"))


def _increment_count(
    counts: dict[str, int],
    key: str,
    amount: int = 1,
) -> None:
    if not key:
        return
    counts[key] = counts.get(key, 0) + amount


def _drop_empty(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): item
        for key, item in value.items()
        if item not in (None, "", [], {})
    }


def _research_continuity_summary(
    run_root: Path,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    phase4 = _mapping_or_empty(inventory.get("phase4_evidence_coverage"))
    current_run_evidence = phase4.get("current_run_evidence") is True
    base = {
        "schema_version": "scion.postrun_research_continuity_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "current_run_evidence": current_run_evidence,
        "available": False,
        "report_count": 0,
        "continuity_report_count": 0,
        "entries": [],
    }
    if not current_run_evidence:
        return base

    report_paths = _research_efficiency_report_paths(run_root, inventory)
    entries = []
    for path in report_paths:
        doc = _read_json_object(path)
        continuity = doc.get("research_continuity")
        if not isinstance(continuity, Mapping) or not continuity:
            continue
        entries.append(
            {
                "report": path.name,
                "path": str(path),
                "same_mechanism_followup": _mapping_or_empty(
                    continuity.get("same_mechanism_followup")
                ),
                "branch_lesson_usage": _mapping_or_empty(
                    continuity.get("branch_lesson_usage")
                ),
                "weak_positive_transfer": _mapping_or_empty(
                    continuity.get("weak_positive_transfer")
                ),
                "lesson_action_counts": _mapping_or_empty(
                    continuity.get("lesson_action_counts")
                ),
                "research_shape_summary": _mapping_or_empty(
                    continuity.get("research_shape_summary")
                ),
            }
        )

    return {
        **base,
        "available": bool(entries),
        "report_count": len(report_paths),
        "continuity_report_count": len(entries),
        "entries": entries,
    }


def _research_efficiency_report_paths(
    run_root: Path,
    inventory: Mapping[str, Any],
) -> list[Path]:
    reports = _mapping_or_empty(inventory.get("postrun_reports"))
    files = reports.get("files")
    if isinstance(files, Mapping):
        research_files = files.get("research_efficiency")
        if isinstance(research_files, list):
            report_dir = run_root / "postrun_acceptance"
            return sorted(
                report_dir / str(path)
                for path in research_files
                if str(path).endswith(".json")
            )
    return sorted(
        path
        for path in (run_root / "postrun_acceptance" / "research_efficiency").glob(
            "*.json"
        )
        if path.is_file()
    )


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(loaded) if isinstance(loaded, Mapping) else {}


def _stop_conditions(inventory: dict[str, Any]) -> list[str]:
    lifecycle = inventory.get("lifecycle") or {}
    if lifecycle.get("prepared_only") is True:
        return [
            "PREPARED-ONLY ROOT: do not analyze copied campaign artifacts as current-run research evidence.",
            "Launch only after completion preflight succeeds, then regenerate/read postrun_acceptance reports before research-quality conclusions.",
        ]
    validity = inventory.get("validity") or {}
    counters = inventory.get("counters") or {}
    conditions: list[str] = []
    if validity.get("invalid_infra_only") is True:
        conditions.append(
            "INVALID INFRA-ONLY RUN: prove provider/proxy/account status and do not analyze as research behavior."
        )
    if _int_or_zero(counters.get("effective_rounds_completed")) == 0:
        conditions.append(
            "No effective rounds recorded: treat as invalid for research-quality conclusions until contradicted by stronger artifacts."
        )
    if _int_or_zero(counters.get("formal_screened_candidates")) == 0:
        conditions.append(
            "No formal screened candidates recorded: do not infer algorithm quality from this run."
        )
    return conditions


def _display(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _list_text(values: list[Any]) -> str:
    return ", ".join(str(value) for value in values) if values else "none"


def _string_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _mapping_text(value: Any) -> str:
    if not isinstance(value, dict) or not value:
        return "none"
    return ", ".join(f"{key}={value[key]}" for key in sorted(value))


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 6)


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
