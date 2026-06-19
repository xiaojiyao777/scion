#!/usr/bin/env python3
"""Check whether a prepared Scion launch root is safe to start."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from postrun_artifact_inventory import build_inventory  # noqa: E402


SCHEMA_VERSION = "scion.launch_readiness.v1"
PROMPT_CONTEXT_READINESS_SCHEMA = "scion.prepared_prompt_context_readiness.v1"
ANALYSIS_BRIEF_SCHEMA = "scion.postrun_analysis_brief.v1"
UNREADY_EXIT = 64
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
REQUIRED_RUNTIME_GUARD_PATHS = ("scion/tools",)
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
        "prompt_context_readiness_complete",
        *_prompt_context_readiness_check(root),
    )
    add_check(
        "prepared_analysis_brief_current",
        *_prepared_analysis_brief_check(root),
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
        "ok"
        if _run_sh_contains_preflight_failure_report_path(run_sh)
        else "failed",
        "write_postrun_acceptance_reports after pre_campaign_completion_preflight=failed",
    )
    add_check(
        "run_script_strict_postrun_readiness",
        "ok" if _run_sh_contains_strict_postrun_readiness(run_sh) else "failed",
        "check_postrun_acceptance.py --require-current-run-ready and "
        "POSTRUN_READINESS_EXIT_STATUS",
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


def _runtime_guard_path_covers(pathspecs: list[str], required: str) -> bool:
    required = required.strip("/")
    for pathspec in pathspecs:
        if not pathspec or pathspec.startswith(":("):
            continue
        normalized = pathspec.strip("/")
        if normalized in {".", required}:
            return True
        if required.startswith(f"{normalized}/"):
            return True
    return False


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
    missing_markers: list[str] = []
    for name, marker in RUN_SCRIPT_RUNTIME_GUARD_MARKERS:
        position = text.find(marker)
        if position < 0:
            missing_markers.append(name)
        else:
            marker_positions[name] = position

    campaign_position = text.find(RUN_SCRIPT_CAMPAIGN_COMMAND_MARKER)
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
        "failures": failures,
    }
    return ("ok" if not failures else "failed"), detail


def _run_sh_contains_preflight_failure_report_path(run_sh: Path) -> bool:
    try:
        text = run_sh.read_text(encoding="utf-8")
    except OSError:
        return False
    old_marker = '"pre_campaign_completion_preflight":"failed"'
    helper_marker = "tools/write_completion_preflight_status.py"
    marker_positions = [
        pos for pos in (text.find(old_marker), text.find(helper_marker)) if pos >= 0
    ]
    if not marker_positions:
        return False
    marker_pos = min(marker_positions)
    exit_pos = text.find('exit "$PREFLIGHT_STATUS"')
    if exit_pos < 0:
        return False
    return (
        "write_postrun_acceptance_reports() {" in text
        and marker_pos < exit_pos
        and "write_postrun_acceptance_reports" in text[marker_pos:exit_pos]
    )


def _run_sh_contains_strict_postrun_readiness(run_sh: Path) -> bool:
    try:
        text = run_sh.read_text(encoding="utf-8")
    except OSError:
        return False
    return (
        "write_postrun_acceptance_reports() {" in text
        and "tools/check_postrun_acceptance.py" in text
        and "--require-current-run-ready" in text
        and "POSTRUN_READINESS_EXIT_STATUS" in text
    )


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


def _prepared_problem_summary_failures(payload: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for field, conclusion_flag, evidence_gap in (
        (
            "warehouse_followup_summary",
            "launch_required_before_plateau_conclusion",
            "launch_required_before_plateau_conclusion",
        ),
        (
            "cvrp_large_twoopt_summary",
            "launch_required_before_twoopt_conclusion",
            "launch_required_before_bounded_twoopt_conclusion",
        ),
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
                conclusion_flag=conclusion_flag,
                evidence_gap=evidence_gap,
            )
        )
    return failures


def _prepared_problem_summary_field_failures(
    summary: dict[str, Any],
    *,
    conclusion_flag: str,
    evidence_gap: str,
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
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
