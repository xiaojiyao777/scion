"""Prospective R7 inputs use existing boundaries without prescribing a patch."""

import json
from pathlib import Path

import yaml

from scion.core.models import Branch, BranchState, ChampionState
from scion.core.research_input import normalize_research_input
from scion.problem.bridge import (
    legacy_problem_spec_from_v1,
    load_problem_spec_v1_from_yaml,
)
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.problems.cvrp.prior_research_observation import (
    CvrpPriorResearchObservationProvider,
)
from scion.proposal.context_manager import ContextManager
from scion.proposal.context_snapshot import freeze_proposal_context

_ROOT = Path(__file__).resolve().parents[3]
_INPUTS = _ROOT / "docs/experiments/v0.4/inputs"
_R6 = "v04-cvrp-r6-minus-2for1-b0"
_R7 = "v04-cvrp-r7-autonomous-source-continuation"


def _yaml(prefix, kind):
    return yaml.safe_load((_INPUTS / f"{prefix}-{kind}.yaml").read_text())


def test_r7_preserves_r6_scientific_gates_and_case_partitions():
    old, new = _yaml(_R6, "protocol"), _yaml(_R7, "protocol")
    for key in old.keys() - {"version", "canary"}:
        assert new[key] == old[key]
    assert _yaml(_R6, "split") | {"version": "ignored"} == (
        _yaml(_R7, "split") | {"version": "ignored"}
    )
    old_seeds, new_seeds = _yaml(_R6, "seeds"), _yaml(_R7, "seeds")
    all_new = [
        seed
        for stage in ("screening", "validation", "frozen", "canary")
        for seed in new_seeds[stage]
    ]
    assert len(all_new) == len(set(all_new)) == 9
    assert all_new == [40009, 40013, 40031, 40037, 40039, 40063, 40087, 40093, 40099]
    for stage in ("screening", "validation", "frozen", "canary"):
        assert not set(new_seeds[stage]) & set(old_seeds[stage])
    assert new["canary"]["seeds"] == new_seeds["canary"]


def test_r7_all_observations_reach_h_in_order_without_added_direction():
    value = normalize_research_input(
        json.loads((_INPUTS / f"{_R7}-research-input.json").read_text())
    )
    problem_root = _ROOT / "scion/problems/cvrp"
    spec = load_problem_spec_v1_from_yaml(problem_root / "problem-v1.yaml")
    context = ContextManager(adapter=CvrpAdapter(spec), research_input=value)
    branch = Branch(
        branch_id="r7-input-check", state=BranchState.EXPLORE, base_champion_id=1
    )
    champion = ChampionState(
        version=1, operator_pool={}, code_snapshot_path=str(problem_root)
    )
    h = context.build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy_problem_spec_from_v1(spec),
    )
    projected = freeze_proposal_context("hypothesis", h).provider_context()
    provider = CvrpPriorResearchObservationProvider()
    expected = [
        provider.project_prior_research_observation(observation=x)
        for x in value["observations"]
    ]
    assert projected["prior_research_observations"] == expected
    diagnostics = [x["terminal"]["failure"]["diagnostics"] for x in expected]
    assert [items[0]["value"] for items in diagnostics] == ["R4", "R5", "R6"]
    assert expected[1]["completed_stages"][0]["decision"] == "not_applicable"
    r6 = {x["name"]: x["value"] for x in diagnostics[2]}
    assert r6["operator_cleanup_overlapped"] is True
    assert r6["X-n351-k40_seed_pattern"] == "loss_loss_loss_loss"
    assert r6["X-n351-k40_both_arms_zero_alns_iterations_pairs"] == 4
    assert all(x["completed_stages"][0]["stage"] == "screening" for x in expected)
    assert not any(x["observed_outputs"]["promotion"] for x in expected)
    assert ".py" not in json.dumps(value["observations"])
