"""Runtime-evidence advisory projection for proposal-visible branch cards."""

from __future__ import annotations

from typing import Any, Mapping

from scion.core.branch_hygiene import RUNTIME_SATURATED_DIVERSITY_REROUTE_GUIDANCE


def _runtime_saturated_diversity_guidance(
    context: Mapping[str, Any],
) -> dict[str, Any]:
    reason_text = " ".join(
        str(value or "")
        for value in (
            context.get("branch_code_status"),
            context.get("last_screening_feedback_tier"),
            context.get("last_telemetry_outcome"),
            context.get("branch_lifecycle_reroute_reason"),
            (
                (context.get("last_branch_lifecycle_policy_block") or {}).get(
                    "reason"
                )
                if isinstance(
                    context.get("last_branch_lifecycle_policy_block"),
                    Mapping,
                )
                else ""
            ),
            (
                (context.get("last_branch_lifecycle_policy_block") or {}).get(
                    "detail"
                )
                if isinstance(
                    context.get("last_branch_lifecycle_policy_block"),
                    Mapping,
                )
                else ""
            ),
        )
    ).lower()
    if not any(
        token in reason_text
        for token in (
            "runtime_saturation",
            "runtime saturation",
            "runtime_budget",
            "no_effect",
            "no effect",
            "zero_effect",
            "zero effect",
        )
    ):
        return {}
    return {
        "policy": RUNTIME_SATURATED_DIVERSITY_REROUTE_GUIDANCE,
        "guidance": (
            "Recent branch feedback is low-effect or runtime-saturated. Avoid "
            "continuing with another homogeneous high-cost variant on the same "
            "branch. Prefer a clean branch/fork or a materially different "
            "research direction that changes the mechanism family, trigger "
            "condition, budget allocation, or evaluation observability."
        ),
        "allowed_same_branch_followup": (
            "Only continue this branch when the follow-up reduces/redirects "
            "work or improves observability for the protected mechanism."
        ),
    }


def _diversity_guidance_sentence(context: Mapping[str, Any]) -> str:
    guidance = context.get("diversity_reroute_guidance")
    if not isinstance(guidance, Mapping) or not guidance:
        return ""
    return (
        "Runtime/no-effect lifecycle feedback is active: avoid another "
        "homogeneous high-cost variant here; prefer changing mechanism family, "
        "trigger condition, budget allocation, or evaluation observability, "
        "or use a clean branch/fork for a new direction. "
    )


def _runtime_evidence_low_confidence_advisory_sentence(
    context: Mapping[str, Any],
) -> str:
    guidance = (
        context.get("runtime_evidence_low_confidence_advisory")
        or context.get("runtime_evidence_clean_fork_guidance")
        or context.get("fresh_runtime_followup")
    )
    if not isinstance(guidance, Mapping) or not guidance:
        return ""
    reason = (
        guidance.get("reason")
        or guidance.get("queue_intent")
        or "runtime_evidence_completeness_clean_fork"
    )
    return (
        " Low-confidence runtime evidence advisory is active: do not treat "
        "runtime saturation/pressure as a strong conclusion or branch-routing "
        "constraint. Need fresh champion runtime before runtime-based "
        "conclusions; same-branch follow-up may focus on improving runtime "
        "evidence completeness. This is tainted proposal guidance excluded "
        f"from DecisionFeatures; reason={reason}."
    )


def _runtime_evidence_prompt_advisory_projection(
    guidance: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(guidance, Mapping) or not guidance:
        return {}
    projected = dict(guidance)
    projected["policy"] = "fresh_runtime_advisory"
    projected["runtime_signal_role"] = "low_confidence_advisory"
    projected["strong_branch_constraint"] = False
    projected["proposal_guidance"] = (
        "Need fresh champion runtime before runtime-based conclusions; do not "
        "treat runtime saturation/pressure as a strong diagnostic when "
        "runtime aggregate evidence is excluded or low confidence."
    )
    projected["tainted_proposal_guidance"] = True
    projected["decision_features_excluded"] = True
    return projected
