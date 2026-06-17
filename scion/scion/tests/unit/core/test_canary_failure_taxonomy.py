from __future__ import annotations

from scion.core.canary_failure import (
    CANARY_CONFIG_ERROR,
    CANARY_FAILED,
    CANARY_FAILURE_CATEGORY_CANDIDATE,
    CANARY_FAILURE_CATEGORY_CONFIG,
    canary_configuration_error,
    decision_reason_codes_for_canary,
    normalize_canary_result,
    public_canary_reason_codes,
)
from scion.core.models import CanaryResult


def test_canary_configuration_error_replaces_algorithm_failure_code() -> None:
    result = canary_configuration_error(
        ValueError(
            "Unsafe case path in strict ExperimentProtocol: "
            "'artifact:instance_prod_can_s01.json#64a747f955e8' "
            "status=absolute_outside_roots reason=absolute case path is outside "
            "workspace and safe_data_roots"
        )
    )

    normalized = normalize_canary_result(result)

    assert normalized.failure_category == CANARY_FAILURE_CATEGORY_CONFIG
    assert normalized.reason_codes == (CANARY_CONFIG_ERROR,)
    assert public_canary_reason_codes(normalized) == (CANARY_CONFIG_ERROR,)
    assert decision_reason_codes_for_canary(
        (CANARY_FAILED,),
        normalized,
    ) == (CANARY_CONFIG_ERROR,)


def test_canary_config_marker_in_reason_is_classified_without_free_text_input() -> None:
    result = CanaryResult(
        passed=False,
        reason=(
            "canary configuration error: Unsafe case path in strict "
            "ExperimentProtocol: status=absolute_outside_roots"
        ),
    )

    normalized = normalize_canary_result(result)

    assert normalized.failure_category == CANARY_FAILURE_CATEGORY_CONFIG
    assert normalized.reason_codes == (CANARY_CONFIG_ERROR,)
    assert normalized.details["failure_category"] == CANARY_FAILURE_CATEGORY_CONFIG
    assert normalized.details["reason_codes"] == [CANARY_CONFIG_ERROR]


def test_candidate_canary_failure_keeps_algorithm_failure_code() -> None:
    result = CanaryResult(
        passed=False,
        reason="Candidate infeasible on canary_x (champion was feasible)",
        details={
            "schema_version": "scion.canary_result.v1",
            "stage": "canary",
            "failure_kind": "candidate_infeasible_champion_feasible",
            "failed_case_id": "canary_x",
        },
    )

    normalized = normalize_canary_result(result)

    assert normalized.failure_category == CANARY_FAILURE_CATEGORY_CANDIDATE
    assert normalized.reason_codes == (CANARY_FAILED,)
    assert public_canary_reason_codes(normalized) == (CANARY_FAILED,)
    assert decision_reason_codes_for_canary(
        (CANARY_FAILED,),
        normalized,
    ) == (CANARY_FAILED,)
