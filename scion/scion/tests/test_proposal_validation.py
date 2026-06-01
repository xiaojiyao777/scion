"""Tests for T19: ProposalEngine Pydantic validation layer."""
from __future__ import annotations

import pytest

from scion.proposal.context_manager import _format_hypothesis
from scion.proposal.engine import ProposalValidationError, _parse_hypothesis, _parse_patch
from scion.proposal.schemas import (
    HYPOTHESIS_PROPOSAL_SCHEMA,
    PATCH_PROPOSAL_SCHEMA,
    HypothesisProposalInput,
)


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


def test_hypothesis_validation_bad_predicted_direction():
    """Free-form predicted_direction should fail at proposal parsing."""
    raw = {
        "hypothesis_text": "Some hypothesis text.",
        "change_locus": "order_level",
        "action": "modify",
        "target_file": "operators/foo.py",
        "predicted_direction": "cost-v2",
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


def test_hypothesis_mechanism_changes_parse_and_format():
    raw = {
        "hypothesis_text": "Modify a declared generic mechanism.",
        "change_locus": "solver",
        "action": "modify",
        "target_file": "policies/solver.py",
        "mechanism_changes": [
            {"id": "search_seed", "change_type": "modify"},
        ],
    }

    result = _parse_hypothesis(raw)

    assert result.mechanism_changes[0].id == "search_seed"
    assert result.mechanism_changes[0].change_type == "modify"
    formatted = _format_hypothesis(result)
    assert "mechanism_changes:" in formatted
    assert "search_seed" in formatted


def test_hypothesis_mechanism_changes_deduplicate_exact_duplicates():
    raw = {
        "hypothesis_text": "Modify a declared generic mechanism.",
        "change_locus": "solver",
        "action": "modify",
        "target_file": "policies/solver.py",
        "mechanism_changes": [
            {"id": "search_seed", "change_type": "modify"},
            {"id": "search_seed", "change_type": "modify"},
        ],
    }

    result = _parse_hypothesis(raw)

    assert [(c.id, c.change_type) for c in result.mechanism_changes] == [
        ("search_seed", "modify")
    ]


def test_hypothesis_mechanism_changes_conflicting_duplicate_normalizes_with_audit():
    raw = {
        "hypothesis_text": "Modify a declared generic mechanism.",
        "change_locus": "solver",
        "action": "modify",
        "target_file": "policies/solver.py",
        "mechanism_changes": [
            {"id": "search_seed", "change_type": "add"},
            {"id": "search_seed", "change_type": "modify"},
        ],
    }

    result = _parse_hypothesis(raw)

    assert [(c.id, c.change_type) for c in result.mechanism_changes] == [
        ("search_seed", "add")
    ]
    assert result.schema_repair_attribution
    repair = result.schema_repair_attribution[0]
    assert repair["diagnostic_code"] == "mechanism_changes_duplicate_id_conflict"
    assert repair["input_change_types"] == ["add", "modify"]
    assert repair["selected_change_type"] == "add"
    assert repair["schema_only_repair"] is True
    assert repair["quality_block"] is False


def test_hypothesis_mechanism_changes_integrate_modify_selects_modify():
    raw = {
        "hypothesis_text": "Modify a declared generic mechanism.",
        "change_locus": "solver",
        "action": "modify",
        "target_file": "policies/solver.py",
        "mechanism_changes": [
            {"id": "search_seed", "change_type": "integrate"},
            {"id": "search_seed", "change_type": "modify"},
        ],
    }

    result = _parse_hypothesis(raw)

    assert [(c.id, c.change_type) for c in result.mechanism_changes] == [
        ("search_seed", "modify")
    ]
    assert result.schema_repair_attribution[0]["selected_change_type"] == "modify"


@pytest.mark.parametrize(
    ("raw_change_type", "normalized_change_type"),
    [
        ("parameterize", "modify"),
        ("tune", "modify"),
        ("telemetry_wiring", "modify"),
    ],
)
def test_hypothesis_mechanism_change_type_alias_normalizes_with_audit(
    raw_change_type: str,
    normalized_change_type: str,
):
    raw = {
        "hypothesis_text": "Modify a declared generic mechanism.",
        "change_locus": "solver",
        "action": "modify",
        "target_file": "policies/solver.py",
        "mechanism_changes": [
            {"id": "search_seed", "change_type": raw_change_type},
        ],
    }

    direct = HypothesisProposalInput.model_validate(raw)
    result = _parse_hypothesis(raw)

    assert direct.mechanism_changes[0].change_type == normalized_change_type
    assert [(c.id, c.change_type) for c in result.mechanism_changes] == [
        ("search_seed", normalized_change_type)
    ]
    repair = next(
        item
        for item in result.schema_repair_attribution
        if item.get("repair_kind") == "mechanism_change_type_alias_normalized"
    )
    assert repair["original_change_type"] == raw_change_type
    assert repair["normalized_change_type"] == normalized_change_type
    assert repair["schema_only_repair"] is True
    assert repair["quality_block"] is False


def test_hypothesis_duplicate_id_with_parameterize_alias_canonicalizes_legal_action():
    raw = {
        "hypothesis_text": "Modify a declared generic mechanism.",
        "change_locus": "solver",
        "action": "modify",
        "target_file": "policies/solver.py",
        "mechanism_changes": [
            {"id": "search_seed", "change_type": "modify"},
            {"id": "search_seed", "change_type": "integrate"},
            {"id": "search_seed", "change_type": "parameterize"},
        ],
    }

    result = _parse_hypothesis(raw)

    assert [(c.id, c.change_type) for c in result.mechanism_changes] == [
        ("search_seed", "modify")
    ]
    repairs = list(result.schema_repair_attribution)
    assert any(
        item.get("repair_kind") == "mechanism_change_type_alias_normalized"
        and item.get("original_change_type") == "parameterize"
        and item.get("normalized_change_type") == "modify"
        for item in repairs
    )
    duplicate = next(
        item
        for item in repairs
        if item.get("diagnostic_code") == "mechanism_changes_duplicate_id_conflict"
    )
    assert duplicate["input_change_types"] == [
        "modify",
        "integrate",
        "parameterize",
    ]
    assert duplicate["normalized_change_types"] == ["modify", "integrate", "modify"]
    assert duplicate["selected_change_type"] == "modify"
    assert duplicate["quality_block"] is False


def test_mechanism_change_schema_guidance_keeps_action_labels_out_of_enum():
    change_type_schema = HYPOTHESIS_PROPOSAL_SCHEMA["properties"][
        "mechanism_changes"
    ]["items"]["properties"]["change_type"]
    patch_change_type_schema = PATCH_PROPOSAL_SCHEMA["properties"][
        "mechanism_changes"
    ]["items"]["properties"]["change_type"]

    assert change_type_schema["enum"] == [
        "add",
        "modify",
        "replace",
        "remove",
        "integrate",
    ]
    assert patch_change_type_schema["enum"] == change_type_schema["enum"]
    assert "parameterize" not in change_type_schema["enum"]
    assert "telemetry_wiring" not in change_type_schema["enum"]
    assert "not change_type values" in change_type_schema["description"]


def test_hypothesis_mechanism_changes_reject_bad_id_and_type():
    raw = {
        "hypothesis_text": "Modify a declared generic mechanism.",
        "change_locus": "solver",
        "action": "modify",
        "target_file": "policies/solver.py",
        "mechanism_changes": [
            {"id": "SearchSeed", "change_type": "modify"},
        ],
    }
    with pytest.raises(ProposalValidationError, match="mechanism id"):
        _parse_hypothesis(raw)

    raw["mechanism_changes"] = [
        {"id": "search_seed", "change_type": "tweak"},
    ]
    with pytest.raises(ProposalValidationError):
        _parse_hypothesis(raw)


def test_hypothesis_runtime_intent_fields_parse_and_format():
    """Runtime intent fields should round-trip into HypothesisProposal context text."""
    raw = {
        "hypothesis_text": "Bound route-pair exploration with candidate filtering.",
        "change_locus": "local_search",
        "action": "create_new",
        "target_runtime_effect": "neutral: same solve budget with fewer evaluated pairs",
        "complexity_claim": "O(k * routes) candidates with k <= 8, no all-pairs scan",
        "runtime_budget_strategy": "top-k route pairs, early exit after first feasible improvement",
        "expected_telemetry": {
            "activity": ["search_iterations"],
            "effect": ["accepted_improvements"],
        },
        "novelty_signature": {"selected_components": ["route_pair_swap"]},
    }

    result = _parse_hypothesis(raw)

    assert result.target_runtime_effect == raw["target_runtime_effect"]
    assert result.complexity_claim == raw["complexity_claim"]
    assert result.runtime_budget_strategy == raw["runtime_budget_strategy"]
    assert result.expected_telemetry == raw["expected_telemetry"]
    assert result.novelty_signature == raw["novelty_signature"]

    formatted = _format_hypothesis(result)
    assert "target_runtime_effect: neutral" in formatted
    assert "complexity_claim: O(k * routes)" in formatted
    assert "runtime_budget_strategy: top-k route pairs" in formatted
    assert "expected_telemetry:" in formatted
    assert "hypothesis_metadata_novelty_signature:" in formatted
    assert "do not copy novelty_signature into code" in formatted


def test_hypothesis_runtime_intent_fields_default_when_missing():
    """Old LLM outputs without runtime intent fields remain valid."""
    result = _parse_hypothesis({
        "hypothesis_text": "Improve the existing move operator.",
        "change_locus": "vehicle_level",
        "action": "modify",
        "target_file": "operators/move.py",
    })

    assert result.target_runtime_effect is None
    assert result.complexity_claim is None
    assert result.runtime_budget_strategy is None
    assert result.expected_telemetry == {}
    assert result.novelty_signature == {}
    assert result.mechanism_changes == ()
    assert "target_runtime_effect" not in _format_hypothesis(result)


def test_hypothesis_schema_exposes_optional_runtime_intent_fields():
    """JSON schema advertises runtime intent fields without making them required."""
    required = set(HYPOTHESIS_PROPOSAL_SCHEMA["required"])
    properties = HYPOTHESIS_PROPOSAL_SCHEMA["properties"]

    for field_name in (
        "target_runtime_effect",
        "complexity_claim",
        "runtime_budget_strategy",
        "expected_telemetry",
        "novelty_signature",
        "mechanism_changes",
    ):
        assert field_name in properties
        assert field_name not in required


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
        "file_path": "operators/new_local_search.py",
        "action": "create",
        "code_content": "class LocalSearch:\n    def execute(self, solution, rng):\n        return solution\n",
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
        "code_content": "class NewOp:\n    def execute(self, solution, rng):\n        return solution\n",
        "test_hint": "Check feasibility",
    }
    result = _parse_patch(raw)
    assert result.test_hint == "Check feasibility"


def test_patch_mechanism_changes_parse_and_schema_is_optional():
    raw = {
        "file_path": "policies/solver.py",
        "action": "modify",
        "code_content": "VALUE = 1\n",
        "mechanism_changes": [
            {"id": "search_seed", "change_type": "integrate"},
        ],
    }

    result = _parse_patch(
        raw,
        context={"allow_host_internal_full_file_modify": True},
    )

    assert result.mechanism_changes[0].id == "search_seed"
    assert result.mechanism_changes[0].change_type == "integrate"
    assert "mechanism_changes" in PATCH_PROPOSAL_SCHEMA["properties"]
    assert "mechanism_changes" not in PATCH_PROPOSAL_SCHEMA["required"]


def test_patch_mechanism_changes_conflicting_duplicate_normalizes_with_audit():
    raw = {
        "file_path": "policies/solver.py",
        "action": "modify",
        "code_content": "VALUE = 1\n",
        "mechanism_changes": [
            {"id": "search_seed", "change_type": "integrate"},
            {"id": "search_seed", "change_type": "modify"},
        ],
    }

    result = _parse_patch(
        raw,
        context={"allow_host_internal_full_file_modify": True},
    )

    assert [(c.id, c.change_type) for c in result.mechanism_changes] == [
        ("search_seed", "modify")
    ]
    assert result.repair_attribution
    repair = result.repair_attribution[0]
    assert repair["diagnostic_code"] == "mechanism_changes_duplicate_id_conflict"
    assert repair["quality_block"] is False


@pytest.mark.parametrize(
    ("raw_change_type", "normalized_change_type"),
    [
        ("parameterize", "modify"),
        ("tune", "modify"),
        ("telemetry_wiring", "modify"),
    ],
)
def test_patch_mechanism_change_type_alias_normalizes_with_audit(
    raw_change_type: str,
    normalized_change_type: str,
):
    raw = {
        "file_path": "policies/solver.py",
        "action": "modify",
        "code_content": "VALUE = 1\n",
        "mechanism_changes": [
            {"id": "search_seed", "change_type": raw_change_type},
        ],
    }

    result = _parse_patch(
        raw,
        context={"allow_host_internal_full_file_modify": True},
    )

    assert [(c.id, c.change_type) for c in result.mechanism_changes] == [
        ("search_seed", normalized_change_type)
    ]
    repair = next(
        item
        for item in result.repair_attribution
        if item.get("repair_kind") == "mechanism_change_type_alias_normalized"
    )
    assert repair["original_value"] == raw_change_type
    assert repair["normalized_value"] == normalized_change_type
    assert repair["schema_only_repair"] is True
    assert repair["quality_block"] is False


def test_patch_mechanism_changes_reject_bad_id():
    raw = {
        "file_path": "policies/solver.py",
        "action": "modify",
        "code_content": "VALUE = 1\n",
        "mechanism_changes": [
            {"id": "bad-id", "change_type": "modify"},
        ],
    }

    with pytest.raises(ProposalValidationError, match="mechanism id"):
        _parse_patch(raw, context={"allow_host_internal_full_file_modify": True})


def test_patch_rejects_additional_changes_json_string_for_shape_retry():
    """Model responses must repair additional_changes shape instead of host parsing."""
    raw = {
        "file_path": "policies/baseline_algorithm.py",
        "action": "modify",
        "code_content": "def solve(instance, rng, time_limit_sec, context):\n    return None\n",
        "additional_changes": (
            '[{"file_path": "policies/baseline_modules/helper.py", '
            '"action": "create", '
            '"code_content": "def helper():\\n    return 1\\n"}]'
        ),
    }
    with pytest.raises(ProposalValidationError) as excinfo:
        _parse_patch(raw)

    message = str(excinfo.value)
    assert "additional_changes must be a JSON array" in message
    assert "Shape-only retry" in message
    assert "mechanism_changes ids" in message


def test_patch_rejects_unparseable_additional_changes_string():
    raw = {
        "file_path": "policies/baseline_algorithm.py",
        "action": "modify",
        "code_content": "def solve(instance, rng, time_limit_sec, context):\n    return None\n",
        "additional_changes": "not-json",
    }
    with pytest.raises(ProposalValidationError, match="additional_changes"):
        _parse_patch(raw)


def test_patch_rejects_unknown_edit_fields_with_additional_changes_guidance():
    raw = {
        "file_path": "policies/baseline_algorithm.py",
        "action": "modify",
        "code_content": "def solve(instance, rng, time_limit_sec, context):\n    return None\n",
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
