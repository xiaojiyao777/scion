from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from scion.core.models import Branch, BranchState, ChampionState
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

_SCION_ROOT = Path(__file__).resolve().parents[3]
_CVRP_ROOT = _SCION_ROOT / "scion" / "problems" / "cvrp"
_INPUT_PATH = (
    _SCION_ROOT
    / "docs"
    / "experiments"
    / "v0.4"
    / "inputs"
    / "v04-cvrp-m9-m7-fc1-research-input.json"
)


def _research_input() -> dict[str, Any]:
    with _INPUT_PATH.open(encoding="utf-8") as handle:
        value = json.load(handle)
    assert isinstance(value, dict)
    return value


def _observation() -> dict[str, Any]:
    value = _research_input()["observations"][0]
    assert isinstance(value, dict)
    return value


def _all_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(*(_all_keys(child) for child in value.values()), set())
    if isinstance(value, list):
        return set().union(*(_all_keys(child) for child in value), set())
    return set()


def _all_strings(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, dict):
        return tuple(text for child in value.values() for text in _all_strings(child))
    if isinstance(value, list):
        return tuple(text for child in value for text in _all_strings(child))
    return ()


def test_cvrp_adapter_exposes_prior_observation_provider() -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")

    provider = CvrpAdapter(spec).prior_research_observation_provider()

    assert isinstance(provider, CvrpPriorResearchObservationProvider)


def test_external_m7_observation_projects_without_loss_or_added_diagnosis() -> None:
    observation = _observation()

    provider = CvrpPriorResearchObservationProvider()

    projected = provider.project_prior_research_observation(observation=observation)

    assert projected is not None
    expected = deepcopy(observation)
    expected["schema_version"] = "scion.cvrp.prior_research_observation.v1"
    expected["observed_outputs"] = {
        "terminal_stage_metrics": False,
        "terminal_safe_features": False,
        "terminal_decision": False,
        "later_stage_metrics": False,
        "promotion": False,
        "retained_baseline_comparison": False,
    }
    assert projected == expected
    assert projected is not observation
    assert projected["completed_stages"] is not observation["completed_stages"]


def test_external_input_contains_question_and_only_observational_m7_fields() -> None:
    research_input = _research_input()
    observation = research_input["observations"][0]
    forbidden_fields = {
        "action",
        "change_locus",
        "mechanism",
        "patch",
        "repair",
        "surface",
        "target_file",
    }

    assert research_input["current_question"].startswith("Scion 能否")
    assert set(research_input) == {"current_question", "observations"}
    assert _all_keys(observation).isdisjoint(forbidden_fields)
    assert all(".py" not in text for text in _all_strings(observation))
    assert all("recommend" not in text.casefold() for text in _all_strings(observation))
    assert all(
        "should_edit" not in text.casefold() for text in _all_strings(observation)
    )


def test_projection_copies_changed_valid_values_from_external_observation() -> None:
    observation = _observation()
    observation["completed_stages"][0]["valid_pairs"] = 31
    observation["completed_stages"][0]["case_outcomes"]["wins"] = 5
    observation["terminal"]["case_id"] = "A-n32-k5"
    observation["terminal"]["seed"] = 5
    observation["terminal"]["failure"]["diagnostics"][1]["value"] = 17

    provider = CvrpPriorResearchObservationProvider()

    projected = provider.project_prior_research_observation(observation=observation)

    assert projected is not None
    assert projected["completed_stages"][0]["valid_pairs"] == 31
    assert projected["completed_stages"][0]["case_outcomes"]["wins"] == 5
    assert projected["terminal"]["case_id"] == "A-n32-k5"
    assert projected["terminal"]["seed"] == 5
    assert projected["terminal"]["failure"]["diagnostics"][1]["value"] == 17


def test_external_input_reaches_frozen_hypothesis_context() -> None:
    research_input = _research_input()
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    adapter = CvrpAdapter(spec)
    branch = Branch(
        branch_id="prior-observation-context",
        state=BranchState.EXPLORE,
        base_champion_id=1,
    )
    champion = ChampionState(
        version=1,
        operator_pool={},
        code_snapshot_path=str(_CVRP_ROOT),
    )
    context = ContextManager(
        adapter=adapter,
        research_input=research_input,
    ).build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy_problem_spec_from_v1(spec),
    )

    provider_context = freeze_proposal_context("hypothesis", context).provider_context()

    assert provider_context["research_question"] == {
        "current_question": research_input["current_question"]
    }
    assert provider_context["prior_research_observations"] == [
        CvrpPriorResearchObservationProvider().project_prior_research_observation(
            observation=research_input["observations"][0]
        )
    ]
    projected_outputs = provider_context["prior_research_observations"][0][
        "observed_outputs"
    ]
    assert "validation_stage_metrics" not in projected_outputs
    assert "frozen_stage_metrics" not in projected_outputs


def _missing_schema(observation: dict[str, Any]) -> None:
    del observation["schema_version"]


def _unknown_instruction_field(observation: dict[str, Any]) -> None:
    observation["patch"] = "change solver.py"


def _unknown_nested_repair_field(observation: dict[str, Any]) -> None:
    observation["terminal"]["failure"]["repair"] = "increase routes"


def _wrong_counter_type(observation: dict[str, Any]) -> None:
    observation["completed_stages"][0]["valid_pairs"] = True


def _inconsistent_pair_counts(observation: dict[str, Any]) -> None:
    observation["completed_stages"][0]["valid_pairs"] = 33


def _reversed_interval(observation: dict[str, Any]) -> None:
    observation["completed_stages"][0]["case_outcomes"]["ci_low"] = 75.0


def _duplicate_diagnostic(observation: dict[str, Any]) -> None:
    observation["terminal"]["failure"]["diagnostics"].append(
        {"name": "route_limit", "value": 37}
    )


@pytest.mark.parametrize(
    "mutate",
    [
        _missing_schema,
        _unknown_instruction_field,
        _unknown_nested_repair_field,
        _wrong_counter_type,
        _inconsistent_pair_counts,
        _reversed_interval,
        _duplicate_diagnostic,
    ],
)
def test_malformed_or_extended_observation_fails_closed(mutate) -> None:
    observation = _observation()
    mutate(observation)

    with pytest.raises(ValueError, match="invalid CVRP prior research observation"):
        CvrpPriorResearchObservationProvider().project_prior_research_observation(
            observation=observation
        )
