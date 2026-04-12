"""Tests for ContractGate (T05) — all 10 checks, positive and negative cases."""
from __future__ import annotations

import pytest

from scion.config.problem import ProblemSpec, SearchSpace, SolverConfig
from scion.contract.gate import ContractGate
from scion.core.models import (
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
)

import datetime


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_spec(
    categories=("selection", "crossover", "mutation"),
    editable=("operators/*.py",),
    frozen=("solver.py", "oracle.py", "operators/base.py"),
    import_whitelist=("random", "math", "copy", "itertools", "numpy"),
) -> ProblemSpec:
    return ProblemSpec(
        name="test_problem",
        root_dir="/tmp/test",
        operator_categories=list(categories),
        search_space=SearchSpace(
            editable=list(editable),
            frozen=list(frozen),
            import_whitelist=list(import_whitelist),
        ),
        solver=SolverConfig(),
    )


@pytest.fixture()
def spec() -> ProblemSpec:
    return make_spec()


@pytest.fixture()
def gate(spec: ProblemSpec) -> ContractGate:
    return ContractGate(spec)


def _hyp_record(
    change_locus: str = "selection",
    action: str = "modify",
    target_file: str = "operators/sel.py",
) -> HypothesisRecord:
    return HypothesisRecord(
        hypothesis_id="h-001",
        branch_id="b-001",
        change_locus=change_locus,
        action=action,
        status="active",
        target_file=target_file,
        created_at=datetime.datetime.now(),
    )


# ---------------------------------------------------------------------------
# C1: Schema
# ---------------------------------------------------------------------------


class TestC1Schema:
    def test_valid_hypothesis_passes(self, gate: ContractGate):
        h = HypothesisProposal(
            hypothesis_text="Try tournament selection",
            change_locus="selection",
            action="modify",
            target_file="operators/sel.py",
        )
        result = gate.validate_hypothesis(h, [], [])
        c1 = next(c for c in result.checks if c.name == "C1_schema")
        assert c1.passed

    def test_empty_hypothesis_text_fails(self, gate: ContractGate):
        h = HypothesisProposal(
            hypothesis_text="  ",
            change_locus="selection",
            action="modify",
            target_file="operators/sel.py",
        )
        result = gate.validate_hypothesis(h, [], [])
        c1 = next(c for c in result.checks if c.name == "C1_schema")
        assert not c1.passed
        assert not result.passed

    def test_empty_change_locus_fails(self, gate: ContractGate):
        h = HypothesisProposal(
            hypothesis_text="valid text",
            change_locus="",
            action="modify",
            target_file="operators/sel.py",
        )
        result = gate.validate_hypothesis(h, [], [])
        c1 = next(c for c in result.checks if c.name == "C1_schema")
        assert not c1.passed


# ---------------------------------------------------------------------------
# C2: change_locus in categories
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# C3: action-target consistency
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# C4: File whitelist
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# C5: Frozen files
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# C6: AST syntax
# ---------------------------------------------------------------------------


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

    def test_delete_action_skips_syntax(self, gate: ContractGate):
        patch = PatchProposal(
            file_path="operators/op.py",
            action="delete",
            code_content="",
        )
        result = gate.validate_patch(patch)
        c6 = next(c for c in result.checks if c.name == "C6_ast_syntax")
        assert c6.passed


# ---------------------------------------------------------------------------
# C7: Interface signature
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# C8: Import whitelist
# ---------------------------------------------------------------------------


class TestC8ImportWhitelist:
    def test_whitelisted_import_passes(self, gate: ContractGate):
        code = "import random\nimport math\n\nclass Op:\n    def execute(self, solution, rng):\n        pass\n"
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c8 = next(c for c in result.checks if c.name == "C8_import_whitelist")
        assert c8.passed

    def test_non_whitelisted_import_fails(self, gate: ContractGate):
        code = "import subprocess\n\nclass Op:\n    def execute(self, solution, rng):\n        pass\n"
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c8 = next(c for c in result.checks if c.name == "C8_import_whitelist")
        assert not c8.passed
        assert not result.passed

    def test_from_import_non_whitelisted_fails(self, gate: ContractGate):
        code = "from socket import socket\n\nclass Op:\n    def execute(self, solution, rng):\n        pass\n"
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c8 = next(c for c in result.checks if c.name == "C8_import_whitelist")
        assert not c8.passed


# ---------------------------------------------------------------------------
# C9: Sensitive API
# ---------------------------------------------------------------------------


class TestC9SensitiveApi:
    def test_clean_code_passes(self, gate: ContractGate):
        code = (
            "import random\n"
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        return random.choice(solution)\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9 = next(c for c in result.checks if c.name == "C9_sensitive_api")
        assert c9.passed

    def test_eval_is_blocked(self, gate: ContractGate):
        code = (
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        return eval('1+1')\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9 = next(c for c in result.checks if c.name == "C9_sensitive_api")
        assert not c9.passed
        assert not result.passed

    def test_exec_is_blocked(self, gate: ContractGate):
        code = (
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        exec('x=1')\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9 = next(c for c in result.checks if c.name == "C9_sensitive_api")
        assert not c9.passed

    def test_os_system_is_blocked(self, gate: ContractGate):
        code = (
            "import os\n"
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        os.system('ls')\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9 = next(c for c in result.checks if c.name == "C9_sensitive_api")
        assert not c9.passed

    def test_open_write_is_blocked(self, gate: ContractGate):
        code = (
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        open('out.txt', 'w').write('x')\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9 = next(c for c in result.checks if c.name == "C9_sensitive_api")
        assert not c9.passed


# ---------------------------------------------------------------------------
# C10: Novelty
# ---------------------------------------------------------------------------


class TestC10Novelty:
    def test_novel_hypothesis_passes(self, gate: ContractGate):
        h = HypothesisProposal(
            hypothesis_text="New idea",
            change_locus="selection",
            action="modify",
            target_file="operators/sel.py",
        )
        result = gate.validate_hypothesis(h, [], [])
        c10 = next(c for c in result.checks if c.name == "C10_novelty")
        assert c10.passed

    def test_duplicate_active_fails(self, gate: ContractGate):
        h = HypothesisProposal(
            hypothesis_text="New idea",
            change_locus="selection",
            action="modify",
            target_file="operators/sel.py",
        )
        active = [_hyp_record("selection", "modify", "operators/sel.py")]
        result = gate.validate_hypothesis(h, active, [])
        c10 = next(c for c in result.checks if c.name == "C10_novelty")
        assert not c10.passed
        assert not result.passed

    def test_duplicate_blacklist_fails(self, gate: ContractGate):
        h = HypothesisProposal(
            hypothesis_text="New idea",
            change_locus="selection",
            action="modify",
            target_file="operators/sel.py",
        )
        blacklisted = [_hyp_record("selection", "modify", "operators/sel.py")]
        result = gate.validate_hypothesis(h, [], blacklisted)
        c10 = next(c for c in result.checks if c.name == "C10_novelty")
        assert not c10.passed

    def test_different_target_is_novel(self, gate: ContractGate):
        h = HypothesisProposal(
            hypothesis_text="New idea for different op",
            change_locus="selection",
            action="modify",
            target_file="operators/sel_v2.py",
        )
        active = [_hyp_record("selection", "modify", "operators/sel.py")]
        result = gate.validate_hypothesis(h, active, [])
        c10 = next(c for c in result.checks if c.name == "C10_novelty")
        assert c10.passed


# ---------------------------------------------------------------------------
# ContractResult structure
# ---------------------------------------------------------------------------


class TestContractResultStructure:
    def test_all_pass_means_passed(self, gate: ContractGate):
        h = HypothesisProposal(
            hypothesis_text="good hypothesis",
            change_locus="selection",
            action="modify",
            target_file="operators/sel.py",
        )
        result = gate.validate_hypothesis(h, [], [])
        assert result.passed
        assert result.failure_reason is None
        assert all(c.passed for c in result.checks)

    def test_first_failure_recorded(self, gate: ContractGate):
        h = HypothesisProposal(
            hypothesis_text="",  # C1 fails
            change_locus="selection",
            action="modify",
            target_file="operators/sel.py",
        )
        result = gate.validate_hypothesis(h, [], [])
        assert not result.passed
        assert result.failure_reason is not None
        assert "C1_schema" in result.failure_reason

    def test_checks_are_tuple_of_check_results(self, gate: ContractGate):
        h = HypothesisProposal(
            hypothesis_text="check",
            change_locus="selection",
            action="modify",
            target_file="operators/sel.py",
        )
        result = gate.validate_hypothesis(h, [], [])
        assert isinstance(result.checks, tuple)
        for c in result.checks:
            assert hasattr(c, "name")
            assert hasattr(c, "passed")
            assert hasattr(c, "elapsed_ms")


# ---------------------------------------------------------------------------
# C9b: Non-rng random source detection (T21)
# ---------------------------------------------------------------------------


def _patch(code: str) -> PatchProposal:
    return PatchProposal(
        file_path="operators/op.py",
        action="modify",
        code_content=code,
    )


def _c9b(gate: ContractGate, code: str):
    result = gate.validate_patch(_patch(code))
    return next(c for c in result.checks if c.name == "C9b_non_rng_random")


class TestC9bNonRngRandom:
    def test_c9b_catches_uuid4(self, gate: ContractGate):
        code = (
            "import uuid\n"
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        vid = uuid.uuid4()\n"
            "        return solution\n"
        )
        c = _c9b(gate, code)
        assert not c.passed
        assert "uuid.uuid4" in c.detail

    def test_c9b_catches_uuid1(self, gate: ContractGate):
        code = (
            "import uuid\n"
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        vid = uuid.uuid1()\n"
            "        return solution\n"
        )
        c = _c9b(gate, code)
        assert not c.passed

    def test_c9b_catches_random_random(self, gate: ContractGate):
        code = (
            "import random\n"
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        x = random.random()\n"
            "        return solution\n"
        )
        c = _c9b(gate, code)
        assert not c.passed
        assert "random.random" in c.detail

    def test_c9b_catches_random_randint(self, gate: ContractGate):
        code = (
            "import random\n"
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        n = random.randint(0, 10)\n"
            "        return solution\n"
        )
        c = _c9b(gate, code)
        assert not c.passed

    def test_c9b_catches_os_urandom(self, gate: ContractGate):
        code = (
            "import os\n"
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        b = os.urandom(16)\n"
            "        return solution\n"
        )
        c = _c9b(gate, code)
        assert not c.passed
        assert "os.urandom" in c.detail

    def test_c9b_catches_secrets_token_hex(self, gate: ContractGate):
        code = (
            "import secrets\n"
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        tok = secrets.token_hex()\n"
            "        return solution\n"
        )
        c = _c9b(gate, code)
        assert not c.passed
        assert "secrets.token_hex" in c.detail

    def test_c9b_catches_secrets_token_bytes(self, gate: ContractGate):
        code = (
            "import secrets\n"
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        tok = secrets.token_bytes(16)\n"
            "        return solution\n"
        )
        c = _c9b(gate, code)
        assert not c.passed

    def test_c9b_catches_secrets_token_urlsafe(self, gate: ContractGate):
        code = (
            "import secrets\n"
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        tok = secrets.token_urlsafe()\n"
            "        return solution\n"
        )
        c = _c9b(gate, code)
        assert not c.passed

    def test_c9b_allows_rng_methods(self, gate: ContractGate):
        code = (
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        x = rng.random()\n"
            "        idx = rng.randint(0, 5)\n"
            "        item = rng.choice([1, 2, 3])\n"
            "        return solution\n"
        )
        c = _c9b(gate, code)
        assert c.passed

    def test_c9b_allows_Random_class_instantiation(self, gate: ContractGate):
        code = (
            "import random\n"
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        r = random.Random(42)\n"
            "        return solution\n"
        )
        c = _c9b(gate, code)
        assert c.passed

    def test_c9b_allows_clean_code(self, gate: ContractGate):
        code = (
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        new_sol = solution.deep_copy()\n"
            "        return new_sol\n"
        )
        c = _c9b(gate, code)
        assert c.passed

    def test_c9b_delete_action_skipped(self, gate: ContractGate):
        patch = PatchProposal(
            file_path="operators/op.py",
            action="delete",
            code_content="",
        )
        result = gate.validate_patch(patch)
        c9b = next((c for c in result.checks if c.name == "C9b_non_rng_random"), None)
        # delete short-circuits before reaching C9b, so it may not be present
        if c9b is not None:
            assert c9b.passed

    # Sprint G-patch: import-from and alias coverage
    def test_c9b_catches_from_random_import_choice(self, gate: ContractGate):
        code = (
            "from random import choice\n"
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        x = choice([1, 2, 3])\n"
            "        return solution\n"
        )
        c = _c9b(gate, code)
        assert not c.passed

    def test_c9b_catches_from_uuid_import_uuid4(self, gate: ContractGate):
        code = (
            "from uuid import uuid4\n"
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        vid = uuid4()\n"
            "        return solution\n"
        )
        c = _c9b(gate, code)
        assert not c.passed

    def test_c9b_catches_import_random_as_alias(self, gate: ContractGate):
        code = (
            "import random as r\n"
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        x = r.choice([1, 2, 3])\n"
            "        return solution\n"
        )
        c = _c9b(gate, code)
        assert not c.passed

    def test_c9b_allows_rng_param_choice(self, gate: ContractGate):
        """rng.choice() must NOT be flagged — rng is the operator's legitimate parameter."""
        code = (
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        x = rng.choice([1, 2, 3])\n"
            "        return solution\n"
        )
        c = _c9b(gate, code)
        assert c.passed

