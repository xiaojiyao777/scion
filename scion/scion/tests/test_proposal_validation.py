"""Tests for T19: ProposalEngine Pydantic validation layer."""

from __future__ import annotations

import pytest

from scion.proposal.engine import (
    ProposalValidationError,
    _parse_hypothesis,
    _parse_patch,
)
from scion.proposal.schemas import (
    HYPOTHESIS_PROPOSAL_SCHEMA,
    HypothesisProposalInput,
)

def _minimal_hypothesis(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "hypothesis_text": "Try a focused local-search change.",
        "change_locus": "local_search",
        "action": "create_new",
        "predicted_direction": "improve",
        "target_weakness": "slow convergence",
        "expected_effect": "faster convergence",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# HypothesisProposalInput validation tests
# ---------------------------------------------------------------------------


def test_minimal_hypothesis_uses_the_single_parser_path():
    raw = _minimal_hypothesis(suggested_weight=0.5)
    result = _parse_hypothesis(raw)
    assert result.hypothesis_text == raw["hypothesis_text"]
    assert result.predicted_direction == "improve"
    assert result.suggested_weight == 0.5


def test_hypothesis_parser_rejects_descriptive_change_locus_suffix() -> None:
    with pytest.raises(
        ProposalValidationError,
        match="must exactly match one provider-visible research surface",
    ):
        _parse_hypothesis(
            _minimal_hypothesis(
                change_locus="solver_design local-search/VNS neighborhood set",
            ),
            allowed_change_loci=("solver_design",),
        )


@pytest.mark.parametrize(
    "missing_field",
    ["hypothesis_text", "change_locus", "action", "predicted_direction", "target_weakness", "expected_effect"],
)
def test_hypothesis_rejects_each_missing_required_field(missing_field: str):
    raw = _minimal_hypothesis()
    del raw[missing_field]
    with pytest.raises(ProposalValidationError):
        _parse_hypothesis(raw)


@pytest.mark.parametrize(
    "removed_field",
    [
        "novelty_signature", "material_difference", "branch_lesson_usage",
        "mechanism_changes", "structural_fingerprint", "target_objectives",
        "expected_telemetry", "mechanism_summary", "failure_modes",
        "risk_flags", "target_runtime_effect", "invariants", "resource_strategy",
    ],
)
def test_hypothesis_rejects_removed_provider_fields(removed_field: str):
    raw = _minimal_hypothesis(**{removed_field: {"legacy": True}})
    with pytest.raises(ProposalValidationError):
        _parse_hypothesis(raw)


@pytest.mark.parametrize("action", ["modify", "remove"])
def test_hypothesis_file_actions_require_target_file(action: str):
    with pytest.raises(ProposalValidationError):
        _parse_hypothesis(_minimal_hypothesis(action=action))


def test_hypothesis_schema_is_exactly_the_model_schema():
    assert HYPOTHESIS_PROPOSAL_SCHEMA == HypothesisProposalInput.model_json_schema()
    assert HYPOTHESIS_PROPOSAL_SCHEMA["additionalProperties"] is False


# ---------------------------------------------------------------------------
# PatchProposalInput validation tests
# ---------------------------------------------------------------------------


def test_patch_validation_missing_code():
    """Empty full-file content should raise ProposalValidationError."""
    raw = {
        "file_path": "operators/new_op.py",
        "action": "create",
        "edit_intent": "full_file",
        "source_digest": None,
        "content_after": "",
        "full_file_reason": "Create the approved operator.",
        "evidence_refs": [],
    }
    with pytest.raises(ProposalValidationError):
        _parse_patch(raw)


def test_patch_validation_missing_file_path():
    """Empty file_path should raise ProposalValidationError."""
    raw = {
        "file_path": "",
        "action": "create",
        "edit_intent": "full_file",
        "source_digest": None,
        "content_after": "class Foo:\n    pass\n",
        "full_file_reason": "Create the approved operator.",
        "evidence_refs": [],
    }
    with pytest.raises(ProposalValidationError):
        _parse_patch(raw)


def test_patch_validation_whitespace_code():
    """Whitespace-only full-file content should raise ProposalValidationError."""
    raw = {
        "file_path": "operators/new_op.py",
        "action": "create",
        "edit_intent": "full_file",
        "source_digest": None,
        "content_after": "   \n  ",
        "full_file_reason": "Create the approved operator.",
        "evidence_refs": [],
    }
    with pytest.raises(ProposalValidationError):
        _parse_patch(raw)


def test_valid_patch_passes_validation():
    """Valid patch dict should return a PatchProposal."""
    raw = {
        "file_path": "operators/new_local_search.py",
        "action": "create",
        "edit_intent": "full_file",
        "source_digest": None,
        "content_after": "class LocalSearch:\n    def execute(self, solution, rng):\n        return solution\n",
        "full_file_reason": "Create the approved local-search operator.",
        "evidence_refs": [],
        "test_hint": None,
    }
    result = _parse_patch(raw)
    assert result.file_path == "operators/new_local_search.py"
    assert result.action == "create"
    assert "LocalSearch" in result.code_content


def test_valid_patch_with_test_hint():
    """Patch with test_hint should pass validation."""
    raw = {
        "file_path": "operators/new_op.py",
        "action": "create",
        "edit_intent": "full_file",
        "source_digest": None,
        "content_after": "class NewOp:\n    def execute(self, solution, rng):\n        return solution\n",
        "full_file_reason": "Create the approved operator.",
        "evidence_refs": [],
        "test_hint": "Check feasibility",
    }
    result = _parse_patch(raw)
    assert result.test_hint == "Check feasibility"


def test_patch_rejects_additional_changes_json_string_for_shape_retry():
    """Model responses must repair additional_changes shape instead of host parsing."""
    raw = {
        "file_path": "policies/baseline_algorithm.py",
        "action": "modify",
        "edit_intent": "full_file",
        "source_digest": "abc123",
        "content_after": "def solve(instance, rng, time_limit_sec, context):\n    return None\n",
        "full_file_reason": "Implement the approved solver change.",
        "evidence_refs": [],
        "additional_changes": (
            '[{"file_path": "policies/baseline_modules/helper.py", '
            '"action": "create", '
            '"edit_intent": "full_file", '
            '"source_digest": null, '
            '"content_after": "def helper():\\n    return 1\\n"}]'
        ),
    }
    with pytest.raises(ProposalValidationError) as excinfo:
        _parse_patch(raw)

    message = str(excinfo.value)
    assert "additional_changes must be a JSON array" in message
    assert "typed edit objects" in message


def test_patch_rejects_unparseable_additional_changes_string():
    raw = {
        "file_path": "policies/baseline_algorithm.py",
        "action": "modify",
        "edit_intent": "full_file",
        "source_digest": "abc123",
        "content_after": "def solve(instance, rng, time_limit_sec, context):\n    return None\n",
        "full_file_reason": "Implement the approved solver change.",
        "evidence_refs": [],
        "additional_changes": "not-json",
    }
    with pytest.raises(ProposalValidationError, match="additional_changes"):
        _parse_patch(raw)


def test_patch_rejects_unknown_edit_fields_with_additional_changes_guidance():
    raw = {
        "file_path": "policies/baseline_algorithm.py",
        "action": "modify",
        "edit_intent": "full_file",
        "source_digest": "abc123",
        "content_after": "def solve(instance, rng, time_limit_sec, context):\n    return None\n",
        "full_file_reason": "Implement the approved solver change.",
        "evidence_refs": [],
        "old_string2": "return None",
        "new_string2": "return context.nearest_neighbor()",
    }

    with pytest.raises(ProposalValidationError) as excinfo:
        _parse_patch(raw)

    message = str(excinfo.value)
    assert "Unsupported patch field" in message
    assert "old_string2" in message
    assert "new_string2" in message
    assert "additional_changes[]" in message
