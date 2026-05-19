"""Focused tests split from test_contract.py."""

from .contract_test_support import *  # noqa: F401,F403

class TestC2ChangeLocus:
    def test_valid_category_passes(self, gate: ContractGate):
        h = HypothesisProposal(
            hypothesis_text="Try mutation strategy",
            change_locus="mutation",
            action="modify",
            target_file="operators/mut.py",
        )
        result = gate.validate_hypothesis(h, [], [])
        c2 = next(c for c in result.checks if c.name == "C2_change_locus")
        assert c2.passed

    def test_unknown_category_fails(self, gate: ContractGate):
        h = HypothesisProposal(
            hypothesis_text="Try mutation strategy",
            change_locus="unknown_category",
            action="modify",
            target_file="operators/mut.py",
        )
        result = gate.validate_hypothesis(h, [], [])
        c2 = next(c for c in result.checks if c.name == "C2_change_locus")
        assert not c2.passed
        assert not result.passed


class TestC3ActionTarget:
    def test_modify_with_target_passes(self, gate: ContractGate):
        h = HypothesisProposal(
            hypothesis_text="modify operator",
            change_locus="selection",
            action="modify",
            target_file="operators/sel.py",
        )
        result = gate.validate_hypothesis(h, [], [])
        c3 = next(c for c in result.checks if c.name == "C3_action_target")
        assert c3.passed

    def test_modify_without_target_fails(self, gate: ContractGate):
        h = HypothesisProposal(
            hypothesis_text="modify operator",
            change_locus="selection",
            action="modify",
            target_file=None,
        )
        result = gate.validate_hypothesis(h, [], [])
        c3 = next(c for c in result.checks if c.name == "C3_action_target")
        assert not c3.passed

    def test_remove_without_target_fails(self, gate: ContractGate):
        h = HypothesisProposal(
            hypothesis_text="remove old operator",
            change_locus="selection",
            action="remove",
            target_file=None,
        )
        result = gate.validate_hypothesis(h, [], [])
        c3 = next(c for c in result.checks if c.name == "C3_action_target")
        assert not c3.passed

    def test_create_new_passes_without_target(self, gate: ContractGate):
        h = HypothesisProposal(
            hypothesis_text="create new operator",
            change_locus="selection",
            action="create_new",
            target_file=None,
        )
        result = gate.validate_hypothesis(h, [], [])
        c3 = next(c for c in result.checks if c.name == "C3_action_target")
        assert c3.passed


class TestC4FileWhitelist:
    def test_editable_file_passes(self, gate: ContractGate):
        patch = PatchProposal(
            file_path="operators/my_op.py",
            action="create",
            code_content="",
        )
        result = gate.validate_patch(patch)
        c4 = next(c for c in result.checks if c.name == "C4_file_whitelist")
        assert c4.passed

    def test_non_editable_file_fails(self, gate: ContractGate):
        patch = PatchProposal(
            file_path="main.py",
            action="modify",
            code_content="x = 1",
        )
        result = gate.validate_patch(patch)
        c4 = next(c for c in result.checks if c.name == "C4_file_whitelist")
        assert not c4.passed
        assert not result.passed

    def test_path_traversal_file_fails(self, gate: ContractGate):
        patch = PatchProposal(
            file_path="operators/../../outside.py",
            action="create",
            code_content="x = 1",
        )
        result = gate.validate_patch(patch)
        c4 = next(c for c in result.checks if c.name == "C4_file_whitelist")
        assert not c4.passed
        assert "path segment" in c4.detail
        assert not result.passed

    def test_absolute_file_path_fails(self, gate: ContractGate):
        patch = PatchProposal(
            file_path="/operators/my_op.py",
            action="create",
            code_content="x = 1",
        )
        result = gate.validate_patch(patch)
        c4 = next(c for c in result.checks if c.name == "C4_file_whitelist")
        assert not c4.passed
        assert "relative" in c4.detail
        assert not result.passed

    def test_backslash_file_path_fails(self, gate: ContractGate):
        patch = PatchProposal(
            file_path=r"operators\my_op.py",
            action="create",
            code_content="x = 1",
        )
        result = gate.validate_patch(patch)
        c4 = next(c for c in result.checks if c.name == "C4_file_whitelist")
        assert not c4.passed
        assert "POSIX" in c4.detail
        assert not result.passed

    def test_single_segment_wildcard_rejects_nested_path(self, gate: ContractGate):
        patch = PatchProposal(
            file_path="operators/archive/evil.py",
            action="create",
            code_content="x = 1",
        )
        result = gate.validate_patch(patch)
        c4 = next(c for c in result.checks if c.name == "C4_file_whitelist")
        assert not c4.passed
        assert not result.passed


class TestC5FrozenFiles:
    def test_non_frozen_passes(self, gate: ContractGate):
        patch = PatchProposal(
            file_path="operators/new_op.py",
            action="create",
            code_content="x = 1",
        )
        result = gate.validate_patch(patch)
        c5 = next(c for c in result.checks if c.name == "C5_frozen_files")
        assert c5.passed

    def test_solver_py_is_frozen(self, gate: ContractGate):
        patch = PatchProposal(
            file_path="solver.py",
            action="modify",
            code_content="x = 1",
        )
        result = gate.validate_patch(patch)
        c5 = next(c for c in result.checks if c.name == "C5_frozen_files")
        assert not c5.passed
        assert not result.passed

    def test_solver_runtime_helpers_can_be_frozen(self):
        gate = ContractGate(
            make_spec(
                editable=("operators/*.py", "solver_runtime/*.py"),
                frozen=("solver.py", "solver_runtime/*.py"),
            )
        )
        patch = PatchProposal(
            file_path="solver_runtime/timing.py",
            action="modify",
            code_content="x = 1",
        )
        result = gate.validate_patch(patch)
        c5 = next(c for c in result.checks if c.name == "C5_frozen_files")
        assert not c5.passed
        assert not result.passed

    def test_oracle_py_is_frozen(self, gate: ContractGate):
        patch = PatchProposal(
            file_path="oracle.py",
            action="modify",
            code_content="x = 1",
        )
        result = gate.validate_patch(patch)
        c5 = next(c for c in result.checks if c.name == "C5_frozen_files")
        assert not c5.passed

    def test_operators_base_is_frozen(self, gate: ContractGate):
        patch = PatchProposal(
            file_path="operators/base.py",
            action="modify",
            code_content="x = 1",
        )
        result = gate.validate_patch(patch)
        c5 = next(c for c in result.checks if c.name == "C5_frozen_files")
        assert not c5.passed


class TestC6AstSyntax:
    def test_valid_python_passes(self, gate: ContractGate):
        patch = PatchProposal(
            file_path="operators/op.py",
            action="create",
            code_content="class Op:\n    def execute(self, solution, rng):\n        pass\n",
        )
        result = gate.validate_patch(patch)
        c6 = next(c for c in result.checks if c.name == "C6_ast_syntax")
        assert c6.passed

    def test_invalid_python_fails(self, gate: ContractGate):
        patch = PatchProposal(
            file_path="operators/op.py",
            action="create",
            code_content="def broken(\n",
        )
        result = gate.validate_patch(patch)
        c6 = next(c for c in result.checks if c.name == "C6_ast_syntax")
        assert not c6.passed
        assert not result.passed

    def test_compile_time_syntax_error_fails(self, gate: ContractGate):
        patch = PatchProposal(
            file_path="operators/op.py",
            action="create",
            code_content=(
                "class Op:\n"
                "    def execute(self, solution, rng):\n"
                "        dict(attempted=1, attempted=0)\n"
            ),
        )
        result = gate.validate_patch(patch)
        c6 = next(c for c in result.checks if c.name == "C6_ast_syntax")
        assert not c6.passed
        assert "keyword argument repeated" in c6.detail
        assert not result.passed

    def test_delete_action_skips_syntax(self, gate: ContractGate):
        patch = PatchProposal(
            file_path="operators/op.py",
            action="delete",
            code_content="",
        )
        result = gate.validate_patch(patch)
        c6 = next(c for c in result.checks if c.name == "C6_ast_syntax")
        assert c6.passed


class TestC7InterfaceSignature:
    def test_correct_signature_passes(self, gate: ContractGate):
        code = (
            "class MyOp:\n"
            "    def execute(self, solution, rng):\n"
            "        return solution\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c7 = next(c for c in result.checks if c.name == "C7_interface")
        assert c7.passed

    def test_wrong_signature_fails(self, gate: ContractGate):
        code = (
            "class MyOp:\n"
            "    def execute(self, sol):\n"
            "        return sol\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c7 = next(c for c in result.checks if c.name == "C7_interface")
        assert not c7.passed
        assert not result.passed

    def test_problem_defined_signature_passes(self, spec: ProblemSpec):
        gate = ContractGate(
            spec,
            operator_execute_signature="execute(self, solution, instance, rng) -> TspSolution",
        )
        code = (
            "class MyOp:\n"
            "    def execute(self, solution, instance, rng):\n"
            "        return solution\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c7 = next(c for c in result.checks if c.name == "C7_interface")
        assert c7.passed

    def test_problem_defined_signature_rejects_legacy_args(self, spec: ProblemSpec):
        gate = ContractGate(
            spec,
            operator_execute_signature="execute(self, solution, instance, rng) -> TspSolution",
        )
        code = (
            "class MyOp:\n"
            "    def execute(self, solution, rng):\n"
            "        return solution\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c7 = next(c for c in result.checks if c.name == "C7_interface")
        assert not c7.passed
        assert "instance" in c7.detail

    def test_missing_execute_fails(self, gate: ContractGate):
        code = "class MyOp:\n    pass\n"
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c7 = next(c for c in result.checks if c.name == "C7_interface")
        assert not c7.passed

    def test_no_class_skips_check(self, gate: ContractGate):
        code = "WEIGHT = 0.5\n"
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c7 = next(c for c in result.checks if c.name == "C7_interface")
        assert c7.passed  # skipped, not a failure
