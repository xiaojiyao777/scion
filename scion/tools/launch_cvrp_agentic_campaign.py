#!/usr/bin/env python3
"""Prepare or launch a CVRP agentic Scion campaign run directory."""

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
from typing import Any, Mapping

import yaml


DEFAULT_EXPERIMENTS_ROOT = Path.home() / "research" / "scion-experiments"
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_BASE_URL = "http://127.0.0.1:8080"
DEFAULT_LOCAL_PROXY_API_KEY = "pwd"
DEFAULT_TIME_LIMIT_SEC = 30
DEFAULT_AGENTIC_SESSION_TIMEOUT_SEC = 3600
DEFAULT_AGENTIC_TOOL_MAX_STEPS = 0
DEFAULT_AGENTIC_TOOL_MAX_CALLS = 0
DEFAULT_AGENTIC_CODE_TOOL_MAX_CALLS = DEFAULT_AGENTIC_TOOL_MAX_CALLS
DEFAULT_AGENTIC_OBSERVATION_MAX_CHARS = 0
DEFAULT_STAGE_TRANSITION_DRAIN_LIMIT = 4
DEFAULT_FRESH_RUNTIME_REPLAY_DRAIN_LIMIT = 0
DEFAULT_PROPOSAL_ATTEMPT_LIMIT = 0
DEFAULT_PROPOSAL_QUALITY_LOOP_LIMIT = 0
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
PREPARED_RUN_MANIFEST_SCHEMA = "scion.launcher_prepared_run_manifest.v1"
TASK_DOC = "scion/TASK.md"
CURRENT_STATE_DOC = "scion/docs/status/current-state.md"
ANALYSIS_HANDOFF_DOC = "scion/docs/operations/postrun-analysis-handoff.md"
CVRP_ANALYSIS_INTENT = (
    "CVRP post-pivot branch-continuation check. Inspect target-intent and "
    "hypothesis traces, branch lesson transfer, protocol effect-vs-MDE, "
    "budget-exhausting runtime feedback, source visibility, and whether the "
    "solver mechanism is materially different from rejected/default-avoid "
    "directions before accepting any conclusion."
)
CVRP_ADAPTER_OPPORTUNITY_FIELDS = (
    "screening_headroom",
    "measurable_opportunity_classes",
    "mechanism_effect_ranking",
    "opportunity_diagnostics",
)
CVRP_ADAPTER_FORBIDDEN_KEY_FRAGMENTS = (
    "pair_evidence",
    "pair_rows",
    "raw_pair",
    "raw_calibration",
    "calibration_pair",
    "bks",
    "validation_case",
    "frozen_case",
    "holdout",
    "prompt_ratio",
    "llm_text",
)
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
  REPORT_STEM="cvrp_${MEASUREMENT_GOVERNANCE//-/_}_${PROPOSAL_CONTEXT_ABLATION//-/_}"
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
  if [[ "$POSTRUN_STATUS" -ne 0 ]]; then
    return "$POSTRUN_STATUS"
  fi
  if [[ "$POSTRUN_READINESS_STATUS" -ne 0 ]]; then
    return "$POSTRUN_READINESS_STATUS"
  fi
  return 0
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
    key = f"cvrp.{label}:prepared"
    if len(key) <= 128:
        return key
    digest = hashlib.sha1(label.encode("utf-8")).hexdigest()[:8]
    suffix = f":prepared.{digest}"
    max_label_len = max(1, 128 - len("cvrp.") - len(suffix))
    trimmed = label[:max_label_len].rstrip("-._") or label[:max_label_len]
    return f"cvrp.{trimmed}{suffix}"


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


def _problem_v1_path_for_problem(scion_dir: Path, problem: str) -> Path:
    return _resolve_spec_path(scion_dir, problem).with_name("problem-v1.yaml")


def _cvrp_measurement_opportunity_diagnostics(
    scion_dir: Path,
    problem: str,
) -> dict[str, Any]:
    """Build proposal-visible CVRP measurement guidance from problem-owned refs."""

    if str(scion_dir) not in sys.path:
        sys.path.insert(0, str(scion_dir))

    from scion.measurement.readiness import measurement_readiness_status  # noqa: PLC0415
    from scion.problem.bridge import load_problem_spec_v1_from_yaml  # noqa: PLC0415

    problem_v1 = _problem_v1_path_for_problem(scion_dir, problem)
    if not problem_v1.is_file():
        raise SystemExit(
            "CVRP agentic launcher requires problem-v1 measurement declaration: "
            f"{problem_v1}"
        )

    spec = load_problem_spec_v1_from_yaml(problem_v1)
    measurement = spec.measurement
    readiness = measurement_readiness_status(spec)
    if readiness.status != "ready":
        raise SystemExit(
            "CVRP measurement calibration is not launch-ready: "
            f"{readiness.reason_code}"
        )

    calibration_ref = str(measurement.calibration_ref or "").strip()
    calibration_path = _resolve_calibration_ref(spec.root_dir, calibration_ref)
    calibration_artifact = _read_calibration_artifact(calibration_path)
    power = _mapping_or_empty(calibration_artifact.get("protocol_power"))
    effect_scale = measurement.effect_scale
    practical_screen_delta = float(effect_scale.practical_delta_screen)
    mde_at_power_80 = float(readiness.mde_at_power_80 or 0.0)
    reason_codes = _cvrp_measurement_reason_codes(
        runtime_model=measurement.runtime_model,
        pairing_validity=measurement.pairing_validity,
        practical_screen_delta=practical_screen_delta,
        mde_at_power_80=mde_at_power_80,
    )
    recommended_min_seeds = _positive_int_or_none(power.get("recommended_min_seeds"))

    diagnostic: dict[str, Any] = {
        "schema_version": "cvrp_measurement_opportunity_handoff.v1",
        "source": "problem_v1.measurement.calibration_ref",
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
        "metric": effect_scale.metric,
        "unit": effect_scale.unit,
        "runtime_model": measurement.runtime_model,
        "pairing_validity": measurement.pairing_validity,
        "practical_screen_delta": practical_screen_delta,
        "practical_validate_delta": float(effect_scale.practical_delta_validate),
        "screening_mde_at_power_80": mde_at_power_80,
        "measurement_readiness": readiness.to_status_payload(),
        "calibration": _calibration_handoff(
            calibration_artifact=calibration_artifact,
            calibration_ref=calibration_ref,
            calibration_path=calibration_path,
            n_pairs=readiness.n_pairs,
        ),
        "summary": _measurement_summary(
            metric=effect_scale.metric,
            mde_at_power_80=mde_at_power_80,
            practical_screen_delta=practical_screen_delta,
        ),
        "reason_codes": reason_codes,
    }
    diagnostic.update(_cvrp_adapter_opportunity_projection(spec))
    if recommended_min_seeds is not None:
        diagnostic["recommended_min_seeds"] = recommended_min_seeds
    return diagnostic


def _cvrp_adapter_opportunity_projection(spec: Any) -> dict[str, Any]:
    """Project problem-owned CVRP opportunity diagnostics into launch focus."""

    from scion.problem.loader import load_problem_adapter  # noqa: PLC0415

    adapter = load_problem_adapter(spec)
    hook = getattr(adapter, "render_problem_measurement_diagnostics", None)
    if not callable(hook):
        raise SystemExit(
            "CVRP agentic launcher requires adapter measurement opportunity "
            "diagnostics"
        )
    payload = hook()
    if not isinstance(payload, Mapping):
        raise SystemExit(
            "CVRP adapter measurement opportunity diagnostics must be a mapping"
        )
    redacted = _redact_cvrp_adapter_opportunity_payload(dict(payload))
    if not isinstance(redacted, Mapping):
        raise SystemExit("CVRP adapter measurement opportunity diagnostics invalid")
    projection: dict[str, Any] = {
        "opportunity_projection_source": (
            "problem_adapter.render_problem_measurement_diagnostics"
        ),
        "adapter_payload_schema": str(redacted.get("schema_version") or "").strip(),
    }
    for field in CVRP_ADAPTER_OPPORTUNITY_FIELDS:
        value = redacted.get(field)
        if value not in ("", None, [], {}, ()):
            projection[field] = value
    missing = [
        field
        for field in CVRP_ADAPTER_OPPORTUNITY_FIELDS
        if projection.get(field) in ("", None, [], {}, ())
    ]
    if missing:
        raise SystemExit(
            "CVRP adapter measurement opportunity diagnostics missing fields: "
            + ", ".join(missing)
        )
    return projection


def _redact_cvrp_adapter_opportunity_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        projected: dict[str, Any] = {}
        for key, child in value.items():
            key_text = str(key)
            if not _cvrp_adapter_key_allowed(key_text):
                continue
            redacted = _redact_cvrp_adapter_opportunity_payload(child)
            if redacted not in ("", None, [], {}, ()):
                projected[key_text] = redacted
        return projected
    if isinstance(value, (list, tuple)):
        projected_items = [
            _redact_cvrp_adapter_opportunity_payload(item) for item in value
        ]
        return [
            item
            for item in projected_items
            if item not in ("", None, [], {}, ())
        ]
    return value


def _cvrp_adapter_key_allowed(key: str) -> bool:
    lowered = key.lower()
    return not any(
        fragment in lowered for fragment in CVRP_ADAPTER_FORBIDDEN_KEY_FRAGMENTS
    )


def _resolve_calibration_ref(root_dir: str, calibration_ref: str) -> Path:
    ref = Path(calibration_ref).expanduser()
    if ref.is_absolute():
        return ref
    return Path(root_dir).expanduser().resolve() / ref


def _read_calibration_artifact(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"unable to read CVRP calibration artifact {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"CVRP calibration artifact must be a JSON object: {path}")
    return payload


def _calibration_handoff(
    *,
    calibration_artifact: Mapping[str, Any],
    calibration_ref: str,
    calibration_path: Path,
    n_pairs: int,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": calibration_artifact.get("schema"),
        "ref": calibration_ref,
        "path": str(calibration_path),
        "calibrated_at": calibration_artifact.get("calibrated_at"),
        "n_pairs": n_pairs,
        "decision_features_excluded": calibration_artifact.get(
            "decision_features_excluded"
        ),
    }
    source_artifact = _compact_source_artifact(
        calibration_artifact.get("source_artifact")
    )
    if source_artifact:
        payload["source_artifact"] = source_artifact
    calibration_run = _compact_calibration_run(
        calibration_artifact.get("calibration_run")
    )
    if calibration_run:
        payload["calibration_run"] = calibration_run
    return payload


def _compact_source_artifact(value: Any) -> dict[str, Any]:
    source = _mapping_or_empty(value)
    payload = {
        "ref": str(source.get("ref") or ""),
        "sha256": str(source.get("sha256") or ""),
    }
    return {
        key: item
        for key, item in payload.items()
        if item not in ("", None)
    }


def _compact_calibration_run(value: Any) -> dict[str, Any]:
    run = _mapping_or_empty(value)
    payload: dict[str, Any] = {}
    for key in (
        "action",
        "replicate_count",
        "selected_surface",
        "selected_case_count",
        "selected_seed_count",
        "seed_offset",
        "bootstrap_samples",
        "decision_features_excluded",
    ):
        item = run.get(key)
        if item not in ("", None, [], {}, ()):
            payload[key] = item
    runtime_policy = _compact_runtime_policy(run.get("runtime_policy"))
    if runtime_policy:
        payload["runtime_policy"] = runtime_policy
    return payload


def _compact_runtime_policy(value: Any) -> dict[str, Any]:
    policy = _mapping_or_empty(value)
    payload: dict[str, Any] = {}
    for key in (
        "selected_policy",
        "runner_timeout_sec",
        "uniform_time_limit_sec",
        "time_limit_sec",
    ):
        item = policy.get(key)
        if item not in ("", None, [], {}, ()):
            payload[key] = item
    return payload


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _positive_int_or_none(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _cvrp_measurement_reason_codes(
    *,
    runtime_model: str,
    pairing_validity: str,
    practical_screen_delta: float,
    mde_at_power_80: float,
) -> list[str]:
    reason_codes: list[str] = []
    if mde_at_power_80 > practical_screen_delta:
        reason_codes.append("CVRP_MDE_EXCEEDS_PRACTICAL_DELTA")
    if pairing_validity == "trajectory_divergent":
        reason_codes.append("TRAJECTORY_DIVERGENT_LOW_SNR")
    if runtime_model == "budget_exhausting":
        reason_codes.append("BUDGET_EXHAUSTING_RUNTIME_REPORT_ONLY")
    return reason_codes


def _measurement_summary(
    *,
    metric: str,
    mde_at_power_80: float,
    practical_screen_delta: float,
) -> str:
    if mde_at_power_80 > practical_screen_delta:
        return (
            f"Formal screening is low-power for small raw {metric} deltas; "
            "sub-MDE effects need direct objective-effect attribution or "
            "same-mechanism follow-up."
        )
    return (
        f"Formal screening MDE is within the declared practical {metric} delta; "
        "interpret effects against the measured A/A noise floor."
    )


def _current_research_guidance_manifest_fields(
    env: dict[str, object],
) -> tuple[dict[str, Any], dict[str, Any]]:
    scion_dir = Path(env["SCION_DIR"])
    if str(scion_dir) not in sys.path:
        sys.path.insert(0, str(scion_dir))

    from scion.problems.cvrp.research_guidance import (  # noqa: PLC0415
        build_cvrp_legacy_research_focus,
        build_cvrp_research_guidance_contract,
    )
    from scion.research_guidance import (  # noqa: PLC0415
        research_guidance_contract_to_dict,
    )

    measurement = _cvrp_measurement_opportunity_diagnostics(
        scion_dir,
        str(env["PROBLEM"]),
    )
    contract = build_cvrp_research_guidance_contract(
        measurement_opportunity_diagnostics=measurement,
    )
    return build_cvrp_legacy_research_focus(
        measurement_opportunity_diagnostics=measurement,
    ), research_guidance_contract_to_dict(contract)


def _build_command(env: dict[str, object]) -> str:
    forced_args = _forced_surface_command_args(env)
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
        f"--agentic-tool-max-steps {env['AGENTIC_TOOL_MAX_STEPS']} "
        f"--agentic-tool-max-calls {env['AGENTIC_TOOL_MAX_CALLS']} "
        f"--agentic-code-tool-max-calls {env['AGENTIC_CODE_TOOL_MAX_CALLS']} "
        f"--agentic-observation-max-chars {env['AGENTIC_OBSERVATION_MAX_CHARS']} "
        f"--proposal-attempt-limit {env['PROPOSAL_ATTEMPT_LIMIT']} "
        f"--proposal-quality-loop-limit {env['PROPOSAL_QUALITY_LOOP_LIMIT']} "
        f"--fresh-runtime-replay-drain-limit "
        f"{env['SCION_FRESH_RUNTIME_REPLAY_DRAIN_LIMIT']} "
        f"--stage-transition-drain-limit "
        f"{env['SCION_STAGE_TRANSITION_DRAIN_LIMIT']} "
        f"--measurement-governance {env['MEASUREMENT_GOVERNANCE']} "
        f"--proposal-context-ablation {env['PROPOSAL_CONTEXT_ABLATION']} "
        f"{forced_args}"
        "--disable-early-stop "
        "--agentic-proposal"
    )


def _forced_surface_command_args(env: Mapping[str, object]) -> str:
    forced_surface = str(env.get("FORCE_SURFACE") or "").strip()
    if not forced_surface:
        return ""
    parts = ["--force-surface", shlex.quote(forced_surface)]
    forced_action = str(env.get("FORCE_ACTION") or "").strip()
    if forced_action:
        parts.extend(["--force-action", shlex.quote(forced_action)])
    forced_target_file = str(env.get("FORCE_TARGET_FILE") or "").strip()
    if forced_target_file:
        parts.extend(["--force-target-file", shlex.quote(forced_target_file)])
    return " ".join(parts) + " "


def _write_launch_env(run_root: Path, env: dict[str, object]) -> None:
    ordered_keys = [
        "RUN_ROOT",
        "CAMPAIGN_DIR",
        "RESUME_FROM_CAMPAIGN",
        "PREPARED_RUN_MANIFEST",
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
        "SCION_FRESH_RUNTIME_REPLAY_DRAIN_LIMIT",
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
        "PROPOSAL_ATTEMPT_LIMIT",
        "PROPOSAL_QUALITY_LOOP_LIMIT",
        "MEASUREMENT_GOVERNANCE",
        "PROPOSAL_CONTEXT_ABLATION",
        "FORCE_SURFACE",
        "FORCE_ACTION",
        "FORCE_TARGET_FILE",
        "CONTROL_PAIR_KEY",
        "AGENTIC_PROPOSAL",
        "DISABLE_EARLY_STOP",
        "AGENTIC_SESSION_TIMEOUT_SEC",
        "AGENTIC_TOOL_MAX_STEPS",
        "AGENTIC_TOOL_MAX_CALLS",
        "AGENTIC_CODE_TOOL_MAX_CALLS",
        "AGENTIC_OBSERVATION_MAX_CHARS",
        "GIT_COMMIT",
        "GIT_RUNTIME_GUARD_PATHS",
        "STARTED_UTC",
    ]
    content = "\n".join(_shell_assign(key, env[key]) for key in ordered_keys) + "\n"
    launch_env = run_root / "launch.env"
    launch_env.write_text(content, encoding="utf-8")
    launch_env.chmod(0o600)


def _write_run_sh(run_root: Path, command: str, env: dict[str, object]) -> None:
    fallback_keys = [
        "RUN_ROOT",
        "PY",
        "SCION_DIR",
        "MEASUREMENT_GOVERNANCE",
        "PROPOSAL_CONTEXT_ABLATION",
        "FORCE_SURFACE",
        "FORCE_ACTION",
        "FORCE_TARGET_FILE",
        "CONTROL_PAIR_KEY",
        "POSTRUN_REPORTS",
    ]
    fallback_assignments = "\n".join(
        _shell_assign(key, env[key]) for key in fallback_keys
    )
    content = f"""#!/usr/bin/env bash
set -uo pipefail
_INHERITED_SCION_API_KEY="${{SCION_API_KEY:-}}"
_RUN_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
{fallback_assignments}
{POSTRUN_REPORT_FUNCTION_SNIPPET}
if [[ ! -r "$_RUN_SCRIPT_DIR/launch.env" ]]; then
  {{
    echo "WRAPPER_EXIT_STATUS:{PREFLIGHT_FAILURE_EXIT_CODE}"
    echo "ENDED_AT:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "LAUNCH_ENV_MISSING:$_RUN_SCRIPT_DIR/launch.env"
  }} > "$RUN_ROOT/exit.txt"
  printf '{{"schema":"outer-wrapper.v1","status":"finished","wrapper_exit_status":{PREFLIGHT_FAILURE_EXIT_CODE},"launch_env_missing":"%s"}}\\n' "$_RUN_SCRIPT_DIR/launch.env" > "$RUN_ROOT/run_status.json"
  write_postrun_acceptance_reports
  exit {PREFLIGHT_FAILURE_EXIT_CODE}
fi
source "$(dirname "$0")/launch.env"
export PYTHONPATH SCION_MODEL SCION_BASE_URL SCION_API_KEY SCION_SDK_MAX_RETRIES SCION_LLM_MAX_RETRIES SCION_FRESH_RUNTIME_REPLAY_DRAIN_LIMIT SCION_STAGE_TRANSITION_DRAIN_LIMIT SCION_PROBLEM_DATA_ROOT PREPARED_RUN_MANIFEST
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
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
  printf '{{"schema":"outer-wrapper.v1","status":"finished","wrapper_exit_status":{PREFLIGHT_FAILURE_EXIT_CODE},"git_runtime_dirty":true}}\n' > "$RUN_ROOT/run_status.json"
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
    printf '{{"schema":"outer-wrapper.v1","status":"finished","wrapper_exit_status":{PREFLIGHT_FAILURE_EXIT_CODE},"git_runtime_commit_mismatch":true}}\n' > "$RUN_ROOT/run_status.json"
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
{COMPLETION_PREFLIGHT_SNIPPET}
CAMPAIGN_EXECUTION_MARKER_STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '{{"schema":"scion.launcher_campaign_execution_marker.v1","started_at":"%s","run_root":"%s","campaign_dir":"%s"}}\n' \
  "$CAMPAIGN_EXECUTION_MARKER_STARTED_AT" "$RUN_ROOT" "$CAMPAIGN_DIR" \
  > "$RUN_ROOT/campaign_execution_marker.v1.json"
echo "CAMPAIGN_EXECUTION_MARKER:$RUN_ROOT/campaign_execution_marker.v1.json" >> "$RUN_ROOT/run.log"
FORCE_ARGS=()
if [[ -n "${{FORCE_SURFACE:-}}" ]]; then
  FORCE_ARGS+=(--force-surface "$FORCE_SURFACE")
  if [[ -n "${{FORCE_ACTION:-}}" ]]; then
    FORCE_ARGS+=(--force-action "$FORCE_ACTION")
  fi
  if [[ -n "${{FORCE_TARGET_FILE:-}}" ]]; then
    FORCE_ARGS+=(--force-target-file "$FORCE_TARGET_FILE")
  fi
fi
"$PY" -m scion.cli.main run \\
  --problem "$PROBLEM" \\
  --protocol "$PROTOCOL" \\
  --split "$SPLIT" \\
  --seeds "$SEEDS" \\
  --campaign-dir "$CAMPAIGN_DIR" \\
  --rounds "$ROUNDS" \\
  --time-limit-sec "$TIME_LIMIT_SEC" \\
  --agentic-session-timeout-sec "$AGENTIC_SESSION_TIMEOUT_SEC" \\
  --agentic-tool-max-steps "$AGENTIC_TOOL_MAX_STEPS" \\
  --agentic-tool-max-calls "$AGENTIC_TOOL_MAX_CALLS" \\
  --agentic-code-tool-max-calls "$AGENTIC_CODE_TOOL_MAX_CALLS" \\
  --agentic-observation-max-chars "$AGENTIC_OBSERVATION_MAX_CHARS" \\
  --proposal-attempt-limit "$PROPOSAL_ATTEMPT_LIMIT" \\
  --proposal-quality-loop-limit "$PROPOSAL_QUALITY_LOOP_LIMIT" \\
  --fresh-runtime-replay-drain-limit "$SCION_FRESH_RUNTIME_REPLAY_DRAIN_LIMIT" \\
  --stage-transition-drain-limit "$SCION_STAGE_TRANSITION_DRAIN_LIMIT" \\
  --measurement-governance "$MEASUREMENT_GOVERNANCE" \\
  --proposal-context-ablation "$PROPOSAL_CONTEXT_ABLATION" \\
  "${{FORCE_ARGS[@]}}" \\
  --disable-early-stop \\
  --agentic-proposal \\
  >> "$RUN_ROOT/run.log" 2>&1
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
  "$PY" "$SCION_DIR/tools/write_postrun_wrapper_status.py" \
    --output "$RUN_ROOT/run_status.json" \
    --wrapper-exit-code "$STATUS" \
    --campaign-exit-code "$CAMPAIGN_STATUS" \
    --postrun-reports-exit-code "$POSTRUN_STATUS" \
    --postrun-readiness-exit-code "$POSTRUN_READINESS_STATUS" \
    --postrun-report-dir "$REPORT_DIR" \
    --postrun-readiness-path "$REPORT_DIR/readiness/$REPORT_STEM.postrun_acceptance_readiness.v1.json" \
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
        "agentic_session_timeout_sec": int(env["AGENTIC_SESSION_TIMEOUT_SEC"]),
        "agentic_tool_max_steps": int(env["AGENTIC_TOOL_MAX_STEPS"]),
        "agentic_tool_max_calls": int(env["AGENTIC_TOOL_MAX_CALLS"]),
        "agentic_code_tool_max_calls": int(env["AGENTIC_CODE_TOOL_MAX_CALLS"]),
        "agentic_observation_max_chars": int(env["AGENTIC_OBSERVATION_MAX_CHARS"]),
        "proposal_attempt_limit": int(env["PROPOSAL_ATTEMPT_LIMIT"]),
        "proposal_quality_loop_limit": int(env["PROPOSAL_QUALITY_LOOP_LIMIT"]),
        "fresh_runtime_replay_drain_limit": int(
            env["SCION_FRESH_RUNTIME_REPLAY_DRAIN_LIMIT"]
        ),
        "stage_transition_drain_limit": int(
            env["SCION_STAGE_TRANSITION_DRAIN_LIMIT"]
        ),
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
    research_focus, research_guidance_contract = _current_research_guidance_manifest_fields(
        env
    )
    manifest = {
        "schema_version": PREPARED_RUN_MANIFEST_SCHEMA,
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
        "problem_family": "cvrp",
        "analysis_intent": CVRP_ANALYSIS_INTENT,
        "research_focus": research_focus,
        "research_guidance_contract": research_guidance_contract,
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
            "protocol": str(env["PROTOCOL"]),
            "split": str(env["SPLIT"]),
            "seeds": str(env["SEEDS"]),
            "data_root": str(env["SCION_PROBLEM_DATA_ROOT"]),
        },
        "execution": {
            "rounds": int(env["ROUNDS"]),
            "time_limit_sec": int(env["TIME_LIMIT_SEC"]),
            "agentic_session_timeout_sec": int(env["AGENTIC_SESSION_TIMEOUT_SEC"]),
            "agentic_tool_max_steps": int(env["AGENTIC_TOOL_MAX_STEPS"]),
            "agentic_tool_max_calls": int(env["AGENTIC_TOOL_MAX_CALLS"]),
            "agentic_code_tool_max_calls": int(env["AGENTIC_CODE_TOOL_MAX_CALLS"]),
            "agentic_observation_max_chars": int(
                env["AGENTIC_OBSERVATION_MAX_CHARS"]
            ),
            "proposal_attempt_limit": int(env["PROPOSAL_ATTEMPT_LIMIT"]),
            "proposal_quality_loop_limit": int(
                env["PROPOSAL_QUALITY_LOOP_LIMIT"]
            ),
            "fresh_runtime_replay_drain_limit": int(
                env["SCION_FRESH_RUNTIME_REPLAY_DRAIN_LIMIT"]
            ),
            "stage_transition_drain_limit": int(
                env["SCION_STAGE_TRANSITION_DRAIN_LIMIT"]
            ),
            "measurement_governance": str(env["MEASUREMENT_GOVERNANCE"]),
            "proposal_context_ablation": str(env["PROPOSAL_CONTEXT_ABLATION"]),
            "force_surface": str(env.get("FORCE_SURFACE") or ""),
            "force_action": str(env.get("FORCE_ACTION") or ""),
            "force_target_file": str(env.get("FORCE_TARGET_FILE") or ""),
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
            "Do not treat aggregate win rate alone as sufficient evidence.",
            "Interpret candidate evidence against A/A MDE and case-level variance.",
            "Require branch depth, mechanism continuity, useful branch lessons, and source visibility checks.",
            "Check the research_focus default-avoid list before accepting "
            "route-merge, construction-seed, cadence, or VNS follow-up as "
            "materially new.",
            "If pursuing the large-instance two-opt seed, require a deadline-aware "
            "bounded local-search implementation and wall-clock evidence.",
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
        f"- Question: {research_focus['current_question']}",
        f"- Next required direction: {research_focus['next_required_direction']}",
        "- Required mechanism ids: "
        + ", ".join(map(str, research_focus["required_mechanism_ids"])),
        f"- Route-merge exception: {research_focus['route_merge_exception_rule']}",
        f"- Construction-seed rule: {research_focus['construction_seed_rule']}",
        "- Missing-primary telemetry rule: "
        f"{research_focus['missing_primary_telemetry_rule']}",
        f"- Decision boundary: {research_focus['decision_boundary']}",
        "- Required evidence:",
    ]
    required_evidence = research_focus.get("required_evidence")
    if isinstance(required_evidence, list) and required_evidence:
        lines.extend(f"  - {item}" for item in required_evidence)
    else:
        lines.append("  - None recorded in the prepared manifest.")
    lines.append("- Measurement/opportunity diagnostics:")
    measurement = research_focus.get("measurement_opportunity_diagnostics")
    if isinstance(measurement, dict):
        for key in (
            "metric",
            "runtime_model",
            "pairing_validity",
            "practical_screen_delta",
            "screening_mde_at_power_80",
            "recommended_min_seeds",
            "opportunity_projection_source",
            "adapter_payload_schema",
            "summary",
        ):
            if key in measurement:
                lines.append(f"  - {key}: {measurement[key]}")
        reason_codes = measurement.get("reason_codes")
        if isinstance(reason_codes, list) and reason_codes:
            lines.append("  - reason_codes: " + ", ".join(map(str, reason_codes)))
        calibration = measurement.get("calibration")
        if isinstance(calibration, dict):
            source_artifact = calibration.get("source_artifact")
            if isinstance(source_artifact, dict) and source_artifact:
                lines.append(
                    "  - calibration_source_sha256: "
                    f"{source_artifact.get('sha256')}"
                )
            calibration_run = calibration.get("calibration_run")
            if isinstance(calibration_run, dict) and calibration_run:
                run_bits = []
                for key in (
                    "replicate_count",
                    "selected_surface",
                    "selected_case_count",
                    "selected_seed_count",
                ):
                    if key in calibration_run:
                        run_bits.append(f"{key}={calibration_run[key]}")
                runtime_policy = calibration_run.get("runtime_policy")
                if isinstance(runtime_policy, dict) and runtime_policy:
                    selected_policy = runtime_policy.get("selected_policy")
                    if selected_policy:
                        run_bits.append(f"runtime_policy={selected_policy}")
                if run_bits:
                    lines.append("  - calibration_run: " + "; ".join(run_bits))
        screening_headroom = measurement.get("screening_headroom")
        if isinstance(screening_headroom, dict) and screening_headroom:
            lines.append("  - screening_headroom:")
            for key in (
                "scope",
                "metric",
                "case_count",
                "gap_pct_min",
                "gap_pct_max",
                "case_count_gap_pct_at_least_3",
                "planning_use",
            ):
                if key in screening_headroom:
                    lines.append(f"    - {key}: {screening_headroom[key]}")
        mechanism_ranking = measurement.get("mechanism_effect_ranking")
        if isinstance(mechanism_ranking, list) and mechanism_ranking:
            lines.append("  - mechanism_effect_ranking:")
            for item in mechanism_ranking[:5]:
                if not isinstance(item, dict):
                    continue
                rank = item.get("rank")
                family = item.get("mechanism_family")
                status = item.get("opportunity_status")
                action = item.get("recommended_action")
                lines.append(
                    f"    - rank={rank}; mechanism_family={family}; "
                    f"opportunity_status={status}; recommended_action={action}"
                )
        opportunity_diagnostics = measurement.get("opportunity_diagnostics")
        if isinstance(opportunity_diagnostics, list) and opportunity_diagnostics:
            lines.append("  - opportunity_diagnostics:")
            for item in opportunity_diagnostics[:5]:
                if not isinstance(item, dict):
                    continue
                dtype = item.get("diagnostic_type")
                family = item.get("mechanism_family")
                action = item.get("recommended_action")
                lines.append(
                    f"    - diagnostic_type={dtype}; "
                    f"mechanism_family={family}; recommended_action={action}"
                )
    else:
        lines.append("  - None recorded in the prepared manifest.")
    lines.append("- Measurable opportunity classes:")
    opportunity_classes = research_focus.get("measurable_opportunity_classes")
    if isinstance(opportunity_classes, list) and opportunity_classes:
        for item in opportunity_classes:
            lines.append(f"  - {item}")
    else:
        lines.append("  - None recorded in the prepared manifest.")
    large_twoopt = research_focus.get("large_instance_two_opt_constraints")
    if isinstance(large_twoopt, dict) and large_twoopt:
        lines.extend(
            [
                "- Large-instance two-opt constraints:",
                f"  - schema_version: {large_twoopt.get('schema_version')}",
                f"  - seed_report: {large_twoopt.get('seed_report')}",
                "  - implementation_constraints:",
            ]
        )
        for item in large_twoopt.get("implementation_constraints") or []:
            lines.append(f"    - {item}")
        lines.append("  - required_pair_evidence:")
        for item in large_twoopt.get("required_pair_evidence") or []:
            lines.append(f"    - {item}")
        lines.append("  - default_reject_directions:")
        for item in large_twoopt.get("default_reject_directions") or []:
            lines.append(f"    - {item}")
    lines.extend([
        "- Default-avoid directions:",
    ])
    for item in research_focus["default_avoid_directions"]:
        lines.append(f"  - {item}")
    case_protection = research_focus.get("case_protection_requirements")
    if isinstance(case_protection, dict) and case_protection:
        lines.extend(
            [
                "- Case-protection requirements:",
                f"  - schema_version: {case_protection.get('schema_version')}",
                "  - protected_cases: "
                + ", ".join(map(str, case_protection.get("protected_cases") or [])),
                "  - rules:",
            ]
        )
        for item in case_protection.get("rules") or []:
            lines.append(f"    - {item}")
        lines.append("  - required_evidence:")
        for item in case_protection.get("required_evidence") or []:
            lines.append(f"    - {item}")
    resume_continuity = research_focus.get("resume_continuity_requirements")
    if isinstance(resume_continuity, dict) and resume_continuity:
        lines.extend(
            [
                "- Resume-continuity requirements:",
                f"  - schema_version: {resume_continuity.get('schema_version')}",
                "  - fallback_sources:",
            ]
        )
        for item in resume_continuity.get("fallback_sources") or []:
            lines.append(f"    - {item}")
        lines.append("  - rules:")
        for item in resume_continuity.get("rules") or []:
            lines.append(f"    - {item}")
        lines.append("  - required_evidence:")
        for item in resume_continuity.get("required_evidence") or []:
            lines.append(f"    - {item}")
    lines.extend(["", "## Config"])
    for key in ("problem", "protocol", "split", "seeds", "data_root"):
        lines.append(f"- {key}: `{config[key]}`")
    lines.extend(["", "## Execution"])
    for key in (
        "rounds",
        "time_limit_sec",
        "agentic_session_timeout_sec",
        "agentic_tool_max_steps",
        "agentic_tool_max_calls",
        "agentic_code_tool_max_calls",
        "agentic_observation_max_chars",
        "proposal_attempt_limit",
        "proposal_quality_loop_limit",
        "fresh_runtime_replay_drain_limit",
        "stage_transition_drain_limit",
        "measurement_governance",
        "proposal_context_ablation",
        "force_surface",
        "force_action",
        "force_target_file",
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
        "cvrp_"
        f"{str(env['MEASUREMENT_GOVERNANCE']).replace('-', '_')}_"
        f"{str(env['PROPOSAL_CONTEXT_ABLATION']).replace('-', '_')}"
    )
    rebuild_prepared_handoff(run_root, report_stem=report_stem, strict=True)


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
    control_pair_key = _prepared_control_pair_key(
        args.control_pair_key,
        label=label,
    )

    env: dict[str, object] = {
        "RUN_ROOT": run_root,
        "CAMPAIGN_DIR": campaign_dir,
        "RESUME_FROM_CAMPAIGN": resume_from_campaign,
        "PREPARED_RUN_MANIFEST": run_root / "prepared_run_manifest.v1.json",
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
        "SCION_FRESH_RUNTIME_REPLAY_DRAIN_LIMIT": (
            args.fresh_runtime_replay_drain_limit
        ),
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
        "PROPOSAL_ATTEMPT_LIMIT": args.proposal_attempt_limit,
        "PROPOSAL_QUALITY_LOOP_LIMIT": args.proposal_quality_loop_limit,
        "MEASUREMENT_GOVERNANCE": args.measurement_governance,
        "PROPOSAL_CONTEXT_ABLATION": args.proposal_context_ablation,
        "FORCE_SURFACE": args.force_surface or "",
        "FORCE_ACTION": args.force_action or "",
        "FORCE_TARGET_FILE": args.force_target_file or "",
        "CONTROL_PAIR_KEY": control_pair_key,
        "AGENTIC_PROPOSAL": 1,
        "DISABLE_EARLY_STOP": 1,
        "AGENTIC_SESSION_TIMEOUT_SEC": args.agentic_session_timeout_sec,
        "AGENTIC_TOOL_MAX_STEPS": args.agentic_tool_max_steps,
        "AGENTIC_TOOL_MAX_CALLS": args.agentic_tool_max_calls,
        "AGENTIC_CODE_TOOL_MAX_CALLS": args.agentic_code_tool_max_calls,
        "AGENTIC_OBSERVATION_MAX_CHARS": args.agentic_observation_max_chars,
        "GIT_COMMIT": _git_commit(repo_root),
        "GIT_RUNTIME_GUARD_PATHS": (
            "scion/scion :(exclude)scion/scion/tests "
            "scion/tools scion/problems/cvrp vrp"
        ),
        "STARTED_UTC": started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    command = _build_command(env)
    _write_launch_env(run_root, env)
    _write_run_sh(run_root, command, env)
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
            f"SCION_FRESH_RUNTIME_REPLAY_DRAIN_LIMIT="
            f"{env['SCION_FRESH_RUNTIME_REPLAY_DRAIN_LIMIT']}\n"
            f"SCION_STAGE_TRANSITION_DRAIN_LIMIT="
            f"{env['SCION_STAGE_TRANSITION_DRAIN_LIMIT']}\n\n"
            f"AGENTIC_SESSION_TIMEOUT_SEC={env['AGENTIC_SESSION_TIMEOUT_SEC']}\n"
            f"AGENTIC_TOOL_MAX_STEPS={env['AGENTIC_TOOL_MAX_STEPS']}\n"
            f"AGENTIC_TOOL_MAX_CALLS={env['AGENTIC_TOOL_MAX_CALLS']}\n"
            f"AGENTIC_CODE_TOOL_MAX_CALLS={env['AGENTIC_CODE_TOOL_MAX_CALLS']}\n"
            "AGENTIC_OBSERVATION_MAX_CHARS="
            f"{env['AGENTIC_OBSERVATION_MAX_CHARS']}\n\n"
            f"PROPOSAL_ATTEMPT_LIMIT={env['PROPOSAL_ATTEMPT_LIMIT']}\n"
            f"PROPOSAL_QUALITY_LOOP_LIMIT={env['PROPOSAL_QUALITY_LOOP_LIMIT']}\n\n"
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
    parser.add_argument(
        "--force-surface",
        default=None,
        help=(
            "Diagnostic pass-through to scion run --force-surface. Use with "
            "--force-action/--force-target-file to constrain the next "
            "hypothesis target."
        ),
    )
    parser.add_argument(
        "--force-action",
        default=None,
        help="Diagnostic pass-through to scion run --force-action.",
    )
    parser.add_argument(
        "--force-target-file",
        default=None,
        help="Diagnostic pass-through to scion run --force-target-file.",
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
        "--agentic-tool-max-steps",
        type=int,
        default=DEFAULT_AGENTIC_TOOL_MAX_STEPS,
        help=(
            "APS per-session step cap for focused v0.4 agentic research. "
            "Defaults to 0, which disables this cap."
        ),
    )
    parser.add_argument(
        "--agentic-tool-max-calls",
        type=int,
        default=DEFAULT_AGENTIC_TOOL_MAX_CALLS,
        help=(
            "APS per-session tool-call cap for focused v0.4 agentic research. "
            "Defaults to 0, which disables this cap."
        ),
    )
    parser.add_argument(
        "--agentic-code-tool-max-calls",
        type=int,
        default=DEFAULT_AGENTIC_CODE_TOOL_MAX_CALLS,
        help=(
            "APS code-phase tool-call cap for focused v0.4 agentic research. "
            "Defaults to 0, which disables this cap."
        ),
    )
    parser.add_argument(
        "--agentic-observation-max-chars",
        type=int,
        default=DEFAULT_AGENTIC_OBSERVATION_MAX_CHARS,
        help=(
            "APS retained observation-character cap for focused v0.4 runs. "
            "Defaults to 0, which disables this cap."
        ),
    )
    parser.add_argument(
        "--proposal-attempt-limit",
        type=int,
        default=DEFAULT_PROPOSAL_ATTEMPT_LIMIT,
        help=(
            "Focused v0.4 proposal attempt cap passed to scion run. Defaults "
            "to 0, which disables this research-headroom cap; runaway loops "
            "still use the core safety guard and circuit breaker."
        ),
    )
    parser.add_argument(
        "--proposal-quality-loop-limit",
        type=int,
        default=DEFAULT_PROPOSAL_QUALITY_LOOP_LIMIT,
        help=(
            "Focused v0.4 proposal-quality block cap passed to scion run. "
            "Defaults to 0, which disables this research-headroom cap."
        ),
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
        "--fresh-runtime-replay-drain-limit",
        type=int,
        default=DEFAULT_FRESH_RUNTIME_REPLAY_DRAIN_LIMIT,
        help=(
            "Focused v0.4 post-budget fresh-runtime replay drain cap passed "
            "to scion run. Defaults to 0, which disables this hidden replay "
            "drain for focused research launches."
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
    if args.agentic_tool_max_steps < 0:
        raise SystemExit("--agentic-tool-max-steps must be >= 0")
    if args.agentic_tool_max_calls < 0:
        raise SystemExit("--agentic-tool-max-calls must be >= 0")
    if args.agentic_code_tool_max_calls < 0:
        raise SystemExit("--agentic-code-tool-max-calls must be >= 0")
    if args.agentic_observation_max_chars < 0:
        raise SystemExit("--agentic-observation-max-chars must be >= 0")
    if args.proposal_attempt_limit < 0:
        raise SystemExit("--proposal-attempt-limit must be >= 0")
    if args.proposal_quality_loop_limit < 0:
        raise SystemExit("--proposal-quality-loop-limit must be >= 0")
    if args.fresh_runtime_replay_drain_limit < 0:
        raise SystemExit("--fresh-runtime-replay-drain-limit must be >= 0")
    if args.stage_transition_drain_limit < 0:
        raise SystemExit("--stage-transition-drain-limit must be >= 0")
    if args.api_key is not None and args.api_key_env:
        raise SystemExit("--api-key and --api-key-env are mutually exclusive")
    if args.force_surface is None and (
        args.force_action is not None or args.force_target_file is not None
    ):
        raise SystemExit(
            "--force-action and --force-target-file require --force-surface"
        )
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
