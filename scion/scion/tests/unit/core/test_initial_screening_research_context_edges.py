from __future__ import annotations

import builtins
import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

import scion.core as core_package
from scion.core import (
    campaign as campaign_module,
)
from scion.core import (
    campaign_composition,
    features,
    initial_screening_controls_composition,
    initial_screening_declaration_composition,
    initial_screening_problem_spec,
    initial_screening_research_context_edges,
    initial_screening_research_context_integration,
    initial_screening_research_context_validation,
    initial_screening_study_controls_run_validation,
    initial_screening_study_controls_validation,
    initial_screening_study_provider_policy,
)
from scion.core.initial_screening_research_context import (
    _ERROR,
    _FILENAME,
    _InitialScreeningResearchContextError,
)
from scion.core.initial_screening_study_controls import (
    _FILENAME as _CONTROLS_FILENAME,
)
from scion.core.models import Branch, BranchState
from scion.proposal.context_manager import manager as context_manager_module
from scion.tests.unit.core.test_initial_screening_research_context_integration import (
    _active_manager,
)


def _assert_fixed(error: BaseException) -> None:
    assert type(error) is _InitialScreeningResearchContextError
    assert error.args == (_ERROR,)
    assert error.__cause__ is None
    assert error.__context__ is None


def _assert_no_declaration_leaf(tmp_path: Path) -> None:
    campaign_dir = tmp_path / "campaign"
    assert not (campaign_dir / _CONTROLS_FILENAME).exists()
    assert not (campaign_dir / _FILENAME).exists()


@pytest.mark.parametrize(
    ("module", "name"),
    (
        (
            campaign_composition,
            "_prepare_initial_screening_controls_setup",
        ),
        (
            initial_screening_controls_composition,
            "_prepare_initial_screening_controls_setup_impl",
        ),
        (
            initial_screening_controls_composition,
            "_resolve_active_research_context_installer",
        ),
        (
            initial_screening_controls_composition,
            "_install_active_research_context_capsule",
        ),
        (
            initial_screening_declaration_composition,
            "_prepare_initial_screening_declarations",
        ),
        (
            initial_screening_declaration_composition,
            "_publish_initial_screening_declarations",
        ),
        (
            initial_screening_declaration_composition,
            "_install_initial_screening_declaration_carriers",
        ),
        (
            initial_screening_declaration_composition,
            "_install_initial_screening_research_context_owner",
        ),
        (
            initial_screening_declaration_composition,
            "_finalize_initial_screening_declarations",
        ),
    ),
)
def test_active_construction_locks_first_level_edges_before_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    module: Any,
    name: str,
) -> None:
    calls: list[str] = []

    def replacement(*_args: Any, **_kwargs: Any) -> Any:
        calls.append(name)
        return None

    monkeypatch.setattr(module, name, replacement)
    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        _active_manager(tmp_path, monkeypatch)

    _assert_fixed(captured.value)
    assert calls == []
    _assert_no_declaration_leaf(tmp_path)


def test_active_run_uses_frozen_caller_when_public_wrapper_is_replaced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    calls: list[str] = []
    preflight_calls: list[str] = []

    def replacement(*_args: Any, **_kwargs: Any) -> None:
        calls.append("wrapper")

    monkeypatch.setattr(
        initial_screening_study_controls_validation,
        "_validate_initial_screening_requested_rounds",
        replacement,
    )
    manager._run_research_environment_preflight = lambda: preflight_calls.append(
        "preflight"
    )

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager.run(2)

    _assert_fixed(captured.value)
    assert calls == []
    assert preflight_calls == []


def test_active_run_uses_frozen_caller_when_authority_tuple_is_replaced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    calls: list[str] = []
    preflight_calls: list[str] = []

    def replacement(*_args: Any, **_kwargs: Any) -> None:
        calls.append("authority")

    monkeypatch.setattr(
        initial_screening_study_controls_validation,
        "_REQUESTED_ROUNDS_CALLER_AUTHORITY",
        ("_validate_initial_screening_requested_rounds", replacement),
    )
    manager._run_research_environment_preflight = lambda: preflight_calls.append(
        "preflight"
    )

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager.run(2)

    _assert_fixed(captured.value)
    assert calls == []
    assert preflight_calls == []


def test_active_run_rejects_local_caller_entry_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    calls: list[str] = []
    preflight_calls: list[str] = []

    def replacement(*_args: Any, **_kwargs: Any) -> None:
        calls.append("entry")

    monkeypatch.setattr(
        campaign_module,
        "_REQUESTED_ROUNDS_CALLER_ENTRY",
        replacement,
    )
    manager._run_research_environment_preflight = lambda: preflight_calls.append(
        "preflight"
    )

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager.run(2)

    _assert_fixed(captured.value)
    assert calls == []
    assert preflight_calls == []


@pytest.mark.parametrize(
    "mutation",
    ("replace", "class", "module_alias", "typing_alias", "add", "delete"),
)
def test_active_run_rejects_campaign_storage_drift_before_preflight(
    mutation: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    calls: list[str] = []

    def replacement(*_args: Any, **_kwargs: Any) -> None:
        calls.append("replacement")

    if mutation == "replace":
        monkeypatch.setattr(campaign_module, "active_slot_inventory", replacement)
    elif mutation == "class":
        monkeypatch.setattr(campaign_module, "CampaignManager", object())
    elif mutation == "module_alias":
        monkeypatch.setattr(campaign_module, "ModuleType", replacement)
    elif mutation == "typing_alias":
        monkeypatch.setattr(campaign_module, "cast", replacement)
    elif mutation == "add":
        monkeypatch.setattr(
            campaign_module,
            "_opaque_post_authority_binding",
            object(),
            raising=False,
        )
    else:
        monkeypatch.delattr(campaign_module, "FunctionType")
    manager._run_research_environment_preflight = lambda: calls.append("preflight")

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager.run(2)

    _assert_fixed(captured.value)
    assert calls == []


def test_active_run_rejects_campaign_builtins_drift_before_use(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    calls: list[str] = []
    preflight_calls: list[str] = []
    builtin_storage = vars(campaign_module)["__builtins__"]
    original = builtin_storage["max"]

    def replacement(*args: Any, **kwargs: Any) -> Any:
        calls.append("max")
        return original(*args, **kwargs)

    monkeypatch.setitem(builtin_storage, "max", replacement)
    manager._run_research_environment_preflight = lambda: preflight_calls.append(
        "preflight"
    )
    captured: Exception | None = None
    try:
        manager.run(2)
    except Exception as error:  # noqa: BLE001 - restore shared builtins first
        captured = error
    finally:
        builtin_storage["max"] = original

    assert captured is not None
    _assert_fixed(captured)
    assert calls == []
    assert preflight_calls == []


def test_active_run_rejects_campaign_key_subclass_without_hook(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    calls: list[str] = []

    class KeyProxy(str):
        def __ne__(self, value: object) -> bool:
            calls.append("key")
            return super().__ne__(value)

    monkeypatch.setitem(vars(campaign_module), KeyProxy("_opaque_binding"), object())
    manager._run_research_environment_preflight = lambda: calls.append("preflight")

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager.run(2)

    _assert_fixed(captured.value)
    assert calls == []


def test_noop_registration_is_rejected_after_composition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def replacement(*_args: Any, **_kwargs: Any) -> None:
        calls.append("register")

    monkeypatch.setattr(
        initial_screening_research_context_validation,
        "_register_initial_screening_research_context_owner",
        replacement,
    )
    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        _active_manager(tmp_path, monkeypatch)

    _assert_fixed(captured.value)
    assert calls == []


@pytest.mark.parametrize("mutation", ("holder", "tuple"))
def test_campaign_caller_rejects_rebased_edge_entry_collection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    original = initial_screening_research_context_edges._read_edge_entry_authority()
    calls: list[str] = []

    def replacement(*_args: Any, **_kwargs: Any) -> None:
        calls.append("compose")

    fake = (
        ("_compose_initial_screening_research_context_campaign", replacement),
        original[1],
    )
    if mutation == "holder":
        monkeypatch.setattr(
            initial_screening_research_context_edges,
            "_ENTRY_HOLDER",
            [fake],
        )
    else:
        monkeypatch.setattr(
            initial_screening_research_context_edges,
            "_EDGE_ENTRY_BINDINGS",
            fake,
        )

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        _active_manager(tmp_path, monkeypatch)

    _assert_fixed(captured.value)
    assert calls == []
    _assert_no_declaration_leaf(tmp_path)


@pytest.mark.parametrize("mutation", ("holder", "tuple"))
def test_context_caller_rejects_rebased_edge_entry_collection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    original = initial_screening_research_context_edges._read_edge_entry_authority()
    calls: list[str] = []

    def replacement(*_args: Any, **_kwargs: Any) -> Any:
        calls.append("resolver")
        return lambda _capsule: {"PRIVATE_SENTINEL": True}

    fake = (
        original[0],
        ("_validated_research_context_materializer_edge", replacement),
    )
    if mutation == "holder":
        monkeypatch.setattr(
            initial_screening_research_context_edges,
            "_ENTRY_HOLDER",
            [fake],
        )
    else:
        monkeypatch.setattr(
            initial_screening_research_context_edges,
            "_EDGE_ENTRY_BINDINGS",
            fake,
        )
    branch = Branch(
        branch_id="b1-rebased-edge-collection",
        state=BranchState.NEW,
        base_champion_id=1,
    )

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager._problem_runtime.build_hypothesis_context(
            branch=branch,
            champion=manager._champion,
        )

    _assert_fixed(captured.value)
    assert calls == []


def test_materializer_seams_cannot_inject_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    calls: list[str] = []
    name = "_validated_research_context_materializer_edge"

    def replacement(*_args: Any, **_kwargs: Any) -> Any:
        calls.append(name)
        return {"PRIVATE_SENTINEL": True}

    monkeypatch.setattr(initial_screening_research_context_edges, name, replacement)
    branch = Branch(
        branch_id="b1-edge-replacement",
        state=BranchState.NEW,
        base_champion_id=1,
    )
    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager._problem_runtime.build_hypothesis_context(
            branch=branch,
            champion=manager._champion,
        )

    _assert_fixed(captured.value)
    assert calls == []


def test_construction_rejects_coordinated_integration_binding_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_validator() -> None:
        calls.append("validator")

    def fake_prepare(*_args: Any, **_kwargs: Any) -> None:
        calls.append("prepare")

    original_entries = (
        initial_screening_research_context_integration._INTEGRATION_ENTRY_BINDINGS
    )
    fake_entries = tuple(
        (item[0], fake_prepare)
        if item[0] == "_prepare_research_context_integration"
        else item
        for item in original_entries
    )
    monkeypatch.setattr(
        initial_screening_research_context_integration,
        "_validate_integration_dependencies",
        fake_validator,
    )
    monkeypatch.setattr(
        initial_screening_research_context_integration,
        "_INTEGRATION_VALIDATOR_BINDING",
        ("_validate_integration_dependencies", fake_validator),
    )
    monkeypatch.setattr(
        initial_screening_research_context_integration,
        "_prepare_research_context_integration",
        fake_prepare,
    )
    monkeypatch.setattr(
        initial_screening_research_context_integration,
        "_INTEGRATION_ENTRY_BINDINGS",
        fake_entries,
    )

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        _active_manager(tmp_path, monkeypatch)

    _assert_fixed(captured.value)
    assert calls == []
    _assert_no_declaration_leaf(tmp_path)


def test_materializer_rejects_coordinated_integration_validator_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    calls: list[str] = []

    def fake_validator() -> None:
        calls.append("validator")

    monkeypatch.setattr(
        initial_screening_research_context_integration,
        "_validate_integration_dependencies",
        fake_validator,
    )
    monkeypatch.setattr(
        initial_screening_research_context_integration,
        "_INTEGRATION_VALIDATOR_BINDING",
        ("_validate_integration_dependencies", fake_validator),
    )
    branch = Branch(
        branch_id="b1-integration-validator-drift",
        state=BranchState.NEW,
        base_champion_id=1,
    )

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager._problem_runtime.build_hypothesis_context(
            branch=branch,
            champion=manager._champion,
        )

    _assert_fixed(captured.value)
    assert calls == []


def test_campaign_ignores_coordinated_caller_authority_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = initial_screening_research_context_edges._read_edge_entry_authority()
    calls: list[str] = []

    def fake_compose(*_args: Any, **_kwargs: Any) -> None:
        calls.append("compose")

    fake_entries = (
        ("_compose_initial_screening_research_context_campaign", fake_compose),
        original[1],
    )

    def fake_reader() -> Any:
        calls.append("reader")
        return fake_entries

    def fake_installer(*_args: Any) -> None:
        calls.append("installer")

    monkeypatch.setattr(
        campaign_module,
        "_RESEARCH_CONTEXT_EDGE_AUTHORITY_HOLDER",
        [(fake_reader, fake_entries)],
    )
    monkeypatch.setattr(
        campaign_module,
        "_read_research_context_edge_authority",
        fake_reader,
    )
    monkeypatch.setattr(
        campaign_module,
        "_install_research_context_edge_authority",
        fake_installer,
    )

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        _active_manager(tmp_path, monkeypatch)

    _assert_fixed(captured.value)
    assert calls == []
    _assert_no_declaration_leaf(tmp_path)


def test_context_ignores_coordinated_caller_authority_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    original = initial_screening_research_context_edges._read_edge_entry_authority()
    calls: list[str] = []

    def fake_resolver(*_args: Any, **_kwargs: Any) -> Any:
        calls.append("resolver")
        return lambda _capsule: {"PRIVATE_SENTINEL": True}

    fake_entries = (
        original[0],
        ("_validated_research_context_materializer_edge", fake_resolver),
    )

    def fake_reader() -> Any:
        calls.append("reader")
        return fake_entries

    def fake_installer(*_args: Any) -> None:
        calls.append("installer")

    monkeypatch.setattr(
        context_manager_module,
        "_RESEARCH_CONTEXT_EDGE_AUTHORITY_HOLDER",
        [(fake_reader, fake_entries)],
    )
    monkeypatch.setattr(
        context_manager_module,
        "_read_research_context_edge_authority",
        fake_reader,
    )
    monkeypatch.setattr(
        context_manager_module,
        "_install_research_context_edge_authority",
        fake_installer,
    )
    branch = Branch(
        branch_id="b1-coordinated-context-authority",
        state=BranchState.NEW,
        base_champion_id=1,
    )

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager._problem_runtime.build_hypothesis_context(
            branch=branch,
            champion=manager._champion,
        )

    _assert_fixed(captured.value)
    assert calls == []


def test_campaign_public_authority_reader_replacement_is_not_called(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_reader() -> Any:
        calls.append("reader")
        return ()

    monkeypatch.setattr(
        campaign_module,
        "_read_research_context_edge_authority",
        fake_reader,
    )

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        _active_manager(tmp_path, monkeypatch)

    _assert_fixed(captured.value)
    assert calls == []
    _assert_no_declaration_leaf(tmp_path)


def test_context_public_authority_reader_replacement_is_not_called(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    calls: list[str] = []

    def fake_reader() -> Any:
        calls.append("reader")
        return ()

    monkeypatch.setattr(
        context_manager_module,
        "_read_research_context_edge_authority",
        fake_reader,
    )
    branch = Branch(
        branch_id="b1-context-public-reader",
        state=BranchState.NEW,
        base_champion_id=1,
    )

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager._problem_runtime.build_hypothesis_context(
            branch=branch,
            champion=manager._champion,
        )

    _assert_fixed(captured.value)
    assert calls == []


@pytest.mark.parametrize("consumer", ("campaign", "context"))
def test_local_storage_validator_replacement_is_not_called(
    consumer: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = None if consumer == "campaign" else _active_manager(tmp_path, monkeypatch)
    original = initial_screening_research_context_edges._validated_module_storages
    calls: list[str] = []

    def replacement() -> Any:
        calls.append("storage")
        return original()

    monkeypatch.setattr(
        initial_screening_research_context_edges,
        "_validated_module_storages",
        replacement,
    )

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        if manager is None:
            _active_manager(tmp_path, monkeypatch)
        else:
            branch = Branch(
                branch_id="b1-local-storage-validator",
                state=BranchState.NEW,
                base_champion_id=1,
            )
            manager._problem_runtime.build_hypothesis_context(
                branch=branch,
                champion=manager._champion,
            )

    _assert_fixed(captured.value)
    assert calls == []


@pytest.mark.parametrize(
    "name",
    (
        "campaign_composition_module",
        "controls_composition_module",
        "declaration_composition_module",
    ),
)
def test_source_module_alias_proxy_is_not_used(
    name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = getattr(initial_screening_research_context_edges, name)
    calls: list[str] = []

    class Proxy:
        def __hash__(self) -> int:
            calls.append("hash")
            return hash(original)

        def __eq__(self, value: object) -> bool:
            calls.append("eq")
            return value is original

    monkeypatch.setattr(initial_screening_research_context_edges, name, Proxy())

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        _active_manager(tmp_path, monkeypatch)

    _assert_fixed(captured.value)
    assert calls == []
    _assert_no_declaration_leaf(tmp_path)


@pytest.mark.parametrize(
    ("module", "name", "original"),
    (
        (campaign_composition, "type", builtins.type),
        (initial_screening_controls_composition, "type", builtins.type),
        (initial_screening_declaration_composition, "type", builtins.type),
        (initial_screening_problem_spec, "all", builtins.all),
    ),
)
def test_source_builtin_shadow_is_rejected_before_call(
    module: Any,
    name: str,
    original: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def replacement(*args: Any, **kwargs: Any) -> Any:
        calls.append(name)
        return original(*args, **kwargs)

    monkeypatch.setattr(module, name, replacement, raising=False)

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        _active_manager(tmp_path, monkeypatch)

    _assert_fixed(captured.value)
    assert calls == []
    _assert_no_declaration_leaf(tmp_path)


def test_provider_prepare_replacement_is_rejected_before_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_storage = vars(initial_screening_study_provider_policy)
    original = provider_storage["_prepare_initial_screening_provider_policy"]
    calls: list[str] = []

    def replacement(*args: Any, **kwargs: Any) -> Any:
        calls.append("prepare")
        return original(*args, **kwargs)

    monkeypatch.setattr(
        initial_screening_study_provider_policy,
        "_prepare_initial_screening_provider_policy",
        replacement,
    )

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        _active_manager(tmp_path, monkeypatch)

    _assert_fixed(captured.value)
    assert calls == []
    _assert_no_declaration_leaf(tmp_path)


@pytest.mark.parametrize(
    ("owner", "name"),
    (
        (campaign_composition.os, "makedirs"),
        (campaign_composition.CampaignVerificationFactory, "build"),
        (features, "SafeFeatureExtractor"),
    ),
)
def test_nested_source_binding_drift_is_rejected_before_call(
    owner: Any,
    name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def replacement(*_args: Any, **_kwargs: Any) -> Any:
        calls.append(name)
        return None

    monkeypatch.setattr(owner, name, replacement)

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        _active_manager(tmp_path, monkeypatch)

    _assert_fixed(captured.value)
    assert calls == []
    _assert_no_declaration_leaf(tmp_path)


def test_core_package_module_replacement_is_rejected_before_use(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = ModuleType(initial_screening_controls_composition.__name__)
    monkeypatch.setattr(
        core_package,
        "initial_screening_controls_composition",
        fake,
    )

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        _active_manager(tmp_path, monkeypatch)

    _assert_fixed(captured.value)
    _assert_no_declaration_leaf(tmp_path)


def test_context_builtin_shadow_is_rejected_before_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    calls: list[str] = []

    def replacement(*args: Any, **kwargs: Any) -> str:
        calls.append("str")
        return builtins.str(*args, **kwargs)

    monkeypatch.setattr(
        context_manager_module,
        "str",
        replacement,
        raising=False,
    )
    branch = Branch(
        branch_id="b1-context-builtin-shadow",
        state=BranchState.NEW,
        base_champion_id=1,
    )

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager._problem_runtime.build_hypothesis_context(
            branch=branch,
            champion=manager._champion,
        )

    _assert_fixed(captured.value)
    assert calls == []


def test_validation_guard_rebase_is_rejected_before_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    calls: list[str] = []

    def replacement(*_args: Any, **_kwargs: Any) -> None:
        calls.append("validation")

    aliases = tuple(
        (name, replacement)
        if name
        in {"_validate_local_helper_anchors", "_validate_validation_dependencies"}
        else item
        for item in initial_screening_research_context_validation._VALIDATION_ALIASES
        for name in (item[0],)
    )
    monkeypatch.setattr(
        initial_screening_research_context_validation,
        "_validate_local_helper_anchors",
        replacement,
    )
    monkeypatch.setattr(
        initial_screening_research_context_validation,
        "_validate_validation_dependencies",
        replacement,
    )
    monkeypatch.setattr(
        initial_screening_research_context_validation,
        "_VALIDATION_ALIASES",
        aliases,
    )
    branch = Branch(
        branch_id="b1-validation-guard-rebase",
        state=BranchState.NEW,
        base_champion_id=1,
    )

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager._problem_runtime.build_hypothesis_context(
            branch=branch,
            champion=manager._champion,
        )

    _assert_fixed(captured.value)
    assert calls == []


@pytest.mark.parametrize(
    "module",
    (
        initial_screening_research_context_integration,
        initial_screening_research_context_validation,
    ),
)
def test_materializer_rejects_late_module_keyset_drift(
    module: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    monkeypatch.setattr(module, "_opaque_late_binding", object(), raising=False)
    branch = Branch(
        branch_id="b1-late-module-keyset-drift",
        state=BranchState.NEW,
        base_champion_id=1,
    )

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager._problem_runtime.build_hypothesis_context(
            branch=branch,
            champion=manager._champion,
        )

    _assert_fixed(captured.value)


def test_late_authority_keysets_are_immutable() -> None:
    edges = initial_screening_research_context_edges
    integration = edges._read_research_context_integration_authority()
    validation = edges._read_validation_authority()

    for names in (integration[4], validation[2]):
        assert type(names) is frozenset
        with pytest.raises(TypeError):
            names["_opaque_late_binding"] = None


@pytest.mark.parametrize(
    "module",
    (
        initial_screening_research_context_integration,
        initial_screening_research_context_validation,
    ),
)
def test_materializer_rejects_late_module_name_subclass_without_hook(
    module: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    calls: list[str] = []

    class NameProxy(str):
        def __ne__(self, value: object) -> bool:
            calls.append("name")
            return super().__ne__(value)

    monkeypatch.setattr(module, "__name__", NameProxy(module.__name__))
    branch = Branch(
        branch_id="b1-late-module-name-drift",
        state=BranchState.NEW,
        base_champion_id=1,
    )

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager._problem_runtime.build_hypothesis_context(
            branch=branch,
            champion=manager._champion,
        )

    _assert_fixed(captured.value)
    assert calls == []


@pytest.mark.parametrize(
    ("consumer", "module"),
    (
        ("construction", campaign_composition),
        ("construction", initial_screening_research_context_edges),
        ("run", campaign_module),
        ("run", initial_screening_study_controls_validation),
        ("context", context_manager_module),
    ),
)
def test_active_edges_reject_module_name_subclass_without_hook(
    consumer: str,
    module: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = (
        None if consumer == "construction" else _active_manager(tmp_path, monkeypatch)
    )
    calls: list[str] = []

    class NameProxy(str):
        def __ne__(self, value: object) -> bool:
            calls.append("name")
            return super().__ne__(value)

    monkeypatch.setattr(module, "__name__", NameProxy(module.__name__))
    calls.clear()

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        if consumer == "construction":
            _active_manager(tmp_path, monkeypatch)
        elif consumer == "run":
            assert manager is not None
            manager.run(2)
        else:
            assert manager is not None
            branch = Branch(
                branch_id="b1-module-name-subclass",
                state=BranchState.NEW,
                base_champion_id=1,
            )
            manager._problem_runtime.build_hypothesis_context(
                branch=branch,
                champion=manager._champion,
            )

    _assert_fixed(captured.value)
    assert calls == []


def test_validation_reimport_rejects_rebased_edges_alias_before_installer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    validation_name = initial_screening_research_context_validation.__name__
    real_edges = initial_screening_research_context_integration.edges_module
    real_installer = vars(real_edges)["_install_validation_authority"]
    calls: list[str] = []
    fake_edges = ModuleType(real_edges.__name__)

    def replacement(module: ModuleType) -> None:
        calls.append("installer")
        real_installer(module)

    fake_edges._install_validation_authority = replacement
    monkeypatch.delitem(sys.modules, validation_name)
    monkeypatch.delattr(
        core_package,
        "initial_screening_research_context_validation",
    )
    monkeypatch.setattr(
        initial_screening_research_context_integration,
        "edges_module",
        fake_edges,
    )

    with pytest.raises(TypeError):
        importlib.import_module(validation_name)

    assert calls == []


@pytest.mark.parametrize(
    "module",
    (
        campaign_module,
        initial_screening_study_controls_run_validation,
    ),
)
def test_active_run_rejects_module_subclass_before_preflight(
    module: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    calls: list[str] = []

    class ModuleProxy(ModuleType):
        def __getattribute__(self, name: str) -> Any:
            calls.append(name)
            return super().__getattribute__(name)

    monkeypatch.setattr(module, "__class__", ModuleProxy)
    calls.clear()
    monkeypatch.setattr(
        manager,
        "_run_research_environment_preflight",
        lambda: calls.append("preflight"),
    )

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager.run(2)

    _assert_fixed(captured.value)
    assert calls == []


def test_construction_rejects_edges_module_subclass_before_vars(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class ModuleProxy(ModuleType):
        def __getattribute__(self, name: str) -> Any:
            calls.append(name)
            return super().__getattribute__(name)

    monkeypatch.setattr(
        initial_screening_research_context_edges,
        "__class__",
        ModuleProxy,
    )
    calls.clear()

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        _active_manager(tmp_path, monkeypatch)

    _assert_fixed(captured.value)
    assert calls == []


@pytest.mark.parametrize("name", ("type", "TypeError"))
def test_edges_builtin_shadow_is_rejected_without_call(
    name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    if name == "type":

        def replacement(value: Any) -> type:
            calls.append(name)
            return builtins.type(value)

    else:

        class replacement(Exception):
            def __init__(self, *_args: Any) -> None:
                calls.append(name)

    monkeypatch.setattr(
        initial_screening_research_context_edges,
        name,
        replacement,
        raising=False,
    )

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        _active_manager(tmp_path, monkeypatch)

    _assert_fixed(captured.value)
    assert calls == []


@pytest.mark.parametrize("consumer", ("campaign", "context"))
@pytest.mark.parametrize("builtin_name", ("BaseException", "TypeError", "ValueError"))
def test_builtin_shadow_is_mapped_to_fixed_error(
    consumer: str,
    builtin_name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = None if consumer == "campaign" else _active_manager(tmp_path, monkeypatch)
    monkeypatch.setattr(
        initial_screening_research_context_edges,
        builtin_name,
        KeyError,
        raising=False,
    )

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        if manager is None:
            _active_manager(tmp_path, monkeypatch)
        else:
            branch = Branch(
                branch_id="b1-builtin-shadow",
                state=BranchState.NEW,
                base_champion_id=1,
            )
            manager._problem_runtime.build_hypothesis_context(
                branch=branch,
                champion=manager._champion,
            )

    _assert_fixed(captured.value)


def test_campaign_missing_registered_edges_module_is_fixed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module_name = initial_screening_research_context_edges.__name__
    monkeypatch.delitem(sys.modules, module_name)
    monkeypatch.delattr(core_package, "initial_screening_research_context_edges")

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        _active_manager(tmp_path, monkeypatch)

    _assert_fixed(captured.value)
    assert module_name not in sys.modules
    _assert_no_declaration_leaf(tmp_path)


def test_context_missing_registered_edges_module_is_fixed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    module_name = initial_screening_research_context_edges.__name__
    monkeypatch.delitem(sys.modules, module_name)
    monkeypatch.delattr(core_package, "initial_screening_research_context_edges")
    branch = Branch(
        branch_id="b1-context-missing-edges",
        state=BranchState.NEW,
        base_champion_id=1,
    )

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager._problem_runtime.build_hypothesis_context(
            branch=branch,
            champion=manager._champion,
        )

    _assert_fixed(captured.value)
    assert module_name not in sys.modules
