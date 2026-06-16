from __future__ import annotations

from dataclasses import fields
from types import SimpleNamespace

from scion.core.explore_step.branch_lesson_usage import (
    branch_lesson_usage_pre_code_block_reason,
    branch_lesson_usage_repair_skeleton,
    branch_lesson_usage_requirement_diagnostic,
    branch_lesson_usage_requirement_from_records,
    branch_lesson_usage_requirement_satisfied,
    branch_lesson_usage_requirement_metadata,
    canonical_branch_lesson_usage_repair,
)
from scion.core.explore_step.pipeline import ExploreStepPipeline
from scion.core.models import (
    Branch,
    BranchState,
    CanaryResult,
    CheckResult,
    ChampionState,
    ContractResult,
    Decision,
    DecisionFeatures,
    FailureEvent,
    HypothesisProposal,
    HypothesisRecord,
    MechanismChange,
    PatchProposal,
    StepRecord,
    VerificationResult,
)
from scion.core.step_result import StepResult
from scion.proposal.context_manager.manager import (
    _record_proposal_branch_lesson_usage_requirement,
)


def _branch() -> Branch:
    return Branch(
        branch_id="branch-clean",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="hash",
    )


def _champion() -> ChampionState:
    return ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="solver",
        code_snapshot_path="/tmp/champion",
        code_snapshot_hash="hash",
    )


def _hypothesis(**kwargs) -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text="Use compact generic branch lesson usage.",
        change_locus="selection_policy",
        action="modify",
        target_file="components/common.py",
        mechanism_changes=(MechanismChange(id="generic_signal", change_type="modify"),),
        **kwargs,
    )


def _record(
    lesson_id: str,
    *,
    required_for: str = "clean_fork_new_branch",
    lesson_role: str = "contrast",
    lesson_type: str = "near_duplicate",
) -> dict:
    return {
        "schema_version": "branch_lesson.v1",
        "lesson_id": lesson_id,
        "source": "proposal_only",
        "decision_input_policy": "excluded_from_decision_features",
        "scope": "cross_branch",
        "lesson_role": lesson_role,
        "lesson_type": lesson_type,
        "maturity": "repeated",
        "source_branch_ids": ["branch-a"],
        "shared_signature": {
            "mechanism_family": "family_a",
            "target_file": "components/common.py",
            "action": "modify",
            "change_locus": "selection_policy",
        },
        "evidence_basis": {"outcome_patterns": {"no_effect": 1}},
        "required_response": {
            "required_for": required_for,
            "required_output_field": "branch_lesson_usage",
            "required_contrast_dimensions": [
                "mechanism_family",
                "target_file",
            ],
            "same_branch_refinement_allowed": (
                required_for == "same_branch_refinement"
            ),
            "sibling_duplication_allowed": False,
        },
        "reason_codes": ["BRANCH_LESSON_REQUIRED"],
    }


def _non_actionable_sibling_record() -> dict:
    return {
        "schema_version": "branch_lesson.v1",
        "lesson_id": "lesson:unknown-active",
        "source": "proposal_only",
        "decision_input_policy": "excluded_from_decision_features",
        "scope": "branch_local",
        "lesson_role": "avoid",
        "lesson_type": "no_effect",
        "maturity": "fresh",
        "source_branch_ids": ["branch-active"],
        "evidence_basis": {
            "activation_statuses": {"unknown": 1},
            "effect_statuses": {"unknown": 1},
            "outcome_patterns": {"active": 1},
            "runtime_evidence_statuses": {"unknown": 1},
        },
        "required_response": {
            "minimum_requirement": (
                "name_borrowed_or_avoided_lesson_and_contrast_dimension"
            ),
            "required_contrast_dimensions": [
                "mechanism_family",
                "target_file",
                "action",
                "change_locus",
                "effect_path",
                "activation_path",
                "runtime_budget_strategy",
            ],
            "required_for": "sibling_nearby_attempt",
            "required_output_field": "branch_lesson_usage",
            "same_branch_refinement_allowed": False,
            "sibling_duplication_allowed": False,
        },
        "reason_codes": ["BRANCH_LESSON_REQUIRED", "LESSON_ACTIVE"],
    }


def test_clean_fork_requirement_blocks_missing_branch_lesson_usage() -> None:
    branch = _branch()
    branch.branch_evidence_summary = {
        "cross_branch_research_payload": {
            "branch_lesson_records": [_record("lesson:clean")]
        }
    }
    metadata = branch_lesson_usage_requirement_metadata(branch)

    detail = branch_lesson_usage_pre_code_block_reason(
        _hypothesis(),
        branch,
    )

    assert detail is not None
    assert "branch_lesson_usage_required_missing" in detail
    assert metadata["required_for"] == "clean_fork_new_branch"
    assert metadata["pre_code_block_required"] is True
    assert metadata["advisory_only"] is False
    assert (
        branch_lesson_usage_requirement_diagnostic(
            {},
            metadata=metadata,
            hypothesis=_hypothesis(),
        )
        == "missing"
    )


def test_non_actionable_sibling_unknown_record_does_not_require_usage() -> None:
    branch = _branch()
    branch.branch_evidence_summary = {
        "branch_lesson_records": [_non_actionable_sibling_record()]
    }

    requirement = branch_lesson_usage_requirement_from_records(
        branch.branch_evidence_summary["branch_lesson_records"]
    )
    metadata = branch_lesson_usage_requirement_metadata(branch)

    assert requirement == {}
    assert metadata == {"required": False}
    assert branch_lesson_usage_pre_code_block_reason(_hypothesis(), branch) is None


def test_same_branch_weak_positive_preserve_satisfies_requirement() -> None:
    branch = _branch()
    branch.branch_evidence_summary = {
        "branch_lesson_records": [
            _record(
                "lesson:local",
                required_for="same_branch_refinement",
                lesson_role="preserve",
                lesson_type="weak_positive",
            )
        ]
    }
    hypothesis = _hypothesis(
        branch_lesson_usage={
            "preserved_same_branch_lesson": {
                "lesson_id": "lesson:local",
                "preserved_signal": "observed_signal",
                "changed_dimensions": ["activation_threshold"],
                "risk_to_avoid": "known_gap",
                "target_file": "components/common.py",
                "action": "modify",
                "mechanism": "generic_signal",
            }
        }
    )

    assert branch_lesson_usage_pre_code_block_reason(hypothesis, branch) is None


def test_same_branch_weak_positive_followup_aliases_do_not_pre_code_block() -> None:
    branch = _branch()
    branch.branch_evidence_summary = {
        "branch_lesson_records": [
            _record(
                "lesson:local-alias",
                required_for="same_branch_refinement",
                lesson_role="preserve",
                lesson_type="weak_positive",
            )
        ]
    }
    hypothesis = _hypothesis(
        branch_lesson_usage={
            "preserved_same_branch_lesson": {
                "source_lesson_id": "lesson:local-alias",
                "preserved_signal": "weak_signal",
                "changed_dimension_ids": ["activation_threshold"],
                "risk": "known_gap",
                "file_path": "common.py",
                "proposal_change_action": "modify_existing",
                "mechanism_linkage_token": "generic_signal_refinement",
            }
        }
    )
    metadata = branch_lesson_usage_requirement_metadata(branch)

    assert branch_lesson_usage_pre_code_block_reason(hypothesis, branch) is None
    skeleton = branch_lesson_usage_repair_skeleton(
        hypothesis.branch_lesson_usage,
        metadata=metadata,
        hypothesis=hypothesis,
    )
    assert skeleton["diagnostic"] == "satisfied"
    normalized = skeleton["normalized_usage"]["preserved_same_branch_lesson"]
    assert normalized["lesson_id"] == "lesson:local-alias"
    assert normalized["target_file"] == "common.py"
    assert normalized["mechanism"] == "generic_signal_refinement"
    assert normalized["recognized_aliases"]["mechanism_linkage_token"] == "mechanism"


def test_same_branch_weak_positive_imperfect_usage_is_advisory() -> None:
    branch = _branch()
    branch.branch_evidence_summary = {
        "branch_lesson_records": [
            _record(
                "lesson:local-imperfect",
                required_for="same_branch_refinement",
                lesson_role="preserve",
                lesson_type="weak_positive",
            )
        ]
    }
    hypothesis = _hypothesis(
        branch_lesson_usage={
            "preserved_same_branch_lesson": {
                "lesson_id": "lesson:local-imperfect",
                "preserved_signal": "weak_signal",
            }
        }
    )
    metadata = branch_lesson_usage_requirement_metadata(branch)

    assert metadata["required_for"] == "same_branch_refinement"
    assert metadata["pre_code_block_required"] is False
    assert branch_lesson_usage_pre_code_block_reason(hypothesis, branch) is None
    skeleton = branch_lesson_usage_repair_skeleton(
        hypothesis.branch_lesson_usage,
        metadata=metadata,
        hypothesis=hypothesis,
    )
    assert skeleton["diagnostic"] == "semantic_mismatch"
    assert set(skeleton["missing_fields"]) >= {"target_file", "action", "mechanism"}
    assert skeleton["required_item_fields"] == [
        "lesson_id",
        "target_file",
        "action",
        "mechanism_id",
        "mechanism_family",
        "changed_dimensions",
    ]
    assert skeleton["expected_linkage"]["candidate_lesson_ids"] == [
        "lesson:local-imperfect"
    ]
    assert skeleton["expected_linkage"]["target_file"] == "components/common.py"
    assert skeleton["expected_linkage"]["action"] == "modify"
    assert skeleton["expected_linkage"]["mechanism_ids"] == ["generic_signal"]
    assert skeleton["expected_linkage"]["mechanism_families"] == ["family_a"]
    assert skeleton["expected_linkage"]["changed_dimensions"] == [
        "mechanism_family",
        "target_file",
    ]
    assert skeleton["corrected_fields"]["lesson_id"] == "lesson:local-imperfect"
    assert skeleton["corrected_fields"]["target_file"] == "components/common.py"
    assert skeleton["corrected_fields"]["action"] == "modify"
    assert skeleton["corrected_fields"]["mechanism_id"] == "generic_signal"
    assert skeleton["corrected_fields"]["mechanism_family"] == "family_a"
    assert skeleton["corrected_fields"]["changed_dimensions"] == [
        "mechanism_family",
        "target_file",
    ]


def test_canonical_repair_fills_strict_linkage_from_skeleton() -> None:
    branch = _branch()
    branch.branch_evidence_summary = {
        "branch_lesson_records": [_record("lesson:repairable")]
    }
    hypothesis = _hypothesis(
        branch_lesson_usage={
            "contrasted_lessons": [
                {
                    "lesson_id": "lesson:repairable",
                    "mechanism_story": "generic_signal",
                    "changed_dimensions": ["mechanism_family"],
                }
            ]
        }
    )
    metadata = branch_lesson_usage_requirement_metadata(branch)

    assert (
        branch_lesson_usage_requirement_diagnostic(
            hypothesis.branch_lesson_usage,
            metadata=metadata,
            hypothesis=hypothesis,
        )
        == "linkage_unrecognized"
    )
    repair = canonical_branch_lesson_usage_repair(
        hypothesis.branch_lesson_usage,
        metadata=metadata,
        hypothesis=hypothesis,
    )

    repaired_usage = repair["branch_lesson_usage"]
    repaired_item = repaired_usage["contrasted_lessons"][0]
    assert repaired_item["lesson_id"] == "lesson:repairable"
    assert repaired_item["target_file"] == "components/common.py"
    assert repaired_item["action"] == "modify"
    assert repaired_item["mechanism_id"] == "generic_signal"
    assert repaired_item["changed_dimensions"] == ["mechanism_family"]
    assert (
        branch_lesson_usage_requirement_diagnostic(
            repaired_usage,
            metadata=metadata,
            hypothesis=hypothesis,
        )
        == "satisfied"
    )
    assert repair["repair_attribution"]["decision_features_excluded"] is True


def test_canonical_repair_does_not_create_missing_usage() -> None:
    branch = _branch()
    branch.branch_evidence_summary = {
        "branch_lesson_records": [_record("lesson:missing")]
    }
    metadata = branch_lesson_usage_requirement_metadata(branch)

    assert (
        canonical_branch_lesson_usage_repair(
            {},
            metadata=metadata,
            hypothesis=_hypothesis(),
        )
        == {}
    )


def test_metadata_only_lesson_usage_fails_requirement() -> None:
    branch = _branch()
    branch.branch_evidence_summary = {
        "branch_lesson_records": [_record("lesson:metadata-only")]
    }
    hypothesis = _hypothesis(
        branch_lesson_usage={
            "schema_version": "branch_lesson_usage.v1",
            "proposal_visibility_only": True,
            "candidate_lesson_ids": ["lesson:metadata-only"],
            "decision_features_excluded": True,
        }
    )

    metadata = branch_lesson_usage_requirement_metadata(branch)

    detail = branch_lesson_usage_pre_code_block_reason(hypothesis, branch)

    assert detail is not None
    assert "branch_lesson_usage_metadata_only" in detail
    assert (
        branch_lesson_usage_requirement_diagnostic(
            hypothesis.branch_lesson_usage,
            metadata=metadata,
            hypothesis=hypothesis,
        )
        == "metadata_only"
    )


def test_clean_fork_contrast_requires_changed_dimensions() -> None:
    branch = _branch()
    branch.branch_evidence_summary = {
        "branch_lesson_records": [_record("lesson:contrast")]
    }

    only_id = _hypothesis(
        branch_lesson_usage={"contrasted_lessons": [{"lesson_id": "lesson:contrast"}]}
    )
    with_dimensions = _hypothesis(
        branch_lesson_usage={
            "contrasted_lessons": [
                {
                    "lesson_id": "lesson:contrast",
                    "contrast_dimensions": ["target_file"],
                    "new_path": "generic_path",
                    "target_file": "components/common.py",
                    "action": "modify",
                    "mechanism": "generic_signal",
                }
            ],
            "clean_fork_diversity_claim": {
                "changed_dimensions": ["target_file"],
                "sibling_duplication_allowed": False,
            },
        }
    )

    assert branch_lesson_usage_pre_code_block_reason(with_dimensions, branch) is None
    metadata = branch_lesson_usage_requirement_metadata(branch)
    assert (
        branch_lesson_usage_requirement_diagnostic(
            only_id.branch_lesson_usage,
            metadata=metadata,
            hypothesis=only_id,
        )
        == "semantic_mismatch"
    )
    assert branch_lesson_usage_requirement_satisfied(
        with_dimensions.branch_lesson_usage,
        metadata=metadata,
        hypothesis=with_dimensions,
    )


def test_clean_fork_action_linked_usage_accepts_generic_mechanism_family() -> None:
    branch = _branch()
    branch.branch_evidence_summary = {
        "branch_lesson_records": [_record("lesson:family")]
    }
    hypothesis = _hypothesis(
        branch_lesson_usage={
            "contrasted_lessons": [
                {
                    "lesson_id": "lesson:family",
                    "contrast_dimensions": ["mechanism_family", "target_file"],
                    "target_file": "components/common.py",
                    "action": "modify",
                    "mechanism_family": "family_a",
                    "change_rationale": "different_trigger_family",
                }
            ],
        }
    )

    assert branch_lesson_usage_pre_code_block_reason(hypothesis, branch) is None


def test_near_duplicate_clean_fork_without_contrast_or_reject_fails() -> None:
    branch = _branch()
    branch.branch_evidence_summary = {
        "branch_lesson_records": [_record("lesson:duplicate")]
    }
    hypothesis = _hypothesis(
        branch_lesson_usage={
            "borrowed_lessons": [
                {
                    "lesson_id": "lesson:duplicate",
                    "target_file": "components/common.py",
                    "action": "modify",
                    "mechanism": "generic_signal",
                    "borrow_reason_code": "same_family_follow_up",
                }
            ],
            "clean_fork_diversity_claim": {
                "changed_dimensions": ["target_file"],
                "sibling_duplication_allowed": False,
            },
        }
    )

    metadata = branch_lesson_usage_requirement_metadata(branch)

    detail = branch_lesson_usage_pre_code_block_reason(hypothesis, branch)

    assert detail is not None
    assert "branch_lesson_usage_semantic_mismatch" in detail
    assert (
        branch_lesson_usage_requirement_diagnostic(
            hypothesis.branch_lesson_usage,
            metadata=metadata,
            hypothesis=hypothesis,
        )
        == "semantic_mismatch"
    )


def test_actionable_sibling_near_duplicate_without_contrast_or_reject_blocks() -> (
    None
):
    branch = _branch()
    branch.branch_evidence_summary = {
        "branch_lesson_records": [
            _record(
                "lesson:sibling-duplicate",
                required_for="sibling_nearby_attempt",
            )
        ]
    }
    hypothesis = _hypothesis(
        branch_lesson_usage={
            "avoided_lessons": [
                {
                    "lesson_id": "lesson:sibling-duplicate",
                    "target_file": "components/common.py",
                    "action": "modify",
                    "mechanism": "generic_signal",
                    "avoid_reason_code": "same_family_no_effect",
                }
            ],
        }
    )

    metadata = branch_lesson_usage_requirement_metadata(branch)

    assert metadata["required"] is True
    assert metadata["required_for"] == "sibling_nearby_attempt"
    assert metadata["pre_code_block_required"] is True
    assert metadata["advisory_only"] is False
    detail = branch_lesson_usage_pre_code_block_reason(hypothesis, branch)
    assert detail is not None
    assert "branch_lesson_usage_semantic_mismatch" in detail
    assert (
        branch_lesson_usage_requirement_diagnostic(
            hypothesis.branch_lesson_usage,
            metadata=metadata,
            hypothesis=hypothesis,
        )
        == "semantic_mismatch"
    )


def test_actionable_sibling_nearby_missing_usage_pre_code_blocks() -> None:
    branch = _branch()
    branch.branch_evidence_summary = {
        "branch_lesson_records": [
            _record(
                "lesson:sibling-missing",
                required_for="sibling_nearby_attempt",
                lesson_role="avoid",
                lesson_type="no_effect",
            )
        ]
    }

    metadata = branch_lesson_usage_requirement_metadata(branch)

    assert metadata["required"] is True
    assert metadata["required_for"] == "sibling_nearby_attempt"
    assert metadata["pre_code_block_required"] is True
    assert metadata["advisory_only"] is False
    detail = branch_lesson_usage_pre_code_block_reason(_hypothesis(), branch)
    assert detail is not None
    assert "branch_lesson_usage_required_missing" in detail
    assert (
        branch_lesson_usage_requirement_diagnostic(
            {},
            metadata=metadata,
            hypothesis=_hypothesis(),
        )
        == "missing"
    )


def test_clean_fork_accepts_machine_readable_near_duplicate_reject() -> None:
    branch = _branch()
    branch.branch_evidence_summary = {
        "branch_lesson_records": [_record("lesson:reject")]
    }
    vague_reject = _hypothesis(
        branch_lesson_usage={
            "rejected_lessons": [
                {
                    "lesson_id": "lesson:reject",
                    "reject_reason": "not suitable",
                    "target_file": "components/common.py",
                    "action": "modify",
                    "mechanism": "generic_signal",
                }
            ],
        }
    )
    linked_reject = _hypothesis(
        branch_lesson_usage={
            "rejected_lessons": [
                {
                    "lesson_id": "lesson:reject",
                    "reject_reason_code": "same_family_changed_target",
                    "target_file": "components/common.py",
                    "action": "modify",
                    "mechanism": "generic_signal",
                }
            ],
        }
    )

    assert branch_lesson_usage_pre_code_block_reason(linked_reject, branch) is None
    metadata = branch_lesson_usage_requirement_metadata(branch)
    assert (
        branch_lesson_usage_requirement_diagnostic(
            vague_reject.branch_lesson_usage,
            metadata=metadata,
            hypothesis=vague_reject,
        )
        == "semantic_mismatch"
    )
    assert branch_lesson_usage_requirement_satisfied(
        linked_reject.branch_lesson_usage,
        metadata=metadata,
        hypothesis=linked_reject,
    )


def test_requirement_metadata_derives_compact_record_from_branch_lessons() -> None:
    branch = _branch()
    branch.branch_evidence_summary = {
        "branch_lesson_records": [_record("lesson:metadata")]
    }

    metadata = branch_lesson_usage_requirement_metadata(branch)
    requirement = branch_lesson_usage_requirement_from_records(
        branch.branch_evidence_summary["branch_lesson_records"]
    )

    assert metadata["required"] is True
    assert metadata["required_for"] == "clean_fork_new_branch"
    assert metadata["candidate_lesson_ids"] == ["lesson:metadata"]
    assert requirement["schema_version"] == "branch_lesson_usage_requirement.v1"
    assert requirement["record_id"].startswith("branch_lesson_usage_requirement:")


def test_weak_positive_borrow_requirement_requires_paths_and_risk_or_contrast() -> None:
    branch = _branch()
    branch.branch_evidence_summary = {
        "branch_lesson_records": [
            _record(
                "lesson:weak-borrow",
                required_for="clean_fork_new_branch",
                lesson_role="borrow",
                lesson_type="weak_positive",
            )
        ]
    }
    missing_paths = _hypothesis(
        branch_lesson_usage={
            "borrowed_lessons": [
                {
                    "lesson_id": "lesson:weak-borrow",
                    "lesson_type": "weak_positive",
                    "borrowed_signal": "weak_positive_signal",
                    "target_file": "components/common.py",
                    "action": "modify",
                    "mechanism": "generic_signal",
                }
            ],
            "contrasted_lessons": [
                {
                    "lesson_id": "lesson:weak-borrow",
                    "contrast_dimensions": ["target_file"],
                    "new_path": "generic_path",
                    "target_file": "components/common.py",
                    "action": "modify",
                    "mechanism": "generic_signal",
                }
            ],
            "clean_fork_diversity_claim": {
                "changed_dimensions": ["target_file"],
                "sibling_duplication_allowed": False,
            },
        }
    )
    with_paths = _hypothesis(
        branch_lesson_usage={
            "borrowed_lessons": [
                {
                    "lesson_id": "lesson:weak-borrow",
                    "lesson_type": "weak_positive",
                    "activation_path": "observed_activation",
                    "effect_path": "weak_effect",
                    "risk_to_avoid": "known_gap",
                    "target_file": "components/common.py",
                    "action": "modify",
                    "mechanism": "generic_signal",
                }
            ],
            "clean_fork_diversity_claim": {
                "changed_dimensions": ["target_file"],
                "sibling_duplication_allowed": False,
            },
        }
    )
    requirement = branch_lesson_usage_requirement_metadata(branch)

    assert requirement["requirement_source"] == "weak_positive_transfer"
    assert requirement["candidate_lesson_types"] == ["weak_positive"]
    assert requirement["candidate_lesson_roles"] == ["borrow"]
    assert branch_lesson_usage_pre_code_block_reason(with_paths, branch) is None
    assert (
        branch_lesson_usage_requirement_diagnostic(
            missing_paths.branch_lesson_usage,
            metadata=requirement,
            hypothesis=missing_paths,
        )
        == "semantic_mismatch"
    )
    assert branch_lesson_usage_requirement_satisfied(
        with_paths.branch_lesson_usage,
        metadata=requirement,
        hypothesis=with_paths,
    )


def test_weak_positive_clean_fork_accepts_machine_readable_reject_reason() -> None:
    branch = _branch()
    branch.branch_evidence_summary = {
        "branch_lesson_records": [
            _record(
                "lesson:weak-reject",
                required_for="clean_fork_new_branch",
                lesson_role="borrow",
                lesson_type="weak_positive",
            )
        ]
    }
    vague_reject = _hypothesis(
        branch_lesson_usage={
            "rejected_weak_positive_lessons": [
                {
                    "lesson_id": "lesson:weak-reject",
                    "lesson_type": "weak_positive",
                    "reject_reason": "not suitable",
                }
            ],
        }
    )
    linked_reject = _hypothesis(
        branch_lesson_usage={
            "rejected_weak_positive_lessons": [
                {
                    "lesson_id": "lesson:weak-reject",
                    "lesson_type": "weak_positive",
                    "reject_reason_code": "target_action_mismatch",
                    "target_file": "components/common.py",
                    "action": "modify",
                    "mechanism": "generic_signal",
                }
            ],
        }
    )

    assert branch_lesson_usage_pre_code_block_reason(linked_reject, branch) is None
    metadata = branch_lesson_usage_requirement_metadata(branch)
    assert (
        branch_lesson_usage_requirement_diagnostic(
            vague_reject.branch_lesson_usage,
            metadata=metadata,
            hypothesis=vague_reject,
        )
        == "semantic_mismatch"
    )
    assert branch_lesson_usage_requirement_satisfied(
        linked_reject.branch_lesson_usage,
        metadata=metadata,
        hypothesis=linked_reject,
    )


def test_context_manager_records_compact_requirement_for_pre_code_gate() -> None:
    branch = _branch()
    records = [_record("lesson:context")]
    requirement = branch_lesson_usage_requirement_from_records(records)

    _record_proposal_branch_lesson_usage_requirement(
        branch,
        requirement=requirement,
        records=records,
    )

    assert (
        branch.branch_evidence_summary["branch_lesson_usage_requirement"]["record_id"]
        == requirement["record_id"]
    )
    assert (
        branch.branch_evidence_summary["branch_lesson_records"][0]["lesson_id"]
        == "lesson:context"
    )
    detail = branch_lesson_usage_pre_code_block_reason(_hypothesis(), branch)
    assert detail is not None
    assert "branch_lesson_usage_required_missing" in detail
    assert requirement["pre_code_block_required"] is True
    assert requirement["advisory_only"] is False

    _record_proposal_branch_lesson_usage_requirement(
        branch,
        requirement={},
        records=[],
    )

    assert "branch_lesson_usage_requirement" not in branch.branch_evidence_summary
    assert "branch_lesson_records" not in branch.branch_evidence_summary


def test_pipeline_blocks_strict_clean_fork_before_code_when_usage_missing() -> None:
    branch = _branch()
    branch.branch_evidence_summary = {
        "branch_lesson_records": [_record("lesson:pipeline")]
    }
    hypothesis = _hypothesis()
    record = HypothesisRecord(
        hypothesis_id="hypothesis-1",
        branch_id=branch.branch_id,
        change_locus=hypothesis.change_locus,
        action=hypothesis.action,
        status="active",
        target_file=hypothesis.target_file,
    )
    steps: list[StepRecord] = []
    failures: list[tuple[Branch, FailureEvent]] = []
    statuses: list[tuple[str, str]] = []
    code_calls = {"count": 0}

    class Store:
        def get_by_status(self, _status: str):
            return []

        def save(self, _record) -> None:
            return None

        def mark_status(self, hypothesis_id: str, status: str) -> None:
            statuses.append((hypothesis_id, status))

    class ContractGate:
        def validate_hypothesis(self, *_args, **_kwargs):
            return ContractResult(passed=True, checks=())

    def generate_code(*_args, **_kwargs):
        code_calls["count"] += 1
        return None

    pipeline = ExploreStepPipeline(
        branch_controller=None,
        contract_gate=ContractGate(),
        verification_gate=None,
        hypothesis_store=Store(),
        registry=None,
        campaign_id="camp",
        get_champion=_champion,
        pending_hypotheses={},
        branch_hypotheses={},
        branch_patches={},
        branch_current_hypothesis={},
        branch_workspaces={},
        failure_streak={},
        increment_round=lambda: 1,
        increment_rounds_since_last_promote=lambda: None,
        generate_hypothesis=lambda _branch: (hypothesis, record),
        generate_code=generate_code,
        attempt_fix=lambda *_args, **_kwargs: None,
        handle_failure=lambda b, f, **_kwargs: failures.append((b, f)),
        record_step=steps.append,
        setup_workspace=lambda _branch: None,
        apply_patch=lambda *_args, **_kwargs: None,
        record_verification_pass=lambda *_args, **_kwargs: None,
        archive_failed_workspace=lambda *_args, **_kwargs: None,
        evaluate=lambda *_args, **_kwargs: (None, None, None),
        apply_decision_and_finalize=lambda *_args, **_kwargs: None,
        decision_reason_codes_for=lambda *_args, **_kwargs: None,
    )

    result = pipeline.run(branch)

    assert result.attempt_kind == "proposal_block"
    assert result.counts_toward_max_rounds is False
    assert result.failure_stage == "proposal"
    assert result.failure_detail is not None
    assert "branch_lesson_usage_required_missing" in result.failure_detail
    assert code_calls["count"] == 0
    assert statuses == [("hypothesis-1", "rejected")]
    assert len(failures) == 1
    assert failures[0][1].category == "proposal"
    assert len(steps) == 1
    assert steps[0].attempt_kind == "proposal_block"
    assert steps[0].counts_toward_max_rounds is False
    assert steps[0].failure_stage == "proposal"


def test_pipeline_canonicalizes_repairable_usage_before_code_block() -> None:
    branch = _branch()
    branch.branch_evidence_summary = {
        "branch_lesson_records": [_record("lesson:pipeline-repair")]
    }
    hypothesis = _hypothesis(
        branch_lesson_usage={
            "contrasted_lessons": [
                {
                    "lesson_id": "lesson:pipeline-repair",
                    "mechanism_story": "generic_signal",
                    "changed_dimensions": ["target_file"],
                }
            ]
        }
    )
    record = HypothesisRecord(
        hypothesis_id="hypothesis-repairable",
        branch_id=branch.branch_id,
        change_locus=hypothesis.change_locus,
        action=hypothesis.action,
        status="active",
        target_file=hypothesis.target_file,
    )
    steps: list[StepRecord] = []
    failures: list[tuple[Branch, FailureEvent]] = []
    statuses: list[tuple[str, str]] = []

    class Store:
        def get_by_status(self, _status: str):
            return []

        def save(self, _record) -> None:
            return None

        def mark_status(self, hypothesis_id: str, status: str) -> None:
            statuses.append((hypothesis_id, status))

    pipeline = ExploreStepPipeline(
        branch_controller=None,
        contract_gate=None,
        verification_gate=None,
        hypothesis_store=Store(),
        registry=None,
        campaign_id="camp",
        get_champion=_champion,
        pending_hypotheses={},
        branch_hypotheses={},
        branch_patches={},
        branch_current_hypothesis={},
        branch_workspaces={},
        failure_streak={},
        increment_round=lambda: 1,
        increment_rounds_since_last_promote=lambda: None,
        generate_hypothesis=lambda _branch: (hypothesis, record),
        generate_code=lambda *_args, **_kwargs: None,
        attempt_fix=lambda *_args, **_kwargs: None,
        handle_failure=lambda b, f, **_kwargs: failures.append((b, f)),
        record_step=steps.append,
        setup_workspace=lambda _branch: None,
        apply_patch=lambda *_args, **_kwargs: None,
        record_verification_pass=lambda *_args, **_kwargs: None,
        archive_failed_workspace=lambda *_args, **_kwargs: None,
        evaluate=lambda *_args, **_kwargs: (None, None, None),
        apply_decision_and_finalize=lambda *_args, **_kwargs: None,
        decision_reason_codes_for=lambda *_args, **_kwargs: None,
    )

    result = pipeline._block_missing_branch_lesson_usage(
        branch,
        hypothesis,
        record,
        round_num=1,
        retry_attempt=False,
        prior_failure=None,
    )

    assert result is None
    assert failures == []
    assert statuses == []
    assert steps == []
    repaired_item = hypothesis.branch_lesson_usage["contrasted_lessons"][0]
    assert repaired_item["target_file"] == "components/common.py"
    assert repaired_item["action"] == "modify"
    assert repaired_item["mechanism_id"] == "generic_signal"
    assert hypothesis.schema_repair_attribution
    assert (
        hypothesis.schema_repair_attribution[-1]["source"]
        == "branch_lesson_usage_repair_skeleton"
    )


def test_pipeline_reuses_destructive_proposal_ref_for_pre_code_checks() -> None:
    branch = _branch()
    records = [_record("lesson:session-block")]
    ref = {
        "material_difference_required": True,
        "material_difference_required_for": "clean_fork_new_branch",
        "material_difference_requirement": {
            "schema_version": "material_difference_requirement.v1",
            "record_type": "material_difference_requirement",
            "required_for": "clean_fork_new_branch",
        },
        "branch_lesson_records": records,
        "branch_lesson_usage_requirement": (
            branch_lesson_usage_requirement_from_records(records)
        ),
    }
    refs = {branch.branch_id: ref}
    provider_calls: list[str] = []
    hypothesis = _hypothesis(
        material_difference={
            "changed_dimensions": ["target_file"],
            "signature_digest": "sig-session-block",
        },
    )
    record = HypothesisRecord(
        hypothesis_id="hypothesis-1",
        branch_id=branch.branch_id,
        change_locus=hypothesis.change_locus,
        action=hypothesis.action,
        status="active",
        target_file=hypothesis.target_file,
    )
    steps: list[StepRecord] = []
    code_calls = {"count": 0}

    class Store:
        def get_by_status(self, _status: str):
            return []

        def save(self, _record) -> None:
            return None

        def mark_status(self, _hypothesis_id: str, _status: str) -> None:
            return None

    class ContractGate:
        def validate_hypothesis(self, *_args, **_kwargs):
            return ContractResult(passed=True, checks=())

    def pop_ref(branch_id: str):
        provider_calls.append(branch_id)
        return refs.pop(branch_id, None)

    def generate_code(*_args, **_kwargs):
        code_calls["count"] += 1
        return None

    pipeline = ExploreStepPipeline(
        branch_controller=None,
        contract_gate=ContractGate(),
        verification_gate=None,
        hypothesis_store=Store(),
        registry=None,
        campaign_id="camp",
        get_champion=_champion,
        pending_hypotheses={},
        branch_hypotheses={},
        branch_patches={},
        branch_current_hypothesis={},
        branch_workspaces={},
        failure_streak={},
        increment_round=lambda: 1,
        increment_rounds_since_last_promote=lambda: None,
        generate_hypothesis=lambda _branch: (hypothesis, record),
        generate_code=generate_code,
        attempt_fix=lambda *_args, **_kwargs: None,
        handle_failure=lambda *_args, **_kwargs: None,
        record_step=steps.append,
        setup_workspace=lambda _branch: None,
        apply_patch=lambda *_args, **_kwargs: None,
        record_verification_pass=lambda *_args, **_kwargs: None,
        archive_failed_workspace=lambda *_args, **_kwargs: None,
        evaluate=lambda *_args, **_kwargs: (None, None, None),
        apply_decision_and_finalize=lambda *_args, **_kwargs: None,
        decision_reason_codes_for=lambda *_args, **_kwargs: None,
        proposal_session_ref_for=pop_ref,
    )

    result = pipeline.run(branch)

    assert provider_calls == [branch.branch_id]
    assert refs == {}
    assert code_calls["count"] == 0
    assert result.attempt_kind == "proposal_block"
    assert result.proposal_session_ref is ref
    assert (
        result.proposal_session_ref["branch_lesson_records"][0]["lesson_id"]
        == "lesson:session-block"
    )
    assert (
        result.proposal_session_ref["branch_lesson_usage_requirement"]["required"]
        is True
    )
    assert "branch_lesson_usage_required_missing" in str(result.failure_detail)
    assert result.failure_stage == "proposal"
    assert steps[0].proposal_session_ref is ref


def test_pipeline_final_step_keeps_destructive_proposal_ref_after_pre_code_checks() -> (
    None
):
    branch = _branch()
    records = [_record("lesson:session-final")]
    ref = {
        "material_difference_required": True,
        "material_difference_required_for": "clean_fork_new_branch",
        "material_difference_requirement": {
            "schema_version": "material_difference_requirement.v1",
            "record_type": "material_difference_requirement",
            "required_for": "clean_fork_new_branch",
        },
        "branch_lesson_records": records,
        "branch_lesson_usage_requirement": (
            branch_lesson_usage_requirement_from_records(records)
        ),
    }
    refs = {branch.branch_id: ref}
    provider_calls: list[str] = []
    hypothesis = _hypothesis(
        material_difference={
            "changed_dimensions": ["target_file"],
            "signature_digest": "sig-session-final",
        },
        branch_lesson_usage={
            "contrasted_lessons": [
                {
                    "lesson_id": "lesson:session-final",
                    "contrast_dimensions": ["target_file"],
                    "new_path": "components/common.py",
                    "target_file": "components/common.py",
                    "action": "modify",
                    "mechanism": "generic_signal",
                }
            ],
            "clean_fork_diversity_claim": {
                "changed_dimensions": ["target_file"],
                "sibling_duplication_allowed": False,
            },
        },
    )
    record = HypothesisRecord(
        hypothesis_id="hypothesis-1",
        branch_id=branch.branch_id,
        change_locus=hypothesis.change_locus,
        action=hypothesis.action,
        status="active",
        target_file=hypothesis.target_file,
    )
    patch = PatchProposal(
        file_path="components/common.py",
        action="modify",
        code_content="def candidate():\n    return None\n",
    )
    steps: list[StepRecord] = []

    class BranchController:
        def get_branch(self, branch_id: str) -> Branch:
            assert branch_id == branch.branch_id
            return branch

        def next_stage(self, branch_id: str) -> None:
            assert branch_id == branch.branch_id

    class Store:
        def get_by_status(self, _status: str):
            return []

        def save(self, _record) -> None:
            return None

        def mark_status(self, _hypothesis_id: str, _status: str) -> None:
            return None

    class ContractGate:
        def validate_hypothesis(self, *_args, **_kwargs):
            return ContractResult(passed=True, checks=())

        def validate_patch(self, *_args, **_kwargs):
            return ContractResult(passed=True, checks=())

    class VerificationGate:
        def run(self, *_args, **_kwargs) -> VerificationResult:
            return VerificationResult(
                passed=True,
                checks=(CheckResult("V", True, "light", "ok", 0),),
            )

    def pop_ref(branch_id: str):
        provider_calls.append(branch_id)
        return refs.pop(branch_id, None)

    pipeline = ExploreStepPipeline(
        branch_controller=BranchController(),
        contract_gate=ContractGate(),
        verification_gate=VerificationGate(),
        hypothesis_store=Store(),
        registry=None,
        campaign_id="camp",
        get_champion=_champion,
        pending_hypotheses={},
        branch_hypotheses={},
        branch_patches={},
        branch_current_hypothesis={},
        branch_workspaces={},
        failure_streak={},
        increment_round=lambda: 1,
        increment_rounds_since_last_promote=lambda: None,
        generate_hypothesis=lambda _branch: (hypothesis, record),
        generate_code=lambda *_args, **_kwargs: patch,
        attempt_fix=lambda *_args, **_kwargs: None,
        handle_failure=lambda *_args, **_kwargs: None,
        record_step=steps.append,
        setup_workspace=lambda _branch: "/tmp/workspace",
        apply_patch=lambda *_args, **_kwargs: SimpleNamespace(code_hash="code-hash"),
        record_verification_pass=lambda *_args, **_kwargs: None,
        archive_failed_workspace=lambda *_args, **_kwargs: None,
        evaluate=lambda *_args, **_kwargs: (
            Decision.ABANDON,
            None,
            CanaryResult(passed=True),
        ),
        apply_decision_and_finalize=lambda **kwargs: StepResult(
            action="explore",
            branch_id=kwargs["branch"].branch_id,
            decision=kwargs["decision"],
            reason="screening complete",
        ),
        decision_reason_codes_for=lambda *_args, **_kwargs: None,
        proposal_session_ref_for=pop_ref,
    )

    result = pipeline.run(branch)

    assert provider_calls == [branch.branch_id]
    assert refs == {}
    assert result.reason == "screening complete"
    assert result.proposal_session_ref is ref
    assert (
        result.proposal_session_ref["branch_lesson_records"][0]["lesson_id"]
        == "lesson:session-final"
    )
    assert (
        result.proposal_session_ref["branch_lesson_usage_requirement"]["required"]
        is True
    )
    assert len(steps) == 1
    assert steps[0].proposal_session_ref is ref
    assert (
        steps[0].proposal_session_ref["branch_lesson_records"][0]["lesson_id"]
        == "lesson:session-final"
    )
    assert (
        steps[0].proposal_session_ref["branch_lesson_usage_requirement"]["required"]
        is True
    )


def test_branch_lesson_usage_fields_do_not_enter_decision_features() -> None:
    decision_fields = {field.name for field in fields(DecisionFeatures)}

    assert "branch_lesson_usage" not in decision_fields
    assert "branch_lesson_records" not in decision_fields
    assert "branch_lesson_usage_requirement" not in decision_fields
    assert "branch_lesson_usage_satisfied_count" not in decision_fields
    assert "branch_lesson_usage_missing_block_count" not in decision_fields
    assert "branch_lesson_usage_metadata_only_count" not in decision_fields
    assert "branch_lesson_usage_linkage_unrecognized_count" not in decision_fields
    assert "branch_lesson_usage_semantic_mismatch_count" not in decision_fields
    assert "branch_lesson_usage_repair_skeleton" not in decision_fields
    assert "borrowed_lesson_count" not in decision_fields
    assert "avoided_lesson_count" not in decision_fields
    assert "contrasted_lesson_count" not in decision_fields
    assert "preserved_same_branch_lesson_count" not in decision_fields
    assert "near_duplicate_diagnostics" not in decision_fields
    assert "saturated_signature_diagnostics" not in decision_fields


def _strict_requirement() -> dict:
    return {
        "schema_version": "branch_lesson_usage_requirement.v1",
        "required": True,
        "required_for": "clean_fork_new_branch",
        "required_fors": ["clean_fork_new_branch"],
        "candidate_lesson_ids": ["lesson:real"],
        "candidate_target_files": ["components/common.py"],
        "candidate_actions": ["modify"],
        "candidate_mechanism_families": ["broad_family"],
    }


def _usage_with_mechanism_linkage(field: str) -> dict:
    return {
        "contrasted_lessons": [
            {
                "lesson_id": "lesson:real",
                "contrast_dimensions": ["target_file", "mechanism"],
                "target_file": "components/common.py",
                "action": "modify",
                field: "generic_signal",
            }
        ],
        "clean_fork_diversity_claim": {
            "changed_dimensions": ["target_file", "mechanism"],
            "sibling_duplication_allowed": False,
        },
    }


def test_real_payload_mechanism_id_target_action_contrast_lesson_passes() -> None:
    hypothesis = _hypothesis()
    usage = _usage_with_mechanism_linkage("mechanism_id")

    assert branch_lesson_usage_requirement_satisfied(
        usage,
        metadata=_strict_requirement(),
        hypothesis=hypothesis,
    )


def test_mechanism_linkage_field_aliases_pass() -> None:
    hypothesis = _hypothesis()

    for field_name in (
        "mechanism",
        "mechanism_id",
        "mechanism_change_id",
        "mechanism_or_mechanism_change_id",
        "mechanism_or_mechanism_change_ids",
    ):
        assert branch_lesson_usage_requirement_satisfied(
            _usage_with_mechanism_linkage(field_name),
            metadata=_strict_requirement(),
            hypothesis=hypothesis,
        ), field_name


def test_mechanism_or_mechanism_change_alias_is_projected_for_repair() -> None:
    hypothesis = _hypothesis()
    usage = _usage_with_mechanism_linkage("mechanism_or_mechanism_change_id")

    skeleton = branch_lesson_usage_repair_skeleton(
        usage,
        metadata=_strict_requirement(),
        hypothesis=hypothesis,
    )

    assert skeleton["diagnostic"] == "satisfied"
    normalized = skeleton["normalized_usage"]["contrasted_lessons"][0]
    assert normalized["mechanism"] == "generic_signal"
    assert normalized["recognized_aliases"][
        "mechanism_or_mechanism_change_id"
    ] == "mechanism"


def test_target_action_mechanism_linkage_are_all_required() -> None:
    hypothesis = _hypothesis()
    required = _strict_requirement()

    for omitted_field in ("target_file", "action", "mechanism_id"):
        usage = _usage_with_mechanism_linkage("mechanism_id")
        del usage["contrasted_lessons"][0][omitted_field]

        assert not branch_lesson_usage_requirement_satisfied(
            usage,
            metadata=required,
            hypothesis=hypothesis,
        ), omitted_field


def test_broad_family_token_satisfies_generic_action_linkage() -> None:
    hypothesis = _hypothesis()
    usage = {
        "contrasted_lessons": [
            {
                "lesson_id": "lesson:real",
                "contrast_dimensions": ["mechanism_family"],
                "target_file": "components/common.py",
                "action": "modify",
                "mechanism_family": "broad_family",
            }
        ],
        "clean_fork_diversity_claim": {
            "changed_dimensions": ["mechanism_family"],
            "sibling_duplication_allowed": False,
        },
    }

    assert branch_lesson_usage_requirement_satisfied(
        usage,
        metadata=_strict_requirement(),
        hypothesis=hypothesis,
    )
    assert (
        branch_lesson_usage_requirement_diagnostic(
            usage,
            metadata=_strict_requirement(),
            hypothesis=hypothesis,
        )
        == "satisfied"
    )


def test_linkage_unrecognized_reason_distinguishes_present_usage() -> None:
    branch = _branch()
    branch.branch_evidence_summary = {
        "branch_lesson_records": [_record("lesson:real")]
    }
    hypothesis = _hypothesis(
        branch_lesson_usage={
            "contrasted_lessons": [
                {
                    "lesson_id": "lesson:real",
                    "contrast_dimensions": ["mechanism"],
                    "target_file": "components/common.py",
                    "action": "modify",
                    "mechanism_story": "generic_signal",
                }
            ],
            "clean_fork_diversity_claim": {
                "changed_dimensions": ["mechanism"],
                "sibling_duplication_allowed": False,
            },
        }
    )

    metadata = branch_lesson_usage_requirement_metadata(branch)
    skeleton = branch_lesson_usage_repair_skeleton(
        hypothesis.branch_lesson_usage,
        metadata=metadata,
        hypothesis=hypothesis,
    )

    detail = branch_lesson_usage_pre_code_block_reason(hypothesis, branch)
    assert detail is not None
    assert "branch_lesson_usage_linkage_unrecognized" in detail
    assert (
        branch_lesson_usage_requirement_diagnostic(
            hypothesis.branch_lesson_usage,
            metadata=metadata,
            hypothesis=hypothesis,
        )
        == "linkage_unrecognized"
    )
    assert skeleton["diagnostic"] == "linkage_unrecognized"
    assert "recognized_linkage_fields" in skeleton["missing_fields"]
