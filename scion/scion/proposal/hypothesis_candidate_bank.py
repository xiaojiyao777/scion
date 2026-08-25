"""Private ordinal K2 candidate storage for one bounded H session."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from copy import deepcopy
from typing import Any

from scion.proposal.bounded_research import require_exact_keys, tool_error
from scion.proposal.engine.exceptions import ProposalValidationError
from scion.proposal.hypothesis_research_basis import HypothesisResearchFinalized

_STAGE_ACTION = "stage_hypothesis_candidate"
_SELECT_ACTION = "select_hypothesis_candidate"
_STAGE_REJECTION_REASONS = frozenset(
    {
        "candidate_hypothesis_duplicate",
        "candidate_payload_invalid",
        "candidate_slot_already_staged",
        "candidate_slot_out_of_order",
        "hypothesis_invalid",
        "nearest_prior_refs_not_read_and_cited",
        "read_refs_not_read",
        "research_basis_invalid",
    }
)
_SELECTION_REJECTION_REASONS = frozenset(
    {
        "candidate_selection_invalid",
        "candidate_slot_not_staged",
        "candidate_slots_incomplete",
    }
)


class HypothesisCandidateBank:
    """One inaccessible-by-value two-slot bank owned by an H session."""

    def __init__(self) -> None:
        self._slots: dict[int, HypothesisResearchFinalized] = {}

    @staticmethod
    def normalize_slots(
        max_candidates: int,
        staged_slots: Collection[int],
    ) -> tuple[int, ...]:
        if type(max_candidates) is not int or max_candidates not in {1, 2}:
            raise ValueError("hypothesis research candidate count must be 1 or 2")
        if any(type(slot) is not int for slot in staged_slots):
            raise ValueError("hypothesis research candidate slots must be integers")
        normalized = tuple(sorted(set(staged_slots)))
        valid = ((),) if max_candidates == 1 else ((), (1,), (1, 2))
        if normalized not in valid:
            raise ValueError("hypothesis research candidate slots are not ordinal")
        return normalized

    @property
    def staged_slots(self) -> tuple[int, ...]:
        return tuple(sorted(self._slots))

    def prevalidate_stage(self, slot: int) -> dict[str, Any] | None:
        if slot in self._slots:
            return candidate_stage_tool_error("candidate_slot_already_staged")
        if len(self._slots) >= 2 or slot != len(self._slots) + 1:
            return candidate_stage_tool_error("candidate_slot_out_of_order")
        return None

    def stage_validated(
        self,
        slot: int,
        candidate: HypothesisResearchFinalized,
    ) -> dict[str, Any] | None:
        ordinal_error = self.prevalidate_stage(slot)
        if ordinal_error is not None:
            return ordinal_error
        if any(
            candidate.hypothesis == staged.hypothesis for staged in self._slots.values()
        ):
            return candidate_stage_tool_error("candidate_hypothesis_duplicate")
        self._slots[slot] = deepcopy(candidate)
        return None

    def select(self, slot: int) -> HypothesisResearchFinalized | dict[str, Any]:
        if slot not in self._slots:
            return candidate_selection_tool_error("candidate_slot_not_staged")
        if len(self._slots) != 2:
            return candidate_selection_tool_error("candidate_slots_incomplete")
        return deepcopy(self._slots[slot])

    def to_research_projection(self) -> dict[str, Any]:
        return {
            "required_slots": 2,
            "staged_candidates": [
                _candidate_projection(slot, self._slots[slot])
                for slot in self.staged_slots
            ],
        }


def parse_hypothesis_candidate_action(
    raw: Mapping[str, Any],
) -> tuple[str, dict[str, Any]] | None:
    action = raw.get("action")
    if action == _STAGE_ACTION:
        require_exact_keys(
            raw,
            {"action", "slot", "hypothesis", "research_basis"},
            label=action,
        )
        if type(raw["slot"]) is not int:
            raise ProposalValidationError(
                "stage_hypothesis_candidate requires an integer slot"
            )
        return action, {
            "slot": raw["slot"],
            "hypothesis": raw["hypothesis"],
            "research_basis": raw["research_basis"],
        }
    if action == _SELECT_ACTION:
        require_exact_keys(raw, {"action", "slot"}, label=action)
        if type(raw["slot"]) is not int:
            raise ProposalValidationError(
                "select_hypothesis_candidate requires an integer slot"
            )
        return action, {"slot": raw["slot"]}
    return None


def candidate_stage_tool_error(reason: str) -> dict[str, Any]:
    if reason not in _STAGE_REJECTION_REASONS:
        raise AssertionError("unknown hypothesis candidate staging rejection category")
    return tool_error(_STAGE_ACTION, reason)


def candidate_selection_tool_error(reason: str) -> dict[str, Any]:
    if reason not in _SELECTION_REJECTION_REASONS:
        raise AssertionError(
            "unknown hypothesis candidate selection rejection category"
        )
    return tool_error(_SELECT_ACTION, reason)


def _candidate_projection(
    slot: int,
    candidate: HypothesisResearchFinalized,
) -> dict[str, Any]:
    hypothesis = candidate.hypothesis
    basis = candidate.research_basis
    return {
        "slot": slot,
        "hypothesis": {
            "hypothesis_text": hypothesis.hypothesis_text,
            "change_locus": hypothesis.change_locus,
            "action": hypothesis.action,
            "target_file": hypothesis.target_file,
            "predicted_direction": hypothesis.predicted_direction,
            "target_weakness": hypothesis.target_weakness,
            "expected_effect": hypothesis.expected_effect,
            "suggested_weight": hypothesis.suggested_weight,
        },
        "research_basis": {
            "read_refs": list(basis.read_refs),
            "nearest_prior_refs": list(basis.nearest_prior_refs),
            "material_delta": basis.material_delta,
            "alternatives_considered": list(basis.alternatives_considered),
            "observable_prediction": basis.observable_prediction,
            "falsification_condition": basis.falsification_condition,
        },
    }


__all__ = [
    "HypothesisCandidateBank",
    "candidate_selection_tool_error",
    "candidate_stage_tool_error",
    "parse_hypothesis_candidate_action",
]
