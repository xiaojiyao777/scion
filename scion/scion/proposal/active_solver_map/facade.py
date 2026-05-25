"""Provider facade for problem-generic active solver map reads."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from typing import Any, Mapping

from pydantic import BaseModel, ValidationError

from scion.problem.providers import (
    ProblemProviderError,
    resolve_active_solver_map_provider,
)
from scion.proposal.active_solver_map.models import (
    ActiveSolverMap,
    AlgorithmSliceReadResult,
    OperatorRegistryReadResult,
    ReadReceipt,
    SourcePolicyReceipt,
    UnavailableReason,
    model_payload,
)

_MAP_TOOL_NAME = "context.read_active_solver_map"
_REGISTRY_TOOL_NAME = "context.read_operator_registry"
_SLICE_TOOL_NAME = "context.read_algorithm_slice"


def read_active_solver_map_payload(
    context: Any,
    *,
    surface: str | None = None,
    subject_id: str | None = None,
) -> dict[str, Any]:
    provider = _active_solver_map_provider(context)
    hook = "active_solver_map_provider.read_active_solver_map"
    if provider is None:
        return _unavailable_payload(
            tool_name=_MAP_TOOL_NAME,
            surface=surface,
            subject_id=subject_id,
            target_id=subject_id,
            reason="active_solver_map_provider_unavailable",
            provider_hook=hook,
        )
    method = getattr(provider, "read_active_solver_map", None)
    if not callable(method):
        return _unavailable_payload(
            tool_name=_MAP_TOOL_NAME,
            surface=surface,
            subject_id=subject_id,
            target_id=subject_id,
            reason="active_solver_map_method_unavailable",
            provider_hook=hook,
        )
    try:
        raw_payload = method(context, surface=surface, subject_id=subject_id)
    except Exception:
        return _unavailable_payload(
            tool_name=_MAP_TOOL_NAME,
            surface=surface,
            subject_id=subject_id,
            target_id=subject_id,
            reason="active_solver_map_provider_exception",
            provider_hook=hook,
        )
    payload = _as_mapping(raw_payload)
    if payload is None:
        return _unavailable_payload(
            tool_name=_MAP_TOOL_NAME,
            surface=surface,
            subject_id=subject_id,
            target_id=subject_id,
            reason="active_solver_map_payload_not_mapping",
            provider_hook=hook,
        )
    payload.setdefault("surface", _clean(surface))
    payload.setdefault("subject_id", _clean(subject_id) or _clean(surface))
    payload.setdefault("snapshot_digest", _digest_payload(payload))
    try:
        solver_map = ActiveSolverMap.model_validate(payload)
    except ValidationError:
        return _unavailable_payload(
            tool_name=_MAP_TOOL_NAME,
            surface=surface,
            subject_id=subject_id,
            target_id=subject_id,
            reason="active_solver_map_payload_invalid",
            provider_hook=hook,
        )
    result = model_payload(solver_map)
    result["available"] = True
    result["read_receipt"] = _read_receipt(
        tool_name=_MAP_TOOL_NAME,
        payload=result,
        surface=result.get("surface"),
        subject_id=result.get("subject_id"),
        target_id=result.get("subject_id"),
        snapshot_digest=result.get("snapshot_digest"),
        available=True,
    )
    return result


def read_operator_registry_payload(
    context: Any,
    *,
    registry_id: str,
    surface: str | None = None,
    subject_id: str | None = None,
) -> dict[str, Any]:
    registry_id = _clean(registry_id)
    provider = _active_solver_map_provider(context)
    hook = "active_solver_map_provider.read_operator_registry"
    if provider is not None:
        method = getattr(provider, "read_operator_registry", None)
        if callable(method):
            try:
                raw_payload = method(
                    context,
                    registry_id=registry_id,
                    surface=surface,
                    subject_id=subject_id,
                )
            except Exception:
                return _unavailable_payload(
                    tool_name=_REGISTRY_TOOL_NAME,
                    surface=surface,
                    subject_id=subject_id,
                    target_id=registry_id,
                    reason="operator_registry_provider_exception",
                    provider_hook=hook,
                )
            payload = _as_mapping(raw_payload)
            if payload is not None:
                normalized = _operator_registry_payload_from_mapping(
                    payload,
                    registry_id=registry_id,
                    surface=surface,
                    subject_id=subject_id,
                )
                if normalized is not None:
                    return _with_receipt(
                        _REGISTRY_TOOL_NAME,
                        normalized,
                        target_id=registry_id,
                    )
                return _unavailable_payload(
                    tool_name=_REGISTRY_TOOL_NAME,
                    surface=surface,
                    subject_id=subject_id,
                    target_id=registry_id,
                    reason="operator_registry_payload_invalid",
                    provider_hook=hook,
                )
    map_payload = read_active_solver_map_payload(
        context,
        surface=surface,
        subject_id=subject_id,
    )
    if not map_payload.get("available"):
        return _unavailable_payload(
            tool_name=_REGISTRY_TOOL_NAME,
            surface=surface,
            subject_id=subject_id,
            target_id=registry_id,
            reason="active_solver_map_unavailable",
            provider_hook=hook,
        )
    try:
        solver_map = ActiveSolverMap.model_validate(
            _active_solver_map_schema_payload(map_payload)
        )
    except ValidationError:
        return _unavailable_payload(
            tool_name=_REGISTRY_TOOL_NAME,
            surface=surface,
            subject_id=subject_id,
            target_id=registry_id,
            reason="active_solver_map_payload_invalid",
            provider_hook=hook,
        )
    for registry in solver_map.operator_registries:
        if registry.registry_id != registry_id:
            continue
        result = OperatorRegistryReadResult(
            registry_id=registry.registry_id,
            surface=solver_map.surface,
            subject_id=solver_map.subject_id,
            snapshot_digest=solver_map.snapshot_digest,
            owner_file=registry.owner_file,
            owner_symbol=registry.owner_symbol,
            registry_kind=registry.registry_kind,
            operators=registry.operators,
            integration_points=(),
        ).model_dump(mode="json")
        result["available"] = True
        return _with_receipt(_REGISTRY_TOOL_NAME, result, target_id=registry_id)
    return _unavailable_payload(
        tool_name=_REGISTRY_TOOL_NAME,
        surface=solver_map.surface or surface,
        subject_id=solver_map.subject_id or subject_id,
        target_id=registry_id,
        snapshot_digest=solver_map.snapshot_digest,
        reason="operator_registry_not_found",
        provider_hook=hook,
    )


def read_algorithm_slice_payload(
    context: Any,
    *,
    slice_id: str,
    surface: str | None = None,
    subject_id: str | None = None,
    max_chars: int | None = None,
) -> dict[str, Any]:
    slice_id = _clean(slice_id)
    provider = _active_solver_map_provider(context)
    hook = "active_solver_map_provider.read_algorithm_slice"
    if provider is not None:
        method = getattr(provider, "read_algorithm_slice", None)
        if callable(method):
            try:
                raw_payload = method(
                    context,
                    slice_id=slice_id,
                    surface=surface,
                    subject_id=subject_id,
                    max_chars=max_chars,
                )
            except Exception:
                return _unavailable_payload(
                    tool_name=_SLICE_TOOL_NAME,
                    surface=surface,
                    subject_id=subject_id,
                    target_id=slice_id,
                    reason="algorithm_slice_provider_exception",
                    provider_hook=hook,
                )
            payload = _as_mapping(raw_payload)
            if payload is not None:
                normalized = _algorithm_slice_payload_from_mapping(
                    payload,
                    slice_id=slice_id,
                    surface=surface,
                    subject_id=subject_id,
                    max_chars=max_chars,
                )
                if normalized is not None:
                    return _with_receipt(
                        _SLICE_TOOL_NAME,
                        normalized,
                        target_id=slice_id,
                        content_digest=normalized.get("content_digest"),
                    )
                return _unavailable_payload(
                    tool_name=_SLICE_TOOL_NAME,
                    surface=surface,
                    subject_id=subject_id,
                    target_id=slice_id,
                    reason="algorithm_slice_payload_invalid",
                    provider_hook=hook,
                )
    map_payload = read_active_solver_map_payload(
        context,
        surface=surface,
        subject_id=subject_id,
    )
    if not map_payload.get("available"):
        return _unavailable_payload(
            tool_name=_SLICE_TOOL_NAME,
            surface=surface,
            subject_id=subject_id,
            target_id=slice_id,
            reason="active_solver_map_unavailable",
            provider_hook=hook,
        )
    try:
        solver_map = ActiveSolverMap.model_validate(
            _active_solver_map_schema_payload(map_payload)
        )
    except ValidationError:
        return _unavailable_payload(
            tool_name=_SLICE_TOOL_NAME,
            surface=surface,
            subject_id=subject_id,
            target_id=slice_id,
            reason="active_solver_map_payload_invalid",
            provider_hook=hook,
        )
    for slice_ref in solver_map.algorithm_slices:
        if slice_ref.slice_id != slice_id:
            continue
        result = AlgorithmSliceReadResult(
            slice_id=slice_ref.slice_id,
            surface=solver_map.surface,
            subject_id=solver_map.subject_id,
            snapshot_digest=solver_map.snapshot_digest,
            file_path=slice_ref.file_path,
            symbols=slice_ref.symbols,
            slice_kind=slice_ref.exposure_level,
            content="",
            content_digest="",
            token_estimate=slice_ref.token_estimate,
            why_visible=slice_ref.purpose,
            source_policy_receipt=SourcePolicyReceipt(
                allowed=False,
                reason="slice content requires provider read_algorithm_slice hook",
                remaining_budget=0,
            ),
            max_chars=max_chars,
        ).model_dump(mode="json")
        return _unavailable_result(
            tool_name=_SLICE_TOOL_NAME,
            payload=result,
            target_id=slice_id,
            reason="algorithm_slice_content_unavailable",
            provider_hook=hook,
        )
    return _unavailable_payload(
        tool_name=_SLICE_TOOL_NAME,
        surface=solver_map.surface or surface,
        subject_id=solver_map.subject_id or subject_id,
        target_id=slice_id,
        snapshot_digest=solver_map.snapshot_digest,
        reason="algorithm_slice_not_found",
        provider_hook=hook,
    )


def _active_solver_map_provider(context: Any) -> Any | None:
    try:
        return resolve_active_solver_map_provider(
            problem_spec=getattr(context, "problem_spec", None),
            adapter=getattr(context, "adapter", None),
        )
    except ProblemProviderError:
        return None


def _operator_registry_payload_from_mapping(
    payload: Mapping[str, Any],
    *,
    registry_id: str,
    surface: str | None,
    subject_id: str | None,
) -> dict[str, Any] | None:
    normalized = dict(payload)
    normalized.setdefault("registry_id", registry_id)
    normalized.setdefault("surface", _clean(surface))
    normalized.setdefault("subject_id", _clean(subject_id))
    normalized.setdefault("snapshot_digest", _digest_payload(normalized))
    if "owner_file" not in normalized and "owner_symbol" not in normalized:
        registry = normalized.get("registry")
        if isinstance(registry, Mapping):
            normalized = {**dict(registry), **normalized}
            normalized.pop("registry", None)
    try:
        model = OperatorRegistryReadResult.model_validate(normalized)
    except ValidationError:
        return None
    result = model.model_dump(mode="json")
    result["available"] = True
    return result


def _algorithm_slice_payload_from_mapping(
    payload: Mapping[str, Any],
    *,
    slice_id: str,
    surface: str | None,
    subject_id: str | None,
    max_chars: int | None,
) -> dict[str, Any] | None:
    normalized = dict(payload)
    normalized.setdefault("slice_id", slice_id)
    normalized.setdefault("surface", _clean(surface))
    normalized.setdefault("subject_id", _clean(subject_id))
    normalized.setdefault("snapshot_digest", _digest_payload(normalized))
    content = str(normalized.get("content") or "")
    truncated = False
    if max_chars is not None:
        max_chars = max(0, int(max_chars))
        if len(content) > max_chars:
            content = content[:max_chars]
            truncated = True
    normalized["content"] = content
    normalized["content_digest"] = _sha256(content)
    normalized["truncated"] = bool(normalized.get("truncated")) or truncated
    normalized["max_chars"] = max_chars
    if "source_policy_receipt" not in normalized:
        normalized["source_policy_receipt"] = {
            "allowed": True,
            "reason": "provider_returned_algorithm_slice",
            "remaining_budget": 0,
        }
    try:
        model = AlgorithmSliceReadResult.model_validate(normalized)
    except ValidationError:
        return None
    result = model.model_dump(mode="json")
    result["available"] = True
    return result


def _unavailable_payload(
    *,
    tool_name: str,
    surface: str | None,
    subject_id: str | None,
    target_id: str | None,
    reason: str,
    provider_hook: str,
    snapshot_digest: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "available": False,
        "surface": _clean(surface),
        "subject_id": _clean(subject_id),
        "snapshot_digest": _clean(snapshot_digest),
        "unavailable": UnavailableReason(
            reason=reason,
            provider_hook=provider_hook,
        ).model_dump(mode="json"),
    }
    payload["read_receipt"] = _read_receipt(
        tool_name=tool_name,
        payload=payload,
        surface=surface,
        subject_id=subject_id,
        target_id=target_id,
        snapshot_digest=snapshot_digest,
        available=False,
    )
    return payload


def _unavailable_result(
    *,
    tool_name: str,
    payload: dict[str, Any],
    target_id: str,
    reason: str,
    provider_hook: str,
) -> dict[str, Any]:
    result = dict(payload)
    result["available"] = False
    result["unavailable"] = UnavailableReason(
        reason=reason,
        provider_hook=provider_hook,
    ).model_dump(mode="json")
    result["read_receipt"] = _read_receipt(
        tool_name=tool_name,
        payload=result,
        surface=result.get("surface"),
        subject_id=result.get("subject_id"),
        target_id=target_id,
        snapshot_digest=result.get("snapshot_digest"),
        content_digest=result.get("content_digest"),
        available=False,
    )
    return result


def _with_receipt(
    tool_name: str,
    payload: dict[str, Any],
    *,
    target_id: str,
    content_digest: str | None = None,
) -> dict[str, Any]:
    result = dict(payload)
    result["read_receipt"] = _read_receipt(
        tool_name=tool_name,
        payload=result,
        surface=result.get("surface"),
        subject_id=result.get("subject_id"),
        target_id=target_id,
        snapshot_digest=result.get("snapshot_digest"),
        content_digest=content_digest,
        available=bool(result.get("available", True)),
    )
    return result


def _active_solver_map_schema_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if key not in {"available", "read_receipt", "unavailable"}
    }


def _read_receipt(
    *,
    tool_name: str,
    payload: Mapping[str, Any],
    surface: Any,
    subject_id: Any,
    target_id: Any,
    snapshot_digest: Any,
    available: bool,
    content_digest: str | None = None,
) -> dict[str, Any]:
    digest = _digest_payload(
        {key: value for key, value in payload.items() if key != "read_receipt"}
    )
    return ReadReceipt(
        tool_name=tool_name,
        surface=_clean(surface),
        subject_id=_clean(subject_id),
        target_id=_clean(target_id),
        snapshot_digest=_clean(snapshot_digest),
        digest=digest,
        content_digest=content_digest,
        available=available,
    ).model_dump(mode="json")


def _as_mapping(value: Any) -> dict[str, Any] | None:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Mapping):
        return dict(value)
    return None


def _digest_payload(payload: Mapping[str, Any]) -> str:
    return _sha256(
        json.dumps(
            _json_ready(payload),
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    )


def _json_ready(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return _json_ready(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _clean(value: Any) -> str:
    return str(value or "").strip()


__all__ = [
    "read_active_solver_map_payload",
    "read_algorithm_slice_payload",
    "read_operator_registry_payload",
]
