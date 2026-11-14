"""Common-repair development keeps scientific gates and private facts isolated."""

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
_PREVIOUS = "v04-cvrp-r12-post-r11-autonomous"
_NEW = "v04-cvrp-r14-post-r13-autonomous"


def _path(prefix, kind):
    return _INPUTS / f"{prefix}-{kind}"


def test_r14_preserves_all_wide_budget_rules_and_scientific_gates():
    new = yaml.safe_load(_path(_NEW, "protocol.yaml").read_text())
    for prefix in (_PREVIOUS, "v04-cvrp-r13-constructor-fixed-b0"):
        old = yaml.safe_load(_path(prefix, "protocol.yaml").read_text())
        assert old.keys() == new.keys()
        for key in old.keys() - {"version", "canary"}:
            assert new[key] == old[key]
        assert new["canary"]["cases"] == old["canary"]["cases"]
    assert new["screening"]["require_expanded_for_pass"] is True
    assert new["runtime"]["time_limits"]["stage_defaults"]["screening"] == 60


def test_r14_seed_selection_is_prospective_and_disjoint():
    ledger = SeedLedgerConfig.from_yaml(_path(_NEW, "seeds.yaml"))
    seeds = [*ledger.screening, *ledger.validation, *ledger.frozen, *ledger.canary]
    primes = [
        n
        for n in range(130001, 130500)
        if all(n % divisor for divisor in range(2, isqrt(n) + 1))
    ][:9]
    assert seeds == primes
    assert len(seeds) == len(set(seeds)) == 9
    for path in _INPUTS.glob("v04-cvrp-*-seeds.yaml"):
        if path == _path(_NEW, "seeds.yaml"):
            continue
        old = SeedLedgerConfig.from_yaml(path)
        assert set(seeds).isdisjoint(
            [*old.screening, *old.validation, *old.frozen, *old.canary]
        ), path.name
    protocol = yaml.safe_load(_path(_NEW, "protocol.yaml").read_text())
    assert protocol["canary"]["seeds"] == ledger.canary


def test_r14_h_receives_all_observations_without_private_regression_details():
    old = json.loads(_path(_PREVIOUS, "research-input.json").read_text())
    value = normalize_research_input(
        json.loads(_path(_NEW, "research-input.json").read_text())
    )
    assert value["observations"][:4] == old["observations"]
    assert len(value["observations"]) == 5
    spec = load_problem_spec_v1_from_yaml(_ROOT / "scion/problems/cvrp/problem-v1.yaml")
    context = ContextManager(adapter=CvrpAdapter(spec), research_input=value)
    h = context.build_hypothesis_context(
        branch=Branch(
            branch_id="r14-input-check", state=BranchState.EXPLORE, base_champion_id=1
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
        "R12-A-fixed",
        "B0-fixed",
        "operator-assisted",
        "R13 SCREENING ONLY",
        "[-36,296.75]",
        "[0,-274,-144,134]",
        "[648,368,367,328]",
        "[226,226,226,226]",
        "57.786-64.337",
        "15 destroy-repair pairs",
        "segment_length=100",
        "alns_threshold=2000",
        "at most 512 customers",
        "R12",
        "[0,11.25]",
        "[-3.25,50.5]",
        "[-45.5,10.5]",
        "zero ALNS",
        "60/90/120/180/240",
        "no target file",
        "not promotion",
        "not original B0",
        "not proof",
    ):
        assert fact in question
    last = projected["prior_research_observations"][-1]
    stage = last["completed_stages"][0]
    assert stage["valid_pairs"] == stage["planned_pairs"] == 24
    assert stage["subject_failures"] == stage["fleet_regressions"] == 0
    assert stage["gate_outcome"] == "unclear"
    assert stage["case_outcomes"] == dict(
        wins=4, losses=1, ties=1, median_delta=91.5, ci_low=-36, ci_high=296.75
    )
    assert not any(last["observed_outputs"].values())
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
        "engineering-diagnostics",
        "110059",
        "110063",
        "capacity110",
        "sparse subset",
    ):
        assert private not in serialized
    assert ".py" not in serialized
    assert not any(
        x["observed_outputs"]["promotion"]
        for x in projected["prior_research_observations"]
    )
