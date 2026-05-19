"""Sprint K unit tests: hypothesis cleanup, visibility improvements."""
from __future__ import annotations

import types
from datetime import datetime
from typing import Dict, List, Optional
from unittest.mock import MagicMock, call, patch

import pytest

from scion.core.branch import BranchController, _ACTIVE_STATES
from scion.core.models import (
    Branch, BranchState, CanaryResult, ChampionState, ContractResult,
    Decision, HypothesisProposal, HypothesisRecord, PatchProposal,
)
from scion.contract.gate import ContractGate
from scion.proposal.context_manager import ContextManager, _summarise_active_hypotheses
from scion.tests.taxonomy_helpers import warehouse_family_taxonomy
from scion.proposal.search_memory import (
    CampaignSearchMemory, FamilyEntry, _make_family_key,
)

WAREHOUSE_MECHANISM_TAXONOMY = warehouse_family_taxonomy()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_branch(state: BranchState = BranchState.STALE, bid: str = "branch-1") -> Branch:
    return Branch(
        branch_id=bid,
        state=state,
        base_champion_id=1,
        base_champion_hash="abc",
    )


def _make_h_record(bid: str = "branch-1", hid: str = "hyp-1") -> HypothesisRecord:
    return HypothesisRecord(
        hypothesis_id=hid,
        branch_id=bid,
        change_locus="vehicle_level",
        action="modify",
        status="active",
        target_file="operators/foo.py",
        hypothesis_text="Improve subcategory swap operator",
    )


def _make_champion() -> ChampionState:
    return ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="x",
        code_snapshot_path="/tmp/champ",
        code_snapshot_hash="y",
    )


def _make_patch() -> PatchProposal:
    return PatchProposal(
        file_path="operators/foo.py",
        action="modify",
        code_content="class Foo:\n    def execute(self, solution, rng): pass\n",
    )


def _make_hypothesis(
    text: str = "Improve subcategory swap",
    locus: str = "vehicle_level",
    action: str = "modify",
    target_file: str = "operators/foo.py",
) -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text=text,
        change_locus=locus,
        action=action,
        target_file=target_file,
    )


# ---------------------------------------------------------------------------
# Minimal campaign harness for K1/K2
# ---------------------------------------------------------------------------

def _make_campaign_harness(
    bid: str = "branch-1",
    h_record: Optional[HypothesisRecord] = None,
    patch: Optional[PatchProposal] = None,
) -> types.SimpleNamespace:
    """Build a minimal namespace that looks like CampaignManager from K1/K2's POV."""
    from scion.core.campaign import CampaignManager
    champion = _make_champion()
    harness = types.SimpleNamespace()
    harness._branch_current_hypothesis = {bid: h_record} if h_record else {}
    harness._branch_patches = {bid: patch} if patch else {}
    harness._branch_hypotheses = {}
    harness._branch_workspaces = {}
    harness._champion = champion
    harness._campaign_id = "campaign-test"

    harness._hyp_store = MagicMock()
    harness._branch_ctrl = MagicMock()
    harness._contract_gate = MagicMock()
    harness._vgate = MagicMock()
    harness._materializer = MagicMock()
    harness._registry = MagicMock()
    harness._experiment_protocol = None
    harness._round_num = 0
    harness._rounds_since_last_promote = 0
    harness._recent_abandoned_count = 0
    harness._hard_abandon_counted_branches = set()
    harness._record_step = MagicMock()
    harness._drain_weight_opt_events = MagicMock()
    harness._record_hard_abandon = types.MethodType(CampaignManager._record_hard_abandon, harness)
    return harness


# ---------------------------------------------------------------------------
# K1: _run_reconcile_step hypothesis cleanup
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# K2: _run_eval_step abort paths
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# K2: RuntimeError abort in the run_one_step dispatcher
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# K3: mark_all_stale skips FROZEN_TESTING
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# K4: active_hyp_summary in build_round1_context
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# K5: record_contract_failure
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# K6: C10 modify key includes hypothesis_text[:50]
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# K7: search_memory family_key includes target_file
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# K8: C10 novelty check includes rejected hypotheses
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# K6-fix: modify key reverted to file-level, rejected filtered by champion_version
# ---------------------------------------------------------------------------


__all__ = [
    name
    for name in globals()
    if not (name.startswith("__") and name.endswith("__"))
]
