"""Warehouse-owned research guidance provider."""

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
    RequiredMechanism,
    ResearchGuidanceContract,
    validate_research_guidance_contract,
)

WAREHOUSE_PROBLEM_FAMILY = "warehouse_delivery"
WAREHOUSE_RESEARCH_GUIDANCE_CONTRACT_SCHEMA = (
    "scion.warehouse_research_guidance_contract.v1"
)
WAREHOUSE_LEGACY_RESEARCH_FOCUS_SCHEMA = "scion.warehouse_research_focus.v1"

WAREHOUSE_ANALYSIS_INTENT = (
    "Warehouse champion-v2 continuous-improvement follow-up. Verify whether "
    "the accepted v0.4 positive research path can produce additional useful "
    "research without regressing promotion behavior; inspect branch transfer, "
    "prompt context, runtime/model explanation, and whether any plateau is real "
    "or a missed continuous-promotion opportunity."
)
WAREHOUSE_ACCEPTED_CHECKPOINT = (
    "Champion v2 promoted from the validation-transfer acceptance-contract "
    "run via split-preserving cost compression in pack_compatible_vehicles."
)
WAREHOUSE_CURRENT_QUESTION = (
    "Starting from champion v2, determine whether warehouse can produce "
    "additional useful research or whether the observed behavior is a real "
    "post-v2 plateau."
)
WAREHOUSE_DECISION_BOUNDARY = (
    "This focus is proposal/delegated-analysis guidance only and must not "
    "enter DecisionFeatures, Protocol gates, promotion input, or scheduler "
    "state."
)
WAREHOUSE_REQUIRED_EVIDENCE = (
    "preserve or improve promotion behavior relative to the v2 checkpoint",
    "inspect branch transfer from the v2 source campaign before judging plateau",
    "distinguish quality-blocked proposals from protocol-evaluated no-effect candidates",
    "interpret split-preserving cost-compression with cost_delta and improving-move telemetry, not split_delta alone",
    "explain fast completion through the declared warehouse runtime/problem model",
)
WAREHOUSE_DEFAULT_AVOID_DIRECTIONS = (
    "restart from baseline instead of champion v2",
    "treat proposal-quality blocks as plateau evidence",
    "treat fast completion as incidental noise rather than runtime-model evidence",
    "treat split_delta_sum==0 as no effect when cost_delta_sum is positive",
    "repeat unbounded merge_vehicles or swap_orders variants without validation-transfer risk controls",
    "launch a broad warehouse matrix before the focused v2 follow-up is analyzed",
)
WAREHOUSE_ADAPTER_OPPORTUNITY_FIELDS = (
    "transfer_risk",
    "required_diagnostics",
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
    "validation_case",
    "frozen_case",
    "holdout",
    "prompt_ratio",
    "llm_text",
)


class WarehouseResearchGuidanceProvider:
    """Build warehouse proposal-only research guidance."""

    def build_guidance_contract(
        self,
        context: GuidanceContext,
    ) -> ResearchGuidanceContract:
        measurement_diagnostics = _measurement_diagnostics_from_context(context)
        return build_warehouse_research_guidance_contract(
            context,
            measurement_diagnostics=measurement_diagnostics,
        )


def build_warehouse_research_guidance_contract(
    context: GuidanceContext | None = None,
    *,
    measurement_diagnostics: Mapping[str, Any] | None = None,
) -> ResearchGuidanceContract:
    """Return the typed warehouse guidance contract for generic rendering."""

    problem_family = WAREHOUSE_PROBLEM_FAMILY
    if context is not None and context.problem_family:
        problem_family = context.problem_family
    if problem_family != WAREHOUSE_PROBLEM_FAMILY:
        raise ValueError(
            "warehouse research guidance requires problem_family="
            f"{WAREHOUSE_PROBLEM_FAMILY!r}, got {problem_family!r}"
        )

    contract = ResearchGuidanceContract(
        schema_version=WAREHOUSE_RESEARCH_GUIDANCE_CONTRACT_SCHEMA,
        problem_family=problem_family,
        current_question=WAREHOUSE_CURRENT_QUESTION,
        required_mechanisms=(
            RequiredMechanism(
                mechanism_id="warehouse_champion_v2_checkpoint",
                category="research_continuity",
                description=WAREHOUSE_ACCEPTED_CHECKPOINT,
                required_observations=(
                    "champion_v2_source_campaign",
                    "promotion_behavior_relative_to_checkpoint",
                ),
                protected_items=("champion_v2", "pack_compatible_vehicles"),
                hypothesis_mechanism_binding="context_only",
            ),
            RequiredMechanism(
                mechanism_id="validation_transfer_continuation",
                category="warehouse_operator_followup",
                description=(
                    "Follow the accepted validation-transfer path with bounded "
                    "operator changes and explicit activation/effect diagnostics."
                ),
                required_observations=(
                    "operator_invocations",
                    "eligible_vehicle_or_order_groups_seen",
                    "accepted_moves",
                    "split_delta_sum",
                    "cost_delta_sum",
                    "improving_move_count",
                ),
                protected_items=(
                    "validation_transfer_acceptance_contract",
                    "split_preserving_cost_compression",
                ),
                hypothesis_mechanism_binding="context_only",
            ),
            RequiredMechanism(
                mechanism_id="warehouse_runtime_model_handoff",
                category="measurement_runtime",
                description=(
                    "Explain fast completion and low-SNR outcomes through the "
                    "declared warehouse runtime/problem model."
                ),
                required_observations=(
                    "runtime_model",
                    "pairing_validity",
                    "screening_mde_at_power_80",
                ),
                protected_items=("measurement_opportunity_diagnostics",),
                hypothesis_mechanism_binding="context_only",
            ),
        ),
        evidence_requirements=_warehouse_evidence_requirements(),
        avoid_rules=_warehouse_avoid_rules(),
        continuity_requirements=(
            ContinuityRequirement(
                requirement_id="continue_from_champion_v2",
                category="champion_lineage",
                description=(
                    "Start from champion v2 and inspect branch transfer before "
                    "calling the post-v2 behavior a plateau."
                ),
                related_ids=(
                    "warehouse_champion_v2_checkpoint",
                    "validation_transfer_continuation",
                ),
            ),
        ),
        guidance_blocks=(
            GuidanceBlock(
                block_id="warehouse_prepared_followup_focus",
                category="proposal_focus",
                title="Champion-v2 warehouse follow-up",
                lines=(
                    WAREHOUSE_ACCEPTED_CHECKPOINT,
                    WAREHOUSE_CURRENT_QUESTION,
                    "Treat quality-blocked, infra-only, or screened-only outcomes as insufficient plateau evidence.",
                    "Tie any split-preserving cost compression claim to cost_delta_sum and improving_move_count, not split_delta_sum alone.",
                ),
            ),
            GuidanceBlock(
                block_id="warehouse_measurement_runtime_focus",
                category="measurement_runtime",
                title="Measurement/runtime interpretation",
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
    """Return the compatibility dict consumed by prepared manifests today."""

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
    """Build proposal-visible warehouse measurement/runtime guidance."""

    if str(scion_dir) not in sys.path:
        sys.path.insert(0, str(scion_dir))

    from scion.measurement.readiness import measurement_readiness_status  # noqa: PLC0415
    from scion.problem.bridge import load_problem_spec_v1_from_yaml  # noqa: PLC0415

    if not problem_v1.is_file():
        raise SystemExit(
            "Warehouse agentic launcher requires problem-v1 measurement "
            f"declaration: {problem_v1}"
        )

    spec = load_problem_spec_v1_from_yaml(problem_v1)
    measurement = spec.measurement
    readiness = measurement_readiness_status(spec)
    if readiness.status != "ready":
        raise SystemExit(
            "Warehouse measurement calibration is not launch-ready: "
            f"{readiness.reason_code}"
        )

    calibration_ref = str(measurement.calibration_ref or "").strip()
    calibration_path = _resolve_calibration_ref(spec.root_dir, calibration_ref)
    calibration_artifact = _read_calibration_artifact(calibration_path)
    power = _mapping_or_empty(calibration_artifact.get("protocol_power"))
    effect_scale = measurement.effect_scale
    practical_screen_delta = float(effect_scale.practical_delta_screen)
    mde_at_power_80 = float(readiness.mde_at_power_80 or 0.0)
    reason_codes = _warehouse_measurement_reason_codes(
        runtime_model=measurement.runtime_model,
        pairing_validity=measurement.pairing_validity,
        practical_screen_delta=practical_screen_delta,
        mde_at_power_80=mde_at_power_80,
    )
    recommended_min_seeds = _positive_int_or_none(power.get("recommended_min_seeds"))
    related_calibrations = _warehouse_related_calibrations(calibration_artifact)

    diagnostic: dict[str, Any] = {
        "schema_version": "warehouse_measurement_runtime_handoff.v1",
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
        "summary": _warehouse_measurement_summary(
            metric=effect_scale.metric,
            mde_at_power_80=mde_at_power_80,
            practical_screen_delta=practical_screen_delta,
        ),
        "reason_codes": reason_codes,
    }
    diagnostic.update(_warehouse_adapter_opportunity_projection(spec))
    if recommended_min_seeds is not None:
        diagnostic["recommended_min_seeds"] = recommended_min_seeds
    if related_calibrations:
        diagnostic["related_calibrations"] = related_calibrations
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


def _warehouse_evidence_requirements() -> tuple[EvidenceRequirement, ...]:
    return (
        EvidenceRequirement(
            requirement_id="promotion_behavior_checkpoint",
            category="champion_continuity",
            description=WAREHOUSE_REQUIRED_EVIDENCE[0],
            mechanism_ids=("warehouse_champion_v2_checkpoint",),
            required_fields=("promotion_behavior", "checkpoint_comparison"),
        ),
        EvidenceRequirement(
            requirement_id="branch_transfer_before_plateau",
            category="research_continuity",
            description=WAREHOUSE_REQUIRED_EVIDENCE[1],
            mechanism_ids=("warehouse_champion_v2_checkpoint",),
            required_fields=("source_campaign_transfer", "plateau_evidence_kind"),
        ),
        EvidenceRequirement(
            requirement_id="quality_block_vs_protocol_effect",
            category="proposal_quality_boundary",
            description=WAREHOUSE_REQUIRED_EVIDENCE[2],
            mechanism_ids=("validation_transfer_continuation",),
            protected_items=("proposal_quality_blocks", "protocol_evaluated_candidates"),
            required_fields=("quality_block_status", "protocol_effect_status"),
        ),
        EvidenceRequirement(
            requirement_id="split_cost_telemetry_interpretation",
            category="measurement_telemetry",
            description=WAREHOUSE_REQUIRED_EVIDENCE[3],
            mechanism_ids=("validation_transfer_continuation",),
            required_fields=("split_delta_sum", "cost_delta_sum", "improving_move_count"),
        ),
        EvidenceRequirement(
            requirement_id="runtime_model_interpretation",
            category="measurement_runtime",
            description=WAREHOUSE_REQUIRED_EVIDENCE[4],
            mechanism_ids=("warehouse_runtime_model_handoff",),
            required_fields=("runtime_model", "pairing_validity", "completion_explanation"),
        ),
    )


def _warehouse_avoid_rules() -> tuple[AvoidRule, ...]:
    return tuple(
        AvoidRule(
            rule_id=_avoid_rule_id(index, description),
            category="warehouse_prepared_focus",
            description=description,
            applies_to=(
                "warehouse_champion_v2_checkpoint",
                "validation_transfer_continuation",
            ),
        )
        for index, description in enumerate(WAREHOUSE_DEFAULT_AVOID_DIRECTIONS, start=1)
    )


def _avoid_rule_id(index: int, description: str) -> str:
    words = [
        "".join(character for character in word.lower() if character.isalnum())
        for word in description.split()
    ]
    slug = "_".join(word for word in words if word)[:48].strip("_")
    return f"avoid_{index}_{slug or 'warehouse_pattern'}"


def _measurement_summary(
    measurement_diagnostics: Mapping[str, Any] | None,
) -> MeasurementGuidanceSummary:
    metric_names = ["subcategory_splits", "total_cost"]
    summary = (
        "Use warehouse measurement/runtime handoff as proposal guidance only; "
        "interpret split and cost effects together."
    )
    limitations = [
        "proposal-only measurement summary",
        "excluded from DecisionFeatures",
        "validation and frozen case details remain hidden",
    ]
    if measurement_diagnostics:
        metric = str(measurement_diagnostics.get("metric") or "").strip()
        if metric and metric not in metric_names:
            metric_names.append(metric)
        summary = str(measurement_diagnostics.get("summary") or summary)
        runtime_model = str(measurement_diagnostics.get("runtime_model") or "").strip()
        pairing_validity = str(
            measurement_diagnostics.get("pairing_validity") or ""
        ).strip()
        if runtime_model:
            limitations.append(f"runtime_model={runtime_model}")
        if pairing_validity:
            limitations.append(f"pairing_validity={pairing_validity}")
        reason_codes = measurement_diagnostics.get("reason_codes")
        if isinstance(reason_codes, list) and reason_codes:
            limitations.append("reason_codes=" + ",".join(map(str, reason_codes)))
    return MeasurementGuidanceSummary(
        summary_id="warehouse_measurement_runtime_handoff",
        summary=summary,
        metric_names=tuple(metric_names),
        limitations=tuple(limitations),
    )


def _measurement_guidance_lines(
    measurement_diagnostics: Mapping[str, Any] | None,
) -> tuple[str, ...]:
    if not measurement_diagnostics:
        return (
            "Use the warehouse runtime/problem model before treating fast completion as plateau evidence.",
            "Measurement diagnostics remain proposal-only and excluded from DecisionFeatures.",
        )
    metric = measurement_diagnostics.get("metric")
    runtime_model = measurement_diagnostics.get("runtime_model")
    pairing_validity = measurement_diagnostics.get("pairing_validity")
    mde = measurement_diagnostics.get("screening_mde_at_power_80")
    summary = measurement_diagnostics.get("summary")
    return (
        f"Metric: {metric}",
        f"Runtime model: {runtime_model}",
        f"Pairing validity: {pairing_validity}",
        f"Screening MDE at 80% power: {mde}",
        f"Summary: {summary}",
    )


def _warehouse_adapter_opportunity_projection(spec: Any) -> dict[str, Any]:
    """Project problem-owned warehouse follow-up diagnostics into launch focus."""

    from scion.problem.loader import load_problem_adapter  # noqa: PLC0415

    adapter = load_problem_adapter(spec)
    hook = getattr(adapter, "render_problem_measurement_diagnostics", None)
    if not callable(hook):
        raise SystemExit(
            "Warehouse agentic launcher requires adapter measurement "
            "follow-up diagnostics"
        )
    payload = hook()
    if not isinstance(payload, Mapping):
        raise SystemExit(
            "Warehouse adapter measurement follow-up diagnostics must be a mapping"
        )
    redacted = _redact_warehouse_adapter_opportunity_payload(dict(payload))
    if not isinstance(redacted, Mapping):
        raise SystemExit("Warehouse adapter measurement diagnostics invalid")
    projection: dict[str, Any] = {
        "opportunity_projection_source": (
            "problem_adapter.render_problem_measurement_diagnostics"
        ),
        "adapter_payload_schema": str(redacted.get("schema_version") or "").strip(),
    }
    for field in WAREHOUSE_ADAPTER_OPPORTUNITY_FIELDS:
        value = redacted.get(field)
        if value not in ("", None, [], {}, ()):
            projection[field] = value
    missing = [
        field
        for field in WAREHOUSE_ADAPTER_OPPORTUNITY_FIELDS
        if projection.get(field) in ("", None, [], {}, ())
    ]
    if missing:
        raise SystemExit(
            "Warehouse adapter measurement follow-up diagnostics missing fields: "
            + ", ".join(missing)
        )
    return projection


def _redact_warehouse_adapter_opportunity_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        projected: dict[str, Any] = {}
        for key, child in value.items():
            key_text = str(key)
            if not _warehouse_adapter_key_allowed(key_text):
                continue
            redacted = _redact_warehouse_adapter_opportunity_payload(child)
            if redacted not in ("", None, [], {}, ()):
                projected[key_text] = redacted
        return projected
    if isinstance(value, (list, tuple)):
        projected_items = [
            _redact_warehouse_adapter_opportunity_payload(item) for item in value
        ]
        return [
            item
            for item in projected_items
            if item not in ("", None, [], {}, ())
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
        raise SystemExit(f"Warehouse calibration artifact must be a JSON object: {path}")
    return payload


def _calibration_handoff(
    *,
    calibration_artifact: Mapping[str, Any],
    calibration_ref: str,
    calibration_path: Path,
    n_pairs: int,
) -> dict[str, Any]:
    calibration_run = _compact_calibration_run(
        calibration_artifact.get("calibration_run")
    )
    payload: dict[str, Any] = {
        "schema": calibration_artifact.get("schema"),
        "ref": calibration_ref,
        "path": str(calibration_path),
        "calibrated_at": calibration_artifact.get("calibrated_at"),
        "n_pairs": n_pairs,
        "decision_features_excluded": calibration_artifact.get(
            "decision_features_excluded"
        ),
        "calibration_run_action": calibration_run.get("action"),
    }
    source_artifact = _compact_source_artifact(
        calibration_artifact.get("source_artifact")
    )
    if source_artifact:
        payload["source_artifact"] = source_artifact
    if calibration_run:
        payload["calibration_run"] = calibration_run
    return {
        key: value
        for key, value in payload.items()
        if value not in ("", None, [], {}, ())
    }


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


def _warehouse_related_calibrations(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    related = artifact.get("related_calibrations")
    if not isinstance(related, list):
        return []
    items: list[dict[str, Any]] = []
    for item in related:
        if not isinstance(item, dict):
            continue
        payload = {
            "action": str(item.get("action") or ""),
            "n_pairs": item.get("n_pairs"),
            "mde_at_power_80": item.get("mde_at_power_80"),
        }
        items.append(
            {
                key: value
                for key, value in payload.items()
                if value not in ("", None)
            }
        )
    return items


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
            f"Warehouse screening is low-power for raw {metric} effects below "
            "the measured MDE; interpret split-preserving cost compression "
            "against the A/A noise floor and current-run runtime evidence."
        )
    return (
        f"Warehouse screening MDE is within the declared practical {metric} delta; "
        "interpret effects against the measured A/A noise floor."
    )
