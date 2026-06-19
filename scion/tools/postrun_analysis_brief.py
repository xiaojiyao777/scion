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

COMMON_REQUIRED_QUESTIONS = (
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
    "Did research_context_actionability_summary connect continuity gaps to "
    "prompt-visible research, source, and cross-branch signal?",
    "Did runtime_feedback_summary show fresh replay drain, stage-transition drain, "
    "and budget diagnostics consistent with the declared runtime model?",
    "Did failure_taxonomy_summary distinguish provider/infra, framework/control, "
    "proposal/codegen/tool, and algorithm-quality failures?",
    "Were repeated near-duplicate branches avoided or correctly diagnosed?",
    "Are failures framework/control regressions, provider/infra failures, or algorithm-quality failures?",
    "Is the next step repair, same-round rerun, or ladder advancement?",
)

PREPARED_ONLY_REQUIRED_QUESTIONS = (
    "Is this still a prepared-only launch root with zero current-run counters "
    "and no postrun acceptance evidence?",
    "Do prepared_run_contract, launch_readiness, and prompt_context_readiness "
    "prove artifact identity, manifest commit, launch markers, and prompt bridge "
    "readiness?",
    "Does the problem-specific prepared handoff include all required report-only "
    "requirements while keeping DecisionFeatures, scheduler, promotion, and "
    "solver semantics unchanged?",
    "Does completion preflight block launch with actionable auth/operator status "
    "when the real completion route is unavailable?",
    "Is the next step launch-readiness recheck or launch, not a research-quality "
    "or plateau/two-opt conclusion?",
)

WAREHOUSE_FOLLOWUP_REQUIRED_QUESTION = (
    "For warehouse follow-up, did warehouse_followup_summary distinguish "
    "prepared-only, incomplete-handoff, quality-blocked, protocol-evaluated, "
    "and plateau-review-ready evidence?"
)

CVRP_LARGE_TWOOPT_REQUIRED_QUESTION = (
    "For CVRP large-twoopt follow-up, did cvrp_large_twoopt_summary distinguish "
    "prepared-only, incomplete handoff, missing review inputs, missing two-opt "
    "mechanism signal, and review-ready evidence?"
)

WAREHOUSE_FOLLOWUP_REQUIREMENT_KEYS = (
    "warehouse_v2_checkpoint_handoff",
    "warehouse_continuous_plateau_question",
    "warehouse_required_evidence_handoff",
    "warehouse_default_avoid_handoff",
    "warehouse_decision_boundary_handoff",
)

WAREHOUSE_FOLLOWUP_REVIEW_AXES = (
    "preserve_or_improve_champion_v2_promotion_behavior",
    "separate_quality_blocked_proposals_from_protocol_evaluated_no_effect",
    "compare_cost_delta_and_improving_move_telemetry_before_split_delta_only_claims",
    "explain_fast_completion_against_warehouse_runtime_model",
    "judge_continuous_improvement_vs_real_plateau_only_after_current_run_postrun_evidence",
)

CVRP_LARGE_TWOOPT_REQUIREMENT_KEYS = (
    "cvrp_large_twoopt_seed_handoff",
    "cvrp_large_twoopt_unbounded_default_avoid_handoff",
    "cvrp_large_twoopt_bounded_constraints_handoff",
    "cvrp_measurement_mde_handoff",
    "cvrp_low_snr_reason_handoff",
    "cvrp_decision_boundary_handoff",
)

CVRP_LARGE_TWOOPT_REVIEW_AXES = (
    "confirm_deadline_or_remaining_time_guard_in_solver_code",
    "confirm_no_unbounded_two_opt_intra_or_vns_fallback_above_large_threshold",
    "inspect_pair_level_total_distance_feasibility_route_count_and_wall_clock_evidence",
    "interpret_effect_against_aa_mde_and_case_level_variance",
    "reject_activation_only_or_seed_selection_only_claims",
)


def build_brief(run_root: Path | str) -> dict[str, Any]:
    inventory = build_inventory(run_root)
    run_root_path = Path(inventory["run_root"])
    campaign_dir = Path(inventory["campaign_dir"])
    branch_research_state_summary = _branch_research_state_summary(inventory)
    protocol_accounting_summary = _protocol_accounting_summary(
        run_root_path,
        inventory,
    )
    measurement_effect_summary = _measurement_effect_summary(
        run_root_path,
        inventory,
    )
    runtime_feedback_summary = _runtime_feedback_summary(
        run_root_path,
        inventory,
    )
    failure_taxonomy_summary = _failure_taxonomy_summary(
        run_root_path,
        inventory,
    )
    prompt_context_visibility_summary = _prompt_context_visibility_summary(
        run_root_path,
        inventory,
    )
    research_continuity_summary = _research_continuity_summary(
        run_root_path,
        inventory,
    )
    research_context_actionability_summary = (
        _research_context_actionability_summary(
            prompt_context_visibility_summary=prompt_context_visibility_summary,
            research_continuity_summary=research_continuity_summary,
        )
    )
    warehouse_followup_summary = _warehouse_followup_summary(
        inventory,
        protocol_accounting_summary=protocol_accounting_summary,
        measurement_effect_summary=measurement_effect_summary,
        runtime_feedback_summary=runtime_feedback_summary,
        failure_taxonomy_summary=failure_taxonomy_summary,
        research_continuity_summary=research_continuity_summary,
    )
    cvrp_large_twoopt_summary = _cvrp_large_twoopt_summary(
        inventory,
        protocol_accounting_summary=protocol_accounting_summary,
        measurement_effect_summary=measurement_effect_summary,
        runtime_feedback_summary=runtime_feedback_summary,
        failure_taxonomy_summary=failure_taxonomy_summary,
        research_continuity_summary=research_continuity_summary,
    )
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
        "branch_research_state_summary": branch_research_state_summary,
        "protocol_accounting_summary": protocol_accounting_summary,
        "measurement_effect_summary": measurement_effect_summary,
        "runtime_feedback_summary": runtime_feedback_summary,
        "failure_taxonomy_summary": failure_taxonomy_summary,
        "prompt_context_visibility_summary": prompt_context_visibility_summary,
        "research_continuity_summary": research_continuity_summary,
        "research_context_actionability_summary": (
            research_context_actionability_summary
        ),
        "warehouse_followup_summary": warehouse_followup_summary,
        "cvrp_large_twoopt_summary": cvrp_large_twoopt_summary,
        "stop_conditions": _stop_conditions(inventory),
        "required_questions": _required_questions(
            lifecycle=inventory["lifecycle"],
            warehouse_followup_summary=warehouse_followup_summary,
            cvrp_large_twoopt_summary=cvrp_large_twoopt_summary,
        ),
    }


def _required_questions(
    *,
    lifecycle: Mapping[str, Any],
    warehouse_followup_summary: Mapping[str, Any],
    cvrp_large_twoopt_summary: Mapping[str, Any],
) -> list[str]:
    if lifecycle.get("prepared_only") is True:
        questions = list(PREPARED_ONLY_REQUIRED_QUESTIONS)
    else:
        questions = list(COMMON_REQUIRED_QUESTIONS)
    if warehouse_followup_summary.get("available") is True:
        questions.append(WAREHOUSE_FOLLOWUP_REQUIRED_QUESTION)
    if cvrp_large_twoopt_summary.get("available") is True:
        questions.append(CVRP_LARGE_TWOOPT_REQUIRED_QUESTION)
    return questions


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
        measurement = research_focus.get("measurement_opportunity_diagnostics")
        lines.append("  - Measurement/opportunity diagnostics:")
        if isinstance(measurement, dict) and measurement:
            for key in (
                "metric",
                "runtime_model",
                "pairing_validity",
                "practical_screen_delta",
                "screening_mde_at_power_80",
                "recommended_min_seeds",
                "summary",
            ):
                value = measurement.get(key)
                if value not in (None, "", [], {}, ()):
                    lines.append(f"    - {key}: {_display(value)}")
            reason_codes = measurement.get("reason_codes")
            if isinstance(reason_codes, list) and reason_codes:
                lines.append(
                    "    - reason_codes: "
                    + ", ".join(_display(item) for item in reason_codes)
                )
        else:
            lines.append("    - None recorded in the prepared manifest.")
        opportunity_classes = research_focus.get("measurable_opportunity_classes")
        lines.append("  - Measurable opportunity classes:")
        if isinstance(opportunity_classes, list) and opportunity_classes:
            lines.extend(f"    - {_display(item)}" for item in opportunity_classes)
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
    problem_specific = phase4.get("problem_specific_requirements")
    if isinstance(problem_specific, dict) and problem_specific:
        lines.extend(
            [
                "",
                "### Problem-Specific Phase 4 Evidence Coverage",
                "| Requirement | Available | Count | Source |",
                "|---|---:|---:|---|",
            ]
        )
        for key, item in sorted(problem_specific.items()):
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

    branch_state = brief.get("branch_research_state_summary") or {}
    branch_aggregate = _mapping_or_empty(branch_state.get("aggregate"))
    lines.extend(
        [
            "",
            "## Branch Research State Summary",
            "- Source: current-run branch, hypothesis, event, and LLM trace "
            "inventory counts.",
            f"- Available: `{_display(branch_state.get('available'))}`",
            "- Current-run evidence: "
            f"`{_display(branch_state.get('current_run_evidence'))}`",
            "- Branches / lineages: "
            f"{_display(branch_aggregate.get('branch_count'))} / "
            f"{_display(branch_aggregate.get('lineage_count'))}",
            "- Branch states: "
            f"{_mapping_text(branch_aggregate.get('branch_state_counts'))}",
            "- Branches with hypotheses/events/sessions/traces: "
            f"{_display(branch_aggregate.get('branches_with_hypotheses'))} / "
            f"{_display(branch_aggregate.get('branches_with_events'))} / "
            f"{_display(branch_aggregate.get('branches_with_sessions'))} / "
            f"{_display(branch_aggregate.get('branches_with_traces'))}",
            "- Rollbacks total / branches with rollback: "
            f"{_display(branch_aggregate.get('rollback_count_total'))} / "
            f"{_display(branch_aggregate.get('branches_with_rollback'))}",
            "- Branch failure codes: "
            f"{_mapping_text(branch_aggregate.get('failure_code_counts'))}",
            "- Hypotheses by status/action/locus: "
            f"{_mapping_text(branch_aggregate.get('hypotheses_by_status'))} / "
            f"{_mapping_text(branch_aggregate.get('hypotheses_by_action'))} / "
            f"{_mapping_text(branch_aggregate.get('hypotheses_by_change_locus'))}",
            "- Events by kind/decision/stage: "
            f"{_mapping_text(branch_aggregate.get('events_by_kind'))} / "
            f"{_mapping_text(branch_aggregate.get('events_by_decision'))} / "
            f"{_mapping_text(branch_aggregate.get('events_by_stage'))}",
        ]
    )
    top_branches = branch_state.get("top_branches")
    if isinstance(top_branches, list) and top_branches:
        lines.extend(
            [
                "| Branch | State | Lineage | Hypotheses | Events | Sessions | Traces | Rollbacks | Failures |",
                "|---|---|---|---:|---:|---:|---:|---:|---|",
            ]
        )
        for branch in top_branches:
            if not isinstance(branch, dict):
                continue
            lines.append(
                "| {branch_id} | {state} | {lineage_id} | {hypotheses} | "
                "{events} | {sessions} | {traces} | {rollbacks} | {failures} |".format(
                    branch_id=_display(branch.get("branch_id")),
                    state=_display(branch.get("state")),
                    lineage_id=_display(branch.get("lineage_id")),
                    hypotheses=_display(branch.get("hypothesis_count")),
                    events=_display(branch.get("event_count")),
                    sessions=_display(branch.get("session_count")),
                    traces=_display(branch.get("trace_count")),
                    rollbacks=_display(branch.get("rollback_count")),
                    failures=_list_text(branch.get("failure_codes") or []),
                )
            )

    accounting = brief.get("protocol_accounting_summary") or {}
    accounting_aggregate = _mapping_or_empty(accounting.get("aggregate"))
    effective_budget = _mapping_or_empty(
        accounting_aggregate.get("effective_budget")
    )
    protocol_rows = _mapping_or_empty(accounting_aggregate.get("protocol_rows"))
    formal_artifacts = _mapping_or_empty(
        accounting_aggregate.get("formal_candidate_artifacts")
    )
    stage_rows = _mapping_or_empty(accounting_aggregate.get("stage_rows"))
    lines.extend(
        [
            "",
            "## Protocol Accounting Summary",
            "- Source: current-run research-efficiency `effective_budget`, "
            "`protocol_rows`, formal candidate, stage-row, and reconciliation fields.",
            f"- Available: `{_display(accounting.get('available'))}`",
            "- Current-run evidence: "
            f"`{_display(accounting.get('current_run_evidence'))}`",
            "- Reports with accounting: "
            f"`{_display(accounting.get('accounting_report_count'))}`",
            "- Requested/effective rounds: "
            f"{_display(effective_budget.get('requested_rounds'))} / "
            f"{_display(effective_budget.get('effective_rounds_completed'))}",
            "- Completed requested rounds reports: "
            f"{_display(effective_budget.get('completed_requested_rounds_true'))}",
            "- Stop reasons: "
            f"{_mapping_text(effective_budget.get('stopped_reason_counts'))}",
            "- Protocol rows metric/evaluated/effective: "
            f"{_display(protocol_rows.get('protocol_metric_results'))} / "
            f"{_display(protocol_rows.get('protocol_evaluated_candidates'))} / "
            f"{_display(protocol_rows.get('effective_protocol_rounds'))}",
            "- Stage rows screening/validation/frozen/fresh-runtime: "
            f"{_display(stage_rows.get('screening'))} / "
            f"{_display(stage_rows.get('validation'))} / "
            f"{_display(stage_rows.get('frozen'))} / "
            f"{_display(stage_rows.get('fresh_runtime_replay'))}",
            "- Formal candidates screened/evaluated/artifact rows: "
            f"{_display(accounting_aggregate.get('formal_screened_candidates'))} / "
            f"{_display(accounting_aggregate.get('formal_protocol_evaluated_candidates'))}"
            " / "
            f"{_display(formal_artifacts.get('row_count'))}",
            "- Formal candidate index statuses: "
            f"{_mapping_text(formal_artifacts.get('index_status_counts'))}",
        ]
    )
    accounting_entries = accounting.get("entries")
    if isinstance(accounting_entries, list) and accounting_entries:
        lines.extend(
            [
                "| Report | Requested | Effective | Protocol rows | "
                "Formal artifacts | Stages s/v/f/fr | Stop reason |",
                "|---|---:|---:|---:|---:|---|---|",
            ]
        )
        for entry in accounting_entries:
            if not isinstance(entry, dict):
                continue
            budget_entry = _mapping_or_empty(entry.get("effective_budget"))
            rows_entry = _mapping_or_empty(entry.get("protocol_rows"))
            artifact_entry = _mapping_or_empty(
                entry.get("formal_candidate_artifacts")
            )
            stage_entry = _mapping_or_empty(entry.get("stage_rows"))
            lines.append(
                "| {report} | {requested} | {effective} | {protocol_rows} | "
                "{formal_artifacts} | {stages} | {stop_reason} |".format(
                    report=_display(entry.get("report")),
                    requested=_display(budget_entry.get("requested_rounds")),
                    effective=_display(
                        budget_entry.get("effective_rounds_completed")
                    ),
                    protocol_rows=_display(rows_entry.get("protocol_metric_results")),
                    formal_artifacts=_display(artifact_entry.get("row_count")),
                    stages=(
                        f"{_display(stage_entry.get('screening'))}/"
                        f"{_display(stage_entry.get('validation'))}/"
                        f"{_display(stage_entry.get('frozen'))}/"
                        f"{_display(stage_entry.get('fresh_runtime_replay'))}"
                    ),
                    stop_reason=_display(budget_entry.get("stopped_reason")),
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
            "- Mechanism-family mapped/unmapped rows: "
            f"{_display(effect_aggregate.get('mechanism_family_mapped_row_count'))} / "
            f"{_display(effect_aggregate.get('mechanism_family_unmapped_row_count'))}",
        ]
    )
    family_effects = effect_aggregate.get("mechanism_family_effects")
    if isinstance(family_effects, dict) and family_effects:
        lines.extend(
            [
                "| Mechanism family | Rows | Positive | Nonpositive | At/Above MDE | CI High Below MDE | Max Effect/MDE |",
                "|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for family, payload in sorted(family_effects.items()):
            if not isinstance(payload, dict):
                continue
            lines.append(
                "| {family} | {rows} | {positive} | {nonpositive} | {above} | "
                "{below} | {ratio} |".format(
                    family=_display(family),
                    rows=_display(payload.get("protocol_row_count")),
                    positive=_display(payload.get("positive_rows")),
                    nonpositive=_display(payload.get("nonpositive_rows")),
                    above=_display(payload.get("rows_at_or_above_mde")),
                    below=_display(payload.get("rows_with_ci_high_below_mde")),
                    ratio=_display(payload.get("max_effect_to_mde_ratio")),
                )
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
    source_visibility = _mapping_or_empty(aggregate.get("source_visibility"))
    if source_visibility:
        lines.extend(
            [
                "- Code source visibility traces: "
                f"{_display(source_visibility.get('code_trace_count'))}",
                "- Code target/protected/required-integration/algorithm visible: "
                f"{_display(source_visibility.get('code_target_source_visible_count'))} / "
                f"{_display(source_visibility.get('code_protected_source_visible_count'))} / "
                f"{_display(source_visibility.get('code_required_integration_source_visible_count'))} / "
                f"{_display(source_visibility.get('code_algorithm_file_read_source_visible_count'))}",
                "- Code missing target/protected/required-source traces: "
                f"{_display(source_visibility.get('code_target_source_missing_count'))} / "
                f"{_display(source_visibility.get('code_protected_source_missing_count'))} / "
                f"{_display(source_visibility.get('code_missing_required_source_trace_count'))}",
                "- Code target source/status: "
                f"{_mapping_text(source_visibility.get('code_target_source_status_counts'))} / "
                f"{_mapping_text(source_visibility.get('code_target_visibility_status_counts'))}",
                "- Hypothesis target source traces/required/visible/not-visible: "
                f"{_display(source_visibility.get('hypothesis_target_source_trace_count'))} / "
                f"{_display(source_visibility.get('hypothesis_target_source_required_count'))} / "
                f"{_display(source_visibility.get('hypothesis_target_source_visible_count'))} / "
                f"{_display(source_visibility.get('hypothesis_target_source_not_visible_count'))}",
                "- Hypothesis target visibility statuses: "
                f"{_mapping_text(source_visibility.get('hypothesis_target_visibility_status_counts'))}",
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
    continuity_aggregate = _mapping_or_empty(continuity.get("aggregate"))
    branch_lesson_failures = _mapping_text(
        continuity_aggregate.get("branch_lesson_semantic_failure_counts")
    )
    branch_lesson_blocks = _mapping_text(
        continuity_aggregate.get("branch_lesson_semantic_block_counts")
    )
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
            "- Branch depth distribution: "
            f"{_mapping_text(continuity_aggregate.get('branch_depth_distribution'))}",
            "- Max/mean branch depth: "
            f"{_display(continuity_aggregate.get('max_branch_depth'))} / "
            f"{_display(continuity_aggregate.get('mean_branch_depth_max'))}",
            "- Active shapes: "
            f"{_mapping_text(continuity_aggregate.get('active_shape_counts'))}",
            "- Active branches/families max: "
            f"{_display(continuity_aggregate.get('active_branch_count_max'))} / "
            f"{_display(continuity_aggregate.get('active_mechanism_family_count_max'))}",
            "- Mechanism family breadth max: "
            f"{_display(continuity_aggregate.get('mechanism_family_count_max'))}",
            "- Mechanism family observations: "
            f"{_mapping_text(continuity_aggregate.get('mechanism_family_counts'))}",
            f"- Branch lesson semantic failures: {branch_lesson_failures}",
            f"- Branch lesson semantic blocks: {branch_lesson_blocks}",
            "- Branch lesson actions: "
            f"{_mapping_text(continuity_aggregate.get('lesson_action_counts'))}",
        ]
    )
    entries = continuity.get("entries")
    if isinstance(entries, list) and entries:
        lines.extend(
            [
                "| Report | Same-mechanism selected/observed | "
                "Branch lessons satisfied/required | Semantic gaps | "
                "Weak-positive accepted/observed | Max depth | Depth distribution | "
                "Active shape | Families |",
                "|---|---:|---:|---:|---:|---:|---|---|---:|",
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
            full_shape = _mapping_or_empty(entry.get("research_shape"))
            active_shape = shape.get("active_shape") or _mapping_or_empty(
                full_shape.get("active_research_shape_signal")
            ).get("shape")
            depth_distribution = shape.get(
                "branch_depth_distribution"
            ) or full_shape.get("branch_depth_distribution")
            lines.append(
                "| {report} | {same_selected}/{same_observed} | "
                "{lesson_satisfied}/{lesson_required} | {semantic_gap} | "
                "{transfer_accepted}/{transfer_observed} | {max_depth} | "
                "{depth_distribution} | {active_shape} | {families} |".format(
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
                    depth_distribution=_mapping_text(depth_distribution),
                    active_shape=_display(active_shape),
                    families=_display(shape.get("mechanism_family_count")),
                )
            )
    else:
        lines.append(
            "- No current-run research_continuity block is available for delegated analysis."
        )

    actionability = brief.get("research_context_actionability_summary") or {}
    actionability_indicators = _mapping_or_empty(actionability.get("indicators"))
    branch_lesson_failure_mix = _mapping_text(
        actionability_indicators.get("branch_lesson_semantic_failure_counts")
    )
    branch_lesson_block_mix = _mapping_text(
        actionability_indicators.get("branch_lesson_semantic_block_counts")
    )
    lines.extend(
        [
            "",
            "## Research Context Actionability Summary",
            "- Source: report-only join of prompt context visibility and "
            "research_continuity diagnostics.",
            f"- Available: `{_display(actionability.get('available'))}`",
            "- Current-run evidence: "
            f"`{_display(actionability.get('current_run_evidence'))}`",
            f"- Guidance status: {_display(actionability.get('guidance_status'))}",
            "- Continuity selected/observed same-mechanism follow-up: "
            f"{_display(actionability_indicators.get('same_mechanism_selected'))} / "
            f"{_display(actionability_indicators.get('same_mechanism_observed'))}",
            "- Branch lessons satisfied/required/semantic gap: "
            f"{_display(actionability_indicators.get('branch_lessons_satisfied'))} / "
            f"{_display(actionability_indicators.get('branch_lessons_required'))} / "
            f"{_display(actionability_indicators.get('branch_lesson_semantic_gap_count'))}",
            "- Branch lesson semantic failure mix: "
            f"{branch_lesson_failure_mix}",
            "- Branch lesson semantic block mix: "
            f"{branch_lesson_block_mix}",
            "- Prompt research/source/cross-branch/governance tokens: "
            f"{_display(actionability_indicators.get('research_signal_tokens'))} / "
            f"{_display(actionability_indicators.get('source_code_tokens'))} / "
            f"{_display(actionability_indicators.get('cross_branch_tokens'))} / "
            f"{_display(actionability_indicators.get('governance_tokens'))}",
            "- Context actionability gaps: "
            f"{_list_text(actionability.get('actionability_gaps') or [])}",
            "- Context actionability recommendations: "
            f"{_list_text(actionability.get('recommendations') or [])}",
        ]
    )

    cvrp_large_twoopt = brief.get("cvrp_large_twoopt_summary") or {}
    if (
        cvrp_large_twoopt.get("available") is True
        or cvrp_large_twoopt.get("problem_family") == "cvrp"
    ):
        cvrp_current_run_evidence = (
            cvrp_large_twoopt.get("current_run_evidence") is True
        )
        evidence = _mapping_or_empty(cvrp_large_twoopt.get("evidence"))
        protocol = _mapping_or_empty(evidence.get("protocol"))
        measurement = _mapping_or_empty(evidence.get("measurement_effect"))
        runtime = _mapping_or_empty(evidence.get("runtime"))
        continuity_evidence = _mapping_or_empty(evidence.get("research_continuity"))
        mechanism = _mapping_or_empty(evidence.get("large_twoopt_mechanism"))
        lines.extend(
            [
                "",
                "## CVRP Large Two-Opt Summary",
                _cvrp_large_twoopt_source_line(cvrp_current_run_evidence),
                f"- Available: `{_display(cvrp_large_twoopt.get('available'))}`",
                "- Current-run evidence: "
                f"`{_display(cvrp_large_twoopt.get('current_run_evidence'))}`",
                "- Launch required before bounded two-opt conclusion: "
                f"`{_display(cvrp_large_twoopt.get('launch_required_before_twoopt_conclusion'))}`",
                f"- Interpretation: {_display(cvrp_large_twoopt.get('interpretation'))}",
                "- Handoff complete: "
                f"`{_display(cvrp_large_twoopt.get('handoff_complete'))}`",
                "- Protocol formal-screened / protocol-evaluated / metric rows: "
                f"{_display(protocol.get('formal_screened_candidates'))} / "
                f"{_display(protocol.get('protocol_evaluated_candidates'))} / "
                f"{_display(protocol.get('protocol_metric_results'))}",
                "- Measurement rows at/above MDE / ci-high below MDE / max effect-MDE: "
                f"{_display(measurement.get('rows_at_or_above_mde'))} / "
                f"{_display(measurement.get('rows_with_ci_high_below_mde'))} / "
                f"{_display(measurement.get('max_effect_to_mde_ratio'))}",
                "- Large two-opt mechanism signal: "
                f"`{_display(mechanism.get('available'))}` / "
                f"{_list_text(mechanism.get('families') or [])}",
                "- Runtime available / diagnostics: "
                f"`{_display(runtime.get('available'))}` / "
                f"{_display(runtime.get('runtime_budget_diagnostic_count'))}",
                "- Research continuity available/reports: "
                f"`{_display(continuity_evidence.get('available'))}` / "
                f"{_display(continuity_evidence.get('continuity_report_count'))}",
            ]
        )
        requirements = cvrp_large_twoopt.get("handoff_requirements")
        if isinstance(requirements, dict) and requirements:
            lines.extend(
                [
                    "| Handoff requirement | Available | Count | Source |",
                    "|---|---:|---:|---|",
                ]
            )
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
        gaps = cvrp_large_twoopt.get("evidence_gaps")
        lines.append("- Evidence gaps:")
        if isinstance(gaps, list) and gaps:
            lines.extend(f"  - {_display(item)}" for item in gaps)
        else:
            lines.append("  - none")
        axes = cvrp_large_twoopt.get("required_review_axes")
        if cvrp_current_run_evidence:
            lines.append("- Required CVRP bounded two-opt review axes:")
        else:
            lines.append("- Deferred post-launch CVRP bounded two-opt review axes:")
            lines.append(
                "  - not_actionable_before_launch_current_run_evidence_required"
            )
        if isinstance(axes, list) and axes:
            lines.extend(f"  - {_display(item)}" for item in axes)
        else:
            lines.append("  - none")

    warehouse = brief.get("warehouse_followup_summary") or {}
    if (
        warehouse.get("available") is True
        or warehouse.get("problem_family") == "warehouse_delivery"
    ):
        warehouse_current_run_evidence = warehouse.get("current_run_evidence") is True
        evidence = _mapping_or_empty(warehouse.get("evidence"))
        protocol = _mapping_or_empty(evidence.get("protocol"))
        measurement = _mapping_or_empty(evidence.get("measurement_effect"))
        quality = _mapping_or_empty(evidence.get("quality_blocks"))
        runtime = _mapping_or_empty(evidence.get("runtime"))
        continuity_evidence = _mapping_or_empty(evidence.get("research_continuity"))
        lines.extend(
            [
                "",
                "## Warehouse Follow-up Summary",
                _warehouse_followup_source_line(warehouse_current_run_evidence),
                f"- Available: `{_display(warehouse.get('available'))}`",
                "- Current-run evidence: "
                f"`{_display(warehouse.get('current_run_evidence'))}`",
                "- Launch required before plateau conclusion: "
                f"`{_display(warehouse.get('launch_required_before_plateau_conclusion'))}`",
                f"- Interpretation: {_display(warehouse.get('interpretation'))}",
                "- Handoff complete: "
                f"`{_display(warehouse.get('handoff_complete'))}`",
                "- Protocol formal-screened / protocol-evaluated / metric rows: "
                f"{_display(protocol.get('formal_screened_candidates'))} / "
                f"{_display(protocol.get('protocol_evaluated_candidates'))} / "
                f"{_display(protocol.get('protocol_metric_results'))}",
                "- Formal candidate artifact rows: "
                f"{_display(protocol.get('formal_candidate_artifact_rows'))}",
                "- Measurement rows at/above MDE / ci-high below MDE / max effect-MDE: "
                f"{_display(measurement.get('rows_at_or_above_mde'))} / "
                f"{_display(measurement.get('rows_with_ci_high_below_mde'))} / "
                f"{_display(measurement.get('max_effect_to_mde_ratio'))}",
                "- Quality-block signal: "
                f"{_display(quality.get('proposal_quality_blocks'))} / "
                f"{_display(quality.get('quality_blocks'))} / "
                f"{_display(quality.get('quality_block_ledger_count'))}",
                "- Quality-block reasons: "
                f"{_mapping_text(quality.get('reason_counts'))}",
                "- Fresh-runtime attempts/executed/protocol results: "
                f"{_display(runtime.get('fresh_runtime_attempts'))} / "
                f"{_display(runtime.get('fresh_runtime_executed'))} / "
                f"{_display(runtime.get('fresh_runtime_protocol_results'))}",
                "- Fresh-runtime statuses: "
                f"{_mapping_text(runtime.get('fresh_runtime_status_counts'))}",
                "- Runtime models / diagnostics: "
                f"{_mapping_text(runtime.get('runtime_model_counts'))} / "
                f"{_display(runtime.get('runtime_budget_diagnostic_count'))}",
                "- Research continuity available/reports: "
                f"`{_display(continuity_evidence.get('available'))}` / "
                f"{_display(continuity_evidence.get('continuity_report_count'))}",
            ]
        )
        requirements = warehouse.get("handoff_requirements")
        if isinstance(requirements, dict) and requirements:
            lines.extend(
                [
                    "| Handoff requirement | Available | Count | Source |",
                    "|---|---:|---:|---|",
                ]
            )
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
        gaps = warehouse.get("evidence_gaps")
        lines.append("- Evidence gaps:")
        if isinstance(gaps, list) and gaps:
            lines.extend(f"  - {_display(item)}" for item in gaps)
        else:
            lines.append("  - none")
        axes = warehouse.get("required_review_axes")
        if warehouse_current_run_evidence:
            lines.append("- Required warehouse review axes:")
        else:
            lines.append("- Deferred post-launch warehouse review axes:")
            lines.append(
                "  - not_actionable_before_launch_current_run_evidence_required"
            )
        if isinstance(axes, list) and axes:
            lines.extend(f"  - {_display(item)}" for item in axes)
        else:
            lines.append("  - none")

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
        ]
    )
    lines.extend(_minimum_delegated_analysis_lines(brief))
    lines.extend(["", "## Required Answers"])
    for index, question in enumerate(brief["required_questions"], start=1):
        lines.append(f"{index}. {question}")

    return "\n".join(lines) + "\n"


def _minimum_delegated_analysis_lines(brief: Mapping[str, Any]) -> list[str]:
    lifecycle = _mapping_or_empty(brief.get("lifecycle"))
    validity = _mapping_or_empty(brief.get("validity"))
    if lifecycle.get("prepared_only") is True:
        return [
            "- Inspect prepared_run_contract, launch_readiness, "
            "prompt_context_readiness, and problem-specific prepared handoff.",
            "- Confirm zero current-run counters and no postrun_acceptance evidence.",
            "- Do not analyze copied campaign artifacts as current-run research evidence.",
            "- If completion preflight failed, verify operator_action/login status "
            "and stop before launch.",
            "- Cite artifact paths, manifest commits, launch markers, or JSON fields "
            "for every conclusion.",
            "- Decide whether the next action is launch-readiness recheck or launch.",
        ]
    if validity.get("run_validity_status") == "invalid_infra_only":
        return [
            "- Stop after proving the infra-only status and failure classification.",
            "- Do not make algorithm-quality, plateau, or mechanism-effect conclusions.",
            "- Cite artifact paths, logs, status fields, or failure reports for every conclusion.",
            "- Decide whether the next action is infra repair or same-round rerun.",
        ]
    return [
        "- Start branch-centric, then round/LLM-call centric.",
        "- Cite artifact paths, branch ids, trace ids, SQL rows, or JSON fields for every conclusion.",
        "- Inspect target intent, hypothesis, code, tool calls, formal candidates, "
        "Protocol/Decision, branch lessons, runtime feedback, and source visibility.",
        "- Decide whether the next action is repair, same-round rerun, or ladder advancement.",
    ]


def _cvrp_large_twoopt_source_line(current_run_evidence: bool) -> str:
    if current_run_evidence:
        return (
            "- Source: prepared CVRP large-twoopt research_focus plus current-run "
            "protocol, measurement, runtime, and continuity summaries."
        )
    return (
        "- Source: prepared CVRP large-twoopt research_focus handoff; current-run "
        "protocol, measurement, runtime, and continuity summaries are absent before launch."
    )


def _warehouse_followup_source_line(current_run_evidence: bool) -> str:
    if current_run_evidence:
        return (
            "- Source: prepared warehouse research_focus plus current-run "
            "protocol, measurement, runtime, failure, and continuity summaries."
        )
    return (
        "- Source: prepared warehouse research_focus handoff; current-run protocol, "
        "measurement, runtime, failure, and continuity summaries are absent before launch."
    )


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


def _branch_research_state_summary(
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    phase4 = _mapping_or_empty(inventory.get("phase4_evidence_coverage"))
    current_run_evidence = phase4.get("current_run_evidence") is True
    branches = [
        dict(branch)
        for branch in inventory.get("branches") or []
        if isinstance(branch, Mapping)
    ]
    events = _mapping_or_empty(inventory.get("events"))
    hypotheses = _mapping_or_empty(inventory.get("hypotheses"))
    base = {
        "schema_version": "scion.postrun_branch_research_state_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "raw_prompts_excluded": True,
        "raw_responses_excluded": True,
        "patch_body_excluded": True,
        "current_run_evidence": current_run_evidence,
        "available": False,
        "aggregate": _empty_branch_research_state_aggregate(),
        "top_branches": [],
    }
    if not current_run_evidence:
        return base

    aggregate = _branch_research_state_aggregate(
        branches=branches,
        events=events,
        hypotheses=hypotheses,
    )
    return {
        **base,
        "available": bool(
            branches
            or _mapping_has_counts(events)
            or _int_or_zero(hypotheses.get("count")) > 0
        ),
        "aggregate": aggregate,
        "top_branches": _top_branch_summaries(branches),
    }


def _empty_branch_research_state_aggregate() -> dict[str, Any]:
    return {
        "branch_count": 0,
        "lineage_count": 0,
        "branch_state_counts": {},
        "branches_with_hypotheses": 0,
        "branches_with_events": 0,
        "branches_with_sessions": 0,
        "branches_with_traces": 0,
        "rollback_count_total": 0,
        "branches_with_rollback": 0,
        "failure_code_counts": {},
        "hypothesis_count": 0,
        "hypotheses_by_status": {},
        "hypotheses_by_action": {},
        "hypotheses_by_change_locus": {},
        "events_by_kind": {},
        "events_by_decision": {},
        "events_by_stage": {},
    }


def _branch_research_state_aggregate(
    *,
    branches: list[dict[str, Any]],
    events: Mapping[str, Any],
    hypotheses: Mapping[str, Any],
) -> dict[str, Any]:
    aggregate = _empty_branch_research_state_aggregate()
    aggregate["branch_count"] = len(branches)
    aggregate["lineage_count"] = len(
        {
            str(branch.get("lineage_id") or branch.get("branch_id") or "")
            for branch in branches
            if str(branch.get("lineage_id") or branch.get("branch_id") or "")
        }
    )
    for branch in branches:
        _increment_count(
            aggregate["branch_state_counts"],
            str(branch.get("state") or "unknown"),
        )
        if _int_or_zero(branch.get("hypothesis_count")) > 0:
            aggregate["branches_with_hypotheses"] += 1
        if _int_or_zero(branch.get("event_count")) > 0:
            aggregate["branches_with_events"] += 1
        if _int_or_zero(branch.get("session_count")) > 0:
            aggregate["branches_with_sessions"] += 1
        if _int_or_zero(branch.get("trace_count")) > 0:
            aggregate["branches_with_traces"] += 1
        rollback_count = _int_or_zero(branch.get("rollback_count"))
        aggregate["rollback_count_total"] += rollback_count
        if rollback_count > 0:
            aggregate["branches_with_rollback"] += 1
        for code in _string_items(branch.get("failure_codes")):
            _increment_count(aggregate["failure_code_counts"], code)

    aggregate["hypothesis_count"] = _int_or_zero(hypotheses.get("count"))
    aggregate["hypotheses_by_status"] = _int_mapping(
        hypotheses.get("by_status")
    )
    aggregate["hypotheses_by_action"] = _int_mapping(
        hypotheses.get("by_action")
    )
    aggregate["hypotheses_by_change_locus"] = _int_mapping(
        hypotheses.get("by_change_locus")
    )
    aggregate["events_by_kind"] = _int_mapping(events.get("by_kind"))
    aggregate["events_by_decision"] = _int_mapping(events.get("by_decision"))
    aggregate["events_by_stage"] = _int_mapping(events.get("by_stage"))
    return aggregate


def _mapping_has_counts(value: Mapping[str, Any]) -> bool:
    for item in value.values():
        if isinstance(item, Mapping) and any(
            _int_or_zero(count) for count in item.values()
        ):
            return True
    return False


def _top_branch_summaries(branches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(
        branches,
        key=lambda branch: (
            -_int_or_zero(branch.get("event_count")),
            -_int_or_zero(branch.get("hypothesis_count")),
            str(branch.get("branch_id") or ""),
        ),
    )
    return [_compact_branch_summary(branch) for branch in ordered[:10]]


def _compact_branch_summary(branch: Mapping[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "branch_id": branch.get("branch_id"),
            "state": branch.get("state"),
            "lineage_id": branch.get("lineage_id"),
            "hypothesis_count": branch.get("hypothesis_count"),
            "event_count": branch.get("event_count"),
            "session_count": branch.get("session_count"),
            "trace_count": branch.get("trace_count"),
            "rollback_count": branch.get("rollback_count"),
            "failure_codes": _string_items(branch.get("failure_codes")),
        }
    )


def _protocol_accounting_summary(
    run_root: Path,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    phase4 = _mapping_or_empty(inventory.get("phase4_evidence_coverage"))
    current_run_evidence = phase4.get("current_run_evidence") is True
    base = {
        "schema_version": "scion.postrun_protocol_accounting_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "current_run_evidence": current_run_evidence,
        "available": False,
        "report_count": 0,
        "accounting_report_count": 0,
        "aggregate": _empty_protocol_accounting_aggregate(),
        "entries": [],
    }
    if not current_run_evidence:
        return base

    report_paths = _research_efficiency_report_paths(run_root, inventory)
    entries: list[dict[str, Any]] = []
    aggregate = _empty_protocol_accounting_aggregate()
    for path in report_paths:
        entry = _protocol_accounting_entry(path)
        if not entry:
            continue
        entries.append(entry)
        _merge_protocol_accounting_aggregate(aggregate, entry)

    return {
        **base,
        "available": bool(entries),
        "report_count": len(report_paths),
        "accounting_report_count": len(entries),
        "aggregate": aggregate,
        "entries": entries,
    }


def _empty_protocol_accounting_aggregate() -> dict[str, Any]:
    return {
        "effective_budget": {
            "counter_counts": {},
            "requested_rounds": 0,
            "effective_rounds_completed": 0,
            "completed_requested_rounds_true": 0,
            "completed_requested_rounds_false": 0,
            "stopped_reason_counts": {},
        },
        "attempts": {
            "proposal_attempts_total": 0,
            "proposal_attempts_consumed": 0,
            "verification_consumed_candidates": 0,
            "verification_failure_consumed_candidates": 0,
        },
        "protocol_rows": {
            "effective_protocol_rounds": 0,
            "protocol_metric_results": 0,
            "protocol_evaluated_candidates": 0,
            "stage_counts": {},
        },
        "formal_screened_candidates": 0,
        "formal_protocol_evaluated_candidates": 0,
        "formal_candidate_artifacts": {
            "row_count": 0,
            "unreadable_rows": 0,
            "index_status_counts": {},
        },
        "stage_rows": {
            "screening": 0,
            "validation": 0,
            "frozen": 0,
            "fresh_runtime_replay": 0,
        },
        "reconciliation_status_counts": {},
    }


def _protocol_accounting_entry(path: Path) -> dict[str, Any]:
    doc = _read_json_object(path)
    effective_budget = _compact_effective_budget(
        _mapping_or_empty(doc.get("effective_budget"))
    )
    attempts = _compact_attempts(_mapping_or_empty(doc.get("attempts")))
    protocol_rows = _compact_protocol_rows(
        _mapping_or_empty(doc.get("protocol_rows"))
    )
    formal_candidates = _compact_formal_candidates(
        _mapping_or_empty(doc.get("formal_candidates"))
    )
    formal_artifacts = _compact_formal_candidate_artifacts(
        _mapping_or_empty(doc.get("formal_candidate_artifacts"))
    )
    stage_rows = _compact_stage_rows(_mapping_or_empty(doc.get("stage_rows")))
    reconciliation = _compact_reconciliation(
        _mapping_or_empty(doc.get("reconciliation"))
    )
    if not any(
        (
            effective_budget,
            attempts,
            protocol_rows,
            formal_candidates,
            formal_artifacts,
            stage_rows,
            reconciliation,
        )
    ):
        return {}
    return {
        "report": path.name,
        "path": str(path),
        "effective_budget": effective_budget,
        "attempts": attempts,
        "protocol_rows": protocol_rows,
        "formal_candidates": formal_candidates,
        "formal_candidate_artifacts": formal_artifacts,
        "stage_rows": stage_rows,
        "reconciliation": reconciliation,
    }


def _compact_effective_budget(raw: Mapping[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "counter": raw.get("counter"),
            "requested_rounds": raw.get("requested_rounds"),
            "effective_rounds_completed": raw.get("effective_rounds_completed"),
            "completed_requested_rounds": raw.get("completed_requested_rounds"),
            "stopped_reason": raw.get("stopped_reason"),
            "semantics": raw.get("semantics"),
        }
    )


def _compact_attempts(raw: Mapping[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "proposal_attempts_total": raw.get("proposal_attempts_total"),
            "proposal_attempts_consumed": raw.get("proposal_attempts_consumed"),
            "verification_consumed_candidates": raw.get(
                "verification_consumed_candidates"
            ),
            "verification_failure_consumed_candidates": raw.get(
                "verification_failure_consumed_candidates"
            ),
        }
    )


def _compact_protocol_rows(raw: Mapping[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "effective_protocol_rounds": raw.get("effective_protocol_rounds"),
            "protocol_metric_results": raw.get("protocol_metric_results"),
            "protocol_evaluated_candidates": raw.get(
                "protocol_evaluated_candidates"
            ),
            "stage_counts": _mapping_or_empty(raw.get("stage_counts")),
            "semantics": raw.get("semantics"),
        }
    )


def _compact_formal_candidates(raw: Mapping[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "formal_screened_candidates": raw.get("formal_screened_candidates"),
            "protocol_evaluated_candidates": raw.get(
                "protocol_evaluated_candidates"
            ),
            "semantics": raw.get("semantics"),
        }
    )


def _compact_formal_candidate_artifacts(raw: Mapping[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "row_count": raw.get("row_count"),
            "index_status": raw.get("index_status"),
            "index_ref": raw.get("index_ref"),
            "unreadable_rows": raw.get("unreadable_rows"),
            "semantics": raw.get("semantics"),
        }
    )


def _compact_stage_rows(raw: Mapping[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "screening": raw.get("screening"),
            "validation": raw.get("validation"),
            "frozen": raw.get("frozen"),
            "fresh_runtime_replay": raw.get("fresh_runtime_replay"),
        }
    )


def _compact_reconciliation(raw: Mapping[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key in (
        "formal_candidate_count_reconciliation",
        "candidate_count_reconciliation",
        "accounting_reconciliation",
    ):
        value = raw.get(key)
        if isinstance(value, Mapping):
            compact[key] = _mapping_or_empty(value)
    return compact


def _merge_protocol_accounting_aggregate(
    aggregate: dict[str, Any],
    entry: Mapping[str, Any],
) -> None:
    effective_budget = _mapping_or_empty(entry.get("effective_budget"))
    effective_target = aggregate["effective_budget"]
    _increment_count(
        effective_target["counter_counts"],
        str(effective_budget.get("counter") or "unknown"),
    )
    effective_target["requested_rounds"] += _int_or_zero(
        effective_budget.get("requested_rounds")
    )
    effective_target["effective_rounds_completed"] += _int_or_zero(
        effective_budget.get("effective_rounds_completed")
    )
    if effective_budget.get("completed_requested_rounds") is True:
        effective_target["completed_requested_rounds_true"] += 1
    elif effective_budget.get("completed_requested_rounds") is False:
        effective_target["completed_requested_rounds_false"] += 1
    _increment_count(
        effective_target["stopped_reason_counts"],
        str(effective_budget.get("stopped_reason") or "unknown"),
    )

    attempts = _mapping_or_empty(entry.get("attempts"))
    for key in aggregate["attempts"]:
        aggregate["attempts"][key] += _int_or_zero(attempts.get(key))

    protocol_rows = _mapping_or_empty(entry.get("protocol_rows"))
    for key in (
        "effective_protocol_rounds",
        "protocol_metric_results",
        "protocol_evaluated_candidates",
    ):
        aggregate["protocol_rows"][key] += _int_or_zero(protocol_rows.get(key))
    stage_counts = protocol_rows.get("stage_counts")
    if isinstance(stage_counts, Mapping):
        for stage, count in sorted(stage_counts.items()):
            _increment_count(
                aggregate["protocol_rows"]["stage_counts"],
                str(stage),
                _int_or_zero(count),
            )

    formal_candidates = _mapping_or_empty(entry.get("formal_candidates"))
    aggregate["formal_screened_candidates"] += _int_or_zero(
        formal_candidates.get("formal_screened_candidates")
    )
    aggregate["formal_protocol_evaluated_candidates"] += _int_or_zero(
        formal_candidates.get("protocol_evaluated_candidates")
    )

    formal_artifacts = _mapping_or_empty(entry.get("formal_candidate_artifacts"))
    artifact_target = aggregate["formal_candidate_artifacts"]
    artifact_target["row_count"] += _int_or_zero(formal_artifacts.get("row_count"))
    artifact_target["unreadable_rows"] += _int_or_zero(
        formal_artifacts.get("unreadable_rows")
    )
    _increment_count(
        artifact_target["index_status_counts"],
        str(formal_artifacts.get("index_status") or "unknown"),
    )

    stage_rows = _mapping_or_empty(entry.get("stage_rows"))
    for key in aggregate["stage_rows"]:
        aggregate["stage_rows"][key] += _int_or_zero(stage_rows.get(key))

    reconciliation = _mapping_or_empty(entry.get("reconciliation"))
    for status in _reconciliation_statuses(reconciliation):
        _increment_count(aggregate["reconciliation_status_counts"], status)


def _reconciliation_statuses(reconciliation: Mapping[str, Any]) -> list[str]:
    statuses: list[str] = []
    for value in reconciliation.values():
        if not isinstance(value, Mapping):
            continue
        for key, item in value.items():
            normalized = str(key).lower()
            if "status" in normalized and item not in (None, "", [], {}):
                statuses.append(str(item))
    return statuses


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
        "mechanism_family_mapped_row_count": 0,
        "mechanism_family_unmapped_row_count": 0,
        "mechanism_family_effects": {},
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
            "mechanism_family_effect_summary": (
                _compact_mechanism_family_effect_summary(
                    _mapping_or_empty(effect.get("mechanism_family_effect_summary"))
                )
            ),
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
            "mechanism_family": row.get("mechanism_family"),
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


def _compact_mechanism_family_effect_summary(
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    if not summary:
        return {}
    by_family: dict[str, Any] = {}
    raw_by_family = summary.get("by_family")
    if isinstance(raw_by_family, Mapping):
        for family, payload in sorted(raw_by_family.items()):
            if not isinstance(payload, Mapping):
                continue
            by_family[str(family)] = _compact_effect_count_summary(payload)
    return _drop_empty(
        {
            "schema_version": summary.get("schema_version"),
            "report_only": summary.get("report_only"),
            "decision_features_excluded": summary.get(
                "decision_features_excluded"
            ),
            "mapping_status": summary.get("mapping_status"),
            "mapped_row_count": summary.get("mapped_row_count"),
            "unmapped_row_count": summary.get("unmapped_row_count"),
            "mechanism_family_count": summary.get("mechanism_family_count"),
            "by_family": by_family,
        }
    )


def _compact_effect_count_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "protocol_row_count": summary.get("protocol_row_count"),
            "rows_with_median_delta": summary.get("rows_with_median_delta"),
            "positive_rows": summary.get("positive_rows"),
            "nonpositive_rows": summary.get("nonpositive_rows"),
            "rows_at_or_above_mde": summary.get("rows_at_or_above_mde"),
            "rows_below_mde": summary.get("rows_below_mde"),
            "rows_with_ci_high_below_mde": summary.get(
                "rows_with_ci_high_below_mde"
            ),
            "max_median_delta": summary.get("max_median_delta"),
            "max_effect_to_mde_ratio": summary.get("max_effect_to_mde_ratio"),
        }
    )


def _empty_effect_count_summary() -> dict[str, Any]:
    return {
        "protocol_row_count": 0,
        "rows_with_median_delta": 0,
        "positive_rows": 0,
        "nonpositive_rows": 0,
        "rows_at_or_above_mde": 0,
        "rows_below_mde": 0,
        "rows_with_ci_high_below_mde": 0,
        "max_median_delta": None,
        "max_effect_to_mde_ratio": None,
    }


def _merge_effect_count_summary(
    target: dict[str, Any],
    source: Mapping[str, Any],
) -> None:
    for key in (
        "protocol_row_count",
        "rows_with_median_delta",
        "positive_rows",
        "nonpositive_rows",
        "rows_at_or_above_mde",
        "rows_below_mde",
        "rows_with_ci_high_below_mde",
    ):
        target[key] = _int_or_zero(target.get(key)) + _int_or_zero(source.get(key))
    for key in ("max_median_delta", "max_effect_to_mde_ratio"):
        current = _float_or_none(target.get(key))
        value = _float_or_none(source.get(key))
        if value is not None and (current is None or value > current):
            target[key] = value


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
    family_summary = _mapping_or_empty(effect.get("mechanism_family_effect_summary"))
    aggregate["mechanism_family_mapped_row_count"] = _int_or_zero(
        aggregate.get("mechanism_family_mapped_row_count")
    ) + _int_or_zero(family_summary.get("mapped_row_count"))
    aggregate["mechanism_family_unmapped_row_count"] = _int_or_zero(
        aggregate.get("mechanism_family_unmapped_row_count")
    ) + _int_or_zero(family_summary.get("unmapped_row_count"))
    by_family = _mapping_or_empty(family_summary.get("by_family"))
    for family, payload in sorted(by_family.items()):
        if not isinstance(payload, Mapping):
            continue
        target = aggregate["mechanism_family_effects"].setdefault(
            str(family),
            _empty_effect_count_summary(),
        )
        _merge_effect_count_summary(target, payload)


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
        "source_visibility": _empty_prompt_source_visibility_aggregate(),
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
        "source_visibility": _empty_prompt_source_visibility_aggregate(),
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
    _add_prompt_source_visibility(
        entry["source_visibility"],
        trace.get("source_visibility_summary"),
    )

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
    _merge_prompt_source_visibility(
        aggregate["source_visibility"],
        _mapping_or_empty(entry.get("source_visibility")),
    )
    families = entry.get("block_family_totals")
    if isinstance(families, Mapping):
        for family, raw in sorted(families.items()):
            if isinstance(raw, Mapping):
                _add_block_family(aggregate["block_family_totals"], str(family), raw)


def _with_prompt_signal_density(aggregate: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(aggregate)
    if not _prompt_source_visibility_has_counts(
        _mapping_or_empty(enriched.get("source_visibility"))
    ):
        enriched["source_visibility"] = {}
    enriched["signal_density"] = _prompt_signal_density(
        _mapping_or_empty(enriched.get("block_family_totals"))
    )
    return enriched


def _empty_prompt_source_visibility_aggregate() -> dict[str, Any]:
    return {
        "schema_version": "scion.postrun_prompt_source_visibility_summary.v1",
        "report_only": True,
        "decision_features_excluded": True,
        "trace_count": 0,
        "code_trace_count": 0,
        "code_target_source_visible_count": 0,
        "code_target_source_missing_count": 0,
        "code_protected_source_visible_count": 0,
        "code_protected_source_missing_count": 0,
        "code_required_integration_source_visible_count": 0,
        "code_algorithm_file_read_source_visible_count": 0,
        "code_missing_required_source_trace_count": 0,
        "code_missing_required_source_path_counts": {},
        "code_target_source_status_counts": {},
        "code_target_visibility_status_counts": {},
        "hypothesis_target_source_trace_count": 0,
        "hypothesis_target_source_required_count": 0,
        "hypothesis_target_source_visible_count": 0,
        "hypothesis_target_source_not_visible_count": 0,
        "hypothesis_target_visibility_status_counts": {},
    }


def _add_prompt_source_visibility(
    target: dict[str, Any],
    raw_summary: Any,
) -> None:
    summary = _mapping_or_empty(raw_summary)
    if not summary:
        return
    target["trace_count"] += 1

    code_guarantees = _mapping_or_empty(summary.get("code_phase_guarantees"))
    code_visibility = _mapping_or_empty(summary.get("code_file_visibility"))
    if code_guarantees or code_visibility:
        target["code_trace_count"] += 1
        if code_guarantees.get("target_source_visible") is True:
            target["code_target_source_visible_count"] += 1
        elif code_guarantees.get("target_source_visible") is False:
            target["code_target_source_missing_count"] += 1
        if code_guarantees.get("protected_source_visible") is True:
            target["code_protected_source_visible_count"] += 1
        elif code_guarantees.get("protected_source_visible") is False:
            target["code_protected_source_missing_count"] += 1
        if code_guarantees.get("required_integration_source_visible") is True:
            target["code_required_integration_source_visible_count"] += 1
        if code_guarantees.get("algorithm_file_read_source_visible") is True:
            target["code_algorithm_file_read_source_visible_count"] += 1
        missing_paths = _string_items(
            code_guarantees.get("missing_required_source_paths")
        )
        if missing_paths:
            target["code_missing_required_source_trace_count"] += 1
        for path in missing_paths:
            _increment_count(target["code_missing_required_source_path_counts"], path)
        _increment_count(
            target["code_target_source_status_counts"],
            str(code_visibility.get("target_source_status") or "unknown"),
        )
        _increment_count(
            target["code_target_visibility_status_counts"],
            str(code_visibility.get("target_prompt_visibility_status") or "unknown"),
        )

    hypothesis_visibility = _mapping_or_empty(
        summary.get("hypothesis_target_source_visibility")
    )
    if hypothesis_visibility:
        target["hypothesis_target_source_trace_count"] += 1
        if hypothesis_visibility.get("target_source_required") is True:
            target["hypothesis_target_source_required_count"] += 1
        status = str(hypothesis_visibility.get("visibility_status") or "unknown")
        _increment_count(
            target["hypothesis_target_visibility_status_counts"],
            status,
        )
        visible = (
            hypothesis_visibility.get("owner_source_visible") is True
            or hypothesis_visibility.get("placeholder_visible") is True
            or status not in {"not_visible", "unknown"}
        )
        if visible:
            target["hypothesis_target_source_visible_count"] += 1
        else:
            target["hypothesis_target_source_not_visible_count"] += 1


def _merge_prompt_source_visibility(
    target: dict[str, Any],
    source: Mapping[str, Any],
) -> None:
    if not source:
        return
    for key in (
        "trace_count",
        "code_trace_count",
        "code_target_source_visible_count",
        "code_target_source_missing_count",
        "code_protected_source_visible_count",
        "code_protected_source_missing_count",
        "code_required_integration_source_visible_count",
        "code_algorithm_file_read_source_visible_count",
        "code_missing_required_source_trace_count",
        "hypothesis_target_source_trace_count",
        "hypothesis_target_source_required_count",
        "hypothesis_target_source_visible_count",
        "hypothesis_target_source_not_visible_count",
    ):
        target[key] = _int_or_zero(target.get(key)) + _int_or_zero(source.get(key))
    for key in (
        "code_missing_required_source_path_counts",
        "code_target_source_status_counts",
        "code_target_visibility_status_counts",
        "hypothesis_target_visibility_status_counts",
    ):
        target_counts = target[key]
        source_counts = source.get(key)
        if not isinstance(source_counts, Mapping):
            continue
        for item_key, value in sorted(source_counts.items()):
            _increment_count(target_counts, str(item_key), _int_or_zero(value))


def _prompt_source_visibility_has_counts(source_visibility: Mapping[str, Any]) -> bool:
    return _int_or_zero(source_visibility.get("trace_count")) > 0


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
        "aggregate": _empty_research_continuity_aggregate(),
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
                "research_shape": _mapping_or_empty(doc.get("research_shape")),
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

    aggregate = _empty_research_continuity_aggregate()
    for entry in entries:
        _merge_research_continuity_aggregate(aggregate, entry)
    return {
        **base,
        "available": bool(entries),
        "report_count": len(report_paths),
        "continuity_report_count": len(entries),
        "aggregate": aggregate,
        "entries": entries,
    }


def _empty_research_continuity_aggregate() -> dict[str, Any]:
    return {
        "max_branch_depth": 0,
        "mean_branch_depth_max": None,
        "branch_depth_distribution": {},
        "active_shape_counts": {},
        "active_branch_count_max": 0,
        "active_mechanism_family_count_max": 0,
        "mechanism_family_count_max": 0,
        "mechanism_family_counts": {},
        "branch_lesson_semantic_failure_counts": {},
        "branch_lesson_semantic_block_counts": {},
        "lesson_action_counts": {},
    }


def _merge_research_continuity_aggregate(
    aggregate: dict[str, Any],
    entry: Mapping[str, Any],
) -> None:
    shape = _mapping_or_empty(entry.get("research_shape_summary"))
    full_shape = _mapping_or_empty(entry.get("research_shape"))
    aggregate["max_branch_depth"] = max(
        _int_or_zero(aggregate.get("max_branch_depth")),
        _int_or_zero(shape.get("max_branch_depth")),
        _int_or_zero(full_shape.get("max_branch_depth")),
    )
    mean_depth = _float_or_none(
        shape.get("mean_branch_depth") or full_shape.get("mean_branch_depth")
    )
    current_mean = _float_or_none(aggregate.get("mean_branch_depth_max"))
    if mean_depth is not None and (current_mean is None or mean_depth > current_mean):
        aggregate["mean_branch_depth_max"] = mean_depth

    depth_distribution = (
        _mapping_or_empty(shape.get("branch_depth_distribution"))
        or _mapping_or_empty(full_shape.get("branch_depth_distribution"))
    )
    for depth, count in sorted(depth_distribution.items()):
        _increment_count(
            aggregate["branch_depth_distribution"],
            str(depth),
            _int_or_zero(count),
        )

    active_shape = str(
        shape.get("active_shape")
        or _mapping_or_empty(full_shape.get("active_research_shape_signal")).get(
            "shape"
        )
        or ""
    )
    if active_shape:
        _increment_count(aggregate["active_shape_counts"], active_shape)
    active_shape_summary = _mapping_or_empty(
        full_shape.get("active_research_shape_signal")
    )
    aggregate["active_branch_count_max"] = max(
        _int_or_zero(aggregate.get("active_branch_count_max")),
        _int_or_zero(shape.get("active_branch_count")),
        _int_or_zero(active_shape_summary.get("active_branch_count")),
    )
    aggregate["active_mechanism_family_count_max"] = max(
        _int_or_zero(aggregate.get("active_mechanism_family_count_max")),
        _int_or_zero(shape.get("active_mechanism_family_count")),
        _int_or_zero(active_shape_summary.get("active_mechanism_family_count")),
    )

    mechanism_breadth = _mapping_or_empty(full_shape.get("mechanism_family_breadth"))
    aggregate["mechanism_family_count_max"] = max(
        _int_or_zero(aggregate.get("mechanism_family_count_max")),
        _int_or_zero(shape.get("mechanism_family_count")),
        _int_or_zero(mechanism_breadth.get("family_count")),
    )
    families = _mapping_or_empty(mechanism_breadth.get("families"))
    for family, count in sorted(families.items()):
        _increment_count(
            aggregate["mechanism_family_counts"],
            str(family),
            _int_or_zero(count),
        )
    lessons = _mapping_or_empty(entry.get("branch_lesson_usage"))
    for key, count in sorted(
        _mapping_or_empty(lessons.get("semantic_failure_counts")).items()
    ):
        _increment_count(
            aggregate["branch_lesson_semantic_failure_counts"],
            str(key),
            _int_or_zero(count),
        )
    for key, count in sorted(
        _mapping_or_empty(lessons.get("semantic_block_counts")).items()
    ):
        _increment_count(
            aggregate["branch_lesson_semantic_block_counts"],
            str(key),
            _int_or_zero(count),
        )
    actions = _mapping_or_empty(entry.get("lesson_action_counts"))
    for key, count in sorted(actions.items()):
        _increment_count(
            aggregate["lesson_action_counts"],
            str(key),
            _int_or_zero(count),
        )


def _research_context_actionability_summary(
    *,
    prompt_context_visibility_summary: Mapping[str, Any],
    research_continuity_summary: Mapping[str, Any],
) -> dict[str, Any]:
    prompt_current = prompt_context_visibility_summary.get("current_run_evidence") is True
    continuity_current = research_continuity_summary.get("current_run_evidence") is True
    prompt_available = prompt_context_visibility_summary.get("available") is True
    continuity_available = research_continuity_summary.get("available") is True
    prompt_aggregate = _mapping_or_empty(
        prompt_context_visibility_summary.get("aggregate")
    )
    continuity_aggregate = _mapping_or_empty(
        research_continuity_summary.get("aggregate")
    )
    continuity_counts = _research_continuity_action_counts(
        research_continuity_summary.get("entries")
    )
    semantic_failure_counts = _int_mapping(
        continuity_aggregate.get("branch_lesson_semantic_failure_counts")
    )
    semantic_block_counts = _int_mapping(
        continuity_aggregate.get("branch_lesson_semantic_block_counts")
    )
    density = _mapping_or_empty(prompt_aggregate.get("signal_density"))
    indicators = {
        "schema_version": "scion.research_context_actionability_indicators.v1",
        "same_mechanism_selected": continuity_counts["same_mechanism_selected"],
        "same_mechanism_observed": continuity_counts["same_mechanism_observed"],
        "same_mechanism_missed": max(
            0,
            continuity_counts["same_mechanism_observed"]
            - continuity_counts["same_mechanism_selected"],
        ),
        "branch_lessons_satisfied": continuity_counts["branch_lessons_satisfied"],
        "branch_lessons_required": continuity_counts["branch_lessons_required"],
        "branch_lesson_semantic_gap_count": continuity_counts[
            "branch_lesson_semantic_gap_count"
        ],
        "branch_lesson_semantic_failure_count": _sum_counts(
            semantic_failure_counts
        ),
        "branch_lesson_semantic_failure_counts": semantic_failure_counts,
        "branch_lesson_semantic_block_count": _sum_counts(semantic_block_counts),
        "branch_lesson_semantic_block_counts": semantic_block_counts,
        "weak_positive_accepted": continuity_counts["weak_positive_accepted"],
        "weak_positive_observed": continuity_counts["weak_positive_observed"],
        "weak_positive_missed": max(
            0,
            continuity_counts["weak_positive_observed"]
            - continuity_counts["weak_positive_accepted"],
        ),
        "research_signal_tokens": _int_or_zero(
            density.get("research_signal_tokens")
        ),
        "source_code_tokens": _int_or_zero(density.get("source_code_tokens")),
        "cross_branch_tokens": _int_or_zero(density.get("cross_branch_tokens")),
        "governance_tokens": _int_or_zero(density.get("governance_tokens")),
        "research_plus_source_to_governance_ratio": density.get(
            "research_plus_source_to_governance_ratio"
        ),
        "omitted_section_trace_count": _int_or_zero(
            prompt_aggregate.get("omitted_section_trace_count")
        ),
        "truncated_section_trace_count": _int_or_zero(
            prompt_aggregate.get("truncated_section_trace_count")
        ),
    }
    actionability_gaps = _research_context_actionability_gaps(
        indicators=indicators,
        prompt_current=prompt_current,
        prompt_available=prompt_available,
        continuity_current=continuity_current,
        continuity_available=continuity_available,
    )
    return {
        "schema_version": "scion.postrun_research_context_actionability_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "current_run_evidence": prompt_current and continuity_current,
        "available": prompt_available or continuity_available,
        "prompt_context_available": prompt_available,
        "research_continuity_available": continuity_available,
        "guidance_status": _research_context_guidance_status(
            actionability_gaps,
            indicators=indicators,
            prompt_available=prompt_available,
            continuity_available=continuity_available,
        ),
        "indicators": indicators,
        "actionability_gaps": actionability_gaps,
        "recommendations": _research_context_actionability_recommendations(
            actionability_gaps,
            indicators=indicators,
        ),
    }


def _research_continuity_action_counts(entries: Any) -> dict[str, int]:
    counts = {
        "same_mechanism_selected": 0,
        "same_mechanism_observed": 0,
        "branch_lessons_satisfied": 0,
        "branch_lessons_required": 0,
        "branch_lesson_semantic_gap_count": 0,
        "weak_positive_accepted": 0,
        "weak_positive_observed": 0,
    }
    if not isinstance(entries, list):
        return counts
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        same_mechanism = _mapping_or_empty(entry.get("same_mechanism_followup"))
        lessons = _mapping_or_empty(entry.get("branch_lesson_usage"))
        transfer = _mapping_or_empty(entry.get("weak_positive_transfer"))
        counts["same_mechanism_selected"] += _int_or_zero(
            same_mechanism.get("selected_same_branch_refinement_count")
        )
        counts["same_mechanism_observed"] += _int_or_zero(
            same_mechanism.get("observed_opportunity_count")
        )
        counts["branch_lessons_satisfied"] += _int_or_zero(
            lessons.get("satisfied_count")
        )
        counts["branch_lessons_required"] += _int_or_zero(
            lessons.get("requirement_count")
        )
        counts["branch_lesson_semantic_gap_count"] += _int_or_zero(
            lessons.get("semantic_gap_count")
        )
        counts["weak_positive_accepted"] += _int_or_zero(
            transfer.get("accepted_count")
        )
        counts["weak_positive_observed"] += _int_or_zero(
            transfer.get("observed_opportunity_count")
        )
    return counts


def _research_context_actionability_gaps(
    *,
    indicators: Mapping[str, Any],
    prompt_current: bool,
    prompt_available: bool,
    continuity_current: bool,
    continuity_available: bool,
) -> list[str]:
    gaps: list[str] = []
    if not (prompt_current or continuity_current):
        return ["no_current_run_prompt_or_continuity_evidence"]
    if continuity_current and continuity_available and not prompt_available:
        gaps.append("research_continuity_available_without_prompt_context_evidence")
    if prompt_current and prompt_available and not continuity_available:
        gaps.append("prompt_context_available_without_research_continuity_evidence")

    semantic_gap = _int_or_zero(indicators.get("branch_lesson_semantic_gap_count"))
    semantic_failures = _int_or_zero(
        indicators.get("branch_lesson_semantic_failure_count")
    )
    semantic_blocks = _int_or_zero(
        indicators.get("branch_lesson_semantic_block_count")
    )
    cross_branch_tokens = _int_or_zero(indicators.get("cross_branch_tokens"))
    research_tokens = _int_or_zero(indicators.get("research_signal_tokens"))
    source_tokens = _int_or_zero(indicators.get("source_code_tokens"))
    governance_tokens = _int_or_zero(indicators.get("governance_tokens"))
    research_plus_source = research_tokens + source_tokens

    if semantic_gap > 0 and cross_branch_tokens <= 0:
        gaps.append("branch_lesson_semantic_gap_without_cross_branch_prompt_signal")
    elif semantic_failures > 0 or semantic_blocks > 0:
        gaps.append("branch_lesson_semantic_gap_despite_cross_branch_prompt_signal")

    if (
        _int_or_zero(indicators.get("same_mechanism_missed")) > 0
        and research_tokens <= 0
    ):
        gaps.append("same_mechanism_opportunities_without_research_signal_prompt")
    if (
        _int_or_zero(indicators.get("weak_positive_missed")) > 0
        and research_tokens + cross_branch_tokens <= 0
    ):
        gaps.append("weak_positive_transfer_without_research_or_lesson_signal")
    if (
        semantic_gap > 0
        and (
            _int_or_zero(indicators.get("omitted_section_trace_count")) > 0
            or _int_or_zero(indicators.get("truncated_section_trace_count")) > 0
        )
    ):
        gaps.append("research_signal_sections_omitted_or_truncated_during_semantic_gap")
    if governance_tokens > research_plus_source and (
        semantic_gap > 0
        or _int_or_zero(indicators.get("same_mechanism_missed")) > 0
        or _int_or_zero(indicators.get("weak_positive_missed")) > 0
    ):
        gaps.append("governance_tokens_dominate_during_research_continuity_gap")
    return list(dict.fromkeys(gaps))


def _research_context_guidance_status(
    gaps: list[str],
    *,
    indicators: Mapping[str, Any],
    prompt_available: bool,
    continuity_available: bool,
) -> str:
    if not prompt_available and not continuity_available:
        return "no_prompt_or_continuity_actionability_evidence"
    if gaps:
        return "context_actionability_review_required"
    if (
        _int_or_zero(indicators.get("same_mechanism_observed")) > 0
        or _int_or_zero(indicators.get("branch_lessons_required")) > 0
        or _int_or_zero(indicators.get("weak_positive_observed")) > 0
    ):
        return "continuity_signals_context_actionable"
    return "no_continuity_opportunities_observed"


def _research_context_actionability_recommendations(
    gaps: list[str],
    *,
    indicators: Mapping[str, Any],
) -> list[str]:
    recommendations: list[str] = []
    for gap in gaps:
        if "without_cross_branch_prompt_signal" in gap:
            recommendations.append(
                "inspect prompt manifests for missing cross_branch_lesson blocks"
            )
        elif "despite_cross_branch_prompt_signal" in gap:
            recommendations.append(
                "inspect branch_lesson_usage records for semantic mismatch causes"
            )
        elif "same_mechanism" in gap:
            recommendations.append(
                "inspect branch-local research_signal blocks before judging churn"
            )
        elif "weak_positive" in gap:
            recommendations.append(
                "inspect research_signal and cross_branch_lesson blocks before judging transfer"
            )
        elif "omitted_or_truncated" in gap:
            recommendations.append(
                "inspect omitted_sections and truncated_sections in prompt manifests"
            )
        elif "governance_tokens_dominate" in gap:
            recommendations.append(
                "inspect signal density before adding more governance text"
            )
        elif "without_prompt_context" in gap:
            recommendations.append(
                "rebuild postrun proposal trajectory manifests before delegated review"
            )
        elif "without_research_continuity" in gap:
            recommendations.append(
                "rebuild research-efficiency reports before delegated review"
            )
        elif "no_current_run" in gap:
            recommendations.append(
                "launch or rebuild current-run evidence before research-quality conclusions"
            )
    semantic_reasons = _int_mapping(
        indicators.get("branch_lesson_semantic_failure_counts")
    )
    semantic_blocks = _int_mapping(
        indicators.get("branch_lesson_semantic_block_counts")
    )
    reason_keys = set(semantic_reasons) | set(semantic_blocks)
    if "metadata_only" in reason_keys:
        recommendations.append(
            "inspect hypotheses that filled branch_lesson_usage with metadata-only payloads"
        )
    if "linkage_unrecognized" in reason_keys:
        recommendations.append(
            "normalize branch_lesson_usage target/action/mechanism linkage aliases"
        )
    if "semantic_mismatch" in reason_keys:
        recommendations.append(
            "inspect lesson ids, changed dimensions, and borrow/contrast/reject semantics"
        )
    return list(dict.fromkeys(recommendations))


def _cvrp_large_twoopt_summary(
    inventory: Mapping[str, Any],
    *,
    protocol_accounting_summary: Mapping[str, Any],
    measurement_effect_summary: Mapping[str, Any],
    runtime_feedback_summary: Mapping[str, Any],
    failure_taxonomy_summary: Mapping[str, Any],
    research_continuity_summary: Mapping[str, Any],
) -> dict[str, Any]:
    phase4 = _mapping_or_empty(inventory.get("phase4_evidence_coverage"))
    launcher = _mapping_or_empty(inventory.get("launcher"))
    contract = _mapping_or_empty(launcher.get("prepared_run_contract"))
    problem_family = contract.get("problem_family")
    current_run_evidence = phase4.get("current_run_evidence") is True
    base = {
        "schema_version": "scion.postrun_cvrp_large_twoopt_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
        "problem_family": problem_family,
        "current_run_evidence": current_run_evidence,
        "available": False,
        "handoff_complete": False,
        "handoff_requirements": {},
        "launch_required_before_twoopt_conclusion": False,
        "interpretation": "not_cvrp",
        "evidence": {},
        "evidence_gaps": [],
        "required_review_axes": list(CVRP_LARGE_TWOOPT_REVIEW_AXES),
        "deferred_review_axes": [],
        "review_axes_actionability": "not_applicable",
    }
    if problem_family != "cvrp":
        return base

    handoff_requirements = _cvrp_large_twoopt_handoff_requirements(
        phase4=phase4,
        contract=contract,
    )
    handoff_complete = bool(handoff_requirements) and all(
        item.get("available") is True for item in handoff_requirements.values()
    )
    counters = _mapping_or_empty(inventory.get("counters"))
    accounting = _mapping_or_empty(protocol_accounting_summary.get("aggregate"))
    protocol_rows = _mapping_or_empty(accounting.get("protocol_rows"))
    formal_artifacts = _mapping_or_empty(
        accounting.get("formal_candidate_artifacts")
    )
    formal_screened_candidates = max(
        _int_or_zero(accounting.get("formal_screened_candidates")),
        _int_or_zero(counters.get("formal_screened_candidates")),
        _int_or_zero(counters.get("screened_experiments")),
    )
    protocol_evaluated_candidates = max(
        _int_or_zero(protocol_rows.get("protocol_evaluated_candidates")),
        _int_or_zero(accounting.get("formal_protocol_evaluated_candidates")),
        _int_or_zero(counters.get("protocol_evaluated_candidates")),
    )
    measurement = _mapping_or_empty(measurement_effect_summary.get("aggregate"))
    runtime = _mapping_or_empty(runtime_feedback_summary.get("aggregate"))
    runtime_budget = _mapping_or_empty(runtime.get("runtime_budget_diagnostics"))
    failure = _mapping_or_empty(failure_taxonomy_summary.get("aggregate"))
    proposal_quality = _mapping_or_empty(failure.get("proposal_quality"))
    quality_block_signal = max(
        _int_or_zero(proposal_quality.get("proposal_quality_blocks")),
        _int_or_zero(proposal_quality.get("quality_blocks")),
        _int_or_zero(proposal_quality.get("quality_block_ledger_count")),
    )
    large_twoopt_mechanism = _cvrp_large_twoopt_mechanism_signal(
        measurement_effect_summary=measurement_effect_summary,
        research_continuity_summary=research_continuity_summary,
    )
    measurement_available = measurement_effect_summary.get("available") is True
    runtime_available = runtime_feedback_summary.get("available") is True
    continuity_available = research_continuity_summary.get("available") is True
    large_twoopt_available = large_twoopt_mechanism.get("available") is True
    evidence = {
        "protocol": {
            "formal_screened_candidates": formal_screened_candidates,
            "protocol_evaluated_candidates": protocol_evaluated_candidates,
            "protocol_metric_results": _int_or_zero(
                protocol_rows.get("protocol_metric_results")
            ),
            "formal_candidate_artifact_rows": _int_or_zero(
                formal_artifacts.get("row_count")
            ),
            "stage_rows": _mapping_or_empty(accounting.get("stage_rows")),
        },
        "measurement_effect": {
            "available": measurement_available,
            "protocol_row_count": _int_or_zero(
                measurement.get("protocol_row_count")
            ),
            "rows_at_or_above_mde": _int_or_zero(
                measurement.get("rows_at_or_above_mde")
            ),
            "rows_with_ci_high_below_mde": _int_or_zero(
                measurement.get("rows_with_ci_high_below_mde")
            ),
            "max_effect_to_mde_ratio": measurement.get("max_effect_to_mde_ratio"),
            "interpretation_counts": _int_mapping(
                measurement.get("interpretation_counts")
            ),
            "mechanism_family_mapped_row_count": _int_or_zero(
                measurement.get("mechanism_family_mapped_row_count")
            ),
            "mechanism_family_unmapped_row_count": _int_or_zero(
                measurement.get("mechanism_family_unmapped_row_count")
            ),
        },
        "large_twoopt_mechanism": large_twoopt_mechanism,
        "quality_blocks": {
            "proposal_quality_blocks": _int_or_zero(
                proposal_quality.get("proposal_quality_blocks")
            ),
            "quality_blocks": _int_or_zero(proposal_quality.get("quality_blocks")),
            "quality_block_ledger_count": _int_or_zero(
                proposal_quality.get("quality_block_ledger_count")
            ),
            "reason_counts": _int_mapping(
                proposal_quality.get("quality_block_reason_counts")
            ),
        },
        "runtime": {
            "available": runtime_available,
            "runtime_model_counts": _int_mapping(
                runtime_budget.get("runtime_model_counts")
            ),
            "runtime_budget_diagnostic_count": _int_or_zero(
                runtime_budget.get("diagnostic_count")
            ),
        },
        "research_continuity": {
            "available": continuity_available,
            "continuity_report_count": _int_or_zero(
                research_continuity_summary.get("continuity_report_count")
            ),
        },
    }
    interpretation = _cvrp_large_twoopt_interpretation(
        current_run_evidence=current_run_evidence,
        handoff_complete=handoff_complete,
        protocol_evaluated_candidates=protocol_evaluated_candidates,
        formal_screened_candidates=formal_screened_candidates,
        quality_block_signal=quality_block_signal,
        measurement_available=measurement_available,
        runtime_available=runtime_available,
        continuity_available=continuity_available,
        large_twoopt_available=large_twoopt_available,
    )
    return {
        **base,
        "available": True,
        "handoff_complete": handoff_complete,
        "handoff_requirements": handoff_requirements,
        "launch_required_before_twoopt_conclusion": not current_run_evidence,
        "interpretation": interpretation,
        "evidence": evidence,
        "evidence_gaps": _cvrp_large_twoopt_evidence_gaps(
            current_run_evidence=current_run_evidence,
            handoff_complete=handoff_complete,
            protocol_evaluated_candidates=protocol_evaluated_candidates,
            quality_block_signal=quality_block_signal,
            measurement_available=measurement_available,
            runtime_available=runtime_available,
            continuity_available=continuity_available,
            large_twoopt_available=large_twoopt_available,
        ),
        "deferred_review_axes": (
            list(CVRP_LARGE_TWOOPT_REVIEW_AXES)
            if not current_run_evidence
            else []
        ),
        "review_axes_actionability": (
            "not_actionable_before_launch_current_run_evidence_required"
            if not current_run_evidence
            else "actionable_current_run_evidence_present"
        ),
    }


def _cvrp_large_twoopt_handoff_requirements(
    *,
    phase4: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    problem_specific = _mapping_or_empty(phase4.get("problem_specific_requirements"))
    checks = _mapping_or_empty(contract.get("checks"))
    requirements: dict[str, Any] = {}
    for key in CVRP_LARGE_TWOOPT_REQUIREMENT_KEYS:
        coverage = _mapping_or_empty(problem_specific.get(key))
        check = _mapping_or_empty(checks.get(key))
        requirements[key] = {
            "available": coverage.get("available") is True
            or check.get("passed") is True,
            "count": _int_or_zero(coverage.get("count")),
            "source": coverage.get("source") or check.get("detail") or "",
            "contract_check_passed": check.get("passed"),
            "contract_detail": check.get("detail"),
        }
    return requirements


def _cvrp_large_twoopt_mechanism_signal(
    *,
    measurement_effect_summary: Mapping[str, Any],
    research_continuity_summary: Mapping[str, Any],
) -> dict[str, Any]:
    families: set[str] = set()
    protocol_rows = 0
    measurement = _mapping_or_empty(measurement_effect_summary.get("aggregate"))
    family_effects = _mapping_or_empty(measurement.get("mechanism_family_effects"))
    for family, payload in sorted(family_effects.items()):
        if not _is_cvrp_large_twoopt_family(str(family)):
            continue
        families.add(str(family))
        protocol_rows += _int_or_zero(
            _mapping_or_empty(payload).get("protocol_row_count")
        )
    entries = measurement_effect_summary.get("entries")
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            effect = _mapping_or_empty(entry.get("protocol_effects_vs_mde"))
            top_rows = effect.get("top_rows_by_effect_to_mde")
            if not isinstance(top_rows, list):
                continue
            for row in top_rows:
                if not isinstance(row, Mapping):
                    continue
                family = str(row.get("mechanism_family") or "")
                if _is_cvrp_large_twoopt_family(family):
                    families.add(family)
    continuity = _mapping_or_empty(research_continuity_summary.get("aggregate"))
    family_counts = _mapping_or_empty(continuity.get("mechanism_family_counts"))
    for family in family_counts:
        if _is_cvrp_large_twoopt_family(str(family)):
            families.add(str(family))
    return {
        "available": bool(families),
        "families": sorted(families),
        "protocol_row_count": protocol_rows,
        "source": (
            "measurement_effect_summary.mechanism_family_effects and "
            "research_continuity_summary.mechanism_family_counts"
        ),
    }


def _is_cvrp_large_twoopt_family(value: str) -> bool:
    normalized = (
        value.lower()
        .replace("-", "_")
        .replace(" ", "_")
        .replace("/", "_")
    )
    compact = normalized.replace("_", "")
    return (
        "two_opt" in normalized
        or "2opt" in compact
        or "twoopt" in compact
    )


def _cvrp_large_twoopt_interpretation(
    *,
    current_run_evidence: bool,
    handoff_complete: bool,
    protocol_evaluated_candidates: int,
    formal_screened_candidates: int,
    quality_block_signal: int,
    measurement_available: bool,
    runtime_available: bool,
    continuity_available: bool,
    large_twoopt_available: bool,
) -> str:
    if not current_run_evidence:
        return "prepared_only_launch_required"
    if protocol_evaluated_candidates <= 0:
        if quality_block_signal > 0:
            return "quality_blocked_no_protocol_twoopt_conclusion"
        if formal_screened_candidates > 0:
            return "screened_without_protocol_evaluation"
        return "insufficient_current_run_evidence"
    if not handoff_complete:
        return "protocol_evaluated_handoff_incomplete"
    if not (
        measurement_available
        and runtime_available
        and continuity_available
    ):
        return "protocol_evaluated_review_inputs_incomplete"
    if not large_twoopt_available:
        return "protocol_evaluated_without_large_twoopt_signal"
    return "bounded_twoopt_review_ready"


def _cvrp_large_twoopt_evidence_gaps(
    *,
    current_run_evidence: bool,
    handoff_complete: bool,
    protocol_evaluated_candidates: int,
    quality_block_signal: int,
    measurement_available: bool,
    runtime_available: bool,
    continuity_available: bool,
    large_twoopt_available: bool,
) -> list[str]:
    gaps: list[str] = []
    if not handoff_complete:
        gaps.append("cvrp_large_twoopt_handoff_requirements_incomplete")
    if not current_run_evidence:
        gaps.append("launch_required_before_bounded_twoopt_conclusion")
        return gaps
    if protocol_evaluated_candidates <= 0:
        if quality_block_signal > 0:
            gaps.append("quality_blocked_before_protocol_evaluation")
        else:
            gaps.append("no_protocol_evaluated_candidates")
    if not measurement_available:
        gaps.append("missing_measurement_effect_summary")
    if not runtime_available:
        gaps.append("missing_runtime_feedback_summary")
    if not continuity_available:
        gaps.append("missing_research_continuity_summary")
    if protocol_evaluated_candidates > 0 and not large_twoopt_available:
        gaps.append("missing_large_twoopt_mechanism_signal")
    return gaps


def _warehouse_followup_summary(
    inventory: Mapping[str, Any],
    *,
    protocol_accounting_summary: Mapping[str, Any],
    measurement_effect_summary: Mapping[str, Any],
    runtime_feedback_summary: Mapping[str, Any],
    failure_taxonomy_summary: Mapping[str, Any],
    research_continuity_summary: Mapping[str, Any],
) -> dict[str, Any]:
    phase4 = _mapping_or_empty(inventory.get("phase4_evidence_coverage"))
    launcher = _mapping_or_empty(inventory.get("launcher"))
    contract = _mapping_or_empty(launcher.get("prepared_run_contract"))
    problem_family = contract.get("problem_family")
    current_run_evidence = phase4.get("current_run_evidence") is True
    base = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
        "problem_family": problem_family,
        "current_run_evidence": current_run_evidence,
        "available": False,
        "handoff_complete": False,
        "handoff_requirements": {},
        "launch_required_before_plateau_conclusion": False,
        "interpretation": "not_warehouse_delivery",
        "evidence": {},
        "evidence_gaps": [],
        "required_review_axes": list(WAREHOUSE_FOLLOWUP_REVIEW_AXES),
        "deferred_review_axes": [],
        "review_axes_actionability": "not_applicable",
    }
    if problem_family != "warehouse_delivery":
        return base

    handoff_requirements = _warehouse_handoff_requirements(
        phase4=phase4,
        contract=contract,
    )
    handoff_complete = bool(handoff_requirements) and all(
        item.get("available") is True for item in handoff_requirements.values()
    )
    counters = _mapping_or_empty(inventory.get("counters"))
    accounting = _mapping_or_empty(protocol_accounting_summary.get("aggregate"))
    protocol_rows = _mapping_or_empty(accounting.get("protocol_rows"))
    formal_artifacts = _mapping_or_empty(
        accounting.get("formal_candidate_artifacts")
    )
    formal_screened_candidates = max(
        _int_or_zero(accounting.get("formal_screened_candidates")),
        _int_or_zero(counters.get("formal_screened_candidates")),
        _int_or_zero(counters.get("screened_experiments")),
    )
    protocol_evaluated_candidates = max(
        _int_or_zero(protocol_rows.get("protocol_evaluated_candidates")),
        _int_or_zero(accounting.get("formal_protocol_evaluated_candidates")),
        _int_or_zero(counters.get("protocol_evaluated_candidates")),
    )
    measurement = _mapping_or_empty(measurement_effect_summary.get("aggregate"))
    runtime = _mapping_or_empty(runtime_feedback_summary.get("aggregate"))
    fresh_runtime = _mapping_or_empty(runtime.get("fresh_runtime_replay_drain"))
    stage_drain = _mapping_or_empty(runtime.get("stage_transition_drain"))
    runtime_budget = _mapping_or_empty(runtime.get("runtime_budget_diagnostics"))
    failure = _mapping_or_empty(failure_taxonomy_summary.get("aggregate"))
    proposal_quality = _mapping_or_empty(failure.get("proposal_quality"))
    quality_block_signal = max(
        _int_or_zero(proposal_quality.get("proposal_quality_blocks")),
        _int_or_zero(proposal_quality.get("quality_blocks")),
        _int_or_zero(proposal_quality.get("quality_block_ledger_count")),
    )
    evidence = {
        "protocol": {
            "formal_screened_candidates": formal_screened_candidates,
            "protocol_evaluated_candidates": protocol_evaluated_candidates,
            "protocol_metric_results": _int_or_zero(
                protocol_rows.get("protocol_metric_results")
            ),
            "formal_candidate_artifact_rows": _int_or_zero(
                formal_artifacts.get("row_count")
            ),
            "stage_rows": _mapping_or_empty(accounting.get("stage_rows")),
        },
        "measurement_effect": {
            "available": measurement_effect_summary.get("available") is True,
            "protocol_row_count": _int_or_zero(
                measurement.get("protocol_row_count")
            ),
            "rows_at_or_above_mde": _int_or_zero(
                measurement.get("rows_at_or_above_mde")
            ),
            "rows_with_ci_high_below_mde": _int_or_zero(
                measurement.get("rows_with_ci_high_below_mde")
            ),
            "max_effect_to_mde_ratio": measurement.get("max_effect_to_mde_ratio"),
            "interpretation_counts": _int_mapping(
                measurement.get("interpretation_counts")
            ),
        },
        "quality_blocks": {
            "proposal_quality_blocks": _int_or_zero(
                proposal_quality.get("proposal_quality_blocks")
            ),
            "quality_blocks": _int_or_zero(proposal_quality.get("quality_blocks")),
            "quality_block_ledger_count": _int_or_zero(
                proposal_quality.get("quality_block_ledger_count")
            ),
            "reports_with_quality_blocks": _int_or_zero(
                proposal_quality.get("reports_with_quality_blocks")
            ),
            "reason_counts": _int_mapping(
                proposal_quality.get("quality_block_reason_counts")
            ),
        },
        "runtime": {
            "available": runtime_feedback_summary.get("available") is True,
            "fresh_runtime_status_counts": _int_mapping(
                fresh_runtime.get("status_counts")
            ),
            "fresh_runtime_attempts": _int_or_zero(fresh_runtime.get("attempts")),
            "fresh_runtime_executed": _int_or_zero(fresh_runtime.get("executed")),
            "fresh_runtime_protocol_results": _int_or_zero(
                fresh_runtime.get("protocol_results")
            ),
            "stage_transition_status_counts": _int_mapping(
                stage_drain.get("status_counts")
            ),
            "runtime_model_counts": _int_mapping(
                runtime_budget.get("runtime_model_counts")
            ),
            "runtime_budget_diagnostic_count": _int_or_zero(
                runtime_budget.get("diagnostic_count")
            ),
        },
        "research_continuity": {
            "available": research_continuity_summary.get("available") is True,
            "continuity_report_count": _int_or_zero(
                research_continuity_summary.get("continuity_report_count")
            ),
        },
    }
    interpretation = _warehouse_followup_interpretation(
        current_run_evidence=current_run_evidence,
        handoff_complete=handoff_complete,
        protocol_evaluated_candidates=protocol_evaluated_candidates,
        formal_screened_candidates=formal_screened_candidates,
        quality_block_signal=quality_block_signal,
        measurement_available=measurement_effect_summary.get("available") is True,
        runtime_available=runtime_feedback_summary.get("available") is True,
        continuity_available=research_continuity_summary.get("available") is True,
    )
    return {
        **base,
        "available": True,
        "handoff_complete": handoff_complete,
        "handoff_requirements": handoff_requirements,
        "launch_required_before_plateau_conclusion": not current_run_evidence,
        "interpretation": interpretation,
        "evidence": evidence,
        "evidence_gaps": _warehouse_followup_evidence_gaps(
            current_run_evidence=current_run_evidence,
            handoff_complete=handoff_complete,
            protocol_evaluated_candidates=protocol_evaluated_candidates,
            quality_block_signal=quality_block_signal,
            measurement_available=measurement_effect_summary.get("available") is True,
            runtime_available=runtime_feedback_summary.get("available") is True,
            continuity_available=research_continuity_summary.get("available") is True,
        ),
        "deferred_review_axes": (
            list(WAREHOUSE_FOLLOWUP_REVIEW_AXES)
            if not current_run_evidence
            else []
        ),
        "review_axes_actionability": (
            "not_actionable_before_launch_current_run_evidence_required"
            if not current_run_evidence
            else "actionable_current_run_evidence_present"
        ),
    }


def _warehouse_handoff_requirements(
    *,
    phase4: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    problem_specific = _mapping_or_empty(phase4.get("problem_specific_requirements"))
    checks = _mapping_or_empty(contract.get("checks"))
    requirements: dict[str, Any] = {}
    for key in WAREHOUSE_FOLLOWUP_REQUIREMENT_KEYS:
        coverage = _mapping_or_empty(problem_specific.get(key))
        check = _mapping_or_empty(checks.get(key))
        requirements[key] = {
            "available": coverage.get("available") is True
            or check.get("passed") is True,
            "count": _int_or_zero(coverage.get("count")),
            "source": coverage.get("source") or check.get("detail") or "",
            "contract_check_passed": check.get("passed"),
            "contract_detail": check.get("detail"),
        }
    return requirements


def _warehouse_followup_interpretation(
    *,
    current_run_evidence: bool,
    handoff_complete: bool,
    protocol_evaluated_candidates: int,
    formal_screened_candidates: int,
    quality_block_signal: int,
    measurement_available: bool,
    runtime_available: bool,
    continuity_available: bool,
) -> str:
    if not current_run_evidence:
        return "prepared_only_launch_required"
    if protocol_evaluated_candidates > 0:
        if not handoff_complete:
            return "protocol_evaluated_handoff_incomplete"
        if not (
            measurement_available
            and runtime_available
            and continuity_available
        ):
            return "protocol_evaluated_review_inputs_incomplete"
        return "protocol_evaluated_plateau_review_ready"
    if quality_block_signal > 0:
        return "quality_blocked_no_protocol_plateau_conclusion"
    if formal_screened_candidates > 0:
        return "screened_without_protocol_evaluation"
    return "insufficient_current_run_evidence"


def _warehouse_followup_evidence_gaps(
    *,
    current_run_evidence: bool,
    handoff_complete: bool,
    protocol_evaluated_candidates: int,
    quality_block_signal: int,
    measurement_available: bool,
    runtime_available: bool,
    continuity_available: bool,
) -> list[str]:
    gaps: list[str] = []
    if not handoff_complete:
        gaps.append("warehouse_handoff_requirements_incomplete")
    if not current_run_evidence:
        gaps.append("launch_required_before_plateau_conclusion")
        return gaps
    if protocol_evaluated_candidates <= 0:
        if quality_block_signal > 0:
            gaps.append("quality_blocked_before_protocol_evaluation")
        else:
            gaps.append("no_protocol_evaluated_candidates")
    if not measurement_available:
        gaps.append("missing_measurement_effect_summary")
    if not runtime_available:
        gaps.append("missing_runtime_feedback_summary")
    if not continuity_available:
        gaps.append("missing_research_continuity_summary")
    return gaps


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


def _int_mapping(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): _int_or_zero(item) for key, item in sorted(value.items())}


def _sum_counts(value: Any) -> int:
    if not isinstance(value, Mapping):
        return 0
    return sum(_int_or_zero(item) for item in value.values())


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
