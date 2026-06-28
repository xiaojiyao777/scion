"""Generic launcher lifecycle model and deterministic ``run.sh`` renderer."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
import shlex
from pathlib import Path
from typing import Mapping


SHELL_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
REPORT_STEM_PREFIX_RE = re.compile(r"^[A-Za-z0-9_]+$")
WRAPPER_SCHEMA = "outer-wrapper.v1"

JsonScalar = bool | int | float | str | None


@dataclass(frozen=True)
class CampaignCommandPlan:
    """Problem-owned campaign command payload wrapped by the launcher lifecycle."""

    command_log: str
    command_body: str
    exported_env_names: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.command_log.strip():
            raise ValueError("command_log must not be empty")
        if not self.command_body.strip():
            raise ValueError("command_body must not be empty")
        for name in self.exported_env_names:
            _validate_shell_name(name)


@dataclass(frozen=True)
class PreCampaignGuard:
    """Problem-owned shell guard executed before campaign start."""

    failure_key: str
    condition: str
    detail: str
    status_fields: Mapping[str, JsonScalar] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.failure_key.strip():
            raise ValueError("failure_key must not be empty")
        if not self.condition.strip():
            raise ValueError("condition must not be empty")
        if not self.detail.strip():
            raise ValueError("detail must not be empty")


@dataclass(frozen=True)
class LauncherLifecyclePlan:
    """Typed outer-wrapper contract for a prepared launcher run."""

    run_root: Path
    campaign_dir: Path
    repo_root: Path
    scion_dir: Path
    python: Path
    git_commit: str
    model: str
    scion_base_url: str
    api_key_env_binding: str
    postrun_report_stem_prefix: str
    command: CampaignCommandPlan
    fallback_assignments: tuple[tuple[str, object], ...]
    exported_env_names: tuple[str, ...]
    pre_campaign_guards: tuple[PreCampaignGuard, ...] = ()
    preflight_failure_exit_code: int = 64

    def __post_init__(self) -> None:
        if not REPORT_STEM_PREFIX_RE.fullmatch(self.postrun_report_stem_prefix):
            raise ValueError(
                "postrun_report_stem_prefix must contain only letters, digits, "
                "or underscores"
            )
        for name, _value in self.fallback_assignments:
            _validate_shell_name(name)
        for name in self.exported_env_names:
            _validate_shell_name(name)


def render_run_sh(plan: LauncherLifecyclePlan) -> str:
    """Render the generic outer lifecycle script for a problem command."""

    fallback_assignments = "\n".join(
        _shell_assign(name, value) for name, value in plan.fallback_assignments
    )
    exported_env_names = " ".join(
        _dedupe(plan.exported_env_names + plan.command.exported_env_names)
    )
    pre_campaign_guards = "\n".join(
        _render_pre_campaign_guard(guard, plan.preflight_failure_exit_code)
        for guard in plan.pre_campaign_guards
    )
    command_body = plan.command.command_body.rstrip()
    return f"""#!/usr/bin/env bash
set -uo pipefail
_INHERITED_SCION_API_KEY="${{SCION_API_KEY:-}}"
_RUN_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PREFLIGHT_FAILURE_EXIT_CODE={plan.preflight_failure_exit_code}
{fallback_assignments}
{_render_postrun_report_function(plan.postrun_report_stem_prefix)}
if [[ ! -r "$_RUN_SCRIPT_DIR/launch.env" ]]; then
  {{
    echo "WRAPPER_EXIT_STATUS:{plan.preflight_failure_exit_code}"
    echo "ENDED_AT:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "LAUNCH_ENV_MISSING:$_RUN_SCRIPT_DIR/launch.env"
  }} > "$RUN_ROOT/exit.txt"
  printf '{{"schema":"outer-wrapper.v1","status":"finished","wrapper_exit_status":{plan.preflight_failure_exit_code},"launch_env_missing":"%s"}}\\n' "$_RUN_SCRIPT_DIR/launch.env" > "$RUN_ROOT/run_status.json"
  write_postrun_acceptance_reports
  exit {plan.preflight_failure_exit_code}
fi
source "$(dirname "$0")/launch.env"
export {exported_env_names}
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
if [[ -n "${{SCION_API_KEY_ENV:-}}" ]]; then
  if [[ "$SCION_API_KEY_ENV" == "SCION_API_KEY" ]]; then
    _RESOLVED_SCION_API_KEY="$_INHERITED_SCION_API_KEY"
  else
    _RESOLVED_SCION_API_KEY="${{!SCION_API_KEY_ENV:-}}"
  fi
  if [[ -z "$_RESOLVED_SCION_API_KEY" ]]; then
    {{
      echo "WRAPPER_EXIT_STATUS:{plan.preflight_failure_exit_code}"
      echo "ENDED_AT:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      echo "SCION_API_KEY_ENV_MISSING:$SCION_API_KEY_ENV"
    }} > "$RUN_ROOT/exit.txt"
    printf '{{"schema":"outer-wrapper.v1","status":"finished","wrapper_exit_status":{plan.preflight_failure_exit_code},"api_key_env_missing":"%s"}}\\n' "$SCION_API_KEY_ENV" > "$RUN_ROOT/run_status.json"
    write_postrun_acceptance_reports
    exit {plan.preflight_failure_exit_code}
  fi
  SCION_API_KEY="$_RESOLVED_SCION_API_KEY"
fi
unset _INHERITED_SCION_API_KEY _RESOLVED_SCION_API_KEY
if ! cd "$SCION_DIR"; then
  {{
    echo "WRAPPER_EXIT_STATUS:{plan.preflight_failure_exit_code}"
    echo "ENDED_AT:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "SCION_DIR_MISSING:$SCION_DIR"
  }} > "$RUN_ROOT/exit.txt"
  printf '{{"schema":"outer-wrapper.v1","status":"finished","wrapper_exit_status":{plan.preflight_failure_exit_code},"scion_dir_missing":"%s"}}\\n' "$SCION_DIR" > "$RUN_ROOT/run_status.json"
  write_postrun_acceptance_reports
  exit {plan.preflight_failure_exit_code}
fi
read -r -a _GIT_RUNTIME_GUARD_PATHS <<< "$GIT_RUNTIME_GUARD_PATHS"
if [[ -n "$(git -C "$REPO_ROOT" status --porcelain -- "${{_GIT_RUNTIME_GUARD_PATHS[@]}}")" ]]; then
  {{
    echo "WRAPPER_EXIT_STATUS:{plan.preflight_failure_exit_code}"
    echo "ENDED_AT:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "GIT_RUNTIME_DIRTY:$GIT_RUNTIME_GUARD_PATHS"
  }} > "$RUN_ROOT/exit.txt"
  printf '{{"schema":"outer-wrapper.v1","status":"finished","wrapper_exit_status":{plan.preflight_failure_exit_code},"git_runtime_dirty":true}}\\n' > "$RUN_ROOT/run_status.json"
  write_postrun_acceptance_reports
  exit {plan.preflight_failure_exit_code}
fi
_ACTUAL_GIT_COMMIT="$(git -C "$REPO_ROOT" rev-parse --short HEAD)"
if [[ "$_ACTUAL_GIT_COMMIT" != "$GIT_COMMIT" ]]; then
  if git -C "$REPO_ROOT" diff --quiet "$GIT_COMMIT" HEAD -- "${{_GIT_RUNTIME_GUARD_PATHS[@]}}"; then
    echo "GIT_COMMIT_DOC_ONLY_MISMATCH_ALLOWED:expected=$GIT_COMMIT actual=$_ACTUAL_GIT_COMMIT paths=$GIT_RUNTIME_GUARD_PATHS" >> "$RUN_ROOT/run.log"
  else
    {{
      echo "WRAPPER_EXIT_STATUS:{plan.preflight_failure_exit_code}"
      echo "ENDED_AT:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      echo "GIT_COMMIT_MISMATCH:expected=$GIT_COMMIT actual=$_ACTUAL_GIT_COMMIT paths=$GIT_RUNTIME_GUARD_PATHS"
    }} > "$RUN_ROOT/exit.txt"
    printf '{{"schema":"outer-wrapper.v1","status":"finished","wrapper_exit_status":{plan.preflight_failure_exit_code},"git_runtime_commit_mismatch":true}}\\n' > "$RUN_ROOT/run_status.json"
    write_postrun_acceptance_reports
    exit {plan.preflight_failure_exit_code}
  fi
fi
unset _ACTUAL_GIT_COMMIT _GIT_RUNTIME_GUARD_PATHS
{{
  echo "STARTED_AT:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "GIT_COMMIT:$GIT_COMMIT"
  echo "CWD:$PWD"
  echo "COMMAND:{plan.command.command_log}"
}} >> "$RUN_ROOT/run.log"
{pre_campaign_guards}
{_LAUNCHER_RUNNING_STATUS_SNIPPET}
{_COMPLETION_PREFLIGHT_SNIPPET}
CAMPAIGN_EXECUTION_MARKER_STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '{{"schema":"scion.launcher_campaign_execution_marker.v1","started_at":"%s","run_root":"%s","campaign_dir":"%s"}}\\n' \\
  "$CAMPAIGN_EXECUTION_MARKER_STARTED_AT" "$RUN_ROOT" "$CAMPAIGN_DIR" \\
  > "$RUN_ROOT/campaign_execution_marker.v1.json"
echo "CAMPAIGN_EXECUTION_MARKER:$RUN_ROOT/campaign_execution_marker.v1.json" >> "$RUN_ROOT/run.log"
{command_body}
STATUS=$?
CAMPAIGN_STATUS=$STATUS
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
POSTRUN_ACCEPTANCE_STATUS=0
write_postrun_acceptance_reports || POSTRUN_ACCEPTANCE_STATUS=$?
if [[ "${{POSTRUN_REPORTS:-1}}" == "1" ]]; then
  if [[ "$POSTRUN_ACCEPTANCE_STATUS" -ne 0 ]]; then
    {{
      echo "POSTRUN_ACCEPTANCE_FAILED:$POSTRUN_ACCEPTANCE_STATUS"
      echo "POSTRUN_REPORTS_EFFECTIVE_EXIT_STATUS:$POSTRUN_STATUS"
      echo "POSTRUN_READINESS_EFFECTIVE_EXIT_STATUS:$POSTRUN_READINESS_STATUS"
    }} >> "$RUN_ROOT/exit.txt"
    if [[ "$STATUS" -eq 0 ]]; then
      STATUS="$POSTRUN_ACCEPTANCE_STATUS"
      echo "WRAPPER_EXIT_STATUS_EFFECTIVE:$STATUS" >> "$RUN_ROOT/exit.txt"
    fi
  fi
  POSTRUN_STATUS_WRITE_STATUS=0
  "$PY" "$SCION_DIR/tools/write_postrun_wrapper_status.py" \\
    --output "$RUN_ROOT/run_status.json" \\
    --wrapper-exit-code "$STATUS" \\
    --campaign-exit-code "$CAMPAIGN_STATUS" \\
    --postrun-reports-exit-code "$POSTRUN_STATUS" \\
    --postrun-readiness-exit-code "$POSTRUN_READINESS_STATUS" \\
    --postrun-report-dir "$REPORT_DIR" \\
    --postrun-readiness-path "$REPORT_DIR/readiness/$REPORT_STEM.postrun_acceptance_readiness.v1.json" \\
    --resume-from-campaign "$RESUME_FROM_CAMPAIGN" \\
    --resume-snapshot-ref "$RESUME_SNAPSHOT_MANIFEST_REF" \\
    --copied-campaign-status-present "$RESUME_COPIED_CAMPAIGN_STATUS_PRESENT" \\
    --copied-campaign-summary-present "$RESUME_COPIED_CAMPAIGN_SUMMARY_PRESENT" \\
    >> "$RUN_ROOT/run.log" 2>&1 || POSTRUN_STATUS_WRITE_STATUS=$?
  if [[ "$POSTRUN_STATUS_WRITE_STATUS" -ne 0 ]]; then
    echo "POSTRUN_STATUS_WRITE_EXIT_STATUS:$POSTRUN_STATUS_WRITE_STATUS" >> "$RUN_ROOT/run.log"
    if [[ "$STATUS" -eq 0 ]]; then
      STATUS="$POSTRUN_STATUS_WRITE_STATUS"
      echo "WRAPPER_EXIT_STATUS_EFFECTIVE:$STATUS" >> "$RUN_ROOT/exit.txt"
    fi
  fi
fi
exit "$STATUS"
"""


def _render_postrun_report_function(report_stem_prefix: str) -> str:
    return f'''write_postrun_acceptance_reports() {{
  if [[ "${{POSTRUN_REPORTS:-1}}" != "1" ]]; then
    return 0
  fi
  REPORT_DIR="$RUN_ROOT/postrun_acceptance"
  REPORT_STEM="{report_stem_prefix}_${{MEASUREMENT_GOVERNANCE//-/_}}_${{PROPOSAL_CONTEXT_ABLATION//-/_}}"
  OBSERVED_CONTROL_ARM="${{MEASUREMENT_GOVERNANCE//-/_}}"
  echo "POSTRUN_ACCEPTANCE_DIR:$REPORT_DIR" >> "$RUN_ROOT/exit.txt"
  {{
    echo "POSTRUN_REPORTS_STARTED_AT:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "POSTRUN_REPORT_DIR:$REPORT_DIR"
  }} >> "$RUN_ROOT/run.log"
  rebuild_args=(
    "$RUN_ROOT"
    --report-stem "$REPORT_STEM"
    --observed-control-arm "$OBSERVED_CONTROL_ARM"
  )
  if [[ -n "${{CONTROL_PAIR_KEY:-}}" ]]; then
    rebuild_args+=(--control-pair-key "$CONTROL_PAIR_KEY")
  fi
  POSTRUN_STATUS=0
  "$PY" "$SCION_DIR/tools/rebuild_postrun_acceptance.py" \\
    "${{rebuild_args[@]}}" \\
    --strict >> "$RUN_ROOT/run.log" 2>&1 || POSTRUN_STATUS=$?
  echo "POSTRUN_REPORTS_EXIT_STATUS:$POSTRUN_STATUS" >> "$RUN_ROOT/run.log"
  mkdir -p "$REPORT_DIR/readiness"
  POSTRUN_READINESS_STATUS=0
  "$PY" "$SCION_DIR/tools/check_postrun_acceptance.py" "$RUN_ROOT" \\
    --require-current-run-ready \\
    --format json \\
    > "$REPORT_DIR/readiness/$REPORT_STEM.postrun_acceptance_readiness.v1.json" \\
    2>> "$RUN_ROOT/run.log" || POSTRUN_READINESS_STATUS=$?
  "$PY" "$SCION_DIR/tools/check_postrun_acceptance.py" "$RUN_ROOT" \\
    --format markdown \\
    > "$REPORT_DIR/readiness/$REPORT_STEM.postrun_acceptance_readiness.md" \\
    2>> "$RUN_ROOT/run.log" || true
  {{
    echo "POSTRUN_READINESS_EXIT_STATUS:$POSTRUN_READINESS_STATUS"
    echo "POSTRUN_REPORTS_FINISHED_AT:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  }} >> "$RUN_ROOT/run.log"
  if [[ "$POSTRUN_STATUS" -ne 0 ]]; then
    return "$POSTRUN_STATUS"
  fi
  if [[ "$POSTRUN_READINESS_STATUS" -ne 0 ]]; then
    return "$POSTRUN_READINESS_STATUS"
  fi
  return 0
}}'''


def _render_pre_campaign_guard(guard: PreCampaignGuard, exit_code: int) -> str:
    payload = {
        "schema": WRAPPER_SCHEMA,
        "status": "finished",
        "wrapper_exit_status": exit_code,
        **guard.status_fields,
    }
    status_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    return f'''if {guard.condition}; then
  {{
    echo "WRAPPER_EXIT_STATUS:{exit_code}"
    echo "ENDED_AT:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "{guard.failure_key}:{guard.detail}"
  }} > "$RUN_ROOT/exit.txt"
  printf '%s\\n' {shlex.quote(status_json)} > "$RUN_ROOT/run_status.json"
  write_postrun_acceptance_reports
  exit {exit_code}
fi'''


def _shell_assign(name: str, value: object) -> str:
    _validate_shell_name(name)
    return f"{name}={shlex.quote(str(value))}"


def _validate_shell_name(name: str) -> None:
    if not SHELL_NAME_RE.fullmatch(name):
        raise ValueError(f"invalid shell name: {name!r}")


def _dedupe(names: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    deduped: list[str] = []
    for name in names:
        if name not in seen:
            deduped.append(name)
            seen.add(name)
    return tuple(deduped)


_COMPLETION_PREFLIGHT_SNIPPET = r'''
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
      --detail "$PREFLIGHT_DETAIL" \
      --resume-from-campaign "$RESUME_FROM_CAMPAIGN" \
      --resume-snapshot-ref "$RESUME_SNAPSHOT_MANIFEST_REF" \
      --copied-campaign-status-present "$RESUME_COPIED_CAMPAIGN_STATUS_PRESENT" \
      --copied-campaign-summary-present "$RESUME_COPIED_CAMPAIGN_SUMMARY_PRESENT"
    write_postrun_acceptance_reports
    exit "$PREFLIGHT_STATUS"
  fi
fi
'''


_LAUNCHER_RUNNING_STATUS_SNIPPET = r'''
LAUNCHER_RUNNING_STARTED_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
LAUNCHER_RUNNING_STATUS_WRITE_STATUS=0
"$PY" "$SCION_DIR/tools/write_launcher_running_status.py" \
  --output "$RUN_ROOT/run_status.json" \
  --run-root "$RUN_ROOT" \
  --campaign-dir "$CAMPAIGN_DIR" \
  --git-commit "$GIT_COMMIT" \
  --model "$SCION_MODEL" \
  --started-utc "$LAUNCHER_RUNNING_STARTED_UTC" \
  --pid "$$" \
  --scion-base-url "$SCION_BASE_URL" \
  --completion-preflight "$COMPLETION_PREFLIGHT" \
  --postrun-reports "$POSTRUN_REPORTS" \
  --resume-from-campaign "$RESUME_FROM_CAMPAIGN" \
  --resume-snapshot-ref "$RESUME_SNAPSHOT_MANIFEST_REF" \
  --copied-campaign-status-present "$RESUME_COPIED_CAMPAIGN_STATUS_PRESENT" \
  --copied-campaign-summary-present "$RESUME_COPIED_CAMPAIGN_SUMMARY_PRESENT" \
  >> "$RUN_ROOT/run.log" 2>&1 || LAUNCHER_RUNNING_STATUS_WRITE_STATUS=$?
if [[ "$LAUNCHER_RUNNING_STATUS_WRITE_STATUS" -ne 0 ]]; then
  {
    echo "WRAPPER_EXIT_STATUS:$PREFLIGHT_FAILURE_EXIT_CODE"
    echo "ENDED_AT:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "LAUNCHER_RUNNING_STATUS_WRITE_FAILED:$LAUNCHER_RUNNING_STATUS_WRITE_STATUS"
  } > "$RUN_ROOT/exit.txt"
  printf '{"schema":"outer-wrapper.v1","status":"finished","wrapper_exit_status":%s,"launcher_running_status_write_failed":%s}\n' \
    "$PREFLIGHT_FAILURE_EXIT_CODE" "$LAUNCHER_RUNNING_STATUS_WRITE_STATUS" \
    > "$RUN_ROOT/run_status.json"
  write_postrun_acceptance_reports
  exit "$PREFLIGHT_FAILURE_EXIT_CODE"
fi
echo "LAUNCHER_RUNNING_STATUS:$RUN_ROOT/run_status.json" >> "$RUN_ROOT/run.log"
'''
