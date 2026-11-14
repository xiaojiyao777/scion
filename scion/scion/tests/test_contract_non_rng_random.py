"""Focused tests split from test_contract.py."""

from .contract_test_support import *  # noqa: F401,F403

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
