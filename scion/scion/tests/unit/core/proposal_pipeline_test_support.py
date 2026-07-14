from __future__ import annotations

import json
from pathlib import Path
import threading
from types import SimpleNamespace
from typing import Any, Mapping

import pytest

from scion.core.models import (
    Branch,
    BranchState,
    ChampionState,
    CheckResult,
    DecisionFeatures,
    FailureEvent,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    StepRecord,
    VerificationResult,
)
from scion.core.proposal_pipeline import ProposalPipeline
from scion.proposal.engine import PromptCallReceipt

from ..source_ledger_test_support import ledgerize_code_context
from scion.proposal.prompt_manifest_accounting import _provider_prompt_hash
from scion.core.public_refs import contains_absolute_path
from scion.proposal.engine import ProposalValidationError
from scion.proposal.llm_client import LLMBalanceError


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
            "research_surfaces": [
                {"name": "local_search", "kind": "operator"}
            ],
            "champion_operators_code": "",
            "champion_stats": {},
        }

    def build_code_context(self, **kwargs):
        self.code_kwargs = kwargs
        hypothesis = kwargs["hypothesis"]
        return ledgerize_code_context({
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
        })

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
        self.attempt_audits: dict[str, Mapping[str, Any]] = {}
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

    @staticmethod
    def _receipt(snapshot) -> PromptCallReceipt:
        trace_ref = f"artifacts/llm_traces/{snapshot.render_kind}-fixture.json"
        return PromptCallReceipt(
            request_kind=snapshot.render_kind,
            trace_ref=trace_ref,
            prompt_manifest_ref=f"{trace_ref}#/prompt_manifest",
            raw_response_ref=f"{trace_ref}#/response",
            prompt_hash=_provider_prompt_hash(
                snapshot.system_blocks,
                snapshot.user_prompt,
            ),
            context_digest=snapshot.context_digest,
            provider_ok=True,
            ok=True,
        )

    def generate_hypothesis_with_receipt(self, context, snapshot):
        return self.generate_hypothesis(context), self._receipt(snapshot)

    def generate_code_with_receipt(self, context, snapshot):
        return self.generate_code(context), self._receipt(snapshot)

    def generate_direct_hypothesis_with_receipt(
        self,
        context,
        snapshot,
        *,
        attempt_audit=None,
    ):
        if attempt_audit is not None:
            self.attempt_audits["hypothesis"] = dict(attempt_audit)
        return self.generate_hypothesis_with_receipt(context, snapshot)

    def generate_direct_code_with_receipt(
        self,
        context,
        snapshot,
        *,
        attempt_audit=None,
    ):
        if attempt_audit is not None:
            self.attempt_audits["code"] = dict(attempt_audit)
        return self.generate_code_with_receipt(context, snapshot)

class FakeBranchController:
    def __init__(self, branches):
        self._branches = list(branches)

    def get_active_branches(self):
        return list(self._branches)


class FakeHypothesisStore:
    def __init__(self, records: list[HypothesisRecord] | None = None) -> None:
        self.records = list(records or [])

    def get_by_status(self, status):
        return [record for record in self.records if record.status == status]

    def get_by_branch(self, branch_id):
        return [record for record in self.records if record.branch_id == branch_id]

    def save(self, record: HypothesisRecord) -> None:
        self.records = [
            existing
            for existing in self.records
            if existing.hypothesis_id != record.hypothesis_id
        ]
        self.records.append(record)

    def mark_status(self, hypothesis_id: str, status: str) -> None:
        for record in self.records:
            if record.hypothesis_id == hypothesis_id:
                record.status = status

    def get_one(self, hypothesis_id: str) -> HypothesisRecord | None:
        return next(
            (
                record
                for record in self.records
                if record.hypothesis_id == hypothesis_id
            ),
            None,
        )


class MemoryLineageRegistry:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def record_event(self, event: dict):
        self.events.append(dict(event))
        return event.get("event_id", "event-1")


def _branch(branch_id: str = "branch-1") -> Branch:
    return Branch(
        branch_id=branch_id,
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="hash-1",
    )


def _champion() -> ChampionState:
    return ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="solver",
        code_snapshot_path="/tmp/champion",
        code_snapshot_hash="hash",
    )


def _pipeline(
    *,
    creative: FakeCreative | None = None,
    lineage_registry=None,
    branch_workspace: str = "/tmp/branch",
    forced_locus: str | None = "local_search",
    persistent_forced_locus: str | None = None,
    forced_surface_action: str | None = None,
    forced_surface_target_file: str | None = None,
    forced_surface_diagnostic: bool = False,
    problem_spec=None,
    split_manifest_hash: str | None = None,
    seed_ledger_hash: str | None = None,
):
    if lineage_registry is None:
        lineage_registry = MemoryLineageRegistry()
    branch = _branch()
    sibling = _branch("sibling")
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
            ]
        )
    runtime = FakeProblemRuntime(spec=problem_spec)
    failures: list[tuple[Branch, FailureEvent]] = []
    balance_exhausted = {"value": False}
    pipeline = ProposalPipeline(
        creative=creative or FakeCreative(),
        problem_runtime=runtime,
        classifier=SimpleNamespace(
            classify=lambda text: SimpleNamespace(
                family_id="bounded-local",
                source="test",
                taxonomy_version="v1",
            )
        ),
        branch_controller=FakeBranchController([branch, sibling]),
        hypothesis_store=FakeHypothesisStore(),
        branch_workspaces={branch.branch_id: branch_workspace},
        champion_lock=threading.Lock(),
        get_champion=_champion,
        step_history=[],
        handle_failure=lambda b, f: failures.append((b, f)),
        mark_balance_exhausted=lambda: balance_exhausted.__setitem__("value", True),
        lineage_registry=lineage_registry,
        campaign_id="camp-1",
        problem_id="toy",
        problem_spec_hash="spec-hash",
        split_manifest_hash=split_manifest_hash,
        seed_ledger_hash=seed_ledger_hash,
        persistent_forced_locus=(
            persistent_forced_locus
            if persistent_forced_locus is not None
            else forced_locus
        ),
        forced_surface_action=forced_surface_action,
        forced_surface_target_file=forced_surface_target_file,
        forced_surface_diagnostic=forced_surface_diagnostic,
    )
    return pipeline, branch, runtime, failures, balance_exhausted


__all__ = [
    name
    for name in globals()
    if not (name.startswith("__") and name.endswith("__"))
]
