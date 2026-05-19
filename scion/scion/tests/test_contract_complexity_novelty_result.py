"""Focused tests split from test_contract.py."""

from .contract_test_support import *  # noqa: F401,F403

class TestC9cComplexityBound:
    def test_pairwise_combinations_with_constant_k_pass(self, gate: ContractGate):
        code = (
            "from itertools import combinations\n"
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        for a, b in combinations(sorted(solution.vehicles), 2):\n"
            "            pass\n"
            "        return solution\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9c = next(c for c in result.checks if c.name == "C9c_complexity_bound")
        assert c9c.passed

    def test_high_order_combinations_fail(self, gate: ContractGate):
        code = (
            "from itertools import combinations\n"
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        for subset in combinations(sorted(solution.vehicles), 4):\n"
            "            pass\n"
            "        return solution\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9c = next(c for c in result.checks if c.name == "C9c_complexity_bound")
        assert not c9c.passed
        assert not result.passed
        assert "high-order" in c9c.detail

    def test_variable_size_combinations_fail(self, gate: ContractGate):
        code = (
            "from itertools import combinations\n"
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        vids = sorted(solution.vehicles)\n"
            "        for size in range(2, min(5, len(vids) + 1)):\n"
            "            for subset in combinations(vids, size):\n"
            "                pass\n"
            "        return solution\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9c = next(c for c in result.checks if c.name == "C9c_complexity_bound")
        assert not c9c.passed
        assert "variable_k" in c9c.detail

    def test_aliased_high_order_combinations_fail(self, gate: ContractGate):
        code = (
            "from itertools import combinations as combos\n"
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        routes = sorted(solution.vehicles)\n"
            "        for subset in combos(routes, 3):\n"
            "            pass\n"
            "        return solution\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9c = next(c for c in result.checks if c.name == "C9c_complexity_bound")
        assert not c9c.passed
        assert "combinations(..., 3)" in c9c.detail

    def test_permutations_fail(self, gate: ContractGate):
        code = (
            "import itertools\n"
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        for route_order in itertools.permutations(solution.routes):\n"
            "            pass\n"
            "        return solution\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9c = next(c for c in result.checks if c.name == "C9c_complexity_bound")
        assert not c9c.passed
        assert "permutations" in c9c.detail

    def test_product_over_two_problem_scale_iterables_fails(self, gate: ContractGate):
        code = (
            "from itertools import product\n"
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        customers = solution.customer_ids\n"
            "        for route, customer in product(solution.routes, customers):\n"
            "            pass\n"
            "        return solution\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9c = next(c for c in result.checks if c.name == "C9c_complexity_bound")
        assert not c9c.passed
        assert "product" in c9c.detail

    def test_non_itertools_object_methods_named_like_itertools_pass(self, gate: ContractGate):
        code = (
            "class Helper:\n"
            "    def product(self, a, b):\n"
            "        return []\n"
            "    def permutations(self, a):\n"
            "        return []\n"
            "    def combinations(self, a, k):\n"
            "        return []\n"
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        helper = Helper()\n"
            "        for item in helper.product(solution.routes, solution.customer_ids):\n"
            "            pass\n"
            "        for item in helper.permutations(solution.routes):\n"
            "            pass\n"
            "        for item in helper.combinations(solution.routes, 4):\n"
            "            pass\n"
            "        return solution\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9c = next(c for c in result.checks if c.name == "C9c_complexity_bound")
        assert c9c.passed

    def test_itertools_module_alias_product_still_fails(self, gate: ContractGate):
        code = (
            "import itertools as it\n"
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        for route, customer in it.product(solution.routes, solution.customer_ids):\n"
            "            pass\n"
            "        return solution\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9c = next(c for c in result.checks if c.name == "C9c_complexity_bound")
        assert not c9c.passed
        assert "product" in c9c.detail

    def test_while_true_fails(self, gate: ContractGate):
        code = (
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        while True:\n"
            "            break\n"
            "        return solution\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9c = next(c for c in result.checks if c.name == "C9c_complexity_bound")
        assert not c9c.passed
        assert "uncapped while" in c9c.detail

    def test_while_true_with_counter_bound_passes(self, gate: ContractGate):
        code = (
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        i = 0\n"
            "        max_iter = 10\n"
            "        while True:\n"
            "            i += 1\n"
            "            if i >= max_iter:\n"
            "                break\n"
            "        return solution\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9c = next(c for c in result.checks if c.name == "C9c_complexity_bound")
        assert c9c.passed

    def test_while_true_with_collection_progress_passes(self, gate: ContractGate):
        code = (
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        unvisited = set(solution.customer_ids)\n"
            "        route = []\n"
            "        while True:\n"
            "            if not unvisited:\n"
            "                break\n"
            "            customer = min(unvisited)\n"
            "            route.append(customer)\n"
            "            unvisited.remove(customer)\n"
            "        return solution\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9c = next(c for c in result.checks if c.name == "C9c_complexity_bound")
        assert c9c.passed

    def test_bounded_counter_while_passes(self, gate: ContractGate):
        code = (
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        i = 0\n"
            "        while i < 10:\n"
            "            i += 1\n"
            "        return solution\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9c = next(c for c in result.checks if c.name == "C9c_complexity_bound")
        assert c9c.passed

    def test_bounded_collection_size_growth_while_passes(self, gate: ContractGate):
        code = (
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        customers = list(solution.customer_ids)\n"
            "        cap = min(8, len(customers))\n"
            "        neighbors = []\n"
            "        while len(neighbors) < cap:\n"
            "            neighbors.append(customers[len(neighbors)])\n"
            "        return solution\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9c = next(c for c in result.checks if c.name == "C9c_complexity_bound")
        assert c9c.passed

    def test_collection_size_growth_without_bound_fails(self, gate: ContractGate):
        code = (
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        target = solution.customer_count\n"
            "        items = []\n"
            "        while len(items) < threshold:\n"
            "            items.append(target)\n"
            "        return solution\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9c = next(c for c in result.checks if c.name == "C9c_complexity_bound")
        assert not c9c.passed
        assert "uncapped while" in c9c.detail

    def test_collection_size_self_assignment_does_not_count_as_progress(
        self,
        gate: ContractGate,
    ):
        code = (
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        cap = min(8, len(solution.customer_ids))\n"
            "        items = []\n"
            "        while len(items) < cap:\n"
            "            items = items\n"
            "        return solution\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9c = next(c for c in result.checks if c.name == "C9c_complexity_bound")
        assert not c9c.passed
        assert "uncapped while" in c9c.detail

    def test_runtime_guarded_while_passes(self, gate: ContractGate):
        code = (
            "class Context:\n"
            "    def remaining_time(self):\n"
            "        return 1.0\n"
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    while context.remaining_time() > 0.5:\n"
            "        break\n"
            "    while True:\n"
            "        if context.remaining_time() < 0.25:\n"
            "            break\n"
            "    return None\n"
        )
        patch = PatchProposal(
            file_path="operators/op.py",
            action="create",
            code_content=code,
        )
        result = gate.validate_patch(patch)
        c9c = next(c for c in result.checks if c.name == "C9c_complexity_bound")
        assert c9c.passed

    def test_three_level_problem_scale_nested_loops_fail(self, gate: ContractGate):
        code = (
            "class Op:\n"
            "    def execute(self, solution, rng):\n"
            "        for route in solution.routes:\n"
            "            for customer in route:\n"
            "                for other in solution.customer_ids:\n"
            "                    pass\n"
            "        return solution\n"
        )
        patch = PatchProposal(file_path="operators/op.py", action="create", code_content=code)
        result = gate.validate_patch(patch)
        c9c = next(c for c in result.checks if c.name == "C9c_complexity_bound")
        assert not c9c.passed
        assert "three-level" in c9c.detail


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
