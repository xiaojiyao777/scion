#!/usr/bin/env python3
"""Prepare or launch a warehouse agentic Scion campaign run directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


DEFAULT_EXPERIMENTS_ROOT = Path.home() / "research" / "scion-experiments"
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_BASE_URL = "http://127.0.0.1:8080"
DEFAULT_LOCAL_PROXY_API_KEY = "pwd"
DEFAULT_TIME_LIMIT_SEC = 30
DEFAULT_AGENTIC_SESSION_TIMEOUT_SEC = 900
DEFAULT_PYTHON = Path(sys.executable)
DEFAULT_USER_SUFFIX = "claw"
PREFLIGHT_FAILURE_EXIT_CODE = 64

PROBLEM = "scion/problems/warehouse_delivery/problem.yaml"
PROBLEM_V1 = "scion/problems/warehouse_delivery/problem-v1.yaml"
PROTOCOL = "scion/problems/warehouse_delivery/protocol_prod.yaml"
SPLIT = "scion/problems/warehouse_delivery/split_manifest_prod.yaml"
SEEDS = "scion/problems/warehouse_delivery/seed_ledger.yaml"
MEASUREMENT_GOVERNANCE_CHOICES = ("on", "record-only")
PROPOSAL_CONTEXT_ABLATION_CHOICES = (
    "full",
    "compact-measurement-diagnostics",
    "no-measurement-diagnostics",
    "minimal-research-context",
)
ENV_VAR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
PREPARED_RUN_MANIFEST_SCHEMA = "scion.launcher_prepared_run_manifest.v1"
TASK_DOC = "scion/TASK.md"
CURRENT_STATE_DOC = "scion/docs/status/current-state.md"
ANALYSIS_HANDOFF_DOC = "scion/docs/operations/postrun-analysis-handoff.md"
WAREHOUSE_ANALYSIS_INTENT = (
    "Warehouse champion-v2 continuous-improvement follow-up. Verify whether "
    "the accepted v0.4 positive research path can produce additional useful "
    "research without regressing promotion behavior; inspect branch transfer, "
    "prompt context, runtime/model explanation, and whether any plateau is real "
    "or a missed continuous-promotion opportunity."
)
WAREHOUSE_DEFAULT_AVOID_DIRECTIONS = (
    "restart from baseline instead of champion v2",
    "treat proposal-quality blocks as plateau evidence",
    "treat fast completion as incidental noise rather than runtime-model evidence",
    "treat split_delta_sum==0 as no effect when cost_delta_sum is positive",
    "repeat unbounded merge_vehicles or swap_orders variants without validation-transfer risk controls",
    "launch a broad warehouse matrix before the focused v2 follow-up is analyzed",
)
WAREHOUSE_CURRENT_RESEARCH_FOCUS = {
    "schema_version": "scion.warehouse_research_focus.v1",
    "scope": "report_only_prepared_handoff",
    "accepted_checkpoint": (
        "Champion v2 promoted from the validation-transfer acceptance-contract "
        "run via split-preserving cost compression in pack_compatible_vehicles."
    ),
    "current_question": (
        "Starting from champion v2, determine whether warehouse can produce "
        "additional useful research or whether the observed behavior is a real "
        "post-v2 plateau."
    ),
    "required_evidence": [
        "preserve or improve promotion behavior relative to the v2 checkpoint",
        "inspect branch transfer from the v2 source campaign before judging plateau",
        "distinguish quality-blocked proposals from protocol-evaluated no-effect candidates",
        "interpret split-preserving cost-compression with cost_delta and improving-move telemetry, not split_delta alone",
        "explain fast completion through the declared warehouse runtime/problem model",
    ],
    "default_avoid_directions": list(WAREHOUSE_DEFAULT_AVOID_DIRECTIONS),
    "decision_boundary": (
        "This focus is proposal/delegated-analysis guidance only and must not "
        "enter DecisionFeatures, Protocol gates, promotion input, or scheduler "
        "state."
    ),
}
POSTRUN_ACCEPTANCE_FAMILIES = (
    "summaries",
    "failures",
    "research_efficiency",
    "manifests",
    "analysis_brief",
    "inventory",
    "readiness",
    "rebuild",
)
PREPARED_HANDOFF_FAMILIES = (
    "analysis_brief",
    "inventory",
    "prompt_context_readiness",
    "launch_readiness",
    "rebuild",
)


COMPLETION_PREFLIGHT_SNIPPET = r'''
if [[ "${COMPLETION_PREFLIGHT:-0}" == "1" ]]; then
  PREFLIGHT_DETAIL="$RUN_ROOT/pre_campaign_completion_preflight.v1.json"
  "$PY" "$SCION_DIR/tools/check_gpt55_proxy.py" \
    --base-url "$SCION_BASE_URL" \
    --model "$SCION_MODEL" \
    --api-key "$SCION_API_KEY" \
    --timeout-sec 60 \
    --login-url-on-failure \
    --json \
    > "$PREFLIGHT_DETAIL" 2>> "$RUN_ROOT/run.log"
  PREFLIGHT_STATUS=$?
  echo "COMPLETION_PREFLIGHT_DETAIL:$PREFLIGHT_DETAIL" >> "$RUN_ROOT/run.log"
  if [[ "$PREFLIGHT_STATUS" -ne 0 ]]; then
    {
      echo "WRAPPER_EXIT_STATUS:$PREFLIGHT_STATUS"
      echo "ENDED_AT:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      echo "PRE_CAMPAIGN_COMPLETION_PREFLIGHT_FAILED:1"
    } > "$RUN_ROOT/exit.txt"
    "$PY" "$SCION_DIR/tools/write_completion_preflight_status.py" \
      --output "$RUN_ROOT/run_status.json" \
      --exit-code "$PREFLIGHT_STATUS" \
      --detail "$PREFLIGHT_DETAIL"
    write_postrun_acceptance_reports
    exit "$PREFLIGHT_STATUS"
  fi
fi
'''


POSTRUN_REPORT_FUNCTION_SNIPPET = r'''
write_postrun_acceptance_reports() {
  if [[ "${POSTRUN_REPORTS:-1}" != "1" ]]; then
    return 0
  fi
  REPORT_DIR="$RUN_ROOT/postrun_acceptance"
  REPORT_STEM="warehouse_${MEASUREMENT_GOVERNANCE//-/_}_${PROPOSAL_CONTEXT_ABLATION//-/_}"
  OBSERVED_CONTROL_ARM="${MEASUREMENT_GOVERNANCE//-/_}"
  echo "POSTRUN_ACCEPTANCE_DIR:$REPORT_DIR" >> "$RUN_ROOT/exit.txt"
  {
    echo "POSTRUN_REPORTS_STARTED_AT:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "POSTRUN_REPORT_DIR:$REPORT_DIR"
  } >> "$RUN_ROOT/run.log"
  rebuild_args=(
    "$RUN_ROOT"
    --report-stem "$REPORT_STEM"
    --observed-control-arm "$OBSERVED_CONTROL_ARM"
  )
  if [[ -n "${CONTROL_PAIR_KEY:-}" ]]; then
    rebuild_args+=(--control-pair-key "$CONTROL_PAIR_KEY")
  fi
  POSTRUN_STATUS=0
  "$PY" "$SCION_DIR/tools/rebuild_postrun_acceptance.py" \
    "${rebuild_args[@]}" \
    --strict >> "$RUN_ROOT/run.log" 2>&1 || POSTRUN_STATUS=$?
  echo "POSTRUN_REPORTS_EXIT_STATUS:$POSTRUN_STATUS" >> "$RUN_ROOT/run.log"
  mkdir -p "$REPORT_DIR/readiness"
  POSTRUN_READINESS_STATUS=0
  "$PY" "$SCION_DIR/tools/check_postrun_acceptance.py" "$RUN_ROOT" \
    --require-current-run-ready \
    --format json \
    > "$REPORT_DIR/readiness/$REPORT_STEM.postrun_acceptance_readiness.v1.json" \
    2>> "$RUN_ROOT/run.log" || POSTRUN_READINESS_STATUS=$?
  "$PY" "$SCION_DIR/tools/check_postrun_acceptance.py" "$RUN_ROOT" \
    --format markdown \
    > "$REPORT_DIR/readiness/$REPORT_STEM.postrun_acceptance_readiness.md" \
    2>> "$RUN_ROOT/run.log" || true
  {
    echo "POSTRUN_READINESS_EXIT_STATUS:$POSTRUN_READINESS_STATUS"
    echo "POSTRUN_REPORTS_FINISHED_AT:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } >> "$RUN_ROOT/run.log"
}
'''


POSTRUN_REPORT_SNIPPET = r'''
write_postrun_acceptance_reports
'''


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _git_commit(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"failed to resolve git commit: {exc.stderr.strip()}") from exc
    return result.stdout.strip()


def _model_slug(model: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "", model).lower()
    return slug or "model"


def _safe_label(label: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", label.strip())
    normalized = normalized.strip(".-_")
    if not normalized:
        raise SystemExit("--label must contain at least one filename-safe character")
    return normalized


def _prepared_control_pair_key(value: str | None, *, label: str) -> str:
    explicit = str(value or "").strip()
    if explicit:
        return explicit
    key = f"warehouse.{label}:prepared"
    if len(key) <= 128:
        return key
    digest = hashlib.sha1(label.encode("utf-8")).hexdigest()[:8]
    suffix = f":prepared.{digest}"
    max_label_len = max(1, 128 - len("warehouse.") - len(suffix))
    trimmed = label[:max_label_len].rstrip("-._") or label[:max_label_len]
    return f"warehouse.{trimmed}{suffix}"


def _shell_assign(name: str, value: object) -> str:
    return f"{name}={shlex.quote(str(value))}"


def _validate_env_var_name(name: str) -> None:
    if not ENV_VAR_RE.fullmatch(name):
        raise SystemExit(
            "--api-key-env must be a valid shell environment variable name"
        )


def _default_api_key_for_base_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if normalized in {
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8080/v1",
        "http://localhost:8080",
        "http://localhost:8080/v1",
    }:
        return DEFAULT_LOCAL_PROXY_API_KEY
    return ""


def _resolve_api_key(args: argparse.Namespace) -> tuple[str, str]:
    api_key_env = args.api_key_env or ""
    if api_key_env:
        return "", api_key_env
    if args.api_key is not None:
        return args.api_key, ""
    return _default_api_key_for_base_url(args.base_url), ""


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _rewrite_case_path(value: Any, *, data_root: Path) -> Any:
    if not isinstance(value, str):
        return value
    path = Path(value)
    if path.is_absolute():
        parts = path.parts
        if "production" in parts:
            production_index = parts.index("production")
            return str(data_root.joinpath(*parts[production_index:]))
        return value.replace("/home/clawd/research/scion-data", str(data_root))
    return value


def _rewrite_warehouse_configs(
    *,
    repo_root: Path,
    config_dir: Path,
    warehouse_data_root: Path,
    problem: str,
    problem_v1: str,
    protocol: str,
    split: str,
    seeds: str,
) -> dict[str, Path]:
    source_paths = {
        "problem": _resolve_source_path(repo_root, problem),
        "problem_v1": _resolve_source_path(repo_root, problem_v1),
        "protocol": _resolve_source_path(repo_root, protocol),
        "split": _resolve_source_path(repo_root, split),
        "seeds": _resolve_source_path(repo_root, seeds),
    }
    for name, path in source_paths.items():
        if not path.exists():
            raise SystemExit(f"{name} source not found: {path}")

    config_dir.mkdir(parents=True, exist_ok=True)
    problem_out = config_dir / "problem.yaml"
    problem_v1_out = config_dir / "problem-v1.yaml"
    protocol_out = config_dir / "protocol_prod.yaml"
    split_out = config_dir / "split_manifest_prod.yaml"
    seeds_out = config_dir / "seed_ledger.yaml"

    surrogate_root = repo_root / "surrogate"
    canary_case = surrogate_root / "data" / "instance_small_1.json"

    for source, destination in (
        (source_paths["problem"], problem_out),
        (source_paths["problem_v1"], problem_v1_out),
    ):
        payload = _load_yaml(source)
        payload["root_dir"] = str(surrogate_root)
        if "canary_case_path" in payload:
            payload["canary_case_path"] = str(canary_case)
        _write_yaml(destination, payload)

    split_payload = _load_yaml(source_paths["split"])
    split_payload["safe_data_roots"] = [str(warehouse_data_root)]
    for section in ("canary", "screening", "validation", "frozen"):
        values = split_payload.get(section)
        if isinstance(values, list):
            split_payload[section] = [
                _rewrite_case_path(value, data_root=warehouse_data_root)
                for value in values
            ]
    _write_yaml(split_out, split_payload)

    protocol_out.write_text(
        source_paths["protocol"].read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    seeds_out.write_text(
        source_paths["seeds"].read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    return {
        "problem": problem_out,
        "problem_v1": problem_v1_out,
        "protocol": protocol_out,
        "split": split_out,
        "seeds": seeds_out,
    }


def _resolve_source_path(repo_root: Path, spec_path: str) -> Path:
    path = Path(spec_path).expanduser()
    if path.is_absolute():
        return path
    return repo_root / path


def _build_command(env: dict[str, object]) -> str:
    return (
        f"{env['PY']} -m scion.cli.main run "
        f"--problem {env['PROBLEM']} "
        f"--protocol {env['PROTOCOL']} "
        f"--split {env['SPLIT']} "
        f"--seeds {env['SEEDS']} "
        f"--campaign-dir {env['CAMPAIGN_DIR']} "
        f"--rounds {env['ROUNDS']} "
        f"--time-limit-sec {env['TIME_LIMIT_SEC']} "
        f"--agentic-session-timeout-sec {env['AGENTIC_SESSION_TIMEOUT_SEC']} "
        f"--measurement-governance {env['MEASUREMENT_GOVERNANCE']} "
        f"--proposal-context-ablation {env['PROPOSAL_CONTEXT_ABLATION']} "
        "--disable-early-stop "
        "--agentic-proposal"
    )


def _write_launch_env(run_root: Path, env: dict[str, object]) -> None:
    ordered_keys = [
        "RUN_ROOT",
        "CAMPAIGN_DIR",
        "RESUME_FROM_CAMPAIGN",
        "PREPARED_RUN_MANIFEST",
        "CONFIG_DIR",
        "REPO_ROOT",
        "SCION_DIR",
        "PY",
        "PYTHONPATH",
        "SCION_MODEL",
        "SCION_BASE_URL",
        "SCION_API_KEY",
        "SCION_API_KEY_ENV",
        "SCION_SDK_MAX_RETRIES",
        "SCION_LLM_MAX_RETRIES",
        "SCION_WAREHOUSE_DATA_ROOT",
        "SCION_PROBLEM_DATA_ROOT",
        "COMPLETION_PREFLIGHT",
        "POSTRUN_REPORTS",
        "PROBLEM",
        "PROBLEM_V1",
        "PROTOCOL",
        "SPLIT",
        "SEEDS",
        "ROUNDS",
        "TIME_LIMIT_SEC",
        "MEASUREMENT_GOVERNANCE",
        "PROPOSAL_CONTEXT_ABLATION",
        "CONTROL_PAIR_KEY",
        "AGENTIC_PROPOSAL",
        "DISABLE_EARLY_STOP",
        "AGENTIC_SESSION_TIMEOUT_SEC",
        "GIT_COMMIT",
        "GIT_RUNTIME_GUARD_PATHS",
        "STARTED_UTC",
    ]
    content = "\n".join(_shell_assign(key, env[key]) for key in ordered_keys) + "\n"
    launch_env = run_root / "launch.env"
    launch_env.write_text(content, encoding="utf-8")
    launch_env.chmod(0o600)


def _write_run_sh(run_root: Path, command: str) -> None:
    content = f"""#!/usr/bin/env bash
set -uo pipefail
_INHERITED_SCION_API_KEY="${{SCION_API_KEY:-}}"
source "$(dirname "$0")/launch.env"
export PYTHONPATH SCION_MODEL SCION_BASE_URL SCION_API_KEY SCION_SDK_MAX_RETRIES SCION_LLM_MAX_RETRIES SCION_WAREHOUSE_DATA_ROOT SCION_PROBLEM_DATA_ROOT PREPARED_RUN_MANIFEST
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
{POSTRUN_REPORT_FUNCTION_SNIPPET}
if [[ -n "${{SCION_API_KEY_ENV:-}}" ]]; then
  if [[ "$SCION_API_KEY_ENV" == "SCION_API_KEY" ]]; then
    _RESOLVED_SCION_API_KEY="$_INHERITED_SCION_API_KEY"
  else
    _RESOLVED_SCION_API_KEY="${{!SCION_API_KEY_ENV:-}}"
  fi
  if [[ -z "$_RESOLVED_SCION_API_KEY" ]]; then
    {{
      echo "WRAPPER_EXIT_STATUS:{PREFLIGHT_FAILURE_EXIT_CODE}"
      echo "ENDED_AT:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      echo "SCION_API_KEY_ENV_MISSING:$SCION_API_KEY_ENV"
    }} > "$RUN_ROOT/exit.txt"
    printf '{{"schema":"outer-wrapper.v1","status":"finished","wrapper_exit_status":{PREFLIGHT_FAILURE_EXIT_CODE},"api_key_env_missing":"%s"}}\\n' "$SCION_API_KEY_ENV" > "$RUN_ROOT/run_status.json"
    write_postrun_acceptance_reports
    exit {PREFLIGHT_FAILURE_EXIT_CODE}
  fi
  SCION_API_KEY="$_RESOLVED_SCION_API_KEY"
fi
unset _INHERITED_SCION_API_KEY _RESOLVED_SCION_API_KEY
if ! cd "$SCION_DIR"; then
  {{
    echo "WRAPPER_EXIT_STATUS:{PREFLIGHT_FAILURE_EXIT_CODE}"
    echo "ENDED_AT:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "SCION_DIR_MISSING:$SCION_DIR"
  }} > "$RUN_ROOT/exit.txt"
  printf '{{"schema":"outer-wrapper.v1","status":"finished","wrapper_exit_status":{PREFLIGHT_FAILURE_EXIT_CODE},"scion_dir_missing":"%s"}}\\n' "$SCION_DIR" > "$RUN_ROOT/run_status.json"
  write_postrun_acceptance_reports
  exit {PREFLIGHT_FAILURE_EXIT_CODE}
fi
read -r -a _GIT_RUNTIME_GUARD_PATHS <<< "$GIT_RUNTIME_GUARD_PATHS"
if [[ -n "$(git -C "$REPO_ROOT" status --porcelain -- "${{_GIT_RUNTIME_GUARD_PATHS[@]}}")" ]]; then
  {{
    echo "WRAPPER_EXIT_STATUS:{PREFLIGHT_FAILURE_EXIT_CODE}"
    echo "ENDED_AT:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "GIT_RUNTIME_DIRTY:$GIT_RUNTIME_GUARD_PATHS"
  }} > "$RUN_ROOT/exit.txt"
  printf '{{"schema":"outer-wrapper.v1","status":"finished","wrapper_exit_status":{PREFLIGHT_FAILURE_EXIT_CODE},"git_runtime_dirty":true}}\\n' > "$RUN_ROOT/run_status.json"
  write_postrun_acceptance_reports
  exit {PREFLIGHT_FAILURE_EXIT_CODE}
fi
_ACTUAL_GIT_COMMIT="$(git -C "$REPO_ROOT" rev-parse --short HEAD)"
if [[ "$_ACTUAL_GIT_COMMIT" != "$GIT_COMMIT" ]]; then
  if git -C "$REPO_ROOT" diff --quiet "$GIT_COMMIT" HEAD -- "${{_GIT_RUNTIME_GUARD_PATHS[@]}}"; then
    echo "GIT_COMMIT_DOC_ONLY_MISMATCH_ALLOWED:expected=$GIT_COMMIT actual=$_ACTUAL_GIT_COMMIT paths=$GIT_RUNTIME_GUARD_PATHS" >> "$RUN_ROOT/run.log"
  else
    {{
      echo "WRAPPER_EXIT_STATUS:{PREFLIGHT_FAILURE_EXIT_CODE}"
      echo "ENDED_AT:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      echo "GIT_COMMIT_MISMATCH:expected=$GIT_COMMIT actual=$_ACTUAL_GIT_COMMIT paths=$GIT_RUNTIME_GUARD_PATHS"
    }} > "$RUN_ROOT/exit.txt"
    printf '{{"schema":"outer-wrapper.v1","status":"finished","wrapper_exit_status":{PREFLIGHT_FAILURE_EXIT_CODE},"git_runtime_commit_mismatch":true}}\\n' > "$RUN_ROOT/run_status.json"
    write_postrun_acceptance_reports
    exit {PREFLIGHT_FAILURE_EXIT_CODE}
  fi
fi
unset _ACTUAL_GIT_COMMIT _GIT_RUNTIME_GUARD_PATHS
{{
  echo "STARTED_AT:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "GIT_COMMIT:$GIT_COMMIT"
  echo "CWD:$PWD"
  echo "COMMAND:{command}"
}} >> "$RUN_ROOT/run.log"
if [[ ! -d "$SCION_WAREHOUSE_DATA_ROOT/production/generated" || ! -d "$SCION_WAREHOUSE_DATA_ROOT/production/converted" ]]; then
  {{
    echo "WRAPPER_EXIT_STATUS:{PREFLIGHT_FAILURE_EXIT_CODE}"
    echo "ENDED_AT:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "WAREHOUSE_DATA_ROOT_MISSING:$SCION_WAREHOUSE_DATA_ROOT"
  }} > "$RUN_ROOT/exit.txt"
  printf '{{"schema":"outer-wrapper.v1","status":"finished","wrapper_exit_status":{PREFLIGHT_FAILURE_EXIT_CODE},"warehouse_data_root_missing":true}}\\n' > "$RUN_ROOT/run_status.json"
  write_postrun_acceptance_reports
  exit {PREFLIGHT_FAILURE_EXIT_CODE}
fi
{COMPLETION_PREFLIGHT_SNIPPET}
"$PY" -m scion.cli.main run \\
  --problem "$PROBLEM" \\
  --protocol "$PROTOCOL" \\
  --split "$SPLIT" \\
  --seeds "$SEEDS" \\
  --campaign-dir "$CAMPAIGN_DIR" \\
  --rounds "$ROUNDS" \\
  --time-limit-sec "$TIME_LIMIT_SEC" \\
  --agentic-session-timeout-sec "$AGENTIC_SESSION_TIMEOUT_SEC" \\
  --measurement-governance "$MEASUREMENT_GOVERNANCE" \\
  --proposal-context-ablation "$PROPOSAL_CONTEXT_ABLATION" \\
  --disable-early-stop \\
  --agentic-proposal \\
  >> "$RUN_ROOT/run.log" 2>&1
STATUS=$?
{{
  echo "WRAPPER_EXIT_STATUS:$STATUS"
  echo "ENDED_AT:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  if [[ -f "$CAMPAIGN_DIR/run_status.json" ]]; then
    echo "CAMPAIGN_RUN_STATUS:$CAMPAIGN_DIR/run_status.json"
  fi
  if [[ -f "$CAMPAIGN_DIR/campaign_summary.json" ]]; then
    echo "CAMPAIGN_SUMMARY:$CAMPAIGN_DIR/campaign_summary.json"
  fi
}} > "$RUN_ROOT/exit.txt"
if [[ -f "$CAMPAIGN_DIR/run_status.json" ]]; then
  cp "$CAMPAIGN_DIR/run_status.json" "$RUN_ROOT/run_status.json"
else
  printf '{{"schema":"outer-wrapper.v1","status":"finished","wrapper_exit_status":%s}}\\n' "$STATUS" > "$RUN_ROOT/run_status.json"
fi
{POSTRUN_REPORT_SNIPPET}
exit "$STATUS"
"""
    run_sh = run_root / "run.sh"
    run_sh.write_text(content, encoding="utf-8")
    run_sh.chmod(0o755)


def _launch(run_root: Path) -> str:
    result = subprocess.run(
        ["bash", "-lc", "nohup setsid bash run.sh > nohup.log 2>&1 & echo $!"],
        cwd=run_root,
        check=True,
        text=True,
        capture_output=True,
    )
    pid = result.stdout.strip()
    (run_root / "pid").write_text(pid + "\n", encoding="utf-8")
    return pid


def _write_prepare_status(run_root: Path, env: dict[str, object]) -> None:
    campaign_dir = Path(env["CAMPAIGN_DIR"])
    resume_from = str(env.get("RESUME_FROM_CAMPAIGN") or "")
    status = {
        "schema": "scion.launcher_prepare.v1",
        "status": "prepared",
        "prepared_only": True,
        "run_root": str(run_root),
        "campaign_dir": str(campaign_dir),
        "resume_from_campaign": resume_from,
        "copied_campaign_status_present": bool(resume_from)
        and (campaign_dir / "run_status.json").is_file(),
        "copied_campaign_summary_present": bool(resume_from)
        and (campaign_dir / "campaign_summary.json").is_file(),
        "scion_model": str(env["SCION_MODEL"]),
        "scion_base_url": str(env["SCION_BASE_URL"]),
        "completion_preflight": bool(int(env["COMPLETION_PREFLIGHT"])),
        "postrun_reports": bool(int(env["POSTRUN_REPORTS"])),
        "control_pair_key": str(env.get("CONTROL_PAIR_KEY") or ""),
        "git_commit": str(env["GIT_COMMIT"]),
        "started_utc": str(env["STARTED_UTC"]),
    }
    (run_root / "run_status.json").write_text(
        json.dumps(status, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_prepared_run_manifest(
    run_root: Path,
    env: dict[str, object],
    *,
    command: str,
) -> None:
    manifest = {
        "schema_version": PREPARED_RUN_MANIFEST_SCHEMA,
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
        "problem_family": "warehouse_delivery",
        "analysis_intent": WAREHOUSE_ANALYSIS_INTENT,
        "research_focus": WAREHOUSE_CURRENT_RESEARCH_FOCUS,
        "task_doc": TASK_DOC,
        "current_state_doc": CURRENT_STATE_DOC,
        "analysis_handoff_doc": ANALYSIS_HANDOFF_DOC,
        "run_root": str(run_root),
        "campaign_dir": str(env["CAMPAIGN_DIR"]),
        "resume_from_campaign": str(env.get("RESUME_FROM_CAMPAIGN") or ""),
        "command": command,
        "launch_command": "nohup setsid bash run.sh > nohup.log 2>&1 &",
        "model": {
            "name": str(env["SCION_MODEL"]),
            "base_url": str(env["SCION_BASE_URL"]),
            "completion_preflight": bool(int(env["COMPLETION_PREFLIGHT"])),
        },
        "git": {
            "commit": str(env["GIT_COMMIT"]),
            "runtime_guard_paths": str(env["GIT_RUNTIME_GUARD_PATHS"]),
        },
        "config": {
            "problem": str(env["PROBLEM"]),
            "problem_v1": str(env["PROBLEM_V1"]),
            "protocol": str(env["PROTOCOL"]),
            "split": str(env["SPLIT"]),
            "seeds": str(env["SEEDS"]),
            "warehouse_data_root": str(env["SCION_WAREHOUSE_DATA_ROOT"]),
            "problem_data_root": str(env["SCION_PROBLEM_DATA_ROOT"]),
        },
        "execution": {
            "rounds": int(env["ROUNDS"]),
            "time_limit_sec": int(env["TIME_LIMIT_SEC"]),
            "agentic_session_timeout_sec": int(env["AGENTIC_SESSION_TIMEOUT_SEC"]),
            "measurement_governance": str(env["MEASUREMENT_GOVERNANCE"]),
            "proposal_context_ablation": str(env["PROPOSAL_CONTEXT_ABLATION"]),
            "agentic_proposal": bool(int(env["AGENTIC_PROPOSAL"])),
            "disable_early_stop": bool(int(env["DISABLE_EARLY_STOP"])),
        },
        "report_metadata": {
            "control_pair_key": str(env.get("CONTROL_PAIR_KEY") or ""),
            "postrun_reports": bool(int(env["POSTRUN_REPORTS"])),
            "postrun_report_dir": str(run_root / "postrun_acceptance"),
            "postrun_acceptance_families": list(POSTRUN_ACCEPTANCE_FAMILIES),
            "prepared_handoff_dir": str(run_root / "prepared_handoff"),
            "prepared_handoff_families": list(PREPARED_HANDOFF_FAMILIES),
        },
        "acceptance_focus": [
            "Check that existing warehouse promotion behavior does not regress.",
            "Distinguish real plateau from missed continuous-promotion opportunities.",
            "Explain observed fast completion through the declared runtime/problem model.",
            "Use research_focus to separate champion-v2 follow-up evidence from "
            "quality-block, fast-completion, or split-delta-only false plateau "
            "signals.",
            "Treat this manifest as launch/handoff evidence only, not as Decision input.",
        ],
        "started_utc": str(env["STARTED_UTC"]),
    }
    (run_root / "prepared_run_manifest.v1.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (run_root / "prepared_run_manifest.md").write_text(
        _render_prepared_run_manifest_markdown(manifest),
        encoding="utf-8",
    )


def _render_prepared_run_manifest_markdown(manifest: dict[str, object]) -> str:
    config = manifest["config"]
    execution = manifest["execution"]
    reports = manifest["report_metadata"]
    research_focus = manifest["research_focus"]
    assert isinstance(config, dict)
    assert isinstance(execution, dict)
    assert isinstance(reports, dict)
    assert isinstance(research_focus, dict)
    lines = [
        "# Prepared Run Manifest",
        "",
        f"- Schema: `{manifest['schema_version']}`",
        f"- Problem family: `{manifest['problem_family']}`",
        f"- Report-only: `{manifest['report_only']}`",
        f"- Decision features excluded: `{manifest['decision_features_excluded']}`",
        f"- Run root: `{manifest['run_root']}`",
        f"- Campaign dir: `{manifest['campaign_dir']}`",
        f"- Resume from campaign: `{manifest['resume_from_campaign'] or ''}`",
        f"- Analysis handoff: `{manifest['analysis_handoff_doc']}`",
        "",
        "## Analysis Intent",
        str(manifest["analysis_intent"]),
        "",
        "## Current Research Focus",
        f"- Accepted checkpoint: {research_focus['accepted_checkpoint']}",
        f"- Question: {research_focus['current_question']}",
        f"- Decision boundary: {research_focus['decision_boundary']}",
        "- Required evidence:",
    ]
    for item in research_focus["required_evidence"]:
        lines.append(f"  - {item}")
    lines.append("- Default-avoid directions:")
    for item in research_focus["default_avoid_directions"]:
        lines.append(f"  - {item}")
    lines.extend([
        "",
        "## Config",
    ])
    for key in (
        "problem",
        "problem_v1",
        "protocol",
        "split",
        "seeds",
        "warehouse_data_root",
        "problem_data_root",
    ):
        lines.append(f"- {key}: `{config[key]}`")
    lines.extend(["", "## Execution"])
    for key in (
        "rounds",
        "time_limit_sec",
        "agentic_session_timeout_sec",
        "measurement_governance",
        "proposal_context_ablation",
        "agentic_proposal",
        "disable_early_stop",
    ):
        lines.append(f"- {key}: `{execution[key]}`")
    lines.extend(
        [
            "",
            "## Postrun Acceptance",
            f"- Enabled: `{reports['postrun_reports']}`",
            f"- Report dir: `{reports['postrun_report_dir']}`",
            f"- Families: `{', '.join(reports['postrun_acceptance_families'])}`",
            f"- Control pair key: `{reports['control_pair_key']}`",
            f"- Prepared handoff dir: `{reports['prepared_handoff_dir']}`",
            f"- Prepared handoff families: `{', '.join(reports['prepared_handoff_families'])}`",
            "",
            "## Acceptance Focus",
        ]
    )
    for item in manifest["acceptance_focus"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def _write_prepared_handoff(run_root: Path, env: dict[str, object]) -> None:
    tools_dir = Path(__file__).resolve().parent
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))

    from rebuild_prepared_handoff import rebuild_prepared_handoff  # noqa: PLC0415

    report_stem = (
        "warehouse_"
        f"{str(env['MEASUREMENT_GOVERNANCE']).replace('-', '_')}_"
        f"{str(env['PROPOSAL_CONTEXT_ABLATION']).replace('-', '_')}"
    )
    rebuild_prepared_handoff(run_root, report_stem=report_stem, strict=True)


def prepare(args: argparse.Namespace) -> tuple[Path, str | None]:
    repo_root = _repo_root()
    scion_dir = repo_root / "scion"
    started_at = datetime.now(timezone.utc)
    timestamp = started_at.strftime("%Y%m%dT%H%M%SZ")
    label = _safe_label(args.label)
    run_name = (
        f"{label}-{args.rounds}r-{_model_slug(args.model)}-"
        f"{timestamp}-{DEFAULT_USER_SUFFIX}"
    )
    run_root = args.experiments_root.expanduser().resolve() / run_name
    campaign_dir = run_root / "campaign"
    config_dir = run_root / "config"
    if args.resume_from_campaign is None:
        campaign_dir.mkdir(parents=True, exist_ok=False)
        resume_from_campaign = ""
    else:
        resume_source = args.resume_from_campaign.expanduser().resolve()
        if not resume_source.is_dir():
            raise SystemExit(
                f"--resume-from-campaign is not a directory: {resume_source}"
            )
        run_root.mkdir(parents=True, exist_ok=False)
        shutil.copytree(resume_source, campaign_dir)
        resume_from_campaign = str(resume_source)
    warehouse_data_root = args.warehouse_data_root.expanduser().resolve()
    config_paths = _rewrite_warehouse_configs(
        repo_root=repo_root,
        config_dir=config_dir,
        warehouse_data_root=warehouse_data_root,
        problem=args.problem,
        problem_v1=args.problem_v1,
        protocol=args.protocol,
        split=args.split,
        seeds=args.seeds,
    )
    api_key, api_key_env = _resolve_api_key(args)
    control_pair_key = _prepared_control_pair_key(
        args.control_pair_key,
        label=label,
    )

    env: dict[str, object] = {
        "RUN_ROOT": run_root,
        "CAMPAIGN_DIR": campaign_dir,
        "RESUME_FROM_CAMPAIGN": resume_from_campaign,
        "PREPARED_RUN_MANIFEST": run_root / "prepared_run_manifest.v1.json",
        "CONFIG_DIR": config_dir,
        "REPO_ROOT": repo_root,
        "SCION_DIR": scion_dir,
        "PY": args.python,
        "PYTHONPATH": scion_dir,
        "SCION_MODEL": args.model,
        "SCION_BASE_URL": args.base_url,
        "SCION_API_KEY": api_key,
        "SCION_API_KEY_ENV": api_key_env,
        "SCION_SDK_MAX_RETRIES": 0,
        "SCION_LLM_MAX_RETRIES": 2,
        "SCION_WAREHOUSE_DATA_ROOT": warehouse_data_root,
        "SCION_PROBLEM_DATA_ROOT": warehouse_data_root,
        "COMPLETION_PREFLIGHT": 1 if args.completion_preflight else 0,
        "POSTRUN_REPORTS": 0 if args.skip_postrun_reports else 1,
        "PROBLEM": config_paths["problem"],
        "PROBLEM_V1": config_paths["problem_v1"],
        "PROTOCOL": config_paths["protocol"],
        "SPLIT": config_paths["split"],
        "SEEDS": config_paths["seeds"],
        "ROUNDS": args.rounds,
        "TIME_LIMIT_SEC": args.time_limit_sec,
        "MEASUREMENT_GOVERNANCE": args.measurement_governance,
        "PROPOSAL_CONTEXT_ABLATION": args.proposal_context_ablation,
        "CONTROL_PAIR_KEY": control_pair_key,
        "AGENTIC_PROPOSAL": 1,
        "DISABLE_EARLY_STOP": 1,
        "AGENTIC_SESSION_TIMEOUT_SEC": args.agentic_session_timeout_sec,
        "GIT_COMMIT": _git_commit(repo_root),
        "GIT_RUNTIME_GUARD_PATHS": (
            "scion/scion :(exclude)scion/scion/tests "
            "scion/tools scion/problems/warehouse_delivery surrogate"
        ),
        "STARTED_UTC": started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    command = _build_command(env)
    _write_launch_env(run_root, env)
    _write_run_sh(run_root, command)
    api_key_display = (
        f"<from-env:{env['SCION_API_KEY_ENV']}>"
        if str(env["SCION_API_KEY_ENV"])
        else "<set>"
        if str(env["SCION_API_KEY"])
        else "<unset>"
    )
    (run_root / "command.txt").write_text(
        (
            "environment:\n"
            f"SCION_MODEL={env['SCION_MODEL']}\n"
            f"SCION_BASE_URL={env['SCION_BASE_URL']}\n"
            f"SCION_WAREHOUSE_DATA_ROOT={env['SCION_WAREHOUSE_DATA_ROOT']}\n\n"
            f"COMPLETION_PREFLIGHT={env['COMPLETION_PREFLIGHT']}\n\n"
            f"GIT_RUNTIME_GUARD_PATHS={env['GIT_RUNTIME_GUARD_PATHS']}\n\n"
            "SCION_API_KEY="
            f"{api_key_display}\n\n"
            "report_metadata:\n"
            f"CONTROL_PAIR_KEY={env['CONTROL_PAIR_KEY']}\n"
            f"POSTRUN_REPORTS={env['POSTRUN_REPORTS']}\n"
            f"POSTRUN_REPORT_DIR={env['RUN_ROOT'] / 'postrun_acceptance'}\n\n"
            f"PREPARED_RUN_MANIFEST={env['RUN_ROOT'] / 'prepared_run_manifest.v1.json'}\n\n"
            f"PREPARED_HANDOFF_DIR={env['RUN_ROOT'] / 'prepared_handoff'}\n\n"
            "config:\n"
            f"PROBLEM={env['PROBLEM']}\n"
            f"PROBLEM_V1={env['PROBLEM_V1']}\n"
            f"PROTOCOL={env['PROTOCOL']}\n"
            f"SPLIT={env['SPLIT']}\n"
            f"SEEDS={env['SEEDS']}\n\n"
            f"RESUME_FROM_CAMPAIGN={env['RESUME_FROM_CAMPAIGN']}\n\n"
            "command:\n"
            f"{command}\n\n"
            "launch:\n"
            "nohup setsid bash run.sh > nohup.log 2>&1 &\n"
        ),
        encoding="utf-8",
    )
    _write_prepared_run_manifest(run_root, env, command=command)
    _write_prepare_status(run_root, env)
    _write_prepared_handoff(run_root, env)

    pid = _launch(run_root) if args.launch else None
    return run_root, pid


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare a warehouse agentic Scion campaign run root. "
            "By default this only writes launch files and does not start Scion."
        )
    )
    parser.add_argument("--rounds", type=int, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--problem", default=PROBLEM)
    parser.add_argument("--problem-v1", default=PROBLEM_V1)
    parser.add_argument("--protocol", default=PROTOCOL)
    parser.add_argument("--split", default=SPLIT)
    parser.add_argument("--seeds", default=SEEDS)
    parser.add_argument(
        "--measurement-governance",
        choices=MEASUREMENT_GOVERNANCE_CHOICES,
        default="on",
    )
    parser.add_argument(
        "--proposal-context-ablation",
        choices=PROPOSAL_CONTEXT_ABLATION_CHOICES,
        default="full",
    )
    parser.add_argument(
        "--control-pair-key",
        default=None,
        help=(
            "Report-only metadata for matched-control launches. Written to "
            "launch.env and command.txt; not passed to scion run."
        ),
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--api-key",
        default=None,
        help=(
            "API key for the configured OpenAI-compatible proxy. "
            "Defaults to the local gpt-5.5 proxy key for 127.0.0.1:8080; "
            "use an explicit value for other proxies."
        ),
    )
    parser.add_argument(
        "--api-key-env",
        default=None,
        help=(
            "Read the API key from this environment variable when run.sh starts. "
            "Use this for non-local or shared runners so secrets are not written "
            "to launch.env or command.txt."
        ),
    )
    parser.add_argument(
        "--completion-preflight",
        action="store_true",
        help=(
            "Before starting Scion, require a real chat completion with "
            "SCION_MODEL/SCION_BASE_URL/SCION_API_KEY. This catches broken "
            "proxy sessions that still pass /v1/models."
        ),
    )
    parser.add_argument(
        "--skip-postrun-reports",
        action="store_true",
        help=(
            "Do not generate postrun acceptance report artifacts after Scion "
            "exits. The default is to write summary, failures, "
            "research-efficiency, proposal-trajectory manifest, and artifact "
            "inventory reports."
        ),
    )
    parser.add_argument(
        "--python",
        type=Path,
        default=DEFAULT_PYTHON,
        help="Python executable to write into launch.env and run.sh.",
    )
    parser.add_argument(
        "--warehouse-data-root",
        type=Path,
        default=Path.home() / "research" / "scion-data",
        help=(
            "Warehouse production data root for generated/converted cases. "
            "The launcher rewrites copied production split paths to this root."
        ),
    )
    parser.add_argument(
        "--resume-from-campaign",
        type=Path,
        default=None,
        help=(
            "Copy an existing campaign directory into the new run root before "
            "launch. Use this to continue from a promoted champion such as "
            "warehouse champion v2 instead of starting from the baseline."
        ),
    )
    parser.add_argument(
        "--time-limit-sec",
        type=int,
        default=DEFAULT_TIME_LIMIT_SEC,
    )
    parser.add_argument(
        "--agentic-session-timeout-sec",
        type=int,
        default=DEFAULT_AGENTIC_SESSION_TIMEOUT_SEC,
    )
    parser.add_argument(
        "--experiments-root",
        type=Path,
        default=DEFAULT_EXPERIMENTS_ROOT,
    )
    parser.add_argument(
        "--launch",
        action="store_true",
        help="Start run.sh with nohup setsid and write pid. Default is prepare only.",
    )
    args = parser.parse_args()
    if args.rounds < 1:
        raise SystemExit("--rounds must be >= 1")
    if args.time_limit_sec < 1:
        raise SystemExit("--time-limit-sec must be >= 1")
    if args.agentic_session_timeout_sec < 1:
        raise SystemExit("--agentic-session-timeout-sec must be >= 1")
    if args.api_key is not None and args.api_key_env:
        raise SystemExit("--api-key and --api-key-env are mutually exclusive")
    if args.api_key_env:
        _validate_env_var_name(args.api_key_env)
    if not str(args.python).strip():
        raise SystemExit("--python must not be empty")
    if not args.base_url.strip():
        raise SystemExit("--base-url must not be empty")
    for option_name in ("problem", "problem_v1", "protocol", "split", "seeds"):
        if not str(getattr(args, option_name)).strip():
            raise SystemExit(f"--{option_name.replace('_', '-')} must not be empty")
    return args


def main() -> None:
    run_root, pid = prepare(parse_args())
    print(f"RUN_ROOT={run_root}")
    if pid is None:
        print("PREPARED_ONLY=1")
    else:
        print(f"PID={pid}")


if __name__ == "__main__":
    main()
