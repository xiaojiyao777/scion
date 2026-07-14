#!/usr/bin/env python3
"""Check whether a prepared Scion launch root is safe to start."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
SCION_PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(SCION_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(SCION_PROJECT_DIR))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from scion.postrun.inventory.prepared_contract import (
    REMOVED_RUNTIME_COMMAND_OPTIONS,
    REMOVED_RUNTIME_ENV_KEYS,
    command_has_shell_flag,
    prepared_execution_runtime_mode,
)  # noqa: E402
from scion.postrun.handoff.prompt_context_readiness_validation import (  # noqa: E402
    check_prepared_prompt_context_readiness,
)
from scion.problems.postrun_inventory import (
    build_problem_inventory as build_inventory,
)  # noqa: E402

SCHEMA_VERSION = "scion.launch_readiness.v1"
PREPARED_HANDOFF_REBUILD_SCHEMA = "scion.prepared_handoff_rebuild.v1"
ANALYSIS_BRIEF_SCHEMA = "scion.postrun_analysis_brief.v1"
UNREADY_EXIT = 64
REPO_DIR = Path(__file__).resolve().parents[2]
PROBLEM_SPECIFIC_CONTRACT_PREFIXES = {
    "cvrp": ("cvrp_",),
    "warehouse_delivery": ("warehouse_",),
}
PREPARED_ONLY_REQUIRED_QUESTION_MARKER = (
    "Is this still a prepared-only launch root with zero current-run counters "
    "and no postrun acceptance evidence?"
)
CURRENT_RUN_REQUIRED_QUESTION_MARKER = (
    "Did the agent perform effective research, or only satisfy framework controls?"
)
PREPARED_HANDOFF_REBUILD_FAMILIES = (
    "analysis_brief",
    "inventory",
    "prompt_context_readiness",
    "launch_readiness",
)
REQUIRED_RUNTIME_GUARD_PATHS = (
    "scion/tools",
    "scion/scion/cli",
    "scion/scion/core",
    "scion/scion/lineage",
)
PROBLEM_RUNTIME_GUARD_PATHS = {
    "cvrp": (
        "scion/scion/problems/cvrp",
        "scion/problems/cvrp",
        "vrp",
    ),
    "warehouse_delivery": (
        "scion/scion/problems/warehouse_delivery",
        "scion/problems/warehouse_delivery",
        "surrogate",
    ),
}
RUN_SCRIPT_CAMPAIGN_COMMAND_MARKER = "-m scion.cli.main run"
RUN_SCRIPT_RUNTIME_GUARD_MARKERS = (
    (
        "dirty_status_check",
        'git -C "$REPO_ROOT" status --porcelain',
    ),
    ("dirty_failure_marker", "GIT_RUNTIME_DIRTY"),
    (
        "actual_commit_read",
        'git -C "$REPO_ROOT" rev-parse --short HEAD',
    ),
    (
        "commit_compare",
        'if [[ "$_ACTUAL_GIT_COMMIT" != "$GIT_COMMIT" ]]; then',
    ),
    ("commit_mismatch_failure_marker", "GIT_COMMIT_MISMATCH"),
)
RUN_SCRIPT_RUNTIME_GUARD_ECHO_MARKERS = {
    "dirty_failure_marker",
    "commit_mismatch_failure_marker",
}


def build_readiness(
    run_root: Path | str,
    *,
    completion_preflight: bool = False,
    guarded_wrapper_launch: bool = False,
    api_key: str | None = None,
    api_key_env: str | None = None,
    timeout_sec: float = 60.0,
) -> dict[str, Any]:
    """Return report-only launch-readiness checks for a prepared root."""

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

    inventory = build_inventory(root)
    lifecycle = inventory.get("lifecycle") if isinstance(inventory, dict) else {}
    validity = inventory.get("validity") if isinstance(inventory, dict) else {}
    counters = inventory.get("counters") if isinstance(inventory, dict) else {}
    launcher = inventory.get("launcher") if isinstance(inventory, dict) else {}
    prepared_contract = (
        launcher.get("prepared_run_contract") if isinstance(launcher, dict) else {}
    )
    contract_checks = (
        prepared_contract.get("checks") if isinstance(prepared_contract, dict) else {}
    )
    postrun_counts = (
        inventory.get("postrun_reports", {}).get("counts", {})
        if isinstance(inventory, dict)
        else {}
    )
    proposal_runtime = (
        inventory.get("proposal_runtime") if isinstance(inventory, dict) else {}
    )

    add_check("inventory_loaded", "ok", str(root))
    add_check(
        "proposal_runtime_mode_resolved",
        (
            "ok"
            if isinstance(proposal_runtime, dict)
            and proposal_runtime.get("status") == "resolved"
            else "failed"
        ),
        proposal_runtime,
    )
    add_check(
        "prepared_only_not_started",
        (
            "ok"
            if lifecycle.get("prepared_only") is True
            and lifecycle.get("pre_campaign_completion_preflight_failed") is not True
            and validity.get("run_validity_status") == "prepared_only"
            and validity.get("run_completeness_status") == "not_started"
            else "failed"
        ),
        {
            "lifecycle": lifecycle,
            "validity": validity,
        },
    )
    add_check(
        "zero_current_run_counters",
        (
            "ok"
            if all(
                _int_or_zero(counters.get(key)) == 0
                for key in (
                    "effective_rounds_completed",
                    "formal_screened_candidates",
                    "protocol_evaluated_candidates",
                    "screened_experiments",
                    "proposal_attempts_total",
                )
            )
            else "failed"
        ),
        counters,
    )
    add_check(
        "prepared_contract_complete",
        "ok" if prepared_contract.get("contract_complete") is True else "failed",
        prepared_contract.get("manifest_path"),
    )
    add_check(
        "git_runtime_consistent",
        _contract_check_status(contract_checks, "git_runtime_consistent"),
        _contract_check_detail(contract_checks, "git_runtime_consistent"),
    )
    add_check(
        "git_runtime_worktree_clean",
        *_git_runtime_worktree_clean(prepared_contract),
    )
    add_check(
        "git_runtime_guard_commit_consistent",
        *_git_runtime_guard_commit_consistent(prepared_contract),
    )
    add_check(
        "runtime_guard_paths_cover_launch_tools",
        *_runtime_guard_paths_cover_launch_tools(prepared_contract),
    )
    problem_runtime_status, problem_runtime_detail, problem_runtime_required = (
        _runtime_guard_paths_cover_problem_runtime(prepared_contract)
    )
    add_check(
        "runtime_guard_paths_cover_problem_runtime",
        problem_runtime_status,
        problem_runtime_detail,
        required=problem_runtime_required,
    )
    add_check(
        "postrun_families_complete",
        _contract_check_status(contract_checks, "postrun_families_complete"),
        _contract_check_detail(contract_checks, "postrun_families_complete"),
    )
    problem_specific_status, problem_specific_detail, problem_specific_required = (
        _problem_specific_prepared_handoff_check(prepared_contract)
    )
    add_check(
        "problem_specific_prepared_handoff",
        problem_specific_status,
        problem_specific_detail,
        required=problem_specific_required,
    )
    add_check(
        "prepared_handoff_rebuild_declared_outputs_present",
        *_prepared_handoff_rebuild_declared_outputs_present(root),
    )
    add_check(
        "prompt_context_readiness_complete",
        *_prompt_context_readiness_check(root),
    )
    add_check(
        "prepared_analysis_brief_current",
        *_prepared_analysis_brief_check(root),
    )
    add_check(
        "analysis_brief_prepared_contract_consistency",
        *_prepared_analysis_brief_contract_consistency_check(root, prepared_contract),
    )

    run_sh = root / "run.sh"
    add_check("run_script_present", "ok" if run_sh.is_file() else "failed", str(run_sh))
    add_check(
        "run_script_runtime_guard_contract_consistency",
        *_run_script_runtime_guard_contract_consistency(
            root,
            run_sh,
            prepared_contract,
        ),
    )
    add_check(
        "run_script_syntax",
        *_run_script_syntax(run_sh),
    )
    add_check(
        "run_script_runtime_guard_enforced",
        *_run_script_runtime_guard_enforced(run_sh),
    )
    add_check(
        "run_script_runtime_guard_failure_reports",
        *_run_script_runtime_guard_failure_reports(run_sh),
    )
    add_check(
        "run_script_preflight_failure_reports",
        *_run_script_preflight_failure_reports(run_sh),
    )
    add_check(
        "run_script_launch_env_failure_reports",
        *_run_script_launch_env_failure_reports(run_sh),
    )
    add_check(
        "launch_env_secret_permissions",
        *_launch_env_secret_permissions(root),
    )
    add_check(
        "run_script_scion_dir_failure_reports",
        *_run_script_scion_dir_failure_reports(run_sh),
    )
    add_check(
        "run_script_completion_preflight_enforced",
        *_run_script_completion_preflight_enforced(root, run_sh),
    )
    add_check(
        "run_script_campaign_execution_marker_enforced",
        *_run_script_campaign_execution_marker_enforced(run_sh),
    )
    add_check(
        "run_script_pythonpath_enforced",
        *_run_script_pythonpath_enforced(root, run_sh),
    )
    add_check(
        "run_script_model_route_enforced",
        *_run_script_model_route_enforced(root, run_sh, prepared_contract),
    )
    add_check(
        "run_script_campaign_contract_consistency",
        *_run_script_campaign_contract_consistency(root, run_sh, prepared_contract),
    )
    add_check(
        "manifest_campaign_command_cli_parse",
        *_manifest_campaign_command_cli_parse(root, prepared_contract),
    )
    add_check(
        "run_script_direct_runtime_controls_absent",
        *_run_script_direct_runtime_controls_absent(
            root,
            run_sh,
            prepared_contract,
        ),
    )
    add_check(
        "formal_research_target_unbound",
        *_formal_research_target_unbound(root, prepared_contract),
    )
    add_check(
        "formal_research_clean_start",
        *_formal_research_clean_start(root, prepared_contract),
    )
    add_check(
        "run_script_strict_postrun_rebuild",
        *_run_script_strict_postrun_rebuild(run_sh),
    )
    add_check(
        "run_script_strict_postrun_readiness",
        *_run_script_strict_postrun_readiness(run_sh),
    )
    add_check(
        "run_script_postrun_reports_after_campaign",
        *_run_script_postrun_reports_after_campaign(run_sh),
    )
    add_check(
        "run_script_data_root_failure_reports",
        *_run_script_data_root_failure_reports(run_sh),
    )
    add_check(
        "run_script_api_key_env_failure_reports",
        *_run_script_api_key_env_failure_reports(run_sh),
    )
    add_check(
        "not_already_started",
        "ok" if not (root / "exit.txt").exists() else "failed",
        str(root / "exit.txt"),
    )
    add_check(
        "postrun_acceptance_not_present",
        "ok" if not (root / "postrun_acceptance").exists() else "failed",
        {
            "path": str(root / "postrun_acceptance"),
            "counts": postrun_counts,
        },
    )

    if completion_preflight:
        add_check(
            "completion_preflight",
            *_completion_preflight_check(
                prepared_contract=prepared_contract,
                api_key=api_key,
                api_key_env=api_key_env,
                timeout_sec=timeout_sec,
            ),
        )
    else:
        add_check(
            "completion_preflight",
            "skipped",
            "pass --completion-preflight to require a real chat completion",
            required=False,
        )

    static_ready = all(
        item["status"] == "ok"
        for name, item in checks.items()
        if item.get("required") is True and name != "completion_preflight"
    )
    completion_ready = (
        checks["completion_preflight"]["status"] == "ok"
        if completion_preflight
        else True
    )
    ready = bool(static_ready and completion_ready)
    launch_ready = bool(static_ready and completion_preflight and completion_ready)
    guarded_wrapper_launch_ready = bool(
        static_ready
        and checks["run_script_completion_preflight_enforced"]["status"] == "ok"
        and checks["run_script_campaign_execution_marker_enforced"]["status"]
        == "ok"
    )
    failed_required_checks = _failed_check_names(checks, required=True)
    failed_static_required_checks = [
        name for name in failed_required_checks if name != "completion_preflight"
    ]
    failed_optional_checks = _failed_check_names(checks, required=False)
    completion_summary = _completion_preflight_summary(
        checks.get("completion_preflight")
    )
    completion_action = (
        completion_summary.get("operator_action")
        if isinstance(completion_summary.get("operator_action"), dict)
        else {}
    )
    runtime_guard_summary = _runtime_guard_commit_summary(
        checks.get("git_runtime_guard_commit_consistent")
    )
    launch_env_summary = _launch_env_permissions_summary(
        checks.get("launch_env_secret_permissions")
    )
    campaign_marker_summary = _campaign_execution_marker_summary(
        checks.get("run_script_campaign_execution_marker_enforced")
    )
    launch_blockers = _launch_blockers(
        static_ready=static_ready,
        completion_preflight=completion_preflight,
        completion_ready=completion_ready,
        failed_static_required_checks=failed_static_required_checks,
    )
    guarded_wrapper_launch_blockers = list(failed_static_required_checks)
    if guarded_wrapper_launch and not guarded_wrapper_launch_ready:
        if not guarded_wrapper_launch_blockers:
            guarded_wrapper_launch_blockers.append(
                "guarded_wrapper_launch_readiness_failed"
            )
    if guarded_wrapper_launch:
        readiness_scope = "guarded_wrapper_launch"
        ready_meaning = (
            "guarded wrapper launch readiness; run.sh owns the sole live "
            "pre-campaign completion preflight"
        )
        selected_launch_blockers = guarded_wrapper_launch_blockers
    elif completion_preflight:
        readiness_scope = "external_live_probe"
        ready_meaning = "external diagnostic live-probe readiness"
        selected_launch_blockers = launch_blockers
    else:
        readiness_scope = "prepared_audit"
        ready_meaning = "static prepared-root audit; no launch workflow selected"
        selected_launch_blockers = launch_blockers
    return {
        "schema_version": SCHEMA_VERSION,
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
        "run_root": str(root),
        "static_ready": static_ready,
        "launch_ready": launch_ready,
        "guarded_wrapper_launch_ready": guarded_wrapper_launch_ready,
        "ready": ready,
        "ready_meaning": ready_meaning,
        "readiness_scope": readiness_scope,
        "launch_blockers": launch_blockers,
        "guarded_wrapper_launch_blockers": guarded_wrapper_launch_blockers,
        "selected_launch_blockers": selected_launch_blockers,
        "guarded_wrapper_launch_selected": guarded_wrapper_launch,
        "completion_preflight_required": completion_preflight,
        "completion_preflight_summary": completion_summary,
        "completion_http_status": completion_summary.get("http_status"),
        "completion_classification": completion_summary.get("classification"),
        "completion_code": completion_summary.get("code"),
        "completion_auth_pool": completion_summary.get("auth_pool"),
        "completion_login_url": completion_summary.get("login_url"),
        "completion_next_step": completion_action.get("next_step"),
        "completion_operator_action": (
            completion_action if completion_action else None
        ),
        "runtime_guard_status": runtime_guard_summary.get("status"),
        "runtime_guard_reason": runtime_guard_summary.get("reason"),
        "prepared_runtime_commit": runtime_guard_summary.get("prepared_commit"),
        "actual_runtime_commit": runtime_guard_summary.get("actual_commit"),
        "runtime_guard_paths": runtime_guard_summary.get("runtime_guard_paths"),
        "launch_env_secret_permissions": launch_env_summary.get("status"),
        "launch_env_mode": launch_env_summary.get("mode"),
        "campaign_execution_marker_summary": campaign_marker_summary,
        "campaign_execution_marker_status": campaign_marker_summary.get("status"),
        "campaign_execution_marker_ok": campaign_marker_summary.get("ok"),
        "campaign_execution_marker_failure_reasons": campaign_marker_summary.get(
            "failure_reasons"
        ),
        "campaign_execution_marker_position": campaign_marker_summary.get(
            "marker_position"
        ),
        "campaign_execution_marker_preflight_failure_exit_position": (
            campaign_marker_summary.get("preflight_failure_exit_position")
        ),
        "campaign_execution_marker_campaign_command_position": (
            campaign_marker_summary.get("campaign_command_position")
        ),
        "failed_required_checks": failed_required_checks,
        "failed_static_required_checks": failed_static_required_checks,
        "failed_optional_checks": failed_optional_checks,
        "checks": checks,
    }


def _launch_blockers(
    *,
    static_ready: bool,
    completion_preflight: bool,
    completion_ready: bool,
    failed_static_required_checks: list[str],
) -> list[str]:
    blockers = list(failed_static_required_checks)
    if not completion_preflight:
        blockers.append("completion_preflight_not_run")
    elif not completion_ready:
        blockers.append("completion_preflight")
    if not static_ready and not blockers:
        blockers.append("static_readiness_failed")
    return blockers


def _failed_check_names(
    checks: dict[str, dict[str, Any]],
    *,
    required: bool,
) -> list[str]:
    return [
        name
        for name, item in sorted(checks.items())
        if item.get("required") is required
        and item.get("status") not in {"ok", "skipped"}
    ]


def _completion_preflight_summary(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {
            "status": "missing",
            "required": False,
            "ok": False,
        }
    detail = item.get("detail")
    detail_map = detail if isinstance(detail, dict) else {}
    chat = detail_map.get("chat")
    chat_map = chat if isinstance(chat, dict) else {}
    auth_status = detail_map.get("auth_status")
    auth_status_map = auth_status if isinstance(auth_status, dict) else {}
    auth_pool = auth_status_map.get("pool")
    action = detail_map.get("operator_action")
    action_map = action if isinstance(action, dict) else {}

    summary: dict[str, Any] = {
        "status": item.get("status"),
        "required": bool(item.get("required")),
        "ok": item.get("status") == "ok",
        "http_status": chat_map.get("http_status"),
        "classification": chat_map.get("classification"),
        "code": chat_map.get("code"),
        "message": chat_map.get("message"),
        "auth_pool": auth_pool if isinstance(auth_pool, dict) else None,
        "model": detail_map.get("model") or action_map.get("model"),
        "base_url": detail_map.get("base_url") or action_map.get("base_url"),
        "login_url": detail_map.get("login_url") or action_map.get("login_url"),
    }
    if action_map:
        summary["operator_action"] = action_map
    return summary


def _runtime_guard_commit_summary(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {
            "status": "missing",
            "reason": None,
            "prepared_commit": None,
            "actual_commit": None,
            "runtime_guard_paths": None,
        }
    detail = item.get("detail")
    detail_map = detail if isinstance(detail, dict) else {}
    return {
        "status": item.get("status"),
        "reason": detail_map.get("reason"),
        "prepared_commit": detail_map.get("prepared_commit"),
        "actual_commit": detail_map.get("actual_commit"),
        "runtime_guard_paths": detail_map.get("runtime_guard_paths"),
    }


def _launch_env_permissions_summary(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {
            "status": "missing",
            "mode": None,
        }
    detail = item.get("detail")
    detail_map = detail if isinstance(detail, dict) else {}
    return {
        "status": item.get("status"),
        "mode": detail_map.get("mode"),
    }


def _campaign_execution_marker_summary(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {
            "status": "missing",
            "ok": False,
            "failure_reasons": [],
            "marker_position": None,
            "preflight_failure_exit_position": None,
            "campaign_command_position": None,
        }
    detail = item.get("detail")
    detail_map = detail if isinstance(detail, dict) else {}
    raw_failures = detail_map.get("failures")
    failures = raw_failures if isinstance(raw_failures, list) else []
    failure_reasons = [
        str(failure.get("reason"))
        for failure in failures
        if isinstance(failure, dict) and failure.get("reason")
    ]
    marker_positions = {
        "file": detail_map.get("marker_file_position"),
        "schema": detail_map.get("marker_schema_position"),
        "log": detail_map.get("marker_log_position"),
    }
    executable_positions = [
        value
        for value in marker_positions.values()
        if isinstance(value, int) and value >= 0
    ]
    return {
        "status": item.get("status"),
        "required": bool(item.get("required")),
        "ok": item.get("status") == "ok",
        "failure_reasons": failure_reasons,
        "marker_position": min(executable_positions) if executable_positions else None,
        "marker_positions": marker_positions,
        "preflight_proxy_position": detail_map.get("preflight_proxy_position"),
        "preflight_failure_exit_position": detail_map.get(
            "preflight_failure_exit_position"
        ),
        "campaign_command_position": detail_map.get("campaign_command_position"),
        "ignored_non_executable_marker_counts": detail_map.get(
            "ignored_non_executable_marker_counts"
        ),
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Launch Readiness: {Path(str(report['run_root'])).name}",
        "",
        "- Schema: `scion.launch_readiness.v1`",
        "- Scope: report-only prepared-root launch check.",
        "- Boundary: this report does not mutate campaign state, scheduler state, "
        "promotion state, `DecisionFeatures`, or Protocol evidence.",
        f"- Static ready: `{_display(report.get('static_ready'))}`",
        "- Guarded wrapper launch ready: "
        f"`{_display(report.get('guarded_wrapper_launch_ready'))}`",
        "- External live-probe ready: "
        f"`{_display(report.get('launch_ready'))}`",
        f"- Readiness scope: `{_display(report.get('readiness_scope'))}`",
        f"- Legacy `ready` meaning: {_display(report.get('ready_meaning'))}",
        "- External live-probe blockers: "
        f"`{_display(report.get('launch_blockers'))}`",
        "- Guarded wrapper blockers: "
        f"`{_display(report.get('guarded_wrapper_launch_blockers'))}`",
        "- Selected workflow blockers: "
        f"`{_display(report.get('selected_launch_blockers'))}`",
        f"- Completion preflight required: `{_display(report.get('completion_preflight_required'))}`",
        "- Campaign execution marker: "
        f"`{_display(report.get('campaign_execution_marker_status'))}`",
        "- Campaign execution marker failures: "
        f"`{_display(report.get('campaign_execution_marker_failure_reasons'))}`",
        f"- Failed required checks: `{_display(report.get('failed_required_checks'))}`",
        "",
        "## Checks",
        "| Check | Status | Required | Detail |",
        "|---|---:|---:|---|",
    ]
    checks = report.get("checks")
    if isinstance(checks, dict):
        for name, item in sorted(checks.items()):
            if not isinstance(item, dict):
                continue
            lines.append(
                "| {name} | {status} | {required} | {detail} |".format(
                    name=name,
                    status=_display(item.get("status")),
                    required=_display(item.get("required")),
                    detail=_display(item.get("detail")),
                )
            )
    action_lines = _completion_preflight_action_lines(report)
    if action_lines:
        lines.extend(["", "## Completion Preflight Action", *action_lines])
    lines.extend(
        [
            "",
            "## Launch Rule",
            "- `readiness_scope=prepared_audit` is not proof that the provider is live.",
            "- When `guarded_wrapper_launch_ready=true`, an explicit operator "
            "decision may start `run.sh`; its enforced pre-campaign guard owns the "
            "single live completion preflight and persists the receipt before any "
            "campaign command.",
            "- Do not run an external `--completion-preflight` immediately before "
            "starting the guarded wrapper; that duplicates the provider request.",
            "- `launch_ready=true` reports an external diagnostic live probe. It is "
            "not required for the guarded-wrapper workflow.",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_root")
    parser.add_argument(
        "--completion-preflight",
        action="store_true",
        help="Require a real completion from the prepared model before reporting ready.",
    )
    parser.add_argument(
        "--require-launch-ready",
        action="store_true",
        help=(
            "Imply --completion-preflight and exit zero only when launch_ready=true."
        ),
    )
    parser.add_argument(
        "--require-guarded-wrapper-launch-ready",
        action="store_true",
        help=(
            "Do not call the provider; exit zero only when the prepared run.sh "
            "is statically ready and enforces the sole live pre-campaign "
            "completion preflight."
        ),
    )
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--api-key-env", default=None)
    parser.add_argument("--timeout-sec", type=float, default=60.0)
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="text",
        help="Output format.",
    )
    args = parser.parse_args(argv)
    if args.api_key and args.api_key_env:
        parser.error("--api-key and --api-key-env are mutually exclusive")
    if args.require_guarded_wrapper_launch_ready and (
        args.completion_preflight or args.require_launch_ready
    ):
        parser.error(
            "--require-guarded-wrapper-launch-ready is mutually exclusive with "
            "--completion-preflight/--require-launch-ready"
        )
    if args.timeout_sec <= 0:
        parser.error("--timeout-sec must be positive")

    report = build_readiness(
        args.run_root,
        completion_preflight=args.completion_preflight or args.require_launch_ready,
        guarded_wrapper_launch=args.require_guarded_wrapper_launch_ready,
        api_key=args.api_key,
        api_key_env=args.api_key_env,
        timeout_sec=args.timeout_sec,
    )
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_markdown(report), end="")
    if args.require_launch_ready:
        return 0 if report["launch_ready"] else UNREADY_EXIT
    if args.require_guarded_wrapper_launch_ready:
        return 0 if report["guarded_wrapper_launch_ready"] else UNREADY_EXIT
    return 0 if report["ready"] else UNREADY_EXIT


def _contract_check_status(checks: Any, name: str) -> str:
    if not isinstance(checks, dict):
        return "failed"
    item = checks.get(name)
    if not isinstance(item, dict):
        return "failed"
    return "ok" if item.get("passed") is True else "failed"


def _contract_check_detail(checks: Any, name: str) -> Any:
    if not isinstance(checks, dict):
        return ""
    item = checks.get(name)
    return item.get("detail") if isinstance(item, dict) else ""


def _runtime_guard_paths_cover_launch_tools(prepared_contract: Any) -> tuple[str, Any]:
    if not isinstance(prepared_contract, dict):
        return "failed", {"reason": "missing_prepared_contract"}
    git = prepared_contract.get("git")
    git_dict = git if isinstance(git, dict) else {}
    raw_paths = str(git_dict.get("runtime_guard_paths") or "").strip()
    pathspecs = _runtime_guard_pathspecs(raw_paths)
    missing = [
        required
        for required in REQUIRED_RUNTIME_GUARD_PATHS
        if not _runtime_guard_path_covers(pathspecs, required)
    ]
    return (
        "ok" if not missing else "failed",
        {
            "runtime_guard_paths": raw_paths,
            "required_paths": list(REQUIRED_RUNTIME_GUARD_PATHS),
            "missing_required_paths": missing,
        },
    )


def _git_runtime_worktree_clean(prepared_contract: Any) -> tuple[str, Any]:
    if not isinstance(prepared_contract, dict):
        return "failed", {"reason": "missing_prepared_contract"}
    git = prepared_contract.get("git")
    git_dict = git if isinstance(git, dict) else {}
    raw_paths = str(git_dict.get("runtime_guard_paths") or "").strip()
    pathspecs = _runtime_guard_pathspecs(raw_paths)
    if not pathspecs:
        return (
            "failed",
            {
                "reason": "missing_runtime_guard_paths",
                "runtime_guard_paths": raw_paths,
            },
        )
    result = subprocess.run(
        ["git", "-C", str(REPO_DIR), "status", "--porcelain"],
        text=True,
        capture_output=True,
        check=False,
    )
    detail: dict[str, Any] = {
        "repo_dir": str(REPO_DIR),
        "runtime_guard_paths": raw_paths,
        "pathspecs": pathspecs,
        "cleanliness_scope": "whole_repository",
        "git_status_exit_code": result.returncode,
        "dirty_entries": result.stdout.splitlines(),
    }
    if result.returncode != 0:
        detail["reason"] = "git_status_failed"
        detail["stderr"] = result.stderr
        return "failed", detail
    if result.stdout.strip():
        detail["reason"] = "worktree_dirty"
        return "failed", detail
    return "ok", detail


def _git_runtime_guard_commit_consistent(prepared_contract: Any) -> tuple[str, Any]:
    if not isinstance(prepared_contract, dict):
        return "failed", {"reason": "missing_prepared_contract"}
    git = prepared_contract.get("git")
    git_dict = git if isinstance(git, dict) else {}
    prepared_commit = str(git_dict.get("commit") or "").strip()
    raw_paths = str(git_dict.get("runtime_guard_paths") or "").strip()
    pathspecs = _runtime_guard_pathspecs(raw_paths)
    detail: dict[str, Any] = {
        "repo_dir": str(REPO_DIR),
        "prepared_commit": prepared_commit,
        "runtime_guard_paths": raw_paths,
        "pathspecs": pathspecs,
    }
    if not prepared_commit:
        detail["reason"] = "missing_prepared_git_commit"
        return "failed", detail
    if not pathspecs:
        detail["reason"] = "missing_runtime_guard_paths"
        return "failed", detail
    head_result = subprocess.run(
        ["git", "-C", str(REPO_DIR), "rev-parse", "--short", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    detail["git_rev_parse_exit_code"] = head_result.returncode
    if head_result.returncode != 0:
        detail["reason"] = "git_rev_parse_failed"
        detail["stderr"] = head_result.stderr
        return "failed", detail
    actual_commit = head_result.stdout.strip()
    detail["actual_commit"] = actual_commit
    if actual_commit == prepared_commit:
        detail["reason"] = "runtime_guard_commit_matches"
        return "ok", detail
    detail["reason"] = "prepared_commit_mismatch"
    return "failed", detail


def _runtime_guard_paths_cover_problem_runtime(
    prepared_contract: Any,
) -> tuple[str, Any, bool]:
    if not isinstance(prepared_contract, dict):
        return "failed", {"reason": "missing_prepared_contract"}, True
    problem_family = str(prepared_contract.get("problem_family") or "")
    required_paths = PROBLEM_RUNTIME_GUARD_PATHS.get(problem_family)
    if not required_paths:
        return (
            "skipped",
            {
                "problem_family": problem_family,
                "reason": "no_problem_specific_runtime_guard_requirements",
            },
            False,
        )
    git = prepared_contract.get("git")
    git_dict = git if isinstance(git, dict) else {}
    raw_paths = str(git_dict.get("runtime_guard_paths") or "").strip()
    pathspecs = _runtime_guard_pathspecs(raw_paths)
    missing = [
        required
        for required in required_paths
        if not _runtime_guard_path_covers(pathspecs, required)
    ]
    return (
        "ok" if not missing else "failed",
        {
            "problem_family": problem_family,
            "runtime_guard_paths": raw_paths,
            "required_paths": list(required_paths),
            "missing_required_paths": missing,
        },
        True,
    )


def _runtime_guard_pathspecs(raw_paths: str) -> list[str]:
    try:
        return shlex.split(raw_paths)
    except ValueError:
        return raw_paths.split()


def _runtime_guard_path_covers(pathspecs: list[str], required: str) -> bool:
    required = required.strip("/")
    includes: list[str] = []
    excludes: list[str] = []
    for pathspec in pathspecs:
        normalized = _normalize_runtime_guard_pathspec(pathspec)
        if not normalized:
            continue
        if normalized[0] == "exclude":
            excludes.append(normalized[1])
        else:
            includes.append(normalized[1])
    if any(
        _runtime_guard_exclude_affects_required(excluded, required)
        for excluded in excludes
    ):
        return False
    return any(
        _runtime_guard_include_covers_required(included, required)
        for included in includes
    )


def _normalize_runtime_guard_pathspec(pathspec: str) -> tuple[str, str] | None:
    text = str(pathspec or "").strip()
    if not text:
        return None
    if text.startswith(":(exclude)"):
        value = text[len(":(exclude)") :].strip("/")
        return ("exclude", value) if value else None
    if text.startswith(":!"):
        value = text[2:].strip("/")
        return ("exclude", value) if value else None
    if text.startswith(":("):
        return None
    value = text.strip("/")
    return ("include", value) if value else None


def _runtime_guard_include_covers_required(included: str, required: str) -> bool:
    if included in {".", required}:
        return True
    return required.startswith(f"{included}/")


def _runtime_guard_exclude_affects_required(excluded: str, required: str) -> bool:
    if excluded == required:
        return True
    if required.startswith(f"{excluded}/"):
        return True
    return excluded.startswith(f"{required}/")


def _problem_specific_prepared_handoff_check(
    prepared_contract: Any,
) -> tuple[str, Any, bool]:
    if not isinstance(prepared_contract, dict):
        return (
            "failed",
            {"reason": "missing_prepared_contract"},
            True,
        )
    problem_family = prepared_contract.get("problem_family")
    prefixes = PROBLEM_SPECIFIC_CONTRACT_PREFIXES.get(str(problem_family))
    if not prefixes:
        return (
            "skipped",
            {
                "problem_family": problem_family,
                "reason": "no_problem_specific_prepared_handoff_requirements",
            },
            False,
        )

    checks = prepared_contract.get("checks")
    if not isinstance(checks, dict):
        return (
            "failed",
            {
                "problem_family": problem_family,
                "reason": "missing_prepared_contract_checks",
            },
            True,
        )

    selected: dict[str, dict[str, Any]] = {}
    failed: list[str] = []
    for name, item in sorted(checks.items()):
        if not any(str(name).startswith(prefix) for prefix in prefixes):
            continue
        if not isinstance(item, dict):
            passed = False
            detail: Any = ""
        else:
            passed = item.get("passed") is True
            detail = item.get("detail")
        selected[str(name)] = {
            "passed": passed,
            "detail": detail,
        }
        if not passed:
            failed.append(str(name))

    if not selected:
        return (
            "failed",
            {
                "problem_family": problem_family,
                "reason": "missing_problem_specific_prepared_contract_checks",
                "required_prefixes": list(prefixes),
            },
            True,
        )
    return (
        "ok" if not failed else "failed",
        {
            "problem_family": problem_family,
            "failed_checks": failed,
            "checks": selected,
        },
        True,
    )


def _run_script_syntax(run_sh: Path) -> tuple[str, Any]:
    if not run_sh.is_file():
        return "failed", str(run_sh)
    result = subprocess.run(
        ["bash", "-n", str(run_sh)],
        text=True,
        capture_output=True,
        check=False,
    )
    detail = (result.stderr or result.stdout or "").strip()
    return ("ok" if result.returncode == 0 else "failed"), detail


def _run_script_runtime_guard_contract_consistency(
    root: Path,
    run_sh: Path,
    prepared_contract: Any,
) -> tuple[str, Any]:
    if not isinstance(prepared_contract, dict):
        return "failed", {"reason": "missing_prepared_contract"}
    git = prepared_contract.get("git")
    git_dict = git if isinstance(git, dict) else {}
    manifest_commit = str(git_dict.get("commit") or "").strip()
    manifest_paths = _normalize_runtime_guard_paths(
        str(git_dict.get("runtime_guard_paths") or "")
    )
    launch_env = root / "launch.env"
    failures: list[dict[str, Any]] = []
    try:
        launch_env_text = launch_env.read_text(encoding="utf-8")
    except OSError as exc:
        launch_env_text = ""
        failures.append(
            {
                "reason": "unable_to_read_launch_env",
                "launch_env": str(launch_env),
                "error": str(exc),
            }
        )
    try:
        run_bytes = run_sh.read_bytes()
        run_text = run_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        run_bytes = b""
        run_text = ""
        failures.append(
            {
                "reason": "unable_to_read_run_script",
                "run_script": str(run_sh),
                "error": str(exc),
            }
        )

    actual_run_script_sha256 = (
        hashlib.sha256(run_bytes).hexdigest() if run_bytes else None
    )
    launch_env_run_script_sha256 = _shell_assignment_value(
        launch_env_text,
        "RUN_SCRIPT_SHA256",
    )
    manifest = _read_json(root / "prepared_run_manifest.v1.json")
    manifest_run_script = (
        manifest.get("run_script") if isinstance(manifest, dict) else {}
    )
    manifest_run_script_sha256 = (
        manifest_run_script.get("sha256")
        if isinstance(manifest_run_script, dict)
        else None
    )
    if not launch_env_run_script_sha256 or not manifest_run_script_sha256:
        failures.append(
            {
                "reason": "run_script_digest_missing",
                "launch_env_sha256": launch_env_run_script_sha256,
                "manifest_sha256": manifest_run_script_sha256,
            }
        )
    elif not (
        launch_env_run_script_sha256
        == manifest_run_script_sha256
        == actual_run_script_sha256
    ):
        failures.append(
            {
                "reason": "run_script_digest_mismatch",
                "launch_env_sha256": launch_env_run_script_sha256,
                "manifest_sha256": manifest_run_script_sha256,
                "actual_sha256": actual_run_script_sha256,
            }
        )

    launch_env_commit = _shell_assignment_value(launch_env_text, "GIT_COMMIT")
    launch_env_paths = _normalize_runtime_guard_paths(
        _shell_assignment_value(launch_env_text, "GIT_RUNTIME_GUARD_PATHS")
    )
    run_script_commit = _shell_assignment_value(run_text, "GIT_COMMIT")
    run_script_paths = _normalize_runtime_guard_paths(
        _shell_assignment_value(run_text, "GIT_RUNTIME_GUARD_PATHS")
    )
    run_script_commit_pos = _shell_assignment_position(run_text, "GIT_COMMIT")
    run_script_paths_pos = _shell_assignment_position(
        run_text,
        "GIT_RUNTIME_GUARD_PATHS",
    )
    source_pos = _first_launch_env_source_position(run_text)
    guard_pos = _runtime_guard_start_position(run_text)

    effective_commit, effective_commit_source = _runtime_guard_effective_value(
        launch_env_commit,
        run_script_commit,
        run_script_commit_pos,
        source_pos,
        guard_pos,
    )
    effective_paths, effective_paths_source = _runtime_guard_effective_value(
        launch_env_paths,
        run_script_paths,
        run_script_paths_pos,
        source_pos,
        guard_pos,
    )

    if not manifest_commit:
        failures.append({"reason": "missing_manifest_git_commit"})
    if not manifest_paths:
        failures.append({"reason": "missing_manifest_runtime_guard_paths"})
    if launch_env_commit and launch_env_commit != manifest_commit:
        failures.append(
            {
                "reason": "launch_env_git_commit_mismatch",
                "expected": manifest_commit,
                "actual": launch_env_commit,
            }
        )
    if launch_env_paths and launch_env_paths != manifest_paths:
        failures.append(
            {
                "reason": "launch_env_runtime_guard_paths_mismatch",
                "expected": manifest_paths,
                "actual": launch_env_paths,
            }
        )
    if (
        run_script_commit
        and _runtime_guard_assignment_effective(
            run_script_commit_pos,
            source_pos,
            guard_pos,
        )
        and run_script_commit != manifest_commit
    ):
        failures.append(
            {
                "reason": "run_script_git_commit_mismatch",
                "expected": manifest_commit,
                "actual": run_script_commit,
            }
        )
    if (
        run_script_paths
        and _runtime_guard_assignment_effective(
            run_script_paths_pos,
            source_pos,
            guard_pos,
        )
        and run_script_paths != manifest_paths
    ):
        failures.append(
            {
                "reason": "run_script_runtime_guard_paths_mismatch",
                "expected": manifest_paths,
                "actual": run_script_paths,
            }
        )
    if effective_commit is None:
        failures.append({"reason": "missing_effective_git_commit"})
    elif effective_commit != manifest_commit:
        failures.append(
            {
                "reason": "effective_git_commit_mismatch",
                "expected": manifest_commit,
                "actual": effective_commit,
                "source": effective_commit_source,
            }
        )
    if effective_paths is None:
        failures.append({"reason": "missing_effective_runtime_guard_paths"})
    elif effective_paths != manifest_paths:
        failures.append(
            {
                "reason": "effective_runtime_guard_paths_mismatch",
                "expected": manifest_paths,
                "actual": effective_paths,
                "source": effective_paths_source,
            }
        )

    detail = {
        "manifest_git_commit": manifest_commit,
        "manifest_runtime_guard_paths": manifest_paths,
        "launch_env": str(launch_env),
        "run_script": str(run_sh),
        "launch_env_run_script_sha256": launch_env_run_script_sha256,
        "manifest_run_script_sha256": manifest_run_script_sha256,
        "actual_run_script_sha256": actual_run_script_sha256,
        "run_script_digest_matches": bool(
            launch_env_run_script_sha256
            and launch_env_run_script_sha256
            == manifest_run_script_sha256
            == actual_run_script_sha256
        ),
        "launch_env_git_commit": launch_env_commit,
        "launch_env_runtime_guard_paths": launch_env_paths,
        "run_script_git_commit": run_script_commit,
        "run_script_runtime_guard_paths": run_script_paths,
        "run_script_git_commit_position": run_script_commit_pos,
        "run_script_runtime_guard_paths_position": run_script_paths_pos,
        "launch_env_source_position": source_pos,
        "runtime_guard_position": guard_pos,
        "effective_git_commit": effective_commit,
        "effective_git_commit_source": effective_commit_source,
        "effective_runtime_guard_paths": effective_paths,
        "effective_runtime_guard_paths_source": effective_paths_source,
        "failures": failures,
    }
    return ("ok" if not failures else "failed"), detail


def _normalize_runtime_guard_paths(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(str(value).strip().split())


def _runtime_guard_start_position(run_text: str) -> int:
    marker = 'read -r -a _GIT_RUNTIME_GUARD_PATHS <<< "$GIT_RUNTIME_GUARD_PATHS"'
    position = run_text.find(marker)
    if position >= 0:
        return position
    return run_text.find(
        'git -C "$REPO_ROOT" status --porcelain -- "${_GIT_RUNTIME_GUARD_PATHS[@]}"'
    )


def _runtime_guard_assignment_effective(
    assignment_pos: int,
    source_pos: int,
    guard_pos: int,
) -> bool:
    if assignment_pos < 0:
        return False
    if guard_pos >= 0 and assignment_pos > guard_pos:
        return False
    return source_pos < 0 or assignment_pos > source_pos


def _runtime_guard_effective_value(
    launch_env_value: str | None,
    run_script_value: str | None,
    run_script_pos: int,
    source_pos: int,
    guard_pos: int,
) -> tuple[str | None, str]:
    if _runtime_guard_assignment_effective(run_script_pos, source_pos, guard_pos):
        return run_script_value, "run_script"
    if launch_env_value is not None:
        return launch_env_value, "launch_env"
    if run_script_value is not None and (source_pos < 0 or run_script_pos < source_pos):
        return run_script_value, "run_script_fallback"
    return None, "missing"


def _run_script_runtime_guard_enforced(run_sh: Path) -> tuple[str, Any]:
    if not run_sh.is_file():
        return "failed", {"run_script": str(run_sh), "reason": "missing_run_script"}
    try:
        text = run_sh.read_text(encoding="utf-8")
    except OSError as exc:
        return (
            "failed",
            {
                "run_script": str(run_sh),
                "reason": "unable_to_read_run_script",
                "error": str(exc),
            },
        )

    marker_positions: dict[str, int] = {}
    ignored_marker_counts: dict[str, int] = {}
    missing_markers: list[str] = []
    for name, marker in RUN_SCRIPT_RUNTIME_GUARD_MARKERS:
        position, ignored = _find_runtime_guard_marker_position(
            text,
            marker,
            allow_echo=name in RUN_SCRIPT_RUNTIME_GUARD_ECHO_MARKERS,
        )
        ignored_marker_counts[name] = ignored
        if position < 0:
            missing_markers.append(name)
        else:
            marker_positions[name] = position

    campaign_position = _campaign_command_position(text)
    markers_after_campaign = [
        name
        for name, position in sorted(marker_positions.items())
        if campaign_position >= 0 and position > campaign_position
    ]
    failures: list[dict[str, Any]] = []
    permissive_markers = [
        marker
        for marker in (
            "GIT_COMMIT_DOC_ONLY_MISMATCH_ALLOWED",
            'status --porcelain -- "${_GIT_RUNTIME_GUARD_PATHS[@]}"',
            'diff --quiet "$GIT_COMMIT" HEAD',
        )
        if marker in text
    ]
    if missing_markers:
        failures.append(
            {
                "reason": "missing_runtime_guard_markers",
                "markers": missing_markers,
            }
        )
    if campaign_position < 0:
        failures.append(
            {
                "reason": "missing_campaign_command_marker",
                "marker": RUN_SCRIPT_CAMPAIGN_COMMAND_MARKER,
            }
        )
    if markers_after_campaign:
        failures.append(
            {
                "reason": "runtime_guard_after_campaign_command",
                "markers": markers_after_campaign,
            }
        )
    if permissive_markers:
        failures.append(
            {
                "reason": "permissive_runtime_guard_present",
                "markers": permissive_markers,
            }
        )

    detail = {
        "run_script": str(run_sh),
        "campaign_command_marker": RUN_SCRIPT_CAMPAIGN_COMMAND_MARKER,
        "required_markers": [name for name, _ in RUN_SCRIPT_RUNTIME_GUARD_MARKERS],
        "missing_markers": missing_markers,
        "markers_after_campaign_command": markers_after_campaign,
        "permissive_markers": permissive_markers,
        "ignored_non_executable_marker_counts": ignored_marker_counts,
        "failures": failures,
    }
    return ("ok" if not failures else "failed"), detail


def _run_sh_contains_preflight_failure_report_path(run_sh: Path) -> bool:
    status, _detail = _run_script_preflight_failure_reports(run_sh)
    return status == "ok"


def _run_script_runtime_guard_failure_reports(run_sh: Path) -> tuple[str, Any]:
    dirty_status, dirty_detail = _run_script_status_failure_reports(
        run_sh,
        marker="GIT_RUNTIME_DIRTY",
        status_marker='"git_runtime_dirty":true',
        missing_call_reason="missing_postrun_report_call_after_git_runtime_dirty",
        missing_exit_reason="missing_git_runtime_dirty_failure_exit",
        call_after_exit_reason="postrun_report_call_after_git_runtime_dirty_exit",
        status_missing_reason="git_runtime_dirty_status_writer_missing",
        status_before_marker_reason="git_runtime_dirty_status_writer_before_marker",
        call_before_status_reason=(
            "postrun_report_call_before_git_runtime_dirty_status_writer"
        ),
    )
    mismatch_status, mismatch_detail = _run_script_status_failure_reports(
        run_sh,
        marker="GIT_COMMIT_MISMATCH",
        status_marker='"git_runtime_commit_mismatch":true',
        missing_call_reason="missing_postrun_report_call_after_git_commit_mismatch",
        missing_exit_reason="missing_git_commit_mismatch_failure_exit",
        call_after_exit_reason="postrun_report_call_after_git_commit_mismatch_exit",
        status_missing_reason="git_commit_mismatch_status_writer_missing",
        status_before_marker_reason="git_commit_mismatch_status_writer_before_marker",
        call_before_status_reason=(
            "postrun_report_call_before_git_commit_mismatch_status_writer"
        ),
    )
    detail = {
        "run_script": str(run_sh),
        "dirty_failure": dirty_detail,
        "commit_mismatch_failure": mismatch_detail,
        "failures": list(dirty_detail.get("failures", []))
        + list(mismatch_detail.get("failures", [])),
    }
    return (
        "ok" if dirty_status == "ok" and mismatch_status == "ok" else "failed",
        detail,
    )


def _run_script_preflight_failure_reports(run_sh: Path) -> tuple[str, Any]:
    failures: list[dict[str, Any]] = []
    try:
        text = run_sh.read_text(encoding="utf-8")
    except OSError as exc:
        return (
            "failed",
            {
                "run_script": str(run_sh),
                "reason": "unable_to_read_run_script",
                "error": str(exc),
            },
        )

    old_marker = '"pre_campaign_completion_preflight":"failed"'
    helper_marker = "tools/write_completion_preflight_status.py"
    helper_pos, _helper_block = _shell_command_block_containing_marker(
        text,
        helper_marker,
    )
    inline_status_pos, _inline_status_block = _shell_command_block_containing_marker(
        text,
        old_marker,
    )
    status_writers = [
        (pos, kind)
        for pos, kind in (
            (helper_pos, "helper"),
            (inline_status_pos, "inline_status"),
        )
        if pos >= 0
    ]
    writer_pos, writer_kind = (
        min(status_writers, key=lambda item: item[0]) if status_writers else (-1, None)
    )
    failure_guard_pos = text.find('if [[ "$PREFLIGHT_STATUS" -ne 0 ]]; then')
    call_search_start = failure_guard_pos if failure_guard_pos >= 0 else writer_pos
    exit_search_start = writer_pos if writer_pos >= 0 else failure_guard_pos
    call_pos = _find_line_after(
        text,
        "write_postrun_acceptance_reports",
        call_search_start,
    )
    exit_pos = _find_line_after(
        text,
        'exit "$PREFLIGHT_STATUS"',
        exit_search_start,
    )
    function_pos, ignored_function_count = _shell_function_definition_position(
        text,
        "write_postrun_acceptance_reports",
    )

    if function_pos < 0:
        failures.append({"reason": "missing_postrun_report_function"})
    if failure_guard_pos < 0:
        failures.append({"reason": "preflight_failure_guard_missing"})
    if writer_pos < 0:
        failures.append({"reason": "preflight_failure_status_writer_missing"})
    if writer_pos >= 0 and failure_guard_pos >= 0 and writer_pos < failure_guard_pos:
        failures.append({"reason": "preflight_status_writer_before_failure_guard"})
    if call_pos < 0:
        failures.append(
            {"reason": "missing_postrun_report_call_after_preflight_failure"}
        )
    if exit_pos < 0:
        failures.append({"reason": "missing_preflight_failure_exit"})
    if writer_pos >= 0 and exit_pos >= 0 and writer_pos > exit_pos:
        failures.append({"reason": "preflight_status_writer_after_exit"})
    if call_pos >= 0 and writer_pos >= 0 and call_pos < writer_pos:
        failures.append(
            {"reason": "postrun_report_call_before_preflight_status_writer"}
        )
    if call_pos >= 0 and exit_pos >= 0 and call_pos > exit_pos:
        failures.append({"reason": "postrun_report_call_after_preflight_exit"})

    detail = {
        "run_script": str(run_sh),
        "preflight_failure_guard_position": failure_guard_pos,
        "preflight_status_writer_kind": writer_kind,
        "preflight_status_writer_position": writer_pos,
        "postrun_report_function_position": function_pos,
        "ignored_non_executable_function_definition_count": ignored_function_count,
        "postrun_report_call_position": call_pos,
        "preflight_failure_exit_position": exit_pos,
        "failures": failures,
    }
    return ("ok" if not failures else "failed"), detail


def _run_script_strict_postrun_readiness(run_sh: Path) -> tuple[str, Any]:
    failures: list[dict[str, Any]] = []
    try:
        text = run_sh.read_text(encoding="utf-8")
    except OSError as exc:
        text = ""
        failures.append(
            {
                "reason": "unable_to_read_run_script",
                "run_script": str(run_sh),
                "error": str(exc),
            }
        )

    postrun_pos, postrun_block = _shell_command_block_containing_marker(
        text,
        "tools/check_postrun_acceptance.py",
    )
    postrun_has_strict_flag = command_has_shell_flag(
        postrun_block,
        "--require-current-run-ready",
    )
    readiness_marker_pos, ignored_readiness_markers = _find_executable_marker_position(
        text,
        "POSTRUN_READINESS_EXIT_STATUS",
    )
    function_pos, ignored_function_count = _shell_function_definition_position(
        text,
        "write_postrun_acceptance_reports",
    )
    if function_pos < 0:
        failures.append({"reason": "missing_postrun_report_function"})
    if postrun_pos < 0:
        failures.append({"reason": "postrun_acceptance_command_missing"})
    elif not postrun_has_strict_flag:
        failures.append({"reason": "postrun_acceptance_strict_flag_missing"})
    if readiness_marker_pos < 0:
        failures.append({"reason": "postrun_readiness_exit_status_marker_missing"})
    if (
        postrun_pos >= 0
        and readiness_marker_pos >= 0
        and readiness_marker_pos < postrun_pos
    ):
        failures.append({"reason": "postrun_readiness_exit_status_before_readiness"})

    detail = {
        "run_script": str(run_sh),
        "postrun_report_function_position": function_pos,
        "ignored_non_executable_function_definition_count": ignored_function_count,
        "postrun_acceptance_command_position": postrun_pos,
        "postrun_acceptance_strict_flag": postrun_has_strict_flag,
        "postrun_readiness_exit_status_position": readiness_marker_pos,
        "ignored_non_executable_readiness_marker_count": ignored_readiness_markers,
        "failures": failures,
    }
    return ("ok" if not failures else "failed"), detail


def _run_script_strict_postrun_rebuild(run_sh: Path) -> tuple[str, Any]:
    failures: list[dict[str, Any]] = []
    try:
        text = run_sh.read_text(encoding="utf-8")
    except OSError as exc:
        text = ""
        failures.append(
            {
                "reason": "unable_to_read_run_script",
                "run_script": str(run_sh),
                "error": str(exc),
            }
        )

    rebuild_pos, rebuild_block = _shell_command_block_containing_marker(
        text,
        "tools/rebuild_postrun_acceptance.py",
    )
    rebuild_has_strict_flag = command_has_shell_flag(rebuild_block, "--strict")
    readiness_pos, _readiness_block = _shell_command_block_containing_marker(
        text,
        "tools/check_postrun_acceptance.py",
    )
    status_marker_pos, ignored_status_markers = _find_executable_marker_position(
        text,
        "POSTRUN_REPORTS_EXIT_STATUS",
    )
    function_pos, ignored_function_count = _shell_function_definition_position(
        text,
        "write_postrun_acceptance_reports",
    )
    if function_pos < 0:
        failures.append({"reason": "missing_postrun_report_function"})
    if rebuild_pos < 0:
        failures.append({"reason": "postrun_rebuild_command_missing"})
    elif not rebuild_has_strict_flag:
        failures.append({"reason": "postrun_rebuild_strict_flag_missing"})
    if rebuild_pos >= 0 and readiness_pos >= 0 and rebuild_pos > readiness_pos:
        failures.append({"reason": "postrun_rebuild_after_readiness"})
    if status_marker_pos < 0:
        failures.append({"reason": "postrun_reports_exit_status_marker_missing"})
    if rebuild_pos >= 0 and status_marker_pos >= 0 and status_marker_pos < rebuild_pos:
        failures.append({"reason": "postrun_reports_exit_status_before_rebuild"})

    detail = {
        "run_script": str(run_sh),
        "postrun_report_function_position": function_pos,
        "ignored_non_executable_function_definition_count": ignored_function_count,
        "postrun_rebuild_command_position": rebuild_pos,
        "postrun_rebuild_strict_flag": rebuild_has_strict_flag,
        "postrun_acceptance_command_position": readiness_pos,
        "postrun_reports_exit_status_position": status_marker_pos,
        "ignored_non_executable_status_marker_count": ignored_status_markers,
        "failures": failures,
    }
    return ("ok" if not failures else "failed"), detail


def _run_script_completion_preflight_enforced(
    root: Path,
    run_sh: Path,
) -> tuple[str, Any]:
    launch_env = root / "launch.env"
    failures: list[dict[str, Any]] = []
    try:
        launch_env_text = launch_env.read_text(encoding="utf-8")
    except OSError as exc:
        launch_env_text = ""
        failures.append(
            {
                "reason": "unable_to_read_launch_env",
                "launch_env": str(launch_env),
                "error": str(exc),
            }
        )
    try:
        run_text = run_sh.read_text(encoding="utf-8")
    except OSError as exc:
        run_text = ""
        failures.append(
            {
                "reason": "unable_to_read_run_script",
                "run_script": str(run_sh),
                "error": str(exc),
            }
        )

    completion_value = _shell_assignment_value(
        launch_env_text,
        "COMPLETION_PREFLIGHT",
    )
    if completion_value != "1":
        failures.append(
            {
                "reason": "completion_preflight_not_enabled",
                "launch_env": str(launch_env),
                "actual": completion_value,
            }
        )

    source_pos = _first_launch_env_source_position(run_text)
    preflight_guard_positions = _executable_marker_positions(
        run_text,
        'if [[ "${COMPLETION_PREFLIGHT:-0}" == "1" ]]; then',
    )
    preflight_pos = (
        preflight_guard_positions[0] if len(preflight_guard_positions) == 1 else -1
    )
    proxy_positions = _executable_marker_positions(
        run_text,
        "tools/check_completion_proxy.py",
    )
    proxy_pos, proxy_block = _shell_command_block_containing_marker(
        run_text,
        "tools/check_completion_proxy.py",
    )
    receipt_assignment_positions = _executable_marker_positions(
        run_text,
        'PREFLIGHT_DETAIL="$RUN_ROOT/pre_campaign_completion_preflight.v1.json"',
    )
    all_receipt_assignment_positions = _executable_assignment_positions(
        run_text,
        "PREFLIGHT_DETAIL",
    )
    unexpected_receipt_references = [
        record
        for record in _executable_marker_lines(run_text, "PREFLIGHT_DETAIL")
        if not _allowed_preflight_detail_reference(record["line"])
    ]
    preflight_status_positions = _executable_assignment_positions(
        run_text,
        "PREFLIGHT_STATUS",
        expected_value="$?",
    )
    preflight_failure_exit_positions = _executable_marker_positions(
        run_text,
        'exit "$PREFLIGHT_STATUS"',
    )
    campaign_pos = _campaign_command_position(run_text)
    if source_pos < 0:
        failures.append({"reason": "run_script_does_not_source_launch_env"})
    if not preflight_guard_positions:
        failures.append({"reason": "completion_preflight_guard_missing"})
    elif len(preflight_guard_positions) != 1:
        failures.append(
            {
                "reason": "completion_preflight_guard_not_unique",
                "count": len(preflight_guard_positions),
            }
        )
    if not proxy_positions:
        failures.append({"reason": "completion_preflight_proxy_call_missing"})
    elif len(proxy_positions) != 1:
        failures.append(
            {
                "reason": "completion_preflight_proxy_call_not_unique",
                "count": len(proxy_positions),
            }
        )
    if len(receipt_assignment_positions) != 1:
        failures.append(
            {
                "reason": "completion_preflight_receipt_path_not_unique",
                "count": len(receipt_assignment_positions),
            }
        )
    if len(all_receipt_assignment_positions) != 1:
        failures.append(
            {
                "reason": "completion_preflight_receipt_assignment_not_unique",
                "count": len(all_receipt_assignment_positions),
            }
        )
    if unexpected_receipt_references:
        failures.append(
            {
                "reason": "completion_preflight_receipt_reference_not_canonical",
                "references": unexpected_receipt_references,
            }
        )
    if len(preflight_status_positions) != 1:
        failures.append(
            {
                "reason": "completion_preflight_status_capture_not_unique",
                "count": len(preflight_status_positions),
            }
        )
    if len(preflight_failure_exit_positions) != 1:
        failures.append(
            {
                "reason": "completion_preflight_failure_exit_not_unique",
                "count": len(preflight_failure_exit_positions),
            }
        )
    if '> "$PREFLIGHT_DETAIL"' not in proxy_block:
        failures.append(
            {"reason": "completion_preflight_receipt_redirection_missing"}
        )
    if campaign_pos < 0:
        failures.append(
            {
                "reason": "missing_campaign_command_marker",
                "marker": RUN_SCRIPT_CAMPAIGN_COMMAND_MARKER,
            }
        )
    if source_pos >= 0 and preflight_pos >= 0 and source_pos > preflight_pos:
        failures.append({"reason": "launch_env_sourced_after_preflight"})
    if preflight_pos >= 0 and campaign_pos >= 0 and preflight_pos > campaign_pos:
        failures.append({"reason": "completion_preflight_after_campaign"})
    if proxy_pos >= 0 and campaign_pos >= 0 and proxy_pos > campaign_pos:
        failures.append({"reason": "completion_proxy_call_after_campaign"})
    receipt_pos = (
        receipt_assignment_positions[0]
        if len(receipt_assignment_positions) == 1
        and len(all_receipt_assignment_positions) == 1
        else -1
    )
    preflight_status_pos = (
        preflight_status_positions[0] if len(preflight_status_positions) == 1 else -1
    )
    preflight_failure_exit_pos = (
        preflight_failure_exit_positions[0]
        if len(preflight_failure_exit_positions) == 1
        else -1
    )
    ordered_positions = (
        preflight_pos,
        receipt_pos,
        proxy_pos,
        preflight_status_pos,
        preflight_failure_exit_pos,
        campaign_pos,
    )
    if all(position >= 0 for position in ordered_positions) and not all(
        left < right for left, right in zip(ordered_positions, ordered_positions[1:])
    ):
        failures.append(
            {
                "reason": "completion_preflight_execution_order_invalid",
                "positions": list(ordered_positions),
            }
        )

    detail = {
        "launch_env": str(launch_env),
        "run_script": str(run_sh),
        "completion_preflight": completion_value,
        "launch_env_source_position": source_pos,
        "preflight_guard_position": preflight_pos,
        "preflight_guard_positions": preflight_guard_positions,
        "proxy_call_position": proxy_pos,
        "proxy_call_positions": proxy_positions,
        "executable_proxy_call_count": len(proxy_positions),
        "receipt_path_assignment_positions": receipt_assignment_positions,
        "all_receipt_assignment_positions": all_receipt_assignment_positions,
        "unexpected_receipt_references": unexpected_receipt_references,
        "receipt_redirection_present": '> "$PREFLIGHT_DETAIL"' in proxy_block,
        "preflight_status_capture_positions": preflight_status_positions,
        "preflight_failure_exit_positions": preflight_failure_exit_positions,
        "campaign_command_position": campaign_pos,
        "failures": failures,
    }
    return ("ok" if not failures else "failed"), detail


def _run_script_campaign_execution_marker_enforced(run_sh: Path) -> tuple[str, Any]:
    failures: list[dict[str, Any]] = []
    try:
        run_text = run_sh.read_text(encoding="utf-8")
    except OSError as exc:
        run_text = ""
        failures.append(
            {
                "reason": "unable_to_read_run_script",
                "run_script": str(run_sh),
                "error": str(exc),
            }
        )

    campaign_pos = _campaign_command_position(run_text)
    preflight_proxy_pos, _proxy_block = _shell_command_block_containing_marker(
        run_text,
        "tools/check_completion_proxy.py",
    )
    preflight_failure_exit_pos = _find_line_after(
        run_text,
        'exit "$PREFLIGHT_STATUS"',
        preflight_proxy_pos if preflight_proxy_pos >= 0 else 0,
    )
    marker_file_pos, ignored_marker_file_count = _find_executable_marker_position(
        run_text,
        "campaign_execution_marker.v1.json",
    )
    marker_schema_pos, ignored_marker_schema_count = _find_executable_marker_position(
        run_text,
        "scion.launcher_campaign_execution_marker.v1",
    )
    marker_log_pos, ignored_marker_log_count = _find_executable_marker_position(
        run_text,
        "CAMPAIGN_EXECUTION_MARKER:",
    )

    if campaign_pos < 0:
        failures.append(
            {
                "reason": "missing_campaign_command_marker",
                "marker": RUN_SCRIPT_CAMPAIGN_COMMAND_MARKER,
            }
        )
    if marker_file_pos < 0:
        failures.append({"reason": "campaign_execution_marker_file_write_missing"})
    if marker_schema_pos < 0:
        failures.append({"reason": "campaign_execution_marker_schema_missing"})
    if marker_log_pos < 0:
        failures.append({"reason": "campaign_execution_marker_log_marker_missing"})

    marker_positions = [
        pos for pos in (marker_file_pos, marker_schema_pos, marker_log_pos) if pos >= 0
    ]
    if (
        preflight_proxy_pos >= 0
        and marker_positions
        and any(pos < preflight_proxy_pos for pos in marker_positions)
    ):
        failures.append({"reason": "campaign_execution_marker_before_preflight"})
    if preflight_proxy_pos >= 0 and preflight_failure_exit_pos < 0:
        failures.append(
            {"reason": "campaign_execution_marker_preflight_failure_exit_missing"}
        )
    if (
        preflight_failure_exit_pos >= 0
        and marker_positions
        and any(pos <= preflight_failure_exit_pos for pos in marker_positions)
    ):
        failures.append(
            {"reason": "campaign_execution_marker_before_preflight_failure_exit"}
        )
    if (
        campaign_pos >= 0
        and marker_positions
        and any(pos > campaign_pos for pos in marker_positions)
    ):
        failures.append({"reason": "campaign_execution_marker_after_campaign"})

    detail = {
        "run_script": str(run_sh),
        "preflight_proxy_position": preflight_proxy_pos,
        "preflight_failure_exit_position": preflight_failure_exit_pos,
        "campaign_command_position": campaign_pos,
        "marker_file_position": marker_file_pos,
        "marker_schema_position": marker_schema_pos,
        "marker_log_position": marker_log_pos,
        "ignored_non_executable_marker_counts": {
            "file": ignored_marker_file_count,
            "schema": ignored_marker_schema_count,
            "log": ignored_marker_log_count,
        },
        "failures": failures,
    }
    return ("ok" if not failures else "failed"), detail


def _launch_env_secret_permissions(root: Path) -> tuple[str, Any]:
    launch_env = root / "launch.env"
    failures: list[dict[str, Any]] = []
    mode: int | None = None
    try:
        mode = stat.S_IMODE(launch_env.stat().st_mode)
    except OSError as exc:
        failures.append(
            {
                "reason": "unable_to_stat_launch_env",
                "launch_env": str(launch_env),
                "error": str(exc),
            }
        )

    if mode is not None and mode & 0o077:
        failures.append(
            {
                "reason": "launch_env_has_group_or_other_permissions",
                "launch_env": str(launch_env),
                "mode": oct(mode),
                "group_or_other_mode": oct(mode & 0o077),
                "expected": "no group/other permission bits",
            }
        )

    detail = {
        "launch_env": str(launch_env),
        "mode": oct(mode) if mode is not None else None,
        "expected": "no group/other permission bits",
        "failures": failures,
    }
    return ("ok" if not failures else "failed"), detail


def _run_script_pythonpath_enforced(root: Path, run_sh: Path) -> tuple[str, Any]:
    launch_env = root / "launch.env"
    failures: list[dict[str, Any]] = []
    try:
        launch_env_text = launch_env.read_text(encoding="utf-8")
    except OSError as exc:
        launch_env_text = ""
        failures.append(
            {
                "reason": "unable_to_read_launch_env",
                "launch_env": str(launch_env),
                "error": str(exc),
            }
        )
    try:
        run_text = run_sh.read_text(encoding="utf-8")
    except OSError as exc:
        run_text = ""
        failures.append(
            {
                "reason": "unable_to_read_run_script",
                "run_script": str(run_sh),
                "error": str(exc),
            }
        )

    scion_dir = _shell_assignment_value(launch_env_text, "SCION_DIR")
    pythonpath = _shell_assignment_value(launch_env_text, "PYTHONPATH")
    if scion_dir and not Path(scion_dir).expanduser().is_absolute():
        failures.append(
            {
                "reason": "scion_dir_not_absolute",
                "launch_env": str(launch_env),
                "scion_dir": scion_dir,
            }
        )
    if not pythonpath:
        failures.append({"reason": "pythonpath_missing", "launch_env": str(launch_env)})
    elif scion_dir and not _path_list_contains(pythonpath, scion_dir):
        failures.append(
            {
                "reason": "pythonpath_missing_scion_dir",
                "launch_env": str(launch_env),
                "pythonpath": pythonpath,
                "scion_dir": scion_dir,
            }
        )

    source_pos = _first_launch_env_source_position(run_text)
    export_pos = _export_assignment_position(run_text, "PYTHONPATH")
    campaign_pos = _campaign_command_position(run_text)
    if source_pos < 0:
        failures.append({"reason": "run_script_does_not_source_launch_env"})
    if export_pos < 0:
        failures.append({"reason": "run_script_does_not_export_pythonpath"})
    if campaign_pos < 0:
        failures.append(
            {
                "reason": "missing_campaign_command_marker",
                "marker": RUN_SCRIPT_CAMPAIGN_COMMAND_MARKER,
            }
        )
    if source_pos >= 0 and campaign_pos >= 0 and source_pos > campaign_pos:
        failures.append({"reason": "launch_env_sourced_after_campaign"})
    if export_pos >= 0 and campaign_pos >= 0 and export_pos > campaign_pos:
        failures.append({"reason": "pythonpath_export_after_campaign"})

    detail = {
        "launch_env": str(launch_env),
        "run_script": str(run_sh),
        "scion_dir": scion_dir,
        "pythonpath": pythonpath,
        "launch_env_source_position": source_pos,
        "pythonpath_export_position": export_pos,
        "campaign_command_position": campaign_pos,
        "failures": failures,
    }
    return ("ok" if not failures else "failed"), detail


def _run_script_model_route_enforced(
    root: Path,
    run_sh: Path,
    prepared_contract: Any,
) -> tuple[str, Any]:
    launch_env = root / "launch.env"
    failures: list[dict[str, Any]] = []
    try:
        launch_env_text = launch_env.read_text(encoding="utf-8")
    except OSError as exc:
        launch_env_text = ""
        failures.append(
            {
                "reason": "unable_to_read_launch_env",
                "launch_env": str(launch_env),
                "error": str(exc),
            }
        )
    try:
        run_text = run_sh.read_text(encoding="utf-8")
    except OSError as exc:
        run_text = ""
        failures.append(
            {
                "reason": "unable_to_read_run_script",
                "run_script": str(run_sh),
                "error": str(exc),
            }
        )

    manifest = _prepared_manifest_from_contract(root, prepared_contract)
    manifest_model = _manifest_model_name(manifest)
    manifest_base_url = _manifest_model_base_url(manifest)
    env_model = _shell_assignment_value(launch_env_text, "SCION_MODEL")
    env_base_url = _shell_assignment_value(launch_env_text, "SCION_BASE_URL")

    if not manifest_model:
        failures.append(
            {
                "reason": "manifest_model_missing",
                "manifest": str(
                    manifest.get("manifest_path")
                    or root / "prepared_run_manifest.v1.json"
                ),
            }
        )
    if not env_model:
        failures.append(
            {"reason": "scion_model_missing", "launch_env": str(launch_env)}
        )
    if manifest_model and env_model and env_model != manifest_model:
        failures.append(
            {
                "reason": "scion_model_manifest_mismatch",
                "launch_env": str(launch_env),
                "manifest_model": manifest_model,
                "env_model": env_model,
            }
        )
    if not env_base_url:
        failures.append(
            {"reason": "scion_base_url_missing", "launch_env": str(launch_env)}
        )
    if manifest_base_url and env_base_url and env_base_url != manifest_base_url:
        failures.append(
            {
                "reason": "scion_base_url_manifest_mismatch",
                "launch_env": str(launch_env),
                "manifest_base_url": manifest_base_url,
                "env_base_url": env_base_url,
            }
        )

    campaign_pos = _campaign_command_position(run_text)
    model_export_pos = _export_assignment_position(run_text, "SCION_MODEL")
    base_export_pos = _export_assignment_position(run_text, "SCION_BASE_URL")
    proxy_pos, proxy_block = _shell_command_block_containing_marker(
        run_text,
        "tools/check_completion_proxy.py",
    )
    proxy_model_ok = _shell_command_has_option_value(
        proxy_block,
        "--model",
        {"$SCION_MODEL", "${SCION_MODEL}"},
    )
    proxy_base_ok = _shell_command_has_option_value(
        proxy_block,
        "--base-url",
        {"$SCION_BASE_URL", "${SCION_BASE_URL}"},
    )
    proxy_model_pos = (
        run_text.find("--model", proxy_pos, campaign_pos if campaign_pos >= 0 else None)
        if proxy_model_ok
        else -1
    )
    proxy_base_pos = (
        run_text.find(
            "--base-url", proxy_pos, campaign_pos if campaign_pos >= 0 else None
        )
        if proxy_base_ok
        else -1
    )
    if model_export_pos < 0:
        failures.append({"reason": "run_script_does_not_export_scion_model"})
    if base_export_pos < 0:
        failures.append({"reason": "run_script_does_not_export_scion_base_url"})
    if campaign_pos < 0:
        failures.append(
            {
                "reason": "missing_campaign_command_marker",
                "marker": RUN_SCRIPT_CAMPAIGN_COMMAND_MARKER,
            }
        )
    if proxy_pos < 0:
        failures.append({"reason": "completion_preflight_proxy_call_missing"})
    if proxy_model_pos < 0:
        failures.append({"reason": "completion_preflight_model_env_missing"})
    if proxy_base_pos < 0:
        failures.append({"reason": "completion_preflight_base_url_env_missing"})
    for reason, position in (
        ("scion_model_export_after_campaign", model_export_pos),
        ("scion_base_url_export_after_campaign", base_export_pos),
        ("completion_preflight_model_after_campaign", proxy_model_pos),
        ("completion_preflight_base_url_after_campaign", proxy_base_pos),
    ):
        if position >= 0 and campaign_pos >= 0 and position > campaign_pos:
            failures.append({"reason": reason})

    detail = {
        "launch_env": str(launch_env),
        "run_script": str(run_sh),
        "model_authority": "prepared_manifest",
        "manifest_model": manifest_model,
        "env_model": env_model,
        "manifest_base_url": manifest_base_url,
        "env_base_url": env_base_url,
        "scion_model_export_position": model_export_pos,
        "scion_base_url_export_position": base_export_pos,
        "proxy_call_position": proxy_pos,
        "proxy_model_position": proxy_model_pos,
        "proxy_base_url_position": proxy_base_pos,
        "campaign_command_position": campaign_pos,
        "failures": failures,
    }
    return ("ok" if not failures else "failed"), detail


def _run_script_campaign_contract_consistency(
    root: Path,
    run_sh: Path,
    prepared_contract: Any,
) -> tuple[str, Any]:
    launch_env = root / "launch.env"
    failures: list[dict[str, Any]] = []
    try:
        launch_env_text = launch_env.read_text(encoding="utf-8")
    except OSError as exc:
        launch_env_text = ""
        failures.append(
            {
                "reason": "unable_to_read_launch_env",
                "launch_env": str(launch_env),
                "error": str(exc),
            }
        )
    try:
        run_text = run_sh.read_text(encoding="utf-8")
    except OSError as exc:
        run_text = ""
        failures.append(
            {
                "reason": "unable_to_read_run_script",
                "run_script": str(run_sh),
                "error": str(exc),
            }
        )

    manifest = _prepared_manifest_from_contract(root, prepared_contract)
    config = _mapping_or_empty(manifest.get("config"))
    execution = _mapping_or_empty(manifest.get("execution"))
    manifest_command = manifest.get("command")
    manifest_command_text = (
        manifest_command if isinstance(manifest_command, str) else ""
    )
    manifest_run_root = str(manifest.get("run_root") or "")
    manifest_campaign_dir = str(manifest.get("campaign_dir") or "")
    manifest_path_from_root = (
        str(Path(manifest_run_root) / "prepared_run_manifest.v1.json")
        if manifest_run_root
        else ""
    )

    identity_fields = {
        "run_root": {
            "env": "RUN_ROOT",
            "expected": manifest_run_root,
        },
        "campaign_dir": {
            "env": "CAMPAIGN_DIR",
            "expected": manifest_campaign_dir,
            "option": "--campaign-dir",
        },
        "prepared_run_manifest": {
            "env": "PREPARED_RUN_MANIFEST",
            "expected": manifest_path_from_root,
        },
    }
    config_fields = {
        "problem": {"env": "PROBLEM", "option": "--problem"},
        "protocol": {"env": "PROTOCOL", "option": "--protocol"},
        "split": {"env": "SPLIT", "option": "--split"},
        "seeds": {"env": "SEEDS", "option": "--seeds"},
    }
    execution_fields = {
        "rounds": {"env": "ROUNDS", "option": "--rounds", "kind": "int"},
        "time_limit_sec": {
            "env": "TIME_LIMIT_SEC",
            "option": "--time-limit-sec",
            "kind": "int",
        },
    }

    field_details: dict[str, Any] = {}

    for field, spec in identity_fields.items():
        env_key = str(spec["env"])
        expected = str(spec.get("expected") or "")
        env_value = _shell_assignment_value(launch_env_text, env_key)
        field_details[field] = {
            "env_key": env_key,
            "expected": expected,
            "launch_env_value": env_value,
        }
        if not expected:
            failures.append({"reason": f"{field}_manifest_missing"})
        if not env_value:
            failures.append({"reason": f"{field}_launch_env_missing"})
        elif expected and env_value != expected:
            failures.append(
                {
                    "reason": f"{field}_launch_env_manifest_mismatch",
                    "expected": expected,
                    "actual": env_value,
                }
            )

    source_pos = _first_launch_env_source_position(run_text)
    campaign_pos = _campaign_command_position(run_text)
    campaign_status_pos = run_text.find("STATUS=$?", campaign_pos)
    campaign_end_pos = (
        campaign_status_pos if campaign_status_pos >= 0 else len(run_text)
    )
    campaign_command_block = (
        run_text[campaign_pos:campaign_end_pos] if campaign_pos >= 0 else ""
    )
    if source_pos < 0:
        failures.append({"reason": "run_script_does_not_source_launch_env"})
    if campaign_pos < 0:
        failures.append(
            {
                "reason": "missing_campaign_command_marker",
                "marker": RUN_SCRIPT_CAMPAIGN_COMMAND_MARKER,
            }
        )
    if source_pos >= 0 and campaign_pos >= 0 and source_pos > campaign_pos:
        failures.append({"reason": "launch_env_sourced_after_campaign"})

    run_script_option_fields: dict[str, Any] = {}
    for field, spec in {
        "campaign_dir": identity_fields["campaign_dir"],
        **config_fields,
        **execution_fields,
    }.items():
        env_key = str(spec["env"])
        option = str(spec["option"])
        env_value = _shell_assignment_value(launch_env_text, env_key)
        manifest_value: Any
        if field in config_fields:
            manifest_value = config.get(field)
        elif field in execution_fields:
            manifest_value = execution.get(field)
        else:
            manifest_value = manifest_campaign_dir
        command_value = _shell_command_option_value(manifest_command_text, option)
        run_script_value = _shell_command_option_value(campaign_command_block, option)
        kind = str(spec.get("kind") or "string")

        field_detail = {
            "env_key": env_key,
            "option": option,
            "launch_env_value": env_value,
            "manifest_value": manifest_value,
            "manifest_command_value": command_value,
            "run_script_value": run_script_value,
        }
        run_script_option_fields[field] = field_detail

        if kind == "int":
            manifest_parsed = _parse_positive_int(manifest_value)
            env_parsed = _parse_positive_int(env_value)
            command_parsed = _parse_positive_int(command_value)
            run_script_parsed = _parse_positive_int(run_script_value)
            field_detail.update(
                {
                    "launch_env_int": env_parsed,
                    "manifest_int": manifest_parsed,
                    "manifest_command_int": command_parsed,
                    "run_script_int": run_script_parsed,
                }
            )
            if manifest_parsed is None:
                failures.append(
                    {
                        "reason": f"{field}_manifest_missing_or_invalid",
                        "actual": manifest_value,
                    }
                )
            if env_parsed is None:
                failures.append(
                    {
                        "reason": f"{field}_launch_env_missing_or_invalid",
                        "actual": env_value,
                    }
                )
            elif manifest_parsed is not None and env_parsed != manifest_parsed:
                failures.append(
                    {
                        "reason": f"{field}_launch_env_manifest_mismatch",
                        "expected": manifest_parsed,
                        "actual": env_parsed,
                    }
                )
            if command_parsed is None:
                failures.append(
                    {
                        "reason": f"{field}_manifest_command_missing_or_invalid",
                        "option": option,
                        "actual": command_value,
                    }
                )
            elif manifest_parsed is not None and command_parsed != manifest_parsed:
                failures.append(
                    {
                        "reason": f"{field}_manifest_command_mismatch",
                        "option": option,
                        "expected": manifest_parsed,
                        "actual": command_parsed,
                    }
                )
            if run_script_value in {f"${env_key}", f"${{{env_key}}}"}:
                continue
            if run_script_parsed is None:
                failures.append(
                    {
                        "reason": f"{field}_run_script_option_missing_or_invalid",
                        "option": option,
                        "actual": run_script_value,
                    }
                )
            elif manifest_parsed is not None and run_script_parsed != manifest_parsed:
                failures.append(
                    {
                        "reason": f"{field}_run_script_option_mismatch",
                        "option": option,
                        "expected": manifest_parsed,
                        "actual": run_script_parsed,
                    }
                )
            continue

        expected_text = str(manifest_value or "")
        if not expected_text:
            failures.append({"reason": f"{field}_manifest_missing"})
        if not env_value:
            failures.append({"reason": f"{field}_launch_env_missing"})
        elif expected_text and env_value != expected_text:
            failures.append(
                {
                    "reason": f"{field}_launch_env_manifest_mismatch",
                    "expected": expected_text,
                    "actual": env_value,
                }
            )
        if command_value != expected_text:
            failures.append(
                {
                    "reason": f"{field}_manifest_command_mismatch",
                    "option": option,
                    "expected": expected_text,
                    "actual": command_value,
                }
            )
        accepted_run_values = {
            f"${env_key}",
            f"${{{env_key}}}",
        }
        if env_value:
            accepted_run_values.add(env_value)
        if expected_text:
            accepted_run_values.add(expected_text)
        if run_script_value not in accepted_run_values:
            failures.append(
                {
                    "reason": f"{field}_run_script_option_mismatch",
                    "option": option,
                    "expected": sorted(accepted_run_values),
                    "actual": run_script_value,
                }
            )

    detail = {
        "launch_env": str(launch_env),
        "run_script": str(run_sh),
        "manifest_path": manifest.get("manifest_path"),
        "manifest_command_present": bool(manifest_command_text),
        "identity_fields": field_details,
        "campaign_option_fields": run_script_option_fields,
        "launch_env_source_position": source_pos,
        "campaign_command_position": campaign_pos,
        "campaign_status_position": campaign_status_pos,
        "failures": failures,
    }
    return ("ok" if not failures else "failed"), detail


def _run_script_direct_runtime_controls_absent(
    root: Path,
    run_sh: Path,
    prepared_contract: Any,
) -> tuple[str, Any]:
    launch_env = root / "launch.env"
    failures: list[dict[str, Any]] = []
    try:
        launch_env_text = launch_env.read_text(encoding="utf-8")
    except OSError as exc:
        launch_env_text = ""
        failures.append(
            {
                "reason": "unable_to_read_launch_env",
                "launch_env": str(launch_env),
                "error": str(exc),
            }
        )
    try:
        run_text = run_sh.read_text(encoding="utf-8")
    except OSError as exc:
        run_text = ""
        failures.append(
            {
                "reason": "unable_to_read_run_script",
                "run_script": str(run_sh),
                "error": str(exc),
            }
        )

    manifest = _prepared_manifest_from_contract(root, prepared_contract)
    manifest_command = manifest.get("command")
    execution = manifest.get("execution")
    if not isinstance(execution, dict):
        execution = {}
    try:
        proposal_runtime_mode = prepared_execution_runtime_mode(execution)
    except ValueError as exc:
        proposal_runtime_mode = None
        failures.append(
            {
                "reason": "proposal_runtime_mode_unknown_or_conflicting",
                "detail": str(exc),
            }
        )

    campaign_pos = _campaign_command_position(run_text)
    campaign_status_pos = run_text.find("STATUS=$?", campaign_pos)
    campaign_end_pos = (
        campaign_status_pos if campaign_status_pos >= 0 else len(run_text)
    )
    campaign_command_block = (
        run_text[campaign_pos:campaign_end_pos] if campaign_pos >= 0 else ""
    )

    if proposal_runtime_mode != "direct_v3":
        failures.append({"reason": "prepared_runtime_is_not_direct_v3"})
    present_env_controls = [
        key
        for key in REMOVED_RUNTIME_ENV_KEYS
        if _shell_assignment_value(launch_env_text, key) is not None
    ]
    present_manifest_options = [
        option
        for option in REMOVED_RUNTIME_COMMAND_OPTIONS
        if command_has_shell_flag(manifest_command, option)
    ]
    present_run_script_options = [
        option
        for option in REMOVED_RUNTIME_COMMAND_OPTIONS
        if command_has_shell_flag(campaign_command_block, option)
    ]
    if present_env_controls:
        failures.append(
            {
                "reason": "removed_runtime_controls_in_launch_env",
                "keys": present_env_controls,
            }
        )
    if present_manifest_options:
        failures.append(
            {
                "reason": "removed_runtime_controls_in_manifest_command",
                "options": present_manifest_options,
            }
        )
    if present_run_script_options:
        failures.append(
            {
                "reason": "removed_runtime_controls_in_run_script",
                "options": present_run_script_options,
            }
        )
    if campaign_pos < 0:
        failures.append(
            {
                "reason": "missing_campaign_command_marker",
                "marker": RUN_SCRIPT_CAMPAIGN_COMMAND_MARKER,
            }
        )

    detail = {
        "launch_env": str(launch_env),
        "run_script": str(run_sh),
        "proposal_runtime_mode": proposal_runtime_mode,
        "removed_runtime_env_keys_present": present_env_controls,
        "removed_manifest_command_options_present": present_manifest_options,
        "removed_run_script_options_present": present_run_script_options,
        "campaign_command_position": campaign_pos,
        "campaign_status_position": campaign_status_pos,
        "failures": failures,
    }
    return ("ok" if not failures else "failed"), detail


def _manifest_campaign_command_cli_parse(
    root: Path,
    prepared_contract: Any,
) -> tuple[str, Any]:
    """Ask the real CLI to parse the prepared command without running it."""

    manifest = _prepared_manifest_from_contract(root, prepared_contract)
    command = manifest.get("command")
    detail: dict[str, Any] = {
        "manifest_path": manifest.get("manifest_path"),
        "command": command,
        "parse_only": True,
        "failures": [],
    }
    failures = detail["failures"]
    if not isinstance(command, str) or not command.strip():
        failures.append({"reason": "manifest_command_missing"})
        return "failed", detail
    try:
        tokens = shlex.split(command, comments=False, posix=True)
    except ValueError as exc:
        failures.append({"reason": "manifest_command_shell_parse_failed", "error": str(exc)})
        return "failed", detail
    if len(tokens) < 4 or tokens[1:4] != ["-m", "scion.cli.main", "run"]:
        failures.append(
            {
                "reason": "manifest_command_not_scion_run",
                "prefix": tokens[:4],
            }
        )
        return "failed", detail

    parse_command = [*tokens, "--help"]
    env = dict(os.environ)
    current_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(SCION_PROJECT_DIR)
        if not current_pythonpath
        else str(SCION_PROJECT_DIR) + os.pathsep + current_pythonpath
    )
    try:
        result = subprocess.run(
            parse_command,
            cwd=REPO_DIR,
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        failures.append(
            {
                "reason": "manifest_command_cli_parse_unavailable",
                "error": str(exc),
            }
        )
        return "failed", detail
    detail.update(
        {
            "parse_command": parse_command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    )
    if result.returncode != 0:
        failures.append(
            {
                "reason": "manifest_command_cli_parse_failed",
                "returncode": result.returncode,
            }
        )
    return ("ok" if not failures else "failed"), detail


def _formal_research_target_unbound(
    root: Path,
    prepared_contract: Any,
) -> tuple[str, Any]:
    """Reject diagnostic target forcing from completion/formal launch roots."""

    launch_env = root / "launch.env"
    try:
        launch_env_text = launch_env.read_text(encoding="utf-8")
    except OSError as exc:
        return "failed", {
            "launch_env": str(launch_env),
            "failures": [
                {
                    "reason": "unable_to_read_launch_env",
                    "error": str(exc),
                }
            ],
        }
    manifest = _prepared_manifest_from_contract(root, prepared_contract)
    command = manifest.get("command")
    forced_env = {
        key: _shell_assignment_value(launch_env_text, key)
        for key in ("FORCE_SURFACE", "FORCE_ACTION", "FORCE_TARGET_FILE")
    }
    active_env = {key: value for key, value in forced_env.items() if value}
    forced_options = [
        option
        for option in ("--force-surface", "--force-action", "--force-target-file")
        if command_has_shell_flag(command, option)
    ]
    failures: list[dict[str, Any]] = []
    if active_env:
        failures.append(
            {
                "reason": "formal_launch_contains_forced_target_env",
                "values": active_env,
            }
        )
    if forced_options:
        failures.append(
            {
                "reason": "formal_launch_contains_forced_target_options",
                "options": forced_options,
            }
        )
    return ("ok" if not failures else "failed"), {
        "launch_env": str(launch_env),
        "manifest_path": manifest.get("manifest_path"),
        "forced_env": forced_env,
        "forced_command_options": forced_options,
        "failures": failures,
    }


def _formal_research_clean_start(
    root: Path,
    prepared_contract: Any,
) -> tuple[str, Any]:
    """Require formal evidence to start without restored campaign state."""

    launch_env = root / "launch.env"
    try:
        launch_env_text = launch_env.read_text(encoding="utf-8")
    except OSError as exc:
        return "failed", {
            "launch_env": str(launch_env),
            "failures": [
                {
                    "reason": "unable_to_read_launch_env",
                    "error": str(exc),
                }
            ],
        }
    manifest = _prepared_manifest_from_contract(root, prepared_contract)
    command = manifest.get("command")
    env_resume = _shell_assignment_value(launch_env_text, "RESUME_FROM_CAMPAIGN")
    manifest_resume = manifest.get("resume_from_campaign")
    resume_options = [
        option
        for option in ("--resume-from-campaign",)
        if command_has_shell_flag(command, option)
    ]
    failures: list[dict[str, Any]] = []
    if env_resume:
        failures.append(
            {
                "reason": "formal_launch_contains_resume_env",
                "value": env_resume,
            }
        )
    if manifest_resume:
        failures.append(
            {
                "reason": "formal_launch_contains_resume_manifest",
                "value": manifest_resume,
            }
        )
    if resume_options:
        failures.append(
            {
                "reason": "formal_launch_contains_resume_options",
                "options": resume_options,
            }
        )
    return ("ok" if not failures else "failed"), {
        "launch_env": str(launch_env),
        "manifest_path": manifest.get("manifest_path"),
        "resume_env": env_resume,
        "resume_manifest": manifest_resume,
        "resume_command_options": resume_options,
        "failures": failures,
    }


def _prepared_manifest_from_contract(
    root: Path, prepared_contract: Any
) -> dict[str, Any]:
    manifest = prepared_contract if isinstance(prepared_contract, dict) else {}
    manifest_path = manifest.get("manifest_path")
    path = (
        Path(manifest_path) if manifest_path else root / "prepared_run_manifest.v1.json"
    )
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return {}
    payload.setdefault("manifest_path", str(path))
    return payload


def _shell_assignment_value(text: str, key: str) -> str | None:
    prefix = f"{key}="
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or not stripped.startswith(prefix):
            continue
        value = stripped[len(prefix) :].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        return value
    return None


def _shell_assignment_position(text: str, key: str) -> int:
    prefix = f"{key}="
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and stripped.startswith(prefix):
            return offset + line.find(prefix)
        offset += len(line)
    return -1


def _parse_positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _parse_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _shell_command_option_value(command: str, option: str) -> str | None:
    if not command:
        return None
    try:
        tokens = shlex.split(command, comments=False, posix=True)
    except ValueError:
        return None
    for index, token in enumerate(tokens[:-1]):
        if token == option:
            return tokens[index + 1]
    return None


def _path_list_contains(path_list: str, required: str) -> bool:
    if not required:
        return True
    entries = [entry for entry in path_list.split(os.pathsep) if entry]
    return required in entries


def _first_launch_env_source_position(text: str) -> int:
    markers = (
        'source "$(dirname "$0")/launch.env"',
        '. "$(dirname "$0")/launch.env"',
        'source "$RUN_ROOT/launch.env"',
        '. "$RUN_ROOT/launch.env"',
    )
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if _line_is_non_executed_shell_text(stripped):
            offset += len(line)
            continue
        for marker in markers:
            if stripped == marker:
                return offset + line.find(marker)
        offset += len(line)
    return -1


def _export_assignment_position(text: str, key: str) -> int:
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("export ") and key in stripped.split()[1:]:
            return offset + line.find(key)
        offset += len(line)
    return -1


def _campaign_command_position(text: str) -> int:
    position, _line = _campaign_command_line(text)
    return position


def _shell_command_block_containing_marker(text: str, marker: str) -> tuple[int, str]:
    offset = 0
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        stripped = line.strip()
        if marker not in stripped or _line_is_non_executed_shell_text(stripped):
            offset += len(line)
            continue
        block = [line]
        cursor = index
        while block[-1].rstrip().endswith("\\") and cursor + 1 < len(lines):
            cursor += 1
            block.append(lines[cursor])
        return offset + line.find(marker), "".join(block)
    return -1, ""


def _executable_marker_positions(text: str, marker: str) -> list[int]:
    positions: list[int] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if marker in stripped and not _line_is_non_executed_shell_text(stripped):
            positions.append(offset + line.find(marker))
        offset += len(line)
    return positions


def _executable_marker_lines(text: str, marker: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if marker in stripped and not _line_is_non_executed_shell_text(stripped):
            records.append(
                {
                    "position": offset + line.find(marker),
                    "line": stripped,
                }
            )
        offset += len(line)
    return records


def _allowed_preflight_detail_reference(line: str) -> bool:
    if line == 'PREFLIGHT_DETAIL="$RUN_ROOT/pre_campaign_completion_preflight.v1.json"':
        return True
    if (
        "tools/check_completion_proxy.py" in line
        and '> "$PREFLIGHT_DETAIL"' in line
    ):
        return True
    if line.startswith('> "$PREFLIGHT_DETAIL"'):
        return True
    if line.startswith('echo "COMPLETION_PREFLIGHT_DETAIL:$PREFLIGHT_DETAIL"'):
        return True
    if line == 'chmod 600 "$PREFLIGHT_DETAIL" 2>> "$RUN_ROOT/run.log" \\':
        return True
    return line.startswith('--detail "$PREFLIGHT_DETAIL"')


def _executable_assignment_positions(
    text: str,
    name: str,
    *,
    expected_value: str | None = None,
) -> list[int]:
    prefix = f"{name}="
    positions: list[int] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if (
            stripped.startswith(prefix)
            and not _line_is_non_executed_shell_text(stripped)
            and (
                expected_value is None
                or stripped.removeprefix(prefix) == expected_value
            )
        ):
            positions.append(offset + line.find(name))
        offset += len(line)
    return positions


def _shell_command_has_option_value(
    command: str,
    option: str,
    expected_values: set[str],
) -> bool:
    if not command:
        return False
    try:
        tokens = shlex.split(command, comments=False, posix=True)
    except ValueError:
        return False
    for index, token in enumerate(tokens[:-1]):
        if token == option and tokens[index + 1] in expected_values:
            return True
    return False


def _campaign_command_line(text: str) -> tuple[int, str]:
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if (
            RUN_SCRIPT_CAMPAIGN_COMMAND_MARKER in stripped
            and not _line_is_campaign_command_echo(stripped)
        ):
            return offset + line.find(RUN_SCRIPT_CAMPAIGN_COMMAND_MARKER), stripped
        offset += len(line)
    return -1, ""


def _line_is_campaign_command_echo(stripped_line: str) -> bool:
    return _line_is_non_executed_shell_text(stripped_line) or (
        stripped_line.startswith("COMMAND:")
        or 'echo "COMMAND:' in stripped_line
        or "echo 'COMMAND:" in stripped_line
    )


def _line_is_non_executed_shell_text(stripped_line: str) -> bool:
    return stripped_line.startswith("echo ") or stripped_line.startswith("#")


def _run_script_postrun_reports_after_campaign(run_sh: Path) -> tuple[str, Any]:
    if not run_sh.is_file():
        return "failed", {"run_script": str(run_sh), "reason": "missing_run_script"}
    try:
        text = run_sh.read_text(encoding="utf-8")
    except OSError as exc:
        return (
            "failed",
            {
                "run_script": str(run_sh),
                "reason": "unable_to_read_run_script",
                "error": str(exc),
            },
        )

    campaign_pos = _campaign_command_position(text)
    status_pos = text.find("STATUS=$?", campaign_pos) if campaign_pos >= 0 else -1
    call_pos = (
        text.find("write_postrun_acceptance_reports", status_pos)
        if status_pos >= 0
        else -1
    )
    postrun_status_pos = (
        _find_line_after(text, "POSTRUN_ACCEPTANCE_STATUS=0", status_pos)
        if status_pos >= 0
        else -1
    )
    postrun_failed_marker_pos = (
        text.find("POSTRUN_ACCEPTANCE_FAILED", call_pos) if call_pos >= 0 else -1
    )
    status_writer_pos = (
        text.find("tools/write_postrun_wrapper_status.py", call_pos)
        if call_pos >= 0
        else -1
    )
    wrapper_effective_pos = (
        text.find("WRAPPER_EXIT_STATUS_EFFECTIVE", call_pos) if call_pos >= 0 else -1
    )
    exit_pos = text.find('exit "$STATUS"', status_pos) if status_pos >= 0 else -1
    failures: list[dict[str, Any]] = []
    if campaign_pos < 0:
        failures.append(
            {
                "reason": "missing_campaign_command_marker",
                "marker": RUN_SCRIPT_CAMPAIGN_COMMAND_MARKER,
            }
        )
    if status_pos < 0:
        failures.append({"reason": "missing_campaign_status_capture"})
    if call_pos < 0:
        failures.append({"reason": "missing_postrun_report_call_after_campaign"})
    if postrun_status_pos < 0:
        failures.append({"reason": "missing_postrun_acceptance_status_capture"})
    if call_pos >= 0 and postrun_status_pos >= 0 and postrun_status_pos > call_pos:
        failures.append({"reason": "postrun_acceptance_status_capture_after_call"})
    if call_pos >= 0 and postrun_failed_marker_pos < 0:
        failures.append({"reason": "missing_postrun_acceptance_failure_marker"})
    if call_pos >= 0 and wrapper_effective_pos < 0:
        failures.append({"reason": "missing_postrun_wrapper_effective_status_marker"})
    if call_pos >= 0 and status_writer_pos < 0:
        failures.append({"reason": "missing_postrun_wrapper_status_writer"})
    if exit_pos < 0:
        failures.append({"reason": "missing_campaign_status_exit"})
    if call_pos >= 0 and exit_pos >= 0 and call_pos > exit_pos:
        failures.append({"reason": "postrun_report_call_after_exit"})
    if status_writer_pos >= 0 and exit_pos >= 0 and status_writer_pos > exit_pos:
        failures.append({"reason": "postrun_wrapper_status_writer_after_exit"})

    detail = {
        "run_script": str(run_sh),
        "campaign_command_marker": RUN_SCRIPT_CAMPAIGN_COMMAND_MARKER,
        "campaign_command_position": campaign_pos,
        "campaign_status_position": status_pos,
        "postrun_acceptance_status_position": postrun_status_pos,
        "postrun_report_call_position": call_pos,
        "postrun_acceptance_failure_marker_position": postrun_failed_marker_pos,
        "postrun_wrapper_effective_status_marker_position": wrapper_effective_pos,
        "postrun_wrapper_status_writer_position": status_writer_pos,
        "campaign_status_exit_position": exit_pos,
        "failures": failures,
    }
    return ("ok" if not failures else "failed"), detail


def _run_script_data_root_failure_reports(run_sh: Path) -> tuple[str, Any]:
    if not run_sh.is_file():
        return "failed", {"run_script": str(run_sh), "reason": "missing_run_script"}
    try:
        text = run_sh.read_text(encoding="utf-8")
    except OSError as exc:
        return (
            "failed",
            {
                "run_script": str(run_sh),
                "reason": "unable_to_read_run_script",
                "error": str(exc),
            },
        )

    marker_matches: list[tuple[int, str, int]] = []
    ignored_marker_count = 0
    for marker in ("WAREHOUSE_DATA_ROOT_MISSING", "CVRP_SPLIT_DATA_INVALID"):
        marker_pos, ignored_count = _find_executable_marker_position(text, marker)
        ignored_marker_count += ignored_count
        if marker_pos >= 0:
            marker_matches.append((marker_pos, marker, ignored_count))
    if not marker_matches:
        return (
            "ok",
            {
                "run_script": str(run_sh),
                "required": False,
                "reason": "no_data_root_failure_path",
                "ignored_non_executable_marker_count": ignored_marker_count,
            },
        )

    marker_pos, marker, _marker_ignored_count = min(marker_matches)

    call_pos = _find_line_after(text, "write_postrun_acceptance_reports", marker_pos)
    exit_pos = _find_next_exit_after(text, marker_pos)
    failures: list[dict[str, Any]] = []
    if call_pos < 0:
        failures.append(
            {"reason": "missing_postrun_report_call_after_data_root_failure"}
        )
    if exit_pos < 0:
        failures.append({"reason": "missing_data_root_failure_exit"})
    if call_pos >= 0 and exit_pos >= 0 and call_pos > exit_pos:
        failures.append({"reason": "postrun_report_call_after_data_root_exit"})

    detail = {
        "run_script": str(run_sh),
        "required": True,
        "failure_marker": marker,
        "failure_marker_position": marker_pos,
        "ignored_non_executable_marker_count": ignored_marker_count,
        "postrun_report_call_position": call_pos,
        "failure_exit_position": exit_pos,
        "failures": failures,
    }
    return ("ok" if not failures else "failed"), detail


def _run_script_api_key_env_failure_reports(run_sh: Path) -> tuple[str, Any]:
    return _run_script_marker_failure_reports(
        run_sh,
        marker="SCION_API_KEY_ENV_MISSING",
        missing_call_reason="missing_postrun_report_call_after_api_key_env_failure",
        missing_exit_reason="missing_api_key_env_failure_exit",
        call_after_exit_reason="postrun_report_call_after_api_key_env_exit",
    )


def _run_script_scion_dir_failure_reports(run_sh: Path) -> tuple[str, Any]:
    status, detail = _run_script_status_failure_reports(
        run_sh,
        marker="SCION_DIR_MISSING",
        status_marker='"scion_dir_missing"',
        missing_call_reason="missing_postrun_report_call_after_scion_dir_failure",
        missing_exit_reason="missing_scion_dir_failure_exit",
        call_after_exit_reason="postrun_report_call_after_scion_dir_exit",
        status_missing_reason="scion_dir_failure_status_writer_missing",
        status_before_marker_reason="scion_dir_failure_status_writer_before_marker",
        call_before_status_reason=(
            "postrun_report_call_before_scion_dir_failure_status_writer"
        ),
    )
    if status == "ok" and detail.get("required") is False:
        failures = list(detail.get("failures", []))
        failures.append({"reason": "scion_dir_failure_path_missing"})
        detail = dict(detail)
        detail["failures"] = failures
        return "failed", detail
    return status, detail


def _run_script_launch_env_failure_reports(run_sh: Path) -> tuple[str, Any]:
    status, detail = _run_script_status_failure_reports(
        run_sh,
        marker="LAUNCH_ENV_MISSING",
        status_marker='"launch_env_missing"',
        missing_call_reason="missing_postrun_report_call_after_launch_env_failure",
        missing_exit_reason="missing_launch_env_failure_exit",
        call_after_exit_reason="postrun_report_call_after_launch_env_exit",
        status_missing_reason="launch_env_failure_status_writer_missing",
        status_before_marker_reason="launch_env_failure_status_writer_before_marker",
        call_before_status_reason=(
            "postrun_report_call_before_launch_env_failure_status_writer"
        ),
    )
    if status == "ok" and detail.get("required") is False:
        failures = list(detail.get("failures", []))
        failures.append({"reason": "launch_env_failure_path_missing"})
        detail = dict(detail)
        detail["failures"] = failures
        return "failed", detail
    return status, detail


def _run_script_status_failure_reports(
    run_sh: Path,
    *,
    marker: str,
    status_marker: str,
    missing_call_reason: str,
    missing_exit_reason: str,
    call_after_exit_reason: str,
    status_missing_reason: str,
    status_before_marker_reason: str,
    call_before_status_reason: str,
) -> tuple[str, Any]:
    if not run_sh.is_file():
        return "failed", {"run_script": str(run_sh), "reason": "missing_run_script"}
    try:
        text = run_sh.read_text(encoding="utf-8")
    except OSError as exc:
        return (
            "failed",
            {
                "run_script": str(run_sh),
                "reason": "unable_to_read_run_script",
                "error": str(exc),
            },
        )

    marker_pos, ignored_marker_count = _find_executable_marker_position(text, marker)
    if marker_pos < 0:
        return (
            "ok",
            {
                "run_script": str(run_sh),
                "required": False,
                "reason": "failure_marker_not_present",
                "failure_marker": marker,
                "status_marker": status_marker,
                "ignored_non_executable_marker_count": ignored_marker_count,
            },
        )

    status_pos, _status_block = _shell_command_block_containing_marker(
        text,
        status_marker,
    )
    call_pos = _find_line_after(text, "write_postrun_acceptance_reports", marker_pos)
    exit_pos = _find_next_exit_after(text, marker_pos)
    function_pos, ignored_function_count = _shell_function_definition_position(
        text,
        "write_postrun_acceptance_reports",
    )
    failures: list[dict[str, Any]] = []
    if function_pos < 0:
        failures.append({"reason": "missing_postrun_report_function"})
    if status_pos < 0:
        failures.append({"reason": status_missing_reason})
    if status_pos >= 0 and status_pos < marker_pos:
        failures.append({"reason": status_before_marker_reason})
    if call_pos < 0:
        failures.append({"reason": missing_call_reason})
    if exit_pos < 0:
        failures.append({"reason": missing_exit_reason})
    if call_pos >= 0 and exit_pos >= 0 and call_pos > exit_pos:
        failures.append({"reason": call_after_exit_reason})
    if call_pos >= 0 and status_pos >= 0 and call_pos < status_pos:
        failures.append({"reason": call_before_status_reason})

    detail = {
        "run_script": str(run_sh),
        "required": True,
        "failure_marker": marker,
        "status_marker": status_marker,
        "failure_marker_position": marker_pos,
        "status_writer_position": status_pos,
        "postrun_report_function_position": function_pos,
        "ignored_non_executable_function_definition_count": ignored_function_count,
        "ignored_non_executable_marker_count": ignored_marker_count,
        "postrun_report_call_position": call_pos,
        "failure_exit_position": exit_pos,
        "failures": failures,
    }
    return ("ok" if not failures else "failed"), detail


def _run_script_marker_failure_reports(
    run_sh: Path,
    *,
    marker: str,
    missing_call_reason: str,
    missing_exit_reason: str,
    call_after_exit_reason: str,
) -> tuple[str, Any]:
    if not run_sh.is_file():
        return "failed", {"run_script": str(run_sh), "reason": "missing_run_script"}
    try:
        text = run_sh.read_text(encoding="utf-8")
    except OSError as exc:
        return (
            "failed",
            {
                "run_script": str(run_sh),
                "reason": "unable_to_read_run_script",
                "error": str(exc),
            },
        )

    marker_pos, ignored_marker_count = _find_executable_marker_position(text, marker)
    if marker_pos < 0:
        return (
            "ok",
            {
                "run_script": str(run_sh),
                "required": False,
                "reason": "failure_marker_not_present",
                "failure_marker": marker,
                "ignored_non_executable_marker_count": ignored_marker_count,
            },
        )

    call_pos = _find_line_after(text, "write_postrun_acceptance_reports", marker_pos)
    exit_pos = _find_next_exit_after(text, marker_pos)
    failures: list[dict[str, Any]] = []
    if call_pos < 0:
        failures.append({"reason": missing_call_reason})
    if exit_pos < 0:
        failures.append({"reason": missing_exit_reason})
    if call_pos >= 0 and exit_pos >= 0 and call_pos > exit_pos:
        failures.append({"reason": call_after_exit_reason})

    detail = {
        "run_script": str(run_sh),
        "required": True,
        "failure_marker": marker,
        "failure_marker_position": marker_pos,
        "ignored_non_executable_marker_count": ignored_marker_count,
        "postrun_report_call_position": call_pos,
        "failure_exit_position": exit_pos,
        "failures": failures,
    }
    return ("ok" if not failures else "failed"), detail


def _find_executable_marker_position(text: str, marker: str) -> tuple[int, int]:
    offset = 0
    ignored = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if marker in stripped:
            if stripped.startswith("#"):
                ignored += 1
            else:
                return offset + line.find(marker), ignored
        offset += len(line)
    return -1, ignored


def _find_runtime_guard_marker_position(
    text: str,
    marker: str,
    *,
    allow_echo: bool,
) -> tuple[int, int]:
    offset = 0
    ignored = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if marker in stripped:
            non_executed = stripped.startswith("#") or (
                not allow_echo and _line_is_non_executed_shell_text(stripped)
            )
            if non_executed:
                ignored += 1
            else:
                return offset + line.find(marker), ignored
        offset += len(line)
    return -1, ignored


def _shell_function_definition_position(
    text: str,
    function_name: str,
) -> tuple[int, int]:
    target = f"{function_name}() {{"
    offset = 0
    ignored = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if target in stripped:
            if _line_is_non_executed_shell_text(stripped):
                ignored += 1
            elif stripped.startswith(target):
                return offset + line.find(target), ignored
        offset += len(line)
    return -1, ignored


def _find_line_after(text: str, line: str, start: int) -> int:
    if start < 0:
        return -1
    offset = start
    needle = line.strip()
    while True:
        position = text.find(needle, offset)
        if position < 0:
            return -1
        line_start = text.rfind("\n", 0, position) + 1
        line_end = text.find("\n", position)
        if line_end < 0:
            line_end = len(text)
        if text[line_start:line_end].strip() == needle:
            return position
        offset = position + len(needle)


def _find_next_exit_after(text: str, start: int) -> int:
    if start < 0:
        return -1
    offset = start
    while True:
        position = text.find("exit ", offset)
        if position < 0:
            return -1
        line_start = text.rfind("\n", 0, position) + 1
        line_end = text.find("\n", position)
        if line_end < 0:
            line_end = len(text)
        if text[line_start:line_end].strip().startswith("exit "):
            return position
        offset = position + len("exit ")


def _prepared_handoff_rebuild_declared_outputs_present(root: Path) -> tuple[str, Any]:
    handoff_dir = root / "prepared_handoff"
    manifest_path = handoff_dir / "rebuild" / "prepared_handoff_rebuild.v1.json"
    manifest = _read_json(manifest_path)
    detail: dict[str, Any] = {
        "manifest_path": str(manifest_path),
        "ok_families": [],
        "manifest_failures": [],
        "missing_outputs": [],
        "inconsistent_outputs": [],
        "unexpected_outputs": [],
        "family_failures": [],
    }
    if not isinstance(manifest, dict):
        detail["reason"] = "missing_rebuild_manifest"
        return "failed", detail

    prepared_manifest_path = root / "prepared_run_manifest.v1.json"
    prepared_manifest = _read_json(prepared_manifest_path)
    prepared_manifest_dict = (
        prepared_manifest if isinstance(prepared_manifest, dict) else {}
    )
    manifest_failures: list[dict[str, Any]] = []
    expected_identity = {
        "artifact_kind": "prepared_handoff_rebuild",
        "run_root": str(root),
        "prepared_handoff_dir": str(handoff_dir),
        "problem_family": prepared_manifest_dict.get("problem_family"),
        "prepared_manifest_commit": _manifest_commit(prepared_manifest_dict),
    }
    for field, expected in expected_identity.items():
        if manifest.get(field) != expected:
            manifest_failures.append(
                {
                    "reason": "manifest_identity_mismatch",
                    "field": field,
                    "expected": expected,
                    "actual": manifest.get(field),
                }
            )

    boundary_expectations = {
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
        "complete": True,
    }
    for field, expected in boundary_expectations.items():
        if manifest.get(field) is not expected:
            manifest_failures.append(
                {
                    "reason": "manifest_boundary_flag_mismatch",
                    "field": field,
                    "expected": expected,
                    "actual": manifest.get(field),
                }
            )

    family_failures: list[dict[str, Any]] = []
    if manifest.get("schema_version") != PREPARED_HANDOFF_REBUILD_SCHEMA:
        manifest_failures.append(
            {
                "reason": "schema_mismatch",
                "expected": PREPARED_HANDOFF_REBUILD_SCHEMA,
                "actual": manifest.get("schema_version"),
            }
        )
    families = manifest.get("families")
    families_dict = families if isinstance(families, dict) else {}
    if not families_dict:
        family_failures.append({"reason": "missing_rebuild_manifest_families"})

    for family_name in PREPARED_HANDOFF_REBUILD_FAMILIES:
        if family_name not in families_dict:
            family_failures.append(
                {
                    "family": family_name,
                    "reason": "missing_standard_family",
                }
            )

    ok_families: list[str] = []
    missing_outputs: list[dict[str, Any]] = []
    inconsistent_outputs: list[dict[str, Any]] = []
    unexpected_outputs: list[dict[str, Any]] = []
    out_of_scope_outputs: list[dict[str, Any]] = []
    for family_name, raw_family in sorted(families_dict.items()):
        family = raw_family if isinstance(raw_family, dict) else {}
        family_status = family.get("status")
        raw_outputs = family.get("outputs")
        outputs = (
            [str(item) for item in raw_outputs if str(item).strip()]
            if isinstance(raw_outputs, list)
            else []
        )
        outputs_present = (
            family.get("outputs_present")
            if isinstance(family.get("outputs_present"), dict)
            else {}
        )
        if family_status != "ok":
            family_failures.append(
                {
                    "family": str(family_name),
                    "status": family_status,
                    "reason": "family_status_not_ok",
                }
            )
            continue
        if not outputs:
            family_failures.append(
                {
                    "family": str(family_name),
                    "status": family_status,
                    "reason": "ok_family_without_outputs",
                }
            )
            continue

        ok_families.append(str(family_name))
        declared_paths: set[Path] = set()
        for output in outputs:
            path = _prepared_handoff_manifest_output_path(output, handoff_dir)
            in_scope = _prepared_handoff_manifest_output_in_family(
                path,
                handoff_dir,
                str(family_name),
            )
            if not in_scope:
                out_of_scope_outputs.append(
                    {
                        "family": str(family_name),
                        "path": str(path),
                        "manifest_output": output,
                        "expected_directory": str(handoff_dir / str(family_name)),
                        "reason": "manifest_output_outside_family_directory",
                    }
                )
            else:
                declared_paths.add(path.resolve())
            actual_present = path.is_file()
            manifest_present = outputs_present.get(output)
            if actual_present is False:
                missing_outputs.append(
                    {
                        "family": str(family_name),
                        "path": str(path),
                        "manifest_output": output,
                    }
                )
            if isinstance(manifest_present, bool):
                if manifest_present is not actual_present:
                    inconsistent_outputs.append(
                        {
                            "family": str(family_name),
                            "path": str(path),
                            "manifest_output": output,
                            "manifest_outputs_present": manifest_present,
                            "actual_present": actual_present,
                        }
                    )
            else:
                inconsistent_outputs.append(
                    {
                        "family": str(family_name),
                        "path": str(path),
                        "manifest_output": output,
                        "manifest_outputs_present": manifest_present,
                        "actual_present": actual_present,
                        "reason": "missing_outputs_present_entry",
                    }
                )

        family_dir = handoff_dir / str(family_name)
        if family_dir.is_dir():
            for path in sorted(family_dir.iterdir()):
                if not path.is_file() or path.suffix not in {".json", ".md"}:
                    continue
                if path.resolve() not in declared_paths:
                    unexpected_outputs.append(
                        {
                            "family": str(family_name),
                            "path": str(path),
                            "reason": "undeclared_generated_output",
                        }
                    )

    detail["ok_families"] = ok_families
    detail["manifest_failures"] = manifest_failures
    detail["missing_outputs"] = missing_outputs
    detail["inconsistent_outputs"] = inconsistent_outputs
    detail["unexpected_outputs"] = unexpected_outputs
    detail["out_of_scope_outputs"] = out_of_scope_outputs
    detail["family_failures"] = family_failures
    return (
        (
            "failed"
            if missing_outputs
            or inconsistent_outputs
            or unexpected_outputs
            or out_of_scope_outputs
            or manifest_failures
            or family_failures
            else "ok"
        ),
        detail,
    )


def _prepared_handoff_manifest_output_path(value: str, handoff_dir: Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return handoff_dir / path


def _prepared_handoff_manifest_output_in_family(
    path: Path,
    handoff_dir: Path,
    family_name: str,
) -> bool:
    try:
        return path.resolve().parent == (handoff_dir / family_name).resolve()
    except OSError:
        return False


def _prompt_context_readiness_check(root: Path) -> tuple[str, Any]:
    return check_prepared_prompt_context_readiness(root, repo_dir=REPO_DIR)


def _prepared_analysis_brief_check(root: Path) -> tuple[str, Any]:
    brief_dir = root / "prepared_handoff" / "analysis_brief"
    paths = sorted(brief_dir.glob("*.json"))
    detail: dict[str, Any] = {
        "directory": str(brief_dir),
        "artifacts": [path.name for path in paths],
        "failures": [],
    }
    failures: list[dict[str, Any]] = []
    if not paths:
        failures.append({"artifact": None, "reason": "missing_prepared_analysis_brief"})

    for path in paths:
        payload = _read_json(path)
        failures.extend(
            {"artifact": path.name, **failure}
            for failure in _prepared_analysis_brief_failures(payload, root=root)
        )

    detail["failures"] = failures
    return ("ok" if not failures else "failed"), detail


def _prepared_analysis_brief_failures(
    payload: Any,
    *,
    root: Path,
) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return [{"reason": "invalid_json_payload"}]

    failures: list[dict[str, Any]] = []
    if payload.get("schema_version") != ANALYSIS_BRIEF_SCHEMA:
        failures.append(
            {
                "reason": "schema_mismatch",
                "schema_version": payload.get("schema_version"),
            }
        )
    if payload.get("run_root") != str(root):
        failures.append(
            {
                "reason": "artifact_identity_mismatch",
                "field": "run_root",
                "expected": str(root),
                "actual": payload.get("run_root"),
            }
        )
    failures.extend(_prepared_analysis_contract_failures(payload, root=root))

    boundary_expectations = {
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
    }
    for key, expected in boundary_expectations.items():
        if payload.get(key) is not expected:
            failures.append(
                {
                    "reason": "boundary_flag_mismatch",
                    "field": key,
                    "expected": expected,
                    "actual": payload.get(key),
                }
            )

    lifecycle = payload.get("lifecycle")
    lifecycle_dict = lifecycle if isinstance(lifecycle, dict) else {}
    if lifecycle_dict.get("prepared_only") is not True:
        failures.append(
            {
                "reason": "analysis_brief_not_prepared_only",
                "prepared_only": lifecycle_dict.get("prepared_only"),
            }
        )
    if lifecycle_dict.get("current_run_evidence") is not False:
        failures.append(
            {
                "reason": "analysis_brief_current_run_evidence_not_false",
                "current_run_evidence": lifecycle_dict.get("current_run_evidence"),
            }
        )

    validity = payload.get("validity")
    validity_dict = validity if isinstance(validity, dict) else {}
    expected_validity = {
        "run_validity_status": "prepared_only",
        "run_completeness_status": "not_started",
    }
    for key, expected in expected_validity.items():
        if validity_dict.get(key) != expected:
            failures.append(
                {
                    "reason": "analysis_brief_validity_mismatch",
                    "field": key,
                    "expected": expected,
                    "actual": validity_dict.get(key),
                }
            )

    questions = payload.get("required_questions")
    questions_list = (
        [str(item) for item in questions] if isinstance(questions, list) else []
    )
    if PREPARED_ONLY_REQUIRED_QUESTION_MARKER not in questions_list:
        failures.append({"reason": "prepared_only_required_question_missing"})
    if CURRENT_RUN_REQUIRED_QUESTION_MARKER in questions_list:
        failures.append({"reason": "current_run_required_question_present"})

    return failures


def _prepared_analysis_contract_failures(
    payload: dict[str, Any],
    *,
    root: Path,
) -> list[dict[str, Any]]:
    manifest_path = root / "prepared_run_manifest.v1.json"
    manifest = _read_json(manifest_path)
    manifest_dict = manifest if isinstance(manifest, dict) else {}
    contract = payload.get("prepared_run_contract")
    if not isinstance(contract, dict):
        return [{"reason": "prepared_run_contract_missing"}]

    failures: list[dict[str, Any]] = []
    if contract.get("contract_complete") is not True:
        failures.append(
            {
                "reason": "prepared_run_contract_incomplete",
                "contract_complete": contract.get("contract_complete"),
            }
        )

    report_metadata = manifest_dict.get("report_metadata")
    report_metadata_dict = report_metadata if isinstance(report_metadata, dict) else {}
    expected_identity = {
        "manifest_path": str(manifest_path),
        "problem_family": manifest_dict.get("problem_family"),
        "model": _manifest_model_name(manifest_dict),
        "control_pair_key": report_metadata_dict.get("control_pair_key"),
        "resume_from_campaign": _normalized_prepared_contract_value(
            "resume_from_campaign",
            manifest_dict.get("resume_from_campaign"),
        ),
    }
    for field, expected in expected_identity.items():
        actual = _normalized_prepared_contract_value(field, contract.get(field))
        if actual != expected:
            failures.append(
                {
                    "reason": "prepared_run_contract_identity_mismatch",
                    "field": field,
                    "expected": expected,
                    "actual": actual,
                }
            )

    git = contract.get("git")
    git_dict = git if isinstance(git, dict) else {}
    expected_commit = _manifest_commit(manifest_dict)
    if git_dict.get("commit") != expected_commit:
        failures.append(
            {
                "reason": "prepared_run_contract_identity_mismatch",
                "field": "git.commit",
                "expected": expected_commit,
                "actual": git_dict.get("commit"),
            }
        )

    return failures


def _prepared_analysis_brief_contract_consistency_check(
    root: Path,
    prepared_contract: Any,
) -> tuple[str, Any]:
    directory = root / "prepared_handoff" / "analysis_brief"
    paths = sorted(directory.glob("*.json")) if directory.is_dir() else []
    detail: dict[str, Any] = {
        "directory": str(directory),
        "artifacts": [path.name for path in paths],
        "failures": [],
    }
    failures: list[dict[str, Any]] = []
    if not isinstance(prepared_contract, dict) or not prepared_contract:
        failures.append(
            {"artifact": None, "reason": "inventory_prepared_contract_missing"}
        )
    if not paths:
        failures.append({"artifact": None, "reason": "missing_prepared_analysis_brief"})

    for path in paths:
        payload = _read_json(path)
        if not isinstance(payload, dict):
            failures.append({"artifact": path.name, "reason": "invalid_json_payload"})
            continue
        failures.extend(
            {"artifact": path.name, **failure}
            for failure in _prepared_contract_consistency_failures(
                payload.get("prepared_run_contract"),
                prepared_contract,
            )
        )

    detail["failures"] = failures
    return ("ok" if not failures else "failed"), detail


def _normalized_prepared_contract_value(field: str, value: Any) -> Any:
    if field == "resume_from_campaign" and value in (None, ""):
        return ""
    return value


def _prepared_contract_consistency_failures(
    brief_contract: Any,
    inventory_contract: Any,
) -> list[dict[str, Any]]:
    if not isinstance(brief_contract, dict):
        return [{"reason": "analysis_brief_prepared_contract_missing"}]
    if not isinstance(inventory_contract, dict):
        return [{"reason": "inventory_prepared_contract_missing"}]

    failures: list[dict[str, Any]] = []
    for field in (
        "schema_version",
        "report_only",
        "quality_judgment",
        "decision_features_excluded",
        "manifest_path",
        "manifest_present",
        "contract_complete",
        "problem_family",
        "model",
        "analysis_intent",
        "acceptance_focus",
        "research_focus",
        "resume_from_campaign",
        "control_pair_key",
        "completion_preflight",
        "postrun_reports",
    ):
        brief_value = _normalized_prepared_contract_value(
            field,
            brief_contract.get(field),
        )
        inventory_value = _normalized_prepared_contract_value(
            field,
            inventory_contract.get(field),
        )
        if brief_value != inventory_value:
            failures.append(
                {
                    "reason": f"prepared_contract_{field}_mismatch",
                    "field": field,
                    "brief": brief_value,
                    "inventory": inventory_value,
                }
            )
    for field in ("execution", "git", "checks"):
        brief_value = _prepared_contract_nested_comparison_value(
            field,
            brief_contract.get(field),
        )
        inventory_value = _prepared_contract_nested_comparison_value(
            field,
            inventory_contract.get(field),
        )
        if brief_value != inventory_value:
            failures.append(
                {
                    "reason": f"prepared_contract_{field}_mismatch",
                    "field": field,
                }
            )
    return failures


def _prepared_contract_nested_comparison_value(
    field: str,
    value: Any,
) -> dict[str, Any]:
    value_dict = value if isinstance(value, dict) else {}
    if field == "git":
        return _prepared_contract_git_comparison_value(value_dict)
    if field == "checks":
        return _prepared_contract_checks_comparison_value(value_dict)
    return dict(value_dict)


def _prepared_contract_git_comparison_value(
    value: dict[str, Any],
) -> dict[str, Any]:
    if value.get("consistent") is True and value.get("commit") == value.get(
        "manifest_commit"
    ):
        return {
            "commit": value.get("commit"),
            "manifest_commit": value.get("manifest_commit"),
            "runtime_guard_paths": value.get("runtime_guard_paths"),
            "consistent": True,
        }
    return dict(value)


def _prepared_contract_checks_comparison_value(
    value: dict[str, Any],
) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, raw_check in value.items():
        if not isinstance(raw_check, dict):
            normalized[key] = raw_check
            continue
        check = dict(raw_check)
        if key == "git_runtime_consistent" and check.get("passed") is True:
            check["detail"] = "runtime_guard_paths_consistent"
        if key == "cvrp_protected_cases_in_split" and isinstance(
            check.get("detail"),
            dict,
        ):
            # Compare the stable split identity, not an environment-local path.
            detail = dict(check["detail"])
            if "split" in detail:
                detail["split_path"] = detail["split"]
            check["detail"] = detail
        normalized[key] = check
    return normalized


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _manifest_commit(manifest: dict[str, Any]) -> Any:
    git = manifest.get("git")
    return git.get("commit") if isinstance(git, dict) else None


def _manifest_model_name(manifest: dict[str, Any]) -> Any:
    model = manifest.get("model")
    return model.get("name") if isinstance(model, dict) else None


def _manifest_model_base_url(manifest: dict[str, Any]) -> Any:
    model = manifest.get("model")
    return model.get("base_url") if isinstance(model, dict) else None


def _repo_path_contains(relative_path: str, marker: str) -> bool:
    return _path_contains(REPO_DIR / relative_path, marker)


def _path_contains(path: Path, marker: str) -> bool:
    try:
        return marker in path.read_text(encoding="utf-8")
    except OSError:
        return False


def _completion_preflight_check(
    *,
    prepared_contract: Any,
    api_key: str | None,
    api_key_env: str | None,
    timeout_sec: float,
) -> tuple[str, Any]:
    model = "gpt-5.5"
    base_url = "http://127.0.0.1:8080"
    manifest = prepared_contract if isinstance(prepared_contract, dict) else {}
    manifest_path = manifest.get("manifest_path")
    if manifest_path:
        try:
            payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        model_doc = payload.get("model") if isinstance(payload, dict) else {}
        if isinstance(model_doc, dict):
            model = str(model_doc.get("name") or model)
            base_url = str(model_doc.get("base_url") or base_url)

    command = [
        sys.executable,
        str(TOOLS_DIR / "check_completion_proxy.py"),
        "--base-url",
        base_url,
        "--model",
        model,
        "--timeout-sec",
        str(timeout_sec),
        "--login-url-on-failure",
        "--json",
    ]
    subprocess_env: dict[str, str] | None = None
    if api_key_env:
        command.extend(["--api-key-env", api_key_env])
    elif api_key:
        readiness_api_key_env = "SCION_COMPLETION_PREFLIGHT_API_KEY"
        command.extend(["--api-key-env", readiness_api_key_env])
        subprocess_env = os.environ.copy()
        subprocess_env[readiness_api_key_env] = api_key
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        env=subprocess_env,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    payload = _with_completion_preflight_action(
        payload,
        model=model,
        base_url=base_url,
    )
    return ("ok" if result.returncode == 0 else "failed"), payload


def _with_completion_preflight_action(
    payload: Any,
    *,
    model: str,
    base_url: str,
) -> Any:
    if not isinstance(payload, dict):
        return payload
    detail = dict(payload)
    chat = detail.get("chat")
    chat_detail = chat if isinstance(chat, dict) else {}
    classification = str(chat_detail.get("classification") or "")
    if detail.get("ok") is True or not classification:
        return detail

    login_url = str(detail.get("login_url") or "")
    action: dict[str, Any] = {
        "classification": classification,
        "summary": (
            f"Resolve the {model} completion preflight before starting this "
            "prepared campaign."
        ),
        "rerun_command": (
            "python scion/tools/check_launch_readiness.py <run_root> "
            "--require-launch-ready --format json"
        ),
        "model": model,
        "base_url": base_url,
    }
    if classification in {
        "auth_token_invalidated",
        "not_authenticated",
        "unauthorized",
    }:
        action["next_step"] = (
            "Refresh the local proxy login, then rerun launch readiness until "
            "launch_ready=true."
        )
        if login_url:
            action["login_url"] = login_url
    elif classification == "no_available_accounts":
        action["next_step"] = (
            f"Wait for an active {model} account or refresh the proxy account pool, "
            "then rerun launch readiness."
        )
    elif classification == "rate_limited":
        action["next_step"] = (
            "Wait for the rate limit window to clear, then rerun launch readiness."
        )
    elif classification == "completion_timeout":
        action["next_step"] = (
            "The upstream completion did not finish within the configured safety "
            "timeout. Inspect route liveness before starting a new run; do not "
            "retry this campaign automatically."
        )
    elif classification == "transport_error":
        action["next_step"] = (
            f"Start or repair the local {model} proxy endpoint, then rerun launch readiness."
        )
    else:
        action["next_step"] = (
            "Inspect the chat preflight detail, repair the proxy or model route, "
            "then rerun launch readiness."
        )
    detail["operator_action"] = action
    return detail


def _completion_preflight_action_lines(report: dict[str, Any]) -> list[str]:
    checks = report.get("checks")
    if not isinstance(checks, dict):
        return []
    item = checks.get("completion_preflight")
    if not isinstance(item, dict) or item.get("status") == "ok":
        return []
    detail = item.get("detail")
    if not isinstance(detail, dict):
        return []
    action = detail.get("operator_action")
    if not isinstance(action, dict):
        return []
    lines = [
        f"- Classification: `{_display(action.get('classification'))}`",
        f"- Next step: {_display(action.get('next_step'))}",
    ]
    login_url = action.get("login_url")
    if login_url:
        lines.append(f"- Login URL: `{_display(login_url)}`")
    lines.append(f"- Rerun: `{_display(action.get('rerun_command'))}`")
    return lines


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _display(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())
