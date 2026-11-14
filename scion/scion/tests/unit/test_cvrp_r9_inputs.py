"""Post-B0 research keeps ordinary facts available without selecting a mechanism."""

import json
from math import isqrt
from pathlib import Path

import yaml

from scion.config.problem import SeedLedgerConfig
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
_R7 = "v04-cvrp-r7-autonomous-source-continuation"
_R8 = "v04-cvrp-r8-r7-final-b0"
_R9 = "v04-cvrp-r9-post-b0-autonomous"


def _path(prefix, kind):
    return _INPUTS / f"{prefix}-{kind}"


def test_r9_preserves_existing_scientific_gates():
    old = yaml.safe_load(_path(_R7, "protocol.yaml").read_text())
    new = yaml.safe_load(_path(_R9, "protocol.yaml").read_text())
    assert old.keys() == new.keys()
    for key in old.keys() - {"version", "canary"}:
        assert new[key] == old[key]
    assert new["canary"]["cases"] == old["canary"]["cases"]
    assert new["screening"]["require_expanded_for_pass"] is True


def test_r9_seed_selection_is_prospective_and_disjoint():
    new = SeedLedgerConfig.from_yaml(_path(_R9, "seeds.yaml"))
    ordered = [*new.screening, *new.validation, *new.frozen, *new.canary]
    first_primes = [
        n
        for n in range(80001, 80300)
        if all(n % divisor for divisor in range(2, isqrt(n) + 1))
    ][:9]
    assert ordered == first_primes
    assert len(ordered) == len(set(ordered)) == 9
    for prefix, kind in (
        (_R7, "seeds.yaml"),
        (_R8, "seeds.yaml"),
        (_R8, "retained-seeds.yaml"),
    ):
        old = SeedLedgerConfig.from_yaml(_path(prefix, kind))
        assert set(ordered).isdisjoint(
            [*old.screening, *old.validation, *old.frozen, *old.canary]
        )
    protocol = yaml.safe_load(_path(_R9, "protocol.yaml").read_text())
    assert protocol["canary"]["seeds"] == new.canary


def test_r9_preserves_prior_observations_and_exposes_r8_question_to_h():
    old = json.loads(_path(_R7, "research-input.json").read_text())
    value = normalize_research_input(
        json.loads(_path(_R9, "research-input.json").read_text())
    )
    assert value["observations"][:3] == old["observations"]
    assert len(value["observations"]) == 4
    spec = load_problem_spec_v1_from_yaml(_ROOT / "scion/problems/cvrp/problem-v1.yaml")
    context = ContextManager(adapter=CvrpAdapter(spec), research_input=value)
    h = context.build_hypothesis_context(
        branch=Branch(
            branch_id="r9-input-check", state=BranchState.EXPLORE, base_champion_id=1
        ),
        champion=ChampionState(
            version=1, operator_pool={}, code_snapshot_path=str(spec.root_dir)
        ),
        problem_spec=legacy_problem_spec_from_v1(spec),
    )
    projected = freeze_proposal_context("hypothesis", h).provider_context()
    provider = CvrpPriorResearchObservationProvider()
    expected = [
        provider.project_prior_research_observation(observation=x)
        for x in value["observations"]
    ]
    assert projected["prior_research_observations"] == expected
    assert (
        projected["research_question"]["current_question"] == value["current_question"]
    )
    assert "R8" in value["current_question"]
    assert "NOT_CONFIRMED" in value["current_question"]
    assert "no target file" in value["current_question"]
    diagnostics = [x["terminal"]["failure"]["diagnostics"] for x in expected]
    assert [items[0]["value"] for items in diagnostics] == ["R4", "R5", "R6", "R8"]
    r8 = {x["name"]: x["value"] for x in diagnostics[-1]}
    assert len(r8) == 32
    assert r8["execution_order_counterbalanced"] is True
    assert r8["tai100a_seed_pattern"] == "win_win_win_win"
    assert r8["X-n351-k40_median_delta"] == -319
    assert r8["X-n190-k8_candidate_alns_iterations_min"] == 1
    assert r8["large_cases_post_initial_objective_equals_final"] is True
    assert expected[-1]["claim_context"]["incremental_effect_isolated"] is False
    assert all(x["completed_stages"][0]["stage"] == "screening" for x in expected)
    assert not any(x["observed_outputs"]["promotion"] for x in expected)
    assert ".py" not in json.dumps(value)
