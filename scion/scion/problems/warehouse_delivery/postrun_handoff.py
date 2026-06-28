"""Warehouse-owned prepared postrun handoff validators."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from scion.problems.warehouse_delivery.research_guidance import (
    WAREHOUSE_DEFAULT_AVOID_DIRECTIONS,
    WAREHOUSE_REQUIRED_EVIDENCE,
)


WAREHOUSE_REQUIRED_EVIDENCE_TOKENS = (
    ("promotion behavior",),
    ("branch transfer",),
    ("quality-blocked", "protocol-evaluated"),
    ("cost_delta", "split_delta"),
    ("fast completion", "runtime"),
)
WAREHOUSE_DEFAULT_AVOID_TOKENS = (
    "baseline",
    "proposal-quality",
    "fast completion",
    "split_delta_sum==0",
    "broad warehouse matrix",
)
WAREHOUSE_REQUIRED_MEASUREMENT_REASON_CODES = frozenset(
    (
        "WAREHOUSE_MDE_EXCEEDS_PRACTICAL_DELTA",
        "TRAJECTORY_DIVERGENT_LOW_SNR",
    )
)
WAREHOUSE_FOLLOWUP_REQUIREMENT_KEYS = (
    "warehouse_v2_checkpoint_handoff",
    "warehouse_continuous_plateau_question",
    "warehouse_required_evidence_handoff",
    "warehouse_default_avoid_handoff",
    "warehouse_decision_boundary_handoff",
)

CoverageItemFactory = Callable[[int, str], dict[str, Any]]
AddCheck = Callable[[str, bool, Any], None]


class WarehousePreparedHandoffReviewPort:
    """Warehouse-owned prepared-handoff checks and coverage."""

    problem_family = "warehouse_delivery"

    def prepared_contract_checks(
        self,
        manifest: Mapping[str, Any],
        *,
        manifest_run_root: str = "",
        local_run_root: Any = None,
        repo_dir: Any = None,
        scion_project_dir: Any = None,
    ) -> dict[str, dict[str, Any]]:
        del manifest_run_root, local_run_root, repo_dir, scion_project_dir
        checks: dict[str, dict[str, Any]] = {}

        def add_check(name: str, passed: bool, detail: Any = "") -> None:
            checks[name] = {"passed": bool(passed), "detail": detail}

        add_warehouse_prepared_handoff_checks(manifest, add_check)
        return checks

    def phase4_requirements(
        self,
        manifest: Mapping[str, Any],
        coverage_item: CoverageItemFactory,
    ) -> dict[str, Any]:
        return warehouse_prepared_handoff_phase4_requirements(
            manifest,
            coverage_item,
        )

    def prepared_prompt_context_signals(
        self,
        manifest: Mapping[str, Any],
        research_focus: Mapping[str, Any],
    ) -> dict[str, dict[str, Any]]:
        return warehouse_prepared_prompt_context_signals(
            manifest,
            research_focus,
        )


def add_warehouse_prepared_handoff_checks(
    manifest: Mapping[str, Any],
    add_check: AddCheck,
) -> None:
    """Append legacy-compatible warehouse prepared handoff checks."""

    if manifest.get("problem_family") != "warehouse_delivery":
        return

    research_focus = manifest.get("research_focus")
    focus_is_dict = isinstance(research_focus, dict)
    focus = research_focus if focus_is_dict else {}
    add_check(
        "warehouse_followup_handoff_present",
        focus_is_dict,
        "research_focus",
    )
    add_check(
        "warehouse_followup_handoff_report_only",
        focus.get("scope") == "report_only_prepared_handoff"
        and "DecisionFeatures" in str(focus.get("decision_boundary") or "")
        and manifest.get("decision_features_excluded") is True,
        {
            "scope": focus.get("scope"),
            "decision_features_excluded": manifest.get(
                "decision_features_excluded"
            ),
        },
    )

    checkpoint = str(focus.get("accepted_checkpoint") or "").lower()
    question = str(focus.get("current_question") or "").lower()
    add_check(
        "warehouse_followup_v2_checkpoint_present",
        "v2" in checkpoint and "v2" in question and "plateau" in question,
        {
            "accepted_checkpoint": focus.get("accepted_checkpoint"),
            "current_question": focus.get("current_question"),
        },
    )

    required_evidence = _string_items(focus.get("required_evidence"))
    required_text = "\n".join(required_evidence).lower()
    missing_required = [
        "/".join(tokens)
        for tokens in WAREHOUSE_REQUIRED_EVIDENCE_TOKENS
        if not all(token.lower() in required_text for token in tokens)
    ]
    add_check(
        "warehouse_followup_required_evidence_complete",
        not missing_required,
        {
            "count": len(required_evidence),
            "missing": missing_required,
        },
    )

    default_avoid = _string_items(focus.get("default_avoid_directions"))
    default_avoid_text = "\n".join(default_avoid).lower()
    missing_avoid = [
        token
        for token in WAREHOUSE_DEFAULT_AVOID_TOKENS
        if token.lower() not in default_avoid_text
    ]
    add_check(
        "warehouse_followup_default_avoid_complete",
        not missing_avoid,
        {
            "count": len(default_avoid),
            "missing": missing_avoid,
        },
    )

    measurement = focus.get("measurement_opportunity_diagnostics")
    measurement_is_dict = isinstance(measurement, dict)
    add_check(
        "warehouse_measurement_handoff_present",
        measurement_is_dict,
        "research_focus.measurement_opportunity_diagnostics",
    )
    if not isinstance(measurement, dict):
        measurement = {}
    add_check(
        "warehouse_measurement_handoff_report_only",
        measurement.get("proposal_visibility_only") is True
        and measurement.get("decision_features_excluded") is True,
        {
            "proposal_visibility_only": measurement.get(
                "proposal_visibility_only"
            ),
            "decision_features_excluded": measurement.get(
                "decision_features_excluded"
            ),
        },
    )
    add_check(
        "warehouse_measurement_handoff_mde_present",
        _positive_number(measurement.get("screening_mde_at_power_80"))
        and _positive_number(measurement.get("practical_screen_delta")),
        {
            "screening_mde_at_power_80": measurement.get(
                "screening_mde_at_power_80"
            ),
            "practical_screen_delta": measurement.get("practical_screen_delta"),
        },
    )
    readiness = _mapping_or_empty(measurement.get("measurement_readiness"))
    calibration = _mapping_or_empty(measurement.get("calibration"))
    source = str(measurement.get("source") or "")
    add_check(
        "warehouse_measurement_handoff_problem_owned_source",
        source == "problem_v1.measurement.calibration_ref"
        and readiness.get("status") == "ready"
        and readiness.get("reason_code") == "ok"
        and calibration.get("schema") == "scion.aa_noise_floor.v1"
        and calibration.get("decision_features_excluded") is True,
        {
            "source": source,
            "measurement_readiness_status": readiness.get("status"),
            "measurement_readiness_reason_code": readiness.get("reason_code"),
            "calibration_schema": calibration.get("schema"),
            "calibration_ref": calibration.get("ref"),
            "calibration_decision_features_excluded": calibration.get(
                "decision_features_excluded"
            ),
        },
    )
    reason_codes = set(_string_items(measurement.get("reason_codes")))
    missing_reason_codes = sorted(
        WAREHOUSE_REQUIRED_MEASUREMENT_REASON_CODES - reason_codes
    )
    add_check(
        "warehouse_measurement_handoff_reason_codes",
        not missing_reason_codes,
        {
            "required": sorted(WAREHOUSE_REQUIRED_MEASUREMENT_REASON_CODES),
            "missing": missing_reason_codes,
        },
    )


def warehouse_prepared_handoff_phase4_requirements(
    manifest: Mapping[str, Any],
    coverage_item: CoverageItemFactory,
) -> dict[str, Any]:
    """Return legacy Phase 4 warehouse handoff coverage payloads."""

    focus = _mapping_or_empty(manifest.get("research_focus"))
    measurement = _mapping_or_empty(focus.get("measurement_opportunity_diagnostics"))
    reason_codes = set(_string_items(measurement.get("reason_codes")))
    checkpoint = str(focus.get("accepted_checkpoint") or "")
    question = str(focus.get("current_question") or "")
    required_evidence = _string_items(focus.get("required_evidence"))
    default_avoid = _string_items(focus.get("default_avoid_directions"))
    boundary = str(focus.get("decision_boundary") or "")

    required_text = "\n".join(required_evidence)
    avoid_text = "\n".join(default_avoid)
    return {
        "warehouse_measurement_mde_handoff": coverage_item(
            int(
                _positive_number(measurement.get("screening_mde_at_power_80"))
                and _positive_number(measurement.get("practical_screen_delta"))
                and measurement.get("source")
                == "problem_v1.measurement.calibration_ref"
            ),
            "prepared_run_manifest warehouse measurement_opportunity_diagnostics problem-owned MDE/practical delta",
        ),
        "warehouse_low_snr_reason_handoff": coverage_item(
            int(not (WAREHOUSE_REQUIRED_MEASUREMENT_REASON_CODES - reason_codes)),
            "prepared_run_manifest warehouse measurement_opportunity_diagnostics reason_codes",
        ),
        "warehouse_v2_checkpoint_handoff": coverage_item(
            int("v2" in checkpoint.lower() and "v2" in question.lower()),
            "prepared_run_manifest warehouse research_focus accepted_checkpoint/current_question",
        ),
        "warehouse_continuous_plateau_question": coverage_item(
            int(
                (
                    "continuous" in question.lower()
                    or "additional useful research" in question.lower()
                )
                and "plateau" in question.lower()
            ),
            "prepared_run_manifest warehouse research_focus current_question",
        ),
        "warehouse_required_evidence_handoff": coverage_item(
            int(
                all(
                    all(token.lower() in required_text.lower() for token in tokens)
                    for tokens in WAREHOUSE_REQUIRED_EVIDENCE_TOKENS
                )
            ),
            "prepared_run_manifest warehouse research_focus required_evidence",
        ),
        "warehouse_default_avoid_handoff": coverage_item(
            int(
                all(
                    token.lower() in avoid_text.lower()
                    for token in WAREHOUSE_DEFAULT_AVOID_TOKENS
                )
            ),
            "prepared_run_manifest warehouse research_focus default_avoid_directions",
        ),
        "warehouse_decision_boundary_handoff": coverage_item(
            int(
                "decisionfeatures" in boundary.lower()
                and "protocol" in boundary.lower()
                and "promotion" in boundary.lower()
                and "scheduler" in boundary.lower()
            ),
            "prepared_run_manifest warehouse research_focus decision_boundary",
        ),
    }


def warehouse_prepared_prompt_context_signals(
    manifest: Mapping[str, Any],
    research_focus: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Build warehouse-owned prepared prompt/context readiness signals."""

    if manifest.get("problem_family") != "warehouse_delivery":
        return {}

    signals: dict[str, dict[str, Any]] = {}
    measurement = _mapping_or_empty(
        research_focus.get("measurement_opportunity_diagnostics")
    )
    readiness = _mapping_or_empty(measurement.get("measurement_readiness"))
    calibration = _mapping_or_empty(measurement.get("calibration"))
    transfer_risk = _mapping_or_empty(measurement.get("transfer_risk"))
    required_diagnostics = _mapping_or_empty(
        measurement.get("required_diagnostics")
    )
    opportunity_diagnostic_count = _sequence_count(
        measurement.get("opportunity_diagnostics")
    )
    measurable_opportunity_count = _sequence_count(
        measurement.get("measurable_opportunity_classes")
    )
    signals["warehouse_measurement_runtime_handoff"] = _signal(
        available=(
            bool(measurement)
            and measurement.get("source")
            == "problem_v1.measurement.calibration_ref"
            and measurement.get("proposal_visibility_only") is True
            and measurement.get("decision_features_excluded") is True
            and readiness.get("status") == "ready"
            and calibration.get("schema") == "scion.aa_noise_floor.v1"
            and bool(transfer_risk)
            and bool(required_diagnostics)
            and measurable_opportunity_count > 0
            and opportunity_diagnostic_count > 0
        ),
        required=True,
        source="prepared_run_manifest.research_focus.measurement_opportunity_diagnostics",
        detail={
            "schema_version": measurement.get("schema_version"),
            "opportunity_projection_source": measurement.get(
                "opportunity_projection_source"
            ),
            "metric": measurement.get("metric"),
            "runtime_model": measurement.get("runtime_model"),
            "pairing_validity": measurement.get("pairing_validity"),
            "screening_mde_at_power_80": measurement.get(
                "screening_mde_at_power_80"
            ),
            "measurement_readiness_status": readiness.get("status"),
            "calibration_schema": calibration.get("schema"),
            "transfer_risk_present": bool(transfer_risk),
            "required_diagnostics_present": bool(required_diagnostics),
            "measurable_opportunity_count": measurable_opportunity_count,
            "opportunity_diagnostic_count": opportunity_diagnostic_count,
        },
    )
    required_evidence = _string_items(research_focus.get("required_evidence"))
    avoid_items = _string_items(research_focus.get("default_avoid_directions"))
    signals["warehouse_v2_followup_question"] = _signal(
        available=bool(
            research_focus.get("accepted_checkpoint")
            and research_focus.get("current_question")
        ),
        required=True,
        source=(
            "prepared_run_manifest.research_focus.accepted_checkpoint "
            "and current_question"
        ),
        detail={
            "accepted_checkpoint_present": bool(
                research_focus.get("accepted_checkpoint")
            ),
            "current_question_present": bool(
                research_focus.get("current_question")
            ),
        },
    )
    signals["warehouse_required_evidence"] = _signal(
        available=bool(required_evidence),
        required=True,
        source="prepared_run_manifest.research_focus.required_evidence",
        detail={"count": len(required_evidence)},
    )
    signals["warehouse_default_avoid_directions"] = _signal(
        available=bool(avoid_items),
        required=True,
        source="prepared_run_manifest.research_focus.default_avoid_directions",
        detail={"count": len(avoid_items)},
    )
    return signals


def expected_warehouse_required_evidence() -> tuple[str, ...]:
    return tuple(WAREHOUSE_REQUIRED_EVIDENCE)


def expected_warehouse_default_avoid_directions() -> tuple[str, ...]:
    return tuple(WAREHOUSE_DEFAULT_AVOID_DIRECTIONS)


def _positive_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (float, int)) and value > 0


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _string_items(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _sequence_count(value: Any) -> int:
    if isinstance(value, (list, tuple)):
        return len(value)
    if isinstance(value, dict):
        return len(value)
    return 0


def _signal(
    *,
    available: bool,
    required: bool,
    source: Any,
    detail: Any,
) -> dict[str, Any]:
    return {
        "available": bool(available),
        "required": bool(required),
        "source": source,
        "detail": detail,
        "runtime_generated_after_launch": False,
    }
