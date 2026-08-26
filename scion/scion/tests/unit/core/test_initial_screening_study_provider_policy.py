from __future__ import annotations

import gc
import json
import weakref
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from scion.core.initial_screening_study_controls import (
    _FILENAME as _CONTROLS_FILENAME,
)
from scion.core.initial_screening_study_controls import (
    _InitialScreeningStudyControlsRequest,
)
from scion.core.initial_screening_study_controls_io import (
    _publish_attached_control,
    _publish_controls,
)
from scion.core.initial_screening_study_provider_policy import (
    _ERROR,
    _FILENAME,
    _LIMITATIONS,
    _REGISTERED_OWNERS,
    _InitialScreeningProviderPolicyError,
    _InitialScreeningProviderPolicyRequest,
)
from scion.core.resource_envelope import ProviderCallBudget
from scion.proposal.llm.client import LLMClient
from scion.proposal.llm.study_policy import _CAPSULE_ATTRIBUTE
from scion.tests.unit.core.test_initial_screening_study_controls import _manager

_EXPECTED_LIMITATIONS = (
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
_REQUEST_SPECS = (
    ("hypothesis", "generate_hypothesis"),
    ("hypothesis_research_turn", "hypothesis_research_turn"),
    ("code", "generate_patch"),
    ("code_research_turn", "code_research_turn"),
    ("code_research_finalize", "finalize_code_research"),
)


class _BombStorage(dict[Any, Any]):
    def __init__(self, value: dict[str, Any], hooks: list[str]) -> None:
        super().__init__(value)
        self._hooks = hooks

    def __iter__(self):
        self._hooks.append("iter")
        return super().__iter__()

    def __contains__(self, key: object) -> bool:
        self._hooks.append("contains")
        return super().__contains__(key)

    def __getitem__(self, key: object) -> Any:
        self._hooks.append("getitem")
        return super().__getitem__(key)

    def get(self, key: object, default: Any = None) -> Any:
        self._hooks.append("get")
        return super().get(key, default)

    def items(self):
        self._hooks.append("items")
        return super().items()


def _fixed_error(error: BaseException) -> None:
    assert type(error) is _InitialScreeningProviderPolicyError
    assert str(error) == _ERROR
    assert error.args == (_ERROR,)
    assert error.__cause__ is None
    assert error.__context__ is None


def _provider_manager(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    model: str = "gpt-5.6-sol",
    base_url: str = "https://provider.example",
    reasoning: str = "high",
    api_key: str = "private-provider-secret",
) -> tuple[Any, LLMClient, dict[str, Any]]:
    monkeypatch.delenv("SCION_LLM_TIMEOUT_SEC", raising=False)
    monkeypatch.delenv("SCION_DEEPSEEK_REASONING_EFFORT", raising=False)
    if reasoning:
        monkeypatch.setenv("SCION_REASONING_EFFORT", reasoning)
    else:
        monkeypatch.delenv("SCION_REASONING_EFFORT", raising=False)
    client = LLMClient(
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout_sec=61.0,
    )
    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
        llm_client=client,
        provider_policy_request=_InitialScreeningProviderPolicyRequest(),
    )
    payload = json.loads((tmp_path / "campaign" / _FILENAME).read_bytes())
    return manager, client, payload


def _run_without_provider(manager: Any) -> int:
    manager._run_research_environment_preflight = lambda: None
    manager._campaign_loop.run = lambda *, requested_rounds: requested_rounds
    return manager.run(2)


def _assert_rejected_before_run(manager: Any) -> None:
    preflight_calls: list[None] = []
    manager._run_research_environment_preflight = lambda: preflight_calls.append(None)
    manager._campaign_loop.run = lambda *, requested_rounds: requested_rounds

    with pytest.raises(_InitialScreeningProviderPolicyError) as caught:
        manager.run(2)

    _fixed_error(caught.value)
    assert preflight_calls == []
    assert manager._provider_call_budget.used == 0


def test_zero_marker_has_stable_body_free_representation() -> None:
    marker = _InitialScreeningProviderPolicyRequest()

    assert repr(marker) == "_InitialScreeningProviderPolicyRequest(<redacted>)"
    assert str(marker) == repr(marker)
    assert "0x" not in repr(marker)


def test_provider_marker_requires_controls_before_campaign_root(tmp_path: Path) -> None:
    campaign_dir = tmp_path / "campaign"

    with pytest.raises(_InitialScreeningProviderPolicyError) as caught:
        _manager(
            tmp_path,
            campaign_dir=campaign_dir,
            provider_policy_request=_InitialScreeningProviderPolicyRequest(),
        )

    _fixed_error(caught.value)
    assert not campaign_dir.exists()


def test_no_provider_marker_preserves_s2c1_owner_and_leaf(tmp_path: Path) -> None:
    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )

    assert not hasattr(manager, "_initial_screening_provider_policy_active")
    assert not hasattr(manager, "_initial_screening_provider_policy")
    assert not (tmp_path / "campaign" / _FILENAME).exists()
    manager._run_research_environment_preflight = lambda: None
    manager._campaign_loop.run = lambda *, requested_rounds: requested_rounds
    assert manager.run(2) == 2


@pytest.mark.parametrize("with_controls", (False, True))
def test_fresh_exact_client_without_marker_preserves_ordinary_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    with_controls: bool,
) -> None:
    monkeypatch.setenv("SCION_REASONING_EFFORT", "high")
    client = LLMClient(
        model="gpt-5.6-sol",
        api_key="secret",
        base_url="https://provider.example",
        timeout_sec=61.0,
    )
    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=(
            _InitialScreeningStudyControlsRequest(requested_rounds=2)
            if with_controls
            else None
        ),
        llm_client=client,
    )

    assert not hasattr(manager, "_initial_screening_provider_policy_active")
    assert not hasattr(manager, "_initial_screening_provider_policy")
    assert not hasattr(client, _CAPSULE_ATTRIBUTE)
    assert not (tmp_path / "campaign" / _FILENAME).exists()


def test_no_marker_ignores_nonexact_client_storage_without_reserved_key(
    tmp_path: Path,
) -> None:
    hooks: list[str] = []
    client = LLMClient(
        model="gpt-5.6-sol",
        api_key="secret",
        base_url="https://provider.example",
        timeout_sec=61.0,
    )
    object.__setattr__(client, "__dict__", _BombStorage(vars(client), hooks))

    manager, _aliases, _objectives = _manager(tmp_path, llm_client=client)

    assert hooks == []
    assert not hasattr(manager, "_initial_screening_provider_policy")


def test_no_marker_detects_capsule_in_nonexact_storage_without_hooks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _first, client, _payload = _provider_manager(tmp_path / "first", monkeypatch)
    hooks: list[str] = []
    object.__setattr__(client, "__dict__", _BombStorage(vars(client), hooks))
    second_root = tmp_path / "second" / "campaign"

    with pytest.raises(_InitialScreeningProviderPolicyError) as caught:
        _manager(
            tmp_path / "second",
            campaign_dir=second_root,
            llm_client=client,
        )

    _fixed_error(caught.value)
    assert hooks == []
    assert not second_root.exists()


@pytest.mark.parametrize(
    (
        "model",
        "base_url",
        "reasoning",
        "provider",
        "effective_url",
        "effective_reasoning",
        "thinking_mode",
        "system_blocks",
        "tool_choice",
    ),
    (
        (
            "claude-opus-4-6",
            "https://anthropic.example",
            "",
            "anthropic",
            "https://anthropic.example",
            "",
            "disabled",
            "native_system_blocks",
            "required_named_tool",
        ),
        (
            "gpt-5.6-sol",
            "https://openai.example",
            "high",
            "openai_compatible",
            "https://openai.example/v1",
            "high",
            "disabled",
            "merged_into_user_prompt",
            "required_named_function",
        ),
        (
            "deepseek-v4-pro",
            "https://api.deepseek.com",
            "low",
            "openai_compatible",
            "https://api.deepseek.com",
            "high",
            "enabled",
            "merged_into_user_prompt",
            "omitted",
        ),
        (
            "minimax-text-01",
            "https://provider.example",
            "",
            "openai_compatible",
            "https://provider.example/v1",
            "",
            "disabled",
            "merged_into_user_prompt",
            "required_named_function",
        ),
    ),
)
def test_exact_provider_policy_leaf_and_consumers_are_joined(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    model: str,
    base_url: str,
    reasoning: str,
    provider: str,
    effective_url: str,
    effective_reasoning: str,
    thinking_mode: str,
    system_blocks: str,
    tool_choice: str,
) -> None:
    manager, client, payload = _provider_manager(
        tmp_path,
        monkeypatch,
        model=model,
        base_url=base_url,
        reasoning=reasoning,
    )
    raw = (tmp_path / "campaign" / _FILENAME).read_bytes()

    assert _LIMITATIONS == _EXPECTED_LIMITATIONS
    assert len(raw) <= 65_536
    assert raw == (
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )
    assert set(payload) == {
        "schema_version",
        "scope",
        "limitations",
        "client",
        "request_policies",
    }
    assert payload["schema_version"] == "scion.initial_screening_provider_policy.v1"
    assert payload["scope"] == "REQUESTED_PROVIDER_POLICY_ONLY"
    assert tuple(payload["limitations"]) == _EXPECTED_LIMITATIONS
    client_payload = payload["client"]
    assert set(client_payload) == {
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
    assert client_payload == {
        "client_type": "scion.proposal.llm.client.LLMClient",
        "requested_model": model,
        "configured_base_url": base_url,
        "effective_sdk_base_url": effective_url,
        "provider_transport": provider,
        "requested_reasoning_effort": reasoning,
        "effective_reasoning_effort": effective_reasoning,
        "thinking_mode": thinking_mode,
        "base_timeout_sec": 61.0,
        "sdk_max_retries_requested": 0,
        "request_body_policy": {
            "temperature": "omitted",
            "top_p": "omitted",
            "seed": "omitted",
            "stream": "omitted",
            "system_blocks": system_blocks,
            "tool_choice": tool_choice,
        },
    }
    assert [
        (entry["request_kind"], entry["tool_name"])
        for entry in payload["request_policies"]
    ] == list(_REQUEST_SPECS)
    assert all(
        set(entry)
        == {
            "request_kind",
            "tool_name",
            "timeout_sec",
            "provider",
            "output_token_policy",
            "output_token_parameter",
            "provider_transport_output_ceiling_tokens",
        }
        for entry in payload["request_policies"]
    )
    caller = manager._creative._provider_calls
    assert manager._llm_client is client
    assert manager._creative._client is client
    assert caller._client is client
    assert manager._creative._model is caller._model
    assert manager._creative._model == model
    assert caller._provider_call_budget is manager._provider_call_budget
    assert manager._evidence_recorder.model_id == model
    assert (
        getattr(client, _CAPSULE_ATTRIBUTE)
        is manager._initial_screening_provider_policy.capsule
    )
    assert (tmp_path / "campaign" / _FILENAME).stat().st_mode & 0o777 == 0o600
    assert _run_without_provider(manager) == 2


def test_five_timeout_overrides_are_frozen_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = {
        "hypothesis": 101.0,
        "hypothesis_research_turn": 102.0,
        "code": 103.0,
        "code_research_turn": 104.0,
        "code_research_finalize": 105.0,
    }
    for kind, timeout in expected.items():
        monkeypatch.setenv(f"SCION_LLM_{kind.upper()}_TIMEOUT_SEC", str(timeout))
    manager, client, payload = _provider_manager(tmp_path, monkeypatch)

    assert {
        entry["request_kind"]: entry["timeout_sec"]
        for entry in payload["request_policies"]
    } == expected
    for kind in expected:
        monkeypatch.setenv(f"SCION_LLM_{kind.upper()}_TIMEOUT_SEC", "999")
    for kind, tool_name in _REQUEST_SPECS:
        policy = client.resolve_request_policy(
            request_kind=kind,
            tool={"name": tool_name},
            model=client.model,
        )
        assert policy["timeout_sec"] == expected[kind]
    assert _run_without_provider(manager) == 2


@pytest.mark.parametrize(
    "raw_timeout",
    ("bad-private-timeout", "0", "-1", "nan", "inf", " 9 "),
)
def test_invalid_timeout_override_is_private_fixed_pre_root_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
    raw_timeout: str,
) -> None:
    monkeypatch.setenv("SCION_LLM_CODE_TIMEOUT_SEC", raw_timeout)
    client = LLMClient(
        model="gpt-5.6-sol",
        api_key="private-provider-secret",
        base_url="https://provider.example",
        timeout_sec=61.0,
    )

    with pytest.raises(_InitialScreeningProviderPolicyError) as caught:
        _manager(
            tmp_path,
            request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
            llm_client=client,
            provider_policy_request=_InitialScreeningProviderPolicyRequest(),
        )

    _fixed_error(caught.value)
    assert not (tmp_path / "campaign").exists()
    captured = capsys.readouterr()
    rendered = (
        captured.out
        + captured.err
        + "".join(record.getMessage() for record in caplog.records)
    )
    assert raw_timeout not in rendered


def test_both_private_control_leaves_exist_before_workspace_side_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scion.core import campaign_composition

    original_init = campaign_composition.WorkspaceMaterializer.__init__
    observed: list[set[str]] = []

    def guarded_init(self: Any, root: str, **kwargs: Any) -> None:
        observed.append({entry.name for entry in Path(root).iterdir()})
        original_init(self, root, **kwargs)

    monkeypatch.setattr(
        campaign_composition.WorkspaceMaterializer,
        "__init__",
        guarded_init,
    )
    _provider_manager(tmp_path, monkeypatch)

    assert observed == [{_CONTROLS_FILENAME, _FILENAME}]


def test_policy_carriers_and_public_artifacts_do_not_project_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "private-provider-secret-sentinel"
    manager, client, payload = _provider_manager(
        tmp_path,
        monkeypatch,
        api_key=secret,
    )
    runtime_inputs = manager._initial_screening_provider_policy
    publication = runtime_inputs.publication
    capsule = getattr(client, _CAPSULE_ATTRIBUTE)
    baseline = weakref.WeakKeyDictionary.get(_REGISTERED_OWNERS, manager)

    assert secret not in json.dumps(payload)
    assert repr(runtime_inputs) == "_InitialScreeningProviderPolicyInputs(<redacted>)"
    assert repr(publication) == "_ProviderPolicyPublication(<redacted>)"
    assert repr(baseline) == "_RegisteredProviderPolicyBaseline(<redacted>)"
    assert repr(capsule) == "_FrozenInitialScreeningStudyPolicy(<redacted>)"
    assert all(
        "0x" not in repr(value)
        for value in (runtime_inputs, publication, baseline, capsule)
    )
    assert _run_without_provider(manager) == 2
    for path in (tmp_path / "campaign").rglob("*"):
        if path.is_file():
            assert secret.encode() not in path.read_bytes()


def test_provider_registry_weak_baseline_does_not_retain_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, client, _payload = _provider_manager(tmp_path, monkeypatch)
    baseline = weakref.WeakKeyDictionary.get(_REGISTERED_OWNERS, manager)
    assert baseline is not None
    manager_ref = weakref.ref(manager)
    runtime_inputs_ref = baseline.runtime_inputs_ref

    del manager
    gc.collect()

    assert manager_ref() is None
    assert runtime_inputs_ref() is None
    assert getattr(client, _CAPSULE_ATTRIBUTE) is baseline.capsule_ref()


@pytest.mark.parametrize(
    "base_url",
    (
        "https://EXAMPLE.com",
        "https://example.com/",
        "https://user@example.com",
        "https://example.com?query=1",
        "https://example.com#fragment",
        "https://example.com/%2e%2e",
        "https://example.com/a//b",
        "https://example.com/a/../b",
        "https://example.com:443/",
        "http://remote.example",
        "http://192.0.2.1",
        "https://example.com\\escape",
    ),
)
def test_hostile_provider_url_fails_before_campaign_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    base_url: str,
) -> None:
    campaign_dir = tmp_path / "campaign"
    client = LLMClient(
        model="gpt-5.6-sol",
        api_key="secret",
        base_url=base_url,
        timeout_sec=61.0,
    )
    monkeypatch.setenv("SCION_REASONING_EFFORT", "high")

    with pytest.raises(_InitialScreeningProviderPolicyError) as caught:
        _manager(
            tmp_path,
            campaign_dir=campaign_dir,
            request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
            llm_client=client,
            provider_policy_request=_InitialScreeningProviderPolicyRequest(),
        )

    _fixed_error(caught.value)
    assert not campaign_dir.exists()
    assert not hasattr(client, _CAPSULE_ATTRIBUTE)


@pytest.mark.parametrize(
    "mutation",
    (
        "client_model",
        "client_cache",
        "client_usage",
        "client_diagnostics",
        "client_reasoning",
        "client_base_url",
        "client_timeout",
        "client_method",
        "owner_client",
        "caller_client",
        "creative_client",
        "creative_model",
        "caller_model",
        "caller_trace_dir",
        "caller_budget",
        "caller_method",
        "evidence_model",
        "capsule",
        "capsule_extra",
    ),
)
def test_runtime_identity_and_pristine_mutants_fail_before_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    manager, client, _payload = _provider_manager(tmp_path, monkeypatch)
    _mutate_provider_runtime(manager, client, mutation, tmp_path)

    _assert_rejected_before_run(manager)


def _mutate_provider_runtime(
    manager: Any,
    client: LLMClient,
    mutation: str,
    tmp_path: Path,
) -> None:
    replacement_client = lambda: LLMClient(
        model="gpt-5.6-sol",
        api_key="another-secret",
        base_url="https://provider.example",
        timeout_sec=61.0,
    )
    capsule = manager._initial_screening_provider_policy.capsule
    mutations = {
        "client_model": lambda: setattr(client, "model", "gpt-5.6-terra"),
        "client_cache": lambda: setattr(client, "_openai_client", object()),
        "client_usage": lambda: setattr(
            client, "_last_usage_metadata", {"input_tokens": 1}
        ),
        "client_diagnostics": lambda: setattr(
            client, "_last_response_diagnostics", {"provider": "mutant"}
        ),
        "client_reasoning": lambda: setattr(client, "reasoning_effort", "medium"),
        "client_base_url": lambda: setattr(client, "base_url", "https://other.example"),
        "client_timeout": lambda: setattr(client, "timeout_sec", 62.0),
        "client_method": lambda: setattr(client, "call_with_tool", dict),
        "owner_client": lambda: setattr(manager, "_llm_client", replacement_client()),
        "caller_client": lambda: setattr(
            manager._creative._provider_calls, "_client", replacement_client()
        ),
        "creative_client": lambda: setattr(manager._creative, "_client", object()),
        "creative_model": lambda: setattr(
            manager._creative, "_model", client.model.encode().decode()
        ),
        "caller_model": lambda: setattr(
            manager._creative._provider_calls, "_model", "gpt-5.6-terra"
        ),
        "caller_trace_dir": lambda: setattr(
            manager._creative._provider_calls,
            "_trace_dir",
            str(tmp_path / "elsewhere"),
        ),
        "caller_budget": lambda: setattr(
            manager._creative._provider_calls,
            "_provider_call_budget",
            ProviderCallBudget(200),
        ),
        "caller_method": lambda: setattr(
            manager._creative._provider_calls, "call", dict
        ),
        "evidence_model": lambda: setattr(
            manager._evidence_recorder, "model_id", "gpt-5.6-terra"
        ),
        "capsule": lambda: object.__setattr__(
            capsule, "requested_model", "gpt-5.6-terra"
        ),
        "capsule_extra": lambda: object.__setattr__(capsule, "api_key", "secret"),
    }
    mutations[mutation]()


@pytest.mark.parametrize(
    "mutation",
    (
        "capsule_string_subclass",
        "client_float_subclass",
        "capsule_extra",
        "client_extra",
    ),
)
def test_structural_provider_mutants_fail_before_both_leaf_rewalks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    from scion.core import (
        initial_screening_study_controls_validation as controls_validation,
    )
    from scion.core import (
        initial_screening_study_provider_policy_validation as provider_validation,
    )

    hooks: list[str] = []

    class EvilStr(str):
        def __eq__(self, other: object) -> bool:
            hooks.append("string equality")
            return super().__eq__(other)

    class EvilFloat(float):
        def __eq__(self, other: object) -> bool:
            hooks.append("float equality")
            return super().__eq__(other)

    manager, client, _payload = _provider_manager(tmp_path, monkeypatch)
    capsule = manager._initial_screening_provider_policy.capsule
    if mutation == "capsule_string_subclass":
        object.__setattr__(capsule, "requested_model", EvilStr(client.model))
    elif mutation == "client_float_subclass":
        client.timeout_sec = EvilFloat(client.timeout_sec)
    elif mutation == "capsule_extra":
        object.__setattr__(capsule, "extra", "mutant")
    else:
        client.__dict__["extra"] = "mutant"
    controls_fs: list[None] = []
    provider_fs: list[None] = []
    monkeypatch.setattr(
        controls_validation,
        "_validate_controls_publication",
        lambda *_args, **_kwargs: controls_fs.append(None),
    )
    monkeypatch.setattr(
        provider_validation,
        "_validate_attached_control_publication",
        lambda *_args, **_kwargs: provider_fs.append(None),
    )

    _assert_rejected_before_run(manager)
    assert hooks == []
    assert controls_fs == []
    assert provider_fs == []


def test_replacing_private_carrier_with_equal_value_cannot_rebaseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, _client, _payload = _provider_manager(tmp_path, monkeypatch)
    manager._initial_screening_provider_policy = replace(
        manager._initial_screening_provider_policy
    )

    _assert_rejected_before_run(manager)


def test_class_drift_and_deleted_markers_cannot_bypass_registry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, _client, _payload = _provider_manager(tmp_path, monkeypatch)
    manager.__class__ = type("DriftedCampaignManager", (type(manager),), {})
    del manager.__dict__["_initial_screening_provider_policy_active"]
    del manager.__dict__["_initial_screening_provider_policy"]
    gc.collect()

    _assert_rejected_before_run(manager)


def test_deleted_provider_carrier_cannot_bypass_registered_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, _client, _payload = _provider_manager(tmp_path, monkeypatch)
    del manager.__dict__["_initial_screening_provider_policy_active"]
    del manager.__dict__["_initial_screening_provider_policy"]
    gc.collect()

    _assert_rejected_before_run(manager)


@pytest.mark.parametrize("with_controls", (False, True))
def test_installed_provider_client_requires_marker_on_second_manager(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    with_controls: bool,
) -> None:
    first, client, _payload = _provider_manager(
        tmp_path,
        monkeypatch,
    )
    first_leaf = tmp_path / "campaign" / _FILENAME
    original_leaf = first_leaf.read_bytes()
    second_base = tmp_path / "second"
    second_root = second_base / "campaign"

    with pytest.raises(_InitialScreeningProviderPolicyError) as caught:
        _manager(
            second_base,
            campaign_dir=second_root,
            request=(
                _InitialScreeningStudyControlsRequest(requested_rounds=2)
                if with_controls
                else None
            ),
            llm_client=client,
        )

    _fixed_error(caught.value)
    assert not second_root.exists()
    assert first_leaf.read_bytes() == original_leaf
    assert first._provider_call_budget.used == 0


def test_later_provider_install_cannot_silently_change_earlier_s2c1_manager(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCION_REASONING_EFFORT", "high")
    client = LLMClient(
        model="gpt-5.6-sol",
        api_key="secret",
        base_url="https://provider.example",
        timeout_sec=61.0,
    )
    first_base = tmp_path / "first"
    first, _aliases, _objectives = _manager(
        first_base,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
        llm_client=client,
    )
    assert not hasattr(client, _CAPSULE_ATTRIBUTE)
    second_base = tmp_path / "second"
    second, _aliases, _objectives = _manager(
        second_base,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
        llm_client=client,
        provider_policy_request=_InitialScreeningProviderPolicyRequest(),
    )
    assert hasattr(client, _CAPSULE_ATTRIBUTE)
    from scion.core import (
        initial_screening_study_controls_validation as controls_validation,
    )
    from scion.core import (
        initial_screening_study_provider_policy_validation as provider_validation,
    )

    controls_fs: list[None] = []
    provider_fs: list[None] = []
    monkeypatch.setattr(
        controls_validation,
        "_validate_controls_publication",
        lambda *_args, **_kwargs: controls_fs.append(None),
    )
    monkeypatch.setattr(
        provider_validation,
        "_validate_attached_control_publication",
        lambda *_args, **_kwargs: provider_fs.append(None),
    )

    _assert_rejected_before_run(first)
    assert controls_fs == []
    assert provider_fs == []
    assert second._provider_call_budget.used == 0


def test_no_marker_gate_scans_provider_caller_client_alias(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCION_REASONING_EFFORT", "high")
    first_client = LLMClient(
        model="gpt-5.6-sol",
        api_key="first-secret",
        base_url="https://provider.example",
        timeout_sec=61.0,
    )
    first, _aliases, _objectives = _manager(
        tmp_path / "first",
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
        llm_client=first_client,
    )
    second_client = LLMClient(
        model="gpt-5.6-sol",
        api_key="second-secret",
        base_url="https://provider.example",
        timeout_sec=61.0,
    )
    _second, _aliases, _objectives = _manager(
        tmp_path / "second",
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
        llm_client=second_client,
        provider_policy_request=_InitialScreeningProviderPolicyRequest(),
    )
    first._creative._provider_calls._client = second_client
    hooks: list[str] = []
    object.__setattr__(
        first._creative,
        "__dict__",
        _BombStorage(vars(first._creative), hooks),
    )
    object.__setattr__(
        first._creative._provider_calls,
        "__dict__",
        _BombStorage(vars(first._creative._provider_calls), hooks),
    )
    object.__setattr__(
        second_client,
        "__dict__",
        _BombStorage(vars(second_client), hooks),
    )
    assert not hasattr(first._llm_client, _CAPSULE_ATTRIBUTE)
    assert not hasattr(first._creative._client, _CAPSULE_ATTRIBUTE)
    assert hasattr(first._creative._provider_calls._client, _CAPSULE_ATTRIBUTE)
    from scion.core import (
        initial_screening_study_controls_validation as controls_validation,
    )
    from scion.core import (
        initial_screening_study_provider_policy_validation as provider_validation,
    )

    controls_fs: list[None] = []
    provider_fs: list[None] = []
    monkeypatch.setattr(
        controls_validation,
        "_validate_controls_publication",
        lambda *_args, **_kwargs: controls_fs.append(None),
    )
    monkeypatch.setattr(
        provider_validation,
        "_validate_attached_control_publication",
        lambda *_args, **_kwargs: provider_fs.append(None),
    )

    _assert_rejected_before_run(first)
    assert hooks == []
    assert controls_fs == []
    assert provider_fs == []


def test_provider_leaf_drift_fails_before_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, _client, _payload = _provider_manager(tmp_path, monkeypatch)
    (tmp_path / "campaign" / _FILENAME).write_bytes(b"{}\n")

    _assert_rejected_before_run(manager)


@pytest.mark.parametrize("child_kind", ("directory", "symlink"))
def test_trace_target_must_remain_absent_under_campaign_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    child_kind: str,
) -> None:
    manager, _client, _payload = _provider_manager(tmp_path, monkeypatch)
    trace_path = tmp_path / "campaign" / "llm_traces"
    protected = tmp_path / "protected"
    protected.mkdir()
    if child_kind == "directory":
        trace_path.mkdir()
    else:
        trace_path.symlink_to(protected, target_is_directory=True)

    _assert_rejected_before_run(manager)
    assert list(protected.iterdir()) == []


def test_registration_exception_uninstalls_exact_caller_capsule(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scion.core import initial_screening_study_provider_policy as provider_policy

    client = LLMClient(
        model="gpt-5.6-sol",
        api_key="secret",
        base_url="https://provider.example",
        timeout_sec=61.0,
    )
    monkeypatch.setenv("SCION_REASONING_EFFORT", "high")
    monkeypatch.setattr(
        provider_policy,
        "_register_initial_screening_provider_policy_owner",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("registration fault")),
    )

    with pytest.raises(_InitialScreeningProviderPolicyError) as caught:
        _manager(
            tmp_path,
            request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
            llm_client=client,
            provider_policy_request=_InitialScreeningProviderPolicyRequest(),
        )

    _fixed_error(caught.value)
    assert not hasattr(client, _CAPSULE_ATTRIBUTE)


def test_registration_rejects_external_trace_target_and_leaves_residual_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scion.core import initial_screening_study_controls as controls

    client = LLMClient(
        model="gpt-5.6-sol",
        api_key="secret",
        base_url="https://provider.example",
        timeout_sec=61.0,
    )
    monkeypatch.setenv("SCION_REASONING_EFFORT", "high")
    original = controls._register_initial_screening_controls_owner

    def register_then_mutate(owner: Any, runtime_inputs: Any) -> None:
        original(owner, runtime_inputs)
        owner._creative._provider_calls._trace_dir = str(tmp_path / "external-traces")

    monkeypatch.setattr(
        controls,
        "_register_initial_screening_controls_owner",
        register_then_mutate,
    )

    with pytest.raises(_InitialScreeningProviderPolicyError) as caught:
        _manager(
            tmp_path,
            request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
            llm_client=client,
            provider_policy_request=_InitialScreeningProviderPolicyRequest(),
        )

    _fixed_error(caught.value)
    assert not hasattr(client, _CAPSULE_ATTRIBUTE)
    assert (tmp_path / "campaign" / _FILENAME).is_file()
    assert not (tmp_path / "external-traces").exists()


def test_post_install_base_exception_removes_capsule_and_registry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scion.core import initial_screening_study_provider_policy as provider_policy

    class Abort(BaseException):
        pass

    client = LLMClient(
        model="gpt-5.6-sol",
        api_key="secret",
        base_url="https://provider.example",
        timeout_sec=61.0,
    )
    monkeypatch.setenv("SCION_REASONING_EFFORT", "high")
    original = provider_policy._register_initial_screening_provider_policy_owner
    observed_owners: list[Any] = []

    def register_then_abort(owner: Any, runtime_inputs: Any) -> None:
        original(owner, runtime_inputs)
        observed_owners.append(owner)
        raise Abort

    monkeypatch.setattr(
        provider_policy,
        "_register_initial_screening_provider_policy_owner",
        register_then_abort,
    )

    with pytest.raises(Abort):
        _manager(
            tmp_path,
            request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
            llm_client=client,
            provider_policy_request=_InitialScreeningProviderPolicyRequest(),
        )

    assert not hasattr(client, _CAPSULE_ATTRIBUTE)
    assert len(observed_owners) == 1
    assert (
        weakref.WeakKeyDictionary.get(
            _REGISTERED_OWNERS,
            observed_owners[0],
        )
        is None
    )


def test_install_return_base_exception_removes_exact_capsule(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scion.proposal.llm import study_policy

    class Abort(BaseException):
        pass

    client = LLMClient(
        model="gpt-5.6-sol",
        api_key="secret",
        base_url="https://provider.example",
        timeout_sec=61.0,
    )
    monkeypatch.setenv("SCION_REASONING_EFFORT", "high")
    original = study_policy._install_initial_screening_study_policy

    def install_then_abort(client_value: Any, capsule: Any) -> None:
        original(client_value, capsule)
        raise Abort

    monkeypatch.setattr(
        study_policy,
        "_install_initial_screening_study_policy",
        install_then_abort,
    )

    with pytest.raises(Abort):
        _manager(
            tmp_path,
            request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
            llm_client=client,
            provider_policy_request=_InitialScreeningProviderPolicyRequest(),
        )

    assert not hasattr(client, _CAPSULE_ATTRIBUTE)


def test_attached_leaf_is_private_and_exclusive(tmp_path: Path) -> None:
    campaign_dir = tmp_path / "campaign"
    first_name = "first.json"
    second_name = "second.json"
    publication = _publish_controls(
        str(campaign_dir),
        b"{}\n",
        protected_roots=(),
        filename=first_name,
        max_bytes=32,
    )

    fingerprint = _publish_attached_control(
        publication,
        b'{"policy":1}\n',
        filename=second_name,
        first_filename=first_name,
        max_bytes=32,
    )

    leaf = campaign_dir / second_name
    assert leaf.read_bytes() == b'{"policy":1}\n'
    assert leaf.stat().st_mode & 0o777 == 0o600
    assert fingerprint[:2] == (leaf.stat().st_dev, leaf.stat().st_ino)
    with pytest.raises((FileExistsError, ValueError)):
        _publish_attached_control(
            publication,
            b'{"policy":1}\n',
            filename=second_name,
            first_filename=first_name,
            max_bytes=32,
        )


def test_final_attached_leaf_validation_fault_rolls_back_known_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scion.core import initial_screening_study_controls_io as controls_io

    campaign_dir = tmp_path / "campaign"
    publication = _publish_controls(
        str(campaign_dir),
        b"{}\n",
        protected_roots=(),
        filename="first.json",
        max_bytes=32,
    )
    monkeypatch.setattr(
        controls_io,
        "_validate_attached_control_publication",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("fault")),
    )

    with pytest.raises(OSError, match="fault"):
        _publish_attached_control(
            publication,
            b'{"policy":1}\n',
            filename="second.json",
            first_filename="first.json",
            max_bytes=32,
        )

    assert not campaign_dir.exists()


@pytest.mark.parametrize(
    "drift",
    ("first_leaf_swap", "attached_leaf_swap", "extra_entry"),
)
def test_final_attached_rewalk_drift_leaves_fail_closed_residual_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
) -> None:
    from scion.core import initial_screening_study_controls_io as controls_io

    campaign_dir = tmp_path / "campaign"
    first_name = "first.json"
    second_name = "second.json"
    publication = _publish_controls(
        str(campaign_dir),
        b"{}\n",
        protected_roots=(),
        filename=first_name,
        max_bytes=32,
    )
    original_validate = controls_io._validate_attached_control_publication

    def drift_then_validate(*args: Any, **kwargs: Any) -> None:
        if drift == "first_leaf_swap":
            (campaign_dir / first_name).unlink()
            (campaign_dir / first_name).write_bytes(b"{}\n")
            (campaign_dir / first_name).chmod(0o600)
        elif drift == "attached_leaf_swap":
            (campaign_dir / second_name).unlink()
            (campaign_dir / second_name).write_bytes(b"replacement\n")
            (campaign_dir / second_name).chmod(0o600)
        else:
            (campaign_dir / "unexpected").write_bytes(b"sentinel")
        original_validate(*args, **kwargs)

    monkeypatch.setattr(
        controls_io,
        "_validate_attached_control_publication",
        drift_then_validate,
    )

    with pytest.raises(ValueError):
        _publish_attached_control(
            publication,
            b'{"policy":1}\n',
            filename=second_name,
            first_filename=first_name,
            max_bytes=32,
        )

    assert campaign_dir.is_dir()
    assert (campaign_dir / first_name).exists()
    assert (campaign_dir / second_name).exists()
    if drift == "attached_leaf_swap":
        assert (campaign_dir / second_name).read_bytes() == b"replacement\n"
    if drift == "extra_entry":
        assert (campaign_dir / "unexpected").read_bytes() == b"sentinel"


def test_attached_leaf_does_not_follow_preexisting_symlink(tmp_path: Path) -> None:
    campaign_dir = tmp_path / "campaign"
    protected = tmp_path / "protected"
    protected.write_bytes(b"sentinel")
    publication = _publish_controls(
        str(campaign_dir),
        b"{}\n",
        protected_roots=(),
        filename="first.json",
        max_bytes=32,
    )
    (campaign_dir / "second.json").symlink_to(protected)

    with pytest.raises(ValueError):
        _publish_attached_control(
            publication,
            b'{"policy":1}\n',
            filename="second.json",
            first_filename="first.json",
            max_bytes=32,
        )

    assert protected.read_bytes() == b"sentinel"
