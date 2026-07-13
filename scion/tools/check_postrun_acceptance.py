#!/usr/bin/env python3
"""Check whether postrun acceptance artifacts are ready for delegated review."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
SCION_ROOT = TOOLS_DIR.parent
if str(SCION_ROOT) not in sys.path:
    sys.path.insert(0, str(SCION_ROOT))

from postrun_analysis_brief import (  # noqa: E402
    _measurement_effect_summary,
    _protocol_accounting_summary,
    _runtime_feedback_summary,
)
from scion.postrun import (  # noqa: E402
    MappingPostrunInventoryPort,
    PostrunReadinessOrchestrator,
    PostrunArtifactAcceptancePort,
    PostrunEvidenceConsistencyAcceptancePort,
    PostrunLifecycleAcceptancePort,
    PostrunPromptVisibilityAcceptancePort,
    ProblemReviewRegistry,
)
from scion.problems.postrun_inventory import (
    build_problem_inventory as build_inventory,
)  # noqa: E402
from scion.problems.warehouse_delivery.postrun_review import (  # noqa: E402
    WarehouseFollowupReviewPort,
)
from scion.postrun.inventory.constants import (  # noqa: E402
    EXIT_MARKERS,
    RUN_LOG_MARKERS,
)

SCHEMA_VERSION = "scion.postrun_acceptance_readiness.v1"
UNREADY_EXIT = 64


def build_readiness(
    run_root: Path | str,
    *,
    include_typed_summary: bool = False,
) -> dict[str, Any]:
    """Return report-only readiness for delegated postrun analysis."""

    root = Path(run_root).expanduser().resolve()
    checks: dict[str, dict[str, Any]] = {}

    def add_check(
        name: str,
        status: str,
        detail: Any = "",
        *,
        required: bool = True,
    ) -> None:
        checks[name] = {
            "status": status,
            "required": bool(required),
            "detail": detail,
        }

    artifact_port = PostrunArtifactAcceptancePort()
    report_dir = root / "postrun_acceptance"
    rebuild_manifest = artifact_port.read_rebuild_manifest(report_dir)
    inventory_path = artifact_port.artifact_json_path_from_manifest(
        rebuild_manifest,
        report_dir,
        "inventory",
    )
    stored_inventory = (
        artifact_port.read_json_object(inventory_path)
        if inventory_path is not None
        else {}
    )
    if stored_inventory:
        inventory = stored_inventory
        inventory_source = "stored_postrun_inventory"
    else:
        inventory = build_inventory(root)
        inventory_source = "live_inventory_rebuild"
    inventory = _with_live_launcher_markers(root, inventory)
    postrun_reports = _mapping_or_empty(inventory.get("postrun_reports"))
    postrun_counts = _mapping_or_empty(postrun_reports.get("counts"))
    proposal_runtime = _mapping_or_empty(inventory.get("proposal_runtime"))
    add_check(
        "proposal_runtime_mode_resolved",
        "ok" if proposal_runtime.get("status") == "resolved" else "failed",
        proposal_runtime,
    )

    analysis_brief_path = artifact_port.analysis_brief_path_from_manifest(
        rebuild_manifest,
        report_dir,
    )
    analysis_brief = (
        artifact_port.read_json_object(analysis_brief_path)
        if analysis_brief_path
        else {}
    )

    checks.update(
        artifact_port.summarize(
            root=root,
            report_dir=report_dir,
            rebuild_manifest=rebuild_manifest,
            inventory_source=inventory_source,
            inventory_path=inventory_path,
            analysis_brief_path=analysis_brief_path,
            analysis_brief=analysis_brief,
            postrun_counts=postrun_counts,
        ).to_payloads()
    )
    checks.update(
        PostrunLifecycleAcceptancePort()
        .summarize(inventory, analysis_brief)
        .to_payloads()
    )
    checks.update(
        PostrunEvidenceConsistencyAcceptancePort()
        .summarize(analysis_brief=analysis_brief, inventory=inventory)
        .to_payloads()
    )
    problem_status, problem_detail = _problem_summary_actionability(
        analysis_brief,
        inventory,
    )
    add_check(
        "problem_summary_actionability",
        problem_status,
        problem_detail,
        required=problem_status != "skipped",
    )
    review_input_status, review_input_detail = _review_input_summaries_actionability(
        root,
        analysis_brief,
        inventory,
    )
    add_check(
        "review_input_summaries_actionability",
        review_input_status,
        review_input_detail,
        required=review_input_status != "skipped",
    )
    consistency_status, consistency_detail = _problem_summary_input_consistency(
        analysis_brief,
        inventory,
    )
    add_check(
        "problem_summary_input_consistency",
        consistency_status,
        consistency_detail,
        required=consistency_status != "skipped",
    )
    prompt_status, prompt_detail = _prompt_source_visibility_actionability(
        root,
        analysis_brief,
        inventory,
    )
    add_check(
        "prompt_source_visibility_actionability",
        prompt_status,
        prompt_detail,
        required=prompt_status != "skipped",
    )
    current_run_analysis_ready = all(
        check["status"] == "ok"
        for check in checks.values()
        if check.get("required") is True
    )
    failed_required_checks = _failed_check_names(checks, required=True)
    failed_optional_checks = _failed_check_names(checks, required=False)
    delegation_ready = (
        checks["analysis_brief_present"]["status"] == "ok"
        and checks["inventory_artifact_present"]["status"] == "ok"
    )
    typed_readiness = _typed_postrun_readiness_payload(
        root,
        inventory,
        analysis_brief=analysis_brief,
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
        "run_root": str(root),
        "postrun_acceptance_dir": str(report_dir),
        "delegation_ready": delegation_ready,
        "current_run_analysis_ready": current_run_analysis_ready,
        "failed_required_checks": failed_required_checks,
        "failed_optional_checks": failed_optional_checks,
        "checks": checks,
    }
    if include_typed_summary:
        payload["typed_readiness_summary"] = typed_readiness
    return payload


def _typed_postrun_readiness_payload(
    root: Path,
    inventory: Mapping[str, Any],
    *,
    analysis_brief: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the Design N typed-port summary without changing legacy output."""

    typed_inventory = dict(inventory)
    if analysis_brief:
        typed_inventory["analysis_brief"] = analysis_brief
    return (
        PostrunReadinessOrchestrator(
            MappingPostrunInventoryPort(typed_inventory),
            problem_reviews=ProblemReviewRegistry(
                {
                    "warehouse_delivery": WarehouseFollowupReviewPort(),
                }
            ),
        )
        .build(root)
        .to_payload()
    )


def _failed_check_names(
    checks: Mapping[str, Mapping[str, Any]],
    *,
    required: bool,
) -> list[str]:
    return [
        name
        for name, check in sorted(checks.items())
        if check.get("required") is required
        and check.get("status") not in {"ok", "skipped"}
    ]


def _with_live_launcher_markers(
    root: Path,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Overlay final launcher marker counts that may be written after inventory."""

    updated = dict(inventory)
    launcher = dict(_mapping_or_empty(updated.get("launcher")))
    launcher["run_log_markers"] = _merged_marker_counts(
        _mapping_or_empty(launcher.get("run_log_markers")),
        _marker_counts_from_file(root / "run.log", RUN_LOG_MARKERS),
    )
    launcher["exit_markers"] = _merged_marker_counts(
        _mapping_or_empty(launcher.get("exit_markers")),
        _marker_counts_from_file(root / "exit.txt", EXIT_MARKERS),
    )
    updated["launcher"] = launcher
    return updated


def _marker_counts_from_file(path: Path, markers: tuple[str, ...]) -> dict[str, int]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    marker_set = set(markers)
    counts: Counter[str] = Counter()
    for raw_line in text.splitlines():
        key = raw_line.split(":", 1)[0].strip()
        if key in marker_set:
            counts[key] += 1
    return dict(sorted(counts.items()))


def _merged_marker_counts(
    stored: Mapping[str, Any],
    live: Mapping[str, Any],
) -> dict[str, int]:
    keys = set(stored) | set(live)
    merged: dict[str, int] = {}
    for key in sorted(keys):
        merged[key] = max(
            _int_or_zero(stored.get(key)),
            _int_or_zero(live.get(key)),
        )
    return merged


def render_markdown(readiness: Mapping[str, Any]) -> str:
    lines = [
        f"# Postrun Acceptance Readiness: {Path(str(readiness['run_root'])).name}",
        "",
        "- Scope: report-only delegated-analysis readiness.",
        "- Boundary: no DecisionFeatures, Protocol gates, promotion, scheduler, "
        "or solver behavior is changed.",
        f"- Delegation ready: `{readiness.get('delegation_ready')}`",
        f"- Current-run analysis ready: `{readiness.get('current_run_analysis_ready')}`",
        f"- Failed required checks: `{_inline_detail(readiness.get('failed_required_checks'))}`",
        "",
        "## Checks",
        "| Check | Required | Status | Detail |",
        "|---|---:|---|---|",
    ]
    checks = readiness.get("checks")
    if isinstance(checks, Mapping):
        for name, check in sorted(checks.items()):
            if not isinstance(check, Mapping):
                continue
            lines.append(
                "| {name} | {required} | {status} | `{detail}` |".format(
                    name=name,
                    required=check.get("required"),
                    status=check.get("status"),
                    detail=_inline_detail(check.get("detail")),
                )
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_root", help="Run root to inspect.")
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Output format.",
    )
    parser.add_argument(
        "--require-current-run-ready",
        action="store_true",
        help="Exit 64 unless current-run analysis readiness passes.",
    )
    args = parser.parse_args(argv)

    readiness = build_readiness(args.run_root)
    if args.format == "json":
        print(_stable_json(readiness), end="")
    else:
        print(render_markdown(readiness), end="")
    if args.require_current_run_ready and not readiness["current_run_analysis_ready"]:
        return UNREADY_EXIT
    return 0


def _brief_current_run_evidence(brief: Mapping[str, Any]) -> bool:
    lifecycle = _mapping_or_empty(brief.get("lifecycle"))
    phase4 = _mapping_or_empty(brief.get("phase4_evidence_coverage"))
    return (
        lifecycle.get("current_run_evidence") is True
        and phase4.get("current_run_evidence") is True
    )


def _problem_summary_actionability(
    brief: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> tuple[str, Any]:
    return "skipped", {
        "reason": "problem_owned_summaries_are_report_only",
        "problem_family": _problem_family(brief, inventory),
        "summary_keys_present": [
            key
            for key in ("warehouse_followup_summary",)
            if isinstance(brief.get(key), Mapping)
        ],
    }


def _problem_family(
    brief: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> str | None:
    launcher = _mapping_or_empty(inventory.get("launcher"))
    inventory_contract = _mapping_or_empty(launcher.get("prepared_run_contract"))
    if isinstance(inventory_contract.get("problem_family"), str):
        return str(inventory_contract["problem_family"])
    brief_contract = _mapping_or_empty(brief.get("prepared_run_contract"))
    if isinstance(brief_contract.get("problem_family"), str):
        return str(brief_contract["problem_family"])
    for key in ("warehouse_followup_summary",):
        summary = _mapping_or_empty(brief.get(key))
        if summary.get("available") is True and isinstance(
            summary.get("problem_family"),
            str,
        ):
            return str(summary["problem_family"])
    return None


def _review_input_summaries_actionability(
    run_root: Path,
    brief: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> tuple[str, Any]:
    del run_root
    return "skipped", {
        "reason": "problem_owned_review_inputs_are_report_only",
        "problem_family": _problem_family(brief, inventory),
    }


def _problem_summary_input_consistency(
    brief: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> tuple[str, Any]:
    return "skipped", {
        "reason": "problem_owned_summary_consistency_is_report_only",
        "problem_family": _problem_family(brief, inventory),
    }


def _prompt_source_visibility_actionability(
    run_root: Path,
    brief: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> tuple[str, Any]:
    problem_family = _problem_family(brief, inventory)
    if problem_family not in {"warehouse_delivery", "cvrp"}:
        return "skipped", {
            "reason": "not_problem_specific_agentic_summary",
            "problem_family": problem_family,
        }

    expected = _prompt_context_visibility_summary(run_root, inventory)
    check = (
        PostrunPromptVisibilityAcceptancePort()
        .summarize(
            problem_family=problem_family,
            summary=_mapping_or_empty(brief.get("prompt_context_visibility_summary")),
            expected=expected,
        )
        .checks[0]
    )
    return check.status, check.detail


def _boundary_marker_failures(
    prefix: str,
    payload: Mapping[str, Any],
    *,
    require_quality: bool = True,
) -> list[str]:
    failures: list[str] = []
    if payload.get("report_only") is not True:
        failures.append(f"{prefix}_not_report_only")
    if require_quality and payload.get("quality_judgment") is not False:
        failures.append(f"{prefix}_quality_judgment_not_false")
    if payload.get("decision_features_excluded") is not True:
        failures.append(f"{prefix}_decision_features_not_excluded")
    return failures


def _string_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _int_or_zero(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _int_mapping(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): _int_or_zero(count) for key, count in value.items()}


def _json_comparison_value(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, sort_keys=True))
    except (TypeError, ValueError):
        return str(value)


def _summary_without_paths(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): (
                _path_signature(item)
                if str(key) == "path"
                else _summary_without_paths(item)
            )
            for key, item in sorted(value.items())
        }
    if isinstance(value, list):
        return [_summary_without_paths(item) for item in value]
    return _json_comparison_value(value)


def _path_signature(value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return _json_comparison_value(value)
    normalized = value.replace("\\", "/")
    return {"path": normalized}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _stable_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def _inline_detail(value: Any) -> str:
    text = (
        json.dumps(value, sort_keys=True)
        if isinstance(value, (dict, list))
        else str(value)
    )
    return text.replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
