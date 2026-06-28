"""Validation for prepared prompt-context readiness artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from scion.postrun.handoff.prepared_prompt_context import (
    RESEARCH_FOCUS_PROMPT_SUMMARY_SCHEMA,
    RESEARCH_FOCUS_PROJECTION_SUMMARY_SCHEMA,
    research_focus_prompt_summary,
    research_focus_projection_summary,
)
from scion.postrun.handoff.prompt_context_readiness import (
    ACTIVE_SUBJECT_CODE_CONSTRAINT_PROMPT_MARKERS,
    ACTIVE_SUBJECT_CODE_CONSTRAINT_PROVIDER_SUMMARY_SCHEMA,
    LAUNCH_RESEARCH_FOCUS_PROMPT_MARKERS,
    PROMPT_CONTEXT_READINESS_SCHEMA,
    active_subject_code_constraints_provider_payload_summary,
    default_prepared_handoff_ports_by_family,
    resolve_problem_v1_path,
)


DEFAULT_REPO_DIR = Path(__file__).resolve().parents[4]


def check_prepared_prompt_context_readiness(
    root: Path | str,
    *,
    repo_dir: Path | str | None = None,
    ports_by_family: Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Validate prepared prompt-context readiness artifacts for launch checks."""

    run_root = Path(root).expanduser().resolve()
    resolved_repo_dir = _resolve_repo_dir(repo_dir)
    port_registry = (
        dict(ports_by_family)
        if ports_by_family is not None
        else default_prepared_handoff_ports_by_family()
    )
    readiness_dir = run_root / "prepared_handoff" / "prompt_context_readiness"
    paths = sorted(readiness_dir.glob("*.json"))
    manifest_path = run_root / "prepared_run_manifest.v1.json"
    manifest = _read_json(manifest_path)
    manifest_dict = manifest if isinstance(manifest, dict) else {}
    detail: dict[str, Any] = {
        "directory": str(readiness_dir),
        "artifacts": [path.name for path in paths],
        "artifact_summaries": [],
        "provider_prompt_scope": "prepared_renderer_summary_not_live_provider_prompt",
        "raw_provider_prompt_rendered": False,
        "failures": [],
    }
    failures: list[dict[str, Any]] = []
    if not paths:
        failures.append({"artifact": None, "reason": "missing_prompt_context_readiness"})

    for path in paths:
        payload = _read_json(path)
        detail["artifact_summaries"].append(
            _prompt_context_artifact_summary(
                payload,
                artifact=path.name,
                ports_by_family=port_registry,
            )
        )
        failures.extend(
            {"artifact": path.name, **failure}
            for failure in _prompt_context_artifact_failures(
                payload,
                root=run_root,
                manifest_path=manifest_path,
                manifest=manifest_dict,
                repo_dir=resolved_repo_dir,
                ports_by_family=port_registry,
            )
        )

    live_markers = {
        "source_markers": {
            name: _repo_path_contains(resolved_repo_dir, relative_path, marker)
            for name, (relative_path, marker) in (
                LAUNCH_RESEARCH_FOCUS_PROMPT_MARKERS.items()
            )
        },
        "launch_markers": {
            "prepared_manifest_exists": (
                run_root / "prepared_run_manifest.v1.json"
            ).is_file(),
            "launch_env_assignment": _path_contains(
                run_root / "launch.env",
                "PREPARED_RUN_MANIFEST=",
            ),
            "run_sh_exports_manifest": _path_contains(
                run_root / "run.sh",
                "PREPARED_RUN_MANIFEST",
            )
            and _path_contains(run_root / "run.sh", "export ")
            and _path_contains(run_root / "run.sh", "scion.cli.main run"),
        },
    }
    family = str(manifest_dict.get("problem_family") or "")
    spec = _problem_prompt_bridge_spec(family, port_registry)
    if spec is not None:
        active_subject_markers = {
            **ACTIVE_SUBJECT_CODE_CONSTRAINT_PROMPT_MARKERS,
            **dict(spec.active_subject_provider_markers),
        }
        live_markers[spec.active_subject_marker_group_name] = {
            name: _repo_path_contains(resolved_repo_dir, relative_path, marker)
            for name, (relative_path, marker) in active_subject_markers.items()
        }
        live_markers[spec.measurement_marker_group_name] = {
            name: _repo_path_contains(resolved_repo_dir, relative_path, marker)
            for name, (relative_path, marker) in (
                spec.measurement_source_markers.items()
            )
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


def _prompt_context_artifact_summary(
    payload: Any,
    *,
    artifact: str,
    ports_by_family: Mapping[str, Any],
) -> dict[str, Any]:
    """Return compact operator-facing prompt-context evidence scope."""

    if not isinstance(payload, dict):
        return {
            "artifact": artifact,
            "valid_payload": False,
            "reason": "invalid_json_payload",
        }
    readiness = payload.get("readiness")
    readiness_dict = readiness if isinstance(readiness, dict) else {}
    signals = payload.get("signals")
    signals_dict = signals if isinstance(signals, dict) else {}
    focus_bridge = _mapping_or_empty(
        signals_dict.get("prepared_research_focus_prompt_bridge")
    )
    focus_detail = _mapping_or_empty(focus_bridge.get("detail"))
    focus_summary = _mapping_or_empty(focus_detail.get("prompt_summary"))
    family = str(payload.get("problem_family") or "")
    spec = _problem_prompt_bridge_spec(family, ports_by_family)
    code_signal_name = spec.active_subject_signal_name if spec is not None else ""
    code_bridge = _mapping_or_empty(signals_dict.get(code_signal_name))
    code_detail = _mapping_or_empty(code_bridge.get("detail"))
    code_summary = _mapping_or_empty(code_detail.get("code_prompt_summary"))
    return {
        "artifact": artifact,
        "valid_payload": True,
        "problem_family": family,
        "ready_for_launch_prompt_audit": readiness_dict.get(
            "ready_for_launch_prompt_audit"
        ),
        "missing_required": readiness_dict.get("missing_required"),
        "raw_provider_prompt_rendered": payload.get("raw_provider_prompt_rendered"),
        "provider_prompt_scope": (
            "live_provider_prompt"
            if payload.get("raw_provider_prompt_rendered") is True
            else "prepared_renderer_summary_not_live_provider_prompt"
        ),
        "prepared_focus_prompt_summary": {
            "available": focus_summary.get("available"),
            "problem_family": focus_summary.get("problem_family"),
            "contract_present": focus_summary.get("contract_present"),
            "contract_source": focus_summary.get("contract_source"),
            "schema_valid": focus_summary.get("schema_valid"),
            "contract_schema_version": focus_summary.get(
                "contract_schema_version"
            ),
            "proposal_visibility_only": focus_summary.get(
                "proposal_visibility_only"
            ),
            "expected_rendered_path_count": len(
                focus_summary.get("expected_rendered_paths") or []
            ),
            "rendered_required_path_count": focus_summary.get(
                "rendered_required_path_count"
            ),
            "missing_rendered_paths": focus_summary.get("missing_rendered_paths"),
            "guidance_text_digest_present": focus_summary.get(
                "guidance_text_digest_present"
            ),
        },
        "active_subject_code_constraints_summary": {
            "available": code_summary.get("available"),
            "prompt_section_present": code_summary.get("prompt_section_present"),
            "subject_id": code_summary.get("subject_id"),
            "constraint_ids_all_present": code_summary.get(
                "constraint_ids_all_present"
            ),
            "forbidden_patterns_all_present": code_summary.get(
                "forbidden_patterns_all_present"
            ),
        },
    }


def _prompt_context_artifact_failures(
    payload: Any,
    *,
    root: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    repo_dir: Path,
    ports_by_family: Mapping[str, Any],
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
    failures.extend(
        _research_focus_prompt_summary_failures(
            detail_dict.get("prompt_summary"),
            manifest_path=manifest_path,
            manifest=manifest,
        )
    )

    projection = signals_dict.get("prepared_research_focus_projection")
    if not isinstance(projection, dict):
        failures.append({"reason": "prepared_focus_projection_missing"})
    else:
        if projection.get("required") is not True:
            failures.append(
                {
                    "reason": "prepared_focus_projection_not_required",
                    "required": projection.get("required"),
                }
            )
        if projection.get("available") is not True:
            failures.append(
                {
                    "reason": "prepared_focus_projection_unavailable",
                    "available": projection.get("available"),
                }
            )
        if projection.get("runtime_generated_after_launch") is True:
            failures.append({"reason": "prepared_focus_projection_runtime_generated"})
        failures.extend(
            _research_focus_projection_summary_failures(
                projection.get("detail"),
                manifest_path=manifest_path,
                manifest=manifest,
            )
        )

    family = str(manifest.get("problem_family") or "")
    spec = _problem_prompt_bridge_spec(family, ports_by_family)
    if spec is not None:
        bridge_signal_name = spec.active_subject_signal_name
        failure_prefix = spec.active_subject_failure_prefix
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
            failures.extend(
                _active_subject_code_constraints_provider_payload_failures(
                    code_detail_dict.get("provider_payload"),
                    root=root,
                    manifest=manifest,
                    spec=spec,
                    repo_dir=repo_dir,
                    failure_prefix=failure_prefix,
                )
            )
            failures.extend(
                _active_subject_code_constraints_prompt_summary_failures(
                    code_detail_dict.get("code_prompt_summary"),
                    root=root,
                    manifest=manifest,
                    spec=spec,
                    repo_dir=repo_dir,
                    failure_prefix=failure_prefix,
                )
            )

        diagnostics_signal_name = spec.measurement_signal_name
        failure_prefix = spec.measurement_failure_prefix
        diagnostics_bridge = signals_dict.get(diagnostics_signal_name)
        if not isinstance(diagnostics_bridge, dict):
            failures.append({"reason": f"{failure_prefix}_missing"})
        else:
            if diagnostics_bridge.get("required") is not True:
                failures.append(
                    {
                        "reason": f"{failure_prefix}_not_required",
                        "required": diagnostics_bridge.get("required"),
                    }
                )
            if diagnostics_bridge.get("available") is not True:
                failures.append(
                    {
                        "reason": f"{failure_prefix}_unavailable",
                        "available": diagnostics_bridge.get("available"),
                    }
                )
            if diagnostics_bridge.get("runtime_generated_after_launch") is True:
                failures.append({"reason": f"{failure_prefix}_runtime_generated"})
            diagnostics_detail = diagnostics_bridge.get("detail")
            diagnostics_detail_dict = (
                diagnostics_detail if isinstance(diagnostics_detail, dict) else {}
            )
            markers = diagnostics_detail_dict.get("source_markers")
            markers_dict = markers if isinstance(markers, dict) else {}
            missing_markers = [
                name
                for name, available in markers_dict.items()
                if available is not True
            ]
            if not markers_dict or missing_markers:
                failures.append(
                    {
                        "reason": f"{failure_prefix}_source_markers_missing",
                        "missing": missing_markers or ["<all>"],
                    }
                )
            failures.extend(
                _problem_measurement_diagnostics_prompt_summary_failures(
                    diagnostics_detail_dict.get("diagnostic_summary"),
                    root=root,
                    manifest=manifest,
                    spec=spec,
                    repo_dir=repo_dir,
                    failure_prefix=failure_prefix,
                )
            )

    return failures


def _research_focus_prompt_summary_failures(
    value: Any,
    *,
    manifest_path: Path,
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    payload = value if isinstance(value, dict) else {}
    expected = research_focus_prompt_summary(
        manifest_path=manifest_path,
        manifest=manifest,
    )
    failures: list[dict[str, Any]] = []
    if not payload:
        return [{"reason": "prepared_focus_prompt_summary_missing"}]

    boundary_expectations = {
        "schema_version": RESEARCH_FOCUS_PROMPT_SUMMARY_SCHEMA,
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "raw_prompt_excluded": True,
        "available": True,
        "reason": "ok",
        "forbidden_prompt_tokens_present": [],
        "missing_rendered_paths": [],
    }
    for field, expected_value in boundary_expectations.items():
        if payload.get(field) != expected_value:
            failures.append(
                {
                    "reason": "prepared_focus_prompt_summary_field_mismatch",
                    "field": field,
                    "expected": expected_value,
                    "actual": payload.get(field),
                }
            )

    if expected.get("available") is not True:
        failures.append(
            {
                "reason": "prepared_focus_live_prompt_summary_unavailable",
                "expected": expected,
            }
        )
        return failures

    compare_fields = (
        "problem_family",
        "manifest_path",
        "contract_present",
        "legacy_research_focus_present",
        "contract_source",
        "schema_valid",
        "contract_schema_version",
        "visibility_policy",
        "proposal_visibility_only",
        "expected_rendered_paths",
        "rendered_paths",
        "launch_focus_schema_present",
        "launch_focus_taint_present",
        "prompt_section_present",
        "compact_prompt_value_present",
        "launch_research_focus_key_present",
        "decision_features_exclusion_present",
        "manifest_path_present",
        "contract_schema_present",
        "guidance_text_digest_present",
        "rendered_required_paths",
        "rendered_required_path_count",
        "required_rendered_path_count",
    )
    for field in compare_fields:
        if payload.get(field) != expected.get(field):
            failures.append(
                {
                    "reason": "prepared_focus_prompt_summary_field_mismatch",
                    "field": field,
                    "expected": expected.get(field),
                    "actual": payload.get(field),
                }
            )
    return failures


def _research_focus_projection_summary_failures(
    value: Any,
    *,
    manifest_path: Path,
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    payload = value if isinstance(value, dict) else {}
    expected = research_focus_projection_summary(
        manifest_path=manifest_path,
        manifest=manifest,
    )
    failures: list[dict[str, Any]] = []
    if not payload:
        return [{"reason": "prepared_focus_projection_detail_missing"}]

    boundary_expectations = {
        "schema_version": RESEARCH_FOCUS_PROJECTION_SUMMARY_SCHEMA,
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "raw_prompt_excluded": True,
        "available": True,
        "reason": "ok",
        "schema_valid": True,
        "proposal_visibility_only": True,
        "missing_rendered_paths": [],
        "forbidden_prompt_tokens_present": [],
    }
    for field, expected_value in boundary_expectations.items():
        if payload.get(field) != expected_value:
            failures.append(
                {
                    "reason": "prepared_focus_projection_field_mismatch",
                    "field": field,
                    "expected": expected_value,
                    "actual": payload.get(field),
                }
            )

    if expected.get("available") is not True:
        failures.append(
            {
                "reason": "prepared_focus_projection_live_unavailable",
                "expected": expected,
            }
        )
        return failures

    compare_fields = (
        "problem_family",
        "manifest_path",
        "contract_present",
        "legacy_research_focus_present",
        "contract_source",
        "schema_valid",
        "contract_schema_version",
        "visibility_policy",
        "proposal_visibility_only",
        "expected_rendered_paths",
        "rendered_paths",
        "missing_rendered_paths",
        "rendered_path_count",
        "forbidden_prompt_tokens_present",
    )
    for field in compare_fields:
        if payload.get(field) != expected.get(field):
            failures.append(
                {
                    "reason": "prepared_focus_projection_field_mismatch",
                    "field": field,
                    "expected": expected.get(field),
                    "actual": payload.get(field),
                }
            )
    return failures


def _problem_measurement_diagnostics_prompt_summary_failures(
    value: Any,
    *,
    root: Path,
    manifest: dict[str, Any],
    spec: Any,
    repo_dir: Path,
    failure_prefix: str,
) -> list[dict[str, Any]]:
    payload = value if isinstance(value, dict) else {}
    problem_v1 = resolve_problem_v1_path(
        root=root,
        manifest=manifest,
        repo_dir=repo_dir,
        spec=spec,
    )
    expected = spec.measurement_prompt_summary(problem_v1_path=problem_v1)
    failures: list[dict[str, Any]] = []
    if not payload:
        return [{"reason": f"{failure_prefix}_diagnostic_summary_missing"}]

    boundary_expectations = {
        "schema_version": spec.measurement_prompt_summary_schema,
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "raw_payload_excluded": True,
        "raw_prompt_excluded": True,
        "available": True,
        "reason": "ok",
        "forbidden_prompt_tokens_present": [],
    }
    for field, expected_value in boundary_expectations.items():
        if payload.get(field) != expected_value:
            failures.append(
                {
                    "reason": f"{failure_prefix}_diagnostic_summary_field_mismatch",
                    "field": field,
                    "expected": expected_value,
                    "actual": payload.get(field),
                }
            )

    if expected.get("available") is not True:
        failures.append(
            {
                "reason": f"{failure_prefix}_live_diagnostic_summary_unavailable",
                "expected": expected,
            }
        )
        return failures

    for field in spec.measurement_prompt_summary_compare_fields:
        if payload.get(field) != expected.get(field):
            failures.append(
                {
                    "reason": f"{failure_prefix}_diagnostic_summary_field_mismatch",
                    "field": field,
                    "expected": expected.get(field),
                    "actual": payload.get(field),
                }
            )
    for field in spec.measurement_prompt_summary_positive_fields:
        if _int_or_zero(payload.get(field)) <= 0:
            failures.append({"reason": f"{failure_prefix}_diagnostic_summary_empty"})
            break
    return failures


def _active_subject_code_constraints_provider_payload_failures(
    value: Any,
    *,
    root: Path,
    manifest: dict[str, Any],
    spec: Any,
    repo_dir: Path,
    failure_prefix: str,
) -> list[dict[str, Any]]:
    payload = value if isinstance(value, dict) else {}
    expected = active_subject_code_constraints_provider_payload_summary(
        root=root,
        manifest=manifest,
        repo_dir=repo_dir,
        spec=spec,
    )
    failures: list[dict[str, Any]] = []
    if not payload:
        return [{"reason": f"{failure_prefix}_provider_payload_missing"}]

    boundary_expectations = {
        "schema_version": ACTIVE_SUBJECT_CODE_CONSTRAINT_PROVIDER_SUMMARY_SCHEMA,
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "raw_payload_excluded": True,
        "available": True,
    }
    for field, expected_value in boundary_expectations.items():
        if payload.get(field) != expected_value:
            failures.append(
                {
                    "reason": f"{failure_prefix}_provider_payload_field_mismatch",
                    "field": field,
                    "expected": expected_value,
                    "actual": payload.get(field),
                }
            )

    if expected.get("available") is not True:
        failures.append(
            {
                "reason": f"{failure_prefix}_live_provider_payload_unavailable",
                "expected": expected,
            }
        )
        return failures

    compare_fields = (
        "problem_family",
        "surface",
        "version",
        "subject_id",
        "constraint_count",
        "object_model_hint_count",
        "api_contract_count",
        "forbidden_pattern_count",
        "total_guidance_item_count",
    )
    for field in compare_fields:
        if payload.get(field) != expected.get(field):
            failures.append(
                {
                    "reason": f"{failure_prefix}_provider_payload_field_mismatch",
                    "field": field,
                    "expected": expected.get(field),
                    "actual": payload.get(field),
                }
            )
    if _int_or_zero(payload.get("total_guidance_item_count")) <= 0:
        failures.append({"reason": f"{failure_prefix}_provider_payload_empty"})
    return failures


def _active_subject_code_constraints_prompt_summary_failures(
    value: Any,
    *,
    root: Path,
    manifest: dict[str, Any],
    spec: Any,
    repo_dir: Path,
    failure_prefix: str,
) -> list[dict[str, Any]]:
    payload = value if isinstance(value, dict) else {}
    problem_v1 = resolve_problem_v1_path(
        root=root,
        manifest=manifest,
        repo_dir=repo_dir,
        spec=spec,
    )
    expected = spec.active_subject_prompt_summary(problem_v1_path=problem_v1)
    failures: list[dict[str, Any]] = []
    if not payload:
        return [{"reason": f"{failure_prefix}_code_prompt_summary_missing"}]

    boundary_expectations = {
        "schema_version": spec.active_subject_prompt_summary_schema,
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "raw_payload_excluded": True,
        "available": True,
        "reason": "ok",
    }
    for field, expected_value in boundary_expectations.items():
        if payload.get(field) != expected_value:
            failures.append(
                {
                    "reason": f"{failure_prefix}_code_prompt_summary_field_mismatch",
                    "field": field,
                    "expected": expected_value,
                    "actual": payload.get(field),
                }
            )

    if expected.get("available") is not True:
        failures.append(
            {
                "reason": f"{failure_prefix}_live_code_prompt_summary_unavailable",
                "expected": expected,
            }
        )
        return failures

    for field in spec.active_subject_prompt_summary_compare_fields:
        if payload.get(field) != expected.get(field):
            failures.append(
                {
                    "reason": f"{failure_prefix}_code_prompt_summary_field_mismatch",
                    "field": field,
                    "expected": expected.get(field),
                    "actual": payload.get(field),
                }
            )
    for field, suffix in spec.active_subject_prompt_summary_positive_checks:
        if _int_or_zero(payload.get(field)) <= 0:
            failures.append({"reason": f"{failure_prefix}_code_prompt_summary_{suffix}"})
    return failures


def _problem_prompt_bridge_spec(
    family: str,
    ports_by_family: Mapping[str, Any],
) -> Any | None:
    port = ports_by_family.get(family)
    if port is None:
        return None
    return port.prompt_bridge_spec()


def _resolve_repo_dir(repo_dir: Path | str | None) -> Path:
    if repo_dir is None:
        return DEFAULT_REPO_DIR
    return Path(repo_dir).expanduser().resolve()


def _repo_path_contains(repo_dir: Path, relative_path: str, marker: str) -> bool:
    return _path_contains(repo_dir / relative_path, marker)


def _path_contains(path: Path, marker: str) -> bool:
    try:
        return marker in path.read_text(encoding="utf-8")
    except OSError:
        return False


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        import json

        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _manifest_commit(manifest: dict[str, Any]) -> Any:
    git = manifest.get("git")
    if not isinstance(git, dict):
        return None
    return git.get("commit")


def _manifest_model_name(manifest: dict[str, Any]) -> Any:
    model = manifest.get("model")
    if not isinstance(model, dict):
        return None
    return model.get("name")


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
