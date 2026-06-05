from __future__ import annotations

import re
import uuid

from scion.core.features import BudgetState, SafeFeatureExtractor
from scion.core.models import (
    Branch,
    BranchState,
    CanaryResult,
    CheckResult,
    ContractResult,
    HypothesisProposal,
    MechanismChange,
    VerificationResult,
)
from scion.core.repeated_contract_failures import (
    REPEATED_CONTRACT_FAILURE_CODE,
    REPEATED_CONTRACT_REROUTE_REASON,
    extract_contract_failure_signature,
    record_contract_failure_attempt,
)


def _hypothesis() -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text="Use a bounded cache for a reusable state delta.",
        change_locus="algorithm_design",
        action="modify",
        target_file="policies/state.py",
        mechanism_changes=(
            MechanismChange("state_delta_cache", "modify"),
        ),
    )


def _session_ref() -> dict:
    return {
        "session_id": "session-contract",
        "failure_category": "contract_boundary_failure",
        "failure_code": "object_model_no_dynamic_private_attrs",
        "contract_preview_codes": [
            "object_model_no_dynamic_private_attrs",
        ],
        "primary_failure": {
            "stage": "self_check",
            "reason": "contract_preview_failed",
            "category": "contract_boundary_failure",
            "code": "object_model_no_dynamic_private_attrs",
        },
    }


def _contract() -> ContractResult:
    return ContractResult(
        passed=True,
        checks=(CheckResult("C", True, "light", "ok", 0),),
    )


def _verification() -> VerificationResult:
    return VerificationResult(
        passed=True,
        checks=(CheckResult("V", True, "light", "ok", 0),),
    )


def test_extract_contract_failure_signature_uses_structured_fields() -> None:
    signature = extract_contract_failure_signature(
        "Contract preview failed: state.py prose says private cache is invalid",
        _hypothesis(),
        _session_ref(),
        failure_stage="code_generation",
    )

    assert signature is not None
    assert signature.target_file == "policies/state.py"
    assert signature.mechanism_ids == ("state_delta_cache",)
    assert signature.contract_check == "object_model_no_dynamic_private_attrs"
    assert signature.failure_category == "contract_boundary_failure"
    assert signature.selected_surface == "algorithm_design"


def test_repeated_contract_signature_marks_reroute_without_free_text_leak() -> None:
    branch = Branch(
        str(uuid.uuid4()),
        BranchState.EXPLORE,
        1,
        "champ",
    )
    detail = (
        "Contract preview failed: object_model_no_dynamic_private_attrs; "
        "state.py prose says the private cache keeps mutable branch state"
    )

    first = record_contract_failure_attempt(
        branch,
        detail,
        _hypothesis(),
        _session_ref(),
        failure_stage="code_generation",
    )
    second = record_contract_failure_attempt(
        branch,
        detail,
        _hypothesis(),
        _session_ref(),
        failure_stage="code_generation",
    )

    assert first.count == 1
    assert first.threshold_reached is False
    assert second.count == 2
    assert second.threshold_reached is True
    assert branch.pending_retry is False
    assert branch.failure_codes == [REPEATED_CONTRACT_FAILURE_CODE]
    assert all(re.fullmatch(r"[A-Z][A-Z0-9_]*", code) for code in branch.failure_codes)

    evidence = branch.branch_evidence_summary["repeated_contract_failures"]
    assert evidence["last_signature"]["contract_check"] == (
        "object_model_no_dynamic_private_attrs"
    )
    assert evidence["last_signature"]["target_file"] == "policies/state.py"
    assert "state.py prose says" not in str(evidence)

    block = branch.last_branch_lifecycle_policy_block
    assert block["reason"] == REPEATED_CONTRACT_REROUTE_REASON
    assert block["reroute_reason"] == REPEATED_CONTRACT_REROUTE_REASON
    assert block["failure_code"] == REPEATED_CONTRACT_FAILURE_CODE
    assert block["same_hypothesis_retry"] == "blocked"
    assert block["failure_signature"]["mechanism_ids"] == ["state_delta_cache"]
    assert "private cache keeps mutable branch state" not in str(block)


def test_decision_features_keep_only_repeated_contract_enum() -> None:
    branch = Branch(
        str(uuid.uuid4()),
        BranchState.EXPLORE,
        1,
        "champ",
    )
    branch.failure_codes = [
        REPEATED_CONTRACT_FAILURE_CODE,
        "OBJECT_MODEL_NO_DYNAMIC_PRIVATE_ATTRS",
    ]

    features = SafeFeatureExtractor().extract(
        branch=branch,
        hypothesis_action="modify",
        contract=_contract(),
        verification=_verification(),
        canary=CanaryResult(True),
        protocol=None,
        budget=BudgetState(total=10, used=1),
    )

    assert features.recent_failure_codes == (REPEATED_CONTRACT_FAILURE_CODE,)
    assert "object_model_no_dynamic_private_attrs" not in str(features)
    assert "state.py" not in str(features)
