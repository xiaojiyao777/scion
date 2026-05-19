"""Tests for ContractGate (T05) — all 10 checks, positive and negative cases."""
from __future__ import annotations

import pytest
from types import SimpleNamespace

from scion.config.problem import ProblemSpec, SearchSpace, SolverConfig
from scion.contract.gate import ContractGate
from scion.core.models import (
    HypothesisProposal,
    HypothesisRecord,
    MechanismChange,
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
    hypothesis_text: str = "New idea",
) -> HypothesisRecord:
    return HypothesisRecord(
        hypothesis_id="h-001",
        branch_id="b-001",
        change_locus=change_locus,
        action=action,
        status="active",
        target_file=target_file,
        hypothesis_text=hypothesis_text,
        created_at=datetime.datetime.now(),
    )


# ---------------------------------------------------------------------------
# C1: Schema
# ---------------------------------------------------------------------------














# ---------------------------------------------------------------------------
# C2: change_locus in categories
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# C3: action-target consistency
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# C4: File whitelist
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# C5: Frozen files
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# C6: AST syntax
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# C7: Interface signature
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# C8: Import whitelist
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# C9: Sensitive API
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# C9c: Complexity bound
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# C10: Novelty
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# ContractResult structure
# ---------------------------------------------------------------------------




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


__all__ = [
    name
    for name in globals()
    if not (name.startswith("__") and name.endswith("__"))
]
