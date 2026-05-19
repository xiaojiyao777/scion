"""Schema and draft-payload preview tools."""

from __future__ import annotations

from typing import Any, Mapping

from pydantic import ValidationError

from scion.contract.gate import ContractGate
from scion.core.models import (
    HypothesisProposal,
    MechanismChange,
    PatchFileChange,
    PatchProposal,
    mechanism_changes,
    patch_file_changes,
)
from scion.proposal.schemas import HypothesisProposalInput, PatchProposalInput
from scion.proposal.tools.base import _BaseReadOnlyTool
from scion.proposal.tools.models import (
    DraftHypothesisInput,
    DraftPatchInput,
    ProposalExposureLevel,
    ProposalObservation,
    ProposalToolContext,
    ProposalToolFailureCode,
    ProposalToolPermission,
    SchemaPreviewInput,
)
from scion.proposal.tools.previews.common import (
    _COMPACT_FEEDBACK_LIST_ITEMS,
    _NONEMPTY_SEQUENCE_NOVELTY_FIELDS,
    _PREVIEW_CHECK_DETAIL_CHARS,
    _PREVIEW_FAILURE_REASON_CHARS,
    _PREVIEW_MAX_CHECKS,
    _SEMANTIC_SIGNATURE_SCALAR_STRING_CHARS,
    _artifact_id,
    _champion_version,
    _compact_preview_value,
    _contract_gate,
    _contract_problem_spec,
    _drop_internal_preview_objects,
    _module_classes,
    _module_level_functions,
    _patch_path_error,
    _patch_preview_summary,
)
from scion.proposal.tools.previews.contract import (
    _checks_payload,
    _first_failure,
)
from scion.proposal.tools.previews.permissions import (
    _forced_hypothesis_violation,
    _forced_surface_constraint_payload,
)
from scion.proposal.tools.surface import (
    _coerce_compact_list,
    _drop_empty_items,
    _surface_for_hypothesis,
)
from scion.proposal.tools.utils import _attr, _limit_text, _model_payload, _strip_forbidden_value
from scion.runtime.telemetry_guard import (
    EXPECTED_TELEMETRY_CATEGORIES,
    declared_mechanism_runtime_probes,
    declared_surface_telemetry_fields,
    normalize_expected_telemetry,
)

class DraftHypothesisTool(_BaseReadOnlyTool):
    name = "proposal.draft_hypothesis"
    input_schema = DraftHypothesisInput
    permission = ProposalToolPermission.DRAFT_PATCH
    max_result_chars = 24000

    def call(
        self,
        args: DraftHypothesisInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        hypothesis = _hypothesis_from_input(args)
        forced_violation = _forced_hypothesis_violation(context, hypothesis)
        if forced_violation is not None:
            return self._error(
                context,
                failure_code=ProposalToolFailureCode.SCHEMA_ERROR,
                summary="Hypothesis draft violates forced research-surface constraint.",
                structured_payload={
                    "passed": False,
                    "failure_reason": forced_violation,
                    "forced_surface_constraint": _forced_surface_constraint_payload(
                        context
                    ),
                    "hypothesis": _model_payload(hypothesis),
                    "workspace_materialized": False,
                },
                repair_hint="Draft only the forced surface/action/target.",
            )
        schema_result = _hypothesis_schema_preview(context, hypothesis)
        if not schema_result["passed"]:
            return self._error(
                context,
                failure_code=ProposalToolFailureCode.SCHEMA_ERROR,
                summary="Hypothesis draft failed schema preview.",
                structured_payload=schema_result,
                repair_hint="Repair structured hypothesis fields before drafting.",
            )

        artifact_id = _artifact_id("hypothesis", hypothesis)
        payload = {
            "artifact_kind": "hypothesis_draft",
            "artifact_id": artifact_id,
            "hypothesis": _model_payload(hypothesis),
            "schema_preview": schema_result,
            "workspace_materialized": False,
        }
        return self._observation(
            context,
            observation_type="hypothesis_draft",
            summary="Returned tainted hypothesis draft artifact.",
            structured_payload=payload,
            artifact_ref=f"proposal-artifact://{context.session_id}/{artifact_id}",
            exposure_level=ProposalExposureLevel.SCRATCH,
        )

class DraftPatchTool(_BaseReadOnlyTool):
    name = "proposal.draft_patch"
    input_schema = DraftPatchInput
    permission = ProposalToolPermission.DRAFT_PATCH
    max_result_chars = 80000

    def call(
        self,
        args: DraftPatchInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        patch = _patch_from_input(args)
        path_error = _patch_path_error(patch.file_path)
        if path_error is not None:
            return self._error(
                context,
                failure_code=ProposalToolFailureCode.PERMISSION_DENIED,
                summary="Patch draft target path is unsafe.",
                structured_payload={
                    "file_path": patch.file_path,
                    "path_error": path_error,
                    "workspace_materialized": False,
                },
                repair_hint="Use a normalized POSIX path relative to the candidate root.",
            )

        artifact_id = _artifact_id("patch", patch)
        payload = {
            "artifact_kind": "patch_draft",
            "artifact_id": artifact_id,
            "patch": _model_payload(patch),
            "workspace_materialized": False,
        }
        return self._observation(
            context,
            observation_type="patch_draft",
            summary="Returned tainted patch draft artifact without workspace writes.",
            structured_payload=payload,
            artifact_ref=f"proposal-artifact://{context.session_id}/{artifact_id}",
            exposure_level=ProposalExposureLevel.SCRATCH,
        )

class SchemaPreviewTool(_BaseReadOnlyTool):
    name = "proposal.schema_preview"
    input_schema = SchemaPreviewInput
    permission = ProposalToolPermission.CONTRACT_PREVIEW
    max_result_chars = 24000

    def call(
        self,
        args: SchemaPreviewInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        payload: dict[str, Any] = {
            "passed": True,
            "hypothesis": None,
            "patch": None,
            "workspace_materialized": False,
        }
        if args.hypothesis is None and args.patch is None:
            payload["passed"] = False
            payload["errors"] = ["Provide hypothesis and/or patch payload."]
        if args.hypothesis is not None:
            payload["hypothesis"] = _schema_preview_hypothesis_payload(
                context,
                args.hypothesis,
            )
            payload["passed"] = payload["passed"] and bool(
                payload["hypothesis"]["passed"]
            )
        if args.patch is not None:
            payload["patch"] = _schema_preview_patch_payload(args.patch)
            payload["passed"] = payload["passed"] and bool(payload["patch"]["passed"])
        payload = _drop_internal_preview_objects(payload)
        summary = _schema_preview_summary(payload)

        return self._observation(
            context,
            observation_type="schema_preview",
            summary=summary,
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
        )

def _schema_preview_summary(payload: Mapping[str, Any]) -> str:
    if bool(payload.get("passed")):
        return "Schema preview passed."
    details: list[str] = []
    for section_name in ("hypothesis", "patch"):
        section = payload.get(section_name)
        if not isinstance(section, Mapping):
            continue
        reason = section.get("failure_reason")
        if reason:
            details.append(str(reason))
        errors = section.get("errors")
        if isinstance(errors, list):
            for error in errors:
                if isinstance(error, Mapping):
                    loc = ".".join(str(part) for part in error.get("loc", ()) or ())
                    message = error.get("msg") or error.get("message") or error
                    details.append(f"{loc}: {message}" if loc else str(message))
                elif error:
                    details.append(str(error))
    if not details:
        return "Schema preview found issues."
    compact = "; ".join(dict.fromkeys(details))
    return "Schema preview found issues: " + _limit_text(compact, 420)

def _hypothesis_from_input(value: HypothesisProposalInput) -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text=value.hypothesis_text,
        change_locus=value.change_locus,
        action=value.action,  # type: ignore[arg-type]
        target_file=value.target_file or None,
        predicted_direction=value.predicted_direction,  # type: ignore[arg-type]
        target_weakness=value.target_weakness,
        expected_effect=value.expected_effect,
        suggested_weight=value.suggested_weight,
        target_objectives=tuple(value.target_objectives or ()),
        protected_objectives=tuple(value.protected_objectives or ()),
        objective_tradeoff_policy=value.objective_tradeoff_policy,
        no_op_condition=value.no_op_condition,
        risk_to_higher_priority=value.risk_to_higher_priority,
        target_runtime_effect=value.target_runtime_effect,
        complexity_claim=value.complexity_claim,
        runtime_budget_strategy=value.runtime_budget_strategy,
        expected_telemetry=dict(value.expected_telemetry or {}),
        novelty_signature=dict(value.novelty_signature or {}),
        mechanism_changes=tuple(
            MechanismChange(id=change.id, change_type=change.change_type)
            for change in value.mechanism_changes
        ),
    )

def _patch_from_input(value: PatchProposalInput) -> PatchProposal:
    return PatchProposal(
        file_path=value.file_path,
        action=value.action,  # type: ignore[arg-type]
        code_content=value.code_content,
        test_hint=value.test_hint or None,
        additional_changes=tuple(
            PatchFileChange(
                file_path=change.file_path,
                action=change.action,  # type: ignore[arg-type]
                code_content=change.code_content,
                test_hint=change.test_hint or None,
            )
            for change in value.additional_changes
        ),
        premise_check=value.premise_check,
        premise_check_reason=value.premise_check_reason,
        mechanism_changes=tuple(
            MechanismChange(id=change.id, change_type=change.change_type)
            for change in value.mechanism_changes
        ),
    )

def _schema_preview_hypothesis_payload(
    context: ProposalToolContext,
    raw: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        validated = DraftHypothesisInput.model_validate(dict(raw))
    except ValidationError as exc:
        return {
            "passed": False,
            "errors": exc.errors(include_url=False),
        }
    hypothesis = _hypothesis_from_input(validated)
    schema_result = _hypothesis_schema_preview(context, hypothesis)
    return {
        **schema_result,
        "hypothesis": _hypothesis_preview_summary(hypothesis),
        "hypothesis_object": hypothesis,
    }

def _hypothesis_preview_summary(
    hypothesis: HypothesisProposal,
) -> dict[str, Any]:
    novelty_signature = (
        hypothesis.novelty_signature
        if isinstance(hypothesis.novelty_signature, Mapping)
        else {}
    )
    novelty_payload: dict[str, Any] = {}
    for idx, (key, value) in enumerate(
        sorted(novelty_signature.items(), key=lambda item: str(item[0]))
    ):
        if idx >= _PREVIEW_MAX_CHECKS:
            break
        novelty_payload[str(key)] = _compact_preview_value(value)
    return _drop_empty_items(
        {
            "change_locus": hypothesis.change_locus,
            "action": hypothesis.action,
            "target_file": hypothesis.target_file,
            "predicted_direction": hypothesis.predicted_direction,
            "target_objectives": list(hypothesis.target_objectives),
            "protected_objectives": list(hypothesis.protected_objectives),
            "target_runtime_effect": hypothesis.target_runtime_effect,
            "suggested_weight": hypothesis.suggested_weight,
            "novelty_signature_keys": [
                str(key)
                for key in sorted(novelty_signature.keys(), key=str)[
                    :_PREVIEW_MAX_CHECKS
                ]
            ],
            "novelty_signature": novelty_payload,
            "hypothesis_text_chars": len(hypothesis.hypothesis_text or ""),
            "expected_effect_chars": len(hypothesis.expected_effect or ""),
            "runtime_budget_strategy_chars": len(
                hypothesis.runtime_budget_strategy or ""
            ),
            "expected_telemetry": _compact_preview_value(
                getattr(hypothesis, "expected_telemetry", {}) or {}
            ),
            "mechanism_changes": _compact_preview_value(
                [
                    {"id": change.id, "change_type": change.change_type}
                    for change in getattr(hypothesis, "mechanism_changes", ()) or ()
                ]
            ),
        }
    )

def _schema_preview_patch_payload(raw: Mapping[str, Any]) -> dict[str, Any]:
    try:
        payload = dict(raw)
        payload.pop("repair_attribution", None)
        validated = DraftPatchInput.model_validate(payload)
    except ValidationError as exc:
        return {
            "passed": False,
            "errors": exc.errors(include_url=False),
        }
    patch = _patch_from_input(validated)
    path_errors = []
    for index, change in enumerate(patch_file_changes(patch)):
        path_error = _patch_path_error(change.file_path)
        if path_error is not None:
            loc = ("file_path",) if index == 0 else (
                "additional_changes",
                index - 1,
                "file_path",
            )
            path_errors.append({"loc": loc, "msg": path_error})
    patch_summary = _patch_preview_summary(patch)
    if path_errors:
        return {
            "passed": False,
            "errors": path_errors,
            "patch": patch_summary,
        }
    return {
        "passed": True,
        "errors": [],
        "patch": patch_summary,
        "patch_object": patch,
    }

def _hypothesis_schema_preview(
    context: ProposalToolContext,
    hypothesis: HypothesisProposal,
) -> dict[str, Any]:
    result = _contract_gate(context).validate_hypothesis(
        hypothesis,
        [],
        [],
        current_champion_version=_champion_version(context.champion),
    )
    schema_check_names = {
        "C1_schema",
        "C11_expected_telemetry",
        "C12_mechanism_binding",
    }
    c1_checks = [check for check in result.checks if check.name in schema_check_names]
    c11_check = next(
        (check for check in result.checks if check.name == "C11_expected_telemetry"),
        None,
    )
    c12_check = next(
        (check for check in result.checks if check.name == "C12_mechanism_binding"),
        None,
    )
    novelty_guidance = _semantic_signature_preview_guidance(context, hypothesis)
    passed = bool(c1_checks and all(check.passed for check in c1_checks))
    forced_violation = _forced_hypothesis_violation(context, hypothesis)
    if forced_violation is not None:
        passed = False
    if novelty_guidance.get("required") and (
        novelty_guidance.get("missing_fields")
        or novelty_guidance.get("invalid_fields")
    ):
        passed = False
    return {
        "passed": passed,
        "checks": _checks_payload(
            c1_checks,
            detail_chars=_PREVIEW_CHECK_DETAIL_CHARS,
            max_checks=4,
        ),
        "failure_reason": (
            None
            if passed
            else (
                forced_violation
                if forced_violation is not None
                else (
                    novelty_guidance.get("detail")
                    if (
                        novelty_guidance.get("missing_fields")
                        or novelty_guidance.get("invalid_fields")
                    )
                    else _limit_text(
                        _first_failure(c1_checks) or "", _PREVIEW_FAILURE_REASON_CHARS
                    )
                )
            )
        ),
        "expected_telemetry_contract": _expected_telemetry_contract_preview(
            context,
            hypothesis,
            c11_check,
        ),
        "mechanism_binding": _mechanism_binding_preview(hypothesis, c12_check),
        "forced_surface_constraint": _forced_surface_constraint_payload(context),
        "novelty_signature_guidance": novelty_guidance,
    }

def _expected_telemetry_contract_preview(
    context: ProposalToolContext,
    hypothesis: HypothesisProposal,
    c11_check: Any | None,
) -> dict[str, Any]:
    expected = getattr(hypothesis, "expected_telemetry", {}) or {}
    requested_categories: list[str] = []
    invalid_categories: list[str] = []
    if isinstance(expected, Mapping):
        for raw_category in expected:
            category = str(raw_category or "").strip().lower()
            if not category:
                continue
            requested_categories.append(category)
            if category not in EXPECTED_TELEMETRY_CATEGORIES and category not in {
                "mechanism",
                "mechanisms",
                "declared_mechanism",
                "declared_mechanisms",
                "declared_mechanism_change",
                "declared_mechanism_changes",
                "mechanism_change",
                "mechanism_changes",
            }:
                invalid_categories.append(category)

    surface = _surface_for_hypothesis(context, hypothesis)
    declared_fields = sorted(declared_surface_telemetry_fields(surface))
    try:
        problem_spec = _contract_problem_spec(context)
    except Exception:
        problem_spec = None
    mechanism_fields = sorted(
        {
            probe.field
            for probe in declared_mechanism_runtime_probes(
                problem_spec=problem_spec,
                surface=surface,
                declared_mechanisms=mechanism_changes(hypothesis),
            )
        }
    )
    claims = normalize_expected_telemetry(expected)
    requested_fields = {
        category: list(fields)
        for category, fields in sorted(claims.items())
        if fields
    }
    passed = None if c11_check is None else bool(_attr(c11_check, "passed"))
    detail = "" if c11_check is None or passed else str(_attr(c11_check, "detail", ""))
    return _drop_empty_items(
        {
            "name": "C11_expected_telemetry",
            "passed": passed,
            "detail": _limit_text(detail, _PREVIEW_FAILURE_REASON_CHARS),
            "requested_categories": requested_categories,
            "invalid_categories": sorted(dict.fromkeys(invalid_categories)),
            "allowed_categories": sorted(EXPECTED_TELEMETRY_CATEGORIES),
            "requested_fields": requested_fields,
            "declared_runtime_fields": declared_fields[:_PREVIEW_MAX_CHECKS * 4],
            "declared_mechanism_runtime_fields": mechanism_fields[
                : _PREVIEW_MAX_CHECKS * 4
            ],
            "repair_hint": (
                "Use only allowed expected_telemetry categories and exact runtime "
                "keys declared by the selected research surface evidence contract. "
                "Do not put explanatory prose in expected_telemetry values; if "
                "mechanism fields are declared, substitute the concrete mechanism "
                "id into those field templates."
                if not passed
                else ""
            ),
        }
    )

def _mechanism_binding_preview(
    hypothesis: HypothesisProposal,
    c12_check: Any | None,
) -> dict[str, Any]:
    passed = None if c12_check is None else bool(_attr(c12_check, "passed"))
    detail = "" if c12_check is None or passed else str(_attr(c12_check, "detail", ""))
    return _drop_empty_items(
        {
            "name": "C12_mechanism_binding",
            "passed": passed,
            "detail": _limit_text(detail, _PREVIEW_FAILURE_REASON_CHARS),
            "mechanism_changes": _compact_preview_value(
                [
                    {"id": change.id, "change_type": change.change_type}
                    for change in mechanism_changes(hypothesis)
                ]
            ),
            "repair_hint": (
                "Declare mechanism_changes that match the selected surface "
                "mechanism telemetry and echo them in the patch."
                if not passed
                else ""
            ),
        }
    )

def _semantic_signature_preview_guidance(
    context: ProposalToolContext,
    hypothesis: HypothesisProposal,
) -> dict[str, Any]:
    surface = _surface_for_hypothesis(context, hypothesis)
    novelty = _attr(surface, "novelty") if surface is not None else None
    strategy = str(_attr(novelty, "strategy", "") or "")
    fields = _coerce_compact_list(_attr(novelty, "signature_fields", []))
    if strategy != "semantic_signature" or not fields:
        return {}

    missing: list[str] = []
    invalid_sequence: list[str] = []
    invalid_scalar: list[str] = []
    unsupported: list[str] = []
    for field in fields:
        name = str(field).strip()
        if not name:
            continue
        if not ContractGate.supports_semantic_signature_field(name):
            unsupported.append(name)
            continue
        if name in {"predicted_direction", "target_objectives", "protected_objectives"}:
            value = getattr(hypothesis, name, None)
            if value in (None, "", [], (), {}):
                missing.append(name)
            continue
        values = hypothesis.novelty_signature
        if (
            not isinstance(values, dict)
            or name not in values
            or _semantic_signature_value_missing(values[name])
        ):
            missing.append(name)
            continue
        if (
            name in _NONEMPTY_SEQUENCE_NOVELTY_FIELDS
            and not _is_nonempty_text_sequence(values[name])
        ):
            invalid_sequence.append(name)
        if (
            isinstance(values.get(name), str)
            and len(values[name].strip()) > _SEMANTIC_SIGNATURE_SCALAR_STRING_CHARS
        ):
            invalid_scalar.append(
                f"{name} > {_SEMANTIC_SIGNATURE_SCALAR_STRING_CHARS} chars"
            )

    detail = ""
    if missing:
        detail = (
            "missing structured novelty_signature identity for semantic_signature "
            f"surface '{hypothesis.change_locus}': {', '.join(missing)}"
        )
    elif invalid_sequence:
        detail = (
            "invalid structured novelty_signature identity for semantic_signature "
            f"surface '{hypothesis.change_locus}': {', '.join(invalid_sequence)} "
            "must be non-empty arrays of component names"
        )
    elif invalid_scalar:
        detail = (
            "invalid structured novelty_signature identity for semantic_signature "
            f"surface '{hypothesis.change_locus}': {', '.join(invalid_scalar)}. "
            "Use compact tokens or short phrases and put rationale in "
            "hypothesis_text."
        )
    elif unsupported:
        detail = (
            "unsupported novelty.signature_fields for semantic_signature surface "
            f"'{hypothesis.change_locus}': {', '.join(unsupported)}"
        )
    else:
        detail = (
            "semantic_signature identity is present; contract preview/C10 will "
            "still reject duplicate structured values."
        )
    return _drop_empty_items(
        {
            "required": True,
            "strategy": strategy,
            "signature_fields": fields,
            "missing_fields": missing,
            "invalid_fields": [*invalid_sequence, *invalid_scalar],
            "nonempty_sequence_fields": [
                field for field in fields if field in _NONEMPTY_SEQUENCE_NOVELTY_FIELDS
            ],
            "unsupported_fields": unsupported,
            "detail": detail,
        }
    )

def _semantic_signature_value_missing(value: Any) -> bool:
    if value is None or value is False:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, frozenset, dict)):
        return len(value) == 0
    return False

def _is_nonempty_text_sequence(value: Any) -> bool:
    if not isinstance(value, (list, tuple, set, frozenset)) or not value:
        return False
    return all(isinstance(item, str) and bool(item.strip()) for item in value)


__all__ = [
    "DraftHypothesisTool",
    "DraftPatchTool",
    "SchemaPreviewTool",
    "_expected_telemetry_contract_preview",
    "_hypothesis_from_input",
    "_hypothesis_preview_summary",
    "_hypothesis_schema_preview",
    "_is_nonempty_text_sequence",
    "_mechanism_binding_preview",
    "_patch_from_input",
    "_schema_preview_hypothesis_payload",
    "_schema_preview_patch_payload",
    "_schema_preview_summary",
    "_semantic_signature_preview_guidance",
    "_semantic_signature_value_missing",
]
