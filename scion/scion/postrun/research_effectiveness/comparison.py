"""Pure exact-five-block comparison for M32 research effectiveness."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .endpoints import _evaluate_arm, _ratio
from .models import (
    BLOCK_UNSCORABLE,
    LoadedHistoryAvailable,
    LoadedHistoryUnavailable,
    MatchedResearchEffectivenessBlock,
    ResearchEffectivenessArmArtifacts,
    ResearchEffectivenessExpectation,
    _ArmEvaluation,
    _fail,
)

_SCHEMA_VERSION = "scion.research_effectiveness.five_block.v1"
_BLOCK_CONDITIONS = (
    "f_higher",
    "t_higher",
    "q_higher",
    "e_not_worse",
    "loaded_h_replay_not_higher",
    "within_h_replay_not_higher",
    "loaded_pair_replay_not_higher",
    "within_pair_replay_not_higher",
    "candidate_only_not_higher",
    "k2_infeasibility_zero",
    "k2_protected_regression_zero",
    "reference_failure_classes_zero",
)
_REFERENCE_FAILURE_FIELDS = (
    "champion_failure_candidates",
    "shared_failure_candidates",
    "bilateral_failure_candidates",
)


@dataclass(frozen=True, repr=False)
class _EvaluatedBlock:
    source: MatchedResearchEffectivenessBlock
    k1: _ArmEvaluation
    k2: _ArmEvaluation

    def __repr__(self) -> str:
        return "_EvaluatedBlock(<redacted>)"


def compare_five_block_research_effectiveness(
    *,
    blocks: tuple[MatchedResearchEffectivenessBlock, ...],
) -> dict[str, Any]:
    """Compare endpoint conditions over exactly five supplied artifact blocks.

    This offline result does not establish population freshness, full matched
    controls, ordering authority, or live authority, and it never authorizes a
    GO or advance action.
    """

    checked = _validate_blocks(blocks)
    evaluated = tuple(_evaluate_block(block) for block in checked)
    statuses = tuple(_block_status(block) for block in evaluated)
    all_scoreable = all(status == "SCOREABLE" for status in statuses)
    if not all_scoreable:
        signs = [
            _block_sign(ordinal, status, conditions=None)
            for ordinal, status in enumerate(statuses, 1)
        ]
        return _comparison_report(
            status="inconclusive",
            signs=signs,
            cross_block=_unavailable_cross_block(),
        )

    conditions = tuple(_block_conditions(block) for block in evaluated)
    signs = [
        _block_sign(ordinal, "SCOREABLE", conditions=values)
        for ordinal, values in enumerate(conditions, 1)
    ]
    cross_block = _cross_block_output(evaluated)
    satisfied = all(all(values.values()) for values in conditions) and bool(
        cross_block["endpoint_conditions_satisfied"]
    )
    return _comparison_report(
        status=(
            "endpoint_conditions_satisfied"
            if satisfied
            else "endpoint_conditions_not_satisfied"
        ),
        signs=signs,
        cross_block=cross_block,
    )


def _validate_blocks(
    blocks: tuple[MatchedResearchEffectivenessBlock, ...],
) -> tuple[MatchedResearchEffectivenessBlock, ...]:
    if type(blocks) is not tuple or len(blocks) != 5:
        _fail("FIVE_BLOCK_INPUT_INVALID")
    problem_id: str | None = None
    for block in blocks:
        if type(block) is not MatchedResearchEffectivenessBlock:
            _fail("MATCHED_BLOCK_INPUT_INVALID")
        _validate_matched_expectations(block.k1, block.k2)
        current_problem = block.k1.expectation.problem_id
        if problem_id is None:
            problem_id = current_problem
        elif current_problem != problem_id:
            _fail("FIVE_BLOCK_PROBLEM_MISMATCH")
    return blocks


def _validate_matched_expectations(
    k1: ResearchEffectivenessArmArtifacts,
    k2: ResearchEffectivenessArmArtifacts,
) -> None:
    if (
        type(k1) is not ResearchEffectivenessArmArtifacts
        or type(k2) is not ResearchEffectivenessArmArtifacts
    ):
        _fail("MATCHED_BLOCK_ARM_INVALID")
    if k1.expectation.max_hypothesis_candidates != 1 or (
        k2.expectation.max_hypothesis_candidates != 2
    ):
        _fail("MATCHED_BLOCK_K_INVALID")
    if _expectation_match_key(k1.expectation) != _expectation_match_key(k2.expectation):
        _fail("MATCHED_BLOCK_EXPECTATION_MISMATCH")


def _expectation_match_key(
    expectation: ResearchEffectivenessExpectation,
) -> tuple[Any, ...]:
    return (
        expectation.problem_id,
        expectation.expected_initial_case_count,
        expectation.expected_initial_pair_count,
        expectation.a_cap,
        expectation.p_cap,
    )


def _evaluate_block(block: MatchedResearchEffectivenessBlock) -> _EvaluatedBlock:
    return _EvaluatedBlock(
        source=block,
        k1=_evaluate_artifacts(block.k1, block.loaded_history),
        k2=_evaluate_artifacts(block.k2, block.loaded_history),
    )


def _evaluate_artifacts(
    artifacts: ResearchEffectivenessArmArtifacts,
    loaded_history: LoadedHistoryAvailable | LoadedHistoryUnavailable,
) -> _ArmEvaluation:
    return _evaluate_arm(
        status=artifacts.status,
        summary=artifacts.summary,
        current_history=artifacts.current_history,
        loaded_history=loaded_history,
        expectation=artifacts.expectation,
        initial_cells=artifacts.initial_cells,
    )


def _block_status(block: _EvaluatedBlock) -> str:
    if _has_reference_failure(block.k1.report) or _has_reference_failure(
        block.k2.report
    ):
        return BLOCK_UNSCORABLE
    if _is_scoreable(block.k1.report) and _is_scoreable(block.k2.report):
        return "SCOREABLE"
    return "INCONCLUSIVE"


def _is_scoreable(report: dict[str, Any]) -> bool:
    return report["scientific_status"] == {"value": "complete", "reasons": []} and (
        report["endpoint_status"] == {"value": "complete", "limitations": []}
    )


def _has_reference_failure(report: dict[str, Any]) -> bool:
    physical = report["physical"]
    return any(physical[field] > 0 for field in _REFERENCE_FAILURE_FIELDS)


def _block_conditions(block: _EvaluatedBlock) -> dict[str, bool]:
    k1 = block.k1.report
    k2 = block.k2.report
    a1 = k1["adjusted"]
    a2 = k2["adjusted"]
    p2 = k2["physical"]
    return {
        "f_higher": a2["f"] > a1["f"],
        "t_higher": _ratio_greater(a2["t"], a1["t"]),
        "q_higher": _ratio_greater(a2["q"], a1["q"]),
        "e_not_worse": _effect_not_worse(a2["e"], a1["e"]),
        "loaded_h_replay_not_higher": _ratio_not_higher(
            a2["loaded_history_h_replay_rate"],
            a1["loaded_history_h_replay_rate"],
        ),
        "within_h_replay_not_higher": _ratio_not_higher(
            a2["within_block_h_replay_rate"],
            a1["within_block_h_replay_rate"],
        ),
        "loaded_pair_replay_not_higher": _ratio_not_higher(
            a2["loaded_history_pair_replay_rate"],
            a1["loaded_history_pair_replay_rate"],
        ),
        "within_pair_replay_not_higher": _ratio_not_higher(
            a2["within_block_pair_replay_rate"],
            a1["within_block_pair_replay_rate"],
        ),
        "candidate_only_not_higher": _ratio_not_higher(
            a2["candidate_only_failure_rate"],
            a1["candidate_only_failure_rate"],
        ),
        "k2_infeasibility_zero": (
            p2["candidate_attributable_infeasibility_candidates"] == 0
        ),
        "k2_protected_regression_zero": p2["protected_regression_candidates"] == 0,
        "reference_failure_classes_zero": not (
            _has_reference_failure(k1) or _has_reference_failure(k2)
        ),
    }


def _ratio_greater(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_numerator, left_denominator = _rational_parts(left)
    right_numerator, right_denominator = _rational_parts(right)
    return left_numerator * right_denominator > (right_numerator * left_denominator)


def _ratio_not_higher(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_numerator, left_denominator = _rational_parts(left)
    right_numerator, right_denominator = _rational_parts(right)
    return left_numerator * right_denominator <= (right_numerator * left_denominator)


def _rational_parts(value: dict[str, Any]) -> tuple[int, int]:
    numerator = value["numerator"]
    denominator = value["denominator"]
    if denominator == 0:
        return 0, 1
    return numerator, denominator


def _effect_not_worse(k2: dict[str, Any], k1: dict[str, Any]) -> bool:
    if k2["status"] != "FINITE":
        return False
    k2_value = k2["value"]
    if not isinstance(k2_value, (int, float)) or not math.isfinite(k2_value):
        return False
    if k1["status"] == "POSITIVE_INFINITY":
        return True
    k1_value = k1["value"]
    return bool(
        k1["status"] == "FINITE"
        and isinstance(k1_value, (int, float))
        and math.isfinite(k1_value)
        and k2_value <= k1_value
    )


def _block_sign(
    ordinal: int,
    status: str,
    *,
    conditions: dict[str, bool] | None,
) -> dict[str, Any]:
    projected = (
        dict(conditions)
        if conditions is not None
        else {name: None for name in _BLOCK_CONDITIONS}
    )
    return {
        "block_ordinal": ordinal,
        "status": status,
        "endpoint_conditions_satisfied": (
            all(projected.values()) if conditions is not None else None
        ),
        "conditions": projected,
    }


def _cross_block_output(
    blocks: tuple[_EvaluatedBlock, ...],
) -> dict[str, Any]:
    k1 = _cross_arm(tuple(block.k1 for block in blocks))
    k2 = _cross_arm(tuple(block.k2 for block in blocks))
    conditions = {
        "h_replay_not_higher": _ratio_not_higher(
            k2["h_replay_rate"], k1["h_replay_rate"]
        ),
        "pair_replay_not_higher": _ratio_not_higher(
            k2["pair_replay_rate"], k1["pair_replay_rate"]
        ),
        "u_f_higher": k2["u_f"] > k1["u_f"],
    }
    return {
        "status": "AVAILABLE",
        "k1": k1,
        "k2": k2,
        "conditions": conditions,
        "endpoint_conditions_satisfied": all(conditions.values()),
    }


def _cross_arm(
    evaluations: tuple[_ArmEvaluation, ...],
) -> dict[str, Any]:
    prior_h: set[tuple[Any, ...]] = set()
    prior_pairs: set[tuple[Any, ...]] = set()
    all_f_pairs: set[tuple[Any, ...]] = set()
    h_replays = 0
    pair_replays = 0
    denominator = 0
    for evaluation in evaluations:
        current_h = evaluation.evidence.exported_h_keys
        current_pairs = evaluation.evidence.pair_keys
        f_pairs = evaluation.evidence.f_pair_keys
        if f_pairs is None:
            _fail("PRIVATE_F_EVIDENCE_UNAVAILABLE")
        h_replays += sum(key in prior_h for key in current_h)
        pair_replays += sum(key in prior_pairs for key in current_pairs)
        prior_h.update(current_h)
        prior_pairs.update(current_pairs)
        all_f_pairs.update(f_pairs)
        denominator += _arm_a_cap(evaluation)
    return {
        "h_replays": h_replays,
        "h_replay_rate": _ratio(h_replays, denominator),
        "pair_replays": pair_replays,
        "pair_replay_rate": _ratio(pair_replays, denominator),
        "u_f": len(all_f_pairs),
    }


def _arm_a_cap(evaluation: _ArmEvaluation) -> int:
    value = evaluation.report["physical"]["a_cap"]
    if type(value) is not int or value <= 0:
        _fail("PRIVATE_ARM_CAP_INVALID")
    return value


def _unavailable_cross_block() -> dict[str, Any]:
    arm = {
        "h_replays": None,
        "h_replay_rate": None,
        "pair_replays": None,
        "pair_replay_rate": None,
        "u_f": None,
    }
    return {
        "status": "UNAVAILABLE",
        "k1": dict(arm),
        "k2": dict(arm),
        "conditions": {
            "h_replay_not_higher": None,
            "pair_replay_not_higher": None,
            "u_f_higher": None,
        },
        "endpoint_conditions_satisfied": None,
    }


def _comparison_report(
    *,
    status: str,
    signs: list[dict[str, Any]],
    cross_block: dict[str, Any],
) -> dict[str, Any]:
    scoreable = sum(sign["status"] == "SCOREABLE" for sign in signs)
    inconclusive = sum(sign["status"] == "INCONCLUSIVE" for sign in signs)
    unscorable = sum(sign["status"] == BLOCK_UNSCORABLE for sign in signs)
    condition_count = (
        sum(sign["endpoint_conditions_satisfied"] is True for sign in signs)
        if status != "inconclusive"
        else None
    )
    return {
        "schema_version": _SCHEMA_VERSION,
        "status": status,
        "block_signs": signs,
        "counts": {
            "blocks_total": 5,
            "blocks_scoreable": scoreable,
            "blocks_inconclusive": inconclusive,
            "blocks_unscorable": unscorable,
            "endpoint_conditions_satisfied": condition_count,
        },
        "cross_block": cross_block,
    }


__all__ = ["compare_five_block_research_effectiveness"]
