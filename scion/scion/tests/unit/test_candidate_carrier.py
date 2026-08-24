"""Provider- and solver-free tests for post-run candidate-carrier selection."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from scion.postrun.handoff import CarrierUnavailable, select_candidate_carrier

_READY_HASH = "a" * 64
_OLD_HASH = "b" * 64


def _hypothesis(text: str = "candidate") -> dict[str, object]:
    return {
        "text": text,
        "action": "modify",
        "change_locus": "solver_design",
        "target_file": "solver.py",
        "predicted_direction": "improve",
        "target_weakness": "quality",
        "expected_effect": "lower objective",
        "suggested_weight": None,
    }


def _summary_hypothesis(value: dict[str, object]) -> dict[str, object]:
    return {
        key: value[key] for key in ("text", "action", "change_locus", "target_file")
    }


def _patch(source: str = "candidate source") -> dict[str, object]:
    return {
        "changes": [
            {
                "file_path": "solver.py",
                "action": "modify",
                "source": source,
            }
        ]
    }


def _history_record(
    *,
    hypothesis: dict[str, object],
    patch: dict[str, object] | None,
    screening: bool,
) -> dict[str, object]:
    return {
        "hypothesis": hypothesis,
        "patch": patch,
        "protocol": {"evidence": {"stage": "screening"}} if screening else None,
    }


def _artifacts(tmp_path: Path) -> dict[str, object]:
    candidate_root = tmp_path / "candidate_workspaces"
    candidate_root.mkdir()
    (candidate_root / "candidate-ready").mkdir()
    (candidate_root / "candidate-old").mkdir()

    screened_hypothesis = _hypothesis()
    screened_patch = _patch()
    historical_hypothesis = _hypothesis("historical candidate")
    steps = [
        {
            "branch_id": "old-explore",
            "hypothesis": _summary_hypothesis(historical_hypothesis),
            "protocol_result": {"stage": "screening"},
        },
        {
            "branch_id": "qualified",
            "hypothesis": _summary_hypothesis(screened_hypothesis),
            "protocol_result": {"stage": "screening"},
        },
        {
            "branch_id": "qualified",
            "hypothesis": _summary_hypothesis(screened_hypothesis),
            "protocol_result": {"stage": "screening"},
        },
    ]
    history = [
        _history_record(
            hypothesis=historical_hypothesis,
            patch=_patch("historical candidate source"),
            screening=True,
        ),
        _history_record(
            hypothesis=deepcopy(screened_hypothesis),
            patch=deepcopy(screened_patch),
            screening=True,
        ),
        _history_record(
            hypothesis=deepcopy(screened_hypothesis),
            patch=deepcopy(screened_patch),
            screening=True,
        ),
    ]
    events = [
        {
            "event_kind": "execution_outcome",
            "stage": "screening",
            "branch_id": "qualified",
        },
        {
            "event_kind": "experiment",
            "stage": "screening",
            "branch_id": "old-explore",
            "code_hash": _OLD_HASH,
            "hypothesis_text": "historical candidate",
            "patch_action": "modify",
            "patch_file": "solver.py",
        },
        *[
            {
                "event_kind": "experiment",
                "stage": "screening",
                "branch_id": "qualified",
                "code_hash": _READY_HASH,
                "hypothesis_text": "candidate",
                "patch_action": "modify",
                "patch_file": "solver.py",
            }
            for _ in range(2)
        ],
    ]
    return {
        "status": {
            "n_steps": 3,
            "branches": [
                {"id": "old-explore", "state": "explore", "current_code_hash": None},
                {
                    "id": "qualified",
                    "state": "ready_validate",
                    "current_code_hash": _READY_HASH,
                },
                {
                    "id": "old-blocked",
                    "state": "blocked_infra",
                    "current_code_hash": _OLD_HASH,
                },
            ],
        },
        "summary": {"n_steps": 3, "steps": steps},
        "history": history,
        "lineage_events": events,
        "candidate_workspaces": candidate_root,
        "workspace_hashes": {
            "candidate-ready": _READY_HASH,
            "candidate-old": _OLD_HASH,
        },
    }


def _select(artifacts: dict[str, object]):
    hashes = artifacts["workspace_hashes"]
    assert isinstance(hashes, dict)
    return select_candidate_carrier(
        status=artifacts["status"],
        summary=artifacts["summary"],
        history=artifacts["history"],
        lineage_events=artifacts["lineage_events"],
        candidate_workspaces=artifacts["candidate_workspaces"],
        compute_workspace_hash=lambda path: hashes[path.name],
    )


def test_selects_one_ready_carrier_with_historical_branches_and_workspaces(
    tmp_path: Path,
) -> None:
    artifacts = _artifacts(tmp_path)

    carrier = _select(artifacts)

    assert carrier.branch_id == "qualified"
    assert carrier.code_hash == _READY_HASH
    assert carrier.screening_indices == (1, 2)
    assert carrier.candidate_workspace.name == "candidate-ready"


@pytest.mark.parametrize("ready_count", [0, 2])
def test_requires_exactly_one_ready_branch(tmp_path: Path, ready_count: int) -> None:
    artifacts = _artifacts(tmp_path)
    status = artifacts["status"]
    assert isinstance(status, dict)
    branches = status["branches"]
    assert isinstance(branches, list)
    branches[1]["state"] = "explore"
    if ready_count == 2:
        branches[0]["state"] = "ready_validate"
        branches[0]["current_code_hash"] = _READY_HASH
        branches[2]["state"] = "ready_validate"

    with pytest.raises(CarrierUnavailable, match="exactly one ready_validate"):
        _select(artifacts)


def test_requires_both_screening_records_on_ready_branch(tmp_path: Path) -> None:
    artifacts = _artifacts(tmp_path)
    summary = artifacts["summary"]
    assert isinstance(summary, dict)
    summary["steps"][2]["branch_id"] = "old-explore"

    with pytest.raises(CarrierUnavailable, match="exactly two aligned screening"):
        _select(artifacts)


@pytest.mark.parametrize("field", ["hypothesis", "patch"])
def test_requires_exact_hypothesis_and_patch_reuse(tmp_path: Path, field: str) -> None:
    artifacts = _artifacts(tmp_path)
    history = artifacts["history"]
    assert isinstance(history, list)
    if field == "hypothesis":
        history[2]["hypothesis"]["expected_effect"] = "different"
    else:
        history[2]["patch"]["changes"][0]["source"] = "different"

    with pytest.raises(CarrierUnavailable, match=f"screening {field}"):
        _select(artifacts)


def test_requires_aligned_screening_records(tmp_path: Path) -> None:
    artifacts = _artifacts(tmp_path)
    history = artifacts["history"]
    assert isinstance(history, list)
    history[2]["protocol"] = None

    with pytest.raises(CarrierUnavailable, match="not stage-aligned"):
        _select(artifacts)


def test_requires_screening_and_branch_code_hash_equality(tmp_path: Path) -> None:
    artifacts = _artifacts(tmp_path)
    events = artifacts["lineage_events"]
    assert isinstance(events, list)
    events[2]["code_hash"] = _OLD_HASH

    with pytest.raises(CarrierUnavailable, match="code hashes differ"):
        _select(artifacts)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("hypothesis_text", "different", "ordinary hypotheses"),
        ("patch_file", "different.py", "ordinary patches"),
    ],
)
def test_requires_lineage_to_match_the_reused_hypothesis_and_patch(
    tmp_path: Path,
    field: str,
    value: str,
    message: str,
) -> None:
    artifacts = _artifacts(tmp_path)
    events = artifacts["lineage_events"]
    assert isinstance(events, list)
    events[2][field] = value

    with pytest.raises(CarrierUnavailable, match=message):
        _select(artifacts)


@pytest.mark.parametrize("matching_count", [0, 2])
def test_requires_exactly_one_hash_matching_workspace(
    tmp_path: Path,
    matching_count: int,
) -> None:
    artifacts = _artifacts(tmp_path)
    hashes = artifacts["workspace_hashes"]
    assert isinstance(hashes, dict)
    hashes["candidate-ready"] = _OLD_HASH
    if matching_count == 2:
        hashes["candidate-ready"] = _READY_HASH
        hashes["candidate-old"] = _READY_HASH

    with pytest.raises(CarrierUnavailable, match="exactly one candidate workspace"):
        _select(artifacts)


def test_rejects_symlink_workspace_entry(tmp_path: Path) -> None:
    artifacts = _artifacts(tmp_path)
    root = artifacts["candidate_workspaces"]
    assert isinstance(root, Path)
    (root / "candidate-link").symlink_to(
        root / "candidate-old", target_is_directory=True
    )

    with pytest.raises(CarrierUnavailable, match="invalid entry"):
        _select(artifacts)
