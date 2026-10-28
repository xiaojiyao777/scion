"""R26 retains complete safe evidence and does not turn diagnostics into gates."""

import ast
import json
import re

from scion.cli.commands.init_run import _load_cli_problem_adapter
from scion.core.models import Branch, BranchState, ChampionState, HypothesisProposal
from scion.core.problem_runtime import ProblemRuntime
from scion.proposal.context_snapshot import freeze_proposal_context
from scion.proposal.edit_protocol.source_discovery import read_only_files_from_context
from scion.tests.unit import test_r16_inputs as helpers
from scion.tests.unit import test_r21_inputs as previous
from scion.tests.unit import test_r25_inputs as r25
from scion.verification.development import declared_development_suites

PREFIX = "v04-cvrp-r26-scope-and-net-benefit-autonomous"
BEGIN = "BEGIN COMPLETE HISTORICAL R25 QUESTION\n"
END = "\nEND COMPLETE HISTORICAL R25 QUESTION"


def test_protocol_unchanged_and_seeds_prospectively_fresh():
    helpers.test_fresh_seeds_and_unchanged_protocol(PREFIX, r25.PREFIX, 320000, 17)


def test_public_formal_closure():
    helpers.test_full_public_formal_closure(
        PREFIX, "scion/scion/problems/cvrp/problem-v1.yaml",
        "v04-cvrp-r7-autonomous-source-continuation", 12, "scion/scion/problems/cvrp",
    )


def test_whole_question_and_observations_without_forced_research():
    old, new = previous.research_input(r25.PREFIX), previous.research_input(PREFIX)
    assert new["observations"] == old["observations"]
    frame, rest = new["current_question"].split(BEGIN, 1)
    historical, _ = rest.split(END, 1)
    assert historical == old["current_question"]
    for phrase in (
        "complete final R22 C3 source", "same local comparator as R24 and R25",
        "not a promotion claim, state restore or sibling merge",
        "H/C retain algorithm and test choice", "no target file",
        "All twenty-three supplied history files are loaded whole",
        "not a new Contract or Decision gate", "do not pool overlapping cells",
        "does not assert a nonempty publication or hit",
        "setup, key construction, scans, misses, eviction and polling",
        "full/empty/partial eligibility", "a separate future experiment",
    ):
        assert phrase in frame


def test_all_twelve_screening_matrices_include_losses():
    addition = previous.research_input(PREFIX)["current_question"].split(END, 1)[1]
    blocks = re.findall(r"STAGE (\d+) ([ABC]\d);([^\n]+)\n(.*?)(?=\nSTAGE|\Z)",
                        addition, re.S)
    assert [int(n) for n, _, _, _ in blocks] == list(range(1, 13))
    assert [label for _, label, _, _ in blocks] == [
        "A1", "B1", "C1", "A2", "B2", "C2", "C2", "A3", "B3", "C3", "A4", "A4",
    ]
    matrices = {}
    for number, _, header, body in blocks:
        seeds = header.split("seeds:", 1)[1].split(";", 1)[0].split(",")
        matrix = {case: json.loads(vector) for case, vector in re.findall(
            r"^([^:\n]+): (\[[^\n]+\]), median", body, re.M
        )}
        count = 8 if int(number) in (7, 12) else 4
        assert len(seeds) == count
        assert len(matrix) == (6 if count == 8 else 5)
        assert all(len(vector) == count for vector in matrix.values())
        matrices[int(number)] = matrix
    assert sum(len(v) for m in matrices.values() for v in m.values()) == 296
    assert matrices[7]["tai100a"] == [52, 7, -76, 3, 6, -14, -14, -29]
    assert matrices[10]["tai100a"] == [20, 12, 93, 58]
    assert matrices[10]["X-n513-k21"] == [-15, -15, -15, -15]
    assert matrices[12]["tai100a"] == [-73, 0, 6, 1, -7, -3, -35, 7]
    assert matrices[12]["A-n54-k7"] == [-5, -1, 5, 0, -5, 0, 4, 1]


def test_no_private_or_operational_input():
    rendered = json.dumps(previous.research_input(PREFIX))
    for private in (
        "B-n39-k5", "X-n106-k14", "tai385", "A-n62-k8", "X-n228-k23",
        "X-n627-k43", "-35.25", "606.25", "320081", "320113",
        "VALIDATION_EXPAND", "d5d34b33", "/metrics/", ".py",
        "Not authenticated", "PROVIDER_TRANSIENT",
    ):
        assert private not in rendered


def test_twenty_three_histories_same_source_and_resources():
    _, old = previous.invocation(r25.PREFIX, "20261026")
    command, new = previous.invocation(PREFIX, "20261028")
    values = previous.option_values
    histories = values(new, "--research-history")
    assert len(histories) == len(set(histories)) == 23
    assert histories[:-1] == values(old, "--research-history")
    root = "/home/clawd/research/scion-experiments/"
    assert histories[-1] == root + r25.PREFIX + "-20261026/research_history.jsonl"
    for option in (
        "--source-tree", "--problem", "--code-research-limits", "--split",
        "--time-limit-sec", "--rounds", "--provider-call-cap",
        "--provider-transient-retries", "--outer-hardwall-sec",
    ):
        assert values(new, option) == values(old, option)
    assert "SCION_MODEL=gpt-6.1-sol SCION_REASONING_EFFORT=high" in command
    assert values(new, "--campaign-dir") == [root + PREFIX + "-20261028"]


def test_projection_preserves_question_and_optional_scope_example():
    adapter = _load_cli_problem_adapter(
        helpers.ROOT / "scion/scion/problems/cvrp/problem-v1.yaml"
    )
    value = previous.research_input(PREFIX)
    runtime = ProblemRuntime(adapter=adapter, research_input=value,
        development_suites=declared_development_suites(adapter.spec))
    branch = Branch(branch_id="r26-preflight", state=BranchState.EXPLORE,
                    base_champion_id=1)
    champion = ChampionState(version=1, operator_pool={},
                             code_snapshot_path=str(adapter.spec.root_dir))
    context = runtime.build_hypothesis_context(branch=branch, champion=champion)
    projected = freeze_proposal_context("hypothesis", context).provider_context()
    assert projected["research_question"]["current_question"] == value["current_question"]
    assert len(projected["prior_research_observations"]) == 5
    hypothesis = HypothesisProposal(hypothesis_text="Context-only test; never dispatched.",
        change_locus=adapter.spec.research_surfaces[0].name,
        action="modify", target_file="policies/baseline_modules/local_search.py")
    context = runtime.build_code_context(branch=branch, hypothesis=hypothesis,
                                         champion=champion)
    freeze_proposal_context("code", context)
    source = read_only_files_from_context(context)["tests/test_solver.py"]
    assert "test_reference_matches_eligible_frontier" in source
    assert "Publication alone does not prove reuse" in source
    collected = [n for n in ast.parse(source).body
                 if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
    assert len(collected) == 2
