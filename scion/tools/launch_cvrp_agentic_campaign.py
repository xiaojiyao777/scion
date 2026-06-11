#!/usr/bin/env python3
"""Prepare or launch a CVRP agentic Scion campaign run directory."""

from __future__ import annotations

import argparse
import re
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml


DEFAULT_EXPERIMENTS_ROOT = Path("/home/clawd/research/scion-experiments")
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_BASE_URL = "http://127.0.0.1:8080"
DEFAULT_LOCAL_PROXY_API_KEY = "pwd"
DEFAULT_TIME_LIMIT_SEC = 30
DEFAULT_AGENTIC_SESSION_TIMEOUT_SEC = 900
DEFAULT_PYTHON = Path("/home/clawd/miniconda3/envs/claw/bin/python")
DEFAULT_USER_SUFFIX = "claw"

PROBLEM = "scion/problems/cvrp/problem.yaml"
PROTOCOL = "scion/problems/cvrp/formal/protocol.yaml"
SPLIT = "scion/problems/cvrp/formal/split_manifest.yaml"
SEEDS = "scion/problems/cvrp/formal/seed_ledger.yaml"
CVRP_SPECS_REQUIRING_PARAMETER_SEARCH_DISABLED = (
    PROBLEM,
    "scion/problems/cvrp/problem-v1.yaml",
)


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


def _preflight_cvrp_parameter_search_disabled(scion_dir: Path) -> None:
    for spec_path in CVRP_SPECS_REQUIRING_PARAMETER_SEARCH_DISABLED:
        full_path = scion_dir / spec_path
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
            raise SystemExit(
                "CVRP agentic launcher requires "
                f"parameter_search.enabled=false in {spec_path}"
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
        "--disable-early-stop "
        "--agentic-proposal"
    )


def _write_launch_env(run_root: Path, env: dict[str, object]) -> None:
    ordered_keys = [
        "RUN_ROOT",
        "CAMPAIGN_DIR",
        "REPO_ROOT",
        "SCION_DIR",
        "PY",
        "PYTHONPATH",
        "SCION_MODEL",
        "SCION_BASE_URL",
        "SCION_API_KEY",
        "SCION_SDK_MAX_RETRIES",
        "SCION_LLM_MAX_RETRIES",
        "SCION_PROBLEM_DATA_ROOT",
        "PROBLEM",
        "PROTOCOL",
        "SPLIT",
        "SEEDS",
        "ROUNDS",
        "TIME_LIMIT_SEC",
        "AGENTIC_PROPOSAL",
        "DISABLE_EARLY_STOP",
        "AGENTIC_SESSION_TIMEOUT_SEC",
        "GIT_COMMIT",
        "STARTED_UTC",
    ]
    content = "\n".join(_shell_assign(key, env[key]) for key in ordered_keys) + "\n"
    (run_root / "launch.env").write_text(content, encoding="utf-8")


def _write_run_sh(run_root: Path, command: str) -> None:
    content = f"""#!/usr/bin/env bash
set -uo pipefail
source "$(dirname "$0")/launch.env"
cd "$SCION_DIR" || exit 1
export PYTHONPATH SCION_MODEL SCION_BASE_URL SCION_API_KEY SCION_SDK_MAX_RETRIES SCION_LLM_MAX_RETRIES SCION_PROBLEM_DATA_ROOT
{{
  echo "STARTED_AT:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "GIT_COMMIT:$GIT_COMMIT"
  echo "CWD:$PWD"
  echo "COMMAND:{command}"
}} >> "$RUN_ROOT/run.log"
"$PY" -m scion.cli.main run \\
  --problem "$PROBLEM" \\
  --protocol "$PROTOCOL" \\
  --split "$SPLIT" \\
  --seeds "$SEEDS" \\
  --campaign-dir "$CAMPAIGN_DIR" \\
  --rounds "$ROUNDS" \\
  --time-limit-sec "$TIME_LIMIT_SEC" \\
  --agentic-session-timeout-sec "$AGENTIC_SESSION_TIMEOUT_SEC" \\
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


def prepare(args: argparse.Namespace) -> tuple[Path, str | None]:
    repo_root = _repo_root()
    scion_dir = repo_root / "scion"
    _preflight_cvrp_parameter_search_disabled(scion_dir)
    started_at = datetime.now(timezone.utc)
    timestamp = started_at.strftime("%Y%m%dT%H%M%SZ")
    label = _safe_label(args.label)
    run_name = (
        f"{label}-{args.rounds}r-{_model_slug(args.model)}-"
        f"{timestamp}-{DEFAULT_USER_SUFFIX}"
    )
    run_root = args.experiments_root.expanduser().resolve() / run_name
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True, exist_ok=False)

    env: dict[str, object] = {
        "RUN_ROOT": run_root,
        "CAMPAIGN_DIR": campaign_dir,
        "REPO_ROOT": repo_root,
        "SCION_DIR": scion_dir,
        "PY": DEFAULT_PYTHON,
        "PYTHONPATH": scion_dir,
        "SCION_MODEL": args.model,
        "SCION_BASE_URL": args.base_url,
        "SCION_API_KEY": (
            args.api_key
            if args.api_key is not None
            else _default_api_key_for_base_url(args.base_url)
        ),
        "SCION_SDK_MAX_RETRIES": 0,
        "SCION_LLM_MAX_RETRIES": 2,
        "SCION_PROBLEM_DATA_ROOT": repo_root / "vrp",
        "PROBLEM": PROBLEM,
        "PROTOCOL": PROTOCOL,
        "SPLIT": SPLIT,
        "SEEDS": SEEDS,
        "ROUNDS": args.rounds,
        "TIME_LIMIT_SEC": args.time_limit_sec,
        "AGENTIC_PROPOSAL": 1,
        "DISABLE_EARLY_STOP": 1,
        "AGENTIC_SESSION_TIMEOUT_SEC": args.agentic_session_timeout_sec,
        "GIT_COMMIT": _git_commit(repo_root),
        "STARTED_UTC": started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    command = _build_command(env)
    _write_launch_env(run_root, env)
    _write_run_sh(run_root, command)
    (run_root / "command.txt").write_text(
        (
            "environment:\n"
            f"SCION_MODEL={env['SCION_MODEL']}\n"
            f"SCION_BASE_URL={env['SCION_BASE_URL']}\n\n"
            "SCION_API_KEY="
            f"{'<set>' if str(env['SCION_API_KEY']) else '<unset>'}\n\n"
            "command:\n"
            f"{command}\n\n"
            "launch:\n"
            "nohup setsid bash run.sh > nohup.log 2>&1 &\n"
        ),
        encoding="utf-8",
    )

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
    if not args.base_url.strip():
        raise SystemExit("--base-url must not be empty")
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
