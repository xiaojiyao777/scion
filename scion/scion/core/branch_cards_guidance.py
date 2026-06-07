"""Branch-card prompt guidance rendering helpers."""

from __future__ import annotations

from typing import Any, Mapping

from scion.core.branch_cards_runtime import (
    _diversity_guidance_sentence,
    _runtime_evidence_low_confidence_advisory_sentence,
)


def branch_hygiene_guidance_from_context(
    context: Mapping[str, Any],
    *,
    card: str,
    parked_lineage: bool,
) -> str:
    """Render human-readable branch hygiene guidance from reconciled context."""
    status = context["branch_code_status"]
    outcome = context.get("last_telemetry_outcome") or "unknown"
    tier = context.get("last_screening_feedback_tier") or "unknown"
    if context["repair_focus_required"]:
        reroute_suffix = _branch_lifecycle_guidance_suffix(context)
        protected = _protected_mechanism_text(context)
        allowed_actions = _allowed_actions_text(context)
        return (
            f"{card}; "
            f"branch_code_status={status}; telemetry_outcome={outcome}; "
            f"screening_tier={tier}; "
            f"repair_focus={context['repair_focus_reason']}; "
            f"repair_policy={context['repair_policy']}; "
            f"hypothesis_generation_mode={context['hypothesis_generation_mode']}; "
            f"branch_followup_policy={context['branch_followup_policy']}; "
            f"clean_fork_policy={context['clean_fork_policy']}; "
            f"allowed_mechanism_ids={protected}; "
            f"protected_mechanism_ids={protected}; "
            f"forbidden_mechanism_policy={context['forbidden_mechanism_policy']}; "
            f"same_mechanism_allowed_actions={allowed_actions}; "
            "do not treat the existing branch workspace as a clean baseline. "
            "Continue only as a repair-focused attempt against champion code: "
            "fix declared telemetry activation/budget wiring or choose a new "
            f"branch instead of building on suspect code. Protected mechanism "
            f"ids for this branch: {protected}; do not add, drop, or rename "
            "them on this branch. Do not introduce unrelated mechanism_changes "
            "ids. Allowed actions here are only tune, integrate, repair, "
            "parameterize, or telemetry wiring within the protected mechanism. "
            "Those are branch research action labels, not mechanism_changes "
            "change_type values; map tune/parameterize to modify and "
            "telemetry_wiring to modify or integrate. "
            "If a different mechanism is needed, use a clean branch/fork "
            f"before drafting it.{reroute_suffix}"
        )
    if parked_lineage:
        return (
            f"{card}; "
            f"branch_code_status={status}; telemetry_outcome={outcome}; "
            f"screening_tier={tier}; baseline_policy="
            f"{context['baseline_policy']}; branch_followup_policy="
            f"{context['branch_followup_policy']}; clean_fork_policy="
            f"{context['clean_fork_policy']}; hypothesis_generation_mode="
            f"{context['hypothesis_generation_mode']}. "
            "This lineage is parked and must not consume an active branch "
            "slot or continue as open exploration. Start from a clean branch "
            "or clean fork for any next research direction."
        )
    if status.startswith("active_"):
        reroute_suffix = _branch_lifecycle_guidance_suffix(context)
        protected = _protected_mechanism_text(context)
        allowed_actions = _allowed_actions_text(context)
        if context.get("weak_positive_followup"):
            runtime_guidance = _runtime_evidence_low_confidence_advisory_sentence(
                context
            )
            return (
                f"{card}; "
                f"branch_code_status={status}; telemetry_outcome={outcome}; "
                f"screening_tier={tier}; baseline_policy="
                f"{context['baseline_policy']}; branch_followup_policy="
                f"{context['branch_followup_policy']}; clean_fork_policy="
                f"{context['clean_fork_policy']}; hypothesis_generation_mode="
                f"{context['hypothesis_generation_mode']}; "
                f"prior_mechanism_ids={protected}; "
                f"prior_touched_file_policy=prefer_branch_local_files. "
                "This is a weak-positive active branch. Default to a "
                "branch-local continuation that refines the prior mechanism, "
                "prior target/touched files, branch-created helpers, or the "
                "trigger, schedule, composition, budget allocation, or "
                "activation of the existing branch idea. If the next "
                "hypothesis changes target file, adds/renames a mechanism "
                "family, or moves work into a new module, it must explicitly "
                "bridge to the branch history: name which prior weak signal "
                "is preserved, which branch-local failure is being tested, "
                "and why the prior mechanism cannot be directly refined."
                f"{runtime_guidance}"
                f"{reroute_suffix}"
            )
        return (
            f"{card}; "
            f"branch_code_status={status}; telemetry_outcome={outcome}; "
            f"screening_tier={tier}; baseline_policy="
            f"{context['baseline_policy']}; branch_followup_policy="
            f"{context['branch_followup_policy']}; clean_fork_policy="
            f"{context['clean_fork_policy']}; hypothesis_generation_mode="
            f"{context['hypothesis_generation_mode']}; "
            f"allowed_mechanism_ids={protected}; "
            f"protected_mechanism_ids={protected}; "
            f"forbidden_mechanism_policy={context['forbidden_mechanism_policy']}; "
            f"same_mechanism_allowed_actions={allowed_actions}. "
            "This is an active branch outcome; "
            "reuse the branch workspace only for the same declared mechanism "
            f"ids: {protected}. The next hypothesis on this branch must keep "
            "those protected mechanism ids and may only tune, integrate, "
            "repair, parameterize, or wire telemetry for the same mechanism. "
            "These are branch research action labels, not mechanism_changes "
            "change_type values; map tune/parameterize to modify and "
            "telemetry_wiring to modify or integrate. "
            f"{_diversity_guidance_sentence(context)}"
            "Do not introduce unrelated mechanism_changes ids. A different "
            "or new mechanism requires a clean branch or clean fork before "
            "generation."
            f"{reroute_suffix}"
        )
    return ""


def _branch_lifecycle_guidance_suffix(context: Mapping[str, Any]) -> str:
    if not context.get("branch_lifecycle_new_mechanism_ineligible"):
        return ""
    return (
        " Prior branch-lifecycle policy blocks marked this branch ineligible "
        "for new-mechanism proposal selection; scheduler should use a clean "
        "branch/fork for new mechanisms, or continue here only under the same "
        "declared mechanism ids."
    )


def _protected_mechanism_text(context: Mapping[str, Any]) -> str:
    ids = [
        str(item).strip()
        for item in (context.get("protected_mechanism_ids") or ())
        if str(item).strip()
    ]
    return ", ".join(ids) if ids else "unknown"


def _allowed_actions_text(context: Mapping[str, Any]) -> str:
    actions = [
        str(item).strip()
        for item in (context.get("same_mechanism_allowed_actions") or ())
        if str(item).strip()
    ]
    return ",".join(actions) if actions else "none"


__all__ = [
    "branch_hygiene_guidance_from_context",
]
