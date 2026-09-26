"""Wide-budget development preserves gates and excludes private R10 outcomes."""

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
_PREVIOUS = "v04-cvrp-r11-wide-budget-autonomous"
_PRIOR_PROTOCOL = "v04-cvrp-r11-wide-budget-autonomous"
_NEW = "v04-cvrp-r12-post-r11-autonomous"


def _path(prefix, kind):
    return _INPUTS / f"{prefix}-{kind}"


def test_r12_preserves_all_wide_budget_rules_and_scientific_gates():
    old = yaml.safe_load(_path(_PRIOR_PROTOCOL, "protocol.yaml").read_text())
    new = yaml.safe_load(_path(_NEW, "protocol.yaml").read_text())
    assert old.keys() == new.keys()
    for key in old.keys() - {"version", "canary"}:
        assert new[key] == old[key]
    assert new["canary"]["cases"] == old["canary"]["cases"]
    assert new["screening"]["require_expanded_for_pass"] is True
    assert new["runtime"]["time_limits"]["stage_defaults"]["screening"] == 60


def test_r12_seed_selection_is_prospective_and_disjoint():
    ledger = SeedLedgerConfig.from_yaml(_path(_NEW, "seeds.yaml"))
    seeds = [*ledger.screening, *ledger.validation, *ledger.frozen, *ledger.canary]
    primes = [
        n
        for n in range(110001, 110500)
        if all(n % divisor for divisor in range(2, isqrt(n) + 1))
    ][:9]
    assert seeds == primes
    assert len(seeds) == len(set(seeds)) == 9
    for prefix, kind in (
        ("v04-cvrp-r6-minus-2for1-b0", "seeds.yaml"),
        ("v04-cvrp-r6-minus-2for1-b0", "retained-seeds.yaml"),
        ("v04-cvrp-r7-autonomous-source-continuation", "seeds.yaml"),
        ("v04-cvrp-r8-r7-final-b0", "seeds.yaml"),
        ("v04-cvrp-r8-r7-final-b0", "retained-seeds.yaml"),
        (_PREVIOUS, "seeds.yaml"),
        (_PRIOR_PROTOCOL, "seeds.yaml"),
        ("v04-cvrp-r10-wide-budget-b0", "retained-seeds.yaml"),
        ("v04-cvrp-r10-wide-budget-b0", "seeds.yaml"),
        ("v04-cvrp-r9-post-b0-autonomous", "seeds.yaml"),
    ):
        old = SeedLedgerConfig.from_yaml(_path(prefix, kind))
        assert set(seeds).isdisjoint(
            [*old.screening, *old.validation, *old.frozen, *old.canary]
        )
    protocol = yaml.safe_load(_path(_NEW, "protocol.yaml").read_text())
    assert protocol["canary"]["seeds"] == ledger.canary


def test_r12_h_receives_screening_facts_without_private_validation_details():
    old = json.loads(_path(_PREVIOUS, "research-input.json").read_text())
    value = normalize_research_input(
        json.loads(_path(_NEW, "research-input.json").read_text())
    )
    assert value["observations"] == old["observations"]
    assert len(value["observations"]) == 4
    spec = load_problem_spec_v1_from_yaml(_ROOT / "scion/problems/cvrp/problem-v1.yaml")
    context = ContextManager(adapter=CvrpAdapter(spec), research_input=value)
    h = context.build_hypothesis_context(
        branch=Branch(
            branch_id="r12-input-check", state=BranchState.EXPLORE, base_champion_id=1
        ),
        champion=ChampionState(
            version=1, operator_pool={}, code_snapshot_path=str(spec.root_dir)
        ),
        problem_spec=legacy_problem_spec_from_v1(spec),
    )
    projected = freeze_proposal_context("hypothesis", h).provider_context()
    provider = CvrpPriorResearchObservationProvider()
    assert projected["prior_research_observations"] == [
        provider.project_prior_research_observation(observation=x)
        for x in value["observations"]
    ]
    question = projected["research_question"]["current_question"]
    assert question == value["current_question"]
    for fact in (
        "R11",
        "[-1,216.75]",
        "alns_threshold=2000",
        "at most 512 customers",
        "all 108 pairs valid",
        "R10",
        "SCREENING ONLY",
        "19.75",
        "[0,179]",
        "SCREENING_PASS",
        "zero ALNS iterations",
        "60/90/120/180/240",
        "no target file",
        "not promotion",
        "not original B0",
    ):
        assert fact in question
    serialized = json.dumps(value)
    for private in (
        "B-n39-k5",
        "X-n106-k14",
        "tai385",
        "A-n62-k8",
        "X-n228-k23",
        "X-n627-k43",
        "unable to pack",
        "customer 624",
        "construction.py",
        "INCOMPLETE_COMPARATOR_EVIDENCE",
        "CHAMPION_RUNTIME_FAILURE",
        "shared_runtime_audit_failure",
        "/metrics/",
        "edac77fa",
    ):
        assert private not in serialized
    assert ".py" not in serialized
    assert not any(
        x["observed_outputs"]["promotion"]
        for x in projected["prior_research_observations"]
    )
