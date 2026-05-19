"""Focused tests split from test_contract.py."""

from .contract_test_support import *  # noqa: F401,F403

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

    def test_dynamic_import_is_blocked(self, gate: ContractGate):
        code = (
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        mod = __import__('math')\n"
            "        return mod.sqrt(4)\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9 = next(c for c in result.checks if c.name == "C9_sensitive_api")
        assert not c9.passed
        assert "__import__" in c9.detail

    def test_dynamic_import_alias_is_blocked(self, gate: ContractGate):
        code = (
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        imp = __import__\n"
            "        return imp('os').system('true')\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9 = next(c for c in result.checks if c.name == "C9_sensitive_api")
        assert not c9.passed
        assert "__import__" in c9.detail

    def test_dynamic_import_result_alias_is_blocked(self, gate: ContractGate):
        code = (
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        imp = __import__\n"
            "        mod = imp('os')\n"
            "        return mod.system('true')\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9 = next(c for c in result.checks if c.name == "C9_sensitive_api")
        assert not c9.passed
        assert "dynamic_import.system" in c9.detail

    def test_importlib_import_module_is_blocked(self, gate: ContractGate):
        code = (
            "import importlib\n"
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        return importlib.import_module('math').sqrt(4)\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9 = next(c for c in result.checks if c.name == "C9_sensitive_api")
        assert not c9.passed
        assert "importlib.import_module" in c9.detail

    def test_importlib_import_module_alias_is_blocked(self, gate: ContractGate):
        code = (
            "import importlib\n"
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        dyn = importlib.import_module\n"
            "        return dyn('os').system('true')\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9 = next(c for c in result.checks if c.name == "C9_sensitive_api")
        assert not c9.passed
        assert "importlib.import_module" in c9.detail

    def test_os_system_callable_alias_is_blocked(self, gate: ContractGate):
        code = (
            "import os\n"
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        run = os.system\n"
            "        return run('true')\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9 = next(c for c in result.checks if c.name == "C9_sensitive_api")
        assert not c9.passed
        assert "os.system" in c9.detail

    def test_literal_reflective_os_system_is_blocked(self, gate: ContractGate):
        code = (
            "import os\n"
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        return getattr(os, 'system')('true')\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9 = next(c for c in result.checks if c.name == "C9_sensitive_api")
        assert not c9.passed
        assert "getattr(os, 'system')" in c9.detail

    def test_literal_reflective_importlib_import_module_is_blocked(
        self,
        gate: ContractGate,
    ):
        code = (
            "import importlib\n"
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        return getattr(importlib, 'import_module')('math')\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9 = next(c for c in result.checks if c.name == "C9_sensitive_api")
        assert not c9.passed
        assert "getattr(importlib, 'import_module')" in c9.detail

    def test_reflective_dynamic_getattr_is_blocked(self, gate: ContractGate):
        code = (
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        attr = 'vehicles'\n"
            "        return getattr(solution, attr)\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9 = next(c for c in result.checks if c.name == "C9_sensitive_api")
        assert not c9.passed
        assert "dynamic_name" in c9.detail

    def test_os_environ_is_blocked(self, gate: ContractGate):
        code = (
            "import os\n"
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        return os.environ.get('SCION_CASE')\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9 = next(c for c in result.checks if c.name == "C9_sensitive_api")
        assert not c9.passed
        assert "os.environ" in c9.detail

    def test_context_baseline_getattr_alias_is_blocked(self, gate: ContractGate):
        gate = ContractGate(
            make_spec(editable=("operators/*.py", "policies/baseline_algorithm.py"))
        )
        code = (
            "def solve(context):\n"
            "    get = getattr\n"
            "    run_baseline = get(context, 'baseline')\n"
            "    return run_baseline(time_limit_sec=0.1)\n"
        )
        patch = PatchProposal(
            file_path="policies/baseline_algorithm.py",
            action="modify",
            code_content=code,
        )
        result = gate.validate_patch(patch)
        c9 = next(c for c in result.checks if c.name == "C9_sensitive_api")
        assert not c9.passed
        assert "context.baseline alias" in c9.detail
