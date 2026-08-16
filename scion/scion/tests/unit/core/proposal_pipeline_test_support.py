from __future__ import annotations

import threading
from types import SimpleNamespace

from scion.core.models import (
    Branch,
    BranchState,
    ChampionState,
    HypothesisProposal,
    PatchProposal,
)
from scion.core.proposal_pipeline import ProposalPipeline

from ..editable_source_context_test_support import editable_code_context


class FakeProblemRuntime:
    def __init__(self, spec=None) -> None:
        self.spec = spec
        self.hypothesis_kwargs = None
        self.code_kwargs = None

    def build_hypothesis_context(self, **kwargs):
        self.hypothesis_kwargs = kwargs
        return {
            "problem_summary": "fixture",
            "branch_id": kwargs["branch"].branch_id,
            "research_surfaces": [{"name": "local_search", "kind": "operator"}],
            "champion_operators_code": "",
            "champion_stats": {},
        }

    def build_code_context(self, **kwargs):
        self.code_kwargs = kwargs
        hypothesis = kwargs["hypothesis"]
        return editable_code_context(
            {
                "problem_summary": "fixture",
                "branch_id": kwargs["branch"].branch_id,
                "approved_hypothesis": {
                    "hypothesis_text": hypothesis.hypothesis_text,
                    "change_locus": hypothesis.change_locus,
                    "action": hypothesis.action,
                    "target_file": hypothesis.target_file,
                    "predicted_direction": hypothesis.predicted_direction,
                    "target_weakness": hypothesis.target_weakness,
                    "expected_effect": hypothesis.expected_effect,
                    "suggested_weight": hypothesis.suggested_weight,
                },
                "target_file": hypothesis.target_file,
                "target_file_code": "",
                "operator_interface_spec": "",
                "editable_patterns": "operators/*.py",
                "frozen_patterns": "solver.py",
                "action": hypothesis.action,
            }
        )


class FakeCreative:
    def __init__(
        self,
        *,
        code_error: Exception | None = None,
    ) -> None:
        self.code_error = code_error
        self.hypothesis_calls = 0
        self.code_calls = 0
        self.hypothesis_context = None
        self.code_context = None
        self.hypothesis = HypothesisProposal(
            hypothesis_text="Bounded route-pair search.",
            change_locus="local_search",
            action="create_new",
            target_file="operators/bounded.py",
            suggested_weight=0.5,
            predicted_direction="improve",
            target_weakness="The current search lacks a bounded route-pair move.",
            expected_effect="Improve distance on screening cases without changing feasibility.",
        )
        self.patch = PatchProposal(
            file_path="operators/bounded.py",
            action="create",
            code_content=(
                "class Bounded:\n"
                "    def execute(self, solution, rng):\n"
                "        return solution\n"
            ),
        )

    def generate_hypothesis(self, context):
        self.hypothesis_calls += 1
        self.hypothesis_context = context
        return self.hypothesis

    def generate_code(self, context):
        self.code_calls += 1
        self.code_context = context
        if self.code_error is not None:
            raise self.code_error
        return self.patch

    def generate_direct_hypothesis(
        self,
        snapshot,
    ):
        return self.generate_hypothesis(snapshot.structured_context)

    def generate_direct_code(
        self,
        snapshot,
    ):
        return self.generate_code(snapshot.structured_context)


def _branch(branch_id: str = "branch-1") -> Branch:
    return Branch(
        branch_id=branch_id,
        state=BranchState.EXPLORE,
        base_champion_id=1,
    )


def _champion() -> ChampionState:
    return ChampionState(
        version=1,
        operator_pool={},
        code_snapshot_path="/tmp/champion",
    )


def _pipeline(
    *,
    creative: FakeCreative | None = None,
    branch_workspace: str = "/tmp/branch",
    problem_spec=None,
):
    branch = _branch()
    if problem_spec is None:
        problem_spec = SimpleNamespace(
            operator_categories=["local_search"],
            search_space=SimpleNamespace(
                editable=["operators/*.py"],
                frozen=[],
                import_whitelist=[],
            ),
            research_surfaces=[
                SimpleNamespace(
                    name="local_search",
                    kind="operator",
                    target_files=["operators/*.py"],
                    create_new_allowed=True,
                    modify_allowed=True,
                    remove_allowed=False,
                )
            ],
        )
    runtime = FakeProblemRuntime(spec=problem_spec)
    balance_exhausted = {"value": False}
    pipeline = ProposalPipeline(
        creative=creative or FakeCreative(),
        problem_runtime=runtime,
        branch_workspaces={branch.branch_id: branch_workspace},
        champion_lock=threading.Lock(),
        get_champion=_champion,
        step_history=[],
        mark_balance_exhausted=lambda: balance_exhausted.__setitem__("value", True),
    )
    return pipeline, branch, runtime, balance_exhausted


__all__ = [
    name for name in globals() if not (name.startswith("__") and name.endswith("__"))
]
