from __future__ import annotations

from pathlib import Path

from scion.contract.gate import ContractGate
from scion.core.models import (
    HypothesisProposal,
    PatchProposal,
)
from scion.problem.bridge import legacy_problem_spec_from_v1
from scion.problem.spec import ProblemSpecV1
from scion.tests.unit.research_surface_helpers import _problem_payload


def test_contract_gate_validates_policy_surface_required_function_presence(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["search_space"]["editable"] = ["operators/*.py", "policies/*.py"]
    payload["research_surfaces"] = [
        {
            "name": "local",
            "kind": "operator",
            "description": "Local operators",
            "target_files": ["operators/*.py"],
        },
        {
            "name": "search_policy",
            "kind": "policy",
            "description": "Budget policy",
            "target_files": ["policies/search_policy.py"],
            "required_functions": [
                "baseline_time_fraction",
                "max_operator_rounds",
                "enable_post_baseline_operators",
            ],
            "create_new_allowed": False,
            "remove_allowed": False,
        },
    ]
    legacy = legacy_problem_spec_from_v1(ProblemSpecV1(**payload))
    gate = ContractGate(legacy)

    valid_patch = PatchProposal(
        file_path="policies/search_policy.py",
        action="modify",
        code_content=(
            "def baseline_time_fraction(instance, time_limit_sec):\n"
            "    return 0.8\n\n"
            "def max_operator_rounds(instance, time_limit_sec):\n"
            "    return 20\n\n"
            "def enable_post_baseline_operators(instance, time_limit_sec):\n"
            "    return True\n"
        ),
    )
    result = gate.validate_patch(valid_patch)
    c7 = next(check for check in result.checks if check.name == "C7_interface")
    assert c7.passed

    missing_patch = PatchProposal(
        file_path="policies/search_policy.py",
        action="modify",
        code_content=(
            "def baseline_time_fraction(instance, time_limit_sec):\n"
            "    return 0.8\n"
        ),
    )
    result = gate.validate_patch(missing_patch)
    c7 = next(check for check in result.checks if check.name == "C7_interface")
    assert not c7.passed
    assert "missing required functions" in c7.detail

    wrong_args_patch = PatchProposal(
        file_path="policies/search_policy.py",
        action="modify",
        code_content=(
            "def baseline_time_fraction(instance):\n"
            "    return 0.8\n\n"
            "def max_operator_rounds(instance, time_limit_sec):\n"
            "    return 20\n\n"
            "def enable_post_baseline_operators(instance, time_limit_sec):\n"
            "    return True\n"
        ),
    )
    result = gate.validate_patch(wrong_args_patch)
    c7 = next(check for check in result.checks if check.name == "C7_interface")
    assert c7.passed


def test_contract_gate_validates_declared_module_function_signatures(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["search_space"]["editable"] = ["policies/*.py"]
    payload["research_surfaces"] = [
        {
            "name": "dispatch_policy",
            "kind": "policy",
            "targets": {"files": ["policies/dispatch.py"]},
            "interface": {
                "required_functions": ["select_limit"],
                "function_signatures": {
                    "select_limit": ["instance", "time_limit_sec"]
                },
            },
        },
    ]
    gate = ContractGate(legacy_problem_spec_from_v1(ProblemSpecV1(**payload)))

    missing = gate.validate_patch(
        PatchProposal(
            file_path="policies/dispatch.py",
            action="modify",
            code_content="def other(instance, time_limit_sec):\n    return 1\n",
        )
    )
    c7 = next(check for check in missing.checks if check.name == "C7_interface")
    assert not c7.passed
    assert "missing required functions ['select_limit']" in c7.detail

    wrong_name = gate.validate_patch(
        PatchProposal(
            file_path="policies/dispatch.py",
            action="modify",
            code_content="def select_limit(problem, time_limit_sec):\n    return 1\n",
        )
    )
    c7 = next(check for check in wrong_name.checks if check.name == "C7_interface")
    assert not c7.passed
    assert "do not match declared prefix" in c7.detail

    extra_required = gate.validate_patch(
        PatchProposal(
            file_path="policies/dispatch.py",
            action="modify",
            code_content=(
                "def select_limit(instance, time_limit_sec, extra):\n"
                "    return 1\n"
            ),
        )
    )
    c7 = next(check for check in extra_required.checks if check.name == "C7_interface")
    assert not c7.passed
    assert "extra required positional parameters ['extra']" in c7.detail

    optional_extra = gate.validate_patch(
        PatchProposal(
            file_path="policies/dispatch.py",
            action="modify",
            code_content=(
                "def select_limit(instance, time_limit_sec, extra=None):\n"
                "    return 1\n"
            ),
        )
    )
    c7 = next(check for check in optional_extra.checks if check.name == "C7_interface")
    assert c7.passed


def test_contract_gate_validates_declared_static_return_values(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["search_space"]["editable"] = ["policies/*.py"]
    payload["research_surfaces"] = [
        {
            "name": "dispatch_policy",
            "kind": "policy",
            "targets": {"files": ["policies/dispatch.py"]},
            "interface": {
                "required_functions": ["select_mode", "select_limit"],
                "function_signatures": {
                    "select_mode": ["instance", "time_limit_sec"],
                    "select_limit": ["instance", "time_limit_sec"],
                },
                "return_values": {
                    "select_mode": {
                        "value_type": "str",
                        "allowed_literals": ["small", "large"],
                    },
                    "select_limit": {
                        "value_type": "int",
                        "numeric_range": [1, 10],
                    },
                },
            },
        },
    ]
    gate = ContractGate(legacy_problem_spec_from_v1(ProblemSpecV1(**payload)))

    good = gate.validate_patch(
        PatchProposal(
            file_path="policies/dispatch.py",
            action="modify",
            code_content=(
                "def select_mode(instance, time_limit_sec):\n"
                "    return 'small'\n\n"
                "def select_limit(instance, time_limit_sec):\n"
                "    return 5\n"
            ),
        )
    )
    c7 = next(check for check in good.checks if check.name == "C7_interface")
    assert c7.passed

    bad_literal = gate.validate_patch(
        PatchProposal(
            file_path="policies/dispatch.py",
            action="modify",
            code_content=(
                "def select_mode(instance, time_limit_sec):\n"
                "    return 'unknown'\n\n"
                "def select_limit(instance, time_limit_sec):\n"
                "    return 5\n"
            ),
        )
    )
    c7 = next(check for check in bad_literal.checks if check.name == "C7_interface")
    assert not c7.passed
    assert "expected one of" in c7.detail

    bad_range = gate.validate_patch(
        PatchProposal(
            file_path="policies/dispatch.py",
            action="modify",
            code_content=(
                "def select_mode(instance, time_limit_sec):\n"
                "    return 'small'\n\n"
                "def select_limit(instance, time_limit_sec):\n"
                "    return 99\n"
            ),
        )
    )
    c7 = next(check for check in bad_range.checks if check.name == "C7_interface")
    assert not c7.passed
    assert "outside declared range" in c7.detail


def test_contract_gate_uses_v2_targets_actions_and_interface(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["search_space"]["editable"] = ["operators/*.py", "policies/*.py"]
    payload["research_surfaces"] = [
        {
            "name": "dispatch_policy",
            "kind": "policy",
            "targets": {
                "files": ["policies/dispatch.py"],
                "create_new_allowed": False,
                "modify_allowed": True,
                "remove_allowed": False,
                "singleton": True,
            },
            "interface": {
                "required_functions": ["select_limit"],
                "return_contract": "problem-defined scalar value",
            },
        },
    ]
    legacy = legacy_problem_spec_from_v1(ProblemSpecV1(**payload))
    gate = ContractGate(legacy)

    remove_hypothesis = HypothesisProposal(
        hypothesis_text="Remove the dispatch policy.",
        change_locus="dispatch_policy",
        action="remove",
        target_file="policies/dispatch.py",
    )
    result = gate.validate_hypothesis(remove_hypothesis, [], [])
    c3 = next(check for check in result.checks if check.name == "C3_action_target")
    assert not c3.passed
    assert "not allowed" in c3.detail

    wrong_target = HypothesisProposal(
        hypothesis_text="Modify a policy through the wrong file.",
        change_locus="dispatch_policy",
        action="modify",
        target_file="operators/not_dispatch.py",
    )
    result = gate.validate_hypothesis(wrong_target, [], [])
    c3 = next(check for check in result.checks if check.name == "C3_action_target")
    assert not c3.passed
    assert "policies/dispatch.py" in c3.detail

    missing_patch = PatchProposal(
        file_path="policies/dispatch.py",
        action="modify",
        code_content="def other_function(instance):\n    return 1\n",
    )
    result = gate.validate_patch(missing_patch)
    c7 = next(check for check in result.checks if check.name == "C7_interface")
    assert not c7.passed
    assert "missing required functions ['select_limit']" in c7.detail

    valid_patch = PatchProposal(
        file_path="policies/dispatch.py",
        action="modify",
        code_content="def select_limit(instance):\n    return 1\n",
    )
    result = gate.validate_patch(valid_patch)
    c7 = next(check for check in result.checks if check.name == "C7_interface")
    assert c7.passed


def test_contract_gate_enforces_surface_action_and_target_rules(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["search_space"]["editable"] = ["operators/*.py", "policies/*.py"]
    payload["research_surfaces"] = [
        {
            "name": "search_policy",
            "kind": "policy",
            "description": "Budget policy",
            "target_files": ["policies/search_policy.py"],
            "create_new_allowed": False,
            "modify_allowed": True,
            "remove_allowed": False,
        },
    ]
    legacy = legacy_problem_spec_from_v1(ProblemSpecV1(**payload))
    gate = ContractGate(legacy)

    remove_hypothesis = HypothesisProposal(
        hypothesis_text="Remove the singleton policy.",
        change_locus="search_policy",
        action="remove",
        target_file="policies/search_policy.py",
    )
    result = gate.validate_hypothesis(remove_hypothesis, [], [])
    c3 = next(check for check in result.checks if check.name == "C3_action_target")
    assert not c3.passed
    assert "not allowed" in c3.detail

    wrong_target = HypothesisProposal(
        hypothesis_text="Modify a policy via the wrong file.",
        change_locus="search_policy",
        action="modify",
        target_file="operators/not_policy.py",
    )
    result = gate.validate_hypothesis(wrong_target, [], [])
    c3 = next(check for check in result.checks if check.name == "C3_action_target")
    assert not c3.passed
    assert "not in target files" in c3.detail


def test_contract_gate_validate_patch_enforces_hypothesis_action_and_surface_permissions(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["search_space"]["editable"] = ["operators/*.py", "policies/*.py"]
    payload["research_surfaces"] = [
        {
            "name": "search_policy",
            "kind": "policy",
            "description": "Budget policy",
            "target_files": ["policies/search_policy.py"],
            "create_new_allowed": False,
            "modify_allowed": True,
            "remove_allowed": False,
        },
        {
            "name": "scratch_policy",
            "kind": "policy",
            "description": "Scratch policy modules",
            "target_files": ["policies/*.py"],
            "create_new_allowed": True,
            "modify_allowed": False,
            "remove_allowed": True,
        },
    ]
    legacy = legacy_problem_spec_from_v1(ProblemSpecV1(**payload))
    gate = ContractGate(legacy)
    policy_code = "def choose_budget(instance):\n    return 1\n"

    modify_hypothesis = HypothesisProposal(
        hypothesis_text="Tune search policy.",
        change_locus="search_policy",
        action="modify",
        target_file="policies/search_policy.py",
    )
    legal_modify = PatchProposal(
        file_path="policies/search_policy.py",
        action="modify",
        code_content=policy_code,
    )
    delete_patch = PatchProposal(
        file_path="policies/search_policy.py",
        action="delete",
        code_content="",
    )
    create_disallowed = PatchProposal(
        file_path="policies/search_policy.py",
        action="create",
        code_content=policy_code,
    )
    scratch_create_hypothesis = HypothesisProposal(
        hypothesis_text="Create scratch policy.",
        change_locus="scratch_policy",
        action="create_new",
        target_file="policies/scratch.py",
    )
    scratch_remove_hypothesis = HypothesisProposal(
        hypothesis_text="Remove scratch policy.",
        change_locus="scratch_policy",
        action="remove",
        target_file="policies/scratch.py",
    )

    result = gate.validate_patch(legal_modify, approved_hypothesis=modify_hypothesis)
    c4b = next(check for check in result.checks if check.name == "C4b_patch_action_target")
    assert c4b.passed
    assert result.passed

    result = gate.validate_patch(delete_patch, approved_hypothesis=modify_hypothesis)
    c4b = next(check for check in result.checks if check.name == "C4b_patch_action_target")
    assert not c4b.passed
    assert "does not match approved hypothesis action" in c4b.detail

    result = gate.validate_patch(delete_patch)
    c4b = next(check for check in result.checks if check.name == "C4b_patch_action_target")
    assert not c4b.passed
    assert "not allowed" in c4b.detail

    result = gate.validate_patch(create_disallowed)
    c4b = next(check for check in result.checks if check.name == "C4b_patch_action_target")
    assert not c4b.passed
    assert "not allowed" in c4b.detail

    scratch_create = PatchProposal(
        file_path="policies/scratch.py",
        action="create",
        code_content=policy_code,
    )
    result = gate.validate_patch(
        scratch_create,
        approved_hypothesis=scratch_create_hypothesis,
    )
    c4b = next(check for check in result.checks if check.name == "C4b_patch_action_target")
    assert c4b.passed

    scratch_delete = PatchProposal(
        file_path="policies/scratch.py",
        action="delete",
        code_content="",
    )
    result = gate.validate_patch(
        scratch_delete,
        approved_hypothesis=scratch_remove_hypothesis,
    )
    c4b = next(check for check in result.checks if check.name == "C4b_patch_action_target")
    assert c4b.passed
    assert result.passed


def test_contract_gate_surface_wildcard_is_segment_aware(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["research_surfaces"] = [
        {
            "name": "local",
            "kind": "operator",
            "description": "Local operators",
            "target_files": ["operators/*.py"],
        },
    ]
    legacy = legacy_problem_spec_from_v1(ProblemSpecV1(**payload))
    gate = ContractGate(legacy)
    direct = HypothesisProposal(
        hypothesis_text="Modify direct operator.",
        change_locus="local",
        action="modify",
        target_file="operators/local_a.py",
    )
    nested = HypothesisProposal(
        hypothesis_text="Modify nested operator.",
        change_locus="local",
        action="modify",
        target_file="operators/archive/evil.py",
    )

    direct_result = gate.validate_hypothesis(direct, [], [])
    nested_result = gate.validate_hypothesis(nested, [], [])
    direct_c3 = next(
        check for check in direct_result.checks if check.name == "C3_action_target"
    )
    nested_c3 = next(
        check for check in nested_result.checks if check.name == "C3_action_target"
    )

    assert direct_c3.passed
    assert nested_c3.passed is False
    assert "not in target files" in nested_c3.detail


def test_contract_gate_requires_operator_class_for_declared_operator_surface(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["research_surfaces"] = [
        {
            "name": "local",
            "kind": "operator",
            "description": "Local operators",
            "target_files": ["operators/*.py"],
        },
    ]
    legacy = legacy_problem_spec_from_v1(ProblemSpecV1(**payload))
    gate = ContractGate(legacy)

    patch = PatchProposal(
        file_path="operators/op.py",
        action="create",
        code_content="WEIGHT = 0.5\n",
    )
    result = gate.validate_patch(patch)
    c7 = next(check for check in result.checks if check.name == "C7_interface")
    assert not c7.passed
    assert "operator class" in c7.detail
