"""Tests for T19: ProposalEngine Pydantic validation layer."""
from __future__ import annotations

import pytest

from scion.proposal.engine import ProposalValidationError, _parse_hypothesis, _parse_patch


# ---------------------------------------------------------------------------
# HypothesisProposalInput validation tests
# ---------------------------------------------------------------------------

def test_hypothesis_validation_missing_fields():
    """Empty hypothesis_text should raise ProposalValidationError."""
    raw = {
        "hypothesis_text": "",
        "change_locus": "order_level",
        "action": "modify",
        "target_file": "operators/foo.py",
    }
    with pytest.raises(ProposalValidationError):
        _parse_hypothesis(raw)


def test_hypothesis_validation_whitespace_only():
    """Whitespace-only hypothesis_text should raise ProposalValidationError."""
    raw = {
        "hypothesis_text": "   ",
        "change_locus": "order_level",
        "action": "create_new",
    }
    with pytest.raises(ProposalValidationError):
        _parse_hypothesis(raw)


def test_hypothesis_validation_empty_change_locus():
    """Empty change_locus should raise ProposalValidationError."""
    raw = {
        "hypothesis_text": "Some hypothesis text.",
        "change_locus": "",
        "action": "create_new",
    }
    with pytest.raises(ProposalValidationError):
        _parse_hypothesis(raw)


def test_hypothesis_validation_bad_action():
    """Invalid action value should raise ProposalValidationError."""
    raw = {
        "hypothesis_text": "Some hypothesis text.",
        "change_locus": "order_level",
        "action": "invalid",
    }
    with pytest.raises(ProposalValidationError):
        _parse_hypothesis(raw)


def test_valid_hypothesis_passes_validation():
    """Valid hypothesis dict should return a HypothesisProposal."""
    raw = {
        "hypothesis_text": "A valid hypothesis exploring 2-opt moves.",
        "change_locus": "local_search",
        "action": "create_new",
        "target_file": None,
        "predicted_direction": "improve",
        "target_weakness": "slow convergence",
        "expected_effect": "faster convergence",
        "suggested_weight": 0.5,
    }
    result = _parse_hypothesis(raw)
    assert result.hypothesis_text == raw["hypothesis_text"]
    assert result.change_locus == "local_search"
    assert result.action == "create_new"
    assert result.suggested_weight == 0.5


def test_valid_hypothesis_modify_action():
    """modify action with target_file should pass validation."""
    raw = {
        "hypothesis_text": "Improve the existing move operator.",
        "change_locus": "vehicle_level",
        "action": "modify",
        "target_file": "operators/move.py",
    }
    result = _parse_hypothesis(raw)
    assert result.action == "modify"
    assert result.target_file == "operators/move.py"


def test_valid_hypothesis_remove_action():
    """remove action should pass validation."""
    raw = {
        "hypothesis_text": "Remove the underperforming swap operator.",
        "change_locus": "order_level",
        "action": "remove",
        "target_file": "operators/swap.py",
    }
    result = _parse_hypothesis(raw)
    assert result.action == "remove"


# ---------------------------------------------------------------------------
# PatchProposalInput validation tests
# ---------------------------------------------------------------------------

def test_patch_validation_missing_code():
    """Empty code_content should raise ProposalValidationError."""
    raw = {
        "file_path": "operators/new_op.py",
        "action": "create",
        "code_content": "",
    }
    with pytest.raises(ProposalValidationError):
        _parse_patch(raw)


def test_patch_validation_missing_file_path():
    """Empty file_path should raise ProposalValidationError."""
    raw = {
        "file_path": "",
        "action": "modify",
        "code_content": "class Foo:\n    pass\n",
    }
    with pytest.raises(ProposalValidationError):
        _parse_patch(raw)


def test_patch_validation_whitespace_code():
    """Whitespace-only code_content should raise ProposalValidationError."""
    raw = {
        "file_path": "operators/new_op.py",
        "action": "create",
        "code_content": "   \n  ",
    }
    with pytest.raises(ProposalValidationError):
        _parse_patch(raw)


def test_valid_patch_passes_validation():
    """Valid patch dict should return a PatchProposal."""
    raw = {
        "file_path": "operators/local_search.py",
        "action": "modify",
        "code_content": "class LocalSearch:\n    def execute(self, solution, rng):\n        return solution\n",
        "test_hint": None,
    }
    result = _parse_patch(raw)
    assert result.file_path == "operators/local_search.py"
    assert result.action == "modify"
    assert "LocalSearch" in result.code_content


def test_valid_patch_with_test_hint():
    """Patch with test_hint should pass validation."""
    raw = {
        "file_path": "operators/new_op.py",
        "action": "create",
        "code_content": "class NewOp:\n    def execute(self, solution, rng):\n        return solution\n",
        "test_hint": "Check feasibility",
    }
    result = _parse_patch(raw)
    assert result.test_hint == "Check feasibility"
