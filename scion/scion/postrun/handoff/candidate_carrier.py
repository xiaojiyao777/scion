"""Select one qualified candidate carrier from ordinary post-run artifacts.

The selector is provider- and solver-free.  It does not interpret candidate
quality and returns no hypothesis or patch body.  Callers remain responsible
for the scientific qualification predicate and for loading normalized
terminal artifacts before invoking it.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_CODE_HASH = re.compile(r"^[0-9a-f]{64}$")
_HYPOTHESIS_PROJECTION = ("text", "action", "change_locus", "target_file")


class CarrierUnavailable(ValueError):
    """The terminal artifacts do not identify exactly one candidate carrier."""


@dataclass(frozen=True)
class CandidateCarrier:
    """Sanitized references for one mechanically selected candidate carrier."""

    branch_id: str
    code_hash: str
    screening_indices: tuple[int, int]
    candidate_workspace: Path


def select_candidate_carrier(
    *,
    status: Mapping[str, Any],
    summary: Mapping[str, Any],
    history: Sequence[Mapping[str, Any]],
    lineage_events: Sequence[Mapping[str, Any]],
    candidate_workspaces: Path,
    compute_workspace_hash: Callable[[Path], str],
) -> CandidateCarrier:
    """Return the sole carrier matching two same-candidate screening records.

    Any number of non-``ready_validate`` branches and nonmatching historical
    candidate workspaces may coexist.  Ambiguous, incomplete or inconsistent
    terminal evidence fails closed with :class:`CarrierUnavailable`.
    """

    status_value = _mapping(status, "status")
    summary_value = _mapping(summary, "summary")
    branch_id, branch_hash = _ready_branch(status_value)

    steps = _mapping_sequence(summary_value.get("steps"), "summary.steps")
    records = _mapping_sequence(history, "history")
    _require_aligned_lengths(status_value, summary_value, steps, records)

    screening_indices = _screening_indices(steps, records, branch_id=branch_id)
    hypotheses: list[Mapping[str, Any]] = []
    patches: list[Mapping[str, Any]] = []
    for index in screening_indices:
        step = steps[index]
        record = records[index]
        if (
            _string(step.get("branch_id"), f"summary.steps[{index}].branch_id")
            != branch_id
        ):
            raise CarrierUnavailable(
                "screening records do not belong to the ready_validate branch"
            )
        hypothesis = _mapping(record.get("hypothesis"), f"history[{index}].hypothesis")
        summary_hypothesis = _mapping(
            step.get("hypothesis"), f"summary.steps[{index}].hypothesis"
        )
        try:
            projected = {key: hypothesis[key] for key in _HYPOTHESIS_PROJECTION}
        except KeyError as exc:
            raise CarrierUnavailable(
                f"history[{index}].hypothesis is incomplete"
            ) from exc
        if dict(summary_hypothesis) != projected:
            raise CarrierUnavailable(
                "summary and history hypothesis projections differ"
            )
        patch = _mapping(record.get("patch"), f"history[{index}].patch")
        changes = _mapping_sequence(
            patch.get("changes"), f"history[{index}].patch.changes"
        )
        if not changes:
            raise CarrierUnavailable("screening patch must contain a change")
        hypotheses.append(hypothesis)
        patches.append(patch)

    if dict(hypotheses[0]) != dict(hypotheses[1]):
        raise CarrierUnavailable("screening hypothesis values differ")
    if dict(patches[0]) != dict(patches[1]):
        raise CarrierUnavailable("screening patches differ")

    _require_screening_code_hash(
        lineage_events=lineage_events,
        branch_id=branch_id,
        branch_hash=branch_hash,
        hypothesis=hypotheses[0],
        patch=patches[0],
    )
    workspace = _matching_candidate_workspace(
        candidate_workspaces=Path(candidate_workspaces),
        branch_hash=branch_hash,
        compute_workspace_hash=compute_workspace_hash,
    )
    return CandidateCarrier(
        branch_id=branch_id,
        code_hash=branch_hash,
        screening_indices=screening_indices,
        candidate_workspace=workspace,
    )


def _ready_branch(status: Mapping[str, Any]) -> tuple[str, str]:
    branches = _mapping_sequence(status.get("branches"), "status.branches")
    ready: list[Mapping[str, Any]] = []
    seen_ids: set[str] = set()
    for index, branch in enumerate(branches):
        branch_id = _string(branch.get("id"), f"status.branches[{index}].id")
        if branch_id in seen_ids:
            raise CarrierUnavailable("status contains duplicate branch ids")
        seen_ids.add(branch_id)
        state = _string(branch.get("state"), f"status.branches[{index}].state")
        if state == "ready_validate":
            ready.append(branch)
    if len(ready) != 1:
        raise CarrierUnavailable(
            "terminal status must contain exactly one ready_validate branch"
        )
    branch = ready[0]
    return _string(branch.get("id"), "ready branch id"), _code_hash(
        branch.get("current_code_hash"), "ready branch current_code_hash"
    )


def _require_aligned_lengths(
    status: Mapping[str, Any],
    summary: Mapping[str, Any],
    steps: Sequence[Mapping[str, Any]],
    history: Sequence[Mapping[str, Any]],
) -> None:
    status_count = _nonnegative_int(status.get("n_steps"), "status.n_steps")
    summary_count = _nonnegative_int(summary.get("n_steps"), "summary.n_steps")
    if status_count != summary_count or status_count != len(steps):
        raise CarrierUnavailable("status and summary step counts differ")
    if len(history) != len(steps):
        raise CarrierUnavailable("summary steps and ordinary history are not aligned")


def _screening_indices(
    steps: Sequence[Mapping[str, Any]],
    history: Sequence[Mapping[str, Any]],
    *,
    branch_id: str,
) -> tuple[int, int]:
    step_indices = tuple(
        index
        for index, step in enumerate(steps)
        if _summary_protocol_stage(step, index) == "screening"
    )
    history_indices = tuple(
        index
        for index, record in enumerate(history)
        if _history_protocol_stage(record, index) == "screening"
    )
    if step_indices != history_indices:
        raise CarrierUnavailable(
            "summary and history screening records are not stage-aligned"
        )
    ready_indices = tuple(
        index
        for index in step_indices
        if _string(
            steps[index].get("branch_id"),
            f"summary.steps[{index}].branch_id",
        )
        == branch_id
    )
    if len(ready_indices) != 2:
        raise CarrierUnavailable(
            "ready_validate branch must have exactly two aligned screening records"
        )
    return ready_indices


def _summary_protocol_stage(step: Mapping[str, Any], index: int) -> str | None:
    protocol = step.get("protocol_result")
    if protocol is None:
        return None
    return _string(
        _mapping(protocol, f"summary.steps[{index}].protocol_result").get("stage"),
        f"summary.steps[{index}].protocol_result.stage",
    )


def _history_protocol_stage(record: Mapping[str, Any], index: int) -> str | None:
    protocol = record.get("protocol")
    if protocol is None:
        return None
    protocol_value = _mapping(protocol, f"history[{index}].protocol")
    evidence = _mapping(
        protocol_value.get("evidence"), f"history[{index}].protocol.evidence"
    )
    return _string(evidence.get("stage"), f"history[{index}].protocol.evidence.stage")


def _require_screening_code_hash(
    *,
    lineage_events: Sequence[Mapping[str, Any]],
    branch_id: str,
    branch_hash: str,
    hypothesis: Mapping[str, Any],
    patch: Mapping[str, Any],
) -> None:
    events = _mapping_sequence(lineage_events, "lineage_events")
    screening = [
        event
        for event in events
        if event.get("event_kind") == "experiment"
        and event.get("stage") == "screening"
        and event.get("branch_id") == branch_id
    ]
    if len(screening) != 2:
        raise CarrierUnavailable(
            "ready_validate branch must have exactly two screening lineage events"
        )
    hashes = tuple(
        _code_hash(event.get("code_hash"), "screening lineage code_hash")
        for event in screening
    )
    if hashes != (branch_hash, branch_hash):
        raise CarrierUnavailable(
            "screening lineage and ready branch code hashes differ"
        )

    hypothesis_text = hypothesis.get("text")
    if not isinstance(hypothesis_text, str) or any(
        event.get("hypothesis_text") != hypothesis_text for event in screening
    ):
        raise CarrierUnavailable("screening lineage and ordinary hypotheses differ")
    changes = _mapping_sequence(patch.get("changes"), "screening patch changes")
    primary = changes[0]
    patch_action = _string(primary.get("action"), "screening patch primary action")
    patch_file = _string(primary.get("file_path"), "screening patch primary file")
    if any(
        event.get("patch_action") != patch_action
        or event.get("patch_file") != patch_file
        for event in screening
    ):
        raise CarrierUnavailable("screening lineage and ordinary patches differ")


def _matching_candidate_workspace(
    *,
    candidate_workspaces: Path,
    branch_hash: str,
    compute_workspace_hash: Callable[[Path], str],
) -> Path:
    if candidate_workspaces.is_symlink() or not candidate_workspaces.is_dir():
        raise CarrierUnavailable("candidate_workspaces must be a regular directory")
    parent = candidate_workspaces.resolve()
    matching: list[Path] = []
    try:
        entries = list(candidate_workspaces.iterdir())
    except OSError as exc:
        raise CarrierUnavailable("candidate_workspaces cannot be enumerated") from exc
    for entry in entries:
        if (
            not entry.name.startswith("candidate-")
            or entry.name == "candidate-"
            or entry.is_symlink()
            or not entry.is_dir()
        ):
            raise CarrierUnavailable("candidate_workspaces contains an invalid entry")
        resolved = entry.resolve()
        if resolved.parent != parent:
            raise CarrierUnavailable("candidate workspace escapes its parent")
        try:
            observed_hash = _code_hash(
                compute_workspace_hash(resolved),
                "candidate workspace code_hash",
            )
        except CarrierUnavailable:
            raise
        except Exception as exc:
            raise CarrierUnavailable("candidate workspace hashing failed") from exc
        if observed_hash == branch_hash:
            matching.append(resolved)
    if len(matching) != 1:
        raise CarrierUnavailable(
            "exactly one candidate workspace must match the ready branch code_hash"
        )
    return matching[0]


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CarrierUnavailable(f"{name} must be an object")
    return value


def _mapping_sequence(value: Any, name: str) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise CarrierUnavailable(f"{name} must be an array")
    return tuple(_mapping(item, f"{name}[{index}]") for index, item in enumerate(value))


def _string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise CarrierUnavailable(f"{name} must be a nonempty string")
    return value


def _code_hash(value: Any, name: str) -> str:
    text = _string(value, name)
    if _CODE_HASH.fullmatch(text) is None:
        raise CarrierUnavailable(f"{name} must be a lowercase SHA-256 hex value")
    return text


def _nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CarrierUnavailable(f"{name} must be a nonnegative integer")
    return value
