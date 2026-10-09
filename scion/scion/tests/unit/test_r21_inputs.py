"""Fresh whole-source continuation keeps complete public evidence and old gates."""

import json
import re
import shlex

import yaml

from scion.cli.commands.init_run import _load_cli_problem_adapter
from scion.core.models import Branch, BranchState, ChampionState
from scion.core.problem_runtime import ProblemRuntime
from scion.core.research_input import normalize_research_input
from scion.problem.bridge import legacy_problem_spec_from_v1
from scion.problems.cvrp.prior_research_observation import (
    CvrpPriorResearchObservationProvider,
)
from scion.proposal.context_snapshot import freeze_proposal_context
from scion.tests.unit import test_r16_inputs as helpers

PREFIX = "v04-cvrp-r21-source-grounded-autonomous"
R19 = "v04-cvrp-r19-reliable-probes-autonomous"
R20 = "v04-cvrp-r20-r19-final-b0-fixed"
DOCS = helpers.INPUTS.parent
BEGIN_HISTORY = "BEGIN COMPLETE HISTORICAL R19 QUESTION\n"
END_HISTORY = "\nEND COMPLETE HISTORICAL R19 QUESTION"


def research_input(prefix=PREFIX):
    return normalize_research_input(
        json.loads((helpers.INPUTS / f"{prefix}-research-input.json").read_text())
    )


def invocation(prefix, date):
    document = (DOCS / f"{prefix}-preregistration-{date}.md").read_text()
    command = document.split("```bash\n", 1)[1].split("```", 1)[0]
    return command, shlex.split(command.replace("\\\n", " "))


def option_values(tokens, option):
    return [tokens[i + 1] for i, value in enumerate(tokens) if value == option]


def test_unchanged_r20_protocol_and_fresh_seeds():
    helpers.test_fresh_seeds_and_unchanged_protocol(PREFIX, R20, 270000, 17)
    for suffix in ("protocol", "seeds"):
        value = yaml.safe_load((helpers.INPUTS / f"{PREFIX}-{suffix}.yaml").read_text())
        assert value["version"] == "0.4-cvrp-r21-source-grounded-autonomous"


def test_public_formal_closure():
    helpers.test_full_public_formal_closure(
        PREFIX,
        "scion/scion/problems/cvrp/problem-v1.yaml",
        "v04-cvrp-r7-autonomous-source-continuation",
        12,
        "scion/scion/problems/cvrp",
    )


def test_current_frame_separates_whole_history_from_actual_inheritance():
    old, new = research_input(R19), research_input()
    assert new["observations"] == old["observations"]
    assert len(new["observations"]) == 5
    question = new["current_question"]
    current, rest = question.split(BEGIN_HISTORY, 1)
    historical, addition = rest.split(END_HISTORY, 1)
    assert historical == old["current_question"]
    assert question.count(BEGIN_HISTORY) == question.count(END_HISTORY) == 1
    for fact in (
        "R21 CURRENT SOURCE AND QUESTION",
        "supersedes historical present-tense descriptions",
        "exact complete final R19 A3 source",
        "not a promotion claim, state restore or sibling merge",
        "does not include the B-branch",
        "eight seeds each",
        "All nineteen supplied history files are loaded whole",
        "H/C retain algorithm and test choice",
        "no target file",
    ):
        assert fact in current
    for fact in (
        "320 valid pairs",
        "five pair losses elsewhere",
        "acceptance or retention in the returned best",
        "0.2-second probe establishes feasibility/deadline behavior only",
        "not large-instance solve-to-operator coverage",
        "not a measured wall-clock speedup",
        "different comparator from R19 and from the new R21 local baseline",
    ):
        assert fact in addition


def test_complete_public_screening_matrix_and_no_private_r20_update():
    new = research_input()
    addition = new["current_question"].split(END_HISTORY, 1)[1]
    matrix = {
        case: json.loads(vector)
        for case, vector in re.findall(
            r"^([^:\n]+): (\[[^\n]+\]), median", addition, flags=re.MULTILINE
        )
    }
    assert matrix == {
        "B-n34-k5": [0, 0, 0, 0, 0, 0, 0, 0],
        "tai100a": [97, 216, 280, 325, 50, 137, 228, 173],
        "X-n351-k40": [12618, 11977, 12031, 12243, 11977, 11923, 11979, 12357],
        "A-n54-k7": [4, 2, 3, 0, 5, 0, 0, -2],
        "X-n190-k8": [3, 124, 76, 76, 76, 129, 76, 76],
        "X-n513-k21": [226, 226, 226, 226, 198, 226, 226, 226],
    }
    assert "260003,260009,260011,260017,260023,260047,260081,260089" in addition
    for private in (
        "B-n39-k5", "X-n106-k14", "tai385", "A-n62-k8", "X-n228-k23",
        "X-n627-k43", "1389.75", "-20.5", "6526", "260111", "260137",
        "260171", "260179", "VALIDATION_EXPAND", "/metrics/", "52b49618",
    ):
        assert private not in json.dumps(new)
    assert "NOT_CONFIRMED" not in addition  # Old public terminals remain intact.
    assert ".py" not in json.dumps(new)  # No prescribed algorithm target.


def test_actual_h_projection_preserves_exact_question_and_observations():
    adapter = _load_cli_problem_adapter(
        helpers.ROOT / "scion/scion/problems/cvrp/problem-v1.yaml"
    )
    value = research_input()
    runtime = ProblemRuntime(adapter=adapter, research_input=value)
    h = runtime.ctx_manager.build_hypothesis_context(
        branch=Branch(branch_id="r21-preflight", state=BranchState.EXPLORE,
                      base_champion_id=1),
        champion=ChampionState(version=1, operator_pool={},
                               code_snapshot_path=str(adapter.spec.root_dir)),
        problem_spec=legacy_problem_spec_from_v1(adapter.spec),
    )
    projected = freeze_proposal_context("hypothesis", h).provider_context()
    provider = CvrpPriorResearchObservationProvider()
    assert projected["research_question"]["current_question"] == value["current_question"]
    assert projected["prior_research_observations"] == [
        provider.project_prior_research_observation(observation=item)
        for item in value["observations"]
    ]


def test_invocation_preserves_whole_history_order_and_frozen_resources():
    old_command, old = invocation(R19, "20261005")
    command, new = invocation(PREFIX, "20261009")
    history = option_values(new, "--research-history")
    assert len(history) == len(set(history)) == 19
    assert history[:-1] == option_values(old, "--research-history")
    assert history[-1] == (
        "/home/clawd/research/scion-experiments/"
        f"{R19}-20261005/research_history.jsonl"
    )
    assert option_values(new, "--source-tree") == [
        "/home/clawd/research/scion-experiments/"
        f"{R20}-20261008/input_snapshots/candidate"
    ]
    for option in (
        "--problem", "--code-research-limits", "--split", "--time-limit-sec",
        "--rounds", "--provider-call-cap", "--provider-transient-retries",
        "--outer-hardwall-sec",
    ):
        assert option_values(new, option) == option_values(old, option)
    for value in (
        "SCION_MODEL=gpt-6.1-sol", "SCION_REASONING_EFFORT=high",
        "SCION_LLM_TIMEOUT_SEC=180", "SCION_LLM_HYPOTHESIS_RESEARCH_TURN_TIMEOUT_SEC=180",
        "SCION_LLM_CODE_RESEARCH_TURN_TIMEOUT_SEC=300",
        "SCION_LLM_CODE_RESEARCH_FINALIZE_TIMEOUT_SEC=300",
    ):
        assert value in command and value in old_command
