#!/usr/bin/env python3
"""Rebuild report-only prepared handoff artifacts for a Scion launch root."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


TOOLS_DIR = Path(__file__).resolve().parent
REPO_DIR = Path(__file__).resolve().parents[2]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from check_launch_readiness import (  # noqa: E402
    build_readiness,
    render_markdown as render_readiness_markdown,
)
from postrun_analysis_brief import (  # noqa: E402
    build_brief,
    render_markdown as render_brief_markdown,
)
from postrun_artifact_inventory import (  # noqa: E402
    build_inventory,
    render_markdown as render_inventory_markdown,
)


SCHEMA_VERSION = "scion.prepared_handoff_rebuild.v1"
PROMPT_CONTEXT_READINESS_SCHEMA = "scion.prepared_prompt_context_readiness.v1"
DEFAULT_FAMILIES = (
    "analysis_brief",
    "inventory",
    "prompt_context_readiness",
    "launch_readiness",
)
RESEARCH_SHAPE_PROMPT_MARKERS = {
    "context_builder": (
        "scion/scion/proposal/context_manager/manager.py",
        "research_shape_diagnostics",
    ),
    "shape_builder": (
        "scion/scion/proposal/context/research_shape.py",
        "proposal_research_shape_prompt_summary.v1",
    ),
    "prompt_renderer": (
        "scion/scion/proposal/engine/hypothesis_prompts.py",
        "research_shape",
    ),
}
LAUNCH_RESEARCH_FOCUS_PROMPT_MARKERS = {
    "manifest_env_reader": (
        "scion/scion/proposal/context_manager/manager.py",
        "PREPARED_RUN_MANIFEST",
    ),
    "context_payload": (
        "scion/scion/proposal/context_manager/manager.py",
        "launch_research_focus",
    ),
    "prompt_renderer": (
        "scion/scion/proposal/engine/hypothesis_prompts.py",
        "launch_research_focus",
    ),
}
ACTIVE_SUBJECT_CODE_CONSTRAINT_PROMPT_MARKERS = {
    "context_provider_payload": (
        "scion/scion/proposal/context_manager/manager.py",
        "active_subject_code_constraints_payload(",
    ),
    "context_key": (
        "scion/scion/proposal/context_manager/manager.py",
        "active_subject_code_constraints",
    ),
    "code_prompt_renderer": (
        "scion/scion/proposal/engine/code_prompts.py",
        "Active Subject Code Constraints",
    ),
}
CVRP_ACTIVE_SUBJECT_CODE_CONSTRAINT_MARKERS = {
    "provider_hook": (
        "scion/scion/problems/cvrp/solver_design_provider.py",
        "def active_subject_code_constraints",
    ),
    "large_twoopt_runtime_guard": (
        "scion/scion/problems/cvrp/solver_design_provider.py",
        "large_instance_two_opt_runtime_guard",
    ),
    "unbounded_twoopt_reject": (
        "scion/scion/problems/cvrp/solver_design_provider.py",
        "UNBOUNDED_TWO_OPT_DEFAULT_REJECT",
    ),
}


def rebuild_prepared_handoff(
    run_root: Path | str,
    *,
    report_stem: str | None = None,
    strict: bool = False,
) -> dict[str, Any]:
    """Rebuild prepared handoff artifacts without starting a campaign."""

    root = Path(run_root).expanduser().resolve()
    manifest = _read_json(root / "prepared_run_manifest.v1.json")
    stem = report_stem or _resolve_report_stem(root, manifest)

    handoff_dir = root / "prepared_handoff"
    brief_dir = handoff_dir / "analysis_brief"
    inventory_dir = handoff_dir / "inventory"
    prompt_context_dir = handoff_dir / "prompt_context_readiness"
    readiness_dir = handoff_dir / "launch_readiness"
    rebuild_dir = handoff_dir / "rebuild"
    for path in (
        brief_dir,
        inventory_dir,
        prompt_context_dir,
        readiness_dir,
        rebuild_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)

    family_results: dict[str, dict[str, Any]] = {}
    family_results["analysis_brief"] = _write_family(
        [
            brief_dir / f"{stem}.prepared_analysis_brief.v1.json",
            brief_dir / f"{stem}.prepared_analysis_brief.md",
        ],
        lambda: _write_analysis_brief(root, brief_dir, stem),
    )
    family_results["inventory"] = _write_family(
        [
            inventory_dir / f"{stem}.prepared_artifact_inventory.v1.json",
            inventory_dir / f"{stem}.prepared_artifact_inventory.md",
        ],
        lambda: _write_inventory(root, inventory_dir, stem),
    )
    family_results["prompt_context_readiness"] = _write_family(
        [
            prompt_context_dir
            / f"{stem}.prepared_prompt_context_readiness.v1.json",
            prompt_context_dir / f"{stem}.prepared_prompt_context_readiness.md",
        ],
        lambda: _write_prompt_context_readiness(root, prompt_context_dir, stem),
    )
    family_results["launch_readiness"] = _write_family(
        [
            readiness_dir / f"{stem}.prepared_launch_readiness.v1.json",
            readiness_dir / f"{stem}.prepared_launch_readiness.md",
        ],
        lambda: _write_launch_readiness(root, readiness_dir, stem),
    )

    complete = all(result.get("status") == "ok" for result in family_results.values())
    rebuild_manifest = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "prepared_handoff_rebuild",
        "generated_at": _utc_now_iso(),
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
        "run_root": str(root),
        "prepared_handoff_dir": str(handoff_dir),
        "report_stem": stem,
        "problem_family": manifest.get("problem_family")
        if isinstance(manifest, dict)
        else None,
        "prepared_manifest_commit": _manifest_commit(manifest),
        "checkout_commit": _git_output(("rev-parse", "--short", "HEAD")),
        "families": family_results,
        "complete": complete,
    }
    manifest_path = rebuild_dir / "prepared_handoff_rebuild.v1.json"
    manifest_path.write_text(_stable_json(rebuild_manifest), encoding="utf-8")
    if strict and not complete:
        failed = ", ".join(
            name
            for name, result in sorted(family_results.items())
            if result.get("status") != "ok"
        )
        raise RuntimeError(f"prepared handoff rebuild incomplete: {failed}")
    return rebuild_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_root", help="Prepared launch root.")
    parser.add_argument("--report-stem", help="Filename stem for rebuilt handoff files.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any handoff family fails to rebuild.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="text",
        help="Output format for the rebuild summary.",
    )
    args = parser.parse_args(argv)

    try:
        manifest = rebuild_prepared_handoff(
            args.run_root,
            report_stem=args.report_stem,
            strict=args.strict,
        )
    except Exception as exc:  # noqa: BLE001
        if args.format == "json":
            print(
                json.dumps(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "complete": False,
                        "error": str(exc),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print(f"prepared handoff rebuild failed: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        print(json.dumps(manifest, indent=2, sort_keys=True))
    else:
        print(f"prepared_handoff_rebuild_complete={manifest['complete']}")
        print(f"prepared_handoff_dir={manifest['prepared_handoff_dir']}")
        print(f"report_stem={manifest['report_stem']}")
        for name, result in sorted(manifest["families"].items()):
            print(f"{name}={result.get('status')}")
    return 0 if manifest["complete"] else 1


def _write_analysis_brief(root: Path, brief_dir: Path, stem: str) -> None:
    brief = build_brief(root)
    (brief_dir / f"{stem}.prepared_analysis_brief.v1.json").write_text(
        _stable_json(brief),
        encoding="utf-8",
    )
    (brief_dir / f"{stem}.prepared_analysis_brief.md").write_text(
        render_brief_markdown(brief),
        encoding="utf-8",
    )


def _write_inventory(root: Path, inventory_dir: Path, stem: str) -> None:
    inventory = build_inventory(root)
    (inventory_dir / f"{stem}.prepared_artifact_inventory.v1.json").write_text(
        _stable_json(inventory),
        encoding="utf-8",
    )
    (inventory_dir / f"{stem}.prepared_artifact_inventory.md").write_text(
        render_inventory_markdown(inventory),
        encoding="utf-8",
    )


def _write_prompt_context_readiness(
    root: Path,
    prompt_context_dir: Path,
    stem: str,
) -> None:
    report = build_prepared_prompt_context_readiness(root)
    (prompt_context_dir / f"{stem}.prepared_prompt_context_readiness.v1.json").write_text(
        _stable_json(report),
        encoding="utf-8",
    )
    (prompt_context_dir / f"{stem}.prepared_prompt_context_readiness.md").write_text(
        render_prompt_context_readiness_markdown(report),
        encoding="utf-8",
    )


def _write_launch_readiness(root: Path, readiness_dir: Path, stem: str) -> None:
    readiness = build_readiness(root)
    (readiness_dir / f"{stem}.prepared_launch_readiness.v1.json").write_text(
        _stable_json(readiness),
        encoding="utf-8",
    )
    (readiness_dir / f"{stem}.prepared_launch_readiness.md").write_text(
        render_readiness_markdown(readiness),
        encoding="utf-8",
    )


def _write_family(
    outputs: list[Path],
    writer: Callable[[], None],
) -> dict[str, Any]:
    try:
        writer()
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "failed",
            "error": str(exc),
            "outputs": [str(path) for path in outputs],
        }
    return {
        "status": "ok",
        "outputs": [str(path) for path in outputs],
    }


def build_prepared_prompt_context_readiness(run_root: Path | str) -> dict[str, Any]:
    """Audit prompt/context signal sources for a prepared-only launch root."""

    root = Path(run_root).expanduser().resolve()
    manifest_path = root / "prepared_run_manifest.v1.json"
    manifest = _read_json(manifest_path)
    manifest_dict = manifest if isinstance(manifest, dict) else {}
    campaign_dir = _resolve_campaign_dir(root, manifest_dict)
    summary_path = campaign_dir / "campaign_summary.json"
    status_path = campaign_dir / "status.json"
    campaign_summary = _read_json(summary_path)
    campaign_status = _read_json(status_path)
    summary_dict = campaign_summary if isinstance(campaign_summary, dict) else {}
    status_dict = campaign_status if isinstance(campaign_status, dict) else {}
    research_focus = _mapping_or_empty(manifest_dict.get("research_focus"))
    model = _mapping_or_empty(manifest_dict.get("model"))
    execution = _mapping_or_empty(manifest_dict.get("execution"))

    signals: dict[str, dict[str, Any]] = {}
    _add_signal(
        signals,
        "prepared_manifest",
        available=bool(manifest_dict),
        required=True,
        source=str(manifest_path),
        detail={"problem_family": manifest_dict.get("problem_family")},
    )
    _add_signal(
        signals,
        "prepared_research_focus",
        available=bool(research_focus),
        required=True,
        source="prepared_run_manifest.research_focus",
        detail={
            "schema_version": research_focus.get("schema_version"),
            "field_count": len(research_focus),
        },
    )
    _add_signal(
        signals,
        "copied_campaign_summary",
        available=bool(summary_dict),
        required=True,
        source=str(summary_path),
        detail={"keys": sorted(summary_dict)[:12]},
    )
    _add_signal(
        signals,
        "copied_campaign_status",
        available=bool(status_dict),
        required=True,
        source=str(status_path),
        detail={"keys": sorted(status_dict)[:12]},
    )
    _add_signal(
        signals,
        "completion_preflight_contract",
        available=model.get("completion_preflight") is True,
        required=False,
        source="prepared_run_manifest.model.completion_preflight",
        detail={"model": model.get("name")},
    )
    _add_focus_signals(signals, manifest_dict, research_focus)
    _add_campaign_state_signals(signals, summary_dict, status_dict)
    _add_research_shape_prompt_signal(signals)
    _add_launch_research_focus_prompt_signal(
        signals,
        root=root,
        required=bool(research_focus),
    )
    _add_active_subject_code_constraints_prompt_signal(
        signals,
        problem_family=manifest_dict.get("problem_family"),
    )

    missing_required = [
        name
        for name, item in sorted(signals.items())
        if item.get("required") is True
        and item.get("available") is not True
        and item.get("runtime_generated_after_launch") is not True
    ]

    return {
        "schema_version": PROMPT_CONTEXT_READINESS_SCHEMA,
        "artifact_kind": "prepared_prompt_context_readiness",
        "generated_at": _utc_now_iso(),
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
        "raw_provider_prompt_rendered": False,
        "run_root": str(root),
        "campaign_dir": str(campaign_dir),
        "prepared_manifest_path": str(manifest_path),
        "problem_family": manifest_dict.get("problem_family"),
        "model": model.get("name"),
        "measurement_governance": execution.get("measurement_governance"),
        "proposal_context_ablation": execution.get("proposal_context_ablation"),
        "prepared_manifest_commit": _manifest_commit(manifest_dict),
        "checkout_commit": _git_output(("rev-parse", "--short", "HEAD")),
        "readiness": {
            "ready_for_launch_prompt_audit": not missing_required,
            "missing_required": missing_required,
            "status": "ready" if not missing_required else "missing_required_sources",
        },
        "signals": signals,
        "notes": [
            "This report audits prompt/context signal sources only.",
            "It does not render raw provider prompts or mutate campaign state.",
            "Branch-level next-prompt context may be generated only after launch.",
        ],
    }


def render_prompt_context_readiness_markdown(report: dict[str, Any]) -> str:
    readiness = report.get("readiness")
    if not isinstance(readiness, dict):
        readiness = {}
    signals = report.get("signals")
    if not isinstance(signals, dict):
        signals = {}

    lines = [
        "# Prepared Prompt/Context Readiness",
        "",
        f"- Schema: `{report.get('schema_version')}`",
        f"- Report-only: `{report.get('report_only')}`",
        f"- Raw provider prompt rendered: `{report.get('raw_provider_prompt_rendered')}`",
        f"- Problem family: `{_display(report.get('problem_family'))}`",
        f"- Model: `{_display(report.get('model'))}`",
        f"- Ready for launch prompt audit: `{readiness.get('ready_for_launch_prompt_audit')}`",
        f"- Status: `{_display(readiness.get('status'))}`",
        "",
        "## Missing Required Sources",
    ]
    missing = readiness.get("missing_required")
    if isinstance(missing, list) and missing:
        for item in missing:
            lines.append(f"- `{item}`")
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Signal Sources",
            "",
            "| Signal | Required | Available | Runtime-generated after launch | Source | Detail |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for name, item in sorted(signals.items()):
        if not isinstance(item, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(name),
                    _md_cell(item.get("required")),
                    _md_cell(item.get("available")),
                    _md_cell(item.get("runtime_generated_after_launch")),
                    _md_cell(item.get("source")),
                    _md_cell(item.get("detail")),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Notes",
        ]
    )
    notes = report.get("notes")
    if isinstance(notes, list) and notes:
        for item in notes:
            lines.append(f"- {item}")
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def _add_focus_signals(
    signals: dict[str, dict[str, Any]],
    manifest: dict[str, Any],
    research_focus: dict[str, Any],
) -> None:
    family = manifest.get("problem_family")
    if family == "cvrp":
        measurement = _mapping_or_empty(
            research_focus.get("measurement_opportunity_diagnostics")
        )
        _add_signal(
            signals,
            "cvrp_measurement_opportunity_handoff",
            available=bool(measurement),
            required=True,
            source="prepared_run_manifest.research_focus.measurement_opportunity_diagnostics",
            detail={
                "schema_version": measurement.get("schema_version"),
                "reason_code_count": len(_string_items(measurement.get("reason_codes"))),
            },
        )
        opportunity_items = _string_items(
            research_focus.get("measurable_opportunity_classes")
        )
        avoid_items = _string_items(research_focus.get("default_avoid_directions"))
        _add_signal(
            signals,
            "cvrp_measurable_opportunity_classes",
            available=bool(opportunity_items),
            required=True,
            source="prepared_run_manifest.research_focus.measurable_opportunity_classes",
            detail={"count": len(opportunity_items)},
        )
        _add_signal(
            signals,
            "cvrp_default_avoid_directions",
            available=bool(avoid_items),
            required=True,
            source="prepared_run_manifest.research_focus.default_avoid_directions",
            detail={"count": len(avoid_items)},
        )
        direct_rules_present = bool(
            research_focus.get("route_merge_exception_rule")
            and research_focus.get("construction_seed_rule")
        )
        _add_signal(
            signals,
            "cvrp_direct_effect_rules",
            available=direct_rules_present,
            required=True,
            source=(
                "prepared_run_manifest.research_focus.route_merge_exception_rule "
                "and construction_seed_rule"
            ),
            detail={
                "route_merge_exception_rule_present": bool(
                    research_focus.get("route_merge_exception_rule")
                ),
                "construction_seed_rule_present": bool(
                    research_focus.get("construction_seed_rule")
                ),
            },
        )
        large_twoopt = _mapping_or_empty(
            research_focus.get("large_instance_two_opt_constraints")
        )
        implementation_items = _string_items(
            large_twoopt.get("implementation_constraints")
        )
        evidence_items = _string_items(large_twoopt.get("required_pair_evidence"))
        reject_items = _string_items(large_twoopt.get("default_reject_directions"))
        _add_signal(
            signals,
            "cvrp_large_twoopt_bounded_constraints",
            available=(
                bool(large_twoopt)
                and bool(implementation_items)
                and bool(evidence_items)
                and bool(reject_items)
                and large_twoopt.get("proposal_visibility_only") is True
                and large_twoopt.get("decision_features_excluded") is True
            ),
            required=True,
            source="prepared_run_manifest.research_focus.large_instance_two_opt_constraints",
            detail={
                "schema_version": large_twoopt.get("schema_version"),
                "seed_report": large_twoopt.get("seed_report"),
                "implementation_constraint_count": len(implementation_items),
                "required_pair_evidence_count": len(evidence_items),
                "default_reject_direction_count": len(reject_items),
            },
        )
    elif family == "warehouse_delivery":
        required_evidence = _string_items(research_focus.get("required_evidence"))
        avoid_items = _string_items(research_focus.get("default_avoid_directions"))
        _add_signal(
            signals,
            "warehouse_v2_followup_question",
            available=bool(
                research_focus.get("accepted_checkpoint")
                and research_focus.get("current_question")
            ),
            required=True,
            source=(
                "prepared_run_manifest.research_focus.accepted_checkpoint "
                "and current_question"
            ),
            detail={
                "accepted_checkpoint_present": bool(
                    research_focus.get("accepted_checkpoint")
                ),
                "current_question_present": bool(
                    research_focus.get("current_question")
                ),
            },
        )
        _add_signal(
            signals,
            "warehouse_required_evidence",
            available=bool(required_evidence),
            required=True,
            source="prepared_run_manifest.research_focus.required_evidence",
            detail={"count": len(required_evidence)},
        )
        _add_signal(
            signals,
            "warehouse_default_avoid_directions",
            available=bool(avoid_items),
            required=True,
            source="prepared_run_manifest.research_focus.default_avoid_directions",
            detail={"count": len(avoid_items)},
        )

    boundary = str(research_focus.get("decision_boundary") or "").lower()
    _add_signal(
        signals,
        "research_focus_decision_boundary",
        available=(
            "decisionfeatures" in boundary
            and "protocol" in boundary
            and "promotion" in boundary
            and "scheduler" in boundary
        ),
        required=family in {"cvrp", "warehouse_delivery"},
        source="prepared_run_manifest.research_focus.decision_boundary",
        detail={"problem_family": family},
    )


def _add_campaign_state_signals(
    signals: dict[str, dict[str, Any]],
    summary: dict[str, Any],
    status: dict[str, Any],
) -> None:
    summary_branch_count = _sequence_count(summary.get("branches"))
    status_branch_count = _sequence_count(status.get("branches"))
    branch_count = max(summary_branch_count, status_branch_count)
    _add_signal(
        signals,
        "copied_branch_snapshot",
        available=branch_count > 0,
        required=False,
        source="campaign_summary.branches or status.branches",
        detail={
            "summary_branch_count": summary_branch_count,
            "status_branch_count": status_branch_count,
        },
        runtime_generated_after_launch=branch_count == 0,
    )

    trace_index_present = bool(
        _mapping_or_empty(summary.get("agentic_session_trace_index"))
        or _mapping_or_empty(status.get("agentic_session_trace_index"))
    )
    _add_signal(
        signals,
        "agentic_session_trace_index",
        available=trace_index_present,
        required=False,
        source="campaign_summary/status agentic_session_trace_index",
        detail={"present": trace_index_present},
        runtime_generated_after_launch=not trace_index_present,
    )

    prompt_manifest_ref_count = _count_prompt_manifest_refs(summary) + (
        _count_prompt_manifest_refs(status)
    )
    _add_signal(
        signals,
        "prompt_manifest_history",
        available=prompt_manifest_ref_count > 0,
        required=False,
        source="campaign_summary/status prompt_manifest references",
        detail={"prompt_manifest_ref_count": prompt_manifest_ref_count},
        runtime_generated_after_launch=prompt_manifest_ref_count == 0,
    )


def _add_research_shape_prompt_signal(signals: dict[str, dict[str, Any]]) -> None:
    marker_results = {
        name: _source_contains(relative_path, marker)
        for name, (relative_path, marker) in RESEARCH_SHAPE_PROMPT_MARKERS.items()
    }
    _add_signal(
        signals,
        "research_shape_prompt_signal",
        available=all(marker_results.values()),
        required=True,
        source="current checkout proposal context and hypothesis prompt code",
        detail={"markers": marker_results},
    )


def _add_launch_research_focus_prompt_signal(
    signals: dict[str, dict[str, Any]],
    *,
    root: Path,
    required: bool,
) -> None:
    source_marker_results = {
        name: _source_contains(relative_path, marker)
        for name, (relative_path, marker) in (
            LAUNCH_RESEARCH_FOCUS_PROMPT_MARKERS.items()
        )
    }
    launch_marker_results = {
        "prepared_manifest_exists": (root / "prepared_run_manifest.v1.json").is_file(),
        "launch_env_assignment": _path_contains(
            root / "launch.env",
            "PREPARED_RUN_MANIFEST=",
        ),
        "run_sh_exports_manifest": _path_contains(
            root / "run.sh",
            "PREPARED_RUN_MANIFEST",
        )
        and _path_contains(root / "run.sh", "export ")
        and _path_contains(root / "run.sh", "scion.cli.main run"),
    }
    _add_signal(
        signals,
        "prepared_research_focus_prompt_bridge",
        available=(
            all(source_marker_results.values())
            and all(launch_marker_results.values())
        ),
        required=required,
        source=(
            "prepared root launch environment plus current checkout "
            "prepared-run manifest reader and hypothesis prompt renderer"
        ),
        detail={
            "source_markers": source_marker_results,
            "launch_markers": launch_marker_results,
        },
    )


def _add_active_subject_code_constraints_prompt_signal(
    signals: dict[str, dict[str, Any]],
    *,
    problem_family: Any,
) -> None:
    if problem_family != "cvrp":
        return
    source_marker_results = {
        name: _source_contains(relative_path, marker)
        for name, (relative_path, marker) in (
            ACTIVE_SUBJECT_CODE_CONSTRAINT_PROMPT_MARKERS.items()
        )
    }
    provider_marker_results = {
        name: _source_contains(relative_path, marker)
        for name, (relative_path, marker) in (
            CVRP_ACTIVE_SUBJECT_CODE_CONSTRAINT_MARKERS.items()
        )
    }
    _add_signal(
        signals,
        "cvrp_active_subject_code_constraints_prompt_bridge",
        available=(
            all(source_marker_results.values())
            and all(provider_marker_results.values())
        ),
        required=True,
        source=(
            "current checkout CVRP active subject code constraint provider plus "
            "code prompt renderer"
        ),
        detail={
            "source_markers": source_marker_results,
            "provider_markers": provider_marker_results,
            "boundary": (
                "report-only source bridge; provider constraints guide code "
                "generation and stay out of DecisionFeatures"
            ),
        },
    )


def _add_signal(
    signals: dict[str, dict[str, Any]],
    name: str,
    *,
    available: bool,
    required: bool,
    source: Any,
    detail: Any = None,
    runtime_generated_after_launch: bool = False,
) -> None:
    signals[name] = {
        "available": bool(available),
        "required": bool(required),
        "source": source,
        "detail": detail,
        "runtime_generated_after_launch": bool(runtime_generated_after_launch),
    }


def _resolve_campaign_dir(root: Path, manifest: dict[str, Any]) -> Path:
    local_campaign = root / "campaign"
    if local_campaign.exists():
        return local_campaign
    manifest_campaign = manifest.get("campaign_dir")
    if isinstance(manifest_campaign, str) and manifest_campaign:
        path = Path(manifest_campaign).expanduser()
        if path.exists():
            return path.resolve()
    return local_campaign


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _string_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _sequence_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return len(value)
    return 0


def _count_prompt_manifest_refs(value: Any) -> int:
    if isinstance(value, dict):
        return sum(
            (1 if "prompt_manifest" in str(key).lower() else 0)
            + _count_prompt_manifest_refs(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return sum(_count_prompt_manifest_refs(item) for item in value)
    if isinstance(value, str) and "prompt_manifest" in value.lower():
        return 1
    return 0


def _source_contains(relative_path: str, marker: str) -> bool:
    path = REPO_DIR / relative_path
    return _path_contains(path, marker)


def _path_contains(path: Path, marker: str) -> bool:
    try:
        return marker in path.read_text(encoding="utf-8")
    except OSError:
        return False


def _display(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _md_cell(value: Any) -> str:
    if isinstance(value, (dict, list)):
        rendered = json.dumps(value, sort_keys=True)
    else:
        rendered = _display(value)
    return rendered.replace("|", "\\|").replace("\n", " ")


def _resolve_report_stem(root: Path, manifest: Any) -> str:
    if isinstance(manifest, dict):
        family = str(manifest.get("problem_family") or "").strip()
        prefix = {
            "cvrp": "cvrp",
            "warehouse_delivery": "warehouse",
        }.get(family, _safe_slug(family) or _safe_slug(root.name))
        execution = manifest.get("execution")
        if not isinstance(execution, dict):
            execution = {}
        governance = _safe_slug(
            str(execution.get("measurement_governance") or "on").replace("-", "_")
        )
        ablation = _safe_slug(
            str(execution.get("proposal_context_ablation") or "full").replace(
                "-",
                "_",
            )
        )
        return f"{prefix}_{governance}_{ablation}"
    return _safe_slug(root.name) or "prepared_handoff"


def _safe_slug(value: str) -> str:
    cleaned = []
    for char in value.strip().lower():
        if char.isalnum() or char == "_":
            cleaned.append(char)
        elif char in {"-", ".", " "}:
            cleaned.append("_")
    slug = "".join(cleaned).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _manifest_commit(manifest: Any) -> str | None:
    if not isinstance(manifest, dict):
        return None
    git = manifest.get("git")
    if not isinstance(git, dict):
        return None
    commit = git.get("commit")
    return str(commit) if commit else None


def _git_output(args: tuple[str, ...]) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(REPO_DIR), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _stable_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
