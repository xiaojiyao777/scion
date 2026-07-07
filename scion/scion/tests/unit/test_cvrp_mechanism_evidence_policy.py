from __future__ import annotations

from types import SimpleNamespace

import pytest

from scion.core.branch_cards import branch_hygiene_context
from scion.core.branch_hygiene import branch_requires_same_mechanism_followup
from scion.core.decision_lifecycle_actions import (
    update_branch_screening_evidence_summary,
)
from scion.core.mechanism_evidence_contract import (
    mechanism_evidence_contract_for_protocol,
)
from scion.core.models import (
    Branch,
    BranchState,
    EvalStats,
    ExperimentStage,
    MechanismChange,
    ProtocolResult,
)
from scion.problem.bridge import load_problem_spec_v1_from_yaml
from scion.runtime.telemetry_guard import build_telemetry_guard_summary
from scion.runtime.telemetry_guard.summary_signals import (
    ACTIVATED_NO_POSITIVE_EFFECT,
    POLICY_OUTCOME_OBSERVED,
)
from scion.tests.unit.research_surface_helpers import _CVRP_ROOT


_POLICY_MECHANISM = "post_vns_best_anchor_acceptance_guard"


def test_generic_default_missing_effect_policy_is_unchanged_without_provider() -> None:
    summary = build_telemetry_guard_summary(
        candidate_runtimes=[{"mechanism_activation": {"target_probe": 1}}],
        problem_spec=_generic_mechanism_probe_spec(),
        selected_surface="solver",
        declared_mechanisms=[MechanismChange(id="target_probe", change_type="modify")],
        effect_observation_required=False,
    )

    diagnostic = summary["mechanism_diagnostics"][0]

    assert diagnostic["diagnostic_type"] == "effect_attribution_missing"
    assert diagnostic["diagnostic_kind"] == ACTIVATED_NO_POSITIVE_EFFECT
    assert diagnostic["telemetry_outcome"] == "effect_attribution_missing"
    assert "context.record_move" in " ".join(diagnostic["repair_guidance"])
    warning = _mechanism_effect_warning(summary, "target_probe")
    assert warning is not None
    assert warning["repairable"] is True


@pytest.mark.parametrize("effect_observation", ["missing", "zero"])
def test_cvrp_policy_rewrites_successor44_missing_or_zero_direct_effect(
    effect_observation: str,
) -> None:
    summary = build_telemetry_guard_summary(
        candidate_runtimes=[
            _cvrp_policy_runtime(
                _POLICY_MECHANISM,
                include_zero_effect=effect_observation == "zero",
            )
        ],
        problem_spec=load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml"),
        selected_surface="solver_design",
        declared_mechanisms=[
            MechanismChange(id=_POLICY_MECHANISM, change_type="add")
        ],
        effect_observation_required=False,
    )

    diagnostic = summary["mechanism_diagnostics"][0]
    guidance = " ".join(diagnostic["repair_guidance"])

    assert diagnostic["diagnostic_type"] == POLICY_OUTCOME_OBSERVED
    assert diagnostic["diagnostic_kind"] == POLICY_OUTCOME_OBSERVED
    assert diagnostic["telemetry_outcome"] == POLICY_OUTCOME_OBSERVED
    assert diagnostic["repairable"] is False
    assert diagnostic["policy_outcome_observed"] is True
    assert "context.record_move" not in guidance
    assert "formal per-case outcome evidence" in guidance
    assert not [
        warning
        for warning in summary["warnings"]
        if warning["code"] == "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED"
        and warning.get("mechanism") == _POLICY_MECHANISM
    ]


def test_cvrp_policy_leaves_other_mechanisms_on_generic_missing_effect_path() -> None:
    mechanism = "other_acceptance_probe"
    summary = build_telemetry_guard_summary(
        candidate_runtimes=[_cvrp_policy_runtime(mechanism)],
        problem_spec=load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml"),
        selected_surface="solver_design",
        declared_mechanisms=[MechanismChange(id=mechanism, change_type="add")],
        effect_observation_required=False,
    )

    diagnostic = summary["mechanism_diagnostics"][0]

    assert diagnostic["diagnostic_type"] == "effect_attribution_missing"
    assert diagnostic["diagnostic_kind"] == ACTIVATED_NO_POSITIVE_EFFECT
    assert "context.record_move" in " ".join(diagnostic["repair_guidance"])
    warning = _mechanism_effect_warning(summary, mechanism)
    assert warning is not None
    assert warning["repairable"] is True


def test_policy_outcome_contract_does_not_require_branch_followup() -> None:
    summary = build_telemetry_guard_summary(
        candidate_runtimes=[_cvrp_policy_runtime(_POLICY_MECHANISM)],
        problem_spec=load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml"),
        selected_surface="solver_design",
        declared_mechanisms=[
            MechanismChange(id=_POLICY_MECHANISM, change_type="add")
        ],
        effect_observation_required=False,
    )
    protocol = _protocol_with_guard(summary)
    branch = Branch(
        branch_id="policy-outcome-observed",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        branch_code_status="clean",
        last_screening_feedback_tier="inactive",
    )

    contract = mechanism_evidence_contract_for_protocol(protocol)
    update_branch_screening_evidence_summary(
        branch,
        protocol_result=protocol,
        screening_feedback=SimpleNamespace(
            tier="inactive",
            pair_wins=0,
            pair_losses=0,
            pair_ties=1,
            activation_status="observed",
            effect_status=POLICY_OUTCOME_OBSERVED,
            opportunity_status="unknown",
        ),
    )
    context = branch_hygiene_context(branch)

    assert contract["primary_status"] == POLICY_OUTCOME_OBSERVED
    assert contract["followup_required"] is False
    assert contract["repairable"] is False
    assert contract["repair_mechanism_ids"] == []
    assert branch_requires_same_mechanism_followup(branch) is False
    assert context["mechanism_followup_required"] is False
    assert context["mechanism_contract_repair_ids"] == []


def _generic_mechanism_probe_spec() -> SimpleNamespace:
    return SimpleNamespace(
        research_surfaces=[
            SimpleNamespace(
                name="solver",
                evidence=SimpleNamespace(
                    activation_runtime_fields={
                        "{mechanism}": ["mechanism_activation"]
                    },
                    effect_probe_runtime_fields={
                        "{mechanism}": ["mechanism_effect"]
                    },
                ),
            )
        ]
    )


def _cvrp_policy_runtime(
    mechanism: str,
    *,
    include_zero_effect: bool = False,
) -> dict[str, object]:
    runtime: dict[str, object] = {
        "solver_algorithm_context_records": {
            f"{mechanism}_iterations": 3,
        },
        "solver_algorithm_phase_runtime_ms": {
            mechanism: 1.25,
        },
    }
    if include_zero_effect:
        runtime["solver_algorithm_phase_improvement_counts"] = {mechanism: 0}
        runtime["solver_algorithm_phase_best_delta"] = {mechanism: 0.0}
    return runtime


def _mechanism_effect_warning(summary: dict, mechanism: str) -> dict | None:
    for warning in summary.get("warnings") or ():
        if (
            isinstance(warning, dict)
            and warning.get("code") == "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED"
            and warning.get("mechanism") == mechanism
        ):
            return warning
    return None


def _protocol_with_guard(guard: dict) -> ProtocolResult:
    return ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=1,
            wins=0,
            losses=0,
            ties=1,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
        ),
        gate_outcome="continue",
        reason_codes=(),
        exposed_summary="screening policy mechanism evidence",
        raw_metrics_ref="/tmp/metrics.json",
        candidate_surface_runtime_summary={"telemetry_guard": guard},
    )
