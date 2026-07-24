from __future__ import annotations

import json
from pathlib import Path

import pytest

import scion.problems.warehouse_delivery.w3_installed_replay as installed_replay
import scion.problems.warehouse_delivery.w3_root_coordinator as coordinator
import scion.runtime.execution.external_installation as external_installation
import scion.runtime.execution.external_linux as external_linux
from scion.problems.warehouse_delivery.w3_installed_replay import (
    RootInstalledAcceptanceAuthority,
    WarehouseW3InstalledAcceptanceBundle,
    verify_w3_installed_replay,
)
from scion.problems.warehouse_delivery.w3_root_coordinator import (
    WarehouseW3InstallPhaseLedger,
    WarehouseW3RootCoordinatorError,
    _FixedStartAuthorizationAuthority,
    _close_w3_root_selection_prefix,
    _initialize_w3_root_layout_at,
    _inspect_w3_root_installation_at,
    _verify_w3_root_layout_at,
    start_w3,
)
from scion.problems.warehouse_delivery.w3_root_preflight import (
    root_transaction_trace_leaf,
)
from scion.problems.warehouse_delivery.w3_start_authorization import (
    ProspectiveStartAuthorizationIntent,
    _bind_start_authorization_for_test,
)
from scion.runtime.execution.external_installation import (
    DurableReceiptDirectory,
    INSTALL_PHASES,
    RootInstallationState,
    RootPhase,
    StartDispatchState,
)
from scion.runtime.execution.external_linux import pin_absolute_directory
from scion.tests.unit.problems.warehouse_delivery.test_w3_environment_receipts import (
    semantic_inputs,
)
from scion.tests.unit.problems.warehouse_delivery.test_w3_start_authorization import (
    _installed_bundle,
    _installed_replay_inputs,
    _prospective_raw,
)
from scion.tests.unit.problems.warehouse_delivery.test_w3_root_selection import (
    _bundle as _selection_bundle,
)


def _fixed_start_inputs(
    values: dict[str, object],
    replay: object,
    evidence: object,
    installed: object,
    intents: tuple[object, ...],
    receipts: tuple[object, ...],
) -> tuple[
    WarehouseW3InstalledAcceptanceBundle,
    coordinator.WarehouseW3InstalledStartGateBundle,
    bytes,
]:
    installed_replay = _installed_replay_inputs(
        values,
        evidence,
        installed,
        intents,
        receipts,
    )
    installed_bundle = WarehouseW3InstalledAcceptanceBundle._create_for_test(
        selection_replay_inputs=replay,
        installed_replay_inputs=installed_replay,
    )
    authorization = _bind_start_authorization_for_test(
        ProspectiveStartAuthorizationIntent.from_bytes(_prospective_raw()),
        selection_replay_inputs=replay,
        prestart_evidence=evidence,
        installed_acceptance=installed,
        phase_intents=intents,
        phase_receipts=receipts,
        recorded_at_utc="2026-07-23T21:00:00Z",
        unit=values["installation"].run_unit,
    )
    prestart_inputs = coordinator.WarehouseW3PreStartProducerReplayInputs(
        candidate_gate_raw=values["candidate_gate"].raw,
        dry_root_raw=values["dry_root"].raw,
        environment_rehash_raw=values["environment_rehash"].raw,
        loaded_manager_raw=values["loaded_manager"].raw,
        prestart_absence_raw=values["prestart_absence"].raw,
        runtime_account_raw=values["runtime_account"].raw,
    )
    start_bundle = coordinator.WarehouseW3InstalledStartGateBundle._create_for_test(
        prospective_intent_raw=_prospective_raw(),
        installed_acceptance_raw=installed.raw,
        prestart_evidence_raw=evidence.raw,
        selection_replay_inputs=replay,
        prestart_producer_replay_inputs=prestart_inputs,
        installed_replay_inputs=installed_replay,
    )
    return installed_bundle, start_bundle, authorization.raw


def _write_install_phase_ledger(
    install: Path,
    *,
    intents: tuple[object, ...],
    receipts: tuple[object, ...],
    bundle: WarehouseW3InstalledAcceptanceBundle | None = None,
) -> None:
    for intent in intents:
        phase = intent.phase
        index = INSTALL_PHASES.index(phase)
        leaf = f"{index:02d}-{phase.value.lower().replace('_', '-')}" ".intent.v1.json"
        path = install / leaf
        path.write_bytes(intent.raw)
        path.chmod(0o444)
    for receipt in receipts:
        phase = receipt.phase
        index = INSTALL_PHASES.index(phase)
        leaf = f"{index:02d}-{phase.value.lower().replace('_', '-')}" ".commit.v2.json"
        path = install / leaf
        path.write_bytes(receipt.raw)
        path.chmod(0o444)
    if bundle is not None:
        chain = verify_w3_installed_replay(
            bundle.installed_replay_inputs,
            bundle.selection_replay_inputs,
        )
        producers = (
            chain.selected_candidate.staged_candidate,
            chain.selected_candidate.root_selection,
            chain.stores_published,
            chain.authority_published,
            chain.projection,
            chain.unit_publication,
            chain.manager_reload,
            chain.prestart_evidence,
            chain.installed_acceptance,
        )
        for phase, producer in zip(INSTALL_PHASES, producers, strict=True):
            path = install / phase.value
            path.write_bytes(producer.raw)
            path.chmod(0o444)
        for leaf, producer in (
            ("CONFIGURED_PAIR_READBACK", chain.configured_pair_readback),
            ("ENVIRONMENT_RELOCATION", chain.environment_relocation),
            ("LOADED_MANAGER", chain.loaded_manager),
        ):
            path = install / leaf
            path.write_bytes(producer.raw)
            path.chmod(0o444)
        path = install / "INSTALLED_REPLAY.v1.json"
        path.write_bytes(bundle.raw)
        path.chmod(0o444)


def _write_transaction_trace(
    import_root: Path,
    bundle: WarehouseW3InstalledAcceptanceBundle,
) -> None:
    chain = verify_w3_installed_replay(
        bundle.installed_replay_inputs,
        bundle.selection_replay_inputs,
    )
    trace = chain.selected_candidate.root_transaction_trace
    path = import_root / root_transaction_trace_leaf(trace.launch_id)
    path.write_bytes(trace.raw)
    path.chmod(0o444)


def test_root_installation_inspection_is_fail_closed_across_phase_windows(
    tmp_path: Path,
    semantic_inputs: dict[str, object],
) -> None:
    values, replay, evidence, installed, intents, receipts = _installed_bundle(
        semantic_inputs
    )
    bundle, _start_bundle, _authorization_raw = _fixed_start_inputs(
        values,
        replay,
        evidence,
        installed,
        intents,
        receipts,
    )
    launch_id = installed.launch_id

    absent = _inspect_w3_root_installation_at(
        tmp_path,
        tmp_path,
        launch_id,
        require_root_owner=False,
    )
    assert absent.state is RootInstallationState.ABSENT
    assert absent.committed_phase_count == 0
    _write_transaction_trace(tmp_path, bundle)

    launch = tmp_path / launch_id
    install = launch / "install"
    install.mkdir(parents=True)
    (launch / "start").mkdir()
    (launch / "terminal").mkdir()
    launch.chmod(0o755)
    install.chmod(0o755)
    (launch / "start").chmod(0o755)
    (launch / "terminal").chmod(0o755)
    empty = _inspect_w3_root_installation_at(
        tmp_path,
        tmp_path,
        launch_id,
        require_root_owner=False,
    )
    assert empty.state is RootInstallationState.PARTIAL_HOLD

    _write_install_phase_ledger(
        install,
        intents=intents[:1],
        receipts=(),
    )
    assert (
        install / "00-root-staging-imported.intent.v1.json"
    ).stat().st_mode & 0o777 == 0o444
    pending = _inspect_w3_root_installation_at(
        tmp_path,
        tmp_path,
        launch_id,
        require_root_owner=False,
    )
    assert pending.state is RootInstallationState.PARTIAL_HOLD
    assert pending.committed_phase_count == 0
    assert pending.pending_phase is RootPhase.ROOT_STAGING_IMPORTED

    _write_install_phase_ledger(
        install,
        intents=(),
        receipts=receipts[:1],
    )
    committed = _inspect_w3_root_installation_at(
        tmp_path,
        tmp_path,
        launch_id,
        require_root_owner=False,
    )
    assert committed.state is RootInstallationState.PARTIAL_HOLD
    assert committed.committed_phase_count == 1
    assert committed.pending_phase is None

    _write_install_phase_ledger(
        install,
        intents=intents[1:],
        receipts=receipts[1:],
        bundle=bundle,
    )
    install.chmod(0o555)
    accepted = _inspect_w3_root_installation_at(
        tmp_path,
        tmp_path,
        launch_id,
        require_root_owner=False,
    )
    assert accepted.state is RootInstallationState.ACCEPTED
    assert accepted.committed_phase_count == 9
    assert accepted.pending_phase is None
    assert accepted.installed_replay_sha256 == bundle.raw_sha256


def test_root_installation_inspection_rejects_unknown_or_incomplete_inventory(
    tmp_path: Path,
    semantic_inputs: dict[str, object],
) -> None:
    values, replay, evidence, installed, intents, receipts = _installed_bundle(
        semantic_inputs
    )
    bundle, _start_bundle, _authorization_raw = _fixed_start_inputs(
        values,
        replay,
        evidence,
        installed,
        intents,
        receipts,
    )
    _write_transaction_trace(tmp_path, bundle)
    launch = tmp_path / installed.launch_id
    install = launch / "install"
    install.mkdir(parents=True)
    (launch / "start").mkdir()
    launch.chmod(0o755)
    install.chmod(0o755)
    (launch / "start").chmod(0o755)
    _write_install_phase_ledger(
        install,
        intents=intents,
        receipts=receipts,
        bundle=bundle,
    )
    install.chmod(0o555)

    missing_terminal = _inspect_w3_root_installation_at(
        tmp_path,
        tmp_path,
        installed.launch_id,
        require_root_owner=False,
    )
    assert missing_terminal.state is RootInstallationState.PARTIAL_HOLD

    install.chmod(0o755)
    unexpected = install / "unexpected.json"
    unexpected.write_bytes(b"{}\n")
    unexpected.chmod(0o444)
    (launch / "terminal").mkdir()
    (launch / "terminal").chmod(0o755)
    install.chmod(0o555)
    unknown = _inspect_w3_root_installation_at(
        tmp_path,
        tmp_path,
        installed.launch_id,
        require_root_owner=False,
    )
    assert unknown.state is RootInstallationState.PARTIAL_HOLD


def test_install_phase_ledger_closes_exact_k0_k8_and_seals_accepted(
    tmp_path: Path,
    semantic_inputs: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values, replay, evidence, installed, intents, receipts = _installed_bundle(
        semantic_inputs
    )
    bundle, _start_bundle, _authorization_raw = _fixed_start_inputs(
        values,
        replay,
        evidence,
        installed,
        intents,
        receipts,
    )
    chain = verify_w3_installed_replay(
        bundle.installed_replay_inputs,
        bundle.selection_replay_inputs,
    )
    _write_transaction_trace(tmp_path, bundle)
    monkeypatch.setattr(external_installation.os, "geteuid", lambda: 0)
    monkeypatch.setattr(coordinator.os, "geteuid", lambda: 0)
    ledger = WarehouseW3InstallPhaseLedger._create_at(
        tmp_path,
        tmp_path,
        chain.selected_candidate,
        require_root_owner=False,
    )
    staging = chain.selected_candidate.root_staging_verification
    candidate_gate = chain.selected_candidate.closure.gate
    authority = staging.authority
    installation = staging.installation
    events: list[str] = []
    identity = chain.manager_reload.manager_identity
    run_properties = dict(chain.loaded_manager.run_properties)
    close_properties = dict(chain.loaded_manager.close_properties)
    run_properties["InvocationID"] = [0] * 16
    close_properties["InvocationID"] = [0] * 16

    class Manager:
        def get_unique_owner(self) -> str:
            return identity.unique_owner

        def get_boot_id(self) -> str:
            return identity.boot_id

        def get_version(self) -> str:
            return identity.version

        def reload(self) -> None:
            events.append("reload")

        def ref_unit(self, unit: str) -> None:
            events.append(f"ref:{unit}")

        def unref_unit(self, unit: str) -> None:
            events.append(f"unref:{unit}")

        def load_unit(self, unit: str) -> str:
            events.append(f"load:{unit}")
            if unit == chain.loaded_manager.run_unit:
                return chain.loaded_manager.run_object_path
            assert unit == chain.loaded_manager.close_unit
            return chain.loaded_manager.close_object_path

        def get_unit(self, unit: str) -> str:
            events.append(f"get:{unit}")
            if unit == chain.loaded_manager.run_unit:
                return chain.loaded_manager.run_object_path
            assert unit == chain.loaded_manager.close_unit
            return chain.loaded_manager.close_object_path

        def read_properties(
            self,
            unit: str,
            names: tuple[str, ...],
        ) -> dict[str, object]:
            events.append(f"read:{unit}")
            source = (
                run_properties
                if unit == chain.loaded_manager.run_unit
                else close_properties
            )
            return {name: source[name] for name in names}

    manager = Manager()
    try:

        def publish_selected_stores(
            selected: object,
            *,
            persist_relocation: object,
        ) -> object:
            assert selected == chain.selected_candidate
            relocation_raw = bundle.installed_replay_inputs.environment_relocation_raw
            assert callable(persist_relocation)
            assert persist_relocation(relocation_raw) == relocation_raw
            assert (
                tmp_path
                / installed.launch_id
                / "install"
                / "02-stores-published.intent.v1.json"
            ).is_file()
            return chain.stores_published

        monkeypatch.setattr(
            coordinator,
            "_publish_w3_selected_stores",
            publish_selected_stores,
        )
        stores = ledger.publish_selected_stores()
        assert stores == chain.stores_published

        def publish_authority_records(
            selected: object,
            runtime_account: object,
        ) -> object:
            assert selected == chain.selected_candidate
            assert runtime_account == chain.runtime_account
            assert (
                tmp_path
                / installed.launch_id
                / "install"
                / "03-authority-published.intent.v1.json"
            ).is_file()
            return chain.authority_published

        monkeypatch.setattr(
            coordinator,
            "_acquire_w3_runtime_account",
            lambda: chain.runtime_account,
        )
        monkeypatch.setattr(
            coordinator,
            "_publish_w3_authority_records",
            publish_authority_records,
        )
        authority_published, runtime_account = ledger.publish_selected_authority(stores)
        assert authority_published == chain.authority_published
        assert runtime_account == chain.runtime_account

        def mount_projection(
            selected: object,
            observed_stores: object,
            observed_authority: object,
            observed_runtime_account: object,
            *,
            boot_id: str,
            namespace_pair: object,
        ) -> object:
            assert selected == chain.selected_candidate
            assert observed_stores == stores
            assert observed_authority == authority_published
            assert observed_runtime_account == runtime_account
            assert boot_id == chain.projection.boot_id
            assert namespace_pair == chain.projection.namespace_pair
            assert (
                tmp_path
                / installed.launch_id
                / "install"
                / "04-projection-mounted.intent.v1.json"
            ).is_file()
            return chain.projection

        monkeypatch.setattr(
            coordinator,
            "_acquire_boot_and_mount_namespace",
            lambda _adapter: (
                chain.projection.boot_id,
                chain.projection.namespace_pair,
            ),
        )
        monkeypatch.setattr(
            coordinator,
            "_mount_w3_projection",
            mount_projection,
        )
        projection = ledger.mount_selected_projection(
            stores_published=stores,
            authority_published=authority_published,
            runtime_account=runtime_account,
        )
        assert projection == chain.projection

        def publish_units(
            selected: object,
            observed_projection: object,
        ) -> object:
            assert selected == chain.selected_candidate
            assert observed_projection == projection
            assert (
                tmp_path
                / installed.launch_id
                / "install"
                / "05-units-published.intent.v1.json"
            ).is_file()
            return chain.unit_publication

        monkeypatch.setattr(
            coordinator,
            "_publish_w3_units",
            publish_units,
        )
        unit_publication = ledger.publish_selected_units(projection)
        assert unit_publication == chain.unit_publication
        assert ledger.phase_intents[2:6] == chain.phase_intents[2:6]
        assert ledger.phase_receipts[2:6] == chain.phase_receipts[2:6]

        manager_reload = ledger.apply_manager_reload_phase(
            manager,
            unit_publication=unit_publication,
        )
        assert manager_reload == chain.manager_reload
        assert ledger.phase_intents[6] == chain.phase_intents[6]
        assert ledger.phase_receipts[6] == chain.phase_receipts[6]

        def acquire_configured_readback(*_args: object, **_kwargs: object) -> object:
            events.append("configured-readback")
            return chain.configured_pair_readback

        def build_prestart_evidence(
            _selected: object,
            **kwargs: object,
        ) -> object:
            assert kwargs["pending_intent"] == chain.phase_intents[7]
            assert kwargs["configured_readback"] == chain.configured_pair_readback
            assert kwargs["loaded_manager"] == chain.loaded_manager
            return chain.prestart_evidence

        monkeypatch.setattr(
            coordinator,
            "_reopen_w3_unit_publications",
            lambda *_args: (b"run\n", b"close\n", None, None),
        )
        monkeypatch.setattr(
            coordinator,
            "_acquire_w3_configured_readback",
            acquire_configured_readback,
        )
        monkeypatch.setattr(
            coordinator,
            "_build_w3_prestart_evidence",
            build_prestart_evidence,
        )
        configured_readback, loaded_manager, prestart_evidence = (
            ledger.load_selected_instances(
                manager,
                stores_published=stores,
                authority_published=authority_published,
                projection=projection,
                unit_publication=unit_publication,
                manager_reload=manager_reload,
                runtime_account=runtime_account,
            )
        )
        assert configured_readback == chain.configured_pair_readback
        assert loaded_manager == chain.loaded_manager
        assert prestart_evidence == chain.prestart_evidence
        assert ledger.phase_intents[7] == chain.phase_intents[7]
        assert ledger.phase_receipts[7] == chain.phase_receipts[7]
        assert events.index("configured-readback") > max(
            index for index, event in enumerate(events) if event.startswith("get:")
        )
        assert events.index("configured-readback") < min(
            index for index, event in enumerate(events) if event.startswith("read:")
        )

        intent, receipt = ledger.accept_installed(chain.installed_acceptance)
        assert intent == chain.phase_intents[8]
        assert receipt == chain.phase_receipts[8]
        before_bundle = _inspect_w3_root_installation_at(
            tmp_path,
            tmp_path,
            installed.launch_id,
            require_root_owner=False,
        )
        assert before_bundle.state is RootInstallationState.PARTIAL_HOLD
        assert before_bundle.committed_phase_count == 9

        accepted = ledger.publish_replay_and_seal(bundle)
        assert accepted.state is RootInstallationState.ACCEPTED
        assert accepted.installed_replay_sha256 == bundle.raw_sha256
        assert (tmp_path / installed.launch_id / "install").stat().st_mode & (
            0o777
        ) == 0o555
    finally:
        ledger.close()


def test_root_selection_prefix_persists_each_intent_before_its_effect(
    tmp_path: Path,
    semantic_inputs: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected, expected_k0_intent, expected_k0, expected_k1_intent, expected_k1 = (
        _selection_bundle(semantic_inputs)
    )
    receipt_root = tmp_path / "quarantine"
    receipt_root.mkdir()
    writer = DurableReceiptDirectory(receipt_root, require_root=False)
    events: list[str] = []
    monkeypatch.setattr(coordinator.os, "geteuid", lambda: 0)
    monkeypatch.setattr(external_installation.os, "geteuid", lambda: 0)

    def import_and_verify() -> object:
        assert (receipt_root / "00-root-staging-imported.intent.v1.json").read_bytes()
        assert not (receipt_root / RootPhase.ROOT_STAGING_IMPORTED.value).exists()
        events.append("import")
        return selected.staged_candidate

    def build_selection(staged: object) -> object:
        assert staged == selected.staged_candidate
        assert (receipt_root / "00-root-staging-imported.commit.v2.json").read_bytes()
        assert not (receipt_root / "01-candidate-selected.intent.v1.json").exists()
        events.append("build-selection")
        return selected

    def publish_selection(root_selection: object) -> bytes:
        assert root_selection == selected
        assert (receipt_root / "01-candidate-selected.intent.v1.json").read_bytes()
        assert not (receipt_root / RootPhase.CANDIDATE_SELECTED.value).exists()
        events.append("publish-selection")
        return selected.raw

    try:
        chain, replay_inputs = _close_w3_root_selection_prefix(
            closure=selected.staged_candidate.root_staging_verification.candidate_gate_closure,
            ingress=selected.staged_candidate.candidate_gate_ingress,
            staging_leaf=selected.staged_candidate.tree_import.staging_leaf,
            trace=selected.root_transaction_trace,
            root_final_absence=selected.root_final_absence,
            writer=writer,
            import_and_verify=import_and_verify,
            build_selection=build_selection,
            publish_selection=publish_selection,
        )
    finally:
        writer.close()

    assert chain.root_selection == selected
    assert chain.root_staging_intent == expected_k0_intent
    assert chain.root_staging_receipt == expected_k0
    assert chain.candidate_selected_intent == expected_k1_intent
    assert chain.candidate_selected_receipt == expected_k1
    assert replay_inputs.root_selection_raw == selected.raw
    assert events == ["import", "build-selection", "publish-selection"]


def test_root_composition_runs_k0_k8_then_independent_loaded_reopen(
    tmp_path: Path,
    semantic_inputs: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values, replay, evidence, installed, intents, receipts = _installed_bundle(
        semantic_inputs
    )
    bundle, _start_bundle, _authorization_raw = _fixed_start_inputs(
        values,
        replay,
        evidence,
        installed,
        intents,
        receipts,
    )
    chain = verify_w3_installed_replay(
        bundle.installed_replay_inputs,
        bundle.selection_replay_inputs,
    )
    _write_transaction_trace(tmp_path, bundle)
    events: list[str] = []

    class Manager:
        pass

    manager = Manager()

    class Ledger:
        def publish_selected_stores(self) -> object:
            events.append("K2")
            return chain.stores_published

        def publish_selected_authority(self, stores: object) -> tuple[object, object]:
            assert stores == chain.stores_published
            events.append("K3")
            return chain.authority_published, chain.runtime_account

        def mount_selected_projection(self, **kwargs: object) -> object:
            assert kwargs["stores_published"] == chain.stores_published
            events.append("K4")
            return chain.projection

        def publish_selected_units(self, projection: object) -> object:
            assert projection == chain.projection
            events.append("K5")
            return chain.unit_publication

        def apply_manager_reload_phase(
            self,
            observed_manager: object,
            *,
            unit_publication: object,
        ) -> object:
            assert observed_manager is manager
            assert unit_publication == chain.unit_publication
            events.append("K6")
            return chain.manager_reload

        def load_selected_instances(
            self,
            observed_manager: object,
            **kwargs: object,
        ) -> tuple[object, object, object]:
            assert observed_manager is manager
            assert kwargs["manager_reload"] == chain.manager_reload
            events.append("K7")
            return (
                chain.configured_pair_readback,
                chain.loaded_manager,
                chain.prestart_evidence,
            )

        def accept_and_seal_selected(
            self,
            selection_inputs: object,
            **_kwargs: object,
        ) -> tuple[object, object]:
            assert selection_inputs == bundle.selection_replay_inputs
            events.append("K8")
            return (
                coordinator.WarehouseW3RootInstallationInspection(
                    launch_id=installed.launch_id,
                    state=RootInstallationState.ACCEPTED,
                    committed_phase_count=len(INSTALL_PHASES),
                    pending_phase=None,
                    installed_replay_sha256=bundle.raw_sha256,
                ),
                bundle,
            )

        def close(self) -> None:
            events.append("close")

    class InstalledAuthority:
        def __init__(self) -> None:
            self.bundle = bundle

        def __enter__(self) -> "InstalledAuthority":
            events.append("independent-reopen")
            return self

        def __exit__(self, *_args: object) -> None:
            events.append("independent-close")

    monkeypatch.setattr(coordinator.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        coordinator,
        "begin_w3_root_installation",
        lambda _candidate, *, source_acceptance_path: (
            Ledger(),
            bundle.selection_replay_inputs,
        ),
    )
    monkeypatch.setattr(coordinator, "SystemdExternalManager", lambda: manager)
    monkeypatch.setattr(
        coordinator,
        "verify_installed_w3",
        lambda launch_id: (
            InstalledAuthority()
            if launch_id == installed.launch_id
            else pytest.fail("launch differs")
        ),
    )

    result = coordinator.apply_w3_root_installation(
        tmp_path / "candidate",
        source_acceptance_path=tmp_path / "source-acceptance.json",
    )

    assert result.state is RootInstallationState.ACCEPTED
    assert events == [
        "K2",
        "K3",
        "K4",
        "K5",
        "K6",
        "K7",
        "K8",
        "close",
        "independent-reopen",
        "independent-close",
    ]


def test_root_layout_is_fresh_exact_and_collision_is_permanent_hold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "var" / "lib"
    parent.mkdir(parents=True)
    monkeypatch.setattr(external_linux.os, "geteuid", lambda: 0)

    _initialize_w3_root_layout_at(
        parent,
        uid=coordinator.os.getuid(),
        gid=coordinator.os.getgid(),
        require_root_owner=False,
    )

    scion_root = parent / "scion"
    expected = {
        "acceptances",
        "authorities",
        "environments",
        "imports",
        "installations",
        "projections",
        "runs",
        "sealed",
        "selections",
        "source-acceptances",
    }
    assert {path.name for path in scion_root.iterdir()} == expected
    assert all(
        (scion_root / name / "w3").is_dir()
        and (scion_root / name / "w3").stat().st_mode & 0o777 == 0o755
        for name in expected
    )
    _verify_w3_root_layout_at(
        parent,
        uid=coordinator.os.getuid(),
        gid=coordinator.os.getgid(),
        require_root_owner=False,
    )

    with pytest.raises(
        WarehouseW3RootCoordinatorError,
        match="permanent hold",
    ):
        _initialize_w3_root_layout_at(
            parent,
            uid=coordinator.os.getuid(),
            gid=coordinator.os.getgid(),
            require_root_owner=False,
        )
    assert {path.name for path in scion_root.iterdir()} == expected


def test_root_layout_ensure_initializes_only_from_total_absence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "var" / "lib"
    parent.mkdir(parents=True)
    calls: list[str] = []
    monkeypatch.setattr(coordinator, "_SCION_ROOT_PARENT", parent)
    monkeypatch.setattr(coordinator.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        coordinator,
        "_initialize_w3_root_layout",
        lambda: calls.append("initialize"),
    )
    monkeypatch.setattr(
        coordinator,
        "_verify_w3_root_layout_at",
        lambda *_args, **_kwargs: calls.append("verify"),
    )

    coordinator._ensure_w3_root_layout()
    assert calls == ["initialize"]

    (parent / "scion").mkdir()
    coordinator._ensure_w3_root_layout()
    assert calls == ["initialize", "verify"]


def test_install_phase_effect_failure_is_permanent_pending_hold(
    tmp_path: Path,
    semantic_inputs: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values, replay, evidence, installed, intents, receipts = _installed_bundle(
        semantic_inputs
    )
    bundle, _start_bundle, _authorization_raw = _fixed_start_inputs(
        values,
        replay,
        evidence,
        installed,
        intents,
        receipts,
    )
    chain = verify_w3_installed_replay(
        bundle.installed_replay_inputs,
        bundle.selection_replay_inputs,
    )
    _write_transaction_trace(tmp_path, bundle)
    monkeypatch.setattr(external_installation.os, "geteuid", lambda: 0)
    ledger = WarehouseW3InstallPhaseLedger._create_at(
        tmp_path,
        tmp_path,
        chain.selected_candidate,
        require_root_owner=False,
    )
    with pytest.raises(RuntimeError, match="effect failed"):
        ledger.apply_phase(
            RootPhase.STORES_PUBLISHED,
            effect_authority_sha256=(chain.phase_intents[2].effect_authority_sha256),
            apply_effect=lambda: (_ for _ in ()).throw(RuntimeError("effect failed")),
            reopen_effect=lambda: chain.stores_published.raw,
        )
    ledger.close()

    held = _inspect_w3_root_installation_at(
        tmp_path,
        tmp_path,
        installed.launch_id,
        require_root_owner=False,
    )
    assert held.state is RootInstallationState.PARTIAL_HOLD
    assert held.committed_phase_count == 2
    assert held.pending_phase is RootPhase.STORES_PUBLISHED
    with pytest.raises(
        WarehouseW3RootCoordinatorError,
        match="launch slot is not absent",
    ):
        WarehouseW3InstallPhaseLedger._create_at(
            tmp_path,
            tmp_path,
            chain.selected_candidate,
            require_root_owner=False,
        )


def test_fixed_start_authorization_retains_named_file_authority(
    tmp_path: Path,
    semantic_inputs: dict[str, object],
) -> None:
    values, replay, evidence, installed, intents, receipts = _installed_bundle(
        semantic_inputs
    )
    _installed_bundle_receipt, bundle, raw = _fixed_start_inputs(
        values,
        replay,
        evidence,
        installed,
        intents,
        receipts,
    )
    start = tmp_path / "start"
    start.mkdir()
    path = start / "START_AUTHORIZED"
    path.write_bytes(raw)
    path.chmod(0o444)
    bundle_path = start / "START_GATE_INPUTS.v1.json"
    bundle_path.write_bytes(bundle.raw)
    bundle_path.chmod(0o444)
    with pin_absolute_directory(str(start)) as pinned:
        authority = _FixedStartAuthorizationAuthority._acquire_from_start(
            pinned,
            require_root_owner=False,
        )
    try:
        assert authority.authorization.raw == raw
        path.unlink()
        path.write_bytes(raw)
        path.chmod(0o444)
        with pytest.raises(
            WarehouseW3RootCoordinatorError,
            match="authority drifted",
        ):
            authority.revalidate()
    finally:
        authority.close()


def test_start_w3_rejects_partial_root_ledger_before_authority_or_manager(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launch_id = "a" * 64
    monkeypatch.setattr(coordinator.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        coordinator,
        "inspect_w3_root_installation",
        lambda requested: coordinator.WarehouseW3RootInstallationInspection(
            launch_id=requested,
            state=RootInstallationState.PARTIAL_HOLD,
            committed_phase_count=7,
            pending_phase=RootPhase.INSTANCES_LOADED,
            installed_replay_sha256=None,
        ),
    )
    monkeypatch.setattr(
        _FixedStartAuthorizationAuthority,
        "acquire",
        classmethod(
            lambda cls, requested: (_ for _ in ()).throw(
                AssertionError("start authority must not be acquired")
            )
        ),
    )
    monkeypatch.setattr(
        coordinator,
        "SystemdExternalManager",
        lambda: (_ for _ in ()).throw(AssertionError("manager must not be acquired")),
    )

    with pytest.raises(
        WarehouseW3RootCoordinatorError,
        match="root installation is not accepted",
    ):
        start_w3(launch_id)


def test_start_w3_spends_one_authorization_and_dispatches_once(
    tmp_path: Path,
    semantic_inputs: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values, replay, evidence, installed, intents, receipts = _installed_bundle(
        semantic_inputs
    )
    bundle, start_bundle, authorization_raw = _fixed_start_inputs(
        values,
        replay,
        evidence,
        installed,
        intents,
        receipts,
    )
    launch_id = installed.launch_id
    launch = tmp_path / launch_id
    install = launch / "install"
    start = launch / "start"
    install.mkdir(parents=True)
    start.mkdir()
    installed_path = install / "INSTALLED_REPLAY.v1.json"
    installed_path.write_bytes(bundle.raw)
    installed_path.chmod(0o444)
    authorization_path = start / "START_AUTHORIZED"
    authorization_path.write_bytes(authorization_raw)
    authorization_path.chmod(0o444)
    start_bundle_path = start / "START_GATE_INPUTS.v1.json"
    start_bundle_path.write_bytes(start_bundle.raw)
    start_bundle_path.chmod(0o444)

    with pin_absolute_directory(str(install)) as pinned_install:
        installed_authority = RootInstalledAcceptanceAuthority._acquire_for_test(
            pinned_install,
            expected_launch_id=launch_id,
        )

    events: list[str] = []
    manager_identity = installed_authority.chain.loaded_manager.manager_identity

    class Manager:
        def get_unique_owner(self) -> str:
            return manager_identity.unique_owner

        def get_boot_id(self) -> str:
            return manager_identity.boot_id

        def get_version(self) -> str:
            return manager_identity.version

        def ref_unit(self, unit: str) -> None:
            events.append(f"ref:{unit}")

        def unref_unit(self, unit: str) -> None:
            events.append(f"unref:{unit}")

        def start_unit(self, unit: str, mode: str) -> str:
            events.append(f"start:{unit}:{mode}")
            return "/org/freedesktop/systemd1/job/42"

    manager = Manager()
    monkeypatch.setattr(coordinator.os, "geteuid", lambda: 0)
    monkeypatch.setattr(external_installation.os, "geteuid", lambda: 0)
    monkeypatch.setattr(coordinator, "_ACCEPTANCE_ROOT", tmp_path)
    monkeypatch.setattr(
        coordinator,
        "inspect_w3_root_installation",
        lambda requested: coordinator.WarehouseW3RootInstallationInspection(
            launch_id=requested,
            state=RootInstallationState.ACCEPTED,
            committed_phase_count=len(INSTALL_PHASES),
            pending_phase=None,
            installed_replay_sha256=bundle.raw_sha256,
        ),
    )
    monkeypatch.setattr(coordinator, "SystemdExternalManager", lambda: manager)
    monkeypatch.setattr(
        coordinator,
        "_verify_installed_authority",
        lambda authority, current_manager: (
            authority.chain.loaded_manager
            if current_manager is manager
            else (_ for _ in ()).throw(AssertionError("manager differs"))
        ),
    )
    monkeypatch.setattr(
        coordinator,
        "_revalidate_installed_source_acceptance",
        lambda authority: None,
    )
    monkeypatch.setattr(
        installed_replay,
        "verify_live_w3_publications",
        lambda *_args, **_kwargs: events.append("gate:publications"),
    )
    monkeypatch.setattr(
        coordinator,
        "verify_live_w3_publications",
        lambda *_args, **_kwargs: events.append("adjacent:publications"),
    )
    monkeypatch.setattr(
        coordinator,
        "verify_live_w3_loaded_manager",
        lambda *_args, **_kwargs: (
            events.append("adjacent:loaded"),
            installed_authority.chain.loaded_manager,
        )[-1],
    )
    gate_results = (
        (
            "loaded",
            "verify_live_w3_loaded_manager",
            installed_authority.chain.loaded_manager,
        ),
        (
            "projection",
            "verify_live_w3_projection",
            installed_authority.chain.projection,
        ),
        (
            "environment",
            "verify_live_w3_environment",
            installed_authority.chain.environment_rehash,
        ),
        (
            "dry-root",
            "verify_live_w3_dry_root",
            installed_authority.chain.dry_root,
        ),
        (
            "absence",
            "verify_live_w3_prestart_absence",
            installed_authority.chain.prestart_absence,
        ),
        (
            "account",
            "verify_live_w3_runtime_account",
            installed_authority.chain.runtime_account,
        ),
    )
    for label, name, result in gate_results:
        monkeypatch.setattr(
            installed_replay,
            name,
            lambda *_args, _label=label, _result=result, **_kwargs: (
                events.append(f"gate:{_label}"),
                _result,
            )[-1],
        )
    monkeypatch.setattr(
        RootInstalledAcceptanceAuthority,
        "acquire",
        classmethod(
            lambda cls, requested: (
                installed_authority
                if requested == launch_id
                else (_ for _ in ()).throw(AssertionError("launch differs"))
            )
        ),
    )

    def acquire_authorization(
        cls: type[_FixedStartAuthorizationAuthority],
        requested: str,
    ) -> _FixedStartAuthorizationAuthority:
        assert requested == launch_id
        with pin_absolute_directory(str(start)) as pinned_start:
            return cls._acquire_from_start(
                pinned_start,
                require_root_owner=False,
            )

    monkeypatch.setattr(
        _FixedStartAuthorizationAuthority,
        "acquire",
        classmethod(acquire_authorization),
    )
    monkeypatch.setattr(
        _FixedStartAuthorizationAuthority,
        "seal_start_directory",
        lambda self: events.append("sealed"),
    )
    monkeypatch.setattr(
        coordinator,
        "DurableReceiptDirectory",
        lambda path: DurableReceiptDirectory(path, require_root=False),
    )

    receipt = start_w3(launch_id)

    assert receipt.state is StartDispatchState.RETURNED
    assert json.loads((start / "START_ISSUED").read_bytes())["method"] == ("StartUnit")
    assert (start / "START_RETURNED").read_bytes() == receipt.raw
    assert events == [
        "gate:publications",
        "gate:loaded",
        "gate:publications",
        "gate:projection",
        "gate:environment",
        "gate:dry-root",
        "gate:absence",
        "gate:account",
        "gate:publications",
        "gate:loaded",
        "adjacent:publications",
        "adjacent:loaded",
        f"ref:{values['installation'].run_unit}",
        f"start:{values['installation'].run_unit}:fail",
        f"unref:{values['installation'].run_unit}",
        "sealed",
    ]
