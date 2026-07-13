"""Warehouse-owned, direct-V3 research guidance."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from scion.research_guidance import (
    AvoidRule,
    ContinuityRequirement,
    EvidenceRequirement,
    GuidanceBlock,
    GuidanceContext,
    MeasurementGuidanceSummary,
    ResearchGuidanceContract,
    validate_research_guidance_contract,
)


WAREHOUSE_PROBLEM_FAMILY = "warehouse_delivery"
WAREHOUSE_RESEARCH_GUIDANCE_CONTRACT_SCHEMA = (
    "scion.warehouse_research_guidance_contract.v2"
)
WAREHOUSE_LEGACY_RESEARCH_FOCUS_SCHEMA = "scion.warehouse_research_focus.v1"

WAREHOUSE_ANALYSIS_INTENT = (
    "Use the current warehouse champion source, branch history, and safe aggregate "
    "measurement evidence to choose an algorithmic improvement on either the "
    "order-level or vehicle-level research surface."
)
WAREHOUSE_ACCEPTED_CHECKPOINT = (
    "The current champion source is the implementation starting point; its "
    "algorithmic choices are evidence, not a prescribed next mechanism."
)
WAREHOUSE_CURRENT_QUESTION = (
    "What source-grounded change on the order-level or vehicle-level surface can "
    "improve the lexicographic warehouse objective while preserving feasibility?"
)
WAREHOUSE_DECISION_BOUNDARY = (
    "This problem-owned context supports hypothesis formation only and remains "
    "outside DecisionFeatures, Protocol decisions, promotion input, and scheduler state."
)
WAREHOUSE_REQUIRED_EVIDENCE = (
    "connect the proposed algorithmic effect to subcategory_splits or total_cost",
    "ground the idea in the current champion source and complete branch evidence",
    "preserve assignment completeness and synchronization",
    "preserve capacity, region, category, pickup, hazard, and locked-order feasibility",
    "use runtime and operator diagnostics as optional explanation when informative",
)
WAREHOUSE_DEFAULT_AVOID_DIRECTIONS = (
    "model the warehouse assignment problem as routing or distance optimization",
    "preselect an operator family before inspecting the current source",
    "move orders without an explicit path to the lexicographic objective",
    "trade away assignment feasibility for an apparent objective improvement",
    "treat optional telemetry as a proposal gate or as a substitute for objective evidence",
)
WAREHOUSE_ADAPTER_OPPORTUNITY_FIELDS = (
    "objective_model",
    "optional_observability",
    "measurable_opportunity_classes",
    "opportunity_diagnostics",
    "policy",
)
WAREHOUSE_ADAPTER_FORBIDDEN_KEY_FRAGMENTS = (
    "pair_evidence",
    "pair_rows",
    "raw_pair",
    "raw_calibration",
    "calibration_pair",
    "evaluation_case",
    "prompt_ratio",
    "llm_text",
)


class WarehouseResearchGuidanceProvider:
    """Build open, problem-owned warehouse hypothesis context."""

    def build_guidance_contract(
        self,
        context: GuidanceContext,
    ) -> ResearchGuidanceContract:
        return build_warehouse_research_guidance_contract(
            context,
            measurement_diagnostics=_measurement_diagnostics_from_context(context),
        )


def build_warehouse_research_guidance_contract(
    context: GuidanceContext | None = None,
    *,
    measurement_diagnostics: Mapping[str, Any] | None = None,
) -> ResearchGuidanceContract:
    """Return warehouse facts without selecting the next mechanism."""

    problem_family = (
        context.problem_family if context is not None else WAREHOUSE_PROBLEM_FAMILY
    )
    if problem_family != WAREHOUSE_PROBLEM_FAMILY:
        raise ValueError(
            "warehouse research guidance requires problem_family="
            f"{WAREHOUSE_PROBLEM_FAMILY!r}, got {problem_family!r}"
        )

    contract = ResearchGuidanceContract(
        schema_version=WAREHOUSE_RESEARCH_GUIDANCE_CONTRACT_SCHEMA,
        problem_family=problem_family,
        current_question=WAREHOUSE_CURRENT_QUESTION,
        required_mechanisms=(),
        evidence_requirements=(
            EvidenceRequirement(
                requirement_id="algorithmic_objective_path",
                category="problem_reasoning",
                description=WAREHOUSE_REQUIRED_EVIDENCE[0],
                required_fields=("subcategory_splits", "total_cost"),
            ),
            EvidenceRequirement(
                requirement_id="current_source_grounding",
                category="source_grounding",
                description=WAREHOUSE_REQUIRED_EVIDENCE[1],
                required_fields=("champion_source", "branch_evidence"),
            ),
            EvidenceRequirement(
                requirement_id="warehouse_feasibility_model",
                category="problem_feasibility",
                description=(
                    f"{WAREHOUSE_REQUIRED_EVIDENCE[2]}; "
                    f"{WAREHOUSE_REQUIRED_EVIDENCE[3]}"
                ),
                required_fields=("assignment", "vehicle_order_ids", "feasibility"),
            ),
        ),
        avoid_rules=tuple(
            AvoidRule(
                rule_id=f"warehouse_fact_{index}",
                category="problem_model",
                description=description,
            )
            for index, description in enumerate(
                WAREHOUSE_DEFAULT_AVOID_DIRECTIONS,
                start=1,
            )
        ),
        continuity_requirements=(
            ContinuityRequirement(
                requirement_id="current_champion_is_starting_source",
                category="source_continuity",
                description=WAREHOUSE_ACCEPTED_CHECKPOINT,
            ),
        ),
        guidance_blocks=(
            GuidanceBlock(
                block_id="warehouse_open_research_surfaces",
                category="research_surfaces",
                title="Open warehouse research surfaces",
                lines=(
                    "order_level: move or exchange orders when the source supports a credible objective path",
                    "vehicle_level: merge, split, resize, or rebuild assignments when the source supports a credible objective path",
                    "Neither surface nor operator family is preferred in advance.",
                ),
            ),
            GuidanceBlock(
                block_id="warehouse_optional_observability",
                category="observability",
                title="Optional algorithm observability",
                lines=(
                    WAREHOUSE_REQUIRED_EVIDENCE[4],
                    "Useful fields may include operator_invocations, accepted_moves, split_delta_sum, cost_delta_sum, and improving_move_count.",
                    "Absence of those fields does not block an otherwise valid algorithmic idea.",
                ),
            ),
            GuidanceBlock(
                block_id="warehouse_measurement_context",
                category="measurement",
                title="Safe aggregate measurement context",
                lines=_measurement_guidance_lines(measurement_diagnostics),
            ),
        ),
        measurement_summary=_measurement_summary(measurement_diagnostics),
        decision_boundary=WAREHOUSE_DECISION_BOUNDARY,
    )
    validate_research_guidance_contract(contract)
    return contract


def build_warehouse_legacy_research_focus(
    scion_dir: str | Path,
    problem_v1: str | Path,
    *,
    measurement_diagnostics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the prepared-manifest compatibility shape with V3 content."""

    if measurement_diagnostics is None:
        measurement_diagnostics = build_warehouse_measurement_opportunity_diagnostics(
            Path(scion_dir),
            Path(problem_v1),
        )
    build_warehouse_research_guidance_contract(
        GuidanceContext(problem_family=WAREHOUSE_PROBLEM_FAMILY),
        measurement_diagnostics=measurement_diagnostics,
    )
    focus = {
        "schema_version": WAREHOUSE_LEGACY_RESEARCH_FOCUS_SCHEMA,
        "scope": "report_only_prepared_handoff",
        "accepted_checkpoint": WAREHOUSE_ACCEPTED_CHECKPOINT,
        "current_question": WAREHOUSE_CURRENT_QUESTION,
        "required_evidence": list(WAREHOUSE_REQUIRED_EVIDENCE),
        "default_avoid_directions": list(WAREHOUSE_DEFAULT_AVOID_DIRECTIONS),
        "decision_boundary": WAREHOUSE_DECISION_BOUNDARY,
        "measurement_opportunity_diagnostics": measurement_diagnostics,
    }
    return json.loads(json.dumps(focus))


def build_warehouse_measurement_opportunity_diagnostics(
    scion_dir: Path,
    problem_v1: Path,
) -> dict[str, Any]:
    """Build complete safe aggregate measurement and opportunity context."""

    if str(scion_dir) not in sys.path:
        sys.path.insert(0, str(scion_dir))

    from scion.measurement.consumer_view import measurement_consumer_view  # noqa: PLC0415
    from scion.problem.bridge import load_problem_spec_v1_from_yaml  # noqa: PLC0415

    if not problem_v1.is_file():
        raise SystemExit(f"Warehouse problem declaration not found: {problem_v1}")

    spec = load_problem_spec_v1_from_yaml(problem_v1)
    measurement = spec.measurement
    measurement_view = measurement_consumer_view(spec)
    if measurement_view.readiness_status != "ready":
        raise SystemExit(
            "Warehouse measurement declaration is not ready: "
            f"{measurement_view.readiness_reason_code}"
        )

    calibration_ref = str(measurement.calibration_ref or "").strip()
    calibration_path = _resolve_calibration_ref(spec.root_dir, calibration_ref)
    calibration_artifact = _read_calibration_artifact(calibration_path)
    practical_screen_delta = float(measurement_view.practical_delta_screen or 0.0)
    practical_validate_delta = float(
        measurement_view.practical_delta_validate or 0.0
    )
    mde_at_power_80 = float(measurement_view.mde_at_power_80 or 0.0)

    diagnostic: dict[str, Any] = {
        "schema_version": "warehouse_measurement_opportunity.v2",
        "source": "problem_v1.measurement.calibration_ref",
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
        "metric": measurement_view.effect_metric,
        "unit": measurement_view.effect_unit,
        "runtime_model": measurement_view.runtime_model,
        "pairing_validity": measurement_view.pairing_validity,
        "practical_screen_delta": practical_screen_delta,
        "practical_validate_delta": practical_validate_delta,
        "screening_mde_at_power_80": mde_at_power_80,
        "measurement_readiness": measurement_view.to_readiness_status_payload(),
        "calibration": _calibration_handoff(
            calibration_artifact=calibration_artifact,
            calibration_ref=calibration_ref,
            calibration_path=calibration_path,
            n_pairs=measurement_view.n_pairs,
        ),
        "summary": _warehouse_measurement_summary(
            metric=measurement_view.effect_metric,
            mde_at_power_80=mde_at_power_80,
            practical_screen_delta=practical_screen_delta,
        ),
        "reason_codes": _warehouse_measurement_reason_codes(
            runtime_model=measurement_view.runtime_model,
            pairing_validity=measurement_view.pairing_validity,
            practical_screen_delta=practical_screen_delta,
            mde_at_power_80=mde_at_power_80,
        ),
    }
    diagnostic.update(_warehouse_adapter_opportunity_projection(spec))
    return diagnostic


def _measurement_diagnostics_from_context(
    context: GuidanceContext,
) -> Mapping[str, Any] | None:
    diagnostics = context.metadata.get("measurement_opportunity_diagnostics")
    if isinstance(diagnostics, Mapping):
        return diagnostics
    scion_dir = context.metadata.get("scion_dir")
    problem_v1 = context.metadata.get("problem_v1")
    if scion_dir and problem_v1:
        return build_warehouse_measurement_opportunity_diagnostics(
            Path(str(scion_dir)),
            Path(str(problem_v1)),
        )
    return None


def _measurement_summary(
    diagnostics: Mapping[str, Any] | None,
) -> MeasurementGuidanceSummary:
    summary = (
        str(diagnostics.get("summary") or "").strip()
        if diagnostics
        else "No aggregate measurement handoff was supplied."
    )
    return MeasurementGuidanceSummary(
        summary_id="warehouse_safe_aggregate_measurement",
        summary=summary,
        metric_names=("subcategory_splits", "total_cost"),
        limitations=(
            "hypothesis context only",
            "excluded from DecisionFeatures",
            "contains aggregate measurement facts and no evaluation-case details",
        ),
    )


def _measurement_guidance_lines(
    diagnostics: Mapping[str, Any] | None,
) -> tuple[str, ...]:
    if not diagnostics:
        return (
            "No aggregate measurement handoff was supplied.",
            "Choose the algorithmic direction from source and branch evidence.",
        )
    return (
        f"Metric: {diagnostics.get('metric')}",
        f"Unit: {diagnostics.get('unit')}",
        f"Runtime model: {diagnostics.get('runtime_model')}",
        f"Pairing validity: {diagnostics.get('pairing_validity')}",
        f"Practical screen delta: {diagnostics.get('practical_screen_delta')}",
        f"Practical formal delta: {diagnostics.get('practical_validate_delta')}",
        f"Screening MDE at 80% power: {diagnostics.get('screening_mde_at_power_80')}",
        f"Summary: {diagnostics.get('summary')}",
    )


def _warehouse_adapter_opportunity_projection(spec: Any) -> dict[str, Any]:
    from scion.problem.loader import load_problem_adapter  # noqa: PLC0415

    adapter = load_problem_adapter(spec)
    payload = adapter.render_problem_measurement_diagnostics()
    if not isinstance(payload, Mapping):
        raise SystemExit("Warehouse adapter research diagnostics must be a mapping")
    safe_payload = _redact_warehouse_adapter_opportunity_payload(dict(payload))
    projection: dict[str, Any] = {
        "opportunity_projection_source": (
            "problem_adapter.render_problem_measurement_diagnostics"
        ),
        "adapter_payload_schema": str(safe_payload.get("schema_version") or ""),
    }
    for field in WAREHOUSE_ADAPTER_OPPORTUNITY_FIELDS:
        value = safe_payload.get(field)
        if value not in ("", None, [], {}, ()):
            projection[field] = value
    missing = [
        field
        for field in WAREHOUSE_ADAPTER_OPPORTUNITY_FIELDS
        if projection.get(field) in ("", None, [], {}, ())
    ]
    if missing:
        raise SystemExit(
            "Warehouse adapter research diagnostics missing fields: "
            + ", ".join(missing)
        )
    return projection


def _redact_warehouse_adapter_opportunity_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _redact_warehouse_adapter_opportunity_payload(child)
            for key, child in value.items()
            if _warehouse_adapter_key_allowed(str(key))
        }
    if isinstance(value, (list, tuple)):
        return [
            _redact_warehouse_adapter_opportunity_payload(item) for item in value
        ]
    return value


def _warehouse_adapter_key_allowed(key: str) -> bool:
    lowered = key.lower()
    return not any(
        fragment in lowered
        for fragment in WAREHOUSE_ADAPTER_FORBIDDEN_KEY_FRAGMENTS
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
        raise SystemExit(
            f"unable to read warehouse calibration artifact {path}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"Warehouse calibration artifact must be an object: {path}")
    return payload


def _calibration_handoff(
    *,
    calibration_artifact: Mapping[str, Any],
    calibration_ref: str,
    calibration_path: Path,
    n_pairs: int,
) -> dict[str, Any]:
    source = calibration_artifact.get("source_artifact")
    source_artifact = dict(source) if isinstance(source, Mapping) else {}
    return {
        "schema": calibration_artifact.get("schema"),
        "ref": calibration_ref,
        "path": str(calibration_path),
        "calibrated_at": calibration_artifact.get("calibrated_at"),
        "n_pairs": n_pairs,
        "decision_features_excluded": calibration_artifact.get(
            "decision_features_excluded"
        ),
        "source_artifact": {
            key: source_artifact.get(key)
            for key in ("ref", "sha256")
            if source_artifact.get(key) not in ("", None)
        },
    }


def _warehouse_measurement_reason_codes(
    *,
    runtime_model: str,
    pairing_validity: str,
    practical_screen_delta: float,
    mde_at_power_80: float,
) -> list[str]:
    reason_codes: list[str] = []
    if mde_at_power_80 > practical_screen_delta:
        reason_codes.append("WAREHOUSE_MDE_EXCEEDS_PRACTICAL_DELTA")
    if pairing_validity == "trajectory_divergent":
        reason_codes.append("TRAJECTORY_DIVERGENT_LOW_SNR")
    if runtime_model == "comparative":
        reason_codes.append("WAREHOUSE_COMPARATIVE_RUNTIME_REPORT_ONLY")
    return reason_codes


def _warehouse_measurement_summary(
    *,
    metric: str,
    mde_at_power_80: float,
    practical_screen_delta: float,
) -> str:
    if mde_at_power_80 > practical_screen_delta:
        return (
            f"Aggregate {metric} effects below the measured screening MDE are "
            "hard to distinguish from the current noise floor; use this as "
            "interpretive context, not as a proposal constraint."
        )
    return (
        f"The measured screening MDE is within the declared practical {metric} "
        "delta; interpret observed effects against the aggregate noise floor."
    )
