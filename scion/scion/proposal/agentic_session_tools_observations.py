"""Observation receipt and visibility helpers for APS proposal tools.

These helpers shape tainted proposal-tool observations for planner visibility and
check whether an equivalent tainted observation is already available. They do not
produce DecisionFeatures or authoritative gate evidence.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from scion.core.models import HypothesisProposal
from scion.proposal.agentic_session_feedback import (
    _has_equivalent_feedback_observation,
    _observation_satisfies_compact_requirement,
)
from scion.proposal.agentic_session_tools_config import (
    _ACTIVE_SOLVER_FILE_READ_TOOLS,
    _ACTIVE_SOLVER_READ_DEFAULT_MAX_CHARS,
    _APS_CODE_SURFACE_READ_CODE_CHARS,
    _SINGLE_SUCCESS_OBSERVATION_TOOLS,
)
from scion.proposal.agentic_utils import (
    _enum_value,
    _sanitize_agentic_value,
)
from scion.proposal.tools import ProposalObservation, ProposalToolContext


def _observation_selection_payload(observation: ProposalObservation) -> dict[str, Any]:
    structured_payload = _sanitize_agentic_value(observation.structured_payload)
    digest_payload = {
        "tool_name": observation.tool_name,
        "observation_type": observation.observation_type,
        "summary": observation.summary,
        "structured_payload": structured_payload,
    }
    digest = hashlib.sha256(
        json.dumps(digest_payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]
    return {
        "observation_id": observation.observation_id,
        "tool_name": observation.tool_name,
        "source": {
            "tool_call_id": observation.tool_call_id,
            "artifact_ref": observation.artifact_ref,
        },
        "phase": "agentic_tool_selection",
        "digest": digest,
        "observation_type": observation.observation_type,
        "summary": _sanitize_agentic_value(observation.summary),
        "is_error": observation.is_error,
        "failure_code": _enum_value(observation.failure_code),
        "exposure_level": _enum_value(observation.exposure_level),
    }


def _surface_names_from_observations(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> list[str]:
    names: list[str] = []
    for observation in observations:
        if observation.is_error or observation.tool_name != "context.list_surfaces":
            continue
        surfaces = observation.structured_payload.get("surfaces", ())
        if not isinstance(surfaces, (list, tuple)):
            continue
        for surface in surfaces:
            if not isinstance(surface, Mapping):
                continue
            for key in ("id", "name"):
                value = surface.get(key)
                if value:
                    names.append(str(value))
    return list(dict.fromkeys(names))


def _has_successful_surface_read(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    surface_name: str,
) -> bool:
    for observation in observations:
        if observation.is_error or observation.tool_name != "context.read_surface":
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        surface = payload.get("surface")
        if isinstance(surface, Mapping) and surface.get("name") == surface_name:
            return True
    return False


def _has_successful_reusable_observation(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    tool_name: str,
    args: Mapping[str, Any],
    *,
    forced_surface: str | None = None,
) -> bool:
    if tool_name in {"feedback.query_screening", "feedback.query_runtime"}:
        return _has_equivalent_feedback_observation(
            observations,
            tool_name,
            args,
            default_surface=str(forced_surface or "").strip(),
        )
    if tool_name == "context.read_algorithm_file":
        return _has_successful_algorithm_file_read(observations, args)
    if tool_name == "context.read_algorithm_symbol":
        return _has_successful_algorithm_symbol_read(observations, args)
    if tool_name == "context.read_operator_registry":
        return _has_successful_active_map_target_read(
            observations,
            tool_name,
            args,
            id_key="registry_id",
        )
    if tool_name == "context.read_algorithm_slice":
        return _has_successful_active_map_target_read(
            observations,
            tool_name,
            args,
            id_key="slice_id",
        )
    if tool_name in _SINGLE_SUCCESS_OBSERVATION_TOOLS:
        return any(
            observation.tool_name == tool_name and not observation.is_error
            for observation in observations
        )
    if tool_name != "context.read_surface":
        return False
    requested_surface = str(args.get("surface") or forced_surface or "").strip()
    if not requested_surface:
        return False
    return _has_successful_surface_read(observations, requested_surface)


def _has_attempted_active_map_target_read(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    tool_name: str,
    args: Mapping[str, Any],
    *,
    id_key: str,
) -> bool:
    requested_id = str(args.get(id_key) or "").strip()
    if not requested_id:
        return False
    for observation in observations:
        if observation.tool_name != tool_name:
            continue
        payload = observation.structured_payload
        observed_id = ""
        if isinstance(payload, Mapping):
            observed_id = str(payload.get(id_key) or "").strip()
        if observed_id == requested_id:
            return True
        if observation.is_error and not observed_id:
            return True
    return False


def _has_successful_tool(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    tool_name: str,
) -> bool:
    return any(
        observation.tool_name == tool_name and not observation.is_error
        for observation in observations
    )


def _has_successful_code_phase_reusable_observation(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    tool_name: str,
    args: Mapping[str, Any],
    *,
    hypothesis: HypothesisProposal,
) -> bool:
    if tool_name == "memory.query":
        return False
    if tool_name in {"feedback.query_screening", "feedback.query_runtime"}:
        return _has_successful_reusable_observation(
            observations,
            tool_name,
            args,
            forced_surface=hypothesis.change_locus,
        )
    if tool_name == "context.read_surface":
        requested_surface = str(
            args.get("surface") or hypothesis.change_locus or ""
        ).strip()
        requested_target = str(
            args.get("target_file") or hypothesis.target_file or ""
        ).strip()
        return _has_code_phase_surface_read(
            observations,
            hypothesis,
            surface=requested_surface,
            target_file=requested_target or None,
        )
    reusable = _has_successful_reusable_observation(
        observations,
        tool_name,
        args,
        forced_surface=hypothesis.change_locus,
    )
    if reusable or tool_name in _ACTIVE_SOLVER_FILE_READ_TOOLS:
        return reusable
    return _has_successful_tool(observations, tool_name)


def _has_successful_algorithm_file_read(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    args: Mapping[str, Any],
) -> bool:
    requested_path = _normalized_algorithm_read_path(args.get("file_path"))
    if not requested_path:
        return False
    requested_max_chars = _requested_algorithm_read_max_chars(args)
    for observation in observations:
        if (
            observation.is_error
            or observation.tool_name != "context.read_algorithm_file"
        ):
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        observed_path = _normalized_algorithm_read_path(payload.get("file_path"))
        if observed_path != requested_path:
            continue
        if _algorithm_payload_satisfies_read_request(
            payload,
            requested_max_chars=requested_max_chars,
        ):
            return True
    return False


def _has_successful_algorithm_symbol_read(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    args: Mapping[str, Any],
) -> bool:
    requested_path = _normalized_algorithm_read_path(args.get("file_path"))
    requested_symbol = str(args.get("symbol") or "").strip()
    if not requested_path or not requested_symbol:
        return False
    requested_max_chars = _requested_algorithm_read_max_chars(args)
    for observation in observations:
        if (
            observation.is_error
            or observation.tool_name != "context.read_algorithm_symbol"
        ):
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        observed_path = _normalized_algorithm_read_path(payload.get("file_path"))
        observed_symbol = str(payload.get("symbol") or "").strip()
        if observed_path != requested_path or observed_symbol != requested_symbol:
            continue
        if _algorithm_payload_satisfies_read_request(
            payload,
            requested_max_chars=requested_max_chars,
        ):
            return True
    return False


def _has_successful_active_map_target_read(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    tool_name: str,
    args: Mapping[str, Any],
    *,
    id_key: str,
) -> bool:
    requested_id = str(args.get(id_key) or "").strip()
    if not requested_id:
        return False
    for observation in observations:
        if observation.is_error or observation.tool_name != tool_name:
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        if str(payload.get(id_key) or "").strip() == requested_id:
            return True
    return False


def _normalized_algorithm_read_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").lstrip("/").strip()


def _requested_algorithm_read_max_chars(args: Mapping[str, Any]) -> int:
    parsed = _coerce_nonnegative_int(args.get("max_chars"))
    if parsed is None:
        return _ACTIVE_SOLVER_READ_DEFAULT_MAX_CHARS
    return parsed


def _algorithm_payload_satisfies_read_request(
    payload: Mapping[str, Any],
    *,
    requested_max_chars: int,
) -> bool:
    if payload.get("readable") is not True:
        return False
    if payload.get("already_observed"):
        coverage = payload.get("coverage")
        if isinstance(coverage, Mapping):
            observed_max = _coerce_nonnegative_int(coverage.get("max_chars"))
            preview_chars = _coerce_nonnegative_int(
                coverage.get("content_preview_chars")
            )
            size_chars = _coerce_nonnegative_int(coverage.get("size_chars"))
            truncated = bool(coverage.get("truncated"))
            if requested_max_chars <= 0:
                return True
            if (
                not truncated
                and size_chars is not None
                and preview_chars is not None
                and preview_chars >= min(size_chars, requested_max_chars)
            ):
                return True
            if observed_max is not None and requested_max_chars <= observed_max and not truncated:
                return True
        max_chars = _coerce_nonnegative_int(payload.get("max_chars"))
        return bool(max_chars is not None and requested_max_chars <= max_chars)
    if bool(payload.get("truncated")):
        return False
    observed_max_chars = _coerce_nonnegative_int(payload.get("max_chars"))
    if observed_max_chars is not None and requested_max_chars > observed_max_chars:
        return False
    content_preview = payload.get("content_preview")
    if content_preview is None:
        return requested_max_chars <= 0
    preview_chars = len(str(content_preview))
    size_chars = _coerce_nonnegative_int(payload.get("size_chars"))
    if size_chars is not None:
        required_preview_chars = min(size_chars, requested_max_chars)
        return preview_chars >= required_preview_chars
    if observed_max_chars is not None:
        required_preview_chars = min(observed_max_chars, requested_max_chars)
        return preview_chars >= required_preview_chars
    if not bool(payload.get("compacted_for_agentic_budget")):
        return True
    return preview_chars >= requested_max_chars


def _successful_algorithm_file_read_paths(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    *,
    count_already_observed: bool = True,
) -> list[str]:
    paths: list[str] = []
    for observation in observations:
        if observation.is_error or observation.tool_name != "context.read_algorithm_file":
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        if (
            not count_already_observed
            and (
                observation.observation_type == "already_observed"
                or payload.get("already_observed")
            )
        ):
            continue
        path = _normalized_algorithm_read_path(payload.get("file_path"))
        if path and path not in paths:
            paths.append(path)
    return paths


def _has_code_phase_surface_read(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    hypothesis: HypothesisProposal,
    *,
    surface: str | None = None,
    target_file: str | None = None,
) -> bool:
    expected_surface = str(surface or hypothesis.change_locus or "").strip()
    expected_target = str(target_file or hypothesis.target_file or "").strip()
    if not expected_surface:
        return False
    for observation in observations:
        if observation.is_error or observation.tool_name != "context.read_surface":
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        observed_surface = payload.get("surface")
        if not (
            isinstance(observed_surface, Mapping)
            and observed_surface.get("name") == expected_surface
        ):
            continue
        if str(payload.get("detail") or "") != "full":
            continue
        observed_target = str(payload.get("target_file") or "").strip()
        if expected_target and observed_target and observed_target != expected_target:
            continue
        artifact = payload.get("current_artifact")
        if not isinstance(artifact, Mapping):
            return True
        if not bool(artifact.get("readable", True)):
            continue
        try:
            max_chars = int(artifact.get("max_chars") or 0)
        except (TypeError, ValueError):
            max_chars = 0
        required_chars = _APS_CODE_SURFACE_READ_CODE_CHARS
        if max_chars >= required_chars or not artifact.get("truncated"):
            return True
    return False


def _coerce_nonnegative_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except Exception:
        return None
    return parsed if parsed >= 0 else None
