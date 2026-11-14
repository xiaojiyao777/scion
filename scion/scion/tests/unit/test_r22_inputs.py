"""R22 studies final retention without prescribing an algorithm or new gate."""

import json
from pathlib import Path

from scion.cli.commands.init_run import _load_cli_problem_adapter
from scion.core.models import Branch, BranchState, ChampionState
from scion.core.problem_runtime import ProblemRuntime
from scion.problem.bridge import legacy_problem_spec_from_v1
from scion.proposal.context_snapshot import freeze_proposal_context
from scion.tests.unit import test_r16_inputs as helpers
from scion.tests.unit import test_r21_inputs as previous

PREFIX = "v04-cvrp-r22-retained-path-autonomous"
BEGIN = "BEGIN COMPLETE HISTORICAL R21 QUESTION\n"
END = "\nEND COMPLETE HISTORICAL R21 QUESTION"


def test_protocol_unchanged_and_seeds_prospectively_fresh():
    helpers.test_fresh_seeds_and_unchanged_protocol(PREFIX, previous.PREFIX, 280000, 17)


def test_public_formal_closure():
    helpers.test_full_public_formal_closure(
        PREFIX, "scion/scion/problems/cvrp/problem-v1.yaml",
        "v04-cvrp-r7-autonomous-source-continuation", 12, "scion/scion/problems/cvrp",
    )


def test_whole_question_observations_and_unforced_retention_emphasis():
    old = previous.research_input()
    new = previous.research_input(PREFIX)
    assert new["observations"] == old["observations"]
    frame, rest = new["current_question"].split(BEGIN, 1)
    historical, addition = rest.split(END, 1)
    assert historical == old["current_question"]
    for phrase in (
        "unchanged complete R21 starting champion", "H/C retain algorithm and test choice",
        "no target file", "no R21", "All twenty supplied history files",
        "real entry, completed computation", "final returned solution",
        "objective retention does not require identical route structure",
        "its rejection does not prove a retention bug",
        "Instrumentation perturbs timing", "not an algorithm prescription",
    ):
        assert phrase.casefold() in frame.casefold()
    for phrase in (
        "352 valid pairs", "Every cross-case distance median is zero",
        "+25,+43,-76,-80", "all eight final distance deltas are zero",
        "including losses and uncertain results", "not a prescribed repair",
    ):
        assert phrase in addition


def test_no_new_private_or_operational_input():
    value = previous.research_input(PREFIX)
    rendered = json.dumps(value)
    for private in (
        "B-n39-k5", "X-n106-k14", "tai385", "A-n62-k8", "X-n228-k23",
        "X-n627-k43", "1389.75", "-20.5", "6526", "260111", "260137",
        "260171", "260179", "VALIDATION_EXPAND", "/metrics/", "52b49618",
        "Not authenticated", "PROVIDER_TRANSIENT", ".py",
    ):
        assert private not in rendered


def test_twenty_whole_histories_same_baseline_and_frozen_resources():
    _, old = previous.invocation(previous.PREFIX, "20261009")
    command, new = previous.invocation(PREFIX, "20261011")
    values = previous.option_values
    history = values(new, "--research-history")
    assert len(history) == len(set(history)) == 20
    assert history[:-1] == values(old, "--research-history")
    root = "/home/clawd/research/scion-experiments/"
    assert history[-1] == root + previous.PREFIX + "-20261009/research_history.jsonl"
    assert values(new, "--source-tree") == [
        root + previous.PREFIX + "-20261009/champions/champion_v1"
    ]
    for option in (
        "--problem", "--code-research-limits", "--split", "--time-limit-sec",
        "--rounds", "--provider-call-cap", "--provider-transient-retries",
        "--outer-hardwall-sec",
    ):
        assert values(new, option) == values(old, option)
    for setting in (
        "SCION_MODEL=gpt-6.1-sol", "SCION_REASONING_EFFORT=high",
        "SCION_LLM_TIMEOUT_SEC=180", "SCION_LLM_CODE_RESEARCH_TURN_TIMEOUT_SEC=300",
    ):
        assert setting in command
    assert values(new, "--campaign-dir") == [root + PREFIX + "-20261011"]


def test_actual_provider_projection_keeps_exact_question_and_retention_example():
    adapter = _load_cli_problem_adapter(
        helpers.ROOT / "scion/scion/problems/cvrp/problem-v1.yaml"
    )
    value = previous.research_input(PREFIX)
    runtime = ProblemRuntime(adapter=adapter, research_input=value)
    context = runtime.ctx_manager.build_hypothesis_context(
        branch=Branch(branch_id="r22-preflight", state=BranchState.EXPLORE,
                      base_champion_id=1),
        champion=ChampionState(version=1, operator_pool={},
                               code_snapshot_path=str(adapter.spec.root_dir)),
        problem_spec=legacy_problem_spec_from_v1(adapter.spec),
    )
    projected = freeze_proposal_context("hypothesis", context).provider_context()
    assert projected["research_question"]["current_question"] == value["current_question"]
    assert len(projected["prior_research_observations"]) == 5
    # The public example is available as source, not collected as a formal gate.
    source = (Path(adapter.spec.root_dir) / "tests/test_solver.py").read_text()
    assert "def test_completed_improvement_survives_real_return" in source
