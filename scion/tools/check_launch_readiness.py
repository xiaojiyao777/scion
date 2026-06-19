#!/usr/bin/env python3
"""Check whether a prepared Scion launch root is safe to start."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from postrun_artifact_inventory import build_inventory, command_has_shell_flag  # noqa: E402


SCHEMA_VERSION = "scion.launch_readiness.v1"
PREPARED_HANDOFF_REBUILD_SCHEMA = "scion.prepared_handoff_rebuild.v1"
PROMPT_CONTEXT_READINESS_SCHEMA = "scion.prepared_prompt_context_readiness.v1"
ANALYSIS_BRIEF_SCHEMA = "scion.postrun_analysis_brief.v1"
UNREADY_EXIT = 64
REQUIRED_SCION_MODEL = "gpt-5.5"
REPO_DIR = Path(__file__).resolve().parents[2]
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
WAREHOUSE_ACTIVE_SUBJECT_CODE_CONSTRAINT_MARKERS = {
    "provider_hook": (
        "scion/scion/problems/warehouse_delivery/adapter.py",
        "def active_subject_code_constraints",
    ),
    "diagnostics_contract": (
        "scion/scion/problems/warehouse_delivery/adapter.py",
        "self.validation_transfer_diagnostics",
    ),
    "bounded_scan_guard": (
        "scion/scion/problems/warehouse_delivery/adapter.py",
        "unbounded full vehicle-pair scans",
    ),
    "lexicographic_guard": (
        "scion/scion/problems/warehouse_delivery/adapter.py",
        "lexicographic",
    ),
}
ACTIVE_SUBJECT_CODE_CONSTRAINT_MARKERS_BY_FAMILY = {
    "cvrp": CVRP_ACTIVE_SUBJECT_CODE_CONSTRAINT_MARKERS,
    "warehouse_delivery": WAREHOUSE_ACTIVE_SUBJECT_CODE_CONSTRAINT_MARKERS,
}
ACTIVE_SUBJECT_CODE_CONSTRAINT_SIGNAL_NAMES = {
    "cvrp": "cvrp_active_subject_code_constraints_prompt_bridge",
    "warehouse_delivery": "warehouse_active_subject_code_constraints_prompt_bridge",
}
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
DEFERRED_REVIEW_AXES_ACTIONABILITY = (
    "not_actionable_before_launch_current_run_evidence_required"
)
PREPARED_PROBLEM_SUMMARY_REQUIREMENTS = {
    "cvrp": {
        "field": "cvrp_large_twoopt_summary",
        "schema": "scion.postrun_cvrp_large_twoopt_summary.v1",
        "conclusion_flag": "launch_required_before_twoopt_conclusion",
        "evidence_gap": "launch_required_before_bounded_twoopt_conclusion",
    },
    "warehouse_delivery": {
        "field": "warehouse_followup_summary",
        "schema": "scion.postrun_warehouse_followup_summary.v1",
        "conclusion_flag": "launch_required_before_plateau_conclusion",
        "evidence_gap": "launch_required_before_plateau_conclusion",
    },
}
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
        "guard_pathspec_array",
        'read -r -a _GIT_RUNTIME_GUARD_PATHS <<< "$GIT_RUNTIME_GUARD_PATHS"',
    ),
    (
        "dirty_status_check",
        'git -C "$REPO_ROOT" status --porcelain -- "${_GIT_RUNTIME_GUARD_PATHS[@]}"',
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
    (
        "runtime_path_diff_check",
        'git -C "$REPO_ROOT" diff --quiet "$GIT_COMMIT" HEAD -- "${_GIT_RUNTIME_GUARD_PATHS[@]}"',
    ),
    (
        "doc_only_mismatch_allowance_marker",
        "GIT_COMMIT_DOC_ONLY_MISMATCH_ALLOWED",
    ),
    ("commit_mismatch_failure_marker", "GIT_COMMIT_MISMATCH"),
)
RUN_SCRIPT_RUNTIME_GUARD_ECHO_MARKERS = {
    "dirty_failure_marker",
    "doc_only_mismatch_allowance_marker",
    "commit_mismatch_failure_marker",
}


def build_readiness(
    run_root: Path | str,
    *,
    completion_preflight: bool = False,
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

    add_check("inventory_loaded", "ok", str(root))
    add_check(
        "prepared_only_not_started",
        "ok"
        if lifecycle.get("prepared_only") is True
        and lifecycle.get("pre_campaign_completion_preflight_failed") is not True
        and validity.get("run_validity_status") == "prepared_only"
        and validity.get("run_completeness_status") == "not_started"
        else "failed",
        {
            "lifecycle": lifecycle,
            "validity": validity,
        },
    )
    add_check(
        "zero_current_run_counters",
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
        else "failed",
        counters,
    )
    add_check(
        "prepared_contract_complete",
        "ok"
        if prepared_contract.get("contract_complete") is True
        else "failed",
        prepared_contract.get("manifest_path"),
    )
    add_check(
        "git_runtime_consistent",
        _contract_check_status(contract_checks, "git_runtime_consistent"),
        _contract_check_detail(contract_checks, "git_runtime_consistent"),
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
        "run_script_syntax",
        *_run_script_syntax(run_sh),
    )
    add_check(
        "run_script_runtime_guard_enforced",
        *_run_script_runtime_guard_enforced(run_sh),
    )
    add_check(
        "run_script_preflight_failure_reports",
        *_run_script_preflight_failure_reports(run_sh),
    )
    add_check(
        "run_script_completion_preflight_enforced",
        *_run_script_completion_preflight_enforced(root, run_sh),
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
        "run_script_no_early_stop_enforced",
        *_run_script_no_early_stop_enforced(root, run_sh, prepared_contract),
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
        if item.get("required") is True
        and name != "completion_preflight"
    )
    completion_ready = (
        checks["completion_preflight"]["status"] == "ok"
        if completion_preflight
        else True
    )
    ready = bool(static_ready and completion_ready)
    launch_ready = bool(static_ready and completion_preflight and completion_ready)
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
        "ready": ready,
        "completion_preflight_required": completion_preflight,
        "checks": checks,
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
        f"- Launch ready: `{_display(report.get('launch_ready'))}`",
        f"- Completion preflight required: `{_display(report.get('completion_preflight_required'))}`",
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
            "- Static readiness is not enough to start an LLM campaign.",
            "- Launch only after rerunning this tool with `--completion-preflight` "
            "and seeing `launch_ready=true`.",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_root")
    parser.add_argument(
        "--completion-preflight",
        action="store_true",
        help="Require a real gpt-5.5 chat completion before reporting ready.",
    )
    parser.add_argument(
        "--require-launch-ready",
        action="store_true",
        help=(
            "Imply --completion-preflight and exit zero only when launch_ready=true."
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
    if args.timeout_sec <= 0:
        parser.error("--timeout-sec must be positive")

    report = build_readiness(
        args.run_root,
        completion_preflight=args.completion_preflight or args.require_launch_ready,
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
    pathspecs = raw_paths.split()
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
    pathspecs = raw_paths.split()
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

    detail = {
        "run_script": str(run_sh),
        "campaign_command_marker": RUN_SCRIPT_CAMPAIGN_COMMAND_MARKER,
        "required_markers": [name for name, _ in RUN_SCRIPT_RUNTIME_GUARD_MARKERS],
        "missing_markers": missing_markers,
        "markers_after_campaign_command": markers_after_campaign,
        "ignored_non_executable_marker_counts": ignored_marker_counts,
        "failures": failures,
    }
    return ("ok" if not failures else "failed"), detail


def _run_sh_contains_preflight_failure_report_path(run_sh: Path) -> bool:
    status, _detail = _run_script_preflight_failure_reports(run_sh)
    return status == "ok"


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
        min(status_writers, key=lambda item: item[0])
        if status_writers
        else (-1, None)
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
    if (
        writer_pos >= 0
        and failure_guard_pos >= 0
        and writer_pos < failure_guard_pos
    ):
        failures.append({"reason": "preflight_status_writer_before_failure_guard"})
    if call_pos < 0:
        failures.append({"reason": "missing_postrun_report_call_after_preflight_failure"})
    if exit_pos < 0:
        failures.append({"reason": "missing_preflight_failure_exit"})
    if writer_pos >= 0 and exit_pos >= 0 and writer_pos > exit_pos:
        failures.append({"reason": "preflight_status_writer_after_exit"})
    if call_pos >= 0 and writer_pos >= 0 and call_pos < writer_pos:
        failures.append({"reason": "postrun_report_call_before_preflight_status_writer"})
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
    preflight_pos = run_text.find('if [[ "${COMPLETION_PREFLIGHT:-0}" == "1" ]]; then')
    proxy_pos, _proxy_block = _shell_command_block_containing_marker(
        run_text,
        "tools/check_gpt55_proxy.py",
    )
    campaign_pos = _campaign_command_position(run_text)
    if source_pos < 0:
        failures.append({"reason": "run_script_does_not_source_launch_env"})
    if preflight_pos < 0:
        failures.append({"reason": "completion_preflight_guard_missing"})
    if proxy_pos < 0:
        failures.append({"reason": "completion_preflight_proxy_call_missing"})
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

    detail = {
        "launch_env": str(launch_env),
        "run_script": str(run_sh),
        "completion_preflight": completion_value,
        "launch_env_source_position": source_pos,
        "preflight_guard_position": preflight_pos,
        "proxy_call_position": proxy_pos,
        "campaign_command_position": campaign_pos,
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

    if not env_model:
        failures.append({"reason": "scion_model_missing", "launch_env": str(launch_env)})
    elif env_model != REQUIRED_SCION_MODEL:
        failures.append(
            {
                "reason": "scion_model_not_gpt55",
                "launch_env": str(launch_env),
                "expected": REQUIRED_SCION_MODEL,
                "actual": env_model,
            }
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
        failures.append({"reason": "scion_base_url_missing", "launch_env": str(launch_env)})
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
        "tools/check_gpt55_proxy.py",
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
        run_text.find("--base-url", proxy_pos, campaign_pos if campaign_pos >= 0 else None)
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
        "required_model": REQUIRED_SCION_MODEL,
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


def _run_script_no_early_stop_enforced(
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
    env_disable_early_stop = _shell_assignment_value(
        launch_env_text,
        "DISABLE_EARLY_STOP",
    )
    campaign_pos = _campaign_command_position(run_text)
    campaign_status_pos = run_text.find("STATUS=$?", campaign_pos)
    campaign_end_pos = campaign_status_pos if campaign_status_pos >= 0 else len(run_text)
    campaign_command_block = (
        run_text[campaign_pos:campaign_end_pos] if campaign_pos >= 0 else ""
    )
    command_has_flag = (
        isinstance(manifest_command, str)
        and command_has_shell_flag(manifest_command, "--disable-early-stop")
    )
    run_script_has_flag = command_has_shell_flag(
        campaign_command_block,
        "--disable-early-stop",
    )

    if env_disable_early_stop != "1":
        failures.append(
            {
                "reason": "disable_early_stop_not_enabled",
                "launch_env": str(launch_env),
                "actual": env_disable_early_stop,
            }
        )
    if not command_has_flag:
        failures.append(
            {
                "reason": "manifest_command_missing_disable_early_stop",
                "manifest_path": manifest.get("manifest_path"),
            }
        )
    if campaign_pos < 0:
        failures.append(
            {
                "reason": "missing_campaign_command_marker",
                "marker": RUN_SCRIPT_CAMPAIGN_COMMAND_MARKER,
            }
        )
    elif not run_script_has_flag:
        failures.append(
            {
                "reason": "run_script_campaign_command_missing_disable_early_stop",
                "run_script": str(run_sh),
            }
        )

    detail = {
        "launch_env": str(launch_env),
        "run_script": str(run_sh),
        "disable_early_stop": env_disable_early_stop,
        "manifest_command_has_disable_early_stop": command_has_flag,
        "run_script_campaign_command_has_disable_early_stop": run_script_has_flag,
        "campaign_command_position": campaign_pos,
        "campaign_status_position": campaign_status_pos,
        "failures": failures,
    }
    return ("ok" if not failures else "failed"), detail


def _prepared_manifest_from_contract(root: Path, prepared_contract: Any) -> dict[str, Any]:
    manifest = prepared_contract if isinstance(prepared_contract, dict) else {}
    manifest_path = manifest.get("manifest_path")
    path = Path(manifest_path) if manifest_path else root / "prepared_run_manifest.v1.json"
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
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"'", '"'}
        ):
            value = value[1:-1]
        return value
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
    return (
        stripped_line.startswith("echo ")
        or stripped_line.startswith("#")
    )


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
    status_pos = (
        text.find("STATUS=$?", campaign_pos)
        if campaign_pos >= 0
        else -1
    )
    call_pos = (
        _find_line_after(text, "write_postrun_acceptance_reports", status_pos)
        if status_pos >= 0
        else -1
    )
    exit_pos = (
        text.find('exit "$STATUS"', status_pos)
        if status_pos >= 0
        else -1
    )
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
    if exit_pos < 0:
        failures.append({"reason": "missing_campaign_status_exit"})
    if call_pos >= 0 and exit_pos >= 0 and call_pos > exit_pos:
        failures.append({"reason": "postrun_report_call_after_exit"})

    detail = {
        "run_script": str(run_sh),
        "campaign_command_marker": RUN_SCRIPT_CAMPAIGN_COMMAND_MARKER,
        "campaign_command_position": campaign_pos,
        "campaign_status_position": status_pos,
        "postrun_report_call_position": call_pos,
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

    marker = "WAREHOUSE_DATA_ROOT_MISSING"
    marker_pos, ignored_marker_count = _find_executable_marker_position(text, marker)
    if marker_pos < 0:
        return (
            "ok",
            {
                "run_script": str(run_sh),
                "required": False,
                "reason": "no_data_root_failure_path",
                "ignored_non_executable_marker_count": ignored_marker_count,
            },
        )

    call_pos = _find_line_after(text, "write_postrun_acceptance_reports", marker_pos)
    exit_pos = _find_next_exit_after(text, marker_pos)
    failures: list[dict[str, Any]] = []
    if call_pos < 0:
        failures.append({"reason": "missing_postrun_report_call_after_data_root_failure"})
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
            non_executed = (
                stripped.startswith("#")
                or (not allow_echo and _line_is_non_executed_shell_text(stripped))
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
        declared_paths = {
            _prepared_handoff_manifest_output_path(output, handoff_dir).resolve()
            for output in outputs
        }
        for output in outputs:
            path = _prepared_handoff_manifest_output_path(output, handoff_dir)
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
    detail["family_failures"] = family_failures
    return (
        "failed"
        if missing_outputs
        or inconsistent_outputs
        or unexpected_outputs
        or manifest_failures
        or family_failures
        else "ok",
        detail,
    )


def _prepared_handoff_manifest_output_path(value: str, handoff_dir: Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return handoff_dir / path


def _prompt_context_readiness_check(root: Path) -> tuple[str, Any]:
    readiness_dir = root / "prepared_handoff" / "prompt_context_readiness"
    paths = sorted(readiness_dir.glob("*.json"))
    manifest_path = root / "prepared_run_manifest.v1.json"
    manifest = _read_json(manifest_path)
    manifest_dict = manifest if isinstance(manifest, dict) else {}
    detail: dict[str, Any] = {
        "directory": str(readiness_dir),
        "artifacts": [path.name for path in paths],
        "failures": [],
    }
    failures: list[dict[str, Any]] = []
    if not paths:
        failures.append({"artifact": None, "reason": "missing_prompt_context_readiness"})

    for path in paths:
        payload = _read_json(path)
        failures.extend(
            {"artifact": path.name, **failure}
            for failure in _prompt_context_artifact_failures(
                payload,
                root=root,
                manifest_path=manifest_path,
                manifest=manifest_dict,
            )
        )

    live_markers = {
        "source_markers": {
            name: _repo_path_contains(relative_path, marker)
            for name, (relative_path, marker) in (
                LAUNCH_RESEARCH_FOCUS_PROMPT_MARKERS.items()
            )
        },
        "launch_markers": {
            "prepared_manifest_exists": (
                root / "prepared_run_manifest.v1.json"
            ).is_file(),
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
        },
    }
    family = str(manifest_dict.get("problem_family") or "")
    provider_markers = ACTIVE_SUBJECT_CODE_CONSTRAINT_MARKERS_BY_FAMILY.get(family)
    if provider_markers:
        marker_name = (
            "cvrp_active_subject_code_constraint_source_markers"
            if family == "cvrp"
            else "warehouse_active_subject_code_constraint_source_markers"
        )
        live_markers[marker_name] = {
            name: _repo_path_contains(relative_path, marker)
            for name, (relative_path, marker) in (
                ACTIVE_SUBJECT_CODE_CONSTRAINT_PROMPT_MARKERS
                | provider_markers
            ).items()
        }
    detail["live_markers"] = live_markers
    missing_live = [
        f"{group}.{name}"
        for group, markers in live_markers.items()
        for name, available in markers.items()
        if available is not True
    ]
    if missing_live:
        failures.append(
            {
                "artifact": None,
                "reason": "live_prompt_bridge_markers_missing",
                "missing": missing_live,
            }
        )

    detail["failures"] = failures
    return ("ok" if not failures else "failed"), detail


def _prompt_context_artifact_failures(
    payload: Any,
    *,
    root: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return [{"reason": "invalid_json_payload"}]

    failures: list[dict[str, Any]] = []
    if payload.get("schema_version") != PROMPT_CONTEXT_READINESS_SCHEMA:
        failures.append(
            {
                "reason": "schema_mismatch",
                "schema_version": payload.get("schema_version"),
            }
        )

    expected_identity = {
        "run_root": str(root),
        "prepared_manifest_path": str(manifest_path),
        "prepared_manifest_commit": _manifest_commit(manifest),
        "problem_family": manifest.get("problem_family"),
        "model": _manifest_model_name(manifest),
    }
    for field, expected in expected_identity.items():
        if payload.get(field) != expected:
            failures.append(
                {
                    "reason": "artifact_identity_mismatch",
                    "field": field,
                    "expected": expected,
                    "actual": payload.get(field),
                }
            )

    boundary_expectations = {
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
        "raw_provider_prompt_rendered": False,
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

    readiness = payload.get("readiness")
    readiness_dict = readiness if isinstance(readiness, dict) else {}
    missing_required = readiness_dict.get("missing_required")
    if readiness_dict.get("ready_for_launch_prompt_audit") is not True:
        failures.append(
            {
                "reason": "prompt_audit_not_ready",
                "status": readiness_dict.get("status"),
            }
        )
    if missing_required != []:
        failures.append(
            {
                "reason": "prompt_audit_missing_required",
                "missing_required": missing_required,
            }
        )

    signals = payload.get("signals")
    signals_dict = signals if isinstance(signals, dict) else {}
    bridge = signals_dict.get("prepared_research_focus_prompt_bridge")
    if not isinstance(bridge, dict):
        failures.append({"reason": "prepared_focus_bridge_missing"})
        return failures

    if bridge.get("required") is not True:
        failures.append(
            {
                "reason": "prepared_focus_bridge_not_required",
                "required": bridge.get("required"),
            }
        )
    if bridge.get("available") is not True:
        failures.append(
            {
                "reason": "prepared_focus_bridge_unavailable",
                "available": bridge.get("available"),
            }
        )
    if bridge.get("runtime_generated_after_launch") is True:
        failures.append({"reason": "prepared_focus_bridge_runtime_generated"})

    detail = bridge.get("detail")
    detail_dict = detail if isinstance(detail, dict) else {}
    for group in ("source_markers", "launch_markers"):
        markers = detail_dict.get(group)
        markers_dict = markers if isinstance(markers, dict) else {}
        missing = [
            name
            for name, available in markers_dict.items()
            if available is not True
        ]
        if not markers_dict or missing:
            failures.append(
                {
                    "reason": f"prepared_focus_bridge_{group}_missing",
                    "missing": missing or ["<all>"],
                }
            )

    family = str(manifest.get("problem_family") or "")
    bridge_signal_name = ACTIVE_SUBJECT_CODE_CONSTRAINT_SIGNAL_NAMES.get(family)
    if bridge_signal_name:
        failure_prefix = (
            "cvrp_active_subject_code_constraints_bridge"
            if family == "cvrp"
            else "warehouse_active_subject_code_constraints_bridge"
        )
        code_bridge = signals_dict.get(bridge_signal_name)
        if not isinstance(code_bridge, dict):
            failures.append({"reason": f"{failure_prefix}_missing"})
        else:
            if code_bridge.get("required") is not True:
                failures.append(
                    {
                        "reason": f"{failure_prefix}_not_required",
                        "required": code_bridge.get("required"),
                    }
                )
            if code_bridge.get("available") is not True:
                failures.append(
                    {
                        "reason": f"{failure_prefix}_unavailable",
                        "available": code_bridge.get("available"),
                    }
                )
            if code_bridge.get("runtime_generated_after_launch") is True:
                failures.append(
                    {"reason": f"{failure_prefix}_runtime_generated"}
                )
            code_detail = code_bridge.get("detail")
            code_detail_dict = code_detail if isinstance(code_detail, dict) else {}
            for group in ("source_markers", "provider_markers"):
                markers = code_detail_dict.get(group)
                markers_dict = markers if isinstance(markers, dict) else {}
                missing = [
                    name
                    for name, available in markers_dict.items()
                    if available is not True
                ]
                if not markers_dict or missing:
                    failures.append(
                        {
                            "reason": f"{failure_prefix}_{group}_missing",
                            "missing": missing or ["<all>"],
                        }
                    )

    return failures


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

    failures.extend(_prepared_problem_summary_failures(payload))
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
    report_metadata_dict = (
        report_metadata if isinstance(report_metadata, dict) else {}
    )
    expected_identity = {
        "manifest_path": str(manifest_path),
        "problem_family": manifest_dict.get("problem_family"),
        "model": _manifest_model_name(manifest_dict),
        "control_pair_key": report_metadata_dict.get("control_pair_key"),
        "resume_from_campaign": manifest_dict.get("resume_from_campaign"),
    }
    for field, expected in expected_identity.items():
        if contract.get(field) != expected:
            failures.append(
                {
                    "reason": "prepared_run_contract_identity_mismatch",
                    "field": field,
                    "expected": expected,
                    "actual": contract.get(field),
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
        if brief_contract.get(field) != inventory_contract.get(field):
            failures.append(
                {
                    "reason": f"prepared_contract_{field}_mismatch",
                    "field": field,
                    "brief": brief_contract.get(field),
                    "inventory": inventory_contract.get(field),
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
    if (
        value.get("consistent") is True
        and value.get("commit") == value.get("manifest_commit")
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
        normalized[key] = check
    return normalized


def _prepared_problem_summary_failures(payload: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    contract = payload.get("prepared_run_contract")
    contract_dict = contract if isinstance(contract, dict) else {}
    problem_family = str(contract_dict.get("problem_family") or "")
    required = PREPARED_PROBLEM_SUMMARY_REQUIREMENTS.get(problem_family)
    if required:
        field = str(required["field"])
        summary = payload.get(field)
        if not isinstance(summary, dict) or summary.get("available") is not True:
            return [
                {
                    "reason": "problem_summary_missing_for_problem_family",
                    "problem_family": problem_family,
                    "expected_summary": field,
                    "available": (
                        summary.get("available") if isinstance(summary, dict) else None
                    ),
                }
            ]
        failures.extend(
            {
                "summary": field,
                **failure,
            }
            for failure in _prepared_problem_summary_field_failures(
                summary,
                expected_schema=str(required["schema"]),
                conclusion_flag=str(required["conclusion_flag"]),
                evidence_gap=str(required["evidence_gap"]),
            )
        )
        for other_family, other in PREPARED_PROBLEM_SUMMARY_REQUIREMENTS.items():
            other_field = str(other["field"])
            if other_family == problem_family:
                continue
            other_summary = payload.get(other_field)
            if (
                isinstance(other_summary, dict)
                and other_summary.get("available") is True
            ):
                failures.append(
                    {
                        "summary": other_field,
                        "reason": "unexpected_problem_summary_available",
                        "problem_family": problem_family,
                    }
                )
        return failures

    for field, required in (
        (str(item["field"]), item)
        for item in PREPARED_PROBLEM_SUMMARY_REQUIREMENTS.values()
    ):
        summary = payload.get(field)
        if not isinstance(summary, dict) or summary.get("available") is not True:
            continue
        failures.extend(
            {
                "summary": field,
                **failure,
            }
            for failure in _prepared_problem_summary_field_failures(
                summary,
                expected_schema=str(required["schema"]),
                conclusion_flag=str(required["conclusion_flag"]),
                evidence_gap=str(required["evidence_gap"]),
            )
        )
    return failures


def _prepared_problem_summary_field_failures(
    summary: dict[str, Any],
    *,
    expected_schema: str,
    conclusion_flag: str,
    evidence_gap: str,
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    if summary.get("schema_version") != expected_schema:
        failures.append(
            {
                "reason": "problem_summary_schema_mismatch",
                "expected": expected_schema,
                "actual": summary.get("schema_version"),
            }
        )
    boundary_expectations = {
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
    }
    for key, expected in boundary_expectations.items():
        if summary.get(key) is not expected:
            failures.append(
                {
                    "reason": "problem_summary_boundary_flag_mismatch",
                    "field": key,
                    "expected": expected,
                    "actual": summary.get(key),
                }
            )
    if summary.get("current_run_evidence") is not False:
        failures.append(
            {
                "reason": "problem_summary_current_run_evidence_not_false",
                "current_run_evidence": summary.get("current_run_evidence"),
            }
        )
    if summary.get("interpretation") != "prepared_only_launch_required":
        failures.append(
            {
                "reason": "problem_summary_interpretation_mismatch",
                "interpretation": summary.get("interpretation"),
            }
        )
    if summary.get(conclusion_flag) is not True:
        failures.append(
            {
                "reason": "problem_summary_launch_required_flag_missing",
                "field": conclusion_flag,
                "actual": summary.get(conclusion_flag),
            }
        )
    gaps = summary.get("evidence_gaps")
    if not isinstance(gaps, list) or evidence_gap not in gaps:
        failures.append(
            {
                "reason": "problem_summary_launch_required_gap_missing",
                "expected": evidence_gap,
                "actual": gaps,
            }
        )
    deferred_axes = summary.get("deferred_review_axes")
    if not isinstance(deferred_axes, list) or not deferred_axes:
        failures.append({"reason": "problem_summary_deferred_review_axes_missing"})
    if summary.get("review_axes_actionability") != DEFERRED_REVIEW_AXES_ACTIONABILITY:
        failures.append(
            {
                "reason": "problem_summary_review_axes_actionability_mismatch",
                "expected": DEFERRED_REVIEW_AXES_ACTIONABILITY,
                "actual": summary.get("review_axes_actionability"),
            }
        )
    return failures


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
        str(TOOLS_DIR / "check_gpt55_proxy.py"),
        "--base-url",
        base_url,
        "--model",
        model,
        "--timeout-sec",
        str(timeout_sec),
        "--login-url-on-failure",
        "--json",
    ]
    if api_key_env:
        command.extend(["--api-key-env", api_key_env])
    elif api_key:
        command.extend(["--api-key", api_key])
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {
            "stdout": result.stdout[-2000:],
            "stderr": result.stderr[-2000:],
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
        "summary": "Resolve the GPT-5.5 proxy preflight before starting this prepared campaign.",
        "rerun_command": (
            "python scion/tools/check_launch_readiness.py <run_root> "
            "--require-launch-ready --format json"
        ),
        "model": model,
        "base_url": base_url,
    }
    if classification in {"auth_token_invalidated", "not_authenticated", "unauthorized"}:
        action["next_step"] = (
            "Refresh the local proxy login, then rerun launch readiness until "
            "launch_ready=true."
        )
        if login_url:
            action["login_url"] = login_url
    elif classification == "no_available_accounts":
        action["next_step"] = (
            "Wait for an active GPT-5.5 account or refresh the proxy account pool, "
            "then rerun launch readiness."
        )
    elif classification == "rate_limited":
        action["next_step"] = (
            "Wait for the rate limit window to clear, then rerun launch readiness."
        )
    elif classification == "transport_error":
        action["next_step"] = (
            "Start or repair the local GPT-5.5 proxy endpoint, then rerun launch readiness."
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
