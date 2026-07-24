from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import scion.problems.warehouse_delivery.w3_composition as composition
import scion.tools.scion_w3_tool as installed_tool
from scion.problems.warehouse_delivery.w3_composition import (
    EXPECTED_ARTIFACT_NAMES,
    EXPECTED_CORRECTION_DESIGN_SHA256,
    EXPECTED_MANIFEST_SHA256,
    EXPECTED_NATIVE_ACCEPTANCE_CONTRACT_SHA256,
    EXPECTED_NATIVE_ACCEPTANCE_RECORD_SHA256,
    EXPECTED_NONCE_LEDGER_PARENT,
    EXPECTED_SOURCE_COMMIT,
    EXPECTED_SCIENTIFIC_DESIGN_SHA256,
    WarehouseW3CompositionError,
    configured_pair_for_installation,
    dispatch_installed_launch,
    inspect_w3_launch_readiness,
    prepare_w3_invocation,
)
from scion.problems.warehouse_delivery.w3_start_gate import (
    WarehouseW3EnvironmentIntegrityRefused,
    WarehouseW3InstalledIdentityRefused,
    WarehouseW3StartPermitRefused,
    WarehouseW3SystemdLineageRefused,
)
from scion.runtime.execution.systemd255 import (
    ConfiguredUnitProperties,
    UnitRole,
)
from scion.runtime.execution.systemd_acquisition import (
    ConfiguredPairFact,
    parse_unit_template,
)

ACCEPTED_ROOT = Path(
    "/home/clawd/research/scion-experiments/"
    "v04-warehouse-w3-problem-source-dry-20260722T234345Z-claw"
)
LAUNCH_ID = "4" * 64
NONCE = "3" * 64


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def _templates() -> tuple[bytes, bytes]:
    base = (
        Path(__file__).resolve().parents[4]
        / "problems"
        / "warehouse_delivery"
        / "systemd"
    )
    return (
        (base / "scion-w3@.service").read_bytes(),
        (base / "scion-w3-close@.service").read_bytes(),
    )


def _pair() -> ConfiguredPairFact:
    run_unit = f"scion-w3@{LAUNCH_ID}.service"
    close_unit = f"scion-w3-close@{LAUNCH_ID}.service"
    run = ConfiguredUnitProperties.from_receipts(
        UnitRole.RUN,
        {
            "Delegate": "pids",
            "DelegateSubgroup": "supervisor",
            "CollectMode": "inactive",
            "Restart": "no",
            "KillMode": "control-group",
            "TimeoutStopSec": "infinity",
            "OnSuccess": close_unit,
            "OnFailure": close_unit,
        },
        {
            "Id": run_unit,
            "Delegate": "yes",
            "DelegateControllers": "pids",
            "DelegateSubgroup": "supervisor",
            "CollectMode": "inactive",
            "Restart": "no",
            "KillMode": "control-group",
            "TimeoutStopUSec": "infinity",
            "OnSuccess": close_unit,
            "OnFailure": close_unit,
        },
        expected_unit=run_unit,
        expected_peer=close_unit,
    )
    closer = ConfiguredUnitProperties.from_receipts(
        UnitRole.CLOSER,
        {
            "CollectMode": "inactive",
            "Restart": "no",
            "TimeoutStartSec": "infinity",
            "After": run_unit,
        },
        {
            "Id": close_unit,
            "CollectMode": "inactive",
            "Restart": "no",
            "TimeoutStartUSec": "infinity",
            "After": run_unit,
        },
        expected_unit=close_unit,
        expected_peer=run_unit,
    )
    return ConfiguredPairFact.create(run, closer)


def test_configured_pair_is_derived_from_exact_unit_templates() -> None:
    run_template, close_template = _templates()

    pair = configured_pair_for_installation(
        LAUNCH_ID,
        parse_unit_template(run_template),
        parse_unit_template(close_template),
    )

    assert pair == _pair()
    assert pair.run.unit == f"scion-w3@{LAUNCH_ID}.service"
    assert pair.closer.unit == f"scion-w3-close@{LAUNCH_ID}.service"


def _records(
    run_template: bytes,
    close_template: bytes,
    *,
    source_commit: str = EXPECTED_SOURCE_COMMIT,
    artifact_names: tuple[str, ...] = EXPECTED_ARTIFACT_NAMES,
) -> tuple[bytes, bytes]:
    manifest = ACCEPTED_ROOT / "warehouse_w3_fixed_arm_manifest.v1.json"
    manifest_bytes = manifest.read_bytes()
    composition = (
        Path(__file__).resolve().parents[4]
        / "problems"
        / "warehouse_delivery"
        / "w3_composition.py"
    ).read_bytes()
    tool = (
        Path(__file__).resolve().parents[4] / "tools" / "scion_w3_tool.py"
    ).read_bytes()
    package_root = Path(__file__).resolve().parents[4]
    project_root = package_root.parent
    launch_paths = (
        package_root / "problems" / "warehouse_delivery" / "w2_preservation.py",
        package_root / "problems" / "warehouse_delivery" / "w3_counter_fixtures.py",
        package_root / "problems" / "warehouse_delivery" / "w3_composition.py",
        package_root / "problems" / "warehouse_delivery" / "w3_candidate_gate.py",
        package_root / "problems" / "warehouse_delivery" / "w3_candidate_ingress.py",
        package_root
        / "problems"
        / "warehouse_delivery"
        / "w3_candidate_coordinator.py",
        package_root / "problems" / "warehouse_delivery" / "w3_environment.py",
        package_root / "problems" / "warehouse_delivery" / "w3_environment_receipts.py",
        package_root / "problems" / "warehouse_delivery" / "w3_installation.py",
        package_root / "problems" / "warehouse_delivery" / "w3_installed_replay.py",
        package_root / "problems" / "warehouse_delivery" / "w3_prestart_facts.py",
        package_root / "problems" / "warehouse_delivery" / "w3_root_coordinator.py",
        package_root / "problems" / "warehouse_delivery" / "w3_root_installation.py",
        package_root / "problems" / "warehouse_delivery" / "w3_root_selection.py",
        package_root / "problems" / "warehouse_delivery" / "w3_root_staging.py",
        package_root / "problems" / "warehouse_delivery" / "w3_start_authorization.py",
        package_root / "problems" / "warehouse_delivery" / "w3_start_gate.py",
        package_root / "problems" / "warehouse_delivery" / "w3_start_store.py",
        package_root / "problems" / "warehouse_delivery" / "w3_terminal_acceptance.py",
        package_root / "problems" / "warehouse_delivery" / "w3_terminal_manager.py",
        package_root / "problems" / "warehouse_delivery" / "w3_wheel.py",
        package_root / "tools" / "scion_w3_tool.py",
        package_root / "tools" / "scion_w3_install.py",
        package_root
        / "problems"
        / "warehouse_delivery"
        / "systemd"
        / "scion-w3@.service",
        package_root
        / "problems"
        / "warehouse_delivery"
        / "systemd"
        / "scion-w3-close@.service",
        package_root / "runtime" / "execution" / "launch_authority.py",
        package_root / "runtime" / "execution" / "systemd_acquisition.py",
        package_root / "runtime" / "execution" / "invocation_terminal.py",
        package_root / "runtime" / "execution" / "spawn_backend.py",
        package_root / "runtime" / "execution" / "cgroup_v2.py",
        package_root / "runtime" / "execution" / "environment_integrity.py",
        package_root / "runtime" / "execution" / "external_installation.py",
        package_root / "runtime" / "execution" / "external_linux.py",
        package_root / "runtime" / "execution" / "systemd255.py",
        package_root / "runtime" / "execution" / "model.py",
        package_root / "problems" / "warehouse_delivery" / "w3_fixed_arm.py",
        package_root / "problems" / "warehouse_delivery" / "w3_validation.py",
        package_root / "problems" / "warehouse_delivery" / "w3_analysis.py",
    )
    manifest_stat = manifest.stat()
    inputs = [
        {
            "logical_path": ("warehouse_w3_fixed_arm_manifest.v1.json"),
            "sealed_path": ("sealed/warehouse_w3_fixed_arm_manifest.v1.json"),
            "sha256": EXPECTED_MANIFEST_SHA256,
            "size_bytes": len(manifest_bytes),
            "provenance": {
                "kind": "external_evidence",
                "source_path": str(manifest),
                "device": manifest_stat.st_dev,
                "inode": manifest_stat.st_ino,
            },
        }
    ]
    for path in launch_paths:
        logical = str(path.relative_to(project_root))
        data = path.read_bytes()
        inputs.append(
            {
                "logical_path": logical,
                "sealed_path": f"sealed/repository/{logical}",
                "sha256": hashlib.sha256(data).hexdigest(),
                "size_bytes": len(data),
                "provenance": {
                    "kind": "git_blob",
                    "commit": source_commit,
                    "path": logical,
                    "blob_oid": "5" * 40,
                },
            }
        )
    inputs.sort(key=lambda item: item["sealed_path"].encode("utf-8"))
    authority_value = {
        "schema": "scion.generic-launch-authority.v1",
        "problem_kind": "warehouse-w3",
        "source_commit": source_commit,
        "source_tree": "2" * 40,
        "manifest": {
            "path": "warehouse_w3_fixed_arm_manifest.v1.json",
            "sha256": EXPECTED_MANIFEST_SHA256,
            "size_bytes": len(manifest_bytes),
        },
        "root_basename": ACCEPTED_ROOT.name,
        "nonce": NONCE,
        "nonce_ledger_parent": EXPECTED_NONCE_LEDGER_PARENT,
        "expected_rows": 172,
        "artifact_names": list(artifact_names),
        "scientific_design_sha256": (EXPECTED_SCIENTIFIC_DESIGN_SHA256),
        "correction_design_sha256": (EXPECTED_CORRECTION_DESIGN_SHA256),
        "native_acceptance_contract_sha256": (
            EXPECTED_NATIVE_ACCEPTANCE_CONTRACT_SHA256
        ),
        "native_acceptance_record_sha256": (EXPECTED_NATIVE_ACCEPTANCE_RECORD_SHA256),
        "sealed_store_aggregate_sha256": "6" * 64,
        "environment_receipt_sha256": "7" * 64,
        "run_template_sha256": hashlib.sha256(run_template).hexdigest(),
        "close_template_sha256": hashlib.sha256(close_template).hexdigest(),
        "guardian_source_sha256": hashlib.sha256(composition).hexdigest(),
        "thin_tool_source_sha256": hashlib.sha256(tool).hexdigest(),
        "closer_source_sha256": hashlib.sha256(composition).hexdigest(),
        "inputs": inputs,
        "retry": False,
        "resume": False,
        "reuse": False,
    }
    authority_raw = _canonical(authority_value)
    authority_sha = hashlib.sha256(authority_raw).hexdigest()
    pair = _pair()
    installation = {
        "schema": "scion.generic-launch-installation.v1",
        "launch_id": LAUNCH_ID,
        "authority_sha256": authority_sha,
        "authority_path": (f"/var/lib/scion/authorities/w3/{authority_sha}.json"),
        "problem_kind": "warehouse-w3",
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "run_root": str(ACCEPTED_ROOT),
        "terminal_root": str(ACCEPTED_ROOT / "control" / "invocation"),
        "nonce": NONCE,
        "nonce_ledger_parent": EXPECTED_NONCE_LEDGER_PARENT,
        "sealed_root": (f"/var/lib/scion/sealed/w3/{EXPECTED_MANIFEST_SHA256}"),
        "sealed_store_aggregate_sha256": "6" * 64,
        "environment_root": ("/var/lib/scion/environments/w3/" + "7" * 64),
        "environment_receipt_sha256": "7" * 64,
        "projection_root": (f"/var/lib/scion/projections/w3/{LAUNCH_ID}"),
        "run_template_sha256": hashlib.sha256(run_template).hexdigest(),
        "close_template_sha256": hashlib.sha256(close_template).hexdigest(),
        "run_unit": f"scion-w3@{LAUNCH_ID}.service",
        "close_unit": f"scion-w3-close@{LAUNCH_ID}.service",
        "configured_pair": pair.to_mapping(),
        "configured_pair_sha256": pair.configured_pair_sha256,
        "retry": False,
        "resume": False,
        "reuse": False,
    }
    return authority_raw, _canonical(installation)


def test_real_accepted_root_composition_is_read_only_and_install_locked() -> None:
    run_template, close_template = _templates()
    authority, installation = _records(
        run_template,
        close_template,
    )
    before = (ACCEPTED_ROOT / "warehouse_w3_fixed_arm_manifest.v1.json").stat()
    fact = inspect_w3_launch_readiness(
        ACCEPTED_ROOT,
        authority,
        installation,
        run_template,
        close_template,
    )
    after = (ACCEPTED_ROOT / "warehouse_w3_fixed_arm_manifest.v1.json").stat()

    assert fact.state == ("COMPOSITION_READY_EXTERNAL_INSTALLATION_REQUIRED")
    assert fact.external_installation_required is True
    assert fact.formal_execution_authorized is False
    assert fact.filesystem_mutated is False
    assert fact.terminal_policy.expected_rows == 172
    assert fact.terminal_policy.artifact_names == EXPECTED_ARTIFACT_NAMES
    assert (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) == (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    )
    assert not (ACCEPTED_ROOT / "control" / "invocation").exists()
    with pytest.raises(
        WarehouseW3CompositionError,
        match="installation acceptance",
    ):
        prepare_w3_invocation(fact)


def test_composition_rejects_semantic_exec_stop_post_drift_even_when_hashed() -> None:
    run_template, close_template = _templates()
    drifted = run_template.replace(
        b"seal-unit-drained %i",
        b"close %i",
    )
    authority, installation = _records(drifted, close_template)

    with pytest.raises(
        WarehouseW3CompositionError,
        match="semantic wiring differs",
    ):
        inspect_w3_launch_readiness(
            ACCEPTED_ROOT,
            authority,
            installation,
            drifted,
            close_template,
        )


def test_composition_rejects_artifact_authority_drift() -> None:
    run_template, close_template = _templates()
    authority, installation = _records(
        run_template,
        close_template,
        artifact_names=("wrong.json", *EXPECTED_ARTIFACT_NAMES[1:]),
    )
    with pytest.raises(
        WarehouseW3CompositionError,
        match="identity differs",
    ):
        inspect_w3_launch_readiness(
            ACCEPTED_ROOT,
            authority,
            installation,
            run_template,
            close_template,
        )


def test_thin_dispatch_has_closed_command_and_launch_id_surface() -> None:
    with pytest.raises(WarehouseW3CompositionError, match="unknown"):
        dispatch_installed_launch("retry", LAUNCH_ID)
    with pytest.raises(WarehouseW3CompositionError, match="launch id"):
        dispatch_installed_launch("run", "not-a-launch")
    with pytest.raises(
        WarehouseW3InstalledIdentityRefused,
        match="installed launch materials",
    ):
        dispatch_installed_launch("run", LAUNCH_ID)


def test_run_material_loader_failure_maps_to_installed_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(
        _launch_id: str,
        *,
        require_claim: bool,
    ) -> object:
        assert require_claim is False
        raise WarehouseW3CompositionError("drifted material")

    monkeypatch.setattr(composition, "_installed_materials", fail)

    with pytest.raises(
        WarehouseW3InstalledIdentityRefused,
        match="installed launch materials",
    ):
        dispatch_installed_launch("run", LAUNCH_ID)


def test_thin_dispatch_routes_only_three_fixed_installed_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    materials = object()
    calls: list[tuple[str, object]] = []

    def load(
        launch_id: str,
        *,
        require_claim: bool,
    ) -> object:
        assert launch_id == LAUNCH_ID
        calls.append(("load-claimed" if require_claim else "load", materials))
        return materials

    monkeypatch.setattr(composition, "_installed_materials", load)
    monkeypatch.setattr(
        composition,
        "_run_installed",
        lambda value: calls.append(("run", value)),
    )
    monkeypatch.setattr(
        composition,
        "_seal_installed_unit_drained",
        lambda value: calls.append(("seal", value)),
    )
    monkeypatch.setattr(
        composition,
        "_close_installed",
        lambda value: calls.append(("close", value)),
    )

    dispatch_installed_launch("run", LAUNCH_ID)
    dispatch_installed_launch("seal-unit-drained", LAUNCH_ID)
    dispatch_installed_launch("close", LAUNCH_ID)

    assert calls == [
        ("load", materials),
        ("run", materials),
        ("load-claimed", materials),
        ("seal", materials),
        ("load-claimed", materials),
        ("close", materials),
    ]


def test_live_issued_gate_binds_fixed_store_to_current_manager(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scion.problems.warehouse_delivery.w3_start_store as start_store

    materials = SimpleNamespace(
        authority=SimpleNamespace(authority_sha256="1" * 64),
        installation=SimpleNamespace(
            launch_id=LAUNCH_ID,
            installation_sha256="2" * 64,
            run_unit=f"scion-w3@{LAUNCH_ID}.service",
        ),
    )
    manager = SimpleNamespace(
        unique_owner=":1.42",
        boot_id="12345678-1234-1234-1234-123456789abc",
        version="255.4-1ubuntu8",
    )
    acquirer = SimpleNamespace(acquire_manager_identity=lambda: manager)
    gate = SimpleNamespace(
        manager_unique_owner=manager.unique_owner,
        boot_id=manager.boot_id,
        manager_version=manager.version,
    )
    observed: dict[str, object] = {}

    context = SimpleNamespace(gate=gate)

    def acquire(**kwargs: object) -> object:
        observed.update(kwargs)
        return context

    monkeypatch.setattr(start_store, "acquire_w3_issued_start_gate", acquire)

    result = composition._require_live_issued_start_gate(
        materials,
        acquirer,
        SimpleNamespace(boot_id=manager.boot_id),
    )

    assert result is context
    assert observed == {
        "expected_launch_id": LAUNCH_ID,
        "expected_authority_sha256": "1" * 64,
        "expected_installation_sha256": "2" * 64,
        "expected_unit": f"scion-w3@{LAUNCH_ID}.service",
    }

    gate.manager_unique_owner = ":1.99"
    with pytest.raises(
        WarehouseW3SystemdLineageRefused,
        match="live systemd manager",
    ):
        composition._require_live_issued_start_gate(
            materials,
            acquirer,
            SimpleNamespace(boot_id=manager.boot_id),
        )


def test_installed_run_consumes_issued_gate_before_nonce_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class GateStop(RuntimeError):
        pass

    events: list[str] = []
    lineage = SimpleNamespace(boot_id="12345678-1234-1234-1234-123456789abc")
    acquirer = SimpleNamespace(acquire_self_lineage=lambda **_kwargs: lineage)
    materials = SimpleNamespace(
        installation=SimpleNamespace(
            run_unit=f"scion-w3@{LAUNCH_ID}.service",
        )
    )
    monkeypatch.setattr(
        composition,
        "SystemdDbusPropertyReader",
        lambda: object(),
    )
    monkeypatch.setattr(
        composition,
        "Systemd255Acquirer",
        lambda _reader: acquirer,
    )
    monkeypatch.setattr(
        composition,
        "_live_configured_pair",
        lambda *_args: object(),
    )
    monkeypatch.setattr(
        composition,
        "_systemd_environment",
        lambda *_args: {"INVOCATION_ID": "a" * 32},
    )

    def stop_at_gate(*_args: object) -> None:
        events.append("issued-gate")
        raise GateStop

    monkeypatch.setattr(
        composition,
        "_require_live_issued_start_gate",
        stop_at_gate,
    )
    monkeypatch.setattr(
        composition,
        "inspect_w3_launch_readiness",
        lambda *_args, **_kwargs: events.append("readiness"),
    )
    monkeypatch.setattr(
        composition,
        "prepare_w3_invocation",
        lambda *_args: events.append("nonce"),
    )

    with pytest.raises(GateStop):
        composition._run_installed(materials)

    assert events == ["issued-gate"]


def test_installed_run_does_not_classify_prepare_mutation_failure_as_72(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = SimpleNamespace(
        unique_owner=":1.42",
        boot_id="12345678-1234-1234-1234-123456789abc",
        version="255.4-1ubuntu8",
    )
    lineage = SimpleNamespace(
        boot_id=manager.boot_id,
        invocation_id="a" * 32,
    )
    context = SimpleNamespace(
        gate=SimpleNamespace(
            manager_unique_owner=manager.unique_owner,
            boot_id=manager.boot_id,
            manager_version=manager.version,
        ),
        verify_environment=lambda _phase: None,
        close=lambda: None,
    )
    acquirer = SimpleNamespace(
        acquire_manager_identity=lambda: manager,
        acquire_self_lineage=lambda **_kwargs: lineage,
    )
    materials = SimpleNamespace(
        authority=SimpleNamespace(raw=b"authority"),
        installation=SimpleNamespace(
            raw=b"installation",
            run_root="/run/scion",
            run_unit=f"scion-w3@{LAUNCH_ID}.service",
        ),
        run_template_raw=b"run",
        close_template_raw=b"close",
    )
    monkeypatch.setattr(
        composition,
        "SystemdDbusPropertyReader",
        lambda: object(),
    )
    monkeypatch.setattr(
        composition,
        "Systemd255Acquirer",
        lambda _reader: acquirer,
    )
    monkeypatch.setattr(
        composition,
        "_live_configured_pair",
        lambda *_args: object(),
    )
    monkeypatch.setattr(
        composition,
        "_systemd_environment",
        lambda *_args: {"INVOCATION_ID": lineage.invocation_id},
    )
    monkeypatch.setattr(
        composition,
        "_require_live_issued_start_gate",
        lambda *_args: context,
    )
    monkeypatch.setattr(
        composition,
        "inspect_w3_launch_readiness",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(
        composition,
        "prepare_w3_invocation",
        lambda _readiness: (_ for _ in ()).throw(OSError("claim failed")),
    )

    with pytest.raises(
        WarehouseW3CompositionError,
        match="claim could not be prepared",
    ) as captured:
        composition._run_installed(materials)

    assert not isinstance(
        captured.value,
        WarehouseW3InstalledIdentityRefused,
    )


def test_live_start_context_revalidation_reacquires_manager_and_environment() -> None:
    phases: list[str] = []
    manager = SimpleNamespace(
        unique_owner=":1.42",
        boot_id="12345678-1234-1234-1234-123456789abc",
        version="255.4-1ubuntu8",
    )
    context = SimpleNamespace(
        gate=SimpleNamespace(
            manager_unique_owner=manager.unique_owner,
            boot_id=manager.boot_id,
            manager_version=manager.version,
        ),
        verify_environment=lambda phase: phases.append(phase),
    )

    composition._revalidate_live_start_context(
        context,
        SimpleNamespace(acquire_manager_identity=lambda: manager),
        SimpleNamespace(boot_id=manager.boot_id),
    )

    assert phases == ["preclaim"]


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("unique_owner", ":1.99"),
        ("boot_id", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        ("version", "256"),
    ),
)
def test_live_start_context_revalidation_rejects_manager_drift(
    field: str,
    value: str,
) -> None:
    expected = SimpleNamespace(
        unique_owner=":1.42",
        boot_id="12345678-1234-1234-1234-123456789abc",
        version="255.4-1ubuntu8",
    )
    current = SimpleNamespace(
        unique_owner=expected.unique_owner,
        boot_id=expected.boot_id,
        version=expected.version,
    )
    setattr(current, field, value)
    context = SimpleNamespace(
        gate=SimpleNamespace(
            manager_unique_owner=expected.unique_owner,
            boot_id=expected.boot_id,
            manager_version=expected.version,
        ),
        verify_environment=lambda _phase: None,
    )

    with pytest.raises(
        WarehouseW3SystemdLineageRefused,
        match="changed before nonce",
    ):
        composition._revalidate_live_start_context(
            context,
            SimpleNamespace(acquire_manager_identity=lambda: current),
            SimpleNamespace(boot_id=expected.boot_id),
        )


def test_completion_environment_drift_marks_incomplete_before_raw_complete() -> None:
    events: list[str] = []

    class Writer:
        def mark_incomplete(self, reason: str) -> None:
            events.append(f"incomplete:{reason}")

        def finish_raw(self) -> None:
            events.append("finish")

    class Backend:
        state = "IDLE"

        def close_idle(self) -> None:
            events.append("backend-close")

    context = SimpleNamespace(
        verify_environment=lambda phase: (
            events.append(f"verify:{phase}"),
            (_ for _ in ()).throw(RuntimeError("drift")),
        )[-1],
    )

    with pytest.raises(
        WarehouseW3CompositionError,
        match="completion environment integrity",
    ):
        composition._complete_installed_run(
            Writer(),
            Backend(),
            context,
        )

    assert events == [
        "verify:completion",
        "incomplete:ENVIRONMENT_COMPLETION_REFUSED",
        "backend-close",
    ]


@pytest.mark.parametrize(
    ("error_type", "status"),
    (
        (WarehouseW3StartPermitRefused, 70),
        (WarehouseW3EnvironmentIntegrityRefused, 71),
        (WarehouseW3InstalledIdentityRefused, 72),
        (WarehouseW3SystemdLineageRefused, 73),
    ),
)
def test_installed_tool_has_exact_preclaim_exit_status_abi(
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[RuntimeError],
    status: int,
) -> None:
    def refuse(_command: str, _launch_id: str) -> None:
        raise error_type("refused")

    monkeypatch.setattr(installed_tool, "dispatch_installed_launch", refuse)

    assert installed_tool.main(["run", LAUNCH_ID]) == status


def test_installed_tool_does_not_classify_unexpected_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(_command: str, _launch_id: str) -> None:
        raise WarehouseW3CompositionError("unexpected")

    monkeypatch.setattr(installed_tool, "dispatch_installed_launch", fail)

    with pytest.raises(WarehouseW3CompositionError, match="unexpected"):
        installed_tool.main(["run", LAUNCH_ID])
