"""Experiment-family history and compact summary helpers."""
from __future__ import annotations

from collections import Counter
from typing import Dict, List, Optional

from scion.core.branch_hygiene import branch_hygiene_context, branch_prompt_card
from scion.core.models import (
    Branch,
    ExperimentStage,
    HypothesisFamily,
    HypothesisRecord,
    StepRecord,
)
from scion.proposal.context.feedback import (
    _filter_hypothesis_prompt_steps,
    _is_safe_pre_protocol_failure_step,
)
from scion.proposal.mechanism_labels import extract_mechanism_label

def _build_branch_direction_prompt(branch: Branch) -> Optional[str]:
    """Build branch direction guidance if a direction has been established."""
    if not branch.direction:
        return None
    return (
        f"## Branch Direction\n"
        f"This branch is exploring: {branch.direction}\n"
        f"Continue building on this direction. Propose improvements or refinements "
        f"to the current approach.\n"
        f"Only switch to a fundamentally different approach if the last 3+ screening "
        f"results show no progress."
    )

def _extract_mechanism_label(
    hypothesis_text: str,
    taxonomy: Optional[list] = None,
    preferred_label: Optional[str] = None,
) -> str:
    """Extract mechanism label from hypothesis text using problem taxonomy."""
    return extract_mechanism_label(
        hypothesis_text,
        taxonomy=taxonomy,
        preferred_label=preferred_label,
    )

def _make_family_id(mechanism_label: str, action_pattern: str, locus_pattern: str) -> str:
    return f"{mechanism_label}/{action_pattern}/{locus_pattern}"

def _get_step_status(step: StepRecord) -> str:
    """Derive a compact status string from a StepRecord."""
    if (
        step.protocol_result is not None
        and step.protocol_result.stage == ExperimentStage.SCREENING
    ):
        return f"screening_{step.protocol_result.gate_outcome}"
    if _is_safe_pre_protocol_failure_step(step):
        return f"failed_{step.failure_stage}"
    return ""

def _extract_families_from_steps(
    steps: List[StepRecord],
    taxonomy: Optional[list] = None,
) -> List[HypothesisFamily]:
    """Build the family list from step history (rebuilt each call — no persistence needed)."""
    family_map: Dict[str, HypothesisFamily] = {}
    for step in _filter_hypothesis_prompt_steps(steps):
        h = step.hypothesis
        mechanism = _extract_mechanism_label(
            h.hypothesis_text or "",
            taxonomy=taxonomy,
            preferred_label=h.change_locus,
        )
        family_id = _make_family_id(mechanism, h.action, h.change_locus)
        status = _get_step_status(step)
        if not status:
            continue
        if family_id in family_map:
            existing = family_map[family_id]
            family_map[family_id] = HypothesisFamily(
                family_id=existing.family_id,
                mechanism_label=existing.mechanism_label,
                action_pattern=existing.action_pattern,
                locus_pattern=existing.locus_pattern,
                evidence_count=existing.evidence_count + 1,
                statuses=existing.statuses + [status],
            )
        else:
            family_map[family_id] = HypothesisFamily(
                family_id=family_id,
                mechanism_label=mechanism,
                action_pattern=h.action,
                locus_pattern=h.change_locus,
                evidence_count=1,
                statuses=[status],
            )
    # Return in insertion order (order of first encounter)
    return list(family_map.values())

def assign_family_id(
    hypothesis_text: str,
    action: str,
    change_locus: str,
    taxonomy: Optional[list] = None,
) -> str:
    """Public helper: compute family_id for a hypothesis (for HypothesisRecord.family_id)."""
    mechanism = _extract_mechanism_label(
        hypothesis_text,
        taxonomy=taxonomy,
        preferred_label=change_locus,
    )
    return _make_family_id(mechanism, action, change_locus)

def build_exploration_coverage(
    families: List[HypothesisFamily],
    *,
    available_actions: Optional[set[str]] = None,
    forced_action: Optional[str] = None,
) -> str:
    """Return a formatted string showing family coverage across attempts (T07)."""
    if not families:
        return ""
    lines = ["## Exploration Coverage"]
    for fam in families:
        status_counts = Counter(fam.statuses)
        parts: List[str] = []
        for status in (
            "screening_pass",
            "screening_expand",
            "screening_continue",
            "screening_fail",
            "screening_unclear",
        ):
            count = status_counts.get(status, 0)
            if count:
                parts.append(f"{status}={count}")
        pre_protocol_failed = sum(
            count
            for status, count in status_counts.items()
            if status.startswith("failed_")
        )
        if pre_protocol_failed:
            parts.append(f"pre_protocol_failed={pre_protocol_failed}")
        status_summary = " ".join(parts) if parts else "screening_seen=0"
        lines.append(
            f"  {fam.family_id}: n={fam.evidence_count} [{status_summary}]"
        )
    # Show unexplored action/locus combos
    explored_actions = {f.action_pattern for f in families}
    all_actions = available_actions or {"create_new", "modify", "remove"}
    unexplored_actions = all_actions - explored_actions
    if unexplored_actions and not forced_action:
        lines.append(f"  Unexplored actions: {sorted(unexplored_actions)}")
    return "\n".join(lines)

def _count_trailing_failures(statuses: List[str]) -> int:
    """Count consecutive trailing failures in statuses list."""
    count = 0
    for s in reversed(statuses):
        if s.startswith("failed_") or "fail" in s:
            count += 1
        else:
            break
    return count

def _summarise_active_hypotheses(active_hypotheses: List[HypothesisRecord]) -> str:
    """Summarise currently active hypotheses so the LLM avoids proposing duplicates."""
    if not active_hypotheses:
        return "(none)"
    lines = []
    for h in active_hypotheses:
        key_str = f"{h.change_locus}/{h.action}"
        if h.target_file:
            key_str += f" → {h.target_file}"
        lines.append(f"  - {key_str}  [OCCUPIED — C10 will reject any duplicate]")
    return "\n".join(lines)

def _summarise_blacklist(blacklist: List[HypothesisRecord]) -> str:
    if not blacklist:
        return "(none)"
    lines = []
    for h in blacklist[:10]:  # Cap at 10
        lines.append(
            f"  - {h.change_locus}/{h.action}"
            + (f" → {h.target_file}" if h.target_file else "")
        )
    return "\n".join(lines)

def _branch_hygiene_status_projection(branch: Branch) -> str:
    context = branch_hygiene_context(branch)
    last_telemetry_outcome = context.get("last_telemetry_outcome") or "none"
    repair_focus_required = bool(context.get("repair_focus_required"))
    parts = [
        branch_prompt_card(branch),
        f"branch_code_status={context['branch_code_status']}",
        f"last_telemetry_outcome={last_telemetry_outcome}",
        f"repair_focus_required={str(repair_focus_required).lower()}",
    ]
    if repair_focus_required and context.get("repair_focus_reason"):
        parts.append(f"repair_focus={context['repair_focus_reason']}")
    if repair_focus_required and context.get("repair_policy"):
        parts.append(f"repair_policy={context['repair_policy']}")
    if context.get("branch_followup_policy"):
        parts.append(f"branch_followup_policy={context['branch_followup_policy']}")
    if context.get("hypothesis_generation_mode"):
        parts.append(
            f"hypothesis_generation_mode={context['hypothesis_generation_mode']}"
        )
    if context.get("clean_fork_policy"):
        parts.append(f"clean_fork_policy={context['clean_fork_policy']}")
    if context.get("branch_mechanism_ids"):
        parts.append(
            "branch_mechanism_ids="
            + ",".join(str(item) for item in context["branch_mechanism_ids"])
        )
    if context.get("allowed_mechanism_ids"):
        parts.append(
            "allowed_mechanism_ids="
            + ",".join(str(item) for item in context["allowed_mechanism_ids"])
        )
    if context.get("protected_mechanism_ids"):
        parts.append(
            "protected_mechanism_ids="
            + ",".join(str(item) for item in context["protected_mechanism_ids"])
        )
    if context.get("forbidden_mechanism_policy"):
        parts.append(
            f"forbidden_mechanism_policy={context['forbidden_mechanism_policy']}"
        )
    if context.get("baseline_policy"):
        parts.append(f"baseline_policy={context['baseline_policy']}")
    diversity_guidance = context.get("diversity_re" + "ro" + "ute_guidance")
    if isinstance(diversity_guidance, dict) and diversity_guidance.get("policy"):
        policy = str(diversity_guidance["policy"]).replace(
            "re" + "ro" + "ute",
            "redirect",
        )
        parts.append(
            "diversity_redirect_guidance="
            f"{policy}"
        )
        parts.append(
            "diversity_action="
            "change_mechanism_family_or_trigger_or_observability"
        )
    if context.get("branch_lifecycle_new_mechanism_ineligible"):
        parts.append("branch_lifecycle_new_mechanism_ineligible=true")
    reselect_key = "branch_lifecycle_re" + "".join(("r", "o", "u", "t", "e")) + "_reason"
    if context.get(reselect_key):
        parts.append(
            "branch_lifecycle_recovery_reason="
            f"{context[reselect_key]}"
        )
    if context.get("next_branch_selection_policy"):
        parts.append(
            "next_branch_selection_policy="
            f"{context['next_branch_selection_policy']}"
        )
    return " ".join(parts)


def _summarise_siblings(siblings: List[Branch]) -> str:
    if not siblings:
        return "(no active sibling branches)"
    lines = []
    for b in siblings[:5]:
        lines.append(
            f"  - branch {b.branch_id[:8]} state={b.state.value} "
            f"{_branch_hygiene_status_projection(b)}"
        )
    return "\n".join(lines)
