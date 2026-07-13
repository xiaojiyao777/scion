#!/usr/bin/env python3
"""Prepare or launch the warehouse direct-v3 Scion campaign."""

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
from typing import Any

import yaml

SCION_PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(SCION_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(SCION_PROJECT_DIR))

from scion.launcher.lifecycle import (
    CampaignCommandPlan,
    LauncherLifecyclePlan,
    PreCampaignGuard,
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

PROBLEM = "scion/problems/warehouse_delivery/problem.yaml"
PROBLEM_V1 = "scion/problems/warehouse_delivery/problem-v1.yaml"
PROTOCOL = "scion/problems/warehouse_delivery/protocol_prod.yaml"
SPLIT = "scion/problems/warehouse_delivery/split_manifest_prod.yaml"
SEEDS = "scion/problems/warehouse_delivery/seed_ledger.yaml"
ENV_VAR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
PREPARED_RUN_MANIFEST_SCHEMA = "scion.launcher_prepared_run_manifest.v1"
TASK_DOC = "scion/TASK.md"
CURRENT_STATE_DOC = "scion/docs/status/current-state.md"
ANALYSIS_HANDOFF_DOC = "scion/docs/operations/postrun-analysis-handoff.md"

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


def _preflight_parameter_search_disabled(
    repo_root: Path,
    *spec_paths: str,
) -> None:
    """Reject hidden post-promotion search in the formal direct runtime."""

    for spec_path in spec_paths:
        full_path = _resolve_source_path(repo_root, spec_path)
        if not full_path.exists():
            raise SystemExit(f"warehouse problem source not found: {full_path}")
        parameter_search = _load_yaml(full_path).get("parameter_search")
        enabled = (
            parameter_search.get("enabled")
            if isinstance(parameter_search, dict)
            else None
        )
        if enabled is not False:
            display_path = (
                str(full_path.relative_to(repo_root))
                if full_path.is_relative_to(repo_root)
                else str(full_path)
            )
            raise SystemExit(
                "Warehouse direct-v3 launcher requires "
                f"parameter_search.enabled=false in {display_path}"
            )


def _warehouse_guidance_manifest_fields(
    env: dict[str, object],
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    scion_dir = Path(env["SCION_DIR"])
    if str(scion_dir) not in sys.path:
        sys.path.insert(0, str(scion_dir))

    from scion.problems.warehouse_delivery.research_guidance import (  # noqa: PLC0415
        WAREHOUSE_ANALYSIS_INTENT,
        build_warehouse_measurement_opportunity_diagnostics,
        build_warehouse_legacy_research_focus,
        build_warehouse_research_guidance_contract,
    )
    from scion.research_guidance import (  # noqa: PLC0415
        GuidanceContext,
        research_guidance_contract_to_dict,
    )

    measurement_diagnostics = build_warehouse_measurement_opportunity_diagnostics(
        scion_dir,
        Path(env["PROBLEM_V1"]),
    )
    contract = build_warehouse_research_guidance_contract(
        GuidanceContext(
            problem_family="warehouse_delivery",
            metadata={"measurement_opportunity_diagnostics": measurement_diagnostics},
        ),
        measurement_diagnostics=measurement_diagnostics,
    )
    return (
        WAREHOUSE_ANALYSIS_INTENT,
        build_warehouse_legacy_research_focus(
            scion_dir,
            Path(env["PROBLEM_V1"]),
            measurement_diagnostics=measurement_diagnostics,
        ),
        research_guidance_contract_to_dict(contract),
    )


def _build_command(env: dict[str, object]) -> str:
    command = (
        f"{env['PY']} -m scion.cli.main run "
        f"--problem {env['PROBLEM']} "
        f"--protocol {env['PROTOCOL']} "
        f"--split {env['SPLIT']} "
        f"--seeds {env['SEEDS']} "
        f"--campaign-dir {env['CAMPAIGN_DIR']} "
        f"--rounds {env['ROUNDS']} "
        f"--time-limit-sec {env['TIME_LIMIT_SEC']}"
    )
    return command


def _write_launch_env(run_root: Path, env: dict[str, object]) -> None:
    ordered_keys = [
        "RUN_ROOT",
        "CAMPAIGN_DIR",
        "RESUME_FROM_CAMPAIGN",
        "RESUME_SNAPSHOT_MANIFEST_REF",
        "RESUME_COPIED_CAMPAIGN_STATUS_PRESENT",
        "RESUME_COPIED_CAMPAIGN_SUMMARY_PRESENT",
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
        "CONTROL_PAIR_KEY",
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
        "CONTROL_PAIR_KEY",
        "POSTRUN_REPORTS",
    ]
    command_lines = [
        '"$PY" -m scion.cli.main run \\',
        '  --problem "$PROBLEM" \\',
        '  --protocol "$PROTOCOL" \\',
        '  --split "$SPLIT" \\',
        '  --seeds "$SEEDS" \\',
        '  --campaign-dir "$CAMPAIGN_DIR" \\',
        '  --rounds "$ROUNDS" \\',
        '  --time-limit-sec "$TIME_LIMIT_SEC" \\',
        '  >> "$RUN_ROOT/run.log" 2>&1',
    ]
    command_plan = CampaignCommandPlan(
        command_log=command,
        exported_env_names=(
            "SCION_WAREHOUSE_DATA_ROOT",
            "SCION_PROBLEM_DATA_ROOT",
        ),
        command_body="\n".join(command_lines),
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
        postrun_report_stem_prefix="warehouse",
        command=command_plan,
        fallback_assignments=tuple((key, env[key]) for key in fallback_keys),
        exported_env_names=(
            "PYTHONPATH",
            "SCION_MODEL",
            "SCION_BASE_URL",
            "SCION_API_KEY",
            "PREPARED_RUN_MANIFEST",
        ),
        pre_campaign_guards=(
            PreCampaignGuard(
                failure_key="WAREHOUSE_DATA_ROOT_MISSING",
                condition=(
                    '[[ ! -d "$SCION_WAREHOUSE_DATA_ROOT/production/generated" '
                    '|| ! -d "$SCION_WAREHOUSE_DATA_ROOT/production/converted" ]]'
                ),
                detail="$SCION_WAREHOUSE_DATA_ROOT",
                status_fields={"warehouse_data_root_missing": True},
            ),
        ),
        preflight_failure_exit_code=PREFLIGHT_FAILURE_EXIT_CODE,
    )
    content = render_run_sh(plan)
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
    (
        analysis_intent,
        research_focus,
        research_guidance_contract,
    ) = _warehouse_guidance_manifest_fields(env)
    manifest = {
        "schema_version": PREPARED_RUN_MANIFEST_SCHEMA,
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
        "problem_family": "warehouse_delivery",
        "analysis_intent": analysis_intent,
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
    measurement = research_focus.get("measurement_opportunity_diagnostics")
    if isinstance(measurement, dict):
        readiness = measurement.get("measurement_readiness")
        if not isinstance(readiness, dict):
            readiness = {}
        lines.extend(
            [
                "- Measurement/runtime handoff:",
                f"  - Source: `{measurement.get('source')}`",
                f"  - Metric: `{measurement.get('metric')}`",
                f"  - Runtime model: `{measurement.get('runtime_model')}`",
                f"  - Pairing validity: `{measurement.get('pairing_validity')}`",
                "  - Screening MDE at 80% power: "
                f"`{measurement.get('screening_mde_at_power_80')}`",
                f"  - Readiness: `{readiness.get('status')}`",
                "  - Calibration evidence level: "
                f"`{readiness.get('calibration_evidence_level')}`",
                "  - Opportunity projection source: "
                f"`{measurement.get('opportunity_projection_source')}`",
                "  - Adapter payload schema: "
                f"`{measurement.get('adapter_payload_schema')}`",
                f"  - Summary: {measurement.get('summary')}",
            ]
        )
        calibration = measurement.get("calibration")
        if isinstance(calibration, dict):
            source_artifact = calibration.get("source_artifact")
            if isinstance(source_artifact, dict) and source_artifact:
                lines.append(
                    "  - Calibration source sha256: "
                    f"`{source_artifact.get('sha256')}`"
                )
            calibration_run = calibration.get("calibration_run")
            if isinstance(calibration_run, dict) and calibration_run:
                run_bits = []
                for key in (
                    "action",
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
                    lines.append("  - Calibration run: " + "; ".join(run_bits))
        transfer_risk = measurement.get("transfer_risk")
        if isinstance(transfer_risk, dict) and transfer_risk:
            lines.append("  - transfer_risk:")
            for key in (
                "risk_model",
                "latest_field_gate_pattern",
                "latest_formal_no_gain_pattern",
            ):
                if key in transfer_risk:
                    lines.append(f"    - {key}: {transfer_risk[key]}")
        required_diagnostics = measurement.get("required_diagnostics")
        if isinstance(required_diagnostics, dict) and required_diagnostics:
            lines.append("  - required_diagnostics:")
            for key in ("activation", "effect"):
                values = required_diagnostics.get(key)
                if isinstance(values, list) and values:
                    lines.append(f"    - {key}: " + ", ".join(map(str, values)))
        opportunity_diagnostics = measurement.get("opportunity_diagnostics")
        if isinstance(opportunity_diagnostics, list) and opportunity_diagnostics:
            lines.append("  - opportunity_diagnostics:")
            for item in opportunity_diagnostics:
                if not isinstance(item, dict):
                    continue
                dtype = item.get("diagnostic_type")
                family = item.get("mechanism_family")
                action = item.get("recommended_action")
                reason_codes = item.get("reason_codes")
                lines.append(
                    f"    - diagnostic_type={dtype}; "
                    f"mechanism_family={family}; recommended_action={action}"
                )
                if isinstance(reason_codes, list) and reason_codes:
                    lines.append(
                        "      reason_codes: " + ", ".join(map(str, reason_codes))
                    )
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

    report_stem = "warehouse_direct_v3"
    rebuild_prepared_handoff(run_root, report_stem=report_stem, strict=True)


def prepare(args: argparse.Namespace) -> tuple[Path, str | None]:
    repo_root = _repo_root()
    scion_dir = repo_root / "scion"
    _preflight_parameter_search_disabled(
        repo_root,
        args.problem,
        args.problem_v1,
    )
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
    try:
        resume_state = prepare_launcher_campaign(
            resume_from_campaign=args.resume_from_campaign,
            campaign_dir=campaign_dir,
            run_root=run_root,
        )
    except ResumePreparationError as exc:
        raise SystemExit(str(exc)) from exc
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
        "CONTROL_PAIR_KEY": control_pair_key,
        "GIT_COMMIT": _git_commit(repo_root),
        "GIT_RUNTIME_GUARD_PATHS": (
            "scion/scion :(exclude)scion/scion/tests "
            "scion/tools scion/problems/warehouse_delivery surrogate"
        ),
        "STARTED_UTC": started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    env.update(resume_state.env())

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
            f"SCION_BASE_URL={env['SCION_BASE_URL']}\n"
            f"SCION_WAREHOUSE_DATA_ROOT={env['SCION_WAREHOUSE_DATA_ROOT']}\n\n"
            f"PROPOSAL_RUNTIME_MODE={PROPOSAL_RUNTIME_MODE}\n"
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
            "Prepare a warehouse Scion campaign run root. "
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
            "a diagnostic/non-formal launch. Completion-preflight formal roots "
            "must start from a fresh campaign."
        ),
    )
    parser.add_argument(
        "--time-limit-sec",
        type=int,
        default=DEFAULT_TIME_LIMIT_SEC,
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
