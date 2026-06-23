from __future__ import annotations

from dataclasses import replace
import json

import pytest

from scion.research_guidance import (
    AvoidRule,
    ContinuityRequirement,
    EvidenceRequirement,
    GuidanceBlock,
    GuidanceContext,
    MeasurementGuidanceSummary,
    ProblemResearchGuidanceProvider,
    RequiredMechanism,
    ResearchGuidanceContract,
    ResearchGuidanceValidationError,
    collect_research_guidance_errors,
    expected_research_guidance_rendered_paths,
    launch_research_guidance_payload,
    render_research_guidance_contract,
    research_guidance_contract_from_dict,
    research_guidance_contract_to_dict,
    research_guidance_projection_summary,
    validate_research_guidance_contract,
    validate_research_guidance_rendered_paths,
)


class DummyGuidanceProvider:
    def build_guidance_contract(
        self,
        context: GuidanceContext,
    ) -> ResearchGuidanceContract:
        return _valid_contract(problem_family=context.problem_family)


def test_dummy_provider_contract_validates_and_renders_generic_blocks() -> None:
    provider: ProblemResearchGuidanceProvider = DummyGuidanceProvider()
    contract = provider.build_guidance_contract(
        GuidanceContext(problem_family="dummy_family", campaign_id="campaign_alpha")
    )

    validate_research_guidance_contract(contract)
    rendered = render_research_guidance_contract(contract)

    assert rendered.rendered_paths == expected_research_guidance_rendered_paths(contract)
    assert "## Required mechanisms" in rendered.text
    assert "## Evidence requirements" in rendered.text
    assert "## Avoid rules" in rendered.text
    assert "## Continuity requirements" in rendered.text
    assert "## Guidance blocks" in rendered.text
    assert "foo_activation_probe" in rendered.text
    assert "case_alpha" in rendered.text
    assert "proposal_visibility_only: true" in rendered.text
    assert "decision_features_excluded: true" in rendered.text
    assert "excluded from DecisionFeatures" in rendered.text


def test_rendered_path_coverage_fails_closed_when_projection_is_missing() -> None:
    contract = _valid_contract()
    rendered = render_research_guidance_contract(contract)
    incomplete_paths = tuple(
        path
        for path in rendered.rendered_paths
        if path != "required_mechanisms.foo_activation_probe"
    )

    with pytest.raises(ResearchGuidanceValidationError, match="missing rendered paths"):
        validate_research_guidance_rendered_paths(contract, incomplete_paths)


def test_contract_serializes_round_trips_and_summarizes_manifest_paths() -> None:
    contract = _valid_contract()
    manifest = {
        "problem_family": contract.problem_family,
        "analysis_intent": "Dummy prepared guidance.",
        "acceptance_focus": ["Keep guidance proposal-only."],
        "research_guidance_contract": research_guidance_contract_to_dict(contract),
        "research_focus": {"current_question": contract.current_question},
    }

    parsed = research_guidance_contract_from_dict(
        manifest["research_guidance_contract"]
    )
    summary = research_guidance_projection_summary(
        manifest_path="/tmp/prepared_run_manifest.v1.json",
        manifest=manifest,
        schema_version="test.research_guidance_projection.v1",
    )

    assert parsed == contract
    assert summary["contract_present"] is True
    assert summary["contract_source"] == "typed_manifest"
    assert summary["schema_valid"] is True
    assert summary["expected_rendered_paths"] == list(
        expected_research_guidance_rendered_paths(contract)
    )
    assert summary["rendered_paths"] == summary["expected_rendered_paths"]
    assert summary["missing_rendered_paths"] == []
    assert summary["available"] is True


def test_typed_manifest_flows_into_context_manager_payload(
    tmp_path,
    monkeypatch,
) -> None:
    contract = _valid_contract()
    manifest_path = tmp_path / "prepared_run_manifest.v1.json"
    manifest = {
        "problem_family": contract.problem_family,
        "analysis_intent": "Dummy prepared guidance.",
        "acceptance_focus": ["Keep guidance proposal-only."],
        "research_guidance_contract": research_guidance_contract_to_dict(contract),
        "research_focus": {"current_question": contract.current_question},
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setenv("PREPARED_RUN_MANIFEST", str(manifest_path))

    from scion.proposal.context_manager.manager import _build_launch_research_focus

    payload = _build_launch_research_focus()
    direct_payload = launch_research_guidance_payload(
        manifest_path=manifest_path,
        manifest=manifest,
    )

    assert payload == direct_payload
    assert payload["schema_version"] == "scion.launch_research_guidance_prompt.v1"
    assert payload["contract_source"] == "typed_manifest"
    assert payload["contract_schema_version"] == contract.schema_version
    assert payload["current_question"] == contract.current_question
    assert payload["decision_boundary"] == contract.decision_boundary
    assert payload["required_mechanism_ids"] == ["foo_activation_probe"]
    assert payload["rendered_paths"] == list(
        expected_research_guidance_rendered_paths(contract)
    )
    assert "foo_activation_probe" in payload["guidance_text"]
    assert "excluded from DecisionFeatures" in payload["guidance_text"]

    from scion.proposal.engine.hypothesis_prompts import (
        _target_intent_launch_focus_required_mechanism_lines,
    )

    guard_lines = _target_intent_launch_focus_required_mechanism_lines(
        {"launch_research_focus": payload}
    )
    assert any("foo_activation_probe" in line for line in guard_lines)
    assert any(contract.current_question in line for line in guard_lines)


@pytest.mark.parametrize(
    ("case_name", "expected_error"),
    [
        (
            "missing_visibility_marker",
            "proposal_visibility_only must be true",
        ),
        (
            "duplicate_block_id",
            "duplicate guidance block id",
        ),
        (
            "empty_required_mechanism_id",
            "mechanism_id must be a non-empty string",
        ),
        (
            "unsupported_visibility_policy",
            "visibility_policy unsupported",
        ),
    ],
)
def test_invalid_contracts_fail_closed(
    case_name: str,
    expected_error: str,
) -> None:
    contract = _invalid_contract(case_name)
    errors = collect_research_guidance_errors(contract)

    assert any(expected_error in error for error in errors)
    with pytest.raises(ResearchGuidanceValidationError, match=expected_error):
        validate_research_guidance_contract(contract)
    with pytest.raises(ResearchGuidanceValidationError, match=expected_error):
        render_research_guidance_contract(contract)


def _invalid_contract(case_name: str) -> ResearchGuidanceContract:
    contract = _valid_contract()
    if case_name == "missing_visibility_marker":
        return replace(contract, proposal_visibility_only=None)
    if case_name == "duplicate_block_id":
        block = contract.guidance_blocks[0]
        return replace(
            contract,
            guidance_blocks=(
                block,
                replace(block, title="Repeated dummy block"),
            ),
        )
    if case_name == "empty_required_mechanism_id":
        return replace(
            contract,
            required_mechanisms=(
                replace(
                    contract.required_mechanisms[0],
                    mechanism_id=" ",
                ),
            ),
        )
    if case_name == "unsupported_visibility_policy":
        return replace(contract, visibility_policy="decision_visible")
    raise AssertionError(f"unknown invalid contract case: {case_name}")


def _valid_contract(problem_family: str = "dummy_family") -> ResearchGuidanceContract:
    return ResearchGuidanceContract(
        schema_version="research-guidance-v1",
        problem_family=problem_family,
        current_question="Which dummy activation path should be probed next?",
        required_mechanisms=(
            RequiredMechanism(
                mechanism_id="foo_activation_probe",
                category="activation_probe",
                description="Observe whether the named probe becomes active.",
                required_observations=("probe_active", "effect_observed"),
            ),
        ),
        evidence_requirements=(
            EvidenceRequirement(
                requirement_id="foo_activation_evidence",
                category="activation_evidence",
                description="Pair activation with effect evidence.",
                mechanism_ids=("foo_activation_probe",),
                protected_items=("case_alpha",),
                required_fields=("activation_status", "effect_delta"),
            ),
        ),
        avoid_rules=(
            AvoidRule(
                rule_id="avoid_unchanged_repeat",
                category="repeat_guard",
                description="Do not repeat an unchanged probe after rejected evidence.",
                applies_to=("foo_activation_probe",),
            ),
        ),
        continuity_requirements=(
            ContinuityRequirement(
                requirement_id="continue_probe_lineage",
                category="lineage",
                description="Carry forward the last probe lesson before proposing.",
                related_ids=("foo_activation_probe", "case_alpha"),
            ),
        ),
        guidance_blocks=(
            GuidanceBlock(
                block_id="dummy_focus_block",
                category="proposal_focus",
                title="Dummy focus",
                lines=(
                    "Prefer a measurable activation path.",
                    "Tie observations to case_alpha.",
                ),
            ),
        ),
        measurement_summary=MeasurementGuidanceSummary(
            summary_id="dummy_measurement_summary",
            summary="Use paired dummy deltas only as proposal guidance.",
            metric_names=("dummy_delta",),
            limitations=("proposal-only summary",),
        ),
        decision_boundary="Proposal guidance only; excluded from DecisionFeatures.",
    )
