"""Provider-free research regressions for terminal R56 and R58 code responses."""

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


def _reexpress_failed_r58_changes(response: dict[str, object]) -> dict[str, object]:
    """Collapse R58's split line deletions into one indentation-neutral edit."""

    corrected = copy.deepcopy(response)
    original_changes = response["additional_changes"]
    corrected_changes = corrected["additional_changes"]
    assert isinstance(original_changes, list)
    assert isinstance(corrected_changes, list)
    first = corrected_changes[0]
    assert isinstance(first, dict)
    assert first["old_string"] == (
        "                    annealing.cool()\n"
        '                    self.context.record_move("alns", attempted=1, accepted=0)'
    )
    first.update(
        {
            "edit_intent": "exact_line_replace",
            "old_string": "annealing.cool()",
            "new_string": "",
            "replace_all": True,
        }
    )
    original_first = original_changes[0]
    assert isinstance(original_first, dict)
    assert {
        key: value
        for key, value in first.items()
        if key not in {"edit_intent", "old_string", "new_string", "replace_all"}
    } == {
        key: value
        for key, value in original_first.items()
        if key not in {"edit_intent", "old_string", "new_string", "replace_all"}
    }
    tail_deletion = corrected_changes.pop(2)
    assert isinstance(tail_deletion, dict)
    assert tail_deletion["old_string"] == (
        "            annealing.cool()\n\n        destroy_weights.update()"
    )

    assert {
        key: value for key, value in corrected.items() if key != "additional_changes"
    } == {key: value for key, value in response.items() if key != "additional_changes"}
    assert corrected_changes[1:] == [
        original_changes[1],
        *original_changes[3:],
    ]
    return corrected


def _approved_r58_hypothesis() -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text=(
            "Replace per-iteration cooling in the ALNS scheduler with "
            "deadline-progress temperature setting immediately before acceptance."
        ),
        change_locus="solver_design",
        action="modify",
        target_file=_SCHEDULER,
        predicted_direction="improve",
        target_weakness=(
            "The temperature is tied to iteration count rather than elapsed budget."
        ),
        expected_effect=(
            "Stabilize the exploration-to-intensification transition under fixed "
            "deadlines while preserving feasibility and route limits."
        ),
    )


def _replay_response(
    tmp_path: Path,
    response: dict[str, object],
    hypothesis: HypothesisProposal,
    *,
    expected_set_progress_calls: int,
):
    """Run only parse, Contract, materialization, and lightweight verification."""

    scheduler_before = _frozen_text("scheduler.py.txt")
    acceptance_before = _frozen_text("acceptance.py.txt")
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

    patch = _parse_patch(
        response,
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
        approved_hypothesis=hypothesis,
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
    assert (
        scheduler_after.count("annealing.set_progress(") == expected_set_progress_calls
    )

    v3 = check_unit_tests(problem_spec, None, str(workspace))
    v4 = check_regression_tests(problem_spec, None, str(workspace))
    assert v3.passed, v3.detail
    assert v4.passed, v4.detail
    assert "skipped" not in v3.detail.lower()
    assert "skipped" not in v4.detail.lower()
    return patch


def _materialize_original_r58_response(
    tmp_path: Path,
    response: dict[str, object],
) -> str:
    """Return scheduler text from the frozen failing response, without V3/V4."""

    scheduler_before = _frozen_text("scheduler.py.txt")
    acceptance_before = _frozen_text("acceptance.py.txt")
    workspace = tmp_path / "original-r58"
    shutil.copytree(
        _CVRP_ROOT,
        workspace,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    (workspace / _SCHEDULER).write_text(scheduler_before, encoding="utf-8")
    (workspace / _ACCEPTANCE).write_text(acceptance_before, encoding="utf-8")
    patch = _parse_patch(
        response,
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
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    problem_spec = legacy_problem_spec_from_v1(spec_v1)
    WorkspaceMaterializer(
        str(tmp_path / "original-r58-materializer"),
        frozen_patterns=frozenset(problem_spec.search_space.frozen),
        editable_patterns=problem_spec.search_space.editable,
    ).apply_patch(str(workspace), patch)
    v3 = check_unit_tests(problem_spec, None, str(workspace))
    assert not v3.passed
    assert "skipped" not in v3.detail.lower()
    return (workspace / _SCHEDULER).read_text(encoding="utf-8")


def test_r56_exact_line_replace_replay_passes_contract_and_cvrp_v3_v4(
    tmp_path: Path,
) -> None:
    """Replay no provider, canary, formal Protocol, Decision, or promotion path."""

    terminal_response = json.loads(_frozen_text("terminal_code_response.json"))
    patch = _replay_response(
        tmp_path,
        _reexpress_failed_r56_change(terminal_response),
        _approved_r56_hypothesis(),
        expected_set_progress_calls=5,
    )
    line_edit_attribution = [
        item
        for item in patch.repair_attribution
        if item.get("edit_intent") == "exact_line_replace"
    ]
    assert len(line_edit_attribution) == 1
    assert line_edit_attribution[0]["selector_match_count"] == 5


def test_r58_exact_line_replace_replay_passes_contract_and_cvrp_v3_v4(
    tmp_path: Path,
) -> None:
    """Counterfactually re-express R58 without any provider or Protocol call."""

    terminal_response = json.loads(_frozen_text("terminal_code_response_r58.json"))
    assert all(
        change.get("edit_intent") == "exact_replace"
        for change in [terminal_response, *terminal_response["additional_changes"]]
    )
    original_scheduler = _materialize_original_r58_response(
        tmp_path,
        terminal_response,
    )
    assert original_scheduler.count("annealing.cool()") == 3
    patch = _replay_response(
        tmp_path,
        _reexpress_failed_r58_changes(terminal_response),
        _approved_r58_hypothesis(),
        expected_set_progress_calls=0,
    )
    line_edit_attribution = [
        item
        for item in patch.repair_attribution
        if item.get("edit_intent") == "exact_line_replace"
    ]
    assert len(line_edit_attribution) == 1
    assert line_edit_attribution[0]["selector_match_count"] == 5
