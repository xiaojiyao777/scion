"""Provider-free research regression for the terminal R56 code response."""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

from scion.contract.gate import ContractGate
from scion.core.models import HypothesisProposal, patch_file_changes
from scion.problem.bridge import (
    legacy_problem_spec_from_v1,
    load_problem_spec_v1_from_yaml,
)
from scion.proposal.engine import _parse_patch
from scion.runtime.workspace import WorkspaceMaterializer
from scion.verification.tests import check_regression_tests, check_unit_tests

_TEST_ROOT = Path(__file__).resolve().parent
_CVRP_ROOT = _TEST_ROOT.parent / "problems" / "cvrp"
_FIXTURE_ROOT = _TEST_ROOT / "fixtures" / "cvrp_r56_exact_line_replace"
_SCHEDULER = "policies/baseline_modules/scheduler.py"
_ACCEPTANCE = "policies/baseline_modules/acceptance.py"


def _frozen_text(name: str) -> str:
    return (_FIXTURE_ROOT / name).read_text(encoding="utf-8")


def _reexpress_failed_r56_change(response: dict[str, object]) -> dict[str, object]:
    """Express only R56's indentation-sensitive multi-site edit in the new form."""

    corrected = copy.deepcopy(response)
    original_changes = response["additional_changes"]
    corrected_changes = corrected["additional_changes"]
    assert isinstance(original_changes, list)
    assert isinstance(corrected_changes, list)
    indices = [
        index
        for index, change in enumerate(original_changes)
        if isinstance(change, dict)
        and change.get("old_string") == "                    annealing.cool()\n"
        and change.get("replace_all") is True
    ]
    assert indices == [0]
    target = corrected_changes[indices[0]]
    assert isinstance(target, dict)
    target.update(
        {
            "edit_intent": "exact_line_replace",
            "old_string": "annealing.cool()",
            "new_string": (
                "annealing.set_progress(\n"
                "    self._annealing_progress(start_ms, reserve)\n"
                ")"
            ),
        }
    )

    assert {
        key: value for key, value in corrected.items() if key != "additional_changes"
    } == {key: value for key, value in response.items() if key != "additional_changes"}
    assert corrected_changes[1:] == original_changes[1:]
    original_target = original_changes[0]
    assert isinstance(original_target, dict)
    assert {
        key: value
        for key, value in target.items()
        if key not in {"edit_intent", "old_string", "new_string"}
    } == {
        key: value
        for key, value in original_target.items()
        if key not in {"edit_intent", "old_string", "new_string"}
    }
    return corrected


def _approved_r56_hypothesis() -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text=(
            "Replace iteration-count cooling with an elapsed-budget-normalized "
            "annealing schedule owned by the ALNS scheduler."
        ),
        change_locus="solver_design",
        action="modify",
        target_file=_SCHEDULER,
        predicted_direction="improve",
        target_weakness=(
            "The amount of diversification is determined by incidental iteration "
            "throughput rather than the fixed elapsed-time budget."
        ),
        expected_effect=(
            "Preserve feasible fleet behavior while improving final-best distance "
            "through elapsed-budget-normalized worsening-move acceptance."
        ),
    )


def test_r56_exact_line_replace_replay_passes_contract_and_cvrp_v3_v4(
    tmp_path: Path,
) -> None:
    """Replay no provider, canary, formal Protocol, Decision, or promotion path."""

    scheduler_before = _frozen_text("scheduler.py.txt")
    acceptance_before = _frozen_text("acceptance.py.txt")
    terminal_response = json.loads(_frozen_text("terminal_code_response.json"))
    assert scheduler_before.count("annealing.cool()") == 5
    assert sorted(
        len(line) - len(line.lstrip(" \t"))
        for line in scheduler_before.splitlines()
        if line.lstrip(" \t") == "annealing.cool()"
    ) == [12, 16, 16, 16, 20]

    workspace = tmp_path / "fresh-b0"
    shutil.copytree(
        _CVRP_ROOT,
        workspace,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    (workspace / _SCHEDULER).write_text(scheduler_before, encoding="utf-8")
    (workspace / _ACCEPTANCE).write_text(acceptance_before, encoding="utf-8")

    corrected_response = _reexpress_failed_r56_change(terminal_response)
    patch = _parse_patch(
        corrected_response,
        context={
            "editable_source_context": {
                "approved_target": _SCHEDULER,
                "sources": [
                    {"path": _SCHEDULER, "content": scheduler_before},
                    {"path": _ACCEPTANCE, "content": acceptance_before},
                ],
                "target_api_guidance": "",
            }
        },
    )
    assert [change.file_path for change in patch_file_changes(patch)] == [
        _SCHEDULER,
        _ACCEPTANCE,
    ]
    line_edit_attribution = [
        item
        for item in patch.repair_attribution
        if item.get("edit_intent") == "exact_line_replace"
    ]
    assert len(line_edit_attribution) == 1
    assert line_edit_attribution[0]["selector_match_count"] == 5

    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    problem_spec = legacy_problem_spec_from_v1(spec_v1)
    contract = ContractGate(
        problem_spec,
        champion_snapshot_path=str(workspace),
    ).validate_patch(
        patch,
        approved_hypothesis=_approved_r56_hypothesis(),
        selected_surface="solver_design",
        base_snapshot_path=str(workspace),
    )
    assert contract.passed, [
        (check.name, check.detail) for check in contract.checks if not check.passed
    ]

    materializer = WorkspaceMaterializer(
        str(tmp_path / "materializer"),
        frozen_patterns=frozenset(problem_spec.search_space.frozen),
        editable_patterns=problem_spec.search_space.editable,
    )
    materializer.apply_patch(str(workspace), patch)

    scheduler_after = (workspace / _SCHEDULER).read_text(encoding="utf-8")
    assert "annealing.cool()" not in scheduler_after
    assert scheduler_after.count("annealing.set_progress(") == 5

    v3 = check_unit_tests(problem_spec, None, str(workspace))
    v4 = check_regression_tests(problem_spec, None, str(workspace))
    assert v3.passed, v3.detail
    assert v4.passed, v4.detail
    assert "skipped" not in v3.detail.lower()
    assert "skipped" not in v4.detail.lower()
