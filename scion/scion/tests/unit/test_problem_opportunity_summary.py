from __future__ import annotations

from scion.opportunity import (
    AvoidedMechanismSummary,
    MechanismEvidenceSummary,
    OpportunityAxis,
    ProblemOpportunitySummary,
    ProtectedCaseSummary,
    redact_problem_opportunity_payload,
)


def test_problem_opportunity_summary_is_proposal_only_and_redacted() -> None:
    summary = ProblemOpportunitySummary(
        problem_family="demo",
        objective="score",
        residual_opportunity=(
            OpportunityAxis(
                axis_id="residual_headroom",
                metric="score",
                status="available",
                summary="bounded improvement remains plausible",
                reason_codes=("HEADROOM",),
            ),
        ),
        mechanism_evidence=(
            MechanismEvidenceSummary(
                mechanism_family="bounded_operator",
                evidence_status="needs_direct_effect",
                opportunity_status="eligible",
                summary="requires direct objective effect evidence",
                reason_codes=("DIRECT_EFFECT_REQUIRED",),
            ),
        ),
        protected_cases=(
            ProtectedCaseSummary(
                case_id="protected-a",
                reason="regression sentinel",
                required_evidence=("objective_delta",),
            ),
        ),
        default_avoid=(
            AvoidedMechanismSummary(
                mechanism_family="repeated_operator",
                reason="prior no-effect evidence",
            ),
        ),
    )

    payload = summary.to_payload()

    assert payload["schema_version"] == "scion.problem_opportunity_summary.v1"
    assert payload["proposal_visibility_only"] is True
    assert payload["decision_features_excluded"] is True
    assert payload["decision_input_policy"] == "excluded_from_decision_features"
    assert payload["residual_opportunity"][0]["axis_id"] == "residual_headroom"
    assert payload["mechanism_evidence"][0]["mechanism_family"] == (
        "bounded_operator"
    )
    assert payload["protected_cases"][0]["case_id"] == "protected-a"


def test_problem_opportunity_redaction_drops_raw_and_holdout_fields() -> None:
    payload = redact_problem_opportunity_payload(
        {
            "safe": "keep",
            "raw_pair_rows": [{"case": "hidden"}],
            "nested": {
                "summary": "keep nested",
                "pair_evidence": [{"row": "hidden"}],
                "validation_case_details": "hidden",
                "prompt_ratios": {"x": 1},
                "llm_text": "hidden",
            },
        }
    )

    assert payload == {"safe": "keep", "nested": {"summary": "keep nested"}}
