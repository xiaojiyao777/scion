"""Tainted feedback diagnosis helpers for agentic proposal prompting."""
from __future__ import annotations

from typing import Any, Mapping

from scion.proposal.tools import ProposalObservation
from scion.proposal.agentic_utils import (
    _drop_empty_dict,
    _json_ready,
    _sanitize_agentic_value,
)

def _safe_positive_int(value: Any) -> bool:
    try:
        return int(value) > 0
    except (TypeError, ValueError):
        return False

def _research_diagnosis_from_observations(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> dict[str, Any]:
    runtime_diagnoses: list[dict[str, Any]] = []
    screening_counts = {
        "screening_observations": 0,
        "runtime_observations": 0,
    }
    for observation in observations:
        if observation.is_error:
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        if observation.tool_name == "feedback.query_screening":
            screening_counts["screening_observations"] += 1
        if observation.tool_name != "feedback.query_runtime":
            continue
        screening_counts["runtime_observations"] += 1
        diagnosis = payload.get("research_diagnosis")
        if isinstance(diagnosis, Mapping):
            runtime_diagnoses.append(_sanitize_agentic_value(diagnosis))
    if not runtime_diagnoses and not any(screening_counts.values()):
        return {}
    meaningful = [
        diagnosis
        for diagnosis in runtime_diagnoses
        if _research_diagnosis_has_signal(diagnosis)
    ]
    diagnosis_source = meaningful or runtime_diagnoses
    latest = diagnosis_source[-1] if diagnosis_source else {}
    return _json_ready(
        {
            "schema_version": "agentic-research-diagnosis.v1",
            "source": "proposal_tool_observations",
            "screening_only": True,
            "observation_counts": screening_counts,
            "runtime_diagnosis_count": len(runtime_diagnoses),
            "runtime_diagnoses_with_signal": len(meaningful),
            "latest_runtime_diagnosis": latest,
            "aggregate_runtime_diagnosis": _aggregate_runtime_diagnoses(
                diagnosis_source
            ),
            "recent_runtime_diagnoses": diagnosis_source[-3:],
            "research_protocol": [
                "Use screening/runtime observations as tainted evidence for proposal reasoning only.",
                "Identify the prior failure pattern before proposing a mechanism change.",
                "Tie the hypothesis to declared surface evidence fields and expected protocol movement.",
                "Do not use validation/frozen holdout detail or raw metric refs.",
            ],
        }
    )


def _research_diagnosis_has_signal(diagnosis: Mapping[str, Any]) -> bool:
    if _safe_positive_int(diagnosis.get("screening_step_count")):
        return True
    for key in (
        "recent_screening_steps",
        "reason_code_counts",
        "failure_mode_tags",
        "runtime_signal_rows",
        "gate_outcome_counts",
    ):
        value = diagnosis.get(key)
        if isinstance(value, Mapping) and value:
            return True
        if isinstance(value, list) and value:
            return True
    return False


def _aggregate_runtime_diagnoses(
    diagnoses: list[dict[str, Any]],
) -> dict[str, Any]:
    reason_counts: dict[str, int] = {}
    surface_counts: dict[str, int] = {}
    gate_counts: dict[str, int] = {}
    failure_tags: set[str] = set()
    runtime_signal_rows: list[dict[str, Any]] = []
    recent_screening_steps: list[dict[str, Any]] = []
    for diagnosis in diagnoses:
        _merge_int_counts(reason_counts, diagnosis.get("reason_code_counts"))
        _merge_int_counts(surface_counts, diagnosis.get("surface_counts"))
        _merge_int_counts(gate_counts, diagnosis.get("gate_outcome_counts"))
        tags = diagnosis.get("failure_mode_tags")
        if isinstance(tags, list):
            failure_tags.update(str(tag) for tag in tags if tag)
        rows = diagnosis.get("runtime_signal_rows")
        if isinstance(rows, list):
            runtime_signal_rows.extend(row for row in rows if isinstance(row, Mapping))
        steps = diagnosis.get("recent_screening_steps")
        if isinstance(steps, list):
            recent_screening_steps.extend(
                step for step in steps if isinstance(step, Mapping)
            )
    return _drop_empty_dict(
        {
            "reason_code_counts": reason_counts,
            "surface_counts": surface_counts,
            "gate_outcome_counts": gate_counts,
            "failure_mode_tags": sorted(failure_tags),
            "runtime_signal_rows": runtime_signal_rows[-8:],
            "recent_screening_steps": recent_screening_steps[-8:],
        }
    )


def _merge_int_counts(target: dict[str, int], value: Any) -> None:
    if not isinstance(value, Mapping):
        return
    for key, count in value.items():
        try:
            amount = int(count)
        except (TypeError, ValueError):
            continue
        target[str(key)] = target.get(str(key), 0) + amount
