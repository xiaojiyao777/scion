"""Manifest serialization for problem-neutral research guidance contracts."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

from scion.research_guidance.rendering import (
    RenderedResearchGuidance,
    render_research_guidance_contract,
)
from scion.research_guidance.schema import (
    AvoidRule,
    ContinuityRequirement,
    EvidenceRequirement,
    GuidanceBlock,
    GuidanceVisibility,
    MeasurementGuidanceSummary,
    RequiredMechanism,
    ResearchGuidanceContract,
    ResearchGuidanceValidationError,
    expected_research_guidance_rendered_paths,
    validate_research_guidance_contract,
)

RESEARCH_GUIDANCE_CONTRACT_MANIFEST_KEY = "research_guidance_contract"
RESEARCH_GUIDANCE_PROMPT_SCHEMA = "scion.launch_research_guidance_prompt.v1"
LEGACY_RESEARCH_FOCUS_ADAPTER_SCHEMA = (
    "scion.legacy_research_focus_contract_adapter.v1"
)


def research_guidance_contract_to_dict(
    contract: ResearchGuidanceContract,
) -> dict[str, Any]:
    """Serialize a valid contract to a JSON-safe manifest mapping."""

    validate_research_guidance_contract(contract)
    value = _json_safe(contract)
    if not isinstance(value, dict):  # pragma: no cover - dataclass guard.
        raise ResearchGuidanceValidationError("contract did not serialize to a dict")
    return value


def research_guidance_contract_from_dict(
    value: Mapping[str, Any],
) -> ResearchGuidanceContract:
    """Parse and validate a manifest contract mapping."""

    if not isinstance(value, Mapping):
        raise ResearchGuidanceValidationError("contract payload must be a mapping")
    contract = ResearchGuidanceContract(
        schema_version=_string(value.get("schema_version")),
        problem_family=_string(value.get("problem_family")),
        current_question=_string(value.get("current_question")),
        required_mechanisms=tuple(
            _required_mechanism(item)
            for item in _mapping_items(value.get("required_mechanisms"))
        ),
        evidence_requirements=tuple(
            _evidence_requirement(item)
            for item in _mapping_items(value.get("evidence_requirements"))
        ),
        avoid_rules=tuple(
            _avoid_rule(item) for item in _mapping_items(value.get("avoid_rules"))
        ),
        continuity_requirements=tuple(
            _continuity_requirement(item)
            for item in _mapping_items(value.get("continuity_requirements"))
        ),
        guidance_blocks=tuple(
            _guidance_block(item)
            for item in _mapping_items(value.get("guidance_blocks"))
        ),
        measurement_summary=_measurement_summary(value.get("measurement_summary")),
        decision_boundary=_string(value.get("decision_boundary")),
        visibility_policy=_string(value.get("visibility_policy"), "proposal_only"),
        proposal_visibility_only=value.get("proposal_visibility_only") is True,
        decision_features_excluded=value.get("decision_features_excluded") is True,
    )
    validate_research_guidance_contract(contract)
    return contract


def research_guidance_contract_from_manifest(
    manifest: Mapping[str, Any],
) -> tuple[ResearchGuidanceContract, str]:
    """Return the typed manifest contract, or a generic legacy adapter contract."""

    typed = manifest.get(RESEARCH_GUIDANCE_CONTRACT_MANIFEST_KEY)
    if isinstance(typed, Mapping):
        return research_guidance_contract_from_dict(typed), "typed_manifest"
    legacy = manifest.get("research_focus")
    if isinstance(legacy, Mapping):
        return legacy_research_focus_to_contract(
            legacy,
            problem_family=_string(manifest.get("problem_family"), "unknown"),
        ), "legacy_research_focus_adapter"
    raise ResearchGuidanceValidationError("missing research guidance contract")


def legacy_research_focus_to_contract(
    research_focus: Mapping[str, Any],
    *,
    problem_family: str,
) -> ResearchGuidanceContract:
    """Adapt an old manifest focus mapping without interpreting domain keys."""

    mechanism_ids = _string_tuple(research_focus.get("required_mechanism_ids"))
    target_intent_mechanism_ids = _string_tuple(
        research_focus.get("target_intent_required_mechanism_ids")
    )
    current_question = (
        _string(research_focus.get("current_question"))
        or _string(research_focus.get("next_required_direction"))
        or "Prepared research focus handoff."
    )
    decision_boundary = (
        _string(research_focus.get("decision_boundary"))
        or "Proposal guidance only; excluded from DecisionFeatures."
    )
    leaf_lines = tuple(_leaf_lines(research_focus)) or (
        "Legacy research focus had no non-empty leaf values.",
    )
    contract = ResearchGuidanceContract(
        schema_version=LEGACY_RESEARCH_FOCUS_ADAPTER_SCHEMA,
        problem_family=problem_family or "unknown",
        current_question=current_question,
        required_mechanisms=tuple(
            RequiredMechanism(
                mechanism_id=mechanism_id,
                category="legacy_required_mechanism",
                description=f"Legacy prepared mechanism id: {mechanism_id}",
            )
            for mechanism_id in mechanism_ids
        )
        + tuple(
            RequiredMechanism(
                mechanism_id=mechanism_id,
                category="legacy_target_intent_required_mechanism",
                description=(
                    "Legacy prepared target-intent mechanism id: "
                    f"{mechanism_id}"
                ),
                hypothesis_mechanism_binding="target_intent_required",
            )
            for mechanism_id in target_intent_mechanism_ids
        ),
        evidence_requirements=tuple(
            EvidenceRequirement(
                requirement_id=f"legacy_required_evidence_{index:02d}",
                category="legacy_required_evidence",
                description=text,
                mechanism_ids=mechanism_ids,
            )
            for index, text in enumerate(
                _string_tuple(research_focus.get("required_evidence")),
                start=1,
            )
        ),
        avoid_rules=tuple(
            AvoidRule(
                rule_id=f"legacy_avoid_{index:02d}_{_slug(text)}",
                category="legacy_default_avoid",
                description=text,
                applies_to=mechanism_ids,
            )
            for index, text in enumerate(
                _string_tuple(research_focus.get("default_avoid_directions")),
                start=1,
            )
        ),
        continuity_requirements=tuple(
            ContinuityRequirement(
                requirement_id=f"legacy_continuity_{index:02d}_{_slug(path)}",
                category="legacy_continuity",
                description=text,
                related_ids=mechanism_ids,
            )
            for index, (path, text) in enumerate(
                _continuity_leaf_items(research_focus),
                start=1,
            )
        ),
        guidance_blocks=(
            GuidanceBlock(
                block_id="legacy_research_focus_payload",
                category="legacy_manifest_adapter",
                title="Legacy prepared research focus payload",
                lines=leaf_lines,
            ),
        ),
        measurement_summary=_legacy_measurement_summary(research_focus),
        decision_boundary=decision_boundary,
    )
    validate_research_guidance_contract(contract)
    return contract


def render_prepared_research_guidance_from_manifest(
    manifest: Mapping[str, Any],
) -> tuple[ResearchGuidanceContract, RenderedResearchGuidance, str]:
    """Validate and render manifest guidance through the generic renderer."""

    contract, source = research_guidance_contract_from_manifest(manifest)
    rendered = render_research_guidance_contract(contract)
    return contract, rendered, source


def launch_research_guidance_payload(
    *,
    manifest_path: str | Path,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the proposal-only context payload for prepared guidance."""

    contract, rendered, source = render_prepared_research_guidance_from_manifest(
        manifest
    )
    legacy_focus = manifest.get("research_focus")
    if not isinstance(legacy_focus, Mapping):
        legacy_focus = {}
    contract_payload = research_guidance_contract_to_dict(contract)
    expected_paths = expected_research_guidance_rendered_paths(contract)
    return {
        "schema_version": RESEARCH_GUIDANCE_PROMPT_SCHEMA,
        "taint": "prepared_launch_research_guidance",
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
        "decision_input_policy": "excluded_from_decision_features",
        "source": "PREPARED_RUN_MANIFEST",
        "contract_source": source,
        "manifest_path": str(manifest_path),
        "problem_family": contract.problem_family,
        "analysis_intent": _string(manifest.get("analysis_intent")),
        "acceptance_focus": _string_list(manifest.get("acceptance_focus")),
        "contract_schema_version": contract.schema_version,
        "current_question": contract.current_question,
        "decision_boundary": contract.decision_boundary,
        "legacy_research_focus_schema_version": _string(
            legacy_focus.get("schema_version")
        ),
        "material_difference_requirement": _json_safe(
            legacy_focus.get("material_difference_requirement")
        ),
        "reviewed_mechanism_ids": _string_list(
            legacy_focus.get("reviewed_mechanism_ids")
        ),
        "suppressed_mechanism_ids": _string_list(
            legacy_focus.get("suppressed_mechanism_ids")
        ),
        "successor_opportunity_families": _string_list(
            legacy_focus.get("successor_opportunity_families")
        ),
        "default_avoid_directions": _string_list(
            legacy_focus.get("default_avoid_directions")
        ),
        "next_required_direction": _string(
            legacy_focus.get("next_required_direction")
        ),
        "required_evidence": [
            item["description"]
            for item in contract_payload.get("evidence_requirements", ())
            if isinstance(item, Mapping) and _string(item.get("description"))
        ],
        "evidence_requirements": contract_payload.get("evidence_requirements", []),
        "required_mechanism_contracts": contract_payload.get(
            "required_mechanisms",
            [],
        ),
        "target_intent_contracts": {
            str(key): _json_safe(value)
            for key, value in legacy_focus.items()
            if isinstance(key, str)
            and key.endswith("_target_intent")
            and value not in ("", None, [], {}, ())
        },
        "case_protection_requirements": _json_safe(
            legacy_focus.get("case_protection_requirements")
        ),
        "resume_continuity_requirements": _json_safe(
            legacy_focus.get("resume_continuity_requirements")
        ),
        "required_mechanism_ids": [
            mechanism.mechanism_id
            for mechanism in contract.required_mechanisms
            if mechanism.hypothesis_mechanism_binding == "required"
        ],
        "target_intent_required_mechanism_ids": [
            mechanism.mechanism_id
            for mechanism in contract.required_mechanisms
            if mechanism.hypothesis_mechanism_binding == "target_intent_required"
        ],
        "expected_rendered_paths": list(expected_paths),
        "rendered_paths": list(rendered.rendered_paths),
        "rendered_path_count": len(rendered.rendered_paths),
        "guidance_text": rendered.text,
        "guidance_text_sha256": hashlib.sha256(
            rendered.text.encode("utf-8")
        ).hexdigest(),
    }


def launch_research_guidance_payload_from_path(
    manifest_path: str | Path,
) -> dict[str, Any]:
    """Build launch guidance from a prepared manifest path, returning empty on miss."""

    path = str(manifest_path or "").strip()
    if not path:
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(manifest, Mapping):
        return {}
    try:
        return launch_research_guidance_payload(
            manifest_path=path,
            manifest=manifest,
        )
    except Exception:
        return {}


def launch_research_guidance_payload_from_env(
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return prepared launch guidance declared by the runtime environment."""

    source = os.environ if env is None else env
    manifest_path = str(
        source.get("PREPARED_RUN_MANIFEST")
        or source.get("SCION_PREPARED_RUN_MANIFEST")
        or ""
    ).strip()
    if not manifest_path:
        return {}
    return launch_research_guidance_payload_from_path(manifest_path)


def research_guidance_projection_summary(
    *,
    manifest_path: str | Path,
    manifest: Mapping[str, Any],
    schema_version: str,
    forbidden_tokens: Sequence[str] = (),
) -> dict[str, Any]:
    """Summarize schema and rendered-path coverage for manifest guidance."""

    problem_family = _string(manifest.get("problem_family"))
    base = {
        "schema_version": schema_version,
        "problem_family": problem_family,
        "manifest_path": str(manifest_path),
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "raw_prompt_excluded": True,
    }
    contract_present = isinstance(
        manifest.get(RESEARCH_GUIDANCE_CONTRACT_MANIFEST_KEY),
        Mapping,
    )
    legacy_present = isinstance(manifest.get("research_focus"), Mapping)
    try:
        contract, rendered, source = render_prepared_research_guidance_from_manifest(
            manifest
        )
        expected_paths = expected_research_guidance_rendered_paths(contract)
        rendered_paths = rendered.rendered_paths
        missing_paths = sorted(set(expected_paths) - set(rendered_paths))
        rendered_lower = rendered.text.lower()
        forbidden_present = [
            token for token in forbidden_tokens if token.lower() in rendered_lower
        ]
    except Exception as exc:
        return {
            **base,
            "available": False,
            "reason": "schema_invalid",
            "contract_present": contract_present,
            "legacy_research_focus_present": legacy_present,
            "contract_source": "missing",
            "schema_valid": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "visibility_policy": "",
            "proposal_visibility_only": False,
            "decision_features_excluded": False,
            "expected_rendered_paths": [],
            "rendered_paths": [],
            "missing_rendered_paths": [],
            "rendered_path_count": 0,
            "forbidden_prompt_tokens_present": [],
        }

    available = not missing_paths and not forbidden_present
    if missing_paths:
        reason = "missing_rendered_paths"
    elif forbidden_present:
        reason = "forbidden_prompt_tokens"
    else:
        reason = "ok"
    return {
        **base,
        "available": available,
        "reason": reason,
        "contract_present": contract_present,
        "legacy_research_focus_present": legacy_present,
        "contract_source": source,
        "schema_valid": True,
        "contract_schema_version": contract.schema_version,
        "visibility_policy": contract.visibility_policy,
        "proposal_visibility_only": contract.proposal_visibility_only,
        "decision_features_excluded": contract.decision_features_excluded,
        "expected_rendered_paths": list(expected_paths),
        "rendered_paths": list(rendered_paths),
        "missing_rendered_paths": missing_paths,
        "rendered_path_count": len(rendered_paths),
        "forbidden_prompt_tokens_present": forbidden_present,
    }


def _required_mechanism(value: Mapping[str, Any]) -> RequiredMechanism:
    return RequiredMechanism(
        mechanism_id=_string(value.get("mechanism_id")),
        category=_string(value.get("category")),
        description=_string(value.get("description")),
        required_observations=_string_tuple(value.get("required_observations")),
        protected_items=_string_tuple(value.get("protected_items")),
        hypothesis_mechanism_binding=_string(
            value.get("hypothesis_mechanism_binding"),
            "required",
        ),
        visibility=_visibility(value.get("visibility")),
    )


def _evidence_requirement(value: Mapping[str, Any]) -> EvidenceRequirement:
    return EvidenceRequirement(
        requirement_id=_string(value.get("requirement_id")),
        category=_string(value.get("category")),
        description=_string(value.get("description")),
        mechanism_ids=_string_tuple(value.get("mechanism_ids")),
        protected_items=_string_tuple(value.get("protected_items")),
        required_fields=_string_tuple(value.get("required_fields")),
        visibility=_visibility(value.get("visibility")),
    )


def _avoid_rule(value: Mapping[str, Any]) -> AvoidRule:
    return AvoidRule(
        rule_id=_string(value.get("rule_id")),
        category=_string(value.get("category")),
        description=_string(value.get("description")),
        applies_to=_string_tuple(value.get("applies_to")),
        visibility=_visibility(value.get("visibility")),
    )


def _continuity_requirement(value: Mapping[str, Any]) -> ContinuityRequirement:
    return ContinuityRequirement(
        requirement_id=_string(value.get("requirement_id")),
        category=_string(value.get("category")),
        description=_string(value.get("description")),
        related_ids=_string_tuple(value.get("related_ids")),
        visibility=_visibility(value.get("visibility")),
    )


def _guidance_block(value: Mapping[str, Any]) -> GuidanceBlock:
    return GuidanceBlock(
        block_id=_string(value.get("block_id")),
        category=_string(value.get("category")),
        title=_string(value.get("title")),
        lines=_string_tuple(value.get("lines")),
        visibility=_visibility(value.get("visibility")),
    )


def _measurement_summary(value: Any) -> MeasurementGuidanceSummary | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ResearchGuidanceValidationError(
            "measurement_summary must be a mapping or null"
        )
    return MeasurementGuidanceSummary(
        summary_id=_string(value.get("summary_id")),
        summary=_string(value.get("summary")),
        metric_names=_string_tuple(value.get("metric_names")),
        limitations=_string_tuple(value.get("limitations")),
        visibility=_visibility(value.get("visibility")),
    )


def _legacy_measurement_summary(
    research_focus: Mapping[str, Any],
) -> MeasurementGuidanceSummary | None:
    measurement = research_focus.get("measurement_opportunity_diagnostics")
    if not isinstance(measurement, Mapping):
        return None
    metric = _string(measurement.get("metric"))
    summary = _string(measurement.get("summary")) or (
        "Legacy measurement diagnostics are proposal-only and excluded from "
        "DecisionFeatures."
    )
    metric_names = (metric,) if metric else ()
    limitations = (
        "legacy manifest adapter",
        "proposal-only summary",
        "excluded from DecisionFeatures",
    )
    return MeasurementGuidanceSummary(
        summary_id="legacy_measurement_diagnostics",
        summary=summary,
        metric_names=metric_names,
        limitations=limitations,
    )


def _visibility(value: Any) -> GuidanceVisibility:
    if not isinstance(value, Mapping):
        return GuidanceVisibility()
    return GuidanceVisibility(
        visibility_policy=_string(value.get("visibility_policy"), "proposal_only"),
        proposal_visibility_only=value.get("proposal_visibility_only", True) is True,
        decision_features_excluded=value.get("decision_features_excluded", True)
        is True,
    )


def _mapping_items(value: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _string_tuple(value: Any) -> tuple[str, ...]:
    return tuple(_string_list(value))


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        candidates: Sequence[Any] = (value,)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        candidates = value
    else:
        candidates = ()
    return [text for item in candidates if (text := _string(item))]


def _string(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return {
            field.name: _json_safe(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, Mapping):
        return {str(key): _json_safe(child) for key, child in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_json_safe(child) for child in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _leaf_lines(value: Any, *, prefix: str = "") -> list[str]:
    if isinstance(value, Mapping):
        lines: list[str] = []
        for key in sorted(value):
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            lines.extend(_leaf_lines(value[key], prefix=child_prefix))
        return lines
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        lines = []
        for index, child in enumerate(value):
            child_prefix = f"{prefix}[{index}]"
            lines.extend(_leaf_lines(child, prefix=child_prefix))
        return lines
    if value in ("", None, [], {}, ()):
        return []
    rendered = json.dumps(value, sort_keys=True, default=str)
    return [f"{prefix}: {rendered}"]


def _continuity_leaf_items(value: Mapping[str, Any]) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for line in _leaf_lines(value):
        path, _, text = line.partition(": ")
        if "continuity" in path.lower() and text.strip():
            items.append((path, text.strip()))
    return items


def _slug(value: str) -> str:
    chars = [char.lower() if char.isalnum() else "_" for char in value]
    return "_".join(part for part in "".join(chars).split("_") if part)[:48] or "item"
