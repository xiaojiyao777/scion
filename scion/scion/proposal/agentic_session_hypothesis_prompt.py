"""Prompt/context assembly helpers for agentic hypothesis sessions."""
from __future__ import annotations

from typing import Any, Mapping

from scion.proposal.agentic_session_common import (
    AgenticProposalRequest,
    ProposalObservation,
    ProposalToolContext,
    _active_algorithm_facts_for_prompt_context,
    _drop_empty_dict,
    _hypothesis_prompt_observations,
    _observation_prompt_payload,
    _research_diagnosis_from_observations,
    _sanitize_agentic_value,
)
from scion.proposal.agentic_session_hypothesis_schema_retry import (
    _launch_focus_required_mechanism_retry_pending,
    _mechanism_id_schema_retry_pending,
    _same_mechanism_preview_retry_pending,
    _schema_retry_corrective_retry_already_used,
    _target_action_permission_retry_pending,
)
from scion.proposal.agentic_session_hypothesis_target import (
    _active_grounding_rejections_for_prompt,
)
from scion.proposal.negative_facts import render_negative_fact_block
from scion.proposal.target_intent_binding import (
    selected_target_intent_payload as _selected_target_intent_payload,
    target_intent_binding_retry_pending as _target_intent_binding_retry_pending,
)
from scion.runtime.telemetry_guard import expected_telemetry_template


def _build_hypothesis_prompt_context(
    *,
    request: AgenticProposalRequest,
    tool_context: ProposalToolContext | None,
    constraints: Mapping[str, Any] | None,
    observations: list[ProposalObservation],
    semantic_rejections: list[Mapping[str, Any]],
    preview_rejections: list[Mapping[str, Any]],
    grounding_rejections: list[Mapping[str, Any]],
    target_intent: Mapping[str, Any] | None = None,
    attempt: int,
) -> tuple[dict[str, Any], list[ProposalObservation]]:
    hypothesis_context = dict(
        _sanitize_agentic_value(request.hypothesis_context or {})
    )
    if request.resume_context is not None:
        hypothesis_context["agentic_resume_context"] = (
            _sanitize_agentic_value(request.resume_context)
        )
    if constraints:
        hypothesis_context["agentic_hypothesis_constraints"] = (
            _sanitize_agentic_value(constraints)
        )
    launch_focus = getattr(tool_context, "launch_research_focus", {}) or {}
    if launch_focus and not hypothesis_context.get("launch_research_focus"):
        hypothesis_context["launch_research_focus"] = (
            _sanitize_agentic_value(launch_focus)
        )
    if target_intent:
        hypothesis_context["agentic_hypothesis_target_intent"] = (
            _sanitize_agentic_value(target_intent)
        )
        target_intent_defaults = _target_intent_formal_defaults(target_intent)
        if target_intent_defaults:
            hypothesis_context["agentic_hypothesis_target_intent_defaults"] = (
                target_intent_defaults
            )
        placeholder = target_intent.get("placeholder")
        if isinstance(placeholder, Mapping):
            hypothesis_context["agentic_hypothesis_target_placeholder"] = (
                _sanitize_agentic_value(placeholder)
            )
    telemetry_guidance = _expected_telemetry_guidance_for_hypothesis(
        tool_context,
    )
    if telemetry_guidance:
        hypothesis_context["agentic_expected_telemetry_guidance"] = (
            telemetry_guidance
        )
    if semantic_rejections:
        hypothesis_context["agentic_hypothesis_semantic_rejections"] = [
            _sanitize_agentic_value(rejection)
            for rejection in semantic_rejections
        ]
        hypothesis_context["agentic_hypothesis_retry_rule"] = (
            "An audited gate found a hard boundary/objective-policy "
            "contradiction in the previous hypothesis. Preserve the "
            "research goal when possible; if the idea remains near an "
            "existing mechanism, explicitly acknowledge that mechanism "
            "and state the material trigger, scoring, schedule, or "
            "behavior difference."
        )
        hypothesis_context["agentic_hypothesis_retry_attempt"] = attempt
    if preview_rejections:
        hypothesis_context["agentic_hypothesis_preview_rejections"] = [
            _sanitize_agentic_value(rejection)
            for rejection in preview_rejections
        ]
        if _schema_retry_corrective_retry_already_used(preview_rejections):
            hypothesis_context["agentic_hypothesis_preview_retry_rule"] = (
                "IDENTITY CORRECTIVE RETRY for a schema/telemetry "
                "repair. Restore the exact protected identity from the "
                "feedback: action, target_file, mechanism_changes ids/"
                "change_types, and telemetry activation refs. The final "
                "task is only to repair expected_telemetry/schema fields "
                "for that same hypothesis; do not explore, rename, or "
                "choose a different mechanism."
            )
        elif _mechanism_id_schema_retry_pending(preview_rejections):
            hypothesis_context["agentic_hypothesis_preview_retry_rule"] = (
                "MECHANISM-ID SCHEMA RETRY. The previous formal "
                "hypothesis used a mechanism_changes id that is not "
                "legal for the formal schema. Use the canonical formal "
                "mechanism id from the feedback exactly in "
                "mechanism_changes and expected telemetry refs. "
                "raw_mechanism_id/provenance fields are audit-only and "
                "must not be copied into formal mechanism_changes."
            )
        elif _launch_focus_required_mechanism_retry_pending(preview_rejections):
            hypothesis_context["agentic_hypothesis_preview_retry_rule"] = (
                "LAUNCH-FOCUS REQUIRED-MECHANISM RETRY. The prepared "
                "research_focus requires an exact mechanism_changes id. "
                "Rewrite the hypothesis around one of required_mechanism_ids "
                "from the feedback, put that exact id in mechanism_changes, "
                "and align expected telemetry activation/effect/budget refs "
                "to that same id. This retry is allowed to replace the "
                "previous mechanism id because the launch focus is the "
                "binding research direction for this campaign."
            )
        elif _target_intent_binding_retry_pending(preview_rejections):
            hypothesis_context["agentic_hypothesis_preview_retry_rule"] = (
                "TARGET-INTENT BINDING RETRY. The selected "
                "hypothesis_target_intent is binding for this final "
                "formal hypothesis call. Preferred repair: rewrite under "
                "the same selected intent and preserve change_locus, "
                "action, target_file, and mechanism family/continuation "
                "from selected_target_intent. If the research idea truly "
                "needs a different owner, action, target_file, or "
                "mechanism, do not repair it inside formal hypothesis; "
                "request a host-owned target-intent reselect flow before "
                "formal hypothesis generation."
            )
        elif _same_mechanism_preview_retry_pending(preview_rejections):
            hypothesis_context["agentic_hypothesis_preview_retry_rule"] = (
                "SAME-MECHANISM BRANCH RETRY. The selected branch is "
                "same_mechanism_only, so replace any unrelated "
                "mechanism_changes ids with one of the protected ids "
                "from the feedback. The only valid task is tune, "
                "integrate, repair, parameterize, or telemetry wiring "
                "inside the protected mechanism. A genuinely different "
                "mechanism requires a clean branch/fork before "
                "hypothesis generation; when active clean-fork slots "
                "are available, treat the new-mechanism idea as a "
                "branch-routing signal rather than burning this "
                "same-branch formal proposal."
            )
        elif _target_action_permission_retry_pending(preview_rejections):
            hypothesis_context["agentic_hypothesis_preview_retry_rule"] = (
                "TARGET-ACTION PERMISSION RETRY. The selected target_file "
                "already exists, so file-level action=create_new is invalid. "
                "Rewrite the same hypothesis with action=modify for that "
                "target_file and plan typed exact_replace/source_digest edits. "
                "Mechanism-level text may still say add or integrate a new "
                "mechanism inside the existing file, but do not preserve "
                "file-level action=create_new."
            )
        else:
            hypothesis_context["agentic_hypothesis_preview_retry_rule"] = (
                "A schema/target preview rejected the previous hypothesis. "
                "This is a structured-field repair, not a semantic novelty "
                "rejection. Preserve the previous action, target_file, "
                "mechanism_changes ids/change_types, and telemetry "
                "activation mechanism; repair only the exact field named "
                "by the failed check unless the preview explicitly says "
                "that surface/action/target is invalid. Natural-language "
                "hypothesis and novelty_signature wording may be clarified "
                "without changing the mechanism."
            )
        hypothesis_context["agentic_hypothesis_retry_attempt"] = attempt
    active_grounding_rejections = _active_grounding_rejections_for_prompt(
        grounding_rejections,
        semantic_rejections=semantic_rejections,
        preview_rejections=preview_rejections,
    )
    if active_grounding_rejections:
        hypothesis_context["agentic_hypothesis_grounding_rejections"] = [
            _sanitize_agentic_value(rejection)
            for rejection in active_grounding_rejections
        ]
        latest_grounding = active_grounding_rejections[-1]
        target_file = str(latest_grounding.get("target_file") or "").strip()
        hypothesis_context["agentic_hypothesis_grounding_retry_rule"] = (
            "The previous solver_design hypothesis selected an existing "
            "target_file whose full source was not visible in the API "
            "prompt that generated it. This grounding feedback is scoped "
            f"to target_file={target_file!r}; do not use source from a "
            "different target_file as grounding. The target file has now "
            "been read and is projected into this API-visible prompt. "
            "Redraft only after using that target-file observation. If "
            "separate semantic feedback requires changing to a different "
            "existing target_file, Scion must ground that new target in "
            "a later prompt before approval."
        )
        hypothesis_context["agentic_hypothesis_retry_attempt"] = attempt
    if observations:
        prompt_observations = _hypothesis_prompt_observations(
            observations,
            tool_context,
        )
        research_diagnosis = _research_diagnosis_from_observations(observations)
        if research_diagnosis:
            hypothesis_context["agentic_research_diagnosis"] = (
                research_diagnosis
            )
        active_algorithm_facts = _active_algorithm_facts_for_prompt_context(
            observations
        )
        if active_algorithm_facts:
            hypothesis_context["agentic_active_algorithm_facts"] = (
                active_algorithm_facts
            )
        hypothesis_context["agentic_tool_observations"] = [
            _observation_prompt_payload(observation)
            for observation in prompt_observations
        ]
        negative_fact_block = render_negative_fact_block(
            active_algorithm_facts=active_algorithm_facts,
            structured_rejections=semantic_rejections,
            prior_quality_blocks=tuple(
                block
                for block in hypothesis_context.get(
                    "agentic_prior_quality_blocks",
                    (),
                )
                if isinstance(block, Mapping)
            ),
        )
        if negative_fact_block:
            existing = str(
                hypothesis_context.get("agentic_negative_fact_block") or ""
            ).strip()
            hypothesis_context["agentic_negative_fact_block"] = (
                existing + "\n" + negative_fact_block
                if existing
                else negative_fact_block
            )
    else:
        prompt_observations = []
    return hypothesis_context, prompt_observations


def _target_intent_formal_defaults(
    target_intent: Mapping[str, Any],
) -> dict[str, Any]:
    selected = _selected_target_intent_payload(target_intent)
    mechanism_id = str(selected.get("mechanism_id") or "").strip()
    return _drop_empty_dict(
        {
            "change_locus": selected.get("change_locus"),
            "action": selected.get("action"),
            "target_file": selected.get("target_file"),
            "mechanism_changes": [
                {"id": mechanism_id, "change_type": "modify"}
            ]
            if mechanism_id
            else [],
            "novelty_signature": _drop_empty_dict(
                {
                    "mechanism_family": selected.get("mechanism_family"),
                }
            ),
            "default_policy": (
                "Formal hypothesis fields inherit selected target intent by "
                "default. Changing owner/action/target/mechanism requires a "
                "fresh host target-intent reselect flow, not in-hypothesis "
                "drift."
            ),
        }
    )


def _expected_telemetry_guidance_for_hypothesis(
    context: ProposalToolContext | None,
) -> dict[str, Any]:
    if context is None:
        return {}
    surfaces: list[str] = []
    forced = str(getattr(context, "forced_surface", "") or "").strip()
    if forced:
        surfaces.append(forced)
    for surface in getattr(context, "active_problem_boundary_surfaces", ()) or ():
        text = str(surface or "").strip()
        if text and text not in surfaces:
            surfaces.append(text)
    if not surfaces:
        return {}
    templates: dict[str, Any] = {}
    for surface in surfaces[:4]:
        template = expected_telemetry_template(
            problem_spec=getattr(context, "problem_spec", None),
            selected_surface=surface,
            declared_mechanisms=("<mechanism_id>",),
            max_fields_per_category=4,
        )
        if template:
            templates[surface] = template
    if not templates:
        return {}
    return _drop_empty_dict(
        {
            "schema_version": "agentic-expected-telemetry-guidance.v1",
            "source": "adapter_declared_runtime_fields",
            "templates_by_surface": templates,
            "rule": (
                "Use only these top-level categories: activity, activation, "
                "effect, budget. Replace <mechanism_id> or {mechanism} with the "
                "exact mechanism_changes id before finalizing the hypothesis."
            ),
            "preview_helper": (
                "Use proposal.schema_preview if unsure; it returns the exact "
                "C11_expected_telemetry repair template without lowering schema "
                "strictness."
            ),
        }
    )


def _hypothesis_prompt_call_kind(
    *,
    attempt: int,
    semantic_rejections: list[Mapping[str, Any]],
    preview_rejections: list[Mapping[str, Any]],
    grounding_rejections: list[Mapping[str, Any]] | None = None,
) -> str:
    if attempt <= 1:
        return "hypothesis"
    previous_attempt = attempt - 1
    grounding_rejections = grounding_rejections or []
    if grounding_rejections and int(grounding_rejections[-1].get("attempt") or 0) == (
        previous_attempt
    ):
        return "hypothesis_grounding_retry"
    if preview_rejections and int(preview_rejections[-1].get("attempt") or 0) == (
        previous_attempt
    ):
        return "hypothesis_preview_retry"
    if semantic_rejections and int(semantic_rejections[-1].get("attempt") or 0) == (
        previous_attempt
    ):
        return "hypothesis_semantic_retry"
    if preview_rejections:
        return "hypothesis_preview_retry"
    if semantic_rejections:
        return "hypothesis_semantic_retry"
    if grounding_rejections:
        return "hypothesis_grounding_retry"
    return "hypothesis_retry"
