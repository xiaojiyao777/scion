#!/usr/bin/env python3
"""Prepare or launch the CVRP direct-v3 Scion campaign."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

SCION_PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(SCION_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(SCION_PROJECT_DIR))

from scion.launcher.lifecycle import (
    CampaignCommandPlan,
    LauncherLifecyclePlan,
    render_run_sh,
)
from scion.launcher.resume import (
    ResumePreparationError,
    prepare_launcher_campaign,
)
DEFAULT_EXPERIMENTS_ROOT = Path.home() / "research" / "scion-experiments"
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_BASE_URL = "http://127.0.0.1:8080"
DEFAULT_LOCAL_PROXY_API_KEY = "pwd"
DEFAULT_TIME_LIMIT_SEC = 30
DEFAULT_PYTHON = Path(sys.executable)
DEFAULT_USER_SUFFIX = "claw"
PREFLIGHT_FAILURE_EXIT_CODE = 64
PROPOSAL_RUNTIME_MODE = "direct_v3"

PROBLEM = "scion/problems/cvrp/problem.yaml"
PROTOCOL = "scion/problems/cvrp/formal/protocol.yaml"
SPLIT = "scion/problems/cvrp/formal/split_manifest.yaml"
SEEDS = "scion/problems/cvrp/formal/seed_ledger.yaml"
CVRP_SPECS_REQUIRING_PARAMETER_SEARCH_DISABLED = (
    PROBLEM,
    "scion/problems/cvrp/problem-v1.yaml",
)
ENV_VAR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
PREPARED_RUN_MANIFEST_SCHEMA = "scion.launcher_prepared_run_manifest.v1"
TASK_DOC = "scion/TASK.md"
CURRENT_STATE_DOC = "scion/docs/status/current-state.md"
ANALYSIS_HANDOFF_DOC = "scion/docs/operations/postrun-analysis-handoff.md"
CVRP_ANALYSIS_INTENT = (
    "Inspect direct hypothesis/code attempts, complete source visibility, "
    "screening evidence, and durable protocol results before accepting a CVRP "
    "research conclusion."
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
                "CVRP direct-v3 launcher requires "
                f"parameter_search.enabled=false in {display_path}"
            )


def _problem_v1_path_for_problem(scion_dir: Path, problem: str) -> Path:
    return _resolve_spec_path(scion_dir, problem).with_name("problem-v1.yaml")


def _cvrp_measurement_opportunity_diagnostics(
    scion_dir: Path,
    problem: str,
) -> dict[str, Any]:
    """Build current CVRP measurement guidance from declared problem data."""

    if str(scion_dir) not in sys.path:
        sys.path.insert(0, str(scion_dir))

    from scion.measurement.consumer_view import measurement_consumer_view  # noqa: PLC0415
    from scion.problem.bridge import load_problem_spec_v1_from_yaml  # noqa: PLC0415

    problem_v1 = _problem_v1_path_for_problem(scion_dir, problem)
    if not problem_v1.is_file():
        raise SystemExit(
            "CVRP direct-v3 launcher requires problem-v1 measurement declaration: "
            f"{problem_v1}"
        )

    spec = load_problem_spec_v1_from_yaml(problem_v1)
    measurement_view = measurement_consumer_view(spec)
    if measurement_view.readiness_status != "ready":
        raise SystemExit(
            "CVRP measurement calibration is not launch-ready: "
            f"{measurement_view.readiness_reason_code}"
        )

    return {
        "schema_version": "scion.cvrp_measurement_handoff.v3",
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
        "metric": measurement_view.effect_metric,
        "unit": measurement_view.effect_unit,
        "practical_screen_delta": measurement_view.practical_delta_screen,
        "practical_validate_delta": measurement_view.practical_delta_validate,
        "screening_mde_at_power_80": measurement_view.mde_at_power_80,
        "problem_owned_guidance": _cvrp_adapter_guidance_projection(spec),
    }


def _cvrp_adapter_guidance_projection(spec: Any) -> dict[str, Any]:
    """Project current problem guidance without historical target fields."""

    from scion.problem.loader import load_problem_adapter  # noqa: PLC0415

    adapter = load_problem_adapter(spec)
    hook = getattr(adapter, "render_problem_measurement_diagnostics", None)
    if not callable(hook):
        raise SystemExit(
            "CVRP direct-v3 launcher requires adapter measurement guidance"
        )
    payload = hook()
    if not isinstance(payload, Mapping):
        raise SystemExit("CVRP adapter measurement guidance must be a mapping")
    redacted = _redact_cvrp_adapter_opportunity_payload(dict(payload))
    if not isinstance(redacted, Mapping):
        raise SystemExit("CVRP adapter measurement guidance is invalid")
    return dict(redacted)
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


def _current_research_guidance_manifest_fields(
    env: dict[str, object],
) -> tuple[dict[str, Any], dict[str, Any]]:
    scion_dir = Path(env["SCION_DIR"])
    if str(scion_dir) not in sys.path:
        sys.path.insert(0, str(scion_dir))

    from scion.problems.cvrp.research_guidance import (  # noqa: PLC0415
        build_cvrp_research_focus,
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
    return build_cvrp_research_focus(
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
        f"{forced_args}"
    ).strip()


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
        "RESUME_SNAPSHOT_MANIFEST_REF",
        "RESUME_COPIED_CAMPAIGN_STATUS_PRESENT",
        "RESUME_COPIED_CAMPAIGN_SUMMARY_PRESENT",
        "PREPARED_RUN_MANIFEST",
        "REPO_ROOT",
        "SCION_DIR",
        "PY",
        "PYTHONPATH",
        "SCION_MODEL",
        "SCION_BASE_URL",
        "SCION_API_KEY",
        "SCION_API_KEY_ENV",
        "SCION_PROBLEM_DATA_ROOT",
        "COMPLETION_PREFLIGHT",
        "POSTRUN_REPORTS",
        "PROBLEM",
        "PROTOCOL",
        "SPLIT",
        "SEEDS",
        "ROUNDS",
        "TIME_LIMIT_SEC",
        "FORCE_SURFACE",
        "FORCE_ACTION",
        "FORCE_TARGET_FILE",
        "CONTROL_PAIR_KEY",
        "GIT_COMMIT",
        "GIT_RUNTIME_GUARD_PATHS",
        "RUN_SCRIPT_SHA256",
        "STARTED_UTC",
    ]
    content = "\n".join(_shell_assign(key, env[key]) for key in ordered_keys) + "\n"
    launch_env = run_root / "launch.env"
    launch_env.write_text(content, encoding="utf-8")
    launch_env.chmod(0o600)


def _write_run_sh(run_root: Path, command: str, env: dict[str, object]) -> str:
    fallback_keys = [
        "RUN_ROOT",
        "PY",
        "SCION_DIR",
        "FORCE_SURFACE",
        "FORCE_ACTION",
        "FORCE_TARGET_FILE",
        "CONTROL_PAIR_KEY",
        "POSTRUN_REPORTS",
    ]
    command_plan = CampaignCommandPlan(
        command_log=command,
        exported_env_names=("SCION_PROBLEM_DATA_ROOT",),
        command_body=r'''FORCE_ARGS=()
if [[ -n "${FORCE_SURFACE:-}" ]]; then
  FORCE_ARGS+=(--force-surface "$FORCE_SURFACE")
  if [[ -n "${FORCE_ACTION:-}" ]]; then
    FORCE_ARGS+=(--force-action "$FORCE_ACTION")
  fi
  if [[ -n "${FORCE_TARGET_FILE:-}" ]]; then
    FORCE_ARGS+=(--force-target-file "$FORCE_TARGET_FILE")
  fi
fi
"$PY" -m scion.cli.main run \
  --problem "$PROBLEM" \
  --protocol "$PROTOCOL" \
  --split "$SPLIT" \
  --seeds "$SEEDS" \
  --campaign-dir "$CAMPAIGN_DIR" \
  --rounds "$ROUNDS" \
  --time-limit-sec "$TIME_LIMIT_SEC" \
  "${FORCE_ARGS[@]}" \
  >> "$RUN_ROOT/run.log" 2>&1''',
    )
    plan = LauncherLifecyclePlan(
        run_root=Path(env["RUN_ROOT"]),
        campaign_dir=Path(env["CAMPAIGN_DIR"]),
        repo_root=Path(env["REPO_ROOT"]),
        scion_dir=Path(env["SCION_DIR"]),
        python=Path(env["PY"]),
        git_commit=str(env["GIT_COMMIT"]),
        model=str(env["SCION_MODEL"]),
        scion_base_url=str(env["SCION_BASE_URL"]),
        api_key_env_binding=str(env["SCION_API_KEY_ENV"]),
        postrun_report_stem_prefix="cvrp",
        command=command_plan,
        fallback_assignments=tuple((key, env[key]) for key in fallback_keys),
        exported_env_names=(
            "PYTHONPATH",
            "SCION_MODEL",
            "SCION_BASE_URL",
            "SCION_API_KEY",
            "PREPARED_RUN_MANIFEST",
        ),
        preflight_failure_exit_code=PREFLIGHT_FAILURE_EXIT_CODE,
    )
    content = render_run_sh(plan)
    run_sh = run_root / "run.sh"
    run_sh.write_text(content, encoding="utf-8")
    run_sh.chmod(0o755)
    return hashlib.sha256(run_sh.read_bytes()).hexdigest()


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
    resume_snapshot_ref = str(env.get("RESUME_SNAPSHOT_MANIFEST_REF") or "")
    status = {
        "schema": "scion.launcher_prepare.v1",
        "status": "prepared",
        "prepared_only": True,
        "run_root": str(run_root),
        "campaign_dir": str(campaign_dir),
        "resume_from_campaign": resume_from,
        "resume_snapshot_ref": resume_snapshot_ref,
        "copied_campaign_status_present": bool(
            int(env.get("RESUME_COPIED_CAMPAIGN_STATUS_PRESENT", 0))
        ),
        "copied_campaign_summary_present": bool(
            int(env.get("RESUME_COPIED_CAMPAIGN_SUMMARY_PRESENT", 0))
        ),
        "scion_model": str(env["SCION_MODEL"]),
        "scion_base_url": str(env["SCION_BASE_URL"]),
        "completion_preflight": bool(int(env["COMPLETION_PREFLIGHT"])),
        "postrun_reports": bool(int(env["POSTRUN_REPORTS"])),
        "control_pair_key": str(env.get("CONTROL_PAIR_KEY") or ""),
        "proposal_runtime_mode": PROPOSAL_RUNTIME_MODE,
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
        "resume_snapshot_ref": str(env.get("RESUME_SNAPSHOT_MANIFEST_REF") or ""),
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
        "run_script": {
            "path": str(run_root / "run.sh"),
            "sha256": str(env["RUN_SCRIPT_SHA256"]),
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
            "proposal_runtime_mode": PROPOSAL_RUNTIME_MODE,
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
            "Interpret paired aggregate, case-level, feasibility, route-count, and runtime evidence together.",
            "Review attribution of the final result against the changed execution path and current source.",
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
    guidance = manifest["research_guidance_contract"]
    assert isinstance(config, dict)
    assert isinstance(execution, dict)
    assert isinstance(reports, dict)
    assert isinstance(research_focus, dict)
    assert isinstance(guidance, dict)

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
        "## Current Research Guidance",
        f"- Question: {research_focus['current_question']}",
        f"- Decision boundary: {research_focus['decision_boundary']}",
        f"- Contract: `{guidance['schema_version']}`",
        "- Required mechanisms: none",
        "- Guidance blocks:",
    ]
    for block in guidance.get("guidance_blocks") or []:
        if not isinstance(block, Mapping):
            continue
        lines.append(f"  - {block.get('title')}: {block.get('category')}")

    lines.extend(["", "## Config"])
    for key in ("problem", "protocol", "split", "seeds", "data_root"):
        lines.append(f"- {key}: `{config[key]}`")
    lines.extend(["", "## Execution"])
    for key in (
        "rounds",
        "time_limit_sec",
        "proposal_runtime_mode",
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
            (
                "- Prepared handoff families: "
                f"`{', '.join(reports['prepared_handoff_families'])}`"
            ),
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

    report_stem = "cvrp_direct_v3"
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
    try:
        resume_state = prepare_launcher_campaign(
            resume_from_campaign=args.resume_from_campaign,
            campaign_dir=campaign_dir,
            run_root=run_root,
        )
    except ResumePreparationError as exc:
        raise SystemExit(str(exc)) from exc
    api_key, api_key_env = _resolve_api_key(args)
    control_pair_key = _prepared_control_pair_key(
        args.control_pair_key,
        label=label,
    )
    env: dict[str, object] = {
        "RUN_ROOT": run_root,
        "CAMPAIGN_DIR": campaign_dir,
        "PREPARED_RUN_MANIFEST": run_root / "prepared_run_manifest.v1.json",
        "REPO_ROOT": repo_root,
        "SCION_DIR": scion_dir,
        "PY": args.python,
        "PYTHONPATH": scion_dir,
        "SCION_MODEL": args.model,
        "SCION_BASE_URL": args.base_url,
        "SCION_API_KEY": api_key,
        "SCION_API_KEY_ENV": api_key_env,
        "SCION_PROBLEM_DATA_ROOT": repo_root / "vrp",
        "COMPLETION_PREFLIGHT": 1 if args.completion_preflight else 0,
        "POSTRUN_REPORTS": 0 if args.skip_postrun_reports else 1,
        "PROBLEM": args.problem,
        "PROTOCOL": args.protocol,
        "SPLIT": args.split,
        "SEEDS": args.seeds,
        "ROUNDS": args.rounds,
        "TIME_LIMIT_SEC": args.time_limit_sec,
        "FORCE_SURFACE": args.force_surface or "",
        "FORCE_ACTION": args.force_action or "",
        "FORCE_TARGET_FILE": args.force_target_file or "",
        "CONTROL_PAIR_KEY": control_pair_key,
        "GIT_COMMIT": _git_commit(repo_root),
        "GIT_RUNTIME_GUARD_PATHS": (
            "scion/scion :(exclude)scion/scion/tests "
            "scion/tools scion/problems/cvrp vrp"
        ),
        "STARTED_UTC": started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    env.update(resume_state.env())

    command = _build_command(env)
    env["RUN_SCRIPT_SHA256"] = _write_run_sh(run_root, command, env)
    _write_launch_env(run_root, env)
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
            f"PROPOSAL_RUNTIME_MODE={PROPOSAL_RUNTIME_MODE}\n\n"
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
            f"RESUME_SNAPSHOT_MANIFEST_REF={env['RESUME_SNAPSHOT_MANIFEST_REF']}\n\n"
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
            "Prepare a CVRP direct-v3 Scion campaign run root. "
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
            "Defaults to the local proxy key for 127.0.0.1:8080; "
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
            "exits. The default is to write summary, failures, trajectory, "
            "analysis-brief, inventory, readiness, and rebuild reports."
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
            "Per solver subprocess timeout. Defaults to 30s for CVRP preliminary "
            "screening validation; pass 10 explicitly only for small smoke runs."
        ),
    )
    parser.add_argument(
        "--resume-from-campaign",
        type=Path,
        default=None,
        help=(
            "Copy an existing campaign directory into the new run root before "
            "a diagnostic/non-formal launch. Completion-preflight formal roots "
            "must start from a fresh campaign."
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
    if args.api_key is not None and args.api_key_env:
        raise SystemExit("--api-key and --api-key-env are mutually exclusive")
    forced_targeting = (
        args.force_surface is not None
        or args.force_action is not None
        or args.force_target_file is not None
    )
    if args.completion_preflight and forced_targeting:
        raise SystemExit(
            "--completion-preflight requires an open research launch without "
            "--force-surface/--force-action/--force-target-file"
        )
    if args.completion_preflight and args.resume_from_campaign is not None:
        raise SystemExit(
            "--completion-preflight requires a fresh campaign without "
            "--resume-from-campaign"
        )
    if args.completion_preflight and args.skip_postrun_reports:
        raise SystemExit(
            "--completion-preflight requires strict postrun reports; "
            "--skip-postrun-reports is diagnostic/non-formal only"
        )
    if args.launch and not args.completion_preflight:
        raise SystemExit("--launch requires --completion-preflight")
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
