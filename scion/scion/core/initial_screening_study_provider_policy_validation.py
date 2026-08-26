"""Pre-run validation for the private initial-screening provider policy."""

from __future__ import annotations

import os
import weakref
from dataclasses import dataclass
from types import MethodType
from typing import Any, cast

from scion.core.evidence_recording import EvidenceRecorder
from scion.core.initial_screening_study_controls_io import (
    _ControlsPublication,
    _validate_absent_private_child,
    _validate_attached_control_publication,
)
from scion.core.initial_screening_study_provider_policy import (
    _ERROR,
    _FILENAME,
    _MAX_BYTES,
    _REGISTERED_OWNERS,
    _InitialScreeningProviderPolicyError,
    _InitialScreeningProviderPolicyInputs,
    _provider_payload_bytes,
    _ProviderPolicyPublication,
    _RegisteredProviderPolicyBaseline,
    _validate_provider_projection_source,
)
from scion.core.resource_envelope import ProviderCallBudget
from scion.proposal.engine import CreativeLayer
from scion.proposal.engine.provider_call import ProviderCaller
from scion.proposal.llm.client import LLMClient


@dataclass(frozen=True, repr=False)
class _ProviderPolicyRunState:
    runtime_inputs: _InitialScreeningProviderPolicyInputs
    baseline: _RegisteredProviderPolicyBaseline

    def __repr__(self) -> str:
        return "_ProviderPolicyRunState(<redacted>)"

    __str__ = __repr__


def _prepare_provider_policy_run_validation(
    owner: Any,
) -> _ProviderPolicyRunState | None:
    """Perform only pure shape and identity checks before either leaf rewalk."""

    failed = False
    result: _ProviderPolicyRunState | None = None
    try:
        result = _prepare_provider_policy_run_validation_unchecked(owner)
    except Exception:  # noqa: BLE001 - expose only the fixed private error
        failed = True
    if failed:
        raise _InitialScreeningProviderPolicyError(_ERROR)
    return result


def _prepare_provider_policy_run_validation_unchecked(
    owner: Any,
) -> _ProviderPolicyRunState | None:
    from scion.core.initial_screening_study_controls_validation import (
        _campaign_owner_storage,
    )

    storage = _campaign_owner_storage(owner)
    marker_keys = {
        "_initial_screening_provider_policy_active",
        "_initial_screening_provider_policy",
    }
    if type(_REGISTERED_OWNERS) is not weakref.WeakKeyDictionary:
        raise TypeError
    present = marker_keys.intersection(storage)
    from scion.core.campaign import CampaignManager

    if type(owner) is not CampaignManager:
        if present or _owner_identity_is_registered(owner):
            raise TypeError
        return None
    if not present:
        _validate_no_provider_capsule(storage)
        if not _owner_identity_is_registered(owner):
            return None
        raise TypeError
    if present != marker_keys:
        raise TypeError
    baseline = weakref.WeakKeyDictionary.get(_REGISTERED_OWNERS, owner)
    active = storage["_initial_screening_provider_policy_active"]
    runtime_inputs = storage["_initial_screening_provider_policy"]
    _validate_baseline_shape(baseline)
    baseline_value = cast(_RegisteredProviderPolicyBaseline, baseline)
    registered = baseline_value.runtime_inputs_ref()
    if (
        active is not True
        or type(runtime_inputs) is not _InitialScreeningProviderPolicyInputs
        or runtime_inputs is not registered
    ):
        raise ValueError
    _validate_runtime_shape(runtime_inputs)
    _validate_provider_projection_source(runtime_inputs.capsule)
    _validate_client_structural_shape(runtime_inputs.client, runtime_inputs.capsule)
    from scion.proposal.llm.study_policy import (
        _validate_frozen_llm_client_shape,
        _validate_frozen_study_provider_policy_shape,
    )

    _validate_frozen_study_provider_policy_shape(runtime_inputs.capsule)
    _validate_frozen_llm_client_shape(runtime_inputs.client, runtime_inputs.capsule)
    publication = runtime_inputs.publication
    if type(publication) is not _ProviderPolicyPublication:
        raise TypeError
    if (
        baseline_value.client_ref() is not runtime_inputs.client
        or baseline_value.capsule_ref() is not runtime_inputs.capsule
        or runtime_inputs.payload_bytes != baseline_value.payload_bytes
        or publication.campaign_dir != baseline_value.campaign_dir
        or publication.directory_fingerprints != baseline_value.directory_fingerprints
        or publication.leaf_fingerprint != baseline_value.leaf_fingerprint
    ):
        raise ValueError
    _validate_direct_consumer_shape(storage, runtime_inputs)
    return _ProviderPolicyRunState(runtime_inputs, baseline_value)


def _validate_no_provider_capsule(storage: dict[str, Any]) -> None:
    """Reject a later-installed capsule on any direct no-marker client seam."""

    from scion.proposal.llm.study_policy import (
        _has_literal_initial_screening_study_policy_capsule,
    )

    for client in _no_provider_client_candidates(storage):
        if _has_literal_initial_screening_study_policy_capsule(client):
            raise ValueError


def _no_provider_client_candidates(storage: dict[str, Any]) -> tuple[Any, ...]:
    candidates = [storage.get("_llm_client")]
    creative = storage.get("_creative")
    if type(creative) is not CreativeLayer:
        return tuple(candidates)
    creative_storage = vars(creative)
    candidates.append(_raw_exact_storage_value(creative_storage, "_client"))
    provider_calls = _raw_exact_storage_value(creative_storage, "_provider_calls")
    if type(provider_calls) is not ProviderCaller:
        return tuple(candidates)
    caller_storage = vars(provider_calls)
    candidates.append(_raw_exact_storage_value(caller_storage, "_client"))
    return tuple(candidates)


def _raw_exact_storage_value(value: Any, name: str) -> Any:
    if not isinstance(value, dict):
        return None
    for key, item in dict.items(value):
        if type(key) is str and key == name:
            return item
    return None


def _validate_provider_policy_publication(
    state: _ProviderPolicyRunState,
    controls_publication: _ControlsPublication,
) -> None:
    """Rewalk the provider leaf and require the future trace target absent."""

    failed = False
    try:
        if type(state) is not _ProviderPolicyRunState:
            raise TypeError
        runtime_inputs = state.runtime_inputs
        publication = runtime_inputs.publication
        from scion.core.initial_screening_study_controls import (
            _FILENAME as _CONTROLS_FILENAME,
        )

        if (
            type(publication) is not _ProviderPolicyPublication
            or type(controls_publication) is not _ControlsPublication
            or publication.campaign_dir != controls_publication.campaign_dir
            or publication.directory_fingerprints
            != controls_publication.directory_fingerprints
        ):
            raise ValueError
        _validate_attached_control_publication(
            controls_publication,
            state.baseline.payload_bytes,
            state.baseline.leaf_fingerprint,
            filename=_FILENAME,
            first_filename=_CONTROLS_FILENAME,
            require_only_control_leaves=False,
            max_bytes=_MAX_BYTES,
        )
        _validate_absent_private_child(controls_publication, "llm_traces")
    except Exception:  # noqa: BLE001 - expose only the fixed private error
        failed = True
    if failed:
        raise _InitialScreeningProviderPolicyError(_ERROR)


def _validate_provider_policy_installed_runtime(
    state: _ProviderPolicyRunState,
    owner: Any,
) -> None:
    """Join the frozen payload to the exact pristine direct consumers."""

    failed = False
    try:
        _validate_provider_policy_installed_runtime_unchecked(state, owner)
    except Exception:  # noqa: BLE001 - expose only the fixed private error
        failed = True
    if failed:
        raise _InitialScreeningProviderPolicyError(_ERROR)


def _validate_provider_policy_installed_runtime_unchecked(
    state: _ProviderPolicyRunState,
    owner: Any,
) -> None:
    from scion.core.initial_screening_study_controls_validation import (
        _campaign_owner_storage,
    )
    from scion.proposal.llm.study_policy import (
        _validate_frozen_llm_client_shape,
        _validate_frozen_study_provider_policy_shape,
    )

    if type(state) is not _ProviderPolicyRunState:
        raise TypeError
    runtime_inputs = state.runtime_inputs
    baseline = state.baseline
    storage = _campaign_owner_storage(owner)
    client = runtime_inputs.client
    capsule = runtime_inputs.capsule
    _validate_frozen_study_provider_policy_shape(capsule)
    _validate_frozen_llm_client_shape(client, capsule)
    if (
        _provider_payload_bytes(capsule) != baseline.payload_bytes
        or type(storage.get("_campaign_dir")) is not str
        or storage["_campaign_dir"] != baseline.campaign_dir
    ):
        raise ValueError
    creative = storage["_creative"]
    provider_calls = vars(creative)["_provider_calls"]
    evidence_recorder = storage["_evidence_recorder"]
    if (
        storage["_llm_client"] is not client
        or creative._client is not client
        or provider_calls._client is not client
        or creative._model is not provider_calls._model
        or creative._model != capsule.requested_model
        or provider_calls._model != capsule.requested_model
        or client.model != capsule.requested_model
        or evidence_recorder.model_id != capsule.requested_model
        or provider_calls._provider_call_budget is not storage["_provider_call_budget"]
        or provider_calls._trace_dir
        != os.path.join(baseline.campaign_dir, "llm_traces")
        or client._anthropic_client is not None
        or client._openai_client is not None
        or client._last_usage_metadata is not None
        or client._last_response_diagnostics is not None
    ):
        raise ValueError


def _validate_baseline_shape(value: Any) -> None:
    if type(value) is not _RegisteredProviderPolicyBaseline:
        raise TypeError
    storage = vars(value)
    expected = {
        "runtime_inputs_ref",
        "client_ref",
        "capsule_ref",
        "payload_bytes",
        "campaign_dir",
        "directory_fingerprints",
        "leaf_fingerprint",
    }
    _validate_storage(storage, expected)
    if (
        type(value.runtime_inputs_ref) is not weakref.ReferenceType
        or type(value.client_ref) is not weakref.ReferenceType
        or type(value.capsule_ref) is not weakref.ReferenceType
        or type(value.payload_bytes) is not bytes
        or type(value.campaign_dir) is not str
        or not _is_directory_fingerprint(value.directory_fingerprints)
        or not _is_int_tuple(value.leaf_fingerprint, 4)
    ):
        raise TypeError


def _validate_runtime_shape(value: Any) -> None:
    if type(value) is not _InitialScreeningProviderPolicyInputs:
        raise TypeError
    storage = vars(value)
    _validate_storage(storage, {"client", "capsule", "payload_bytes", "publication"})
    if type(value.payload_bytes) is not bytes:
        raise TypeError
    publication = value.publication
    if type(publication) is not _ProviderPolicyPublication:
        raise TypeError
    publication_storage = vars(publication)
    _validate_storage(
        publication_storage,
        {"campaign_dir", "directory_fingerprints", "leaf_fingerprint"},
    )
    if (
        type(publication.campaign_dir) is not str
        or not _is_directory_fingerprint(publication.directory_fingerprints)
        or not _is_int_tuple(publication.leaf_fingerprint, 4)
    ):
        raise TypeError


def _validate_direct_consumer_shape(
    storage: dict[str, Any],
    runtime_inputs: _InitialScreeningProviderPolicyInputs,
) -> None:
    required = {
        "_llm_client",
        "_creative",
        "_provider_call_budget",
        "_campaign_dir",
        "_evidence_recorder",
    }
    if not required.issubset(storage):
        raise TypeError
    client = storage["_llm_client"]
    creative = storage["_creative"]
    budget = storage["_provider_call_budget"]
    evidence_recorder = storage["_evidence_recorder"]
    if (
        type(client) is not LLMClient
        or type(creative) is not CreativeLayer
        or type(budget) is not ProviderCallBudget
        or type(evidence_recorder) is not EvidenceRecorder
        or type(storage["_campaign_dir"]) is not str
        or client is not runtime_inputs.client
    ):
        raise TypeError
    evidence_storage = vars(evidence_recorder)
    if (
        type(evidence_storage) is not dict
        or any(type(key) is not str for key in evidence_storage)
        or "model_id" not in evidence_storage
        or type(evidence_storage["model_id"]) is not str
    ):
        raise TypeError
    _validate_storage(vars(creative), {"_client", "_model", "_provider_calls"})
    provider_calls = vars(creative)["_provider_calls"]
    if type(provider_calls) is not ProviderCaller:
        raise TypeError
    _validate_storage(
        vars(provider_calls),
        {"_client", "_model", "_trace_dir", "_provider_call_budget"},
    )
    if (
        type(creative._model) is not str
        or type(provider_calls._model) is not str
        or type(provider_calls._trace_dir) is not str
        or creative._client is not client
        or provider_calls._client is not client
        or provider_calls._provider_call_budget is not budget
    ):
        raise TypeError
    if not _has_exact_methods(
        creative,
        CreativeLayer,
        (
            "generate_direct_hypothesis",
            "generate_direct_code",
            "call_code_research_turn",
            "call_hypothesis_research_turn",
            "call_code_research_finalize",
        ),
    ) or not _has_exact_methods(
        provider_calls,
        ProviderCaller,
        ("call", "_call_provider"),
    ):
        raise TypeError


def _validate_client_structural_shape(client: Any, capsule: Any) -> None:
    from scion.proposal.llm.study_policy import _CAPSULE_ATTRIBUTE

    if type(client) is not LLMClient:
        raise TypeError
    storage = vars(client)
    keys = {
        "model",
        "reasoning_effort",
        "api_key",
        "base_url",
        "timeout_sec",
        "_last_usage_metadata",
        "_last_response_diagnostics",
        "_anthropic_client",
        "_openai_client",
        _CAPSULE_ATTRIBUTE,
    }
    _validate_storage(storage, keys)
    if (
        type(storage["model"]) is not str
        or type(storage["reasoning_effort"]) is not str
        or type(storage["api_key"]) is not str
        or type(storage["base_url"]) is not str
        or type(storage["timeout_sec"]) is not float
        or storage[_CAPSULE_ATTRIBUTE] is not capsule
        or storage["_last_usage_metadata"] is not None
        or storage["_last_response_diagnostics"] is not None
        or storage["_anthropic_client"] is not None
        or storage["_openai_client"] is not None
    ):
        raise TypeError
    if not _has_exact_methods(
        client,
        LLMClient,
        (
            "call_with_tool",
            "resolve_request_policy",
            "reset_call_observations",
            "_tool_call_once",
            "_tool_call_once_anthropic",
            "_tool_call_once_openai",
            "_openai_chat_kwargs",
            "_openai_reasoning_effort",
            "_openai_extra_body",
            "_get_anthropic_client",
            "_get_openai_client",
        ),
    ):
        raise TypeError


def _validate_storage(value: Any, expected: set[str]) -> None:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise TypeError
    if set(value) != expected:
        raise TypeError


def _owner_identity_is_registered(owner: Any) -> bool:
    references = weakref.WeakKeyDictionary.keyrefs(_REGISTERED_OWNERS)
    if type(references) is not list or any(
        type(reference) is not weakref.ReferenceType for reference in references
    ):
        raise TypeError
    return any(reference() is owner for reference in references)


def _is_int_tuple(value: Any, length: int) -> bool:
    return (
        type(value) is tuple
        and len(value) == length
        and all(type(item) is int for item in value)
    )


def _is_directory_fingerprint(value: Any) -> bool:
    return (
        type(value) is tuple
        and bool(value)
        and all(_is_int_tuple(item, 2) for item in value)
    )


def _has_exact_methods(
    instance: Any, expected_type: type, names: tuple[str, ...]
) -> bool:
    if type(instance) is not expected_type:
        return False
    storage = vars(instance)
    if type(storage) is not dict or any(type(key) is not str for key in storage):
        return False
    return all(
        name not in storage
        and type(getattr(instance, name, None)) is MethodType
        and getattr(instance, name).__self__ is instance
        and getattr(instance, name).__func__ is getattr(expected_type, name)
        for name in names
    )
