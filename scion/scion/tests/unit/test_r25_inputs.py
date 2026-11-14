"""R25 preserves whole safe evidence, source choice and scientific boundaries."""

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
from scion.tests.unit import test_r24_inputs as r24
from scion.verification.development import declared_development_suites

PREFIX = "v04-cvrp-r25-counterfactual-evidence-autonomous"
BEGIN = "BEGIN COMPLETE HISTORICAL R24 QUESTION\n"
END = "\nEND COMPLETE HISTORICAL R24 QUESTION"


def test_protocol_unchanged_and_seeds_prospectively_fresh():
    helpers.test_fresh_seeds_and_unchanged_protocol(PREFIX, r24.PREFIX, 310000, 17)


def test_public_formal_closure():
    helpers.test_full_public_formal_closure(
        PREFIX, "scion/scion/problems/cvrp/problem-v1.yaml",
        "v04-cvrp-r7-autonomous-source-continuation", 12, "scion/scion/problems/cvrp",
    )


def test_whole_question_observations_and_unforced_current_source():
    old, new = previous.research_input(r24.PREFIX), previous.research_input(PREFIX)
    assert new["observations"] == old["observations"]
    frame, rest = new["current_question"].split(BEGIN, 1)
    historical, _ = rest.split(END, 1)
    assert historical == old["current_question"]
    for phrase in (
        "complete final R22 C3 source", "same local comparator as R24",
        "not a promotion claim, state restore or sibling merge",
        "H/C retain algorithm and test choice", "no target file",
        "All twenty-two supplied history files are loaded whole",
        "weaker passing probe", "not a new Contract or Decision gate",
        "do not pool overlapping cells", "Do not presuppose a best-return bug",
        "discarding the computed extra-gain flag", "separate future experiment",
    ):
        assert phrase in frame


def test_all_eleven_screening_stages_and_adverse_vectors_remain():
    addition = previous.research_input(PREFIX)["current_question"].split(END, 1)[1]
    blocks = re.findall(r"STAGE (\d+) ([ABCD]\d);([^\n]+)\n(.*?)(?=\nSTAGE|\Z)",
                        addition, re.S)
    assert [int(n) for n, _, _, _ in blocks] == [1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12]
    matrices = {}
    for number, _, header, body in blocks:
        seeds = header.split("seeds:", 1)[1].split(";", 1)[0].split(",")
        matrix = {case: json.loads(vector) for case, vector in re.findall(
            r"^([^:\n]+): (\[[^\n]+\]), median", body, re.M
        )}
        count = 8 if int(number) in (2, 5, 7, 10, 12) else 4
        assert len(seeds) == count
        assert len(matrix) == (6 if count == 8 else 5)
        assert all(len(vector) == count for vector in matrix.values())
        matrices[int(number)] = matrix
    assert sum(len(v) for m in matrices.values() for v in m.values()) == 360
    assert matrices[7] == {
        "B-n34-k5": [0, 0, 0, 0, 0, 0, 0, 0],
        "tai100a": [-2, -3, 77, 50, -32, 58, 0, 122],
        "X-n351-k40": [476, 294, 0, 0, 269, 0, 374, 0],
        "A-n54-k7": [-1, 1, 0, -3, 1, 1, 1, 0],
        "X-n190-k8": [0, 0, 0, 0, 0, 0, 0, 0],
        "X-n513-k21": [32, 32, 32, 32, 47, 32, 32, 32],
    }
    assert matrices[3]["X-n351-k40"] == [-299, -1015, -822, -66]
    assert matrices[12]["X-n351-k40"] == [127, 19, 0, 0, 316, 0, -343, 0]
    assert matrices[12]["tai100a"] == [155, -5, -23, 0, -24, -15, 10, 0]


def test_no_private_or_operational_input():
    rendered = json.dumps(previous.research_input(PREFIX))
    for private in (
        "B-n39-k5", "X-n106-k14", "tai385", "A-n62-k8", "X-n228-k23",
        "X-n627-k43", "-35.25", "606.25", "1075.5", "300137", "300149",
        "300151", "300163", "310111", "310169", "VALIDATION_EXPAND",
        "d5d34b33", "/metrics/", ".py", "Not authenticated", "PROVIDER_TRANSIENT",
    ):
        assert private not in rendered


def test_twenty_two_histories_same_complete_source_and_resources():
    _, old = previous.invocation(r24.PREFIX, "20261024")
    command, new = previous.invocation(PREFIX, "20261026")
    values = previous.option_values
    histories = values(new, "--research-history")
    assert len(histories) == len(set(histories)) == 22
    assert histories[:-1] == values(old, "--research-history")
    root = "/home/clawd/research/scion-experiments/"
    assert histories[-1] == root + r24.PREFIX + "-20261024/research_history.jsonl"
    for option in (
        "--source-tree", "--problem", "--code-research-limits", "--split",
        "--time-limit-sec", "--rounds", "--provider-call-cap",
        "--provider-transient-retries", "--outer-hardwall-sec",
    ):
        assert values(new, option) == values(old, option)
    for setting in (
        "SCION_MODEL=gpt-6.1-sol", "SCION_REASONING_EFFORT=high",
        "SCION_LLM_TIMEOUT_SEC=180", "SCION_LLM_CODE_RESEARCH_TURN_TIMEOUT_SEC=300",
    ):
        assert setting in command
    assert values(new, "--campaign-dir") == [root + PREFIX + "-20261026"]


def test_provider_projection_keeps_question_and_optional_support_separate():
    adapter = _load_cli_problem_adapter(
        helpers.ROOT / "scion/scion/problems/cvrp/problem-v1.yaml"
    )
    value = previous.research_input(PREFIX)
    runtime = ProblemRuntime(adapter=adapter, research_input=value,
        development_suites=declared_development_suites(adapter.spec))
    branch = Branch(branch_id="r25-preflight", state=BranchState.EXPLORE,
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
    hypothesis = HypothesisProposal(hypothesis_text="Context-only test; never dispatched.",
        change_locus=adapter.spec.research_surfaces[0].name,
        action="modify", target_file="policies/baseline_modules/local_search.py")
    context = runtime.build_code_context(branch=branch, hypothesis=hypothesis,
                                         champion=champion)
    freeze_proposal_context("code", context)
    public, editable = read_only_files_from_context(context), all_source_files_from_context(context)
    assert not set(public) & set(editable)
    source = public["tests/test_solver.py"]
    assert "reference_trial_comparison" in source and "additional_gain" in source
    collected = [n for n in ast.parse(source).body
                 if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
    assert len(collected) == 2
