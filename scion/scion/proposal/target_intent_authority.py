"""Proposal-layer authority resolution for hypothesis target intent."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Mapping

from scion.core.branch_hygiene import (
    BRANCH_LOCAL_FOLLOWUP_MODE,
    BRANCH_LOCAL_FOLLOWUP_OR_EXPLICIT_BRIDGE,
    SAME_MECHANISM_FOLLOWUP_ONLY,
    SAME_MECHANISM_ONLY_MODE,
    branch_hygiene_context,
    branch_requires_same_mechanism_followup,
)
from scion.proposal.target_intent_binding import target_intent_mechanism_identity
from scion.proposal.tools.models import ProposalToolContext


@dataclass(frozen=True)
class TargetIntentAuthorityResolution:
    intent: dict[str, Any]
    diagnostics: dict[str, Any] = field(default_factory=dict)
    tool_context_overrides: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _BranchMechanismAuthority:
    protected_ids: tuple[str, ...]
    allowed_ids: tuple[str, ...]
    branch_local: bool
    hypothesis_generation_mode: str = ""
    branch_followup_policy: str = ""
    same_mechanism_followup_required: bool = False

    @property
    def authority_ids(self) -> tuple[str, ...]:
        return _unique_strings(self.protected_ids, self.allowed_ids)


def resolve_target_intent_authority(
    intent: Mapping[str, Any],
    tool_context: ProposalToolContext,
) -> TargetIntentAuthorityResolution:
    """Resolve prepared launch focus against branch-local mechanism authority."""

    required_ids = _launch_focus_required_mechanism_ids_from_context(tool_context)
    updated = dict(intent)
    if not required_ids:
        return TargetIntentAuthorityResolution(intent=updated)

    branch_authority = _branch_mechanism_authority(tool_context)
    current_id = _clean_string(intent.get("mechanism_id"))
    original = _original_target_intent_mechanism(intent)

    if branch_authority.branch_local and branch_authority.authority_ids:
        intersecting_id = _first_in_order(
            required_ids,
            branch_authority.authority_ids,
        )
        if intersecting_id:
            selected_id = intersecting_id
            status = "branch_prepared_focus_intersection"
            updated = _with_selected_mechanism(
                intent,
                selected_id,
                status=status,
                action=_branch_local_followup_action(intent),
                mechanism_sketch=(
                    "Prepared launch-focus required mechanism also belongs to "
                    f"the selected branch-local mechanism authority: {selected_id}."
                ),
                formal_schema_id_policy=(
                    "mechanism_id is authorized by both prepared launch focus "
                    "and branch-local protected/allowed mechanism ids"
                ),
            )
            diagnostics = _authority_diagnostics(
                status=status,
                authority_source="branch_local_prepared_focus_intersection",
                prepared_required_ids=required_ids,
                branch_authority=branch_authority,
                selected_id=selected_id,
                original=original,
                original_action=_clean_string(intent.get("action")),
                selected_action=_branch_local_followup_action(intent),
                prepared_focus_applied=True,
                target_intent_updated=(
                    selected_id != current_id
                    or _branch_local_followup_action(intent)
                    != _normalize_action(intent.get("action"))
                ),
            )
            updated["target_intent_authority"] = diagnostics
            updated["launch_focus_required_mechanism"] = diagnostics
            return TargetIntentAuthorityResolution(
                intent=updated,
                diagnostics=diagnostics,
            )

        selected_id = (
            current_id
            if current_id in set(branch_authority.authority_ids)
            else branch_authority.authority_ids[0]
        )
        status = "prepared_focus_deferred_for_branch_followup"
        updated = _with_selected_mechanism(
            intent,
            selected_id,
            status=status,
            action=_branch_local_followup_action(intent),
            mechanism_sketch=(
                "Branch-local follow-up mechanism authority selected "
                f"{selected_id}; prepared launch-focus required ids were "
                "deferred because they do not intersect the branch authority set."
            ),
            formal_schema_id_policy=(
                "mechanism_id is the branch-local protected/allowed id for this "
                "follow-up; prepared launch-focus required ids are audit-deferred"
            ),
        )
        diagnostics = _authority_diagnostics(
            status=status,
            authority_source="branch_local_mechanism_authority",
            prepared_required_ids=required_ids,
            branch_authority=branch_authority,
            selected_id=selected_id,
            original=original,
            original_action=_clean_string(intent.get("action")),
            selected_action=_branch_local_followup_action(intent),
            prepared_focus_applied=False,
            target_intent_updated=(
                selected_id != current_id
                or _branch_local_followup_action(intent)
                != _normalize_action(intent.get("action"))
            ),
            deferred_required_ids=required_ids,
        )
        effective_focus = _launch_focus_with_deferred_required_ids(
            tool_context,
            required_ids=required_ids,
            diagnostics=diagnostics,
        )
        overrides = {"launch_research_focus": effective_focus} if effective_focus else {}
        updated["target_intent_authority"] = diagnostics
        updated["launch_focus_required_mechanism"] = diagnostics
        return TargetIntentAuthorityResolution(
            intent=updated,
            diagnostics=diagnostics,
            tool_context_overrides=overrides,
        )

    if current_id in required_ids:
        diagnostics = _authority_diagnostics(
            status="prepared_focus_already_selected",
            authority_source="prepared_launch_research_focus",
            prepared_required_ids=required_ids,
            branch_authority=branch_authority,
            selected_id=current_id,
            original=original,
            original_action=_clean_string(intent.get("action")),
            selected_action=_normalize_action(intent.get("action")),
            prepared_focus_applied=True,
            target_intent_updated=False,
        )
        updated["target_intent_authority"] = diagnostics
        updated["launch_focus_required_mechanism"] = diagnostics
        return TargetIntentAuthorityResolution(
            intent=updated,
            diagnostics=diagnostics,
        )

    selected_id = required_ids[0]
    status = "launch_focus_required_mechanism"
    updated = _with_selected_mechanism(
        intent,
        selected_id,
        status=status,
        mechanism_sketch=(
            f"Prepared launch-focus required mechanism {selected_id}; draft "
            "the formal hypothesis around this id."
        ),
        formal_schema_id_policy=(
            "mechanism_id is the prepared launch-focus required id and must be "
            "used exactly in formal mechanism_changes and expected telemetry refs"
        ),
    )
    diagnostics = _authority_diagnostics(
        status=status,
        authority_source="prepared_launch_research_focus",
        prepared_required_ids=required_ids,
        branch_authority=branch_authority,
        selected_id=selected_id,
        original=original,
        original_action=_clean_string(intent.get("action")),
        selected_action=_normalize_action(intent.get("action")),
        prepared_focus_applied=True,
        target_intent_updated=selected_id != current_id,
    )
    updated["target_intent_authority"] = diagnostics
    updated["launch_focus_required_mechanism"] = diagnostics
    return TargetIntentAuthorityResolution(intent=updated, diagnostics=diagnostics)


def tool_context_with_target_intent_authority_overrides(
    tool_context: ProposalToolContext | None,
    target_intent: Mapping[str, Any] | None,
) -> ProposalToolContext | None:
    if tool_context is None or not isinstance(target_intent, Mapping):
        return tool_context
    overrides = target_intent.get("tool_context_overrides")
    if not isinstance(overrides, Mapping):
        intent_value = target_intent.get("intent")
        if isinstance(intent_value, Mapping):
            overrides = intent_value.get("tool_context_overrides")
    if not isinstance(overrides, Mapping):
        return tool_context
    launch_focus = overrides.get("launch_research_focus")
    if not isinstance(launch_focus, Mapping):
        return tool_context
    return replace(tool_context, launch_research_focus=dict(launch_focus))


def _branch_mechanism_authority(
    tool_context: ProposalToolContext,
) -> _BranchMechanismAuthority:
    branch = getattr(tool_context, "branch", None)
    hygiene = (
        dict(tool_context.branch_hygiene)
        if isinstance(getattr(tool_context, "branch_hygiene", None), Mapping)
        else {}
    )
    if not hygiene and branch is not None:
        hygiene = branch_hygiene_context(branch)

    protected_ids = _unique_strings(
        *(hygiene.get(key) for key in ("protected_mechanism_ids", "branch_mechanism_ids")),
        getattr(branch, "branch_mechanism_ids", ()) if branch is not None else (),
        getattr(branch, "telemetry_repair_mechanism_ids", ())
        if branch is not None
        else (),
    )
    allowed_ids = _unique_strings(
        hygiene.get("allowed_mechanism_ids"),
        getattr(branch, "allowed_mechanism_ids", ()) if branch is not None else (),
    )
    generation_mode = _clean_string(hygiene.get("hypothesis_generation_mode"))
    followup_policy = _clean_string(hygiene.get("branch_followup_policy"))
    same_required = _truthy(hygiene.get("same_mechanism_followup_required"))
    if branch is not None:
        same_required = same_required or branch_requires_same_mechanism_followup(branch)

    branch_local = _is_branch_local_authority_mode(
        generation_mode=generation_mode,
        followup_policy=followup_policy,
        same_required=same_required,
        weak_positive_followup=_truthy(hygiene.get("weak_positive_followup")),
        protected_ids=protected_ids,
        allowed_ids=allowed_ids,
    )
    return _BranchMechanismAuthority(
        protected_ids=tuple(protected_ids),
        allowed_ids=tuple(allowed_ids),
        branch_local=branch_local,
        hypothesis_generation_mode=generation_mode,
        branch_followup_policy=followup_policy,
        same_mechanism_followup_required=same_required,
    )


def _is_branch_local_authority_mode(
    *,
    generation_mode: str,
    followup_policy: str,
    same_required: bool,
    weak_positive_followup: bool,
    protected_ids: tuple[str, ...] | list[str],
    allowed_ids: tuple[str, ...] | list[str],
) -> bool:
    if not protected_ids and not allowed_ids:
        return False
    if same_required or weak_positive_followup:
        return True
    if allowed_ids:
        return True
    branch_local_modes = {
        SAME_MECHANISM_ONLY_MODE,
        BRANCH_LOCAL_FOLLOWUP_MODE,
    }
    branch_local_policies = {
        SAME_MECHANISM_FOLLOWUP_ONLY,
        BRANCH_LOCAL_FOLLOWUP_OR_EXPLICIT_BRIDGE,
    }
    if generation_mode in branch_local_modes:
        return True
    if followup_policy in branch_local_policies:
        return True
    mode_text = f"{generation_mode} {followup_policy}".lower()
    return "branch_local" in mode_text or "same_mechanism" in mode_text


def _with_selected_mechanism(
    intent: Mapping[str, Any],
    selected_id: str,
    *,
    status: str,
    action: str | None = None,
    mechanism_sketch: str,
    formal_schema_id_policy: str,
) -> dict[str, Any]:
    updated = dict(intent)
    identity = target_intent_mechanism_identity(
        mechanism_id=selected_id,
        mechanism_family="",
        mechanism_sketch=mechanism_sketch,
    )
    updated.update(identity)
    updated["mechanism_id"] = selected_id
    updated["raw_mechanism_id"] = selected_id
    updated["mechanism_id_status"] = status
    updated["mechanism_sketch"] = mechanism_sketch
    updated["formal_schema_id_policy"] = formal_schema_id_policy
    if action:
        updated["action"] = action
    return updated


def _authority_diagnostics(
    *,
    status: str,
    authority_source: str,
    prepared_required_ids: list[str],
    branch_authority: _BranchMechanismAuthority,
    selected_id: str,
    original: Mapping[str, Any],
    original_action: str,
    selected_action: str,
    prepared_focus_applied: bool,
    target_intent_updated: bool,
    deferred_required_ids: list[str] | None = None,
) -> dict[str, Any]:
    return _drop_empty(
        {
            "name": "target_intent_authority",
            "status": status,
            "authority_status": status,
            "authority_source": authority_source,
            "source": authority_source,
            "applied": prepared_focus_applied,
            "prepared_focus_applied": prepared_focus_applied,
            "prepared_focus_deferred": bool(deferred_required_ids),
            "target_intent_updated": target_intent_updated,
            "required_mechanism_ids": prepared_required_ids,
            "prepared_required_mechanism_ids": prepared_required_ids,
            "deferred_required_mechanism_ids": deferred_required_ids or [],
            "selected_mechanism_id": selected_id,
            "original_target_intent_action": original_action,
            "selected_target_intent_action": selected_action,
            "target_intent_action_updated": (
                selected_action != _normalize_action(original_action)
            ),
            "selected_required_mechanism_id": (
                selected_id if selected_id in set(prepared_required_ids) else ""
            ),
            "selected_branch_mechanism_id": (
                selected_id if selected_id in set(branch_authority.authority_ids) else ""
            ),
            "branch_local_authority": branch_authority.branch_local,
            "branch_protected_mechanism_ids": list(branch_authority.protected_ids),
            "branch_allowed_mechanism_ids": list(branch_authority.allowed_ids),
            "branch_authority_mechanism_ids": list(branch_authority.authority_ids),
            "hypothesis_generation_mode": (
                branch_authority.hypothesis_generation_mode
            ),
            "branch_followup_policy": branch_authority.branch_followup_policy,
            "same_mechanism_followup_required": (
                branch_authority.same_mechanism_followup_required
            ),
            "original_target_intent_mechanism": dict(original),
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
            "tainted": True,
            "rule": _authority_rule(status),
        }
    )


def _authority_rule(status: str) -> str:
    if status == "prepared_focus_deferred_for_branch_followup":
        return (
            "Branch-local protected mechanism authority outranks prepared "
            "launch-focus required ids when the sets are disjoint."
        )
    if status == "branch_prepared_focus_intersection":
        return (
            "Prepared launch focus binds target intent through the intersection "
            "with branch-local protected/allowed mechanism ids."
        )
    return (
        "Prepared launch research_focus required_mechanism_ids bind target-intent "
        "preflight before formal hypothesis generation."
    )


def _launch_focus_with_deferred_required_ids(
    tool_context: ProposalToolContext,
    *,
    required_ids: list[str],
    diagnostics: Mapping[str, Any],
) -> dict[str, Any]:
    focus = getattr(tool_context, "launch_research_focus", {}) or {}
    if not isinstance(focus, Mapping):
        return {}
    updated_focus = dict(focus)
    research_focus = updated_focus.get("research_focus")
    if isinstance(research_focus, Mapping):
        updated_research_focus = dict(research_focus)
        updated_research_focus["required_mechanism_ids"] = []
        updated_research_focus["deferred_required_mechanism_ids"] = list(required_ids)
        updated_research_focus["required_mechanism_authority_status"] = (
            "prepared_focus_deferred_for_branch_followup"
        )
        updated_focus["research_focus"] = updated_research_focus
    else:
        updated_focus["required_mechanism_ids"] = []
        updated_focus["deferred_required_mechanism_ids"] = list(required_ids)
        updated_focus["required_mechanism_authority_status"] = (
            "prepared_focus_deferred_for_branch_followup"
        )
    updated_focus["target_intent_authority"] = _drop_empty(
        {
            "authority_status": diagnostics.get("authority_status"),
            "authority_source": diagnostics.get("authority_source"),
            "prepared_required_mechanism_ids": required_ids,
            "branch_protected_mechanism_ids": diagnostics.get(
                "branch_protected_mechanism_ids"
            ),
            "selected_mechanism_id": diagnostics.get("selected_mechanism_id"),
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
        }
    )
    return updated_focus


def _launch_focus_required_mechanism_ids_from_context(
    tool_context: ProposalToolContext,
) -> list[str]:
    focus = getattr(tool_context, "launch_research_focus", {}) or {}
    if not isinstance(focus, Mapping):
        return []
    research_focus = focus.get("research_focus")
    if not isinstance(research_focus, Mapping):
        research_focus = focus
    return list(_unique_strings(research_focus.get("required_mechanism_ids")))


def _branch_local_followup_action(intent: Mapping[str, Any]) -> str:
    action = _normalize_action(intent.get("action"))
    return action if action == "modify" else "modify"


def _normalize_action(value: Any) -> str:
    action = _clean_string(value)
    return "create_new" if action == "create" else action


def _original_target_intent_mechanism(
    intent: Mapping[str, Any],
) -> dict[str, Any]:
    return _drop_empty(
        {
            "mechanism_id": _clean_string(intent.get("mechanism_id")),
            "raw_mechanism_id": intent.get("raw_mechanism_id"),
            "mechanism_family": intent.get("mechanism_family"),
            "mechanism_sketch": intent.get("mechanism_sketch"),
            "mechanism_id_status": intent.get("mechanism_id_status"),
        }
    )


def _first_in_order(left: list[str], right: tuple[str, ...]) -> str:
    right_set = set(right)
    for item in left:
        if item in right_set:
            return item
    return ""


def _unique_strings(*values: Any) -> tuple[str, ...]:
    items: list[str] = []
    for value in values:
        if isinstance(value, str):
            candidates = (value,)
        elif isinstance(value, Mapping) or value is None:
            candidates = ()
        else:
            try:
                candidates = tuple(value)
            except TypeError:
                candidates = (value,)
        for candidate in candidates:
            text = _clean_string(candidate)
            if text and text not in items:
                items.append(text)
    return tuple(items)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _clean_string(value: Any) -> str:
    return str(value or "").strip()


def _drop_empty(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: cleaned
            for key, item in value.items()
            if (cleaned := _drop_empty(item)) not in (None, "", [], {})
        }
    if isinstance(value, list):
        return [
            cleaned
            for item in value
            if (cleaned := _drop_empty(item)) not in (None, "", [], {})
        ]
    if isinstance(value, tuple):
        return tuple(
            cleaned
            for item in value
            if (cleaned := _drop_empty(item)) not in (None, "", [], {})
        )
    return value
