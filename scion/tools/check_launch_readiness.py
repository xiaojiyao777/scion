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
UNREADY_EXIT = 64


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
        "postrun_families_complete",
        _contract_check_status(contract_checks, "postrun_families_complete"),
        _contract_check_detail(contract_checks, "postrun_families_complete"),
    )

    run_sh = root / "run.sh"
    add_check("run_script_present", "ok" if run_sh.is_file() else "failed", str(run_sh))
    add_check(
        "run_script_syntax",
        *_run_script_syntax(run_sh),
    )
    add_check(
        "run_script_preflight_failure_reports",
        "ok"
        if _run_sh_contains_preflight_failure_report_path(run_sh)
        else "failed",
        "write_postrun_acceptance_reports after pre_campaign_completion_preflight=failed",
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
