"""Private producer boundary for the initial-screening provider policy."""

from __future__ import annotations

import json
import math
import os
import weakref
from dataclasses import dataclass, replace
from types import MethodType
from typing import Any, cast

from scion.core.initial_screening_study_controls_io import _ControlsPublication

_ERROR = "INITIAL_SCREENING_PROVIDER_POLICY_UNAVAILABLE"
_FILENAME = "initial_screening_provider_policy.json"
_MAX_BYTES = 65_536
_SCHEMA_VERSION = "scion.initial_screening_provider_policy.v1"
_SCOPE = "REQUESTED_PROVIDER_POLICY_ONLY"
_LIMITATIONS = (
    "PROVIDER_CREDENTIAL_AND_ACCOUNT_IDENTITY_UNVERIFIED",
    "PROVIDER_PROCESS_NETWORK_TLS_ENVIRONMENT_UNVERIFIED",
    "REMOTE_PROVIDER_BACKEND_IDENTITY_UNVERIFIED",
    "PROVIDER_REQUEST_CODE_CONSTANTS_UNVERIFIED",
    "PROVIDER_TIMEOUT_AND_SDK_RETRY_ENFORCEMENT_UNVERIFIED",
    "LLM_CLIENT_LIFETIME_FRESHNESS_UNVERIFIED",
    "STUDY_MANIFEST_UNVERIFIED",
    "ROOT_LIFETIME_FRESHNESS_UNVERIFIED",
    "MATCHED_RESULT_UNAUTHORIZED",
    "LIVE_EXECUTION_UNAUTHORIZED",
    "STUDY_GO_UNAUTHORIZED",
)


class _Redacted:
    def __repr__(self) -> str:
        return f"{type(self).__name__}(<redacted>)"

    __str__ = __repr__


@dataclass(frozen=True, repr=False)
class _InitialScreeningProviderPolicyRequest(_Redacted):
    """Zero-value package-private opt-in marker."""


@dataclass(frozen=True, repr=False)
class _ProviderPolicyPublication(_Redacted):
    campaign_dir: str
    directory_fingerprints: tuple[tuple[int, int], ...]
    leaf_fingerprint: tuple[int, int, int, int]


@dataclass(frozen=True, repr=False)
class _InitialScreeningProviderPolicyInputs(_Redacted):
    client: Any
    capsule: Any
    payload_bytes: bytes
    publication: _ProviderPolicyPublication | None = None


@dataclass(frozen=True, repr=False)
class _RegisteredProviderPolicyBaseline(_Redacted):
    runtime_inputs_ref: weakref.ReferenceType[_InitialScreeningProviderPolicyInputs]
    client_ref: weakref.ReferenceType[Any]
    capsule_ref: weakref.ReferenceType[Any]
    payload_bytes: bytes
    campaign_dir: str
    directory_fingerprints: tuple[tuple[int, int], ...]
    leaf_fingerprint: tuple[int, int, int, int]


class _InitialScreeningProviderPolicyError(RuntimeError):
    """Body-free fixed failure at the package-private policy boundary."""


_REGISTERED_OWNERS: weakref.WeakKeyDictionary[
    Any, _RegisteredProviderPolicyBaseline
] = weakref.WeakKeyDictionary()


def _reject_reused_provider_client_without_marker(request: Any, client: Any) -> None:
    """Reject silent reuse of an already-installed study capsule."""

    if request is not None:
        return
    from scion.proposal.llm.client import LLMClient
    from scion.proposal.llm.study_policy import (
        _has_literal_initial_screening_study_policy_capsule,
    )

    if type(client) is not LLMClient:
        return
    if _has_literal_initial_screening_study_policy_capsule(client):
        raise _InitialScreeningProviderPolicyError(_ERROR)


def _canonical_json_bytes(value: dict[str, Any]) -> bytes:
    encoded = (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )
    if len(encoded) > _MAX_BYTES:
        raise ValueError
    return encoded


def _provider_payload_bytes(capsule: Any) -> bytes:
    _validate_provider_projection_source(capsule)
    client_projection = capsule.to_projection()
    policies = [entry.to_projection() for entry in capsule.request_policies]
    _validate_client_projection(client_projection)
    _validate_request_policy_projections(policies, client_projection)
    return _canonical_json_bytes(
        {
            "schema_version": _SCHEMA_VERSION,
            "scope": _SCOPE,
            "limitations": list(_LIMITATIONS),
            "client": client_projection,
            "request_policies": policies,
        }
    )


def _validate_provider_projection_source(capsule: Any) -> None:
    from scion.proposal.llm.study_policy import (
        _FrozenInitialScreeningStudyPolicy,
        _FrozenRequestBodyPolicy,
        _FrozenStudyRequestPolicy,
    )

    _validate_projection_source(
        capsule,
        _FrozenInitialScreeningStudyPolicy,
        _FrozenRequestBodyPolicy,
        _FrozenStudyRequestPolicy,
    )


def _validate_projection_source(
    capsule: Any,
    capsule_type: type,
    body_type: type,
    policy_type: type,
) -> None:
    capsule_keys = {
        "client_type",
        "requested_model",
        "configured_base_url",
        "effective_sdk_base_url",
        "provider_transport",
        "requested_reasoning_effort",
        "effective_reasoning_effort",
        "thinking_mode",
        "base_timeout_sec",
        "sdk_max_retries_requested",
        "request_body_policy",
        "request_policies",
    }
    if type(capsule) is not capsule_type:
        raise TypeError
    source = cast(Any, capsule)
    _validate_exact_storage(vars(source), capsule_keys)
    if not _is_exact_method(source.to_projection, source, capsule_type.to_projection):
        raise TypeError
    body = source.request_body_policy
    if type(body) is not body_type:
        raise TypeError
    body_value = cast(Any, body)
    _validate_exact_storage(
        vars(body_value),
        {"temperature", "top_p", "seed", "stream", "system_blocks", "tool_choice"},
    )
    if not _is_exact_method(
        body_value.to_projection,
        body_value,
        body_type.to_projection,
    ):
        raise TypeError
    policies = source.request_policies
    if type(policies) is not tuple or len(policies) != 5:
        raise TypeError
    policy_keys = {
        "request_kind",
        "tool_name",
        "timeout_sec",
        "provider",
        "output_token_policy",
        "output_token_parameter",
        "provider_transport_output_ceiling_tokens",
    }
    for entry in policies:
        if type(entry) is not policy_type:
            raise TypeError
        entry_value = cast(Any, entry)
        _validate_exact_storage(vars(entry_value), policy_keys)
        if not _is_exact_method(
            entry_value.to_projection,
            entry_value,
            policy_type.to_projection,
        ):
            raise TypeError


def _validate_client_projection(value: Any) -> None:
    from scion.proposal.llm.study_policy import (
        _canonical_base_url,
        _effective_sdk_base_url,
    )

    expected = {
        "client_type",
        "requested_model",
        "configured_base_url",
        "effective_sdk_base_url",
        "provider_transport",
        "requested_reasoning_effort",
        "effective_reasoning_effort",
        "thinking_mode",
        "base_timeout_sec",
        "sdk_max_retries_requested",
        "request_body_policy",
    }
    _validate_exact_storage(value, expected)
    string_keys = expected - {
        "base_timeout_sec",
        "sdk_max_retries_requested",
        "request_body_policy",
    }
    if any(type(value[key]) is not str for key in string_keys):
        raise TypeError
    model = value["requested_model"]
    if (
        value["client_type"] != "scion.proposal.llm.client.LLMClient"
        or not model
        or model != model.strip()
        or len(model.encode("utf-8")) > 256
        or any(ord(char) < 0x20 or ord(char) == 0x7F for char in model)
        or value["provider_transport"] not in {"anthropic", "openai_compatible"}
        or value["requested_reasoning_effort"]
        not in {"", "low", "medium", "high", "xhigh", "max"}
        or value["effective_reasoning_effort"]
        not in {"", "low", "medium", "high", "xhigh", "max"}
        or value["thinking_mode"] not in {"disabled", "enabled"}
        or type(value["base_timeout_sec"]) is not float
        or not math.isfinite(value["base_timeout_sec"])
        or value["base_timeout_sec"] <= 0.0
        or type(value["sdk_max_retries_requested"]) is not int
        or value["sdk_max_retries_requested"] != 0
    ):
        raise ValueError
    for key in ("configured_base_url", "effective_sdk_base_url"):
        url = value[key]
        if not url or len(url.encode("utf-8")) > 2048:
            raise ValueError
    configured = _canonical_base_url(value["configured_base_url"])
    if (
        configured != value["configured_base_url"]
        or _canonical_base_url(value["effective_sdk_base_url"])
        != value["effective_sdk_base_url"]
        or _effective_sdk_base_url(
            configured,
            provider=value["provider_transport"],
        )
        != value["effective_sdk_base_url"]
    ):
        raise ValueError
    body = value["request_body_policy"]
    _validate_exact_storage(
        body,
        {"temperature", "top_p", "seed", "stream", "system_blocks", "tool_choice"},
    )
    if any(type(item) is not str for item in body.values()):
        raise TypeError
    if any(
        body[key] != "omitted" for key in ("temperature", "top_p", "seed", "stream")
    ):
        raise ValueError
    provider = value["provider_transport"]
    deepseek = model.startswith("deepseek-")
    expected_system = (
        "native_system_blocks" if provider == "anthropic" else "merged_into_user_prompt"
    )
    expected_tool = (
        "required_named_tool"
        if provider == "anthropic"
        else "omitted"
        if deepseek
        else "required_named_function"
    )
    if body["system_blocks"] != expected_system or body["tool_choice"] != expected_tool:
        raise ValueError


def _validate_request_policy_projections(
    values: Any,
    client: dict[str, Any],
) -> None:
    if type(values) is not list or len(values) != 5:
        raise TypeError
    specs = (
        ("hypothesis", "generate_hypothesis"),
        ("hypothesis_research_turn", "hypothesis_research_turn"),
        ("code", "generate_patch"),
        ("code_research_turn", "code_research_turn"),
        ("code_research_finalize", "finalize_code_research"),
    )
    keys = {
        "request_kind",
        "tool_name",
        "timeout_sec",
        "provider",
        "output_token_policy",
        "output_token_parameter",
        "provider_transport_output_ceiling_tokens",
    }
    anthropic = client["provider_transport"] == "anthropic"
    for value, (kind, tool_name) in zip(values, specs):
        _validate_exact_storage(value, keys)
        if (
            type(value["request_kind"]) is not str
            or type(value["tool_name"]) is not str
            or type(value["timeout_sec"]) is not float
            or type(value["provider"]) is not str
            or type(value["output_token_policy"]) is not str
            or type(value["output_token_parameter"]) is not str
        ):
            raise TypeError
        ceiling = value["provider_transport_output_ceiling_tokens"]
        if ceiling is not None and (type(ceiling) is not int or ceiling <= 0):
            raise TypeError
        if (
            value["request_kind"] != kind
            or value["tool_name"] != tool_name
            or not math.isfinite(value["timeout_sec"])
            or value["timeout_sec"] <= 0.0
            or value["provider"] != client["provider_transport"]
            or value["output_token_policy"]
            != ("provider_native_required" if anthropic else "provider_managed")
            or value["output_token_parameter"]
            != ("max_tokens" if anthropic else "omitted")
            or ceiling != (16384 if anthropic else None)
        ):
            raise ValueError


def _validate_exact_storage(value: Any, expected: set[str]) -> None:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise TypeError
    if set(value) != expected:
        raise TypeError


def _is_exact_method(actual: Any, owner: Any, function: Any) -> bool:
    return (
        type(actual) is MethodType
        and actual.__self__ is owner
        and actual.__func__ is function
    )


def _prepare_initial_screening_provider_policy(
    request: Any,
    llm_client: Any,
) -> _InitialScreeningProviderPolicyInputs:
    """Freeze the exact requested policy before any filesystem operation."""

    failed = False
    result: _InitialScreeningProviderPolicyInputs | None = None
    try:
        if type(request) is not _InitialScreeningProviderPolicyRequest:
            raise TypeError
        request_storage = vars(request)
        if (
            type(request_storage) is not dict
            or any(type(key) is not str for key in request_storage)
            or request_storage
        ):
            raise TypeError
        from scion.proposal.llm.study_policy import (
            _freeze_initial_screening_study_policy,
        )

        frozen_client, capsule = _freeze_initial_screening_study_policy(llm_client)
        if frozen_client is not llm_client:
            raise TypeError
        result = _InitialScreeningProviderPolicyInputs(
            client=frozen_client,
            capsule=capsule,
            payload_bytes=_provider_payload_bytes(capsule),
        )
    except Exception:  # noqa: BLE001 - collapse private preparation failures
        failed = True
    if failed or result is None:
        raise _InitialScreeningProviderPolicyError(_ERROR)
    return result


def _publish_initial_screening_provider_policy(
    runtime_inputs: _InitialScreeningProviderPolicyInputs,
    controls_publication: _ControlsPublication,
) -> _InitialScreeningProviderPolicyInputs:
    """Attach the second private leaf to the fresh controls root."""

    failed = False
    result: _InitialScreeningProviderPolicyInputs | None = None
    try:
        if type(runtime_inputs) is not _InitialScreeningProviderPolicyInputs:
            raise TypeError
        if type(controls_publication) is not _ControlsPublication:
            raise TypeError
        if runtime_inputs.publication is not None:
            raise TypeError
        from scion.core.initial_screening_study_controls import (
            _FILENAME as _CONTROLS_FILENAME,
        )
        from scion.core.initial_screening_study_controls_io import (
            _publish_attached_control,
        )

        leaf_fingerprint = _publish_attached_control(
            controls_publication,
            runtime_inputs.payload_bytes,
            filename=_FILENAME,
            first_filename=_CONTROLS_FILENAME,
            max_bytes=_MAX_BYTES,
        )
        publication = _ProviderPolicyPublication(
            campaign_dir=controls_publication.campaign_dir,
            directory_fingerprints=controls_publication.directory_fingerprints,
            leaf_fingerprint=leaf_fingerprint,
        )
        result = replace(runtime_inputs, publication=publication)
    except Exception:  # noqa: BLE001 - collapse private publication failures
        failed = True
    if failed or result is None:
        raise _InitialScreeningProviderPolicyError(_ERROR)
    return result


def _register_initial_screening_provider_policy_owner(
    owner: Any,
    runtime_inputs: _InitialScreeningProviderPolicyInputs,
) -> None:
    """Register an owner-independent baseline after all consumers are installed."""

    if type(runtime_inputs) is not _InitialScreeningProviderPolicyInputs:
        raise _InitialScreeningProviderPolicyError(_ERROR)
    _validate_exact_storage(
        vars(runtime_inputs),
        {"client", "capsule", "payload_bytes", "publication"},
    )
    publication = runtime_inputs.publication
    if (
        type(publication) is not _ProviderPolicyPublication
        or type(runtime_inputs.payload_bytes) is not bytes
    ):
        raise _InitialScreeningProviderPolicyError(_ERROR)
    _validate_exact_storage(
        vars(publication),
        {"campaign_dir", "directory_fingerprints", "leaf_fingerprint"},
    )
    if (
        type(publication.campaign_dir) is not str
        or not _is_directory_fingerprint(publication.directory_fingerprints)
        or not _is_int_tuple(publication.leaf_fingerprint, 4)
    ):
        raise _InitialScreeningProviderPolicyError(_ERROR)
    from scion.core.campaign import CampaignManager

    if (
        type(owner) is not CampaignManager
        or type(_REGISTERED_OWNERS) is not weakref.WeakKeyDictionary
        or weakref.WeakKeyDictionary.get(_REGISTERED_OWNERS, owner) is not None
    ):
        raise _InitialScreeningProviderPolicyError(_ERROR)
    from scion.proposal.llm.study_policy import (
        _CAPSULE_ATTRIBUTE,
        _has_installed_initial_screening_study_policy,
        _validate_frozen_llm_client_shape,
    )

    _validate_registration_join(owner, runtime_inputs)
    _validate_frozen_llm_client_shape(runtime_inputs.client, runtime_inputs.capsule)
    client_storage = vars(runtime_inputs.client)
    if (
        type(client_storage) is not dict
        or any(type(key) is not str for key in client_storage)
        or client_storage.get(_CAPSULE_ATTRIBUTE) is not runtime_inputs.capsule
        or not _has_installed_initial_screening_study_policy(runtime_inputs.client)
        or _provider_payload_bytes(runtime_inputs.capsule)
        != runtime_inputs.payload_bytes
    ):
        raise _InitialScreeningProviderPolicyError(_ERROR)
    failed = False
    baseline: _RegisteredProviderPolicyBaseline | None = None
    try:
        baseline = _RegisteredProviderPolicyBaseline(
            runtime_inputs_ref=weakref.ref(runtime_inputs),
            client_ref=weakref.ref(runtime_inputs.client),
            capsule_ref=weakref.ref(runtime_inputs.capsule),
            payload_bytes=runtime_inputs.payload_bytes,
            campaign_dir=publication.campaign_dir,
            directory_fingerprints=publication.directory_fingerprints,
            leaf_fingerprint=publication.leaf_fingerprint,
        )
        _REGISTERED_OWNERS[owner] = baseline
    except Exception:  # noqa: BLE001 - sanitize registry insertion failures
        failed = True
    if failed:
        try:
            current = weakref.WeakKeyDictionary.get(_REGISTERED_OWNERS, owner)
            if baseline is not None and current is baseline:
                weakref.WeakKeyDictionary.__delitem__(_REGISTERED_OWNERS, owner)
        except Exception as ignored_cleanup_error:  # noqa: BLE001 - best effort
            del ignored_cleanup_error
        raise _InitialScreeningProviderPolicyError(_ERROR)


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


def _validate_registration_join(
    owner: Any,
    runtime_inputs: _InitialScreeningProviderPolicyInputs,
) -> None:
    from scion.core.campaign import CampaignManager
    from scion.core.evidence_recording import EvidenceRecorder
    from scion.proposal.engine import CreativeLayer
    from scion.proposal.engine.provider_call import ProviderCaller
    from scion.proposal.llm.client import LLMClient

    if type(owner) is not CampaignManager:
        raise TypeError
    storage = vars(owner)
    if type(storage) is not dict or any(type(key) is not str for key in storage):
        raise TypeError
    required = {
        "_initial_screening_provider_policy_active",
        "_initial_screening_provider_policy",
        "_llm_client",
        "_creative",
        "_provider_call_budget",
        "_evidence_recorder",
        "_campaign_dir",
    }
    if not required.issubset(storage):
        raise TypeError
    client = runtime_inputs.client
    creative = storage["_creative"]
    evidence_recorder = storage["_evidence_recorder"]
    publication = runtime_inputs.publication
    if (
        storage["_initial_screening_provider_policy_active"] is not True
        or storage["_initial_screening_provider_policy"] is not runtime_inputs
        or type(client) is not LLMClient
        or storage["_llm_client"] is not client
        or type(creative) is not CreativeLayer
        or type(evidence_recorder) is not EvidenceRecorder
        or type(storage["_campaign_dir"]) is not str
        or type(publication) is not _ProviderPolicyPublication
        or type(publication.campaign_dir) is not str
        or storage["_campaign_dir"] != publication.campaign_dir
    ):
        raise TypeError
    creative_storage = vars(creative)
    if (
        type(creative_storage) is not dict
        or any(type(key) is not str for key in creative_storage)
        or set(creative_storage) != {"_client", "_model", "_provider_calls"}
    ):
        raise TypeError
    provider_calls = creative_storage["_provider_calls"]
    if type(provider_calls) is not ProviderCaller:
        raise TypeError
    caller_storage = vars(provider_calls)
    evidence_storage = vars(evidence_recorder)
    if (
        type(caller_storage) is not dict
        or any(type(key) is not str for key in caller_storage)
        or set(caller_storage)
        != {"_client", "_model", "_trace_dir", "_provider_call_budget"}
        or type(creative_storage["_model"]) is not str
        or type(caller_storage["_model"]) is not str
        or type(caller_storage["_trace_dir"]) is not str
        or type(runtime_inputs.capsule.requested_model) is not str
        or creative_storage["_client"] is not client
        or caller_storage["_client"] is not client
        or creative_storage["_model"] is not caller_storage["_model"]
        or creative_storage["_model"] != runtime_inputs.capsule.requested_model
        or caller_storage["_trace_dir"]
        != os.path.join(publication.campaign_dir, "llm_traces")
        or caller_storage["_provider_call_budget"]
        is not storage["_provider_call_budget"]
        or type(evidence_storage) is not dict
        or any(type(key) is not str for key in evidence_storage)
        or "model_id" not in evidence_storage
        or type(evidence_storage["model_id"]) is not str
        or evidence_storage["model_id"] != runtime_inputs.capsule.requested_model
    ):
        raise TypeError


def _finalize_initial_screening_provider_policy(
    owner: Any,
    runtime_inputs: _InitialScreeningProviderPolicyInputs,
) -> None:
    """Atomically install the capsule, then register its independent baseline."""

    from scion.proposal.llm.study_policy import (
        _install_initial_screening_study_policy,
        _uninstall_initial_screening_study_policy,
    )

    failed = False
    try:
        _install_initial_screening_study_policy(
            runtime_inputs.client,
            runtime_inputs.capsule,
        )
        _register_initial_screening_provider_policy_owner(owner, runtime_inputs)
    except BaseException as error:
        _remove_exact_provider_registration(owner, runtime_inputs)
        try:
            _uninstall_initial_screening_study_policy(
                runtime_inputs.client,
                runtime_inputs.capsule,
            )
        except BaseException as ignored_cleanup_error:  # noqa: BLE001 - best effort
            del ignored_cleanup_error
        if not isinstance(error, Exception):
            raise
        failed = True
    if failed:
        raise _InitialScreeningProviderPolicyError(_ERROR)


def _remove_exact_provider_registration(
    owner: Any,
    runtime_inputs: _InitialScreeningProviderPolicyInputs,
) -> None:
    """Best-effort removal of only this invocation's exact registry value."""

    try:
        if type(_REGISTERED_OWNERS) is not weakref.WeakKeyDictionary:
            return
        current = weakref.WeakKeyDictionary.get(_REGISTERED_OWNERS, owner)
        if (
            type(current) is _RegisteredProviderPolicyBaseline
            and type(current.runtime_inputs_ref) is weakref.ReferenceType
            and current.runtime_inputs_ref() is runtime_inputs
        ):
            weakref.WeakKeyDictionary.__delitem__(_REGISTERED_OWNERS, owner)
    except BaseException as ignored_cleanup_error:  # noqa: BLE001 - best effort
        del ignored_cleanup_error
