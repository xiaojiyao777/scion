#!/usr/bin/env python3
"""Prepare or launch a CVRP agentic Scion campaign run directory."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml


DEFAULT_EXPERIMENTS_ROOT = Path.home() / "research" / "scion-experiments"
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_BASE_URL = "http://127.0.0.1:8080"
DEFAULT_LOCAL_PROXY_API_KEY = "pwd"
DEFAULT_TIME_LIMIT_SEC = 30
DEFAULT_AGENTIC_SESSION_TIMEOUT_SEC = 900
DEFAULT_STAGE_TRANSITION_DRAIN_LIMIT = 4
DEFAULT_PYTHON = Path(sys.executable)
DEFAULT_USER_SUFFIX = "claw"
PREFLIGHT_FAILURE_EXIT_CODE = 64

PROBLEM = "scion/problems/cvrp/problem.yaml"
PROTOCOL = "scion/problems/cvrp/formal/protocol.yaml"
SPLIT = "scion/problems/cvrp/formal/split_manifest.yaml"
SEEDS = "scion/problems/cvrp/formal/seed_ledger.yaml"
CVRP_SPECS_REQUIRING_PARAMETER_SEARCH_DISABLED = (
    PROBLEM,
    "scion/problems/cvrp/problem-v1.yaml",
)
MEASUREMENT_GOVERNANCE_CHOICES = ("on", "record-only")
PROPOSAL_CONTEXT_ABLATION_CHOICES = (
    "full",
    "compact-measurement-diagnostics",
    "no-measurement-diagnostics",
    "minimal-research-context",
)
ENV_VAR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


COMPLETION_PREFLIGHT_SNIPPET = r'''
if [[ "${COMPLETION_PREFLIGHT:-0}" == "1" ]]; then
  "$PY" "$SCION_DIR/tools/check_gpt55_proxy.py" \
    --base-url "$SCION_BASE_URL" \
    --model "$SCION_MODEL" \
    --api-key "$SCION_API_KEY" \
    --timeout-sec 60 \
    --login-url-on-failure \
    >> "$RUN_ROOT/run.log" 2>&1
  PREFLIGHT_STATUS=$?
  if [[ "$PREFLIGHT_STATUS" -ne 0 ]]; then
    {
      echo "WRAPPER_EXIT_STATUS:$PREFLIGHT_STATUS"
      echo "ENDED_AT:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      echo "PRE_CAMPAIGN_COMPLETION_PREFLIGHT_FAILED:1"
    } > "$RUN_ROOT/exit.txt"
    printf '{"schema":"outer-wrapper.v1","status":"finished","wrapper_exit_status":%s,"pre_campaign_completion_preflight":"failed"}\n' "$PREFLIGHT_STATUS" > "$RUN_ROOT/run_status.json"
    exit "$PREFLIGHT_STATUS"
  fi
fi
'''


POSTRUN_REPORT_SNIPPET = r'''
if [[ "${POSTRUN_REPORTS:-1}" == "1" ]]; then
  REPORT_DIR="$RUN_ROOT/postrun_acceptance"
  REPORT_STEM="cvrp_${MEASUREMENT_GOVERNANCE//-/_}_${PROPOSAL_CONTEXT_ABLATION//-/_}"
  OBSERVED_CONTROL_ARM="${MEASUREMENT_GOVERNANCE//-/_}"
  mkdir -p \
    "$REPORT_DIR/summaries" \
    "$REPORT_DIR/failures" \
    "$REPORT_DIR/research_efficiency" \
    "$REPORT_DIR/manifests" \
    "$REPORT_DIR/analysis_brief" \
    "$REPORT_DIR/inventory"
  echo "POSTRUN_ACCEPTANCE_DIR:$REPORT_DIR" >> "$RUN_ROOT/exit.txt"
  {
    echo "POSTRUN_REPORTS_STARTED_AT:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "POSTRUN_REPORT_DIR:$REPORT_DIR"
  } >> "$RUN_ROOT/run.log"
  "$PY" -m scion.cli.main report summary \
    --campaign-dir "$CAMPAIGN_DIR" \
    --output "$REPORT_DIR/summaries/${REPORT_STEM}.summary.json" \
    >> "$RUN_ROOT/run.log" 2>&1 || true
  "$PY" -m scion.cli.main report failures \
    --campaign-dir "$CAMPAIGN_DIR" \
    --output "$REPORT_DIR/failures/${REPORT_STEM}.failures.json" \
    >> "$RUN_ROOT/run.log" 2>&1 || true
  "$PY" -m scion.cli.main report research-efficiency \
    --campaign-dir "$CAMPAIGN_DIR" \
    --output "$REPORT_DIR/research_efficiency/${REPORT_STEM}.research_efficiency.v1.json" \
    >> "$RUN_ROOT/run.log" 2>&1 || true
  manifest_args=(
    --campaign-dir "$CAMPAIGN_DIR"
    --observed-control-arm "$OBSERVED_CONTROL_ARM"
    --output "$REPORT_DIR/manifests/${REPORT_STEM}.proposal_trajectory_manifest.v1.json"
  )
  if [[ -n "${CONTROL_PAIR_KEY:-}" ]]; then
    manifest_args+=(--control-pair-key "$CONTROL_PAIR_KEY")
  fi
  "$PY" -m scion.cli.main report proposal-trajectory-manifest \
    "${manifest_args[@]}" >> "$RUN_ROOT/run.log" 2>&1 || true
  "$PY" "$SCION_DIR/tools/postrun_analysis_brief.py" \
    "$RUN_ROOT" \
    --format json \
    > "$REPORT_DIR/analysis_brief/${REPORT_STEM}.postrun_analysis_brief.v1.json" \
    2>> "$RUN_ROOT/run.log" || true
  "$PY" "$SCION_DIR/tools/postrun_analysis_brief.py" \
    "$RUN_ROOT" \
    --format markdown \
    > "$REPORT_DIR/analysis_brief/${REPORT_STEM}.postrun_analysis_brief.md" \
    2>> "$RUN_ROOT/run.log" || true
  "$PY" "$SCION_DIR/tools/postrun_artifact_inventory.py" \
    "$RUN_ROOT" \
    --format json \
    > "$REPORT_DIR/inventory/${REPORT_STEM}.postrun_artifact_inventory.v1.json" \
    2>> "$RUN_ROOT/run.log" || true
  "$PY" "$SCION_DIR/tools/postrun_artifact_inventory.py" \
    "$RUN_ROOT" \
    --format markdown \
    > "$REPORT_DIR/inventory/${REPORT_STEM}.postrun_artifact_inventory.md" \
    2>> "$RUN_ROOT/run.log" || true
  {
    echo "POSTRUN_REPORTS_FINISHED_AT:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } >> "$RUN_ROOT/run.log"
fi
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


def _resolve_spec_path(scion_dir: Path, spec_path: str) -> Path:
    path = Path(spec_path).expanduser()
    if path.is_absolute():
        return path
    return scion_dir / path


def _preflight_cvrp_parameter_search_disabled(scion_dir: Path, problem: str) -> None:
    problem_path = _resolve_spec_path(scion_dir, problem)
    spec_paths = [problem_path]
    problem_v1_path = problem_path.with_name("problem-v1.yaml")
    if problem_v1_path.exists():
        spec_paths.append(problem_v1_path)

    for full_path in spec_paths:
        with full_path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        parameter_search = (
            data.get("parameter_search") if isinstance(data, dict) else None
        )
        enabled = (
            parameter_search.get("enabled")
            if isinstance(parameter_search, dict)
            else None
        )
        if enabled is not False:
            display_path = (
                str(full_path.relative_to(scion_dir))
                if full_path.is_relative_to(scion_dir)
                else str(full_path)
            )
            raise SystemExit(
                "CVRP agentic launcher requires "
                f"parameter_search.enabled=false in {display_path}"
            )


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
        "SCION_STAGE_TRANSITION_DRAIN_LIMIT",
        "SCION_PROBLEM_DATA_ROOT",
        "COMPLETION_PREFLIGHT",
        "POSTRUN_REPORTS",
        "PROBLEM",
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
    printf '{{"schema":"outer-wrapper.v1","status":"finished","wrapper_exit_status":{PREFLIGHT_FAILURE_EXIT_CODE},"api_key_env_missing":"%s"}}\n' "$SCION_API_KEY_ENV" > "$RUN_ROOT/run_status.json"
    exit {PREFLIGHT_FAILURE_EXIT_CODE}
  fi
  SCION_API_KEY="$_RESOLVED_SCION_API_KEY"
fi
unset _INHERITED_SCION_API_KEY _RESOLVED_SCION_API_KEY
cd "$SCION_DIR" || exit 1
export PYTHONPATH SCION_MODEL SCION_BASE_URL SCION_API_KEY SCION_SDK_MAX_RETRIES SCION_LLM_MAX_RETRIES SCION_STAGE_TRANSITION_DRAIN_LIMIT SCION_PROBLEM_DATA_ROOT
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
read -r -a _GIT_RUNTIME_GUARD_PATHS <<< "$GIT_RUNTIME_GUARD_PATHS"
if [[ -n "$(git -C "$REPO_ROOT" status --porcelain -- "${{_GIT_RUNTIME_GUARD_PATHS[@]}}")" ]]; then
  {{
    echo "WRAPPER_EXIT_STATUS:{PREFLIGHT_FAILURE_EXIT_CODE}"
    echo "ENDED_AT:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "GIT_RUNTIME_DIRTY:$GIT_RUNTIME_GUARD_PATHS"
  }} > "$RUN_ROOT/exit.txt"
  printf '{{"schema":"outer-wrapper.v1","status":"finished","wrapper_exit_status":{PREFLIGHT_FAILURE_EXIT_CODE},"git_runtime_dirty":true}}\n' > "$RUN_ROOT/run_status.json"
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
    printf '{{"schema":"outer-wrapper.v1","status":"finished","wrapper_exit_status":{PREFLIGHT_FAILURE_EXIT_CODE},"git_runtime_commit_mismatch":true}}\n' > "$RUN_ROOT/run_status.json"
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


def prepare(args: argparse.Namespace) -> tuple[Path, str | None]:
    repo_root = _repo_root()
    scion_dir = repo_root / "scion"
    _preflight_cvrp_parameter_search_disabled(scion_dir, args.problem)
    started_at = datetime.now(timezone.utc)
    timestamp = started_at.strftime("%Y%m%dT%H%M%SZ")
    label = _safe_label(args.label)
    run_name = (
        f"{label}-{args.rounds}r-{_model_slug(args.model)}-"
        f"{timestamp}-{DEFAULT_USER_SUFFIX}"
    )
    run_root = args.experiments_root.expanduser().resolve() / run_name
    campaign_dir = run_root / "campaign"
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
    api_key, api_key_env = _resolve_api_key(args)

    env: dict[str, object] = {
        "RUN_ROOT": run_root,
        "CAMPAIGN_DIR": campaign_dir,
        "RESUME_FROM_CAMPAIGN": resume_from_campaign,
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
        "SCION_STAGE_TRANSITION_DRAIN_LIMIT": args.stage_transition_drain_limit,
        "SCION_PROBLEM_DATA_ROOT": repo_root / "vrp",
        "COMPLETION_PREFLIGHT": 1 if args.completion_preflight else 0,
        "POSTRUN_REPORTS": 0 if args.skip_postrun_reports else 1,
        "PROBLEM": args.problem,
        "PROTOCOL": args.protocol,
        "SPLIT": args.split,
        "SEEDS": args.seeds,
        "ROUNDS": args.rounds,
        "TIME_LIMIT_SEC": args.time_limit_sec,
        "MEASUREMENT_GOVERNANCE": args.measurement_governance,
        "PROPOSAL_CONTEXT_ABLATION": args.proposal_context_ablation,
        "CONTROL_PAIR_KEY": args.control_pair_key or "",
        "AGENTIC_PROPOSAL": 1,
        "DISABLE_EARLY_STOP": 1,
        "AGENTIC_SESSION_TIMEOUT_SEC": args.agentic_session_timeout_sec,
        "GIT_COMMIT": _git_commit(repo_root),
        "GIT_RUNTIME_GUARD_PATHS": (
            "scion/scion :(exclude)scion/scion/tests scion/problems/cvrp vrp"
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
            f"SCION_BASE_URL={env['SCION_BASE_URL']}\n\n"
            f"SCION_STAGE_TRANSITION_DRAIN_LIMIT="
            f"{env['SCION_STAGE_TRANSITION_DRAIN_LIMIT']}\n\n"
            f"COMPLETION_PREFLIGHT={env['COMPLETION_PREFLIGHT']}\n\n"
            f"GIT_RUNTIME_GUARD_PATHS={env['GIT_RUNTIME_GUARD_PATHS']}\n\n"
            "SCION_API_KEY="
            f"{api_key_display}\n\n"
            "report_metadata:\n"
            f"CONTROL_PAIR_KEY={env['CONTROL_PAIR_KEY']}\n"
            f"POSTRUN_REPORTS={env['POSTRUN_REPORTS']}\n"
            f"POSTRUN_REPORT_DIR={env['RUN_ROOT'] / 'postrun_acceptance'}\n\n"
            f"RESUME_FROM_CAMPAIGN={env['RESUME_FROM_CAMPAIGN']}\n\n"
            "command:\n"
            f"{command}\n\n"
            "launch:\n"
            "nohup setsid bash run.sh > nohup.log 2>&1 &\n"
        ),
        encoding="utf-8",
    )

    if not args.launch:
        _write_prepare_status(run_root, env)
    pid = _launch(run_root) if args.launch else None
    return run_root, pid


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare a CVRP agentic Scion campaign run root. "
            "By default this only writes launch files and does not start Scion."
        )
    )
    parser.add_argument("--rounds", type=int, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--problem", default=PROBLEM)
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
        "--time-limit-sec",
        type=int,
        default=DEFAULT_TIME_LIMIT_SEC,
        help=(
            "Per solver run budget. Defaults to 30s for CVRP preliminary "
            "screening validation; pass 10 explicitly only for small smoke runs."
        ),
    )
    parser.add_argument(
        "--agentic-session-timeout-sec",
        type=int,
        default=DEFAULT_AGENTIC_SESSION_TIMEOUT_SEC,
    )
    parser.add_argument(
        "--stage-transition-drain-limit",
        type=int,
        default=DEFAULT_STAGE_TRANSITION_DRAIN_LIMIT,
        help=(
            "Bounded post-budget validation/frozen drain cap. Written as "
            "SCION_STAGE_TRANSITION_DRAIN_LIMIT; use 0 only to disable the "
            "post-budget drain."
        ),
    )
    parser.add_argument(
        "--resume-from-campaign",
        type=Path,
        default=None,
        help=(
            "Copy an existing campaign directory into the new run root before "
            "launch so a focused CVRP follow-up can continue from restored "
            "champion, branch, and evidence state."
        ),
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
    if args.stage_transition_drain_limit < 0:
        raise SystemExit("--stage-transition-drain-limit must be >= 0")
    if args.api_key is not None and args.api_key_env:
        raise SystemExit("--api-key and --api-key-env are mutually exclusive")
    if args.api_key_env:
        _validate_env_var_name(args.api_key_env)
    if not str(args.python).strip():
        raise SystemExit("--python must not be empty")
    if not args.base_url.strip():
        raise SystemExit("--base-url must not be empty")
    for option_name in ("problem", "protocol", "split", "seeds"):
        if not getattr(args, option_name).strip():
            raise SystemExit(f"--{option_name} must not be empty")
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
