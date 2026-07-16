"""Focused tests for the lightweight candidate undefined-name check."""

from __future__ import annotations

from scion.core.models import PatchFileChange, PatchProposal
from scion.verification.gate import VerificationGate
from scion.verification.undefined_names import check_undefined_names


def _patch(code: str, *, additional: tuple[PatchFileChange, ...] = ()) -> PatchProposal:
    return PatchProposal(
        file_path="policies/baseline_modules/scheduler.py",
        action="modify",
        code_content=code,
        additional_changes=additional,
    )


def test_rejects_r7_style_stale_names_in_function_and_method_branches():
    result = check_undefined_names(_patch("""\
def update_function(pair_weights, pair_idx, failed):
    if failed:
        destroy_weights.record(d_idx, 0.0)
    pair_weights.record(pair_idx, 0.0)


class Scheduler:
    def update_method(self, pair_weights, pair_idx, infeasible):
        if infeasible:
            repair_weights.record(r_idx, 0.0)
        pair_weights.record(pair_idx, 0.0)
"""))

    assert result.passed is False
    assert result.name == "V1b_undefined_names"
    assert result.metadata["undefined_names"] == {
        "policies/baseline_modules/scheduler.py": [
            "d_idx",
            "destroy_weights",
            "r_idx",
            "repair_weights",
        ]
    }


def test_accepts_imports_closures_builtins_and_implicit_module_globals():
    result = check_undefined_names(_patch("""\
from __future__ import annotations

import math
from collections import defaultdict


def make_score(scale):
    samples = defaultdict(list)

    def score(values: list[float]) -> float:
        samples[__name__].append(len(values))
        return math.fsum(value * scale for value in values) + sum(range(1))

    return score
"""))

    assert result.passed is True
    assert result.metadata["undefined_names"] == {}


def test_checks_additional_changes_as_complete_modules():
    result = check_undefined_names(
        _patch(
            "def solve(instance):\n    return instance\n",
            additional=(
                PatchFileChange(
                    file_path="policies/baseline_modules/helper.py",
                    action="modify",
                    code_content=(
                        "def choose(pair_weights):\n"
                        "    return pair_weights.choose(missing_rng)\n"
                    ),
                ),
            ),
        )
    )

    assert result.passed is False
    assert result.metadata["undefined_names"] == {
        "policies/baseline_modules/helper.py": ["missing_rng"]
    }
    assert "helper.py: missing_rng" in result.detail


def test_wildcard_import_uses_file_local_fallback_without_false_positive():
    result = check_undefined_names(_patch("""\
from runtime_plugin import *


def solve(instance):
    return dynamically_exported_solver(instance)
"""))

    assert result.passed is True
    assert result.metadata["wildcard_import_files"] == [
        "policies/baseline_modules/scheduler.py"
    ]
    assert "wildcard import fallback" in result.detail


def test_gate_runs_undefined_name_check_after_syntax_and_before_interface():
    patch = _patch("""\
class Scheduler:
    def execute(self, solution, rng):
        return stale_weights.choose(rng)
""")

    result = VerificationGate().run("/tmp", "", patch)

    assert result.passed is False
    assert [check.name for check in result.checks] == [
        "V1_syntax",
        "V1b_undefined_names",
    ]
    assert result.first_failure == "V1b_undefined_names"
