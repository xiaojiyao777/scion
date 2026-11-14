"""R24 keeps full adverse evidence and distinguishes its new C3 comparator."""

import ast
import json
import re

from scion.cli.commands.init_run import _load_cli_problem_adapter
from scion.core.models import Branch, BranchState, ChampionState, HypothesisProposal
from scion.core.problem_runtime import ProblemRuntime
from scion.problem.bridge import legacy_problem_spec_from_v1
from scion.proposal.context_snapshot import freeze_proposal_context
from scion.proposal.edit_protocol.source_discovery import (
    all_source_files_from_context,
    read_only_files_from_context,
)
from scion.tests.unit import test_r16_inputs as helpers
from scion.tests.unit import test_r21_inputs as previous
from scion.tests.unit import test_r22_inputs as r22
from scion.verification.development import declared_development_suites

PREFIX = "v04-cvrp-r24-stable-advantage-autonomous"
BEGIN = "BEGIN COMPLETE HISTORICAL R22 QUESTION\n"
END = "\nEND COMPLETE HISTORICAL R22 QUESTION"


def test_protocol_unchanged_and_seeds_prospectively_fresh():
    helpers.test_fresh_seeds_and_unchanged_protocol(PREFIX, r22.PREFIX, 300000, 17)


def test_public_formal_closure():
    helpers.test_full_public_formal_closure(
        PREFIX, "scion/scion/problems/cvrp/problem-v1.yaml",
        "v04-cvrp-r7-autonomous-source-continuation", 12, "scion/scion/problems/cvrp",
    )


def test_whole_question_observations_and_unforced_current_comparator():
    old, new = previous.research_input(r22.PREFIX), previous.research_input(PREFIX)
    assert new["observations"] == old["observations"]
    frame, rest = new["current_question"].split(BEGIN, 1)
    historical, _ = rest.split(END, 1)
    assert historical == old["current_question"]
    for phrase in (
        "complete final R22 C3 source", "new local champion, not R23 A",
        "not a promotion claim, state restore or sibling merge",
        "H/C retain algorithm and test choice", "no target file",
        "Do not presuppose a best-return bug", "not to separately aggregated medians",
        "after initial local search, not raw construction",
        "All twenty-one supplied history files are loaded whole",
        "retain adverse cases and seeds", "separate future experiment",
    ):
        assert phrase in frame


def test_both_complete_public_matrices_include_adverse_cells():
    addition = previous.research_input(PREFIX)["current_question"].split(END, 1)[1]
    r22_text, r23_text = addition.split("R24 PUBLIC R23 SCREENING ONLY.", 1)
    def matrix(text):
        return {
            case: json.loads(vector) for case, vector in re.findall(
                r"^([^:\n]+): (\[[^\n]+\]), median", text, re.MULTILINE
            )
        }
    assert matrix(r22_text) == {
        "B-n34-k5": [0, 0, 0, 0, 0, 0, 0, 0],
        "tai100a": [53, 7, 20, 54, -8, -26, -26, -64],
        "X-n351-k40": [180, 180, 180, 180, 180, 180, 180, 180],
        "A-n54-k7": [-5, -1, -3, -4, 0, 0, 0, 0],
        "X-n190-k8": [67, 67, -83, 67, 67, -62, 67, 67],
        "X-n513-k21": [110, 110, 110, 110, 110, 95, 110, 110],
    }
    assert matrix(r23_text) == {
        "B-n34-k5": [0, 0, 0, 0, 0, 0, 0, 0],
        "tai100a": [-51, -20, -2, -9, 19, 11, 1, -58],
        "X-n351-k40": [180, 180, 180, 180, 180, -42, -312, 180],
        "A-n54-k7": [2, 0, 1, -3, -2, 1, -2, -5],
        "X-n190-k8": [67, 88, 67, 67, 67, 67, 273, 50],
        "X-n513-k21": [110, 95, 110, 110, 110, 110, 110, 110],
    }
    assert "290011,290021,290023,290027,290033,290039,290041,290047" in r23_text
    assert "Both arms preserve their own gains" in r23_text
    # Pair arithmetic, not an identity between separately aggregated medians.
    for a0, a1, b0, b1, expected in (
        (2410, 2100, 2406, 2151, -51),
        (31776, 31467, 31596, 31509, -42),
        (31776, 31284, 31596, 31596, -312),
    ):
        assert a1 <= a0 and b1 <= b0
        assert a1 - b1 == (a0 - b0) + (b0 - b1) - (a0 - a1) == expected


def test_no_new_private_or_operational_input():
    rendered = json.dumps(previous.research_input(PREFIX))
    for private in (
        "B-n39-k5", "X-n106-k14", "tai385", "A-n62-k8", "X-n228-k23",
        "X-n627-k43", "1389.75", "-20.5", "260111", "260137", "260171",
        "260179", "VALIDATION_EXPAND", "/metrics/", "1cd0df7a", ".py",
        "Not authenticated", "PROVIDER_TRANSIENT", "300137", "300187",
    ):
        assert private not in rendered


def test_twenty_one_histories_complete_c3_source_and_frozen_resources():
    _, old = previous.invocation(r22.PREFIX, "20261011")
    command, new = previous.invocation(PREFIX, "20261024")
    values = previous.option_values
    history = values(new, "--research-history")
    assert len(history) == len(set(history)) == 21
    assert history[:-1] == values(old, "--research-history")
    root = "/home/clawd/research/scion-experiments/"
    assert history[-1] == root + r22.PREFIX + "-20261011/research_history.jsonl"
    assert values(new, "--source-tree") == [
        root + "v04-cvrp-r23-r22-final-local-fixed-20261018/input_snapshots/candidate"
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
    assert values(new, "--campaign-dir") == [root + PREFIX + "-20261024"]


def test_actual_provider_projection_and_public_explanation_are_separate():
    adapter = _load_cli_problem_adapter(
        helpers.ROOT / "scion/scion/problems/cvrp/problem-v1.yaml"
    )
    value = previous.research_input(PREFIX)
    runtime = ProblemRuntime(
        adapter=adapter, research_input=value,
        development_suites=declared_development_suites(adapter.spec),
    )
    branch = Branch(branch_id="r24-preflight", state=BranchState.EXPLORE,
                    base_champion_id=1)
    champion = ChampionState(version=1, operator_pool={},
                             code_snapshot_path=str(adapter.spec.root_dir))
    context = runtime.ctx_manager.build_hypothesis_context(
        branch=branch, champion=champion,
        problem_spec=legacy_problem_spec_from_v1(adapter.spec),
    )
    projected = freeze_proposal_context("hypothesis", context).provider_context()
    assert projected["research_question"]["current_question"] == value["current_question"]
    assert len(projected["prior_research_observations"]) == 5
    h = HypothesisProposal(
        hypothesis_text="Context-only test; never dispatched.",
        change_locus=adapter.spec.research_surfaces[0].name,
        action="modify", target_file="policies/baseline_modules/local_search.py",
    )
    c = runtime.build_code_context(branch=branch, hypothesis=h, champion=champion)
    freeze_proposal_context("code", c)
    public = read_only_files_from_context(c)
    editable = all_source_files_from_context(c)
    assert not set(public) & set(editable)
    source = public["tests/test_solver.py"]
    assert "Own-trajectory retention" in source
    assert "final(A-B)" in source
    assert "test_completed_improvement_survives_real_return" in source
    collected = [n.name for n in ast.parse(source).body
                 if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
    assert len(collected) == 2
