from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import grp
import pwd
import select
import signal
import stat
import subprocess
import sys
import threading
from dataclasses import replace
from types import ModuleType, SimpleNamespace
from typing import Any, Callable

import pytest


FIXTURES = Path(__file__).parents[3] / "fixtures" / "runtime" / "execution"
PROJECT = FIXTURES.parents[4]
sys.path.insert(0, str(PROJECT))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"_fixture_{name}", FIXTURES / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


harness = _load("generic_backend_systemd_harness")
installer = _load("generic_backend_root_installer")
formal_case = _load("generic_backend_formal_case")


def _canonical(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("ascii")


def _write(path: Path, value: Any) -> None:
    path.write_bytes(_canonical(value))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FakeInstallerManager:
    owner = ":1.255"

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.calls: list[tuple[str, str | None]] = []

    def reload(self) -> None:
        self.calls.append(("Reload", None))

    def load_unit(self, unit: str) -> str:
        self.calls.append(("LoadUnit", unit))
        return installer._systemd_unit_object_path(unit)

    def unit_property(self, object_path: str, interface: str, name: str) -> Any:
        del interface
        self.calls.append((name, object_path))
        unit = next(
            unit
            for _member, unit in self.calls
            if _member == "LoadUnit"
            and installer._systemd_unit_object_path(str(unit)) == object_path
        )
        return str(self.directory / unit) if name == "FragmentPath" else False


def _render_unit(name: str, values: dict[str, str]) -> str:
    rendered = (FIXTURES / name).read_text(encoding="ascii")
    for key, value in values.items():
        rendered = rendered.replace(f"@{key}@", value)
    assert "@" not in rendered
    return rendered


def _static_authority_chain(
    tmp_path: Path, *, fragment_mutation: str | None = None
) -> dict[str, Any]:
    user = pwd.getpwuid(os.getuid()).pw_name
    group = grp.getgrgid(os.getgid()).gr_name
    root = tmp_path / "formal"
    tree_receipt = root / "authority" / "tree.json"
    prepare_manifest = tmp_path / "prepare.json"
    _write(
        prepare_manifest,
        {
            "schema": installer.PREPARE_SCHEMA,
            "formal_root": str(root),
            "fixture_user": user,
            "fixture_group": group,
            "fifos": [
                {
                    "role": "run-ready",
                    "path": str(root / "fifo" / "run-ready"),
                }
            ],
            "receipt_path": str(tree_receipt),
        },
    )
    installer.prepare_tree(prepare_manifest, require_root=False)

    sealed = root / "sealed"
    run_unit = "scion-w3-test.service"
    close_unit = "scion-w3-test-close.service"
    gc_unit = "scion-w3-test-gc.service"
    paths = {
        "run-fragment": sealed / run_unit,
        "close-fragment": sealed / close_unit,
        "gc-fragment": sealed / gc_unit,
        "run-program": sealed / "run-program.py",
        "stop-program": sealed / "stop-program.py",
        "close-program": sealed / "close-program.py",
        "run-plan": sealed / "run-plan.json",
        "stop-plan": sealed / "stop-plan.json",
        "close-plan": sealed / "close-plan.json",
        "start-descriptor": sealed / "start.json",
        "installer-program": sealed / "generic_backend_root_installer.py",
        "harness-program": sealed / "generic_backend_systemd_harness.py",
    }
    common = {
        "CASE": "pure-authority",
        "FIXTURE_USER": user,
        "FIXTURE_GROUP": group,
        "SEALED_ROOT": str(sealed),
        "INPUT_ROOT": str(root / "input"),
        "WORK_ROOT": str(root / "work"),
        "FIFO_ROOT": str(root / "fifo"),
    }
    run_values = {
        **common,
        "CLOSE_UNIT": close_unit,
        "RUN_PROGRAM": str(paths["run-program"]),
        "RUN_PLAN": str(paths["run-plan"]),
        "STOP_PROGRAM": str(paths["stop-program"]),
        "STOP_PLAN": str(paths["stop-plan"]),
    }
    close_values = {
        **common,
        "RUN_UNIT": run_unit,
        "CLOSE_PROGRAM": str(paths["close-program"]),
        "CLOSE_PLAN": str(paths["close-plan"]),
    }
    gc_values = {
        **common,
        "RUN_PROGRAM": str(paths["run-program"]),
        "RUN_PLAN": str(paths["run-plan"]),
    }
    fragments = {
        "run-fragment": _render_unit("generic-backend-run.service.in", run_values),
        "close-fragment": _render_unit(
            "generic-backend-close.service.in", close_values
        ),
        "gc-fragment": _render_unit(
            "generic-backend-gc-negative.service.in", gc_values
        ),
    }
    if fragment_mutation == "at":
        fragments["gc-fragment"] += "Environment=@UNRESOLVED@\n"
    elif fragment_mutation == "percent":
        fragments["gc-fragment"] += "Environment=UNIT=%n\n"
    elif fragment_mutation == "python":
        fragments["close-fragment"] = fragments["close-fragment"].replace(
            "/usr/bin/python3.12", "/usr/bin/python3.11"
        )
    elif fragment_mutation == "unlisted-plan":
        fragments["gc-fragment"] = fragments["gc-fragment"].replace(
            str(paths["run-plan"]), str(sealed / "missing-plan.json")
        )
    elif fragment_mutation == "exec-extra":
        fragments["run-fragment"] += "ExecStartPre=/bin/true\n"
    elif fragment_mutation == "environment-extra":
        fragments["close-fragment"] += "Environment=SCION_UNCLOSED=1\n"
    elif fragment_mutation == "capability-extra":
        fragments["gc-fragment"] += "AmbientCapabilities=CAP_SYS_ADMIN\n"
    elif fragment_mutation == "unknown-extra":
        fragments["run-fragment"] += "X-Scion-Unclosed=yes\n"
    elif fragment_mutation is not None:
        raise AssertionError(f"unknown fragment mutation {fragment_mutation}")
    for role, text in fragments.items():
        paths[role].write_text(text, encoding="ascii")
    program_source = (
        "#!/usr/bin/env python3\n"
        "from __future__ import annotations\n"
        "raise SystemExit(0)\n"
    )
    for role in ("run-program", "stop-program", "close-program"):
        paths[role].write_text(program_source, encoding="ascii")
    for role in ("run-plan", "stop-plan", "close-plan"):
        _write(paths[role], {"schema": "scion.test.static-plan.v1", "role": role})
    _write(paths["start-descriptor"], _descriptor(run_unit))
    paths["installer-program"].write_bytes(
        (FIXTURES / "generic_backend_root_installer.py").read_bytes()
    )
    paths["harness-program"].write_bytes(
        (FIXTURES / "generic_backend_systemd_harness.py").read_bytes()
    )
    asset_kinds = {
        "run-fragment": "unit-fragment",
        "close-fragment": "unit-fragment",
        "gc-fragment": "unit-fragment",
        "run-program": "python-program",
        "stop-program": "python-program",
        "close-program": "python-program",
        "run-plan": "json-plan",
        "stop-plan": "json-plan",
        "close-plan": "json-plan",
        "start-descriptor": "start-descriptor",
        "installer-program": "installer-program",
        "harness-program": "harness-program",
    }
    inventory = sealed / "static-inventory.tsv"
    tree_binding = installer._asset_reference(tree_receipt)
    destination = root / "authority" / "preflight"
    inventory_lines = [
        f"schema\t{installer.PREFLIGHT_MANIFEST_SCHEMA}\n",
        f"formal_root\t{root}\n",
        f"run_unit\t{run_unit}\n",
        f"close_unit\t{close_unit}\n",
        f"destination_path\t{destination}\n",
        "tree_receipt\t"
        + "\t".join(
            tree_binding[key]
            for key in ("path", "sha256", "device", "inode", "mode")
        )
        + "\n",
    ]
    for role, path in paths.items():
        info = path.lstat()
        inventory_lines.append(
            "\t".join(
                (
                    "asset",
                    role,
                    asset_kinds[role],
                    str(path),
                    _sha(path),
                    str(info.st_dev),
                    str(info.st_ino),
                    "0444",
                )
            )
            + "\n"
        )
    inventory.write_text("".join(inventory_lines), encoding="ascii")
    seal_manifest = tmp_path / "seal.json"
    seal_receipt = root / "authority" / "seal.json"
    sealed_files = [
        {"role": role, "path": str(path), "sha256": _sha(path)}
        for role, path in paths.items()
    ]
    sealed_files.append(
        {
            "role": "preflight-manifest",
            "path": str(inventory),
            "sha256": _sha(inventory),
        }
    )
    _write(
        seal_manifest,
        {
            "schema": installer.SEAL_SCHEMA,
            "formal_root": str(root),
            "tree_receipt": installer._file_reference(tree_receipt),
            "files": sealed_files,
            "receipt_path": str(seal_receipt),
        },
    )
    installer.seal_tree(seal_manifest, require_root=False)
    return {
        "root": root,
        "paths": paths,
        "inventory": inventory,
        "tree_receipt": tree_receipt,
        "seal_receipt": seal_receipt,
        "destination": destination,
        "run_unit": run_unit,
        "close_unit": close_unit,
        "gc_unit": gc_unit,
    }


def _run_static_preflight(chain: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [
            "fakeroot",
            "sh",
            str(FIXTURES / "generic-backend-formal-wrapper.sh"),
            "preflight",
            str(chain["inventory"]),
            str(chain["seal_receipt"]),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        # fakeroot records chmod ownership metadata only inside its child process;
        # mirror the successful wrapper's real-root 0500/0444 postcondition for
        # the independent in-process installer consumer.
        chain["destination"].chmod(0o500)
        (chain["destination"] / "PREFLIGHT.json").chmod(0o444)
    return result


def _publish_test_preflight(chain: dict[str, Any]) -> Path:
    destination = chain["destination"]
    destination.mkdir(mode=0o700)
    path = destination / "PREFLIGHT.json"
    asset_count = sum(
        1
        for line in chain["inventory"].read_text(encoding="ascii").splitlines()
        if line.startswith("asset\t")
    )
    _write(
        path,
        {
            "schema": installer.PREFLIGHT_RECEIPT_SCHEMA,
            "asset_count": str(asset_count),
            "close_unit": chain["close_unit"],
            "formal_root": str(chain["root"]),
            "inventory_manifest": installer._asset_reference(chain["inventory"]),
            "phase": "static-preflight-complete",
            "run_unit": chain["run_unit"],
            "seal_receipt": installer._asset_reference(chain["seal_receipt"]),
            "tree_receipt": installer._asset_reference(chain["tree_receipt"]),
        },
    )
    path.chmod(0o444)
    destination.chmod(0o500)
    return path


def _install_plan(chain: dict[str, Any], tmp_path: Path) -> tuple[Path, Path]:
    receipt_path = chain["root"] / "authority" / "install.json"
    manifest_path = tmp_path / "install.json"
    _write(
        manifest_path,
        {
            "schema": installer.INSTALL_SCHEMA,
            "formal_root": str(chain["root"]),
            "tree_receipt": installer._file_reference(chain["tree_receipt"]),
            "seal_receipt": installer._file_reference(chain["seal_receipt"]),
            "preflight_receipt": installer._file_reference(
                chain["destination"] / "PREFLIGHT.json"
            ),
            "units": [
                {
                    "role": role,
                    "unit": unit,
                    "source": str(chain["paths"][role]),
                    "sha256": _sha(chain["paths"][role]),
                }
                for role, unit in (
                    ("run-fragment", chain["run_unit"]),
                    ("close-fragment", chain["close_unit"]),
                    ("gc-fragment", chain["gc_unit"]),
                )
            ],
            "receipt_path": str(receipt_path),
        },
    )
    return manifest_path, receipt_path


def _install_chain(
    chain: dict[str, Any], tmp_path: Path, manager: FakeInstallerManager
) -> tuple[dict[str, Any], Path]:
    manifest_path, receipt_path = _install_plan(chain, tmp_path)
    original_file = installer.__file__
    installer.__file__ = str(chain["paths"]["installer-program"])
    try:
        receipt = installer.install_units(
            manifest_path,
            manager=manager,
            require_root=False,
            unit_directory=manager.directory,
        )
    finally:
        installer.__file__ = original_file
    assert receipt_path.is_file()
    chain["install_manifest"] = manifest_path
    chain["install_receipt"] = receipt_path
    return receipt, manifest_path


def test_installer_prepares_and_seals_the_new_authority_chain(tmp_path: Path) -> None:
    user = pwd.getpwuid(os.getuid()).pw_name
    group = grp.getgrgid(os.getgid()).gr_name
    root = tmp_path / "formal"
    fifo = root / "fifo" / "run-ready"
    tree_receipt = root / "authority" / "tree.json"
    prepare = tmp_path / "prepare.json"
    _write(
        prepare,
        {
            "schema": installer.PREPARE_SCHEMA,
            "formal_root": str(root),
            "fixture_user": user,
            "fixture_group": group,
            "fifos": [{"role": "run-ready", "path": str(fifo)}],
            "receipt_path": str(tree_receipt),
        },
    )
    prepared = installer.prepare_tree(prepare, require_root=False)
    assert prepared["fifos"][0] == {"role": "run-ready", **installer._identity(fifo)}
    fragment = root / "sealed" / "scion-w3-test.service"
    fragment.write_text(
        "[Unit]\nDescription=test\n[Service]\n"
        f"User={user}\nGroup={group}\n"
        "ExecStart=/usr/bin/python3.12 -I -B /sealed/p.py --plan /sealed/p.json\n",
        encoding="ascii",
    )
    seal = tmp_path / "seal.json"
    seal_receipt = root / "authority" / "seal.json"
    _write(
        seal,
        {
            "schema": installer.SEAL_SCHEMA,
            "formal_root": str(root),
            "tree_receipt": installer._file_reference(tree_receipt),
            "files": [{"role": "run-fragment", "path": str(fragment), "sha256": _sha(fragment)}],
            "receipt_path": str(seal_receipt),
        },
    )
    receipt = installer.seal_tree(seal, require_root=False)
    assert receipt["tree_receipt"] == installer._file_reference(tree_receipt)
    assert receipt["phase"] == "static-authority-sealed"
    assert stat.S_IMODE((root / "sealed").stat().st_mode) == 0o555
    assert stat.S_IMODE(fragment.stat().st_mode) == 0o444


def _installed_authority_chain(
    tmp_path: Path,
) -> tuple[dict[str, Any], Path, FakeInstallerManager, dict[str, Any]]:
    chain = _static_authority_chain(tmp_path)
    preflight = _run_static_preflight(chain)
    assert preflight.returncode == 0, preflight.stderr
    unit_directory = tmp_path / "units"
    unit_directory.mkdir()
    manager = FakeInstallerManager(unit_directory)
    receipt, _manifest = _install_chain(chain, tmp_path, manager)
    return chain, unit_directory, manager, receipt


def _freeze_manifest(
    chain: dict[str, Any], tmp_path: Path
) -> tuple[Path, list[dict[str, str]], Path, Path]:
    evidence = chain["root"] / "work" / "evidence.json"
    _write(evidence, {"schema": "scion.test.evidence.v1", "accepted": True})
    harness_final = chain["root"] / "work" / "harness-final.json"
    roles = ["install-receipt", "evidence", "harness-final"]
    _write(
        harness_final,
        {
            "schema": installer.HARNESS_RECEIPT_SCHEMA,
            "scenario": "H1",
            "final_freeze": {"policy_id": "H1", "output_roles": roles},
        },
    )
    outputs = [
        {"role": role, **installer._file_reference(path)}
        for role, path in (
            ("install-receipt", chain["install_receipt"]),
            ("evidence", evidence),
            ("harness-final", harness_final),
        )
    ]
    manifest = tmp_path / "freeze.json"
    _write(
        manifest,
        {
            "schema": installer.FREEZE_SCHEMA,
            "formal_root": str(chain["root"]),
            "policy_id": "H1",
            "install_receipt": installer._file_reference(
                chain["install_receipt"]
            ),
            "harness_receipt": installer._file_reference(harness_final),
            "outputs": outputs,
            "destination_path": str(chain["root"] / "frozen"),
        },
    )
    return manifest, outputs, evidence, harness_final


def _record_only_test_final_publisher(
    events: list[str] | None = None,
) -> Callable[..., None]:
    """Observe the final seam without claiming a real namespace publication."""

    def publish(
        descriptor: int, *, directory_descriptor: int, name: str
    ) -> None:
        assert name == "FROZEN"
        assert stat.S_ISREG(os.fstat(descriptor).st_mode)
        assert os.fstat(descriptor).st_nlink == 0
        assert stat.S_ISDIR(os.fstat(directory_descriptor).st_mode)
        if events is not None:
            events.append("publish:FROZEN")

    return publish


def _test_materializing_final_publisher(
    descriptor: int, *, directory_descriptor: int, name: str
) -> None:
    """Test-only copy for cleanup consumers; never evidence for real linkat."""

    assert name == "FROZEN"
    assert os.fstat(descriptor).st_nlink == 0
    reader = os.open(f"/proc/self/fd/{descriptor}", os.O_RDONLY | os.O_CLOEXEC)
    try:
        chunks: list[bytes] = []
        while True:
            chunk = os.read(reader, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        raw = b"".join(chunks)
    finally:
        os.close(reader)

    os.fchmod(directory_descriptor, 0o700)
    marker_descriptor: int | None = None
    try:
        marker_descriptor = os.open(
            name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_CLOEXEC
            | os.O_NOFOLLOW,
            0o400,
            dir_fd=directory_descriptor,
        )
        view = memoryview(raw)
        while view:
            written = os.write(marker_descriptor, view)
            assert written > 0
            view = view[written:]
        os.fchmod(marker_descriptor, 0o400)
        os.fsync(marker_descriptor)
    finally:
        if marker_descriptor is not None:
            os.close(marker_descriptor)
        os.fchmod(directory_descriptor, 0o500)


def _cleanup_manifest(chain: dict[str, Any], tmp_path: Path) -> tuple[Path, Path]:
    manifest = tmp_path / "cleanup.json"
    receipt = chain["root"] / "authority" / "cleanup.json"
    _write(
        manifest,
        {
            "schema": installer.CLEANUP_SCHEMA,
            "formal_root": str(chain["root"]),
            "install_receipt": installer._file_reference(chain["install_receipt"]),
            "frozen_receipt": installer._file_reference(
                chain["root"] / "frozen" / "FROZEN"
            ),
            "receipt_path": str(receipt),
        },
    )
    return manifest, receipt


def test_tree_seal_preflight_install_chain_and_manager_ledger(
    tmp_path: Path,
) -> None:
    chain, unit_directory, manager, receipt = _installed_authority_chain(tmp_path)
    preflight_path = chain["destination"] / "PREFLIGHT.json"
    preflight = json.loads(preflight_path.read_text(encoding="ascii"))
    assert preflight["tree_receipt"] == installer._asset_reference(
        chain["tree_receipt"]
    )
    assert preflight["seal_receipt"] == installer._asset_reference(
        chain["seal_receipt"]
    )
    assert preflight["inventory_manifest"] == installer._asset_reference(
        chain["inventory"]
    )
    assert receipt["tree_receipt"] == installer._file_reference(
        chain["tree_receipt"]
    )
    assert receipt["seal_receipt"] == installer._file_reference(
        chain["seal_receipt"]
    )
    assert receipt["preflight_receipt"] == installer._file_reference(
        preflight_path
    )
    assert manager.calls == [
        ("Reload", None),
        ("LoadUnit", chain["run_unit"]),
        ("LoadUnit", chain["close_unit"]),
        ("LoadUnit", chain["gc_unit"]),
        *[
            (name, record["object_path"])
            for record in receipt["units"]
            for name in ("FragmentPath", "NeedDaemonReload")
        ],
    ]
    assert [entry["member"] for entry in receipt["manager_ledger"]] == [
        "Reload",
        "LoadUnit",
        "LoadUnit",
        "LoadUnit",
        "Get",
        "Get",
        "Get",
        "Get",
        "Get",
        "Get",
    ]
    assert [
        (entry["begin_ordinal"], entry["reply_ordinal"])
        for entry in receipt["manager_ledger"]
    ] == [(str(index), str(index + 1)) for index in range(1, 20, 2)]
    for record in receipt["units"]:
        target = Path(record["target"]["path"])
        assert target.parent == unit_directory
        assert record["target"]["sha256"] == record["source"]["sha256"]
        assert target.read_bytes() == Path(record["source"]["path"]).read_bytes()


@pytest.mark.parametrize(
    "mutation",
    [
        "at",
        "percent",
        "python",
        "unlisted-plan",
        "exec-extra",
        "environment-extra",
        "capability-extra",
        "unknown-extra",
    ],
)
def test_wrapper_rejects_nonconcrete_or_unsealed_argv_before_preflight_receipt(
    tmp_path: Path, mutation: str
) -> None:
    chain = _static_authority_chain(tmp_path, fragment_mutation=mutation)
    result = _run_static_preflight(chain)
    assert result.returncode != 0
    assert not chain["destination"].exists()
    assert not (chain["destination"] / "PREFLIGHT.json").exists()


@pytest.mark.parametrize(
    "mutation",
    ["exec-extra", "environment-extra", "capability-extra", "unknown-extra"],
)
def test_installer_independently_rejects_unclosed_concrete_unit_before_mutation(
    tmp_path: Path, mutation: str
) -> None:
    chain = _static_authority_chain(tmp_path, fragment_mutation=mutation)
    _publish_test_preflight(chain)
    unit_directory = tmp_path / "units"
    unit_directory.mkdir()
    manifest, receipt_path = _install_plan(chain, tmp_path)
    manager = FakeInstallerManager(unit_directory)
    original_file = installer.__file__
    installer.__file__ = str(chain["paths"]["installer-program"])
    try:
        with pytest.raises(installer.InstallerError, match="closed|multiset"):
            installer.install_units(
                manifest,
                manager=manager,
                require_root=False,
                unit_directory=unit_directory,
            )
    finally:
        installer.__file__ = original_file
    assert list(unit_directory.iterdir()) == []
    assert manager.calls == []
    assert not receipt_path.exists()
    assert not (chain["root"] / "authority" / "INSTALL-STARTED.json").exists()


def test_wrapper_rejects_symlinked_tree_directory_before_destination_creation(
    tmp_path: Path,
) -> None:
    chain = _static_authority_chain(tmp_path)
    work = chain["root"] / "work"
    replacement = tmp_path / "replacement-work"
    replacement.mkdir(mode=0o700)
    work.rmdir()
    work.symlink_to(replacement, target_is_directory=True)

    result = _run_static_preflight(chain)

    assert result.returncode != 0
    assert "non-symlink directory" in result.stderr
    assert not chain["destination"].exists()


def test_wrapper_rejects_static_inventory_drift_before_destination_creation(
    tmp_path: Path,
) -> None:
    chain = _static_authority_chain(tmp_path)
    inventory = chain["inventory"]
    drifted_destination = chain["root"] / "authority" / "preflight-drifted"
    os.chmod(inventory, 0o644)
    inventory.write_text(
        inventory.read_text(encoding="ascii").replace(
            f"destination_path\t{chain['destination']}\n",
            f"destination_path\t{drifted_destination}\n",
        ),
        encoding="ascii",
    )
    os.chmod(inventory, 0o444)

    result = _run_static_preflight(chain)

    assert result.returncode != 0
    assert (
        "SEAL_RECEIPT does not bind this exact static inventory manifest"
        in result.stderr
    )
    assert not chain["destination"].exists()
    assert not drifted_destination.exists()


@pytest.mark.parametrize(
    "reference_key", ["tree_receipt", "seal_receipt", "preflight_receipt"]
)
def test_install_rejects_each_input_reference_drift_before_mutation(
    tmp_path: Path, reference_key: str
) -> None:
    chain = _static_authority_chain(tmp_path)
    result = _run_static_preflight(chain)
    assert result.returncode == 0, result.stderr
    unit_directory = tmp_path / "units"
    unit_directory.mkdir()
    manifest, receipt_path = _install_plan(chain, tmp_path)
    payload = json.loads(manifest.read_text(encoding="ascii"))
    payload[reference_key]["sha256"] = "0" * 64
    _write(manifest, payload)
    manager = FakeInstallerManager(unit_directory)
    original_file = installer.__file__
    installer.__file__ = str(chain["paths"]["installer-program"])
    try:
        with pytest.raises(installer.InstallerError):
            installer.install_units(
                manifest,
                manager=manager,
                require_root=False,
                unit_directory=unit_directory,
            )
    finally:
        installer.__file__ = original_file

    assert list(unit_directory.iterdir()) == []
    assert manager.calls == []
    assert not receipt_path.exists()
    assert not (chain["root"] / "authority" / "INSTALL-STARTED.json").exists()


@pytest.mark.parametrize("mutation", ("moved-parent", "mode", "owner"))
def test_install_rejects_inventory_preflight_parent_or_metadata_drift_before_mutation(
    tmp_path: Path, mutation: str
) -> None:
    if mutation == "owner" and os.geteuid() != 0:
        pytest.skip("owner-drift branch requires a root-created authority tree")
    chain = _static_authority_chain(tmp_path)
    result = _run_static_preflight(chain)
    assert result.returncode == 0, result.stderr
    manifest, receipt_path = _install_plan(chain, tmp_path)
    payload = json.loads(manifest.read_text(encoding="ascii"))
    destination = chain["destination"]
    if mutation == "moved-parent":
        moved = destination.with_name("preflight-moved")
        destination.rename(moved)
        payload["preflight_receipt"] = installer._file_reference(
            moved / "PREFLIGHT.json"
        )
        _write(manifest, payload)
    elif mutation == "mode":
        destination.chmod(0o700)
    else:
        destination.chown(1, 1)
    unit_directory = tmp_path / "units"
    unit_directory.mkdir()
    manager = FakeInstallerManager(unit_directory)
    original_file = installer.__file__
    installer.__file__ = str(chain["paths"]["installer-program"])
    try:
        with pytest.raises(installer.InstallerError):
            installer.install_units(
                manifest,
                manager=manager,
                require_root=mutation == "owner",
                unit_directory=unit_directory,
            )
    finally:
        installer.__file__ = original_file
    assert manager.calls == []
    assert list(unit_directory.iterdir()) == []
    assert not receipt_path.exists()
    assert not (chain["root"] / "authority" / "INSTALL-STARTED.json").exists()


def test_install_validates_later_invalid_unit_before_first_fragment_copy(
    tmp_path: Path,
) -> None:
    chain = _static_authority_chain(tmp_path)
    result = _run_static_preflight(chain)
    assert result.returncode == 0, result.stderr
    unit_directory = tmp_path / "units"
    unit_directory.mkdir()
    manifest, receipt_path = _install_plan(chain, tmp_path)
    payload = json.loads(manifest.read_text(encoding="ascii"))
    payload["units"][-1]["sha256"] = "0" * 64
    _write(manifest, payload)
    manager = FakeInstallerManager(unit_directory)
    original_file = installer.__file__
    installer.__file__ = str(chain["paths"]["installer-program"])
    try:
        with pytest.raises(installer.InstallerError):
            installer.install_units(
                manifest,
                manager=manager,
                require_root=False,
                unit_directory=unit_directory,
            )
    finally:
        installer.__file__ = original_file
    assert list(unit_directory.iterdir()) == []
    assert manager.calls == []
    assert not receipt_path.exists()
    assert not (chain["root"] / "authority" / "INSTALL-STARTED.json").exists()


@pytest.mark.parametrize("collision", ["alias", "receipt-exists", "marker-exists"])
def test_install_receipt_marker_boundary_fails_before_side_effect(
    tmp_path: Path, collision: str
) -> None:
    chain = _static_authority_chain(tmp_path)
    result = _run_static_preflight(chain)
    assert result.returncode == 0, result.stderr
    unit_directory = tmp_path / "units"
    unit_directory.mkdir()
    manifest, receipt_path = _install_plan(chain, tmp_path)
    marker = chain["root"] / "authority" / "INSTALL-STARTED.json"
    if collision == "alias":
        payload = json.loads(manifest.read_text(encoding="ascii"))
        payload["receipt_path"] = str(marker)
        _write(manifest, payload)
    elif collision == "receipt-exists":
        receipt_path.write_text("occupied\n", encoding="ascii")
    else:
        marker.write_text("occupied\n", encoding="ascii")
    manager = FakeInstallerManager(unit_directory)
    original_file = installer.__file__
    installer.__file__ = str(chain["paths"]["installer-program"])
    try:
        with pytest.raises(installer.InstallerError):
            installer.install_units(
                manifest,
                manager=manager,
                require_root=False,
                unit_directory=unit_directory,
            )
    finally:
        installer.__file__ = original_file
    assert list(unit_directory.iterdir()) == []
    assert manager.calls == []


def test_install_manager_owner_is_validated_before_marker_or_copy(
    tmp_path: Path,
) -> None:
    chain = _static_authority_chain(tmp_path)
    result = _run_static_preflight(chain)
    assert result.returncode == 0, result.stderr
    unit_directory = tmp_path / "units"
    unit_directory.mkdir()
    manifest, receipt_path = _install_plan(chain, tmp_path)
    manager = FakeInstallerManager(unit_directory)
    manager.owner = "org.freedesktop.systemd1"
    original_file = installer.__file__
    installer.__file__ = str(chain["paths"]["installer-program"])
    try:
        with pytest.raises(installer.InstallerError, match="unique bus name"):
            installer.install_units(
                manifest,
                manager=manager,
                require_root=False,
                unit_directory=unit_directory,
            )
    finally:
        installer.__file__ = original_file
    assert list(unit_directory.iterdir()) == []
    assert manager.calls == []
    assert not receipt_path.exists()
    assert not (chain["root"] / "authority" / "INSTALL-STARTED.json").exists()


def test_tree_receipt_rejects_work_owner_different_from_fixture_identity(
    tmp_path: Path,
) -> None:
    chain = _static_authority_chain(tmp_path)
    receipt = json.loads(chain["tree_receipt"].read_text(encoding="ascii"))
    receipt["fixture_uid"] = str(os.getuid() + 1)
    with pytest.raises(installer.InstallerError, match="work root fixture ownership"):
        installer._validate_tree_receipt(
            receipt,
            root=chain["root"],
            require_root=False,
            sealed=True,
        )


@pytest.mark.parametrize("reply", ["wrong", "duplicate"])
def test_install_rejects_noncanonical_or_duplicate_loadunit_object_path_as_poison(
    tmp_path: Path, reply: str
) -> None:
    class BadObjectPathManager(FakeInstallerManager):
        def load_unit(self, unit: str) -> str:
            self.calls.append(("LoadUnit", unit))
            if reply == "duplicate":
                if len([call for call in self.calls if call[0] == "LoadUnit"]) > 1:
                    return installer._systemd_unit_object_path(chain["run_unit"])
                return installer._systemd_unit_object_path(unit)
            return "/org/freedesktop/systemd1/unit/not_2d" + unit

    chain = _static_authority_chain(tmp_path)
    result = _run_static_preflight(chain)
    assert result.returncode == 0, result.stderr
    unit_directory = tmp_path / "units"
    unit_directory.mkdir()
    manifest, receipt_path = _install_plan(chain, tmp_path)
    manager = BadObjectPathManager(unit_directory)
    original_file = installer.__file__
    installer.__file__ = str(chain["paths"]["installer-program"])
    try:
        with pytest.raises(installer.InstallerError, match="object path"):
            installer.install_units(
                manifest,
                manager=manager,
                require_root=False,
                unit_directory=unit_directory,
            )
    finally:
        installer.__file__ = original_file
    assert (chain["root"] / "authority" / "INSTALL-STARTED.json").is_file()
    assert not receipt_path.exists()
    assert sorted(path.name for path in unit_directory.iterdir()) == sorted(
        (chain["run_unit"], chain["close_unit"], chain["gc_unit"])
    )


def test_install_external_failure_retains_poison_and_never_rolls_back(
    tmp_path: Path,
) -> None:
    class FailedReloadManager(FakeInstallerManager):
        def reload(self) -> None:
            super().reload()
            raise OSError("injected reload failure")

    chain = _static_authority_chain(tmp_path)
    result = _run_static_preflight(chain)
    assert result.returncode == 0, result.stderr
    unit_directory = tmp_path / "units"
    unit_directory.mkdir()
    manifest, receipt_path = _install_plan(chain, tmp_path)
    manager = FailedReloadManager(unit_directory)
    original_file = installer.__file__
    installer.__file__ = str(chain["paths"]["installer-program"])
    try:
        with pytest.raises(OSError, match="injected reload failure"):
            installer.install_units(
                manifest,
                manager=manager,
                require_root=False,
                unit_directory=unit_directory,
            )
    finally:
        installer.__file__ = original_file
    assert sorted(path.name for path in unit_directory.iterdir()) == sorted(
        (chain["run_unit"], chain["close_unit"], chain["gc_unit"])
    )
    assert (chain["root"] / "authority" / "INSTALL-STARTED.json").is_file()
    assert not receipt_path.exists()
    assert manager.calls == [("Reload", None)]


@pytest.mark.parametrize("mutation", ["missing", "extra", "source-drift", "existing"])
def test_freeze_rejects_policy_inventory_and_source_or_destination_drift(
    tmp_path: Path, mutation: str
) -> None:
    chain, _unit_directory, _manager, _receipt = _installed_authority_chain(tmp_path)
    manifest, _outputs, evidence, _harness_final = _freeze_manifest(chain, tmp_path)
    payload = json.loads(manifest.read_text(encoding="ascii"))
    if mutation == "missing":
        payload["outputs"].pop(1)
    elif mutation == "extra":
        extra = chain["root"] / "work" / "extra.json"
        _write(extra, {"schema": "scion.test.extra.v1"})
        payload["outputs"].insert(
            -1, {"role": "extra", **installer._file_reference(extra)}
        )
    elif mutation == "source-drift":
        os.chmod(evidence, 0o600)
        evidence.write_text('{"drifted":true}\n', encoding="ascii")
    else:
        (chain["root"] / "frozen").mkdir()
    _write(manifest, payload)
    with pytest.raises(installer.InstallerError):
        installer.freeze_receipts(
            manifest,
            require_root=False,
            _test_final_publisher=_record_only_test_final_publisher(),
        )
    if mutation == "existing":
        assert (chain["root"] / "frozen").is_dir()
    else:
        assert not (chain["root"] / "frozen").exists()


def test_freeze_mid_copy_failure_retains_incomplete_directory_without_frozen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chain, _unit_directory, _manager, _receipt = _installed_authority_chain(tmp_path)
    manifest, _outputs, _evidence, _harness_final = _freeze_manifest(chain, tmp_path)
    original = installer._write_bytes_no_replace
    calls: list[Path] = []

    def fail_second(path: Path, raw: bytes, *, mode: int) -> None:
        calls.append(path)
        if len(calls) == 2:
            raise OSError("injected copy failure")
        original(path, raw, mode=mode)

    monkeypatch.setattr(installer, "_write_bytes_no_replace", fail_second)
    publisher_events: list[str] = []
    with pytest.raises(OSError, match="injected copy failure"):
        installer.freeze_receipts(
            manifest,
            require_root=False,
            _test_final_publisher=_record_only_test_final_publisher(
                publisher_events
            ),
        )
    destination = chain["root"] / "frozen"
    assert destination.is_dir()
    assert calls[0].is_file()
    assert not (destination / "FROZEN").exists()
    assert publisher_events == []


@pytest.mark.parametrize(
    "failure", ("chmod", "destination-fsync", "root-fsync", "parent-fsync")
)
def test_freeze_never_publishes_frozen_before_final_metadata_durability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    chain, _unit_directory, _manager, _receipt = _installed_authority_chain(tmp_path)
    manifest, _outputs, _evidence, _harness_final = _freeze_manifest(chain, tmp_path)
    destination = chain["root"] / "frozen"
    real_chmod = installer.os.chmod
    real_fsync_directory = installer._fsync_directory

    if failure == "chmod":
        def fail_chmod(path: Path, mode: int) -> None:
            if Path(path) == destination and mode == 0o500:
                raise OSError("injected final chmod failure")
            real_chmod(path, mode)

        monkeypatch.setattr(installer.os, "chmod", fail_chmod)
    elif failure == "destination-fsync":
        real_fsync = installer.os.fsync

        def fail_destination_fsync(descriptor: int) -> None:
            info = os.fstat(descriptor)
            current = destination.lstat() if destination.exists() else None
            if (
                current is not None
                and (info.st_dev, info.st_ino) == (current.st_dev, current.st_ino)
                and stat.S_IMODE(info.st_mode) == 0o500
            ):
                raise OSError("injected destination-fsync")
            real_fsync(descriptor)

        monkeypatch.setattr(installer.os, "fsync", fail_destination_fsync)
    else:
        target = {
            "root-fsync": chain["root"],
            "parent-fsync": chain["root"].parent,
        }[failure]

        def fail_final_fsync(path: Path) -> None:
            if (
                Path(path) == target
                and destination.exists()
                and stat.S_IMODE(destination.lstat().st_mode) == 0o500
            ):
                raise OSError(f"injected {failure}")
            real_fsync_directory(path)

        monkeypatch.setattr(installer, "_fsync_directory", fail_final_fsync)

    publisher_events: list[str] = []
    with pytest.raises(OSError, match="injected"):
        installer.freeze_receipts(
            manifest,
            require_root=False,
            _test_final_publisher=_record_only_test_final_publisher(
                publisher_events
            ),
        )
    assert destination.is_dir()
    assert not (destination / "FROZEN").exists()
    assert publisher_events == []


@pytest.mark.parametrize("failure", ("write", "fchmod", "fsync", "publisher"))
def test_freeze_unnamed_marker_failure_never_creates_frozen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    chain, _unit_directory, _manager, _receipt = _installed_authority_chain(tmp_path)
    manifest, _outputs, _evidence, _harness_final = _freeze_manifest(chain, tmp_path)
    destination = chain["root"] / "frozen"
    publisher_events: list[str] = []
    real_write = installer.os.write
    real_fchmod = installer.os.fchmod
    real_fsync = installer.os.fsync

    def is_unnamed_marker(descriptor: int) -> bool:
        info = os.fstat(descriptor)
        return stat.S_ISREG(info.st_mode) and info.st_nlink == 0

    if failure == "write":
        def fail_write(descriptor: int, raw: bytes | memoryview) -> int:
            if is_unnamed_marker(descriptor):
                raise OSError("injected unnamed marker write failure")
            return real_write(descriptor, raw)

        monkeypatch.setattr(installer.os, "write", fail_write)
    elif failure == "fchmod":
        def fail_fchmod(descriptor: int, mode: int) -> None:
            if is_unnamed_marker(descriptor):
                raise OSError("injected unnamed marker fchmod failure")
            real_fchmod(descriptor, mode)

        monkeypatch.setattr(installer.os, "fchmod", fail_fchmod)
    elif failure == "fsync":
        def fail_fsync(descriptor: int) -> None:
            if is_unnamed_marker(descriptor):
                raise OSError("injected unnamed marker fsync failure")
            real_fsync(descriptor)

        monkeypatch.setattr(installer.os, "fsync", fail_fsync)

    def final_publisher(
        descriptor: int, *, directory_descriptor: int, name: str
    ) -> None:
        del descriptor, directory_descriptor
        assert name == "FROZEN"
        publisher_events.append("publish:FROZEN")
        if failure == "publisher":
            raise OSError("injected final publisher failure")

    with pytest.raises(OSError, match="injected"):
        installer.freeze_receipts(
            manifest,
            require_root=False,
            _test_final_publisher=final_publisher,
        )
    assert destination.is_dir()
    assert not (destination / "FROZEN").exists()
    assert publisher_events == (["publish:FROZEN"] if failure == "publisher" else [])


def test_freeze_frozen_publication_is_the_last_successful_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chain, _unit_directory, _manager, _receipt = _installed_authority_chain(tmp_path)
    manifest, _outputs, _evidence, _harness_final = _freeze_manifest(chain, tmp_path)
    events: list[str] = []
    real_close = installer.os.close

    def record_close(descriptor: int) -> None:
        if "publish:FROZEN" in events:
            events.append("close")
        real_close(descriptor)

    monkeypatch.setattr(installer.os, "close", record_close)
    installer.freeze_receipts(
        manifest,
        require_root=False,
        _test_final_publisher=_record_only_test_final_publisher(events),
    )
    publish_index = events.index("publish:FROZEN")
    assert events[publish_index + 1 :]
    assert set(events[publish_index + 1 :]) == {"close"}
    assert not (chain["root"] / "frozen" / "FROZEN").exists()


def test_freeze_privileged_path_uses_unnamed_no_replace_publication_contract() -> None:
    source = Path(installer.__file__).read_text(encoding="ascii")
    tree = ast.parse(source)
    freeze_source = ast.get_source_segment(
        source,
        next(
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "freeze_receipts"
        ),
    )
    assert freeze_source is not None
    assert "if _test_final_publisher is not None" in freeze_source
    assert "require_root or not callable(_test_final_publisher)" in freeze_source
    assert "tmpfile_flag = getattr(os, \"O_TMPFILE\", None)" in freeze_source
    assert "_publish_unnamed_no_replace" in freeze_source
    assert (
        freeze_source.index("os.fchmod(frozen_descriptor, 0o400)")
        < freeze_source.index("os.fsync(frozen_descriptor)")
        < freeze_source.index("final_publisher(")
    )
    publisher_source = ast.get_source_segment(
        source,
        next(
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "_publish_unnamed_no_replace"
        ),
    )
    assert publisher_source is not None
    assert "linkat(" in publisher_source
    assert "_AT_EMPTY_PATH" in publisher_source
    assert "O_CREAT" not in publisher_source


def test_freeze_writes_frozen_last_and_recomputes_every_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chain, unit_directory, _manager, _receipt = _installed_authority_chain(tmp_path)
    manifest, outputs, _evidence, _harness_final = _freeze_manifest(chain, tmp_path)
    byte_writer = installer._write_bytes_no_replace
    json_writer = installer._write_no_replace
    events: list[str] = []

    def record_bytes(path: Path, raw: bytes, *, mode: int) -> None:
        events.append(path.name)
        byte_writer(path, raw, mode=mode)

    def record_json(path: Path, value: Any, *, mode: int) -> None:
        events.append(path.name)
        json_writer(path, value, mode=mode)

    monkeypatch.setattr(installer, "_write_bytes_no_replace", record_bytes)
    monkeypatch.setattr(installer, "_write_no_replace", record_json)
    frozen = installer.freeze_receipts(
        manifest,
        require_root=False,
        _test_final_publisher=_test_materializing_final_publisher,
    )
    assert events[-1:] == ["SHA256SUMS"]
    assert [item["role"] for item in frozen["files"]] == [
        item["role"] for item in outputs
    ]
    for item in frozen["files"]:
        destination = Path(item["destination"]["path"])
        assert _sha(destination) == item["source"]["sha256"]
        assert item["destination"]["sha256"] == item["source"]["sha256"]
    expected_sums = "".join(
        f"{item['sha256']}  {item['role']}\n" for item in outputs
    )
    sums = chain["root"] / "frozen" / "SHA256SUMS"
    assert sums.read_text(encoding="ascii") == expected_sums
    assert frozen["sha256sums"]["sha256"] == _sha(sums)
    assert (chain["root"] / "frozen" / "FROZEN").is_file()
    assert frozen["frozen_root"] == installer._directory_reference(
        chain["root"] / "frozen"
    )
    assert frozen["frozen_root"]["mode"] == "0500"
    assert all((unit_directory / unit).is_file() for unit in (
        chain["run_unit"], chain["close_unit"], chain["gc_unit"]
    ))


@pytest.mark.parametrize("bad_binding", ["install", "frozen"])
def test_cleanup_is_explicit_frozen_bound_and_reloads_once(
    tmp_path: Path, bad_binding: str
) -> None:
    chain, unit_directory, _manager, _receipt = _installed_authority_chain(tmp_path)
    freeze_manifest, _outputs, _evidence, _harness_final = _freeze_manifest(
        chain, tmp_path
    )
    installer.freeze_receipts(
        freeze_manifest,
        require_root=False,
        _test_final_publisher=_test_materializing_final_publisher,
    )
    frozen_path = chain["root"] / "frozen" / "FROZEN"
    cleanup_manifest = tmp_path / "cleanup.json"
    cleanup_receipt = chain["root"] / "authority" / "cleanup.json"
    valid = {
        "schema": installer.CLEANUP_SCHEMA,
        "formal_root": str(chain["root"]),
        "install_receipt": installer._file_reference(chain["install_receipt"]),
        "frozen_receipt": installer._file_reference(frozen_path),
        "receipt_path": str(cleanup_receipt),
    }
    invalid = json.loads(json.dumps(valid))
    invalid[f"{bad_binding}_receipt"]["sha256"] = "0" * 64
    _write(cleanup_manifest, invalid)
    cleanup_manager = FakeInstallerManager(unit_directory)
    with pytest.raises(installer.InstallerError):
        installer.cleanup_units(
            cleanup_manifest, manager=cleanup_manager, require_root=False
        )
    assert cleanup_manager.calls == []
    assert all((unit_directory / unit).is_file() for unit in (
        chain["run_unit"], chain["close_unit"], chain["gc_unit"]
    ))
    _write(cleanup_manifest, valid)
    receipt = installer.cleanup_units(
        cleanup_manifest, manager=cleanup_manager, require_root=False
    )
    assert cleanup_manager.calls == [("Reload", None)]
    assert receipt["phase"] == "explicit-cleanup-complete-not-evidence"
    assert list(unit_directory.iterdir()) == []
    assert cleanup_receipt.is_file()


@pytest.mark.parametrize("collision", ["alias", "receipt-exists", "marker-exists"])
def test_cleanup_receipt_marker_boundary_fails_before_unlink_or_reload(
    tmp_path: Path, collision: str
) -> None:
    chain, unit_directory, _manager, _receipt = _installed_authority_chain(tmp_path)
    freeze_manifest, _outputs, _evidence, _harness = _freeze_manifest(chain, tmp_path)
    installer.freeze_receipts(
        freeze_manifest,
        require_root=False,
        _test_final_publisher=_test_materializing_final_publisher,
    )
    manifest, receipt = _cleanup_manifest(chain, tmp_path)
    marker = chain["root"] / "authority" / "CLEANUP-STARTED.json"
    if collision == "alias":
        payload = json.loads(manifest.read_text(encoding="ascii"))
        payload["receipt_path"] = str(marker)
        _write(manifest, payload)
    elif collision == "receipt-exists":
        receipt.write_text("occupied\n", encoding="ascii")
    else:
        marker.write_text("occupied\n", encoding="ascii")
    manager = FakeInstallerManager(unit_directory)
    with pytest.raises(installer.InstallerError):
        installer.cleanup_units(manifest, manager=manager, require_root=False)
    assert manager.calls == []
    assert all(
        (unit_directory / unit).is_file()
        for unit in (chain["run_unit"], chain["close_unit"], chain["gc_unit"])
    )


def test_cleanup_manager_owner_is_validated_before_marker_or_unlink(
    tmp_path: Path,
) -> None:
    chain, unit_directory, _manager, _receipt = _installed_authority_chain(tmp_path)
    freeze_manifest, _outputs, _evidence, _harness = _freeze_manifest(chain, tmp_path)
    installer.freeze_receipts(
        freeze_manifest,
        require_root=False,
        _test_final_publisher=_test_materializing_final_publisher,
    )
    manifest, receipt = _cleanup_manifest(chain, tmp_path)
    manager = FakeInstallerManager(unit_directory)
    manager.owner = ":1.256"
    with pytest.raises(installer.InstallerError, match="owner changed"):
        installer.cleanup_units(manifest, manager=manager, require_root=False)
    assert manager.calls == []
    assert not receipt.exists()
    assert not (chain["root"] / "authority" / "CLEANUP-STARTED.json").exists()
    assert all(
        (unit_directory / unit).is_file()
        for unit in (chain["run_unit"], chain["close_unit"], chain["gc_unit"])
    )


def test_cleanup_rejects_frozen_directory_metadata_drift_before_unlink(
    tmp_path: Path,
) -> None:
    chain, unit_directory, _manager, _receipt = _installed_authority_chain(tmp_path)
    freeze_manifest, _outputs, _evidence, _harness = _freeze_manifest(chain, tmp_path)
    installer.freeze_receipts(
        freeze_manifest,
        require_root=False,
        _test_final_publisher=_test_materializing_final_publisher,
    )
    manifest, receipt = _cleanup_manifest(chain, tmp_path)
    (chain["root"] / "frozen").chmod(0o700)
    manager = FakeInstallerManager(unit_directory)
    with pytest.raises(installer.InstallerError, match="frozen directory"):
        installer.cleanup_units(manifest, manager=manager, require_root=False)
    assert manager.calls == []
    assert not receipt.exists()
    assert not (chain["root"] / "authority" / "CLEANUP-STARTED.json").exists()
    assert all(
        (unit_directory / unit).is_file()
        for unit in (chain["run_unit"], chain["close_unit"], chain["gc_unit"])
    )


def test_cleanup_external_failure_retains_marker_and_removed_poison(
    tmp_path: Path,
) -> None:
    class FailedReloadManager(FakeInstallerManager):
        def reload(self) -> None:
            super().reload()
            raise OSError("injected cleanup reload failure")

    chain, unit_directory, _manager, _receipt = _installed_authority_chain(tmp_path)
    freeze_manifest, _outputs, _evidence, _harness = _freeze_manifest(chain, tmp_path)
    installer.freeze_receipts(
        freeze_manifest,
        require_root=False,
        _test_final_publisher=_test_materializing_final_publisher,
    )
    manifest, receipt = _cleanup_manifest(chain, tmp_path)
    manager = FailedReloadManager(unit_directory)
    with pytest.raises(OSError, match="injected cleanup reload failure"):
        installer.cleanup_units(manifest, manager=manager, require_root=False)
    assert manager.calls == [("Reload", None)]
    assert (chain["root"] / "authority" / "CLEANUP-STARTED.json").is_file()
    assert not receipt.exists()
    assert list(unit_directory.iterdir()) == []


def test_lossless_dbus_codec_and_descriptor(tmp_path: Path) -> None:
    binary = bytes(range(16))
    assert harness.encode_dbus("ay", binary)["base64"] == "AAECAwQFBgcICQoLDA0ODw=="
    structured = harness.encode_dbus(
        "a(sasbttttuii)", [("/bin/true", ["/bin/true"], False, 1, 2, 3, 4, 5, 1, 0)]
    )
    assert structured["items"][0]["kind"] == "struct"

    class VariantUInt(int):
        signature = "u"

    assert harness.encode_dbus("a{sv}", {"MainPID": VariantUInt(7)})["items"][0]["value"]["value"]["value"] == "7"
    unit = "scion-w3-h1.service"
    descriptor = tmp_path / "start.json"
    _write(descriptor, _descriptor(unit))
    assert harness.decode_start_descriptor(descriptor, unit).unit == unit
    descriptor.write_text(descriptor.read_text().replace('"fail"', '"replace"'))
    with pytest.raises(harness.HarnessError):
        harness.decode_start_descriptor(descriptor, unit)


@pytest.mark.parametrize("premature_eof", (False, True))
def test_system_journal_freeze_requires_end_cursor_in_one_forward_pass(
    premature_eof: bool,
) -> None:
    class FrozenIntervalReader:
        def __init__(self) -> None:
            self.current: str | None = None
            self.iter_calls = 0

        def seek_tail(self) -> None:
            self.current = None

        def get_previous(self) -> dict[str, str]:
            self.current = "cursor-2"
            return {"MESSAGE": "tail"}

        def get_cursor(self) -> str:
            assert self.current is not None
            return self.current

        def seek_head(self) -> None:
            self.current = None

        def __iter__(self):
            self.iter_calls += 1
            rows = [
                ("cursor-1", {"MESSAGE": "one"}),
                ("cursor-2", {"MESSAGE": "two"}),
            ]
            if premature_eof:
                rows.pop()
            for cursor, entry in rows:
                self.current = cursor
                yield entry

    reader = FrozenIntervalReader()
    journal = harness.SystemJournal.__new__(harness.SystemJournal)
    journal._reader = reader
    journal._start_cursor = None
    journal._matches = []
    journal.binding_receipt = {"files": [], "module_version": "test"}
    if premature_eof:
        with pytest.raises(harness.HarnessError, match="before the frozen end cursor"):
            journal.freeze()
    else:
        receipt = journal.freeze()
        assert [item["cursor"] for item in receipt["entries"]] == [
            "cursor-1",
            "cursor-2",
        ]
        assert receipt["entries"][-1]["cursor"] == receipt["end_cursor"]
    assert reader.iter_calls == 1


def test_system_journal_freeze_accepts_only_a_fully_empty_interval() -> None:
    class EmptyReader:
        iter_calls = 0

        def seek_tail(self) -> None:
            pass

        def get_previous(self) -> dict[str, str]:
            return {}

        def seek_head(self) -> None:
            pass

        def __iter__(self):
            self.iter_calls += 1
            return iter(())

    reader = EmptyReader()
    journal = harness.SystemJournal.__new__(harness.SystemJournal)
    journal._reader = reader
    journal._start_cursor = None
    journal._matches = []
    journal.binding_receipt = {"files": [], "module_version": "test"}
    receipt = journal.freeze()
    assert receipt["end_cursor"] is None
    assert receipt["entries"] == []
    assert reader.iter_calls == 1


@pytest.mark.parametrize("invalid_cursor", ("retained-start", "end", "captured"))
def test_system_journal_rejects_empty_or_noncanonical_cursors(
    invalid_cursor: str,
) -> None:
    class InvalidCursorReader:
        def __init__(self) -> None:
            self.current = "cursor-end"

        def seek_tail(self) -> None:
            self.current = "cursor-end"

        def get_previous(self) -> dict[str, str]:
            if invalid_cursor == "end":
                self.current = ""
            return {"MESSAGE": "tail"}

        def get_cursor(self) -> str:
            return self.current

        def seek_head(self) -> None:
            self.current = "cursor-head"

        def seek_cursor(self, cursor: str) -> None:
            self.current = cursor

        def get_next(self) -> dict[str, str]:
            return {"MESSAGE": "next"}

        def __iter__(self):
            self.current = "" if invalid_cursor == "captured" else "cursor-end"
            yield {"MESSAGE": "entry"}

    journal = harness.SystemJournal.__new__(harness.SystemJournal)
    journal._reader = InvalidCursorReader()
    journal._start_cursor = "" if invalid_cursor == "retained-start" else None
    journal._matches = []
    journal.binding_receipt = {"files": [], "module_version": "test"}
    with pytest.raises(harness.HarnessError, match="cursor"):
        journal.freeze()


def test_scenario_policy_table_is_closed_and_orders_every_formal_variant() -> None:
    expected = {f"H{index}" for index in range(13)}
    expected.update(
        f"{case_id}/{variant}"
        for case_id, variants in harness._B_VARIANTS.items()
        for variant in variants
    )
    assert set(harness._SCENARIO_POLICIES) == expected
    for scenario, policy in harness._SCENARIO_POLICIES.items():
        assert policy.scenario_id == scenario
        if scenario == "H0":
            assert policy.acquisition_order == ()
            assert "StartUnit" not in policy.allowed_methods
        elif scenario == "H10":
            assert policy.acquisition_order == ("run-main",)
            assert "RefUnit" not in policy.allowed_methods
        else:
            assert policy.acquisition_order[0] == "run-main"
            assert policy.acquisition_order[-1] in {"closer", "failed-closer"}
        if scenario.startswith("B6/"):
            variant = scenario.split("/", 1)[1]
            assert policy.formal_expected_fact_type == harness._B6_ABI[variant][
                "expected_fact_type"
            ]
            if variant in harness._B6_INSTALLABLE_VARIANTS:
                expected_action = (
                    "b6-issuer-send"
                    if variant.startswith("issuer-")
                    else "b6-zero-signal-release"
                )
                assert policy.formal_actions == (expected_action,)
                assert policy.formal_completion == "typed"
                assert "formal-action" in policy.required_outputs
                assert policy.terminal == harness._terminal()
            else:
                assert policy.formal_actions == ()
                assert policy.formal_completion == "requirement-missing"
                assert "formal-action" not in policy.required_outputs
                assert policy.terminal.run == (
                    "exit-code",
                    "failed",
                    "failed",
                    1,
                    78,
                    1,
                    0,
                )
                assert policy.terminal.stop == ("exit-code", "exited", "78")
                assert "formal-final" in policy.required_outputs
            if variant.startswith("close-"):
                assert variant in harness._B6_DECLARED_FAILSTOP_VARIANTS
                assert policy.formal_expected_fact_type == "FAILSTOP"
        if scenario.startswith("B7/tmpfile-"):
            assert policy.formal_actions == ()
            assert "formal-final" in policy.required_outputs
            assert "formal-failstop" not in policy.required_outputs
        elif scenario.startswith("B7/"):
            assert "formal-final" not in policy.required_outputs
            assert "formal-failstop" in policy.required_outputs
            assert policy.terminal.run == (
                "core-dump",
                "failed",
                "failed",
                3,
                6,
                1,
                0,
            )
            assert policy.terminal.stop == ("core-dump", "dumped", "6")


def test_real_formal_producer_crosses_exact_harness_consumer_and_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unit = "scion-w3-formal-outer.service"
    ready_path = tmp_path / "formal-ready"
    release_path = tmp_path / "formal-release"
    os.mkfifo(ready_path, 0o600)
    os.mkfifo(release_path, 0o600)
    acquisition = harness.Acquisition(
        "run-main",
        tmp_path / "formal-armed.json",
        harness.FifoIdentity(
            ready_path, ready_path.lstat().st_dev, ready_path.lstat().st_ino
        ),
        harness.FifoIdentity(
            release_path,
            release_path.lstat().st_dev,
            release_path.lstat().st_ino,
        ),
    )
    plan_path = tmp_path / "formal-plan.json"
    _write(plan_path, {"schema": "scion.test.formal-outer-plan.v1"})
    program_path = FIXTURES / "generic_backend_formal_case.py"
    plan = {
        "case_id": "B1",
        "variant": "clean",
        "run_unit": unit,
        "final_config_path": str(tmp_path / "formal-config.json"),
        "formal_program": {"path": str(program_path), "sha256": _sha(program_path)},
        "systemd_acquisition": {
            "armed_receipt_path": str(acquisition.armed_receipt_path),
            "ready_fifo": {
                "path": str(ready_path),
                "device": str(acquisition.ready_fifo.device),
                "inode": str(acquisition.ready_fifo.inode),
            },
            "release_fifo": {
                "path": str(release_path),
                "device": str(acquisition.release_fifo.device),
                "inode": str(acquisition.release_fifo.inode),
            },
        },
    }
    _write(plan_path, plan)
    os.chmod(plan_path, 0o444)
    policy = harness._SCENARIO_POLICIES["B1/clean"]
    static_authority = _direct_static_role_authority(
        acquisition,
        policy=policy,
        unit=unit,
        plan_path=plan_path,
        program_path=program_path,
    )
    boot_id = "12345678-1234-1234-1234-123456789abc"
    invocation = "6a" * 16
    identity = {
        "boot_id": boot_id,
        "invocation_id": invocation,
        "pid": os.getpid(),
        "proc_cgroup_raw": f"0::/system.slice/{unit}/supervisor\n",
        "starttime": 456,
        "unified_cgroup": f"/system.slice/{unit}/supervisor",
        "service_control_group": f"/system.slice/{unit}",
        "service_device": 11,
        "service_inode": 12,
        "supervisor_device": 11,
        "supervisor_inode": 13,
    }
    lineage = {"InvocationID": invocation, "MainPID": str(os.getpid())}
    monkeypatch.setattr(
        formal_case,
        "_formal_process_identity",
        lambda _plan, _lineage: dict(identity),
    )
    monkeypatch.setattr(
        formal_case, "_derive_same_pid_lineage", lambda _plan: dict(lineage)
    )
    result: dict[str, Any] = {}
    rendezvous = threading.Condition()
    allow_ready_writer_close = threading.Event()
    stage = {
        "ready_written": False,
        "release_reader_entered": False,
        "producer_finished": False,
    }
    original_write_all = formal_case._write_all
    original_os_open = os.open

    def observed_write_all(descriptor: int, data: bytes) -> None:
        original_write_all(descriptor, data)
        if data != harness.READY_BYTES:
            return
        with rendezvous:
            stage["ready_written"] = True
            rendezvous.notify_all()
        allow_ready_writer_close.wait()

    def observed_os_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        if (
            os.fspath(path) == str(release_path)
            and flags & os.O_ACCMODE == os.O_RDONLY
            and not flags & os.O_NONBLOCK
            and not flags & os.O_PATH
        ):
            with rendezvous:
                stage["release_reader_entered"] = True
                rendezvous.notify_all()
        if dir_fd is None:
            return original_os_open(path, flags, mode)
        return original_os_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(formal_case, "_write_all", observed_write_all)
    monkeypatch.setattr(os, "open", observed_os_open)

    def produce() -> None:
        try:
            result["sha256"] = formal_case._perform_systemd_acquisition(
                plan,
                plan_path=str(plan_path),
                plan_sha256=_sha(plan_path),
                lineage=lineage,
            )
        except BaseException as exc:  # pragma: no cover - asserted below
            result["error"] = exc
        finally:
            with rendezvous:
                stage["producer_finished"] = True
                rendezvous.notify_all()

    pinned = harness.PinnedAcquisition.open(acquisition)
    producer = threading.Thread(target=produce)
    producer.start()
    released = False
    try:
        with rendezvous:
            rendezvous.wait_for(
                lambda: stage["ready_written"] or stage["producer_finished"]
            )
        assert stage["ready_written"], result.get("error")
        readable, _, _ = select.select([pinned.ready_reader_fd], [], [])
        assert readable == [pinned.ready_reader_fd]
        allow_ready_writer_close.set()
        with rendezvous:
            rendezvous.wait_for(
                lambda: stage["release_reader_entered"]
                or stage["producer_finished"]
            )
        assert stage["release_reader_entered"], result.get("error")
        assert pinned.consume_ready() == harness.READY_BYTES
        armed = harness._armed_identity(
            acquisition.armed_receipt_path,
            acquisition,
            static_authority,
            run_unit=unit,
            closer_unit="scion-w3-formal-outer-close.service",
            policy=policy,
        )
    finally:
        allow_ready_writer_close.set()
        with rendezvous:
            rendezvous.wait_for(
                lambda: stage["release_reader_entered"]
                or stage["producer_finished"]
            )
        try:
            if stage["release_reader_entered"]:
                pinned.release()
                released = True
        finally:
            try:
                producer.join()
            finally:
                pinned.close()
                static_authority.plan_asset.close()
                static_authority.program_asset.close()
    assert released
    assert "error" not in result
    assert result["sha256"] == _sha(acquisition.armed_receipt_path)
    assert armed["schema"] == harness.FORMAL_ARMED_SCHEMA
    assert armed["identity"] == identity


def _descriptor(unit: str) -> dict[str, str]:
    return {
        "schema": harness.DESCRIPTOR_SCHEMA,
        "bus": "system",
        "destination": harness.SYSTEMD_DESTINATION,
        "object": harness.MANAGER_PATH,
        "interface": harness.MANAGER_INTERFACE,
        "method": "StartUnit",
        "signature": "ss",
        "unit": unit,
        "mode": "fail",
        "owner": "generic_backend_systemd_harness.py",
    }


_PENDING_ARMED: dict[Path, dict[str, Any]] = {}


def _pending_armed(acquisition: Any) -> dict[str, Any]:
    value = _PENDING_ARMED.get(acquisition.armed_receipt_path)
    assert value is not None
    return json.loads(json.dumps(value))


def _set_pending_armed(acquisition: Any, value: dict[str, Any]) -> None:
    assert not acquisition.armed_receipt_path.exists()
    _PENDING_ARMED[acquisition.armed_receipt_path] = json.loads(json.dumps(value))


def _direct_static_role_authority(
    acquisition: Any,
    *,
    policy: Any,
    unit: str,
    plan_path: Path,
    program_path: Path,
) -> harness.StaticRoleAuthority:
    owner = policy.run_owner
    plan_asset = harness._retain_static_asset(
        _frozen_asset(plan_path),
        role=f"{acquisition.role}-direct-plan",
        kind="json-plan",
        label=f"{acquisition.role} direct static plan",
        require_root=False,
    )
    program_asset = harness._retain_static_asset(
        _frozen_asset(program_path),
        role=f"{acquisition.role}-direct-program",
        kind="python-program",
        label=f"{acquisition.role} direct static program",
        require_root=False,
    )
    return harness.StaticRoleAuthority(
        role=acquisition.role,
        owner=owner.schema,
        mode=owner.mode,
        unit=unit,
        acquisition=acquisition,
        plan_asset=plan_asset,
        program_asset=program_asset,
        private_paths=(),
    )


def _acquisition(
    tmp_path: Path,
    role: str,
    unit: str,
    identity: dict[str, Any],
    *,
    adversary: str | None = None,
    source_receipt: Path | None = None,
) -> Any:
    identity.setdefault("proc_cgroup_raw", f"0::{identity['unified_cgroup']}\n")
    if adversary is not None:
        identity.setdefault("session_id", 1)
        identity.setdefault("stop_selector_environment", {})
    fifo_root = tmp_path / "fifo"
    fifo_root.mkdir(exist_ok=True)
    ready = fifo_root / f"{role}-ready"
    release = fifo_root / f"{role}-release"
    os.mkfifo(ready, 0o600)
    os.mkfifo(release, 0o600)
    item = harness.Acquisition(
        role,
        tmp_path / f"{role}-armed.json",
        harness.FifoIdentity(ready, ready.lstat().st_dev, ready.lstat().st_ino),
        harness.FifoIdentity(release, release.lstat().st_dev, release.lstat().st_ino),
    )
    program_path = FIXTURES / (
        "generic_backend_unit_observer.py"
        if adversary is None
        else "generic_backend_adversary.py"
    )
    program_info = program_path.lstat()
    program = {
        "path": str(program_path),
        "sha256": _sha(program_path),
        "identity": {
            "device": program_info.st_dev,
            "inode": program_info.st_ino,
            "mode": stat.S_IMODE(program_info.st_mode),
        },
    }
    plan_path = tmp_path / f"{role}-plan.json"
    request_path = tmp_path / f"{role}-request.json"
    _write(plan_path, {"schema": "scion.test.armed_plan.v1", "role": role})
    _write(request_path, {"schema": "scion.test.armed_request.v1", "role": role})
    terminal_path = source_receipt or (tmp_path / f"{role}-terminal.json")
    if adversary is None:
        payload = {
            "schema": "scion.generic_backend.systemd_observer_armed.v1",
            "mode": role,
            "unit": unit,
            "process_identity": identity,
            "stop_post_environment": (
                {
                    "INVOCATION_ID": identity["invocation_id"],
                    "SERVICE_RESULT": "success",
                    "EXIT_CODE": "exited",
                    "EXIT_STATUS": "0",
                }
                if role == "exec-stop-post"
                else None
            ),
            "plan_path": str(plan_path),
            "plan_sha256": _sha(plan_path),
            "program": program,
            "request_path": str(request_path),
            "output_path": str(terminal_path),
            "source_selector_path": (
                str(tmp_path / "source-selector.json") if role == "closer" else None
            ),
            "raw_authority_paths": [str(tmp_path / f"{role}-properties.json")],
        }
    else:
        payload = {
            "schema": "scion.generic_backend.systemd_adversary_armed.v1",
            "scenario": adversary,
            "unit": unit,
            "actor": identity,
            "plan_path": str(plan_path),
            "plan_sha256": _sha(plan_path),
            "program": program,
            "request_path": str(request_path),
            "request_sha256": _sha(request_path),
            "receipt_path": str(terminal_path),
        }
    payload["ready_fifo"] = {"path": str(ready), "device": str(ready.lstat().st_dev), "inode": str(ready.lstat().st_ino)}
    payload["release_fifo"] = {"path": str(release), "device": str(release.lstat().st_dev), "inode": str(release.lstat().st_ino)}
    payload["ready_sha256"] = hashlib.sha256(harness.READY_BYTES).hexdigest()
    payload["release_sha256"] = hashlib.sha256(harness.RELEASE_BYTES).hexdigest()
    _set_pending_armed(item, payload)
    return item


class FakeManager:
    owner = ":1.255"
    binding_receipt = {"files": [], "module_version": "1"}

    def __init__(
        self,
        run: str,
        closer: str | None,
        acquisitions: tuple[Any, ...],
        invocations: dict[str, bytes],
        scenario: str,
        on_ready: Callable[[str], None] | None = None,
    ) -> None:
        self.run = run
        self.closer = closer
        self.acquisitions = acquisitions
        self.invocations = invocations
        self.scenario = scenario
        self.on_ready = on_ready
        self.calls: list[tuple[str, ...]] = []
        self.callback: Callable[[Any], None] | None = None
        self.ordinal = 0
        self.ready_index = 0
        self.release_readers: dict[str, int] = {}
        self.loaded_after_gc = False
        self.removed_units: set[str] = set()
        self.pending_stop_job: tuple[int, str, str] | None = None

    @staticmethod
    def _object(unit: str) -> str:
        return "/org/freedesktop/systemd1/unit/" + unit.replace("-", "_2d")

    def _signal(self, member: str, body: tuple[Any, ...]) -> None:
        self.ordinal += 1
        assert self.callback is not None
        self.callback(harness.ManagerSignal(self.ordinal, member, harness._SIGNAL_SIGNATURES[member], body, harness.MANAGER_PATH, self.owner))

    def install_signal_handlers(self, callback: Callable[[Any], None]) -> None:
        self.calls.append(("matches",))
        self.callback = callback

    def subscribe(self) -> None:
        self.calls.append(("Subscribe",))

    def ref_unit(self, unit: str) -> None:
        self.calls.append(("RefUnit", unit))

    def start_unit(self, unit: str, mode: str) -> str:
        self.calls.append(("StartUnit", unit, mode))
        self._signal("JobNew", (1, "/job/1", unit))
        self._signal("UnitNew", (unit, self.get_unit(unit)))
        self._signal("JobRemoved", (1, "/job/1", unit, "done"))
        return "/job/1"

    def stop_unit(self, unit: str, mode: str) -> str:
        self.calls.append(("StopUnit", unit, mode))
        self._signal("JobNew", (2, "/job/2", unit))
        self.pending_stop_job = (2, "/job/2", unit)
        return "/job/2"

    def reset_failed_unit(self, unit: str) -> None:
        self.calls.append(("ResetFailedUnit", unit))

    def unref_unit(self, unit: str) -> None:
        self.calls.append(("UnrefUnit", unit))

    def load_unit(self, unit: str) -> str:
        self.calls.append(("LoadUnit", unit))
        self.loaded_after_gc = True
        self.removed_units.discard(unit)
        return self.get_unit(unit)

    def get_unit(self, unit: str) -> str:
        if unit in self.removed_units:
            class NoSuchUnit(RuntimeError):
                def get_dbus_name(self) -> str:
                    return "org.freedesktop.systemd1.NoSuchUnit"

            raise NoSuchUnit(unit)
        return self._object(unit)

    def property(self, object_path: str, interface: str, name: str) -> Any:
        if object_path == harness.MANAGER_PATH:
            assert interface == harness.MANAGER_INTERFACE and name == "Version"
            return "255.17"
        unit = self.run if object_path == self._object(self.run) else self.closer
        assert unit is not None
        is_run = unit == self.run
        is_h10 = self.closer is None
        invocation = b"" if is_h10 and self.loaded_after_gc else self.invocations[unit]
        failed = self.scenario in {"H7", "H10"} and is_run and not self.loaded_after_gc
        unit_values = {
            "Id": unit,
            "InvocationID": invocation,
            "LoadState": "loaded",
            "ActiveState": "failed" if failed else "inactive",
            "SubState": "failed" if failed else "dead",
            "After": [] if is_run else [self.run],
            "CollectMode": "inactive-or-failed" if is_h10 else "inactive",
            "FragmentPath": "/run/systemd/system/" + unit,
            "NeedDaemonReload": False,
            "OnSuccess": [self.closer] if is_run and self.closer else [],
            "OnFailure": [self.closer] if is_run and self.closer else [],
        }
        service_values = {
            "ControlGroup": "/system.slice/" + unit,
            "Delegate": is_run and not is_h10,
            "DelegateControllers": ["pids"] if is_run and not is_h10 else [],
            "DelegateSubgroup": "supervisor" if is_run and not is_h10 else "",
            "ExecMainCode": 2 if self.scenario == "H7" and is_run else 1,
            "ExecMainStatus": 15 if self.scenario == "H7" and is_run else (29 if self.scenario == "H10" and is_run and not self.loaded_after_gc else 0),
            "ExecStopPost": ([] if not is_run else [("/bin/true", ["/bin/true"], False, 0, 0, 0, 0, 0, 1, 0)]),
            "Group": grp.getgrgid(os.getgid()).gr_name,
            "KillMode": "control-group",
            "MainPID": 123,
            "Restart": "no",
            "Result": "signal" if self.scenario == "H7" and is_run else ("exit-code" if self.scenario == "H10" and is_run and not self.loaded_after_gc else "success"),
            "TimeoutStartUSec": (1 << 64) - 1,
            "TimeoutStopUSec": (1 << 64) - 1,
            "User": pwd.getpwuid(os.getuid()).pw_name,
        }
        return unit_values[name] if interface == harness.UNIT_INTERFACE else service_values[name]

    def wait_for(self, predicate: Callable[[], bool]) -> None:
        if not predicate():
            if self.closer is None:
                self._signal("UnitRemoved", (self.run, self._object(self.run)))
                self.removed_units.add(self.run)
            elif self.pending_stop_job is not None:
                job = self.pending_stop_job
                self.pending_stop_job = None
                self._signal("JobRemoved", (*job, "done"))
            else:
                pending_unref = [
                    item[1]
                    for item in self.calls
                    if item[0] == "UnrefUnit" and item[1] not in self.removed_units
                ]
                if pending_unref:
                    for unit in pending_unref:
                        self._signal("UnitRemoved", (unit, self._object(unit)))
                        self.removed_units.add(unit)
                else:
                    self._signal("JobNew", (3, "/job/3", self.closer))
                    self._signal("JobRemoved", (3, "/job/3", self.closer, "done"))
        assert predicate()

    def wait_readable(self, descriptor: int) -> None:
        del descriptor
        item = self.acquisitions[self.ready_index]
        self.ready_index += 1
        _write(item.armed_receipt_path, _PENDING_ARMED.pop(item.armed_receipt_path))
        if self.on_ready is not None:
            self.on_ready(item.role)
        writer = os.open(item.ready_fifo.path, os.O_WRONLY | os.O_CLOEXEC)
        os.write(writer, harness.READY_BYTES)
        os.close(writer)
        self.release_readers[item.role] = os.open(item.release_fifo.path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)


class FakeJournal:
    binding_receipt = {"files": [], "module_version": "1"}

    def __init__(self) -> None:
        self.calls: list[str] = []

    def begin(self) -> None:
        self.calls.append("begin")

    def add_invocation(self, boot_id: str, invocation_id: str) -> None:
        self.calls.append(f"match:{boot_id}:{invocation_id}")

    def synchronize(self) -> dict[str, Any]:
        self.calls.append("synchronize")
        return {"method": "Synchronize"}

    def freeze(self) -> dict[str, Any]:
        self.calls.append("freeze")
        return {"schema": harness.JOURNAL_RECEIPT_SCHEMA, "data_threshold": "0", "entries": []}


class NoExternalCalls:
    owner = ":1.255"
    binding_receipt = None

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __getattr__(self, name: str) -> Any:
        self.calls.append(name)
        raise AssertionError(name)


def _common_authorities(
    tmp_path: Path, run: str
) -> tuple[Any, Any, Any, Path, Path, Path]:
    descriptor = tmp_path / "start.json"
    _write(descriptor, _descriptor(run))
    install = tmp_path / "installer.json"
    _write(install, {"schema": installer.INSTALL_RECEIPT_SCHEMA, "manager_owner": ":1.255", "reload_call_count": "1", "fixture_user": "scion-fixture", "fixture_group": "scion-fixture"})
    boot = tmp_path / "boot-id"
    boot.write_text("12345678-1234-1234-1234-123456789abc\n", encoding="ascii")
    input_root = tmp_path / "input"
    receipts = tmp_path / "receipts"
    input_root.mkdir(exist_ok=True)
    receipts.mkdir(exist_ok=True)
    program = FIXTURES / "generic_backend_systemd_harness.py"
    return (
        harness.HashedFile(descriptor, _sha(descriptor)),
        harness.HashedFile(install, _sha(install)),
        harness.HashedFile(program, _sha(program)),
        boot,
        input_root,
        receipts,
    )


def _full_harness_authorities(
    tmp_path: Path,
    *,
    run: str,
    closer: str | None,
    acquisitions: tuple[Any, ...],
    plan_mutator: Callable[[str, dict[str, Any]], None] | None = None,
) -> tuple[Any, Any, Any, Path, Path, Path, Any, Any, tuple[Any, ...]]:
    descriptor, _minimal_install, _program, boot, input_root, receipts = (
        _common_authorities(tmp_path, run)
    )
    root = tmp_path / "harness-authority"
    sealed = root / "sealed"
    authority = root / "authority"
    unit_directory = root / "units"
    for path, mode in (
        (root, 0o711), (sealed, 0o755), (root / "input", 0o555),
        (root / "work", 0o700), (root / "fifo", 0o711),
        (authority, 0o700), (unit_directory, 0o755),
    ):
        path.mkdir(parents=True, exist_ok=True)
        os.chmod(path, mode)

    def frozen_json(path: Path, value: Any) -> None:
        _write(path, value)
        os.chmod(path, 0o444)

    def frozen_bytes(path: Path, raw: bytes) -> None:
        path.write_bytes(raw)
        os.chmod(path, 0o444)

    def asset(path: Path) -> dict[str, str]:
        info = path.lstat()
        return {
            "path": str(path), "sha256": _sha(path),
            "device": str(info.st_dev), "inode": str(info.st_ino),
            "mode": format(stat.S_IMODE(info.st_mode), "04o"),
        }

    def reference(path: Path) -> dict[str, str]:
        value = asset(path)
        value.pop("mode")
        return value

    static_roles: list[Any] = []
    inventory_assets: list[tuple[str, str, Path]] = []
    for index, acquisition in enumerate(acquisitions):
        armed = _pending_armed(acquisition)
        owner = (
            "observer"
            if armed["schema"] == "scion.generic_backend.systemd_observer_armed.v1"
            else "adversary"
        )
        mode = armed["mode"] if owner == "observer" else armed["scenario"]
        source_program = Path(armed["program"]["path"])
        program_path = sealed / f"role-{index}-program.py"
        frozen_bytes(program_path, source_program.read_bytes())
        acquisition_value = {
            "armed_receipt_path": str(acquisition.armed_receipt_path),
            "ready_fifo": {
                "path": str(acquisition.ready_fifo.path),
                "device": str(acquisition.ready_fifo.device),
                "inode": str(acquisition.ready_fifo.inode),
            },
            "release_fifo": {
                "path": str(acquisition.release_fifo.path),
                "device": str(acquisition.release_fifo.device),
                "inode": str(acquisition.release_fifo.inode),
            },
        }
        if owner == "observer":
            plan = {
                "schema": "scion.generic_backend.systemd_observer_plan.v1",
                "mode": mode, "program_path": str(program_path),
                "program_sha256": _sha(program_path),
                "request_path": armed["request_path"],
                "output_path": armed["output_path"], "unit": armed["unit"],
                "source_selector_path": armed["source_selector_path"],
                "cgroup_roots": [],
                "property_inputs": [
                    {"raw_authority_path": path}
                    for path in armed["raw_authority_paths"]
                ],
                "acquisition": acquisition_value,
            }
        else:
            plan = {
                "schema": "scion.generic_backend.systemd_adversary_plan.v1",
                "scenario": mode, "unit": armed["unit"], "expected_job_name": None,
                "program_path": str(program_path), "program_sha256": _sha(program_path),
                "request_path": armed["request_path"], "receipt_path": armed["receipt_path"],
                "acquisition": acquisition_value, "hold_release_fifo": None,
            }
        if plan_mutator is not None:
            plan_mutator(acquisition.role, plan)
        plan_path = sealed / f"role-{index}-plan.json"
        frozen_json(plan_path, plan)
        program_info = program_path.lstat()
        armed["plan_path"] = str(plan_path)
        armed["plan_sha256"] = _sha(plan_path)
        armed["program"] = {
            "path": str(program_path), "sha256": _sha(program_path),
            "identity": {"device": program_info.st_dev, "inode": program_info.st_ino, "mode": stat.S_IMODE(program_info.st_mode)},
        }
        _set_pending_armed(acquisition, armed)
        static_roles.append(
            harness.StaticRoleBinding(
                acquisition.role, armed["unit"], owner, mode,
                harness.HashedFile(plan_path, _sha(plan_path)),
                harness.HashedFile(program_path, _sha(program_path)),
            )
        )
        inventory_assets.extend(
            ((f"role-{index}-plan", "json-plan", plan_path),
             (f"role-{index}-program", "python-program", program_path))
        )

    installed_names = [
        run, closer or "scion-w3-h10-unused-close.service", "scion-w3-unused-gc.service"
    ]
    unit_records: list[dict[str, Any]] = []
    manifest_units: list[dict[str, str]] = []
    for index, unit in enumerate(installed_names):
        source = sealed / unit
        frozen_bytes(source, f"[Unit]\nDescription={unit}\n".encode("ascii"))
        target = unit_directory / unit
        target.write_bytes(source.read_bytes())
        os.chmod(target, 0o644)
        target_info = target.lstat()
        object_path = "/org/freedesktop/systemd1/unit/" + unit.replace("-", "_2d")
        role = ("run-fragment", "close-fragment", "gc-fragment")[index]
        manifest_units.append(
            {"role": role, "unit": unit, "source": str(source), "sha256": _sha(source)}
        )
        unit_records.append(
            {
                "role": role, "unit": unit, "source": asset(source),
                "target": {
                    "path": str(target), "sha256": _sha(target),
                    "device": str(target_info.st_dev), "inode": str(target_info.st_ino),
                    "uid": str(target_info.st_uid), "gid": str(target_info.st_gid), "mode": "0644",
                },
                "object_path": object_path, "fragment_path": str(target),
                "need_daemon_reload": False,
            }
        )
        inventory_assets.append((role, "unit-fragment", source))

    installer_program = sealed / "generic_backend_root_installer.py"
    harness_program = sealed / "generic_backend_systemd_harness.py"
    frozen_bytes(installer_program, (FIXTURES / installer_program.name).read_bytes())
    frozen_bytes(harness_program, (FIXTURES / harness_program.name).read_bytes())
    # The pure harness process models execution from the sealed copied program.
    harness.__file__ = str(harness_program)
    inventory_assets.extend(
        (("installer-program", "installer-program", installer_program),
         ("harness-program", "harness-program", harness_program))
    )
    sealed_descriptor = sealed / "start.json"
    frozen_bytes(sealed_descriptor, descriptor.path.read_bytes())
    inventory_assets.append(("start-descriptor", "start-descriptor", sealed_descriptor))

    tree_path = authority / "tree.json"
    root_info = root.stat()
    root_identity = {"path": str(root), "device": str(root_info.st_dev), "inode": str(root_info.st_ino)}
    frozen_json(
        tree_path,
        {"schema": harness.TREE_RECEIPT_SCHEMA, "formal_root": root_identity, "phase": "tree-prepared"},
    )
    tree_reference = reference(tree_path)
    inventory_path = sealed / "static-inventory.tsv"
    destination = authority / "preflight"
    inventory_lines = [
        f"schema\t{harness.PREFLIGHT_MANIFEST_SCHEMA}\n", f"formal_root\t{root}\n",
        f"run_unit\t{run}\n", f"close_unit\t{closer or installed_names[1]}\n",
        f"destination_path\t{destination}\n",
        "tree_receipt\t" + "\t".join(
            tree_reference[key] for key in ("path", "sha256", "device", "inode")
        ) + "\t0444\n",
    ]
    for role, kind, path in inventory_assets:
        binding = asset(path)
        inventory_lines.append(
            "\t".join(("asset", role, kind, binding["path"], binding["sha256"], binding["device"], binding["inode"], binding["mode"])) + "\n"
        )
    frozen_bytes(inventory_path, "".join(inventory_lines).encode("ascii"))
    inventory_binding = asset(inventory_path)
    seal_path = authority / "seal.json"
    sealed_files = [
        {"role": role, **asset(path)} for role, _kind, path in inventory_assets
    ] + [{"role": "preflight-manifest", **inventory_binding}]
    frozen_json(
        seal_path,
        {"schema": harness.SEAL_RECEIPT_SCHEMA, "formal_root": root_identity,
         "tree_receipt": tree_reference, "files": sealed_files,
         "phase": "static-authority-sealed"},
    )
    destination.mkdir(mode=0o700)
    preflight_path = destination / "PREFLIGHT.json"
    frozen_json(
        preflight_path,
        {"schema": harness.PREFLIGHT_RECEIPT_SCHEMA,
         "asset_count": str(len(inventory_assets)), "close_unit": closer or installed_names[1],
         "formal_root": str(root), "inventory_manifest": inventory_binding,
         "phase": "static-preflight-complete", "run_unit": run,
         "seal_receipt": asset(seal_path), "tree_receipt": asset(tree_path)},
    )
    os.chmod(destination, 0o500)
    install_path = authority / "install.json"
    install_manifest_path = sealed / "install-manifest.json"
    frozen_json(
        install_manifest_path,
        {"schema": harness.INSTALL_MANIFEST_SCHEMA, "formal_root": str(root),
         "tree_receipt": reference(tree_path), "seal_receipt": reference(seal_path),
         "preflight_receipt": reference(preflight_path), "units": manifest_units,
         "receipt_path": str(install_path)},
    )
    os.chmod(sealed, 0o555)
    ledger: list[dict[str, Any]] = []

    def manager_entry(interface: str, member: str, object_path: str, signature: str, arguments: list[Any], reply: Any) -> None:
        begin = 2 * len(ledger) + 1
        ledger.append(
            {"begin_ordinal": str(begin), "reply_ordinal": str(begin + 1),
             "interface": interface, "member": member, "object_path": object_path,
             "signature": signature, "arguments": arguments, "reply": reply}
        )

    manager_entry(harness.MANAGER_INTERFACE, "Reload", harness.MANAGER_PATH, "", [], None)
    for record in unit_records:
        manager_entry(harness.MANAGER_INTERFACE, "LoadUnit", harness.MANAGER_PATH, "s", [record["unit"]], record["object_path"])
    for record in unit_records:
        manager_entry(harness.PROPERTIES_INTERFACE, "Get", record["object_path"], "ss", [harness.UNIT_INTERFACE, "FragmentPath"], record["fragment_path"])
        manager_entry(harness.PROPERTIES_INTERFACE, "Get", record["object_path"], "ss", [harness.UNIT_INTERFACE, "NeedDaemonReload"], False)
    frozen_json(
        install_path,
        {"schema": harness.INSTALL_RECEIPT_SCHEMA, "formal_root": root_identity,
         "installer": asset(installer_program), "install_manifest": asset(install_manifest_path),
         "tree_receipt": reference(tree_path), "seal_receipt": reference(seal_path),
         "preflight_receipt": reference(preflight_path), "manager_owner": ":1.255",
         "manager_ledger": ledger, "fixture_user": pwd.getpwuid(os.getuid()).pw_name,
         "fixture_group": grp.getgrgid(os.getgid()).gr_name,
         "fixture_uid": str(os.getuid()), "fixture_gid": str(os.getgid()),
         "reload_call_count": "1", "load_call_count": str(len(unit_records)),
         "units": unit_records, "phase": "installed-before-observation"},
    )
    return (
        harness.HashedFile(sealed_descriptor, _sha(sealed_descriptor)),
        harness.HashedFile(install_path, _sha(install_path)),
        harness.HashedFile(harness_program, _sha(harness_program)),
        boot, input_root, receipts,
        harness.HashedFile(preflight_path, _sha(preflight_path)),
        harness.HashedFile(inventory_path, _sha(inventory_path)), tuple(static_roles),
    )


def _authority_closure_manifest(tmp_path: Path) -> harness.HarnessManifest:
    run = "scion-w3-authority-closure.service"
    actor_receipt = tmp_path / "authority-actor.json"
    actor = {
        "boot_id": "12345678-1234-1234-1234-123456789abc",
        "invocation_id": "33" * 16,
        "pid": 123,
        "starttime": 789,
        "unified_cgroup": f"/system.slice/{run}",
    }
    acquisition = _acquisition(
        tmp_path,
        "run-main",
        run,
        actor,
        adversary="h10-gc-negative",
        source_receipt=actor_receipt,
    )
    _write(
        actor_receipt,
        {
            "schema": "scion.generic_backend.systemd_adversary_receipt.v1",
            "scenario": "h10-gc-negative",
            "unit": run,
            "actor": actor,
        },
    )
    (
        descriptor,
        install,
        program,
        boot,
        input_root,
        receipts,
        preflight_receipt,
        static_inventory,
        static_roles,
    ) = _full_harness_authorities(
        tmp_path,
        run=run,
        closer=None,
        acquisitions=(acquisition,),
    )
    outputs = tuple(
        harness.OutputPath(
            role,
            (input_root if role == "run-main-properties" else receipts)
            / f"{role}.json",
        )
        for role in sorted(harness._SCENARIO_POLICIES["H10"].required_outputs)
    )
    manifest = harness.HarnessManifest(
        "H10",
        descriptor,
        install,
        program,
        run,
        None,
        harness.PinnedFile(boot, boot.lstat().st_dev, boot.lstat().st_ino),
        input_root,
        receipts,
        (acquisition,),
        (),
        outputs,
        {"actor_receipt_path": str(actor_receipt)},
        preflight_receipt,
        static_inventory,
        static_roles,
    )
    return _with_execution_manifest_source(manifest)


def _with_execution_manifest_source(
    manifest: harness.HarnessManifest,
) -> harness.HarnessManifest:
    install = json.loads(
        manifest.installer_receipt.path.read_text(encoding="ascii")
    )
    root = Path(install["formal_root"]["path"])
    path = root / "authority" / "harness" / manifest.scenario / "MANIFEST.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o711)
    os.chmod(root / "authority", 0o700)
    cursor = root / "authority"
    for component in ("harness", *Path(manifest.scenario).parts):
        cursor /= component
        os.chmod(cursor, 0o700)
    _write(
        path,
        {
            "schema": "scion.test.execution_manifest_source.v1",
            "scenario": manifest.scenario,
        },
    )
    os.chmod(path, 0o444)
    source, _raw = harness.ExecutionManifestSource.open_once(
        path, require_root=False
    )
    return replace(manifest, source=source)


def _frozen_asset(path: Path) -> dict[str, str]:
    info = path.lstat()
    return {
        "path": str(path),
        "sha256": _sha(path),
        "device": str(info.st_dev),
        "inode": str(info.st_ino),
        "mode": format(stat.S_IMODE(info.st_mode), "04o"),
    }


def _rewrite_frozen_json(path: Path, value: Any) -> None:
    os.chmod(path, 0o644)
    _write(path, value)
    os.chmod(path, 0o444)


def _append_unconsumed_inventory_asset(
    manifest: harness.HarnessManifest, *, leave_file_present: bool
) -> harness.HarnessManifest:
    assert manifest.static_inventory is not None
    assert manifest.preflight_receipt is not None
    inventory_path = manifest.static_inventory.path
    extra_path = inventory_path.parent / "unconsumed-static-input.bin"
    parent_mode = stat.S_IMODE(extra_path.parent.lstat().st_mode)
    os.chmod(extra_path.parent, 0o755)
    extra_path.write_bytes(b"unconsumed\n")
    os.chmod(extra_path, 0o444)
    os.chmod(extra_path.parent, parent_mode)
    extra_binding = _frozen_asset(extra_path)
    line = "\t".join(
        (
            "asset",
            "unconsumed-static-input",
            "static-input",
            extra_binding["path"],
            extra_binding["sha256"],
            extra_binding["device"],
            extra_binding["inode"],
            extra_binding["mode"],
        )
    ) + "\n"
    os.chmod(inventory_path, 0o644)
    inventory_path.write_bytes(inventory_path.read_bytes() + line.encode("ascii"))
    os.chmod(inventory_path, 0o444)
    inventory_binding = _frozen_asset(inventory_path)

    preflight_path = manifest.preflight_receipt.path
    preflight = json.loads(preflight_path.read_text(encoding="ascii"))
    seal_path = Path(preflight["seal_receipt"]["path"])
    seal = json.loads(seal_path.read_text(encoding="ascii"))
    inventory_rows = [
        item for item in seal["files"] if item["path"] == str(inventory_path)
    ]
    assert len(inventory_rows) == 1
    inventory_rows[0].update(inventory_binding)
    seal["files"].append(
        {"role": "unconsumed-static-input", **extra_binding}
    )
    _rewrite_frozen_json(seal_path, seal)
    seal_binding = _frozen_asset(seal_path)

    preflight["inventory_manifest"] = inventory_binding
    preflight["seal_receipt"] = seal_binding
    preflight["asset_count"] = str(int(preflight["asset_count"]) + 1)
    _rewrite_frozen_json(preflight_path, preflight)
    preflight_binding = _frozen_asset(preflight_path)

    install_path = manifest.installer_receipt.path
    install = json.loads(install_path.read_text(encoding="ascii"))
    install_manifest_path = Path(install["install_manifest"]["path"])
    install_manifest = json.loads(
        install_manifest_path.read_text(encoding="ascii")
    )
    seal_reference = {
        key: seal_binding[key] for key in ("path", "sha256", "device", "inode")
    }
    preflight_reference = {
        key: preflight_binding[key]
        for key in ("path", "sha256", "device", "inode")
    }
    install_manifest["seal_receipt"] = seal_reference
    install_manifest["preflight_receipt"] = preflight_reference
    _rewrite_frozen_json(install_manifest_path, install_manifest)
    install_manifest_binding = _frozen_asset(install_manifest_path)
    install["install_manifest"] = install_manifest_binding
    install["seal_receipt"] = seal_reference
    install["preflight_receipt"] = preflight_reference
    _rewrite_frozen_json(install_path, install)
    if not leave_file_present:
        os.chmod(extra_path.parent, 0o755)
        extra_path.unlink()
        os.chmod(extra_path.parent, parent_mode)
    return replace(
        manifest,
        installer_receipt=harness.HashedFile(install_path, _sha(install_path)),
        preflight_receipt=harness.HashedFile(preflight_path, _sha(preflight_path)),
        static_inventory=harness.HashedFile(inventory_path, _sha(inventory_path)),
    )


def _swap_installer_harness_inventory_kinds(
    manifest: harness.HarnessManifest,
) -> harness.HarnessManifest:
    assert manifest.static_inventory is not None
    assert manifest.preflight_receipt is not None
    inventory_path = manifest.static_inventory.path
    lines = inventory_path.read_text(encoding="ascii").splitlines(keepends=True)
    installer_prefix = "asset\tinstaller-program\tinstaller-program\t"
    harness_prefix = "asset\tharness-program\tharness-program\t"
    swapped: list[str] = []
    counts = {"installer": 0, "harness": 0}
    for line in lines:
        if line.startswith(installer_prefix):
            swapped.append(line.replace(installer_prefix, "asset\tinstaller-program\tharness-program\t", 1))
            counts["installer"] += 1
        elif line.startswith(harness_prefix):
            swapped.append(line.replace(harness_prefix, "asset\tharness-program\tinstaller-program\t", 1))
            counts["harness"] += 1
        else:
            swapped.append(line)
    assert counts == {"installer": 1, "harness": 1}
    os.chmod(inventory_path, 0o644)
    inventory_path.write_text("".join(swapped), encoding="ascii")
    os.chmod(inventory_path, 0o444)
    inventory_binding = _frozen_asset(inventory_path)

    preflight_path = manifest.preflight_receipt.path
    preflight = json.loads(preflight_path.read_text(encoding="ascii"))
    seal_path = Path(preflight["seal_receipt"]["path"])
    seal = json.loads(seal_path.read_text(encoding="ascii"))
    inventory_records = [
        item for item in seal["files"] if item["path"] == str(inventory_path)
    ]
    assert len(inventory_records) == 1
    inventory_records[0].update(inventory_binding)
    _rewrite_frozen_json(seal_path, seal)
    seal_binding = _frozen_asset(seal_path)

    preflight["inventory_manifest"] = inventory_binding
    preflight["seal_receipt"] = seal_binding
    _rewrite_frozen_json(preflight_path, preflight)
    preflight_binding = _frozen_asset(preflight_path)

    install_path = manifest.installer_receipt.path
    install = json.loads(install_path.read_text(encoding="ascii"))
    install_manifest_path = Path(install["install_manifest"]["path"])
    install_manifest = json.loads(
        install_manifest_path.read_text(encoding="ascii")
    )
    seal_reference = {key: seal_binding[key] for key in ("path", "sha256", "device", "inode")}
    preflight_reference = {
        key: preflight_binding[key]
        for key in ("path", "sha256", "device", "inode")
    }
    install_manifest["seal_receipt"] = seal_reference
    install_manifest["preflight_receipt"] = preflight_reference
    _rewrite_frozen_json(install_manifest_path, install_manifest)
    install_manifest_binding = _frozen_asset(install_manifest_path)

    install["install_manifest"] = install_manifest_binding
    install["seal_receipt"] = seal_reference
    install["preflight_receipt"] = preflight_reference
    _rewrite_frozen_json(install_path, install)
    return replace(
        manifest,
        installer_receipt=harness.HashedFile(install_path, _sha(install_path)),
        preflight_receipt=harness.HashedFile(preflight_path, _sha(preflight_path)),
        static_inventory=harness.HashedFile(inventory_path, _sha(inventory_path)),
    )


def test_static_inventory_exact_authority_closure_accepts_the_bound_chain(
    tmp_path: Path,
) -> None:
    manifest = _authority_closure_manifest(tmp_path)
    authority = manifest.prevalidate(require_root=False)
    assert authority["start_descriptor"].unit == manifest.run_unit
    assert authority["assets"]["harness-program"]["path"] == str(
        manifest.harness_program.path
    )
    assert set(authority["assets"]) == set(authority["retained_assets"])
    harness._close_retained_static_authority(authority)


def test_static_role_binding_decode_is_reference_only(tmp_path: Path) -> None:
    missing_plan = tmp_path / "missing-plan.json"
    missing_program = tmp_path / "missing-program.py"
    binding = harness.StaticRoleBinding.decode(
        {
            "role": "run-main",
            "unit": "scion-w3-reference-only.service",
            "owner": "adversary",
            "mode": "h10-gc-negative",
            "plan": {"path": str(missing_plan), "sha256": "11" * 32},
            "program": {"path": str(missing_program), "sha256": "22" * 32},
        },
        label="static_roles[0]",
    )
    assert binding.plan.path == missing_plan
    assert binding.program.path == missing_program


@pytest.mark.parametrize("leave_file_present", (True, False))
def test_static_inventory_rejects_every_unconsumed_row(
    tmp_path: Path, leave_file_present: bool
) -> None:
    manifest = _append_unconsumed_inventory_asset(
        _authority_closure_manifest(tmp_path),
        leave_file_present=leave_file_present,
    )
    with pytest.raises(harness.HarnessError, match="unconsumed-static-input"):
        manifest.prevalidate(require_root=False)


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("layout", "outside its exact root layout"),
        ("inode", "execution manifest source path identity"),
    ),
)
def test_execution_manifest_source_layout_or_identity_drift_rejects_preflight(
    tmp_path: Path, mutation: str, message: str
) -> None:
    manifest = _authority_closure_manifest(tmp_path)
    assert manifest.source is not None
    if mutation == "layout":
        decoy = tmp_path / "MANIFEST.json"
        decoy.write_bytes(manifest.source.path.read_bytes())
        os.chmod(decoy, 0o444)
        with pytest.raises(harness.HarnessError, match="parent-chain layout"):
            harness.ExecutionManifestSource.open_once(
                decoy, require_root=False
            )
        return
    else:
        replacement = tmp_path / "replacement-MANIFEST.json"
        replacement.write_bytes(manifest.source.path.read_bytes())
        os.chmod(replacement, 0o444)
        os.replace(replacement, manifest.source.path)
    manager = NoExternalCalls()
    journal = NoExternalCalls()
    with pytest.raises(harness.HarnessError, match=message):
        harness.FormalSystemHarness(
            manifest, manager, journal, require_root=False
        ).run()
    assert manager.calls == []
    assert journal.calls == []


@pytest.mark.parametrize("mutation", ("symlink-parent", "wrong-mode"))
def test_execution_manifest_source_rejects_unretained_parent_chain(
    tmp_path: Path, mutation: str
) -> None:
    root = tmp_path / f"manifest-{mutation}"
    authority = root / "authority"
    harness_root = authority / "harness"
    scenario = harness_root / "H10"
    for directory, mode in (
        (root, 0o711),
        (authority, 0o700),
        (harness_root, 0o700),
    ):
        directory.mkdir(exist_ok=True)
        os.chmod(directory, mode)
    if mutation == "symlink-parent":
        target = tmp_path / "manifest-real-scenario"
        target.mkdir()
        os.chmod(target, 0o700)
        _write(target / "MANIFEST.json", {"schema": "scion.test.v1"})
        os.chmod(target / "MANIFEST.json", 0o444)
        scenario.symlink_to(target, target_is_directory=True)
    else:
        scenario.mkdir()
        os.chmod(scenario, 0o755)
        _write(scenario / "MANIFEST.json", {"schema": "scion.test.v1"})
        os.chmod(scenario / "MANIFEST.json", 0o444)
    with pytest.raises(harness.HarnessError, match="manifest directory|parent-chain"):
        harness.ExecutionManifestSource.open_once(
            scenario / "MANIFEST.json", require_root=False
        )


def test_execution_manifest_source_revalidates_retained_parent_dirfds(
    tmp_path: Path,
) -> None:
    manifest = _authority_closure_manifest(tmp_path)
    assert manifest.source is not None
    source = manifest.source
    scenario = source.path.parent
    displaced = scenario.with_name("H10-displaced")
    scenario.rename(displaced)
    scenario.mkdir(mode=0o700)
    scenario.chmod(0o700)
    source.path.write_bytes(source.raw)
    source.path.chmod(0o444)
    try:
        with pytest.raises(harness.HarnessError, match="parent-chain directory"):
            source.revalidate(require_root=False)
    finally:
        source.close()


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("inventory-inode", "preflight-bound static inventory.*drifted"),
        ("descriptor-decoy", "StartUnit descriptor.*unique exact"),
        ("harness-decoy", "current exact program path"),
        ("installer-decoy", "root installer program.*unique exact"),
        ("installer-kind-swap", "root installer program.*unique exact"),
        ("role-inode", "run-main static plan.*drifted"),
        ("preexisting-armed", "ARMED destination exists before StartUnit"),
    ),
)
def test_static_inventory_authority_drift_rejects_before_any_external_seam(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    message: str,
) -> None:
    manifest = _authority_closure_manifest(tmp_path)
    if mutation == "inventory-inode":
        assert manifest.static_inventory is not None
        path = manifest.static_inventory.path
        replacement = tmp_path / "replacement-inventory.tsv"
        replacement.write_bytes(path.read_bytes())
        os.chmod(replacement, 0o444)
        original_inode = path.lstat().st_ino
        os.chmod(path.parent, 0o755)
        os.replace(replacement, path)
        os.chmod(path.parent, 0o555)
        assert path.lstat().st_ino != original_inode
    elif mutation in {"descriptor-decoy", "harness-decoy"}:
        source = (
            manifest.descriptor.path
            if mutation == "descriptor-decoy"
            else manifest.harness_program.path
        )
        decoy = tmp_path / f"{mutation}.asset"
        decoy.write_bytes(source.read_bytes())
        os.chmod(decoy, 0o444)
        reference = harness.HashedFile(decoy, _sha(decoy))
        manifest = replace(
            manifest,
            **(
                {"descriptor": reference}
                if mutation == "descriptor-decoy"
                else {"harness_program": reference}
            ),
        )
    elif mutation == "installer-decoy":
        install_path = manifest.installer_receipt.path
        install = json.loads(install_path.read_text(encoding="ascii"))
        installer_path = Path(install["installer"]["path"])
        decoy = tmp_path / "installer-decoy.py"
        decoy.write_bytes(installer_path.read_bytes())
        os.chmod(decoy, 0o444)
        install["installer"] = _frozen_asset(decoy)
        _rewrite_frozen_json(install_path, install)
        manifest = replace(
            manifest,
            installer_receipt=harness.HashedFile(install_path, _sha(install_path)),
        )
    elif mutation == "installer-kind-swap":
        manifest = _swap_installer_harness_inventory_kinds(manifest)
    elif mutation == "preexisting-armed":
        _write(
            manifest.acquisitions[0].armed_receipt_path,
            _PENDING_ARMED[manifest.acquisitions[0].armed_receipt_path],
        )
    else:
        role_path = manifest.static_roles[0].plan.path
        replacement = tmp_path / "replacement-role-plan.json"
        replacement.write_bytes(role_path.read_bytes())
        os.chmod(replacement, 0o444)
        os.chmod(role_path.parent, 0o755)
        os.replace(replacement, role_path)
        os.chmod(role_path.parent, 0o555)

    fifo_opens: list[str] = []

    def forbidden_fifo_open(
        cls: type[harness.PinnedAcquisition], acquisition: Any
    ) -> Any:
        del cls
        fifo_opens.append(acquisition.role)
        raise AssertionError("FIFO pin occurred before authority closure")

    monkeypatch.setattr(
        harness.PinnedAcquisition,
        "open",
        classmethod(forbidden_fifo_open),
    )
    manager = NoExternalCalls()
    journal = NoExternalCalls()
    with pytest.raises(harness.HarnessError, match=message):
        harness.FormalSystemHarness(
            manifest, manager, journal, require_root=False
        ).run()
    assert manager.calls == []
    assert journal.calls == []
    assert fifo_opens == []


@pytest.mark.parametrize(
    ("mutation", "message", "start_called"),
    (
        ("before-start-static", "retained static asset start-descriptor.*drifted", False),
        ("h0-create-remove", "final StartUnit boundary", False),
        ("pre-start-create-remove", "final StartUnit boundary", False),
        ("ready-no-armed", "ARMED creation event", True),
        ("duplicate-armed-event", "exactly one post-Start creation event", True),
        ("late-role-path", "run-main static plan.*drifted", True),
    ),
)
def test_retained_static_and_post_ready_armed_handoff_fail_closed(
    tmp_path: Path,
    mutation: str,
    message: str,
    start_called: bool,
) -> None:
    manifest = _authority_closure_manifest(tmp_path)
    acquisition = manifest.acquisitions[0]

    def replace_same_bytes(path: Path, name: str) -> None:
        replacement = tmp_path / name
        replacement.write_bytes(path.read_bytes())
        os.chmod(replacement, stat.S_IMODE(path.lstat().st_mode))
        parent_mode = stat.S_IMODE(path.parent.lstat().st_mode)
        os.chmod(path.parent, 0o755)
        os.replace(replacement, path)
        os.chmod(path.parent, parent_mode)

    class LifecycleMutationManager(FakeManager):
        h0_mutated = False

        def property(self, object_path: str, interface: str, name: str) -> Any:
            if mutation == "h0-create-remove" and not self.h0_mutated:
                self.h0_mutated = True
                _write(
                    acquisition.armed_receipt_path,
                    _PENDING_ARMED[acquisition.armed_receipt_path],
                )
                acquisition.armed_receipt_path.unlink()
            return super().property(object_path, interface, name)

        def install_signal_handlers(self, callback: Callable[[Any], None]) -> None:
            super().install_signal_handlers(callback)
            if mutation == "before-start-static":
                replace_same_bytes(manifest.descriptor.path, "descriptor-replacement")
            elif mutation == "pre-start-create-remove":
                _write(
                    acquisition.armed_receipt_path,
                    _PENDING_ARMED[acquisition.armed_receipt_path],
                )
                acquisition.armed_receipt_path.unlink()

    def on_ready(_role: str) -> None:
        if mutation == "ready-no-armed":
            acquisition.armed_receipt_path.unlink()
        elif mutation == "duplicate-armed-event":
            replace_same_bytes(
                acquisition.armed_receipt_path, "armed-replacement.json"
            )
        elif mutation == "late-role-path":
            replace_same_bytes(
                manifest.static_roles[0].plan.path, "role-plan-replacement"
            )

    pending = _pending_armed(acquisition)
    identity = pending["actor"]
    manager = LifecycleMutationManager(
        manifest.run_unit,
        None,
        manifest.acquisitions,
        {manifest.run_unit: bytes.fromhex(identity["invocation_id"])},
        "H10",
        on_ready=on_ready,
    )
    journal = FakeJournal()
    with pytest.raises(harness.HarnessError, match=message):
        harness.FormalSystemHarness(
            manifest, manager, journal, require_root=False
        ).run()
    starts = [call for call in manager.calls if call[0] == "StartUnit"]
    assert bool(starts) is start_called


def test_installer_target_mutation_rejects_before_external_observation(
    tmp_path: Path,
) -> None:
    run = "scion-w3-h0-authority.service"
    (
        descriptor,
        install,
        program,
        boot,
        input_root,
        receipts,
        preflight_receipt,
        static_inventory,
        static_roles,
    ) = _full_harness_authorities(
        tmp_path, run=run, closer=None, acquisitions=()
    )
    payload = json.loads(install.path.read_text(encoding="ascii"))
    payload["units"][0]["target"]["sha256"] = "00" * 32
    os.chmod(install.path, 0o644)
    _write(install.path, payload)
    os.chmod(install.path, 0o444)
    install = harness.HashedFile(install.path, _sha(install.path))
    outputs = tuple(
        harness.OutputPath(role, receipts / f"{role}.json")
        for role in sorted(harness._SCENARIO_POLICIES["H0"].required_outputs)
    )
    manifest = harness.HarnessManifest(
        scenario="H0",
        descriptor=descriptor,
        installer_receipt=install,
        harness_program=program,
        run_unit=run,
        closer_unit=None,
        boot_id_file=harness.PinnedFile(
            boot, boot.lstat().st_dev, boot.lstat().st_ino
        ),
        input_root=input_root,
        receipt_root=receipts,
        acquisitions=(),
        formal_actions=(),
        outputs=outputs,
        scenario_input=None,
        preflight_receipt=preflight_receipt,
        static_inventory=static_inventory,
        static_roles=static_roles,
    )
    manager = NoExternalCalls()
    journal = NoExternalCalls()
    with pytest.raises(harness.HarnessError, match="target .* drifted"):
        harness.FormalSystemHarness(
            manifest, manager, journal, require_root=False
        ).run()
    assert manager.calls == []
    assert journal.calls == []


def test_static_plan_output_mutation_rejects_before_external_observation(
    tmp_path: Path,
) -> None:
    run = "scion-w3-h10-plan.service"
    actor_receipt = tmp_path / "actor.json"
    actor = {
        "boot_id": "12345678-1234-1234-1234-123456789abc",
        "invocation_id": "33" * 16,
        "pid": 123,
        "starttime": 789,
        "unified_cgroup": "/system.slice/" + run,
    }
    acquisition = _acquisition(
        tmp_path,
        "run-main",
        run,
        actor,
        adversary="h10-gc-negative",
        source_receipt=actor_receipt,
    )
    _write(
        actor_receipt,
        {
            "schema": "scion.generic_backend.systemd_adversary_receipt.v1",
            "scenario": "h10-gc-negative",
            "unit": run,
            "actor": actor,
        },
    )

    def mutate_plan(_role: str, plan: dict[str, Any]) -> None:
        plan["receipt_path"] = str(tmp_path / "unbound-actor.json")

    (
        descriptor,
        install,
        program,
        boot,
        input_root,
        receipts,
        preflight_receipt,
        static_inventory,
        static_roles,
    ) = _full_harness_authorities(
        tmp_path,
        run=run,
        closer=None,
        acquisitions=(acquisition,),
        plan_mutator=mutate_plan,
    )
    outputs = tuple(
        harness.OutputPath(
            role,
            (input_root if role == "run-main-properties" else receipts)
            / f"{role}.json",
        )
        for role in sorted(harness._SCENARIO_POLICIES["H10"].required_outputs)
    )
    manifest = harness.HarnessManifest(
        scenario="H10",
        descriptor=descriptor,
        installer_receipt=install,
        harness_program=program,
        run_unit=run,
        closer_unit=None,
        boot_id_file=harness.PinnedFile(
            boot, boot.lstat().st_dev, boot.lstat().st_ino
        ),
        input_root=input_root,
        receipt_root=receipts,
        acquisitions=(acquisition,),
        formal_actions=(),
        outputs=outputs,
        scenario_input={"actor_receipt_path": str(actor_receipt)},
        preflight_receipt=preflight_receipt,
        static_inventory=static_inventory,
        static_roles=static_roles,
    )
    manager = NoExternalCalls()
    journal = NoExternalCalls()
    with pytest.raises(harness.HarnessError, match="H10 actor receipt"):
        harness.FormalSystemHarness(
            manifest, manager, journal, require_root=False
        ).run()
    assert manager.calls == []
    assert journal.calls == []


def test_manifest_order_rejects_before_manager_journal_or_fifo_side_effect(
    tmp_path: Path,
) -> None:
    run = "scion-w3-prevalidation.service"
    closer = "scion-w3-prevalidation-close.service"
    boot_id = "12345678-1234-1234-1234-123456789abc"
    invocation = "55" * 16
    run_group = "/system.slice/" + run
    closer_group = "/system.slice/" + closer
    acquisitions = (
        _acquisition(
            tmp_path,
            "exec-stop-post",
            run,
            {
                "boot_id": boot_id,
                "invocation_id": invocation,
                "pid": 102,
                "starttime": 202,
                "unified_cgroup": run_group + "/.control",
            },
        ),
        _acquisition(
            tmp_path,
            "run-main",
            run,
            {
                "boot_id": boot_id,
                "invocation_id": invocation,
                "pid": 101,
                "starttime": 201,
                "unified_cgroup": run_group + "/supervisor",
            },
        ),
        _acquisition(
            tmp_path,
            "closer",
            closer,
            {
                "boot_id": boot_id,
                "invocation_id": "66" * 16,
                "pid": 103,
                "starttime": 203,
                "unified_cgroup": closer_group,
            },
        ),
    )
    descriptor, install, program, boot, input_root, receipts = _common_authorities(
        tmp_path, run
    )
    outputs = tuple(
        harness.OutputPath(role, receipts / f"{role}.json")
        for role in sorted(harness._SCENARIO_POLICIES["H1"].required_outputs)
    )
    manifest = harness.HarnessManifest(
        "H1",
        descriptor,
        install,
        program,
        run,
        closer,
        harness.PinnedFile(boot, boot.lstat().st_dev, boot.lstat().st_ino),
        input_root,
        receipts,
        acquisitions,
        (),
        outputs,
        None,
    )

    class Untouched:
        owner = ":1.255"
        binding_receipt = None
        calls: list[str] = []

        def __getattr__(self, name: str) -> Any:
            self.calls.append(name)
            raise AssertionError(name)

    manager = Untouched()
    journal = Untouched()
    with pytest.raises(harness.HarnessError, match="acquisition order"):
        harness.FormalSystemHarness(
            manifest, manager, journal, require_root=False
        ).run()
    assert manager.calls == []
    assert journal.calls == []


def _positive_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str
) -> tuple[Any, FakeManager, FakeJournal]:
    run = f"scion-w3-{scenario.lower()}.service"
    closer = f"scion-w3-{scenario.lower()}-close.service"
    boot_id = "12345678-1234-1234-1234-123456789abc"
    run_id = "11" * 16
    closer_id = "22" * 16
    run_group = "/system.slice/" + run
    closer_group = "/system.slice/" + closer
    run_actor = {"boot_id": boot_id, "invocation_id": run_id, "pid": 123, "starttime": 456, "unified_cgroup": run_group + "/supervisor"}
    stop_actor = {"boot_id": boot_id, "invocation_id": run_id, "pid": 124, "starttime": 457, "unified_cgroup": run_group + "/.control"}
    closer_actor = {"boot_id": boot_id, "invocation_id": closer_id, "pid": 223, "starttime": 556, "unified_cgroup": closer_group}
    source = tmp_path / "source-terminal.json"
    _write(source, {"schema": "scion.generic_backend.systemd_observer_receipt.v1", "unit": run, "process_identity": stop_actor})
    acquisitions = (
        _acquisition(tmp_path, "run-main", run, run_actor, adversary="h7-guardian-hold" if scenario == "H7" else "h8-extra-topology-hold"),
        _acquisition(tmp_path, "exec-stop-post", run, stop_actor, source_receipt=source),
        _acquisition(tmp_path, "closer", closer, closer_actor),
    )
    cgroups = tmp_path / "cgroups"
    run_dir = cgroups / "run"
    closer_dir = cgroups / "closer"
    (run_dir / "supervisor").mkdir(parents=True)
    (run_dir / ".control").mkdir()
    closer_dir.mkdir()
    (run_dir / "cgroup.procs").write_text("")
    (run_dir / "supervisor" / "cgroup.procs").write_text("123\n")
    (run_dir / ".control" / "cgroup.procs").write_text("124\n")
    (closer_dir / "cgroup.procs").write_text("223\n")

    def open_cgroup(lineage: str):
        directory = run_dir if lineage == run_group else closer_dir
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        info = os.fstat(fd)
        return fd, {"path": lineage, "device": str(info.st_dev), "inode": str(info.st_ino)}

    def on_ready(role: str) -> None:
        if role == "exec-stop-post":
            (run_dir / "supervisor" / "cgroup.procs").write_text("")
            for child in run_dir.glob("job-*"):
                (child / "cgroup.procs").write_text("")
                if scenario == "H8":
                    (child / "cgroup.procs").unlink()

    monkeypatch.setattr(harness, "_open_cgroup_from_manager", open_cgroup)
    descriptor, install, program, boot, input_root, receipts = _common_authorities(tmp_path, run)
    output_roles = tuple(f"{item.role}-properties" for item in acquisitions) + ("source-selector", "final-run-properties", "final-closer-properties", "h12-absence", "h0", "signals", "journal", "final")
    outputs = tuple(harness.OutputPath(role, (input_root if role.endswith("-properties") and not role.startswith("final-") else receipts) / f"{role}.json") for role in output_roles)
    required = set(harness._SCENARIO_POLICIES[scenario].required_outputs)
    outputs = tuple(
        harness.OutputPath(
            role,
            (input_root if role.endswith("-properties") and not role.startswith("final-") else receipts)
            / f"{role}.json",
        )
        for role in sorted(required)
    )
    output_by_role = {item.role: item.path for item in outputs}
    for acquisition in acquisitions:
        payload = _pending_armed(acquisition)
        if payload["schema"] == "scion.generic_backend.systemd_observer_armed.v1":
            payload["raw_authority_paths"] = [
                str(output_by_role[f"{acquisition.role}-properties"])
            ]
            if acquisition.role == "closer":
                payload["source_selector_path"] = str(
                    output_by_role["source-selector"]
                )
            if acquisition.role == "exec-stop-post" and scenario == "H7":
                payload["stop_post_environment"] = {
                    "INVOCATION_ID": run_id,
                    "SERVICE_RESULT": "signal",
                    "EXIT_CODE": "killed",
                    "EXIT_STATUS": "15",
                }
        _set_pending_armed(acquisition, payload)
    (
        descriptor, install, program, boot, input_root, receipts,
        preflight_receipt, static_inventory, static_roles,
    ) = _full_harness_authorities(
        tmp_path, run=run, closer=closer, acquisitions=acquisitions
    )
    scenario_input = (
        {
            "drift_name": "job-1-0123456789abcdef",
            "ledger_path": str(output_by_role["h8-ledger"]),
        }
        if scenario == "H8"
        else None
    )
    manifest = harness.HarnessManifest(
        scenario,
        descriptor,
        install,
        program,
        run,
        closer,
        harness.PinnedFile(boot, boot.lstat().st_dev, boot.lstat().st_ino),
        input_root,
        receipts,
        acquisitions,
        (),
        outputs,
        scenario_input,
        preflight_receipt,
        static_inventory,
        static_roles,
    )
    manifest = _with_execution_manifest_source(manifest)
    manager = FakeManager(
        run,
        closer,
        acquisitions,
        {run: bytes.fromhex(run_id), closer: bytes.fromhex(closer_id)},
        scenario,
        on_ready,
    )
    journal = FakeJournal()
    result = harness.FormalSystemHarness(
        manifest,
        manager,
        journal,
        require_root=False,
        proc_starttime_reader=lambda pid: None,
    ).run()
    return result, manager, journal


@pytest.mark.parametrize("scenario", ["H7", "H8"])
def test_h7_h8_real_armed_shapes_typed_decoders_and_release_rules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str
) -> None:
    result, manager, journal = _positive_fixture(tmp_path, monkeypatch, scenario)
    assert result["execution_manifest_source"] is not None
    h0 = json.loads((tmp_path / "receipts" / "h0.json").read_text())
    assert h0["execution_manifest_source"] == result["execution_manifest_source"]
    assert len([call for call in manager.calls if call[0] == "StartUnit"]) == 1
    assert len([call for call in manager.calls if call[0] == "StopUnit"]) == (1 if scenario == "H7" else 0)
    for role, fd in manager.release_readers.items():
        raw = os.read(fd, 4096)
        assert raw == (b"" if scenario == "H7" and role == "run-main" else harness.RELEASE_BYTES)
        os.close(fd)
    run_raw = json.loads((tmp_path / "input" / "run-main-properties.json").read_text())
    stop_raw = json.loads((tmp_path / "input" / "exec-stop-post-properties.json").read_text())
    final_raw = json.loads((tmp_path / "receipts" / "final-run-properties.json").read_text())
    assert run_raw["normalization"]["lineage"]["decoder"] == "InvocationLineage"
    if scenario == "H7":
        assert stop_raw["normalization"]["stop_post"]["topology_decoder"] == "StopPostTopology"
    else:
        assert stop_raw["normalization"]["stop_post"]["classification"] == "formal-negative-evidence/H8_EXTRA_TOPOLOGY"
        assert stop_raw["normalization"]["stop_post"]["positive_stop_topology_decoder_called"] is False
    assert final_raw["normalization"]["handoff"]["decoder"] == "UnitHandoffProperties"
    absence = json.loads((tmp_path / "receipts" / "h12-absence.json").read_text())
    assert absence["actor_count"] == "3"
    assert [actor["role"] for actor in absence["actors"]] == [
        "run-main",
        "exec-stop-post",
        "closer",
    ]
    assert journal.calls[-2:] == ["synchronize", "freeze"]
    assert result["remaining_refs"] == []
    if scenario == "H8":
        ledger = json.loads((tmp_path / "receipts" / "h8-ledger.json").read_text())
        assert ledger["mkdir_relative_to_pinned_dirfd"] is True
        assert result["classification"] == "formal-negative-evidence/H8_EXTRA_TOPOLOGY"


def test_h10_acquires_before_unit_removed_then_loads_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = "scion-w3-h10.service"
    boot_id = "12345678-1234-1234-1234-123456789abc"
    invocation = "33" * 16
    lineage = "/system.slice/" + run
    actor = {"boot_id": boot_id, "invocation_id": invocation, "pid": 123, "starttime": 789, "unified_cgroup": lineage}
    actor_receipt = tmp_path / "actor.json"
    acquisition = _acquisition(tmp_path, "run-main", run, actor, adversary="h10-gc-negative", source_receipt=actor_receipt)
    _write(actor_receipt, {"schema": "scion.generic_backend.systemd_adversary_receipt.v1", "scenario": "h10-gc-negative", "unit": run, "actor": actor})
    cgroup = tmp_path / "cgroup"
    cgroup.mkdir(parents=True)
    (cgroup / "cgroup.procs").write_text("")

    def open_cgroup(value: str):
        assert value == lineage
        fd = os.open(cgroup, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        info = os.fstat(fd)
        return fd, {"path": value, "device": str(info.st_dev), "inode": str(info.st_ino)}

    monkeypatch.setattr(harness, "_open_cgroup_from_manager", open_cgroup)
    descriptor, install, program, boot, input_root, receipts = _common_authorities(tmp_path, run)
    roles = tuple(sorted(harness._SCENARIO_POLICIES["H10"].required_outputs))
    outputs = tuple(harness.OutputPath(role, (input_root if role == "run-main-properties" else receipts) / f"{role}.json") for role in roles)
    (
        descriptor, install, program, boot, input_root, receipts,
        preflight_receipt, static_inventory, static_roles,
    ) = _full_harness_authorities(
        tmp_path, run=run, closer=None, acquisitions=(acquisition,)
    )
    manifest = harness.HarnessManifest("H10", descriptor, install, program, run, None, harness.PinnedFile(boot, boot.lstat().st_dev, boot.lstat().st_ino), input_root, receipts, (acquisition,), (), outputs, {"actor_receipt_path": str(actor_receipt)}, preflight_receipt, static_inventory, static_roles)
    manager = FakeManager(run, None, (acquisition,), {run: bytes.fromhex(invocation)}, "H10")
    result = harness.FormalSystemHarness(manifest, manager, FakeJournal(), require_root=False).run()
    assert result["classification"] == "rejected-failed-identity-loss"
    assert [call for call in manager.calls if call[0] == "LoadUnit"] == [("LoadUnit", run)]
    fd = manager.release_readers["run-main"]
    assert os.read(fd, 4096) == harness.RELEASE_BYTES
    os.close(fd)


def test_source_selector_binds_exact_terminal_receipt(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_text("{}\n")
    target = tmp_path / "selector.json"
    selector = harness.seal_source_selector(boot_id="12345678-1234-1234-1234-123456789abc", source_unit="scion-w3-h4.service", source_invocation_id="ab" * 16, source_receipt_path=source, selector_path=target)
    assert set(selector) == {"schema", "boot_id", "source_unit", "source_invocation_id", "source_receipt_sha256"}
    assert selector["source_receipt_sha256"] == _sha(source)


@pytest.mark.parametrize(
    "mutation", [None, "action-id", "variant", "outer-sha", "service-inode"]
)
def test_formal_action_armed_cross_binds_typed_blocked_spawn(
    tmp_path: Path, mutation: str | None
) -> None:
    from scion.runtime.execution.model import CgroupIdentity, ProcessIdentity

    unit = "scion-w3-b4-action.service"
    ready = tmp_path / "control"
    os.mkfifo(ready, 0o600)
    fifo = harness.FifoIdentity(ready, ready.lstat().st_dev, ready.lstat().st_ino)
    action = harness.FormalAction(
        "b4-kill-before-release",
        tmp_path / "action-armed.json",
        None,
        tmp_path / "action-ledger.json",
        fifo,
    )
    outer_identity = {
        "boot_id": "12345678-1234-1234-1234-123456789abc",
        "invocation_id": "77" * 16,
        "pid": 701,
        "proc_cgroup_raw": f"0::/system.slice/{unit}/supervisor\n",
        "starttime": 801,
        "unified_cgroup": f"/system.slice/{unit}/supervisor",
        "service_control_group": f"/system.slice/{unit}",
        "service_device": 11,
        "service_inode": 12,
        "supervisor_device": 11,
        "supervisor_inode": 13,
    }
    outer_receipt = {
        "schema": harness.FORMAL_ARMED_SCHEMA,
        "unit": unit,
        "plan_sha256": "aa" * 32,
    }
    outer = {"unit": unit, "identity": outer_identity, "receipt": outer_receipt}
    process = ProcessIdentity(901, 902, 14, 15, 701, 801).to_mapping()
    cgroup = CgroupIdentity(
        unit,
        "supervisor",
        "job-1-0123456789abcdef",
        11,
        12,
        11,
        13,
        11,
        16,
        (unit, "job-1-0123456789abcdef"),
    ).to_mapping()
    payload = {
        "schema": harness.FORMAL_ACTION_ARMED_SCHEMA,
        "action_id": action.action_id,
        "case_id": "B4",
        "variant": "release-after-job-kill",
        "unit": unit,
        "process_identity": process,
        "cgroup_identity": cgroup,
        "control_fifo": {
            "path": str(ready),
            "device": str(fifo.device),
            "inode": str(fifo.inode),
        },
        "systemd_armed_receipt_sha256": hashlib.sha256(
            _canonical(outer_receipt)
        ).hexdigest(),
        "plan_sha256": outer_receipt["plan_sha256"],
        "expected_permit_sha256": hashlib.sha256(
            b"JOB_CGROUP_KILLED\n"
        ).hexdigest(),
    }
    if mutation == "action-id":
        payload["action_id"] = "b4-other"
    elif mutation == "variant":
        payload["variant"] = "clean"
    elif mutation == "outer-sha":
        payload["systemd_armed_receipt_sha256"] = "00" * 32
    elif mutation == "service-inode":
        payload["cgroup_identity"]["service_inode"] += 1
    _write(action.armed_receipt_path, payload)
    if mutation is None:
        accepted = harness._formal_action_armed(
            action,
            harness._SCENARIO_POLICIES["B4/release-after-job-kill"],
            outer,
        )
        assert accepted["cgroup"].job_name == "job-1-0123456789abcdef"
    else:
        with pytest.raises(harness.HarnessError):
            harness._formal_action_armed(
                action,
                harness._SCENARIO_POLICIES["B4/release-after-job-kill"],
                outer,
            )


_B6_HOOK_VARIANTS = {
    "service-consume": "issuer-backend-open",
    "capture-spool-open": "issuer-capture-prepare",
    "pre-native-borrow": "issuer-job-created-pre-native",
    "guard-restore": "issuer-blocked",
    "terminal-fact": "issuer-leader-terminal",
    "reaped-pidfd-close": "issuer-reaped-populated",
    "capture-write": "storage-just-released",
}

_EXPECTED_B6_OPERATION_SEMANTICS = {
    "service-consume": {
        "operation_state": "RETURNED",
        "effect_state": "AUTHORITY_MOVED",
        "return_type": "scion.runtime.execution.cgroup_v2._ServiceCgroupAuthority",
        "exception_type": None,
        "errno": None,
        "postcondition": "exact target operation completed once",
    },
    "capture-spool-open": {
        "operation_state": "RETURNED",
        "effect_state": "FD_ACQUIRED",
        "return_type": "builtins.int",
        "exception_type": None,
        "errno": None,
        "postcondition": "exact target operation completed once",
    },
    "pre-native-borrow": {
        "operation_state": "RETURNED",
        "effect_state": "PINNED_BORROW_RETURNED",
        "return_type": "builtins.int",
        "exception_type": None,
        "errno": None,
        "postcondition": "exact target operation completed once",
    },
    "guard-restore": {
        "operation_state": "RETURNED",
        "effect_state": "MASK_RESTORED_HANDLER_DELIVERED",
        "return_type": "builtins.bool",
        "exception_type": None,
        "errno": None,
        "postcondition": (
            "fixed handler raised inside production restore and guard recovery "
            "returned true"
        ),
    },
    "terminal-fact": {
        "operation_state": "RETURNED",
        "effect_state": "WAIT_FACT_RETURNED",
        "return_type": "scion.runtime.execution.model.WaitFact",
        "exception_type": None,
        "errno": None,
        "postcondition": "exact target operation completed once",
    },
    "reaped-pidfd-close": {
        "operation_state": "RETURNED",
        "effect_state": "PIDFD_CLOSED",
        "return_type": "builtins.NoneType",
        "exception_type": None,
        "errno": None,
        "postcondition": "exact target operation completed once",
    },
    "capture-write": {
        "operation_state": "INJECTED_RETURN",
        "effect_state": "ORIGINAL_STORAGE_WRITE_NOT_CALLED",
        "return_type": "builtins.bool",
        "exception_type": None,
        "errno": None,
        "postcondition": (
            "capture storage became unavailable after one injected false"
        ),
    },
}


def _b6_operation_vector(
    tmp_path: Path, hook: str
) -> tuple[Any, Any, dict[str, Any], dict[str, Any]]:
    variant = _B6_HOOK_VARIANTS[hook]
    abi = harness._B6_ABI[variant]
    operation_path = tmp_path / "operation.json"
    action = harness.FormalAction(
        "b6-issuer-send" if variant.startswith("issuer-") else "b6-zero-signal-release",
        tmp_path / "armed.json",
        operation_path,
        tmp_path / "ledger.json",
        None,
    )
    before = {"pid": 77, "phase": "blocked"}
    armed_receipt = {
        "case_id": "B6",
        "variant": variant,
        "fault": abi["fault"],
        "declared_phase": abi["declared_phase"],
        "hook": abi["hook"],
        "target_operation": abi["target_operation"],
        "planned_ordinal": int(abi["planned_ordinal"]),
        "process_identity": {"pid": 77, "starttime": 88},
        "before_fact": before,
        "release_sha256": hashlib.sha256(harness.RELEASE_BYTES).hexdigest(),
    }
    armed = {"receipt": armed_receipt}
    payload = {
        "schema": harness.B6_OPERATION_SCHEMA,
        "case_id": "B6",
        "variant": variant,
        "fault": abi["fault"],
        "declared_phase": abi["declared_phase"],
        "hook": abi["hook"],
        "target_operation": abi["target_operation"],
        "planned_ordinal": int(abi["planned_ordinal"]),
        "observed_ordinal": int(abi["planned_ordinal"]),
        "injection_count": 1,
        "armed_receipt_sha256": hashlib.sha256(
            _canonical(armed_receipt)
        ).hexdigest(),
        "actor_pid": 77,
        "actor_starttime": 88,
        "before_fact_sha256": hashlib.sha256(_canonical(before)).hexdigest(),
        "release_permit_sha256": hashlib.sha256(
            harness.RELEASE_BYTES
        ).hexdigest(),
        **_EXPECTED_B6_OPERATION_SEMANTICS[hook],
    }
    return action, {"receipt": armed_receipt}, payload, before


@pytest.mark.parametrize("hook", sorted(_B6_HOOK_VARIANTS))
def test_every_b6_hook_operation_tuple_is_exactly_cross_bound(
    tmp_path: Path, hook: str
) -> None:
    action, armed, payload, _before = _b6_operation_vector(tmp_path, hook)
    _write(action.operation_receipt_path, payload)
    accepted = harness._b6_operation(
        action,
        harness._SCENARIO_POLICIES[f"B6/{payload['variant']}"],
        armed,
    )
    assert {
        name: accepted[name] for name in _EXPECTED_B6_OPERATION_SEMANTICS[hook]
    } == _EXPECTED_B6_OPERATION_SEMANTICS[hook]


def test_real_production_guard_returns_true_after_fixed_handler_delivery() -> None:
    from scion.runtime.execution import spawn_backend

    signum = signal.SIGUSR1
    prior_handler = signal.getsignal(signum)
    prior_mask = frozenset(signal.pthread_sigmask(signal.SIG_BLOCK, set()))
    delivered: list[int] = []

    def fixed_handler(received: int, _frame: Any) -> None:
        delivered.append(received)
        raise RuntimeError("fixed handler delivery")

    guard = spawn_backend._IssuerSignalGuard()
    try:
        signal.signal(signum, fixed_handler)
        guard.block()
        os.kill(os.getpid(), signum)
        assert signum in signal.sigpending()
        result = guard.restore()
        assert result is True
        assert delivered == [signum]
        assert _EXPECTED_B6_OPERATION_SEMANTICS["guard-restore"] == {
            "operation_state": "RETURNED",
            "effect_state": "MASK_RESTORED_HANDLER_DELIVERED",
            "return_type": "builtins.bool",
            "exception_type": None,
            "errno": None,
            "postcondition": (
                "fixed handler raised inside production restore and guard recovery "
                "returned true"
            ),
        }
    finally:
        if getattr(guard, "_state", None) == guard._BLOCKED:
            guard.restore()
        signal.signal(signum, prior_handler)
        signal.pthread_sigmask(signal.SIG_SETMASK, prior_mask)


@pytest.mark.parametrize(
    "field",
    (
        "schema",
        "case_id",
        "variant",
        "fault",
        "declared_phase",
        "hook",
        "target_operation",
        "planned_ordinal",
        "observed_ordinal",
        "injection_count",
        "armed_receipt_sha256",
        "actor_pid",
        "actor_starttime",
        "before_fact_sha256",
        "release_permit_sha256",
    ),
)
def test_b6_operation_common_field_mutation_rejects(
    tmp_path: Path, field: str
) -> None:
    action, armed, payload, _before = _b6_operation_vector(
        tmp_path, "capture-write"
    )
    policy = harness._SCENARIO_POLICIES["B6/storage-just-released"]
    original = payload[field]
    payload[field] = original + 1 if type(original) is int else "drift"
    _write(action.operation_receipt_path, payload)
    with pytest.raises(harness.HarnessError):
        harness._b6_operation(action, policy, armed)


@pytest.mark.parametrize("hook", sorted(_B6_HOOK_VARIANTS))
@pytest.mark.parametrize(
    "field",
    (
        "operation_state",
        "effect_state",
        "return_type",
        "exception_type",
        "errno",
        "postcondition",
    ),
)
def test_b6_operation_each_hook_semantic_field_mutation_rejects(
    tmp_path: Path, hook: str, field: str
) -> None:
    action, armed, payload, _before = _b6_operation_vector(tmp_path, hook)
    original = payload[field]
    payload[field] = 5 if field == "errno" else "drift" if original is None else None
    _write(action.operation_receipt_path, payload)
    with pytest.raises(harness.HarnessError):
        harness._b6_operation(
            action,
            harness._SCENARIO_POLICIES[f"B6/{payload['variant']}"],
            armed,
        )


def _encoded_bytes(raw: bytes) -> dict[str, Any]:
    import base64

    return {
        "encoding": "base64",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "byte_length": len(raw),
        "data": base64.b64encode(raw).decode("ascii"),
    }


def _formal_outer_config(
    tmp_path: Path,
    *,
    case_id: str,
    variant: str,
    config_updates: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Path]:
    unit = f"scion-w3-{case_id.lower()}-formal-final.service"
    boot_id = "12345678-1234-1234-1234-123456789abc"
    invocation = "7b" * 16
    program_path = FIXTURES / "generic_backend_formal_case.py"
    program_info = program_path.lstat()
    config_path = tmp_path / "formal-config.json"
    capture_directory = tmp_path / "capture"
    scratch_directory = tmp_path / "scratch"
    capture_directory.mkdir(exist_ok=True)
    scratch_directory.mkdir(exist_ok=True)
    identity = {
        "boot_id": boot_id,
        "invocation_id": invocation,
        "pid": 701,
        "proc_cgroup_raw": f"0::/system.slice/{unit}/supervisor\n",
        "starttime": 801,
        "unified_cgroup": f"/system.slice/{unit}/supervisor",
        "service_control_group": f"/system.slice/{unit}",
        "service_device": 11,
        "service_inode": 12,
        "supervisor_device": 11,
        "supervisor_inode": 13,
    }
    program = {
        "path": str(program_path),
        "sha256": _sha(program_path),
        "identity": {
            "device": program_info.st_dev,
            "inode": program_info.st_ino,
            "mode": stat.S_IMODE(program_info.st_mode),
        },
    }
    outer_receipt = {
        "schema": harness.FORMAL_ARMED_SCHEMA,
        "case_id": case_id,
        "variant": variant,
        "unit": unit,
        "process_identity": identity,
        "plan_path": str(tmp_path / "formal-plan.json"),
        "plan_sha256": "aa" * 32,
        "program": program,
        "final_config_path": str(config_path),
        "ready_fifo": {"path": str(tmp_path / "ready"), "device": "1", "inode": "2"},
        "release_fifo": {"path": str(tmp_path / "release"), "device": "1", "inode": "3"},
        "ready_sha256": hashlib.sha256(harness.READY_BYTES).hexdigest(),
        "release_sha256": hashlib.sha256(harness.RELEASE_BYTES).hexdigest(),
    }
    config = {key: None for key in harness._FORMAL_CONFIG_KEYS}
    config.update(
        {
            "schema": "scion.generic-backend-formal-case.v2",
            "case_id": case_id,
            "variant": variant,
            "receipt_directory": str(tmp_path),
            "receipt_name": "formal-final.json",
            "capture_directory": str(capture_directory),
            "scratch_directory": str(scratch_directory),
            "run_unit": unit,
            "case_script": str(program_path),
            "accepted_probe_sha256": "bb" * 32,
            "accepted_extension_sha256": "cc" * 32,
            "accepted_spawn_backend_sha256": "dd" * 32,
            "plan_sha256": outer_receipt["plan_sha256"],
            "systemd_armed_receipt_sha256": hashlib.sha256(
                _canonical(outer_receipt)
            ).hexdigest(),
        }
    )
    if config_updates is not None:
        config.update(config_updates)
    config["directory_authorities"] = harness._freeze_formal_directory_authorities(
        config
    )
    _write(config_path, config)
    config_sha256 = _sha(config_path)
    fixture_identity = {
        "config_sha256": config_sha256,
        "case_script": str(program_path),
        "case_script_sha256": _sha(program_path),
        "python_executable": "/usr/bin/python3.12",
        "python_version": [3, 12, 11],
        "isolated": 1,
        "dont_write_bytecode": 1,
        "native_extension": "/sealed/_spawn_into_cgroup.so",
        "native_extension_sha256": config["accepted_extension_sha256"],
        "spawn_backend": "/sealed/spawn_backend.py",
        "spawn_backend_sha256": config["accepted_spawn_backend_sha256"],
        "accepted_probe": "/sealed/probe.py",
        "accepted_probe_sha256": config["accepted_probe_sha256"],
    }
    outer = {
        "receipt": outer_receipt,
        "unit": unit,
        "identity": identity,
        "boot_id": boot_id,
        "invocation_id": invocation,
    }
    return outer, config, fixture_identity, tmp_path / "formal-final.json"


def test_formal_config_directory_authorities_are_exact_live_and_prestart_bound(
    tmp_path: Path,
) -> None:
    policy = harness._SCENARIO_POLICIES["B1/clean"]
    outer, config, _fixture_identity, _final_path = _formal_outer_config(
        tmp_path, case_id="B1", variant="clean"
    )
    expected = json.loads(json.dumps(config["directory_authorities"]))
    bound = harness._formal_config_binding(
        policy, outer, expected_directory_authorities=expected
    )
    assert bound[1]["directory_authorities"] == expected
    config_path = Path(outer["receipt"]["final_config_path"])

    mutations: list[dict[str, Any]] = []
    extra = json.loads(json.dumps(config))
    extra["directory_authorities"]["extra"] = dict(
        extra["directory_authorities"]["receipt_directory"]
    )
    mutations.append(extra)
    missing = json.loads(json.dumps(config))
    del missing["directory_authorities"]["scratch_directory"]
    mutations.append(missing)
    wrong_path = json.loads(json.dumps(config))
    wrong_path["directory_authorities"]["capture_directory"]["path"] = str(tmp_path)
    mutations.append(wrong_path)
    for field in ("device", "inode", "mode", "uid", "gid"):
        changed = json.loads(json.dumps(config))
        changed["directory_authorities"]["scratch_directory"][field] += 1
        mutations.append(changed)
    for mutation in mutations:
        _write(config_path, mutation)
        with pytest.raises(harness.HarnessError):
            harness._formal_config_binding(
                policy, outer, expected_directory_authorities=expected
            )
    _write(config_path, config)
    wrong_prestart = json.loads(json.dumps(expected))
    wrong_prestart["receipt_directory"]["inode"] += 1
    with pytest.raises(harness.HarnessError, match="pre-StartUnit"):
        harness._formal_config_binding(
            policy, outer, expected_directory_authorities=wrong_prestart
        )
    capture = Path(config["capture_directory"])
    original_mode = stat.S_IMODE(capture.lstat().st_mode)
    try:
        capture.chmod(original_mode ^ 0o020)
        with pytest.raises(harness.HarnessError, match="identity/mode/ownership"):
            harness._formal_config_binding(
                policy, outer, expected_directory_authorities=expected
            )
    finally:
        capture.chmod(original_mode)


@pytest.mark.parametrize(
    "mutation", [None, "outcome", "case", "requirement", "unknown", "action"]
)
def test_formal_requirement_final_is_exact_and_never_waits_for_b6_action(
    tmp_path: Path, mutation: str | None
) -> None:
    variant = "storage-blocked"
    policy = harness._SCENARIO_POLICIES[f"B6/{variant}"]
    outer, _config, fixture_identity, final_path = _formal_outer_config(
        tmp_path, case_id="B6", variant=variant
    )
    receipt = {
        "schema": harness.FORMAL_RECEIPT_SCHEMA,
        "case_id": "B6",
        "variant": variant,
        "fixture_identity": fixture_identity,
        "outcome": "REQUIREMENT_MISSING",
        "config_sha256": fixture_identity["config_sha256"],
        "requirement_code": "B6_EXACT_GUARDED_SEAM",
        "requirement": "accepted source exposes no exact guarded seam",
    }
    actions: list[dict[str, Any]] = []
    if mutation == "outcome":
        receipt["outcome"] = "PASS"
    elif mutation == "case":
        receipt["variant"] = "storage-just-released"
    elif mutation == "requirement":
        receipt["requirement_code"] = "OTHER"
    elif mutation == "unknown":
        receipt["extra"] = True
    elif mutation == "action":
        actions.append({"unexpected": True})
    _write(final_path, receipt)
    if mutation is None:
        evidence = harness._formal_final(policy, outer, actions)
        assert evidence["outcome"] == "REQUIREMENT_MISSING"
        assert evidence["case_evidence"]["declared_expected_fact_type"] == (
            "ContainedSpawnFailure"
        )
        assert policy.formal_actions == ()
    else:
        with pytest.raises(harness.HarnessError):
            harness._formal_final(policy, outer, actions)


@pytest.mark.parametrize(
    "variant",
    (
        "close-blocked",
        "close-empty-before-eof",
        "close-just-released",
        "close-leader-terminal",
        "close-reaped-populated",
    ),
)
def test_b6_close_rows_keep_declared_failstop_abi_but_requirement_missing_completion(
    tmp_path: Path, variant: str
) -> None:
    policy = harness._SCENARIO_POLICIES[f"B6/{variant}"]
    assert policy.formal_expected_fact_type == "FAILSTOP"
    assert policy.formal_completion == "requirement-missing"
    assert policy.formal_actions == ()
    assert "formal-final" in policy.required_outputs
    assert "formal-failstop" not in policy.required_outputs

    outer, _config, fixture_identity, final_path = _formal_outer_config(
        tmp_path, case_id="B6", variant=variant
    )
    _write(
        final_path,
        {
            "schema": harness.FORMAL_RECEIPT_SCHEMA,
            "case_id": "B6",
            "variant": variant,
            "fixture_identity": fixture_identity,
            "outcome": "REQUIREMENT_MISSING",
            "config_sha256": fixture_identity["config_sha256"],
            "requirement_code": "B6_EXACT_GUARDED_SEAM",
            "requirement": "accepted source exposes no exact guarded seam",
        },
    )
    evidence = harness._formal_final(policy, outer, [])
    assert evidence["case_evidence"] == {
        "kind": "REQUIREMENT_MISSING",
        "requirement_code": "B6_EXACT_GUARDED_SEAM",
        "declared_expected_fact_type": "FAILSTOP",
    }


@pytest.mark.parametrize(
    "mutation", [None, "operation-sha", "armed-sha", "outcome", "fact", "ledger-key"]
)
def test_formal_b6_final_cross_binds_typed_fact_and_operation_sha(
    tmp_path: Path, mutation: str | None
) -> None:
    variant = "storage-just-released"
    policy = harness._SCENARIO_POLICIES[f"B6/{variant}"]
    outer, _config, fixture_identity, final_path = _formal_outer_config(
        tmp_path, case_id="B6", variant=variant
    )
    action, armed, operation_payload, before = _b6_operation_vector(
        tmp_path, "capture-write"
    )
    _write(action.operation_receipt_path, operation_payload)
    operation = harness._b6_operation(action, policy, armed)
    action_ledger = {
        "schema": "scion.generic_backend.b6_action.v1",
        "armed_receipt_sha256": operation["armed_receipt_sha256"],
    }
    ledger = {
        "armed_receipt_sha256": operation["armed_receipt_sha256"],
        "operation_receipt_sha256": hashlib.sha256(_canonical(operation)).hexdigest(),
        "injection_count": 1,
        "operation_call_count": 1,
        "operation_ordinal": 1,
        "before": before,
        "after_release": {
            "release_sha256": operation["release_permit_sha256"]
        },
    }
    case_result = {
        "failure": {
            "fact_type": "ContainedSpawnFailure",
            "fields": {
                "phase": "RELEASED_DRAINING",
                "reason": "CAPTURE_FAILED",
            },
        },
        "fault_ledger": ledger,
        "observed_pipe_size": 65536,
        "emitted_each_stream": 69633,
    }
    receipt = {
        "schema": harness.FORMAL_RECEIPT_SCHEMA,
        "case_id": "B6",
        "variant": variant,
        "fixture_identity": fixture_identity,
        "outcome": "PASS",
        "baseline_inventory": {},
        "backend_open_inventory": {},
        "after_inventory": {},
        "final_inventory_proof": {},
        "case_result": case_result,
    }
    if mutation == "operation-sha":
        ledger["operation_receipt_sha256"] = "00" * 32
    elif mutation == "armed-sha":
        ledger["armed_receipt_sha256"] = "00" * 32
    elif mutation == "outcome":
        receipt["outcome"] = "REQUIREMENT_MISSING"
    elif mutation == "fact":
        case_result["failure"]["fields"]["reason"] = "OTHER"
    elif mutation == "ledger-key":
        ledger["extra"] = True
    _write(final_path, receipt)
    actions = [{"action": action_ledger, "operation": operation}]
    if mutation is None:
        evidence = harness._formal_final(policy, outer, actions)
        assert evidence["case_evidence"]["operation_receipt_sha256"] == (
            ledger["operation_receipt_sha256"]
        )
    else:
        with pytest.raises(harness.HarnessError):
            harness._formal_final(policy, outer, actions)


@pytest.mark.parametrize(
    "mutation",
    [None, "receipt-sha", "hold-fifo", "environment", "descendant", "forged-pid"],
)
def test_formal_b5_final_cross_binds_descendant_and_process_spec(
    tmp_path: Path, mutation: str | None
) -> None:
    variant = "setsid-retain-stdio"
    policy = harness._SCENARIO_POLICIES[f"B5/{variant}"]
    plan_path = tmp_path / "descendant-plan.json"
    request_path = tmp_path / "descendant-request.json"
    descendant_receipt_path = tmp_path / "descendant-receipt.json"
    adversary_path = FIXTURES / "generic_backend_adversary.py"
    adversary_info = adversary_path.lstat()
    program = {
        "path": str(adversary_path),
        "sha256": _sha(adversary_path),
        "identity": {
            "device": adversary_info.st_dev,
            "inode": adversary_info.st_ino,
            "mode": stat.S_IMODE(adversary_info.st_mode),
        },
    }
    _write(plan_path, {"schema": "scion.test.descendant-plan.v1"})
    _write(request_path, {"schema": "scion.test.descendant-request.v1"})
    _write(descendant_receipt_path, {"schema": "scion.test.descendant-receipt.v1"})
    hold_fifo = {"path": str(tmp_path / "hold"), "device": "7", "inode": "8"}
    outer, _config, fixture_identity, final_path = _formal_outer_config(
        tmp_path,
        case_id="B5",
        variant=variant,
        config_updates={
            "control_fifo": hold_fifo,
            "descendant_adversary_plan": {
                "path": str(plan_path),
                "sha256": _sha(plan_path),
            },
            "adversary_script": str(adversary_path),
            "adversary_sha256": _sha(adversary_path),
        },
    )
    job_name = "job-7-aaaaaaaaaaaaaaaa"
    job_cgroup = outer["identity"]["service_control_group"] + "/" + job_name

    def actor(pid: int, starttime: int) -> dict[str, Any]:
        return {
            "boot_id": outer["boot_id"],
            "invocation_id": outer["invocation_id"],
            "pid": pid,
            "proc_cgroup_raw": f"0::{job_cgroup}\n",
            "session_id": pid,
            "starttime": starttime,
            "stop_selector_environment": {},
            "unified_cgroup": job_cgroup,
        }

    environment = [
        _encoded_bytes(b"INVOCATION_ID=" + outer["invocation_id"].encode("ascii")),
        _encoded_bytes(b"LC_ALL=C"),
    ]
    process_spec = {"environment": environment, "spec_sha256": "ef" * 32}
    binding = {
        "plan_path": str(plan_path),
        "plan_sha256": _sha(plan_path),
        "request_path": str(request_path),
        "request_sha256": _sha(request_path),
        "receipt_path": str(descendant_receipt_path),
        "receipt_sha256": _sha(descendant_receipt_path),
        "actor": actor(901, 1001),
        "descendant": actor(902, 1002),
        "hold_release_fifo": hold_fifo,
        "expected_job_name": job_name,
        "expected_job_cgroup": job_cgroup,
        "process_spec": process_spec,
        "process_spec_sha256": process_spec["spec_sha256"],
    }
    case_result = {
        "failure": {
            "fact_type": "ContainedSpawnFailure",
            "fields": {"reason": "DESCENDANT_SURVIVED"},
        },
        "descendant_binding": binding,
        "transported_environment": environment,
    }
    receipt = {
        "schema": harness.FORMAL_RECEIPT_SCHEMA,
        "case_id": "B5",
        "variant": variant,
        "fixture_identity": fixture_identity,
        "outcome": "PASS",
        "baseline_inventory": {},
        "backend_open_inventory": {},
        "after_inventory": {},
        "final_inventory_proof": {},
        "case_result": case_result,
    }
    if mutation == "receipt-sha":
        binding["receipt_sha256"] = "00" * 32
    elif mutation == "hold-fifo":
        binding["hold_release_fifo"] = {**hold_fifo, "inode": "9"}
    elif mutation == "environment":
        case_result["transported_environment"] = [_encoded_bytes(b"LC_ALL=C")]
    elif mutation == "descendant":
        binding["descendant"]["pid"] = binding["actor"]["pid"]
        binding["descendant"]["starttime"] = binding["actor"]["starttime"]
    elif mutation == "forged-pid":
        binding["descendant"].update(
            {"pid": 999999, "starttime": 888888, "session_id": 777777}
        )
    _write(final_path, receipt)
    external = {
        "plan_path": binding["plan_path"],
        "plan_sha256": _sha(plan_path),
        "request_path": binding["request_path"],
        "request_sha256": _sha(request_path),
        "receipt_path": binding["receipt_path"],
        "receipt_sha256": _sha(descendant_receipt_path),
        "program": program,
        "hold_release_fifo": hold_fifo,
        "expected_job_name": job_name,
        "expected_job_cgroup": job_cgroup,
        "actor": actor(901, 1001),
        "descendant": actor(902, 1002),
        "live_descendant": {
            "pid": 902,
            "starttime": 1002,
            "session_id": 902,
            "proc_cgroup_raw": f"0::{job_cgroup}\n",
            "unified_cgroup": job_cgroup,
        },
    }
    actions = [
        {
            "schema": "scion.generic_backend.b5_action.v1",
            "action_id": "b5-never-release-hold",
            "case_id": "B5",
            "variant": variant,
            "control_writer_open_count": "0",
            "permit_write_count": "0",
            "ownership": "production-kill-and-drain-only",
            "descendant_evidence": external,
        }
    ]
    if mutation is None:
        evidence = harness._formal_final(policy, outer, actions)
        assert evidence["case_evidence"]["expected_job_cgroup"] == job_cgroup
        assert evidence["case_evidence"]["action_ledger_sha256"] == hashlib.sha256(
            _canonical(actions[0])
        ).hexdigest()
    else:
        with pytest.raises(harness.HarnessError):
            harness._formal_final(policy, outer, actions)


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("plan-decoy", "B5 descendant plan.*unique exact"),
        ("program-inode", "B5 descendant program.*drifted"),
    ),
)
def test_b5_descendant_static_assets_reject_decoy_or_inode_drift_prestart(
    tmp_path: Path, mutation: str, message: str
) -> None:
    run = "scion-w3-b5-static-authority.service"
    hold_path = tmp_path / "b5-static-hold.fifo"
    os.mkfifo(hold_path, 0o600)
    hold_info = hold_path.lstat()
    hold_fifo = {
        "path": str(hold_path),
        "device": str(hold_info.st_dev),
        "inode": str(hold_info.st_ino),
    }
    program_path = tmp_path / "b5-static-program.py"
    program_path.write_bytes(
        (FIXTURES / "generic_backend_adversary.py").read_bytes()
    )
    os.chmod(program_path, 0o444)
    plan_path = tmp_path / "b5-static-plan.json"
    _write(
        plan_path,
        {
            "schema": "scion.generic_backend.systemd_adversary_plan.v1",
            "scenario": "h6-setsid-descendant",
            "unit": run,
            "expected_job_name": "job-7-aaaaaaaaaaaaaaaa",
            "program_path": str(program_path),
            "program_sha256": _sha(program_path),
            "request_path": str(tmp_path / "b5-static-request.json"),
            "receipt_path": str(tmp_path / "b5-static-receipt.json"),
            "acquisition": None,
            "hold_release_fifo": hold_fifo,
        },
    )
    os.chmod(plan_path, 0o444)
    assets = {
        "b5-static-plan": {
            "role": "b5-static-plan",
            "kind": "json-plan",
            **_frozen_asset(plan_path),
        },
        "b5-static-program": {
            "role": "b5-static-program",
            "kind": "python-program",
            **_frozen_asset(program_path),
        },
    }
    formal_reference_path = plan_path
    if mutation == "plan-decoy":
        formal_reference_path = tmp_path / "b5-static-plan-decoy.json"
        formal_reference_path.write_bytes(plan_path.read_bytes())
        os.chmod(formal_reference_path, 0o444)
    else:
        replacement = tmp_path / "b5-static-program-replacement.py"
        replacement.write_bytes(program_path.read_bytes())
        os.chmod(replacement, 0o444)
        os.replace(replacement, program_path)
    action = harness.FormalAction(
        "b5-never-release-hold",
        None,
        None,
        tmp_path / "b5-static-action.json",
        harness.FifoIdentity(
            hold_path, hold_info.st_dev, hold_info.st_ino
        ),
    )
    with pytest.raises(harness.HarnessError, match=message):
        harness._freeze_b5_descendant_authority(
            {
                "descendant_adversary_plan": {
                    "path": str(formal_reference_path),
                    "sha256": _sha(formal_reference_path),
                }
            },
            action=action,
            run_unit=run,
            variant="setsid-retain-stdio",
            assets=assets,
            retained_assets={},
            require_root=False,
        )


@pytest.mark.parametrize("forged_pid", (False, True))
def test_b5_external_action_freezes_live_descendant_without_opening_hold_writer(
    tmp_path: Path, forged_pid: bool
) -> None:
    variant = "setsid-retain-stdio"
    run = "scion-w3-b5-live-descendant.service"
    invocation = "4d" * 16
    boot_id = "12345678-1234-1234-1234-123456789abc"
    job_name = "job-7-aaaaaaaaaaaaaaaa"
    service_group = f"/system.slice/{run}"
    job_cgroup = f"{service_group}/{job_name}"
    hold_path = tmp_path / "hold.fifo"
    os.mkfifo(hold_path, 0o600)
    hold_info = hold_path.lstat()
    hold_fifo = {
        "path": str(hold_path),
        "device": str(hold_info.st_dev),
        "inode": str(hold_info.st_ino),
    }
    program_path = tmp_path / "generic_backend_adversary.py"
    program_path.write_bytes(
        (FIXTURES / "generic_backend_adversary.py").read_bytes()
    )
    os.chmod(program_path, 0o444)
    program_info = program_path.lstat()
    program = {
        "path": str(program_path),
        "sha256": _sha(program_path),
        "identity": {
            "device": program_info.st_dev,
            "inode": program_info.st_ino,
            "mode": stat.S_IMODE(program_info.st_mode),
        },
    }
    plan_path = tmp_path / "descendant-plan.json"
    request_path = tmp_path / "descendant-request.json"
    receipt_path = tmp_path / "descendant-receipt.json"
    plan = {
        "schema": "scion.generic_backend.systemd_adversary_plan.v1",
        "scenario": "h6-setsid-descendant",
        "unit": run,
        "expected_job_name": job_name,
        "program_path": str(program_path),
        "program_sha256": _sha(program_path),
        "request_path": str(request_path),
        "receipt_path": str(receipt_path),
        "acquisition": None,
        "hold_release_fifo": hold_fifo,
    }
    _write(plan_path, plan)
    os.chmod(plan_path, 0o444)
    action = harness.FormalAction(
        "b5-never-release-hold",
        None,
        None,
        tmp_path / "b5-action.json",
        harness.FifoIdentity(
            hold_path, hold_info.st_dev, hold_info.st_ino
        ),
    )
    formal_plan = {
        "descendant_adversary_plan": {
            "path": str(plan_path),
            "sha256": _sha(plan_path),
        }
    }
    assets = {
        "b5-descendant-plan": {
            "role": "b5-descendant-plan",
            "kind": "json-plan",
            **_frozen_asset(plan_path),
        },
        "b5-descendant-program": {
            "role": "b5-descendant-program",
            "kind": "python-program",
            **_frozen_asset(program_path),
        },
    }
    authority = harness._freeze_b5_descendant_authority(
        formal_plan,
        action=action,
        run_unit=run,
        variant=variant,
        assets=assets,
        retained_assets={},
        require_root=False,
    )
    watch = harness.CreationWatch(receipt_path)
    pinned = harness.PinnedFormalAction.open(action)
    ready_read, ready_write = os.pipe2(os.O_CLOEXEC)
    release_read, release_write = os.pipe2(os.O_CLOEXEC)
    child_pid = os.fork()
    if child_pid == 0:
        try:
            os.close(ready_read)
            os.close(release_write)
            os.setsid()
            os.write(ready_write, b"R")
            os.close(ready_write)
            if os.read(release_read, 1) != b"X":
                os._exit(125)
            os.close(release_read)
            os._exit(0)
        except BaseException:
            os._exit(126)
    os.close(ready_write)
    os.close(release_read)
    try:
        assert os.read(ready_read, 1) == b"R"
        os.close(ready_read)
        child_starttime = harness._read_proc_starttime(child_pid)
        actor_starttime = harness._read_proc_starttime(os.getpid())
        assert child_starttime is not None and actor_starttime is not None

        def identity(pid: int, starttime: int, session_id: int) -> dict[str, Any]:
            return {
                "boot_id": boot_id,
                "invocation_id": invocation,
                "pid": pid,
                "proc_cgroup_raw": f"0::{job_cgroup}\n",
                "session_id": session_id,
                "starttime": starttime,
                "stop_selector_environment": {},
                "unified_cgroup": job_cgroup,
            }

        request = {
            "schema": "scion.generic_backend.systemd_adversary_request.v1",
            "scenario": plan["scenario"],
            "unit": run,
            "expected_invocation_id": invocation,
            "expected_job_name": job_name,
            "expected_job_cgroup": job_cgroup,
            "receipt_path": str(receipt_path),
            "hold_release_fifo": hold_fifo,
        }
        _write(request_path, request)
        request_sha256 = _sha(request_path)
        actor = identity(os.getpid(), actor_starttime, os.getsid(0))
        descendant = identity(child_pid, child_starttime, os.getsid(child_pid))
        if forged_pid:
            descendant.update(
                {"pid": 999999, "starttime": 888888, "session_id": 777777}
            )
        receipt = {
            "schema": "scion.generic_backend.systemd_adversary_receipt.v1",
            "scenario": plan["scenario"],
            "unit": run,
            "actor": actor,
            "expected_invocation_id": invocation,
            "expected_job_name": job_name,
            "expected_job_cgroup": job_cgroup,
            "hold_release_fifo": hold_fifo,
            "release_handshake": {
                "device": hold_info.st_dev,
                "inode": hold_info.st_ino,
                "path": str(hold_path),
                "permit_sha256": hashlib.sha256(harness.RELEASE_BYTES).hexdigest(),
            },
            "request_path": str(request_path),
            "request_sha256": request_sha256,
            "descendant": descendant,
            "formal_plan_binding": {
                "schema": plan["schema"],
                "scenario": plan["scenario"],
                "unit": run,
                "expected_job_name": job_name,
                "plan_path": str(plan_path),
                "plan_sha256": _sha(plan_path),
                "program": program,
                "acquisition": None,
                "hold_release_fifo": hold_fifo,
                "materialized_request_sha256": request_sha256,
            },
        }
        _write(receipt_path, receipt)
        manifest = harness.HarnessManifest(
            f"B5/{variant}",
            SimpleNamespace(),
            SimpleNamespace(),
            SimpleNamespace(),
            run,
            None,
            SimpleNamespace(),
            tmp_path,
            tmp_path,
            (),
            (action,),
            (harness.OutputPath("formal-action", action.action_ledger_path),),
            None,
        )
        formal = harness.FormalSystemHarness(
            manifest,
            object(),
            object(),
            require_root=False,
            proc_cgroup_reader=lambda pid: (
                f"0::{job_cgroup}\n",
                job_cgroup,
            ),
        )
        outer = {
            "boot_id": boot_id,
            "invocation_id": invocation,
            "identity": {"service_control_group": service_group},
        }
        if forged_pid:
            with pytest.raises(
                harness.HarnessError, match="descendant.*external proof"
            ):
                formal._b5_action(pinned, outer, watch, authority)
            assert not action.action_ledger_path.exists()
        else:
            ledger = formal._b5_action(pinned, outer, watch, authority)
            assert ledger["control_writer_open_count"] == "0"
            assert ledger["permit_write_count"] == "0"
            assert ledger["descendant_evidence"]["live_descendant"]["pid"] == child_pid
            assert json.loads(action.action_ledger_path.read_text(encoding="ascii")) == ledger
    finally:
        watch.close()
        pinned.close()
        os.write(release_write, b"X")
        os.close(release_write)
        _, status = os.waitpid(child_pid, 0)
        assert os.waitstatus_to_exitcode(status) == 0


@pytest.mark.parametrize(
    "variant",
    (
        "close-blocked",
        "close-empty-before-eof",
        "close-just-released",
        "close-leader-terminal",
        "close-reaped-populated",
    ),
)
def test_b6_close_producer_row_executes_exact_requirement_missing_classifier(
    variant: str,
) -> None:
    abi = formal_case._B6_ABI[variant]
    assert abi["expected_fact_type"] == "FAILSTOP"
    assert abi["hook"] == "unobservable-source-seam"
    controller = formal_case._B6FaultController(
        {"b6": {**abi, "acquisition": {}}}, {}, None
    )
    with pytest.raises(formal_case.RequirementMissing) as error:
        controller.install(ModuleType("accepted_spawn_backend"))
    assert error.value.code == "B6_EXACT_GUARDED_SEAM"
    assert controller._patches == []


@pytest.mark.parametrize(
    "variant",
    (
        "cgroup-inode-drift",
        "unexpected-sibling",
        "unexpected-nested",
        "supervisor-extra-task",
    ),
)
def test_b7_external_action_executes_real_dirfd_topology_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    variant: str,
) -> None:
    run = f"scion-w3-b7-{variant}.service"
    service_path = tmp_path / "service"
    job_name = "job-7-aaaaaaaaaaaaaaaa"
    job_path = service_path / job_name
    supervisor_path = service_path / "supervisor"
    job_path.mkdir(parents=True)
    supervisor_path.mkdir()
    (supervisor_path / "cgroup.procs").write_bytes(b"")
    service_fd = os.open(
        service_path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
    )
    supervisor_fd = os.open(
        supervisor_path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
    )
    service_info = os.fstat(service_fd)
    supervisor_info = os.fstat(supervisor_fd)
    job_info = job_path.lstat()
    ledger_path = tmp_path / "b7-action.json"
    permit_path = tmp_path / "b7-permit"
    permit_path.write_bytes(b"")
    action = harness.FormalAction(
        f"b7-{variant}", None, None, ledger_path, None
    )

    def open_control_writer() -> int:
        return os.open(permit_path, os.O_WRONLY | os.O_TRUNC | os.O_CLOEXEC)

    pinned = SimpleNamespace(action=action, open_control_writer=open_control_writer)
    child_pid = os.getpid()
    child_starttime = harness._read_proc_starttime(child_pid)
    ready_read = ready_write = release_read = release_write = -1
    if variant == "supervisor-extra-task":
        ready_read, ready_write = os.pipe2(os.O_CLOEXEC)
        release_read, release_write = os.pipe2(os.O_CLOEXEC)
        child_pid = os.fork()
        if child_pid == 0:
            try:
                os.close(ready_read)
                os.close(release_write)
                os.write(ready_write, b"R")
                os.close(ready_write)
                if os.read(release_read, 1) != b"X":
                    os._exit(125)
                os.close(release_read)
                os._exit(0)
            except BaseException:
                os._exit(126)
        os.close(ready_write)
        ready_write = -1
        os.close(release_read)
        release_read = -1
        assert os.read(ready_read, 1) == b"R"
        os.close(ready_read)
        ready_read = -1
        child_starttime = harness._read_proc_starttime(child_pid)
    assert child_starttime is not None
    process = SimpleNamespace(
        pid=child_pid, proc_starttime_ticks=child_starttime
    )
    cgroup = SimpleNamespace(
        job_name=job_name,
        job_device=job_info.st_dev,
        job_inode=job_info.st_ino,
    )
    armed_receipt = {"schema": "scion.test.b7-armed.v1", "variant": variant}
    monkeypatch.setattr(
        harness,
        "_formal_action_armed",
        lambda *_args, **_kwargs: {
            "receipt": armed_receipt,
            "process": process,
            "cgroup": cgroup,
        },
    )
    monkeypatch.setattr(
        harness,
        "_recursive_cgroup_inventory",
        lambda descriptor: {"children": sorted(os.listdir(descriptor))},
    )
    manifest = harness.HarnessManifest(
        f"B7/{variant}",
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        run,
        None,
        SimpleNamespace(),
        tmp_path,
        tmp_path,
        (),
        (action,),
        (harness.OutputPath("formal-action", ledger_path),),
        None,
    )
    formal = harness.FormalSystemHarness(
        manifest, object(), object(), require_root=False
    )
    formal._cgroup_pins[run] = harness.CgroupPin(
        run,
        "ab" * 16,
        f"/system.slice/{run}",
        service_fd,
        {"device": str(service_info.st_dev), "inode": str(service_info.st_ino)},
        supervisor_fd,
        {
            "device": str(supervisor_info.st_dev),
            "inode": str(supervisor_info.st_ino),
        },
    )
    try:
        ledger = formal._b7_action(pinned, {"unit": run})
        assert ledger["mutation"]["kind"] == variant
        assert permit_path.read_bytes() == b"DRIFT_APPLIED\n"
        assert json.loads(ledger_path.read_text(encoding="ascii")) == ledger
        if variant == "cgroup-inode-drift":
            replacement = service_path / f".scion-drift-{job_name}"
            assert replacement.is_dir()
            assert job_path.is_dir()
            assert replacement.stat().st_ino == job_info.st_ino
            assert job_path.stat().st_ino != job_info.st_ino
        elif variant == "unexpected-sibling":
            assert (service_path / ".scion-unexpected-sibling").is_dir()
        elif variant == "unexpected-nested":
            assert (job_path / ".scion-unexpected-nested").is_dir()
        else:
            assert (supervisor_path / "cgroup.procs").read_bytes() == (
                f"{child_pid}\n".encode("ascii")
            )
            assert formal.proc_starttime_reader(child_pid) == child_starttime
    finally:
        formal._cgroup_pins.pop(run).close()
        if release_write >= 0:
            os.write(release_write, b"X")
            os.close(release_write)
            _, status = os.waitpid(child_pid, 0)
            assert os.waitstatus_to_exitcode(status) == 0


@pytest.mark.parametrize("publish_forbidden_final", [False, True])
def test_external_b7_failstop_requires_exact_formal_final_absence(
    tmp_path: Path, publish_forbidden_final: bool
) -> None:
    scenario = "B7/unexpected-sibling"
    policy = harness._SCENARIO_POLICIES[scenario]
    run = "scion-w3-b7-failstop.service"
    closer = "scion-w3-b7-failstop-close.service"
    descriptor, install, program, boot, input_root, receipts = _common_authorities(
        tmp_path, run
    )
    outputs = tuple(
        harness.OutputPath(role, receipts / f"{role}.json")
        for role in sorted(policy.required_outputs)
    )
    output_by_role = {item.role: item.path for item in outputs}
    action = harness.FormalAction(
        "b7-unexpected-sibling",
        tmp_path / "armed.json",
        None,
        output_by_role["formal-action"],
        None,
    )
    _write(action.action_ledger_path, {"schema": "scion.test.action.v1"})
    manifest = harness.HarnessManifest(
        scenario,
        descriptor,
        install,
        program,
        run,
        closer,
        harness.PinnedFile(boot, boot.lstat().st_dev, boot.lstat().st_ino),
        input_root,
        receipts,
        (),
        (action,),
        outputs,
        None,
    )
    config_path = tmp_path / "final-config.json"
    outer_receipt = {
        "unit": run,
        "plan_sha256": "aa" * 32,
        "final_config_path": str(config_path),
    }
    forbidden = tmp_path / "forbidden-final.json"
    capture_directory = tmp_path / "capture"
    scratch_directory = tmp_path / "scratch"
    capture_directory.mkdir()
    scratch_directory.mkdir()
    config = {key: None for key in harness._FORMAL_CONFIG_KEYS}
    config.update(
        {
            "schema": "scion.generic-backend-formal-case.v2",
            "case_id": "B7",
            "variant": "unexpected-sibling",
            "run_unit": run,
            "receipt_directory": str(tmp_path),
            "receipt_name": forbidden.name,
            "capture_directory": str(capture_directory),
            "scratch_directory": str(scratch_directory),
            "plan_sha256": outer_receipt["plan_sha256"],
            "systemd_armed_receipt_sha256": hashlib.sha256(
                _canonical(outer_receipt)
            ).hexdigest(),
        }
    )
    config["directory_authorities"] = harness._freeze_formal_directory_authorities(
        config
    )
    _write(config_path, config)
    if publish_forbidden_final:
        _write(forbidden, {"outcome": "PASS"})
    formal = harness.FormalSystemHarness(
        manifest, object(), object(), require_root=False
    )
    formal._installer_authority = {
        "formal_directory_authorities": config["directory_authorities"]
    }
    formal._formal_outer_armed = {
        "receipt": outer_receipt,
        "unit": run,
    }
    terminal = {
        run: {
            "normalization": {
                "handoff": {
                    "result": "core-dump",
                    "active_state": "failed",
                    "sub_state": "failed",
                    "exec_main_code": "3",
                    "exec_main_status": "6",
                    "exec_stop_post_code": "1",
                    "exec_stop_post_status": "0",
                }
            }
        }
    }
    if publish_forbidden_final:
        with pytest.raises(harness.HarnessError, match="incorrectly published"):
            formal._formal_failstop_evidence(terminal)
    else:
        evidence = formal._formal_failstop_evidence(terminal)
        assert evidence is not None
        assert evidence["formal_final_absent"] is True
        assert evidence["classification"] == (
            "formal-negative-evidence/B7_EXTERNAL_TOPOLOGY_FAILSTOP"
        )


@pytest.mark.parametrize("mutation", ["unknown-key", "wrong-role-unit", "bad-cgroup"])
def test_real_adversary_armed_shape_is_exact_and_role_bound(
    tmp_path: Path, mutation: str
) -> None:
    run = "scion-w3-h8-armed.service"
    closer = "scion-w3-h8-armed-close.service"
    lineage = "/system.slice/" + run + "/supervisor"
    identity = {
        "boot_id": "12345678-1234-1234-1234-123456789abc",
        "invocation_id": "44" * 16,
        "pid": 321,
        "starttime": 654,
        "unified_cgroup": lineage,
    }
    acquisition = _acquisition(
        tmp_path,
        "run-main",
        run,
        identity,
        adversary="h8-extra-topology-hold",
    )
    payload = _pending_armed(acquisition)
    plan_path = Path(payload["plan_path"])
    program_path = Path(payload["program"]["path"])
    _write(
        plan_path,
        {
            "schema": "scion.generic_backend.systemd_adversary_plan.v1",
            "scenario": payload["scenario"],
            "unit": run,
            "expected_job_name": None,
            "program_path": str(program_path),
            "program_sha256": _sha(program_path),
            "request_path": payload["request_path"],
            "receipt_path": payload["receipt_path"],
            "acquisition": {
                "armed_receipt_path": str(acquisition.armed_receipt_path),
                "ready_fifo": payload["ready_fifo"],
                "release_fifo": payload["release_fifo"],
            },
            "hold_release_fifo": None,
        },
    )
    os.chmod(plan_path, 0o444)
    payload["plan_sha256"] = _sha(plan_path)
    _PENDING_ARMED.pop(acquisition.armed_receipt_path)
    _write(acquisition.armed_receipt_path, payload)
    policy = harness._SCENARIO_POLICIES["H8"]
    static_authority = _direct_static_role_authority(
        acquisition,
        policy=policy,
        unit=run,
        plan_path=plan_path,
        program_path=program_path,
    )
    accepted = harness._armed_identity(
        acquisition.armed_receipt_path,
        acquisition,
        static_authority,
        run_unit=run,
        closer_unit=closer,
        policy=policy,
    )
    assert accepted["unit"] == run
    payload = json.loads(acquisition.armed_receipt_path.read_text())
    if mutation == "unknown-key":
        payload["unexpected"] = True
    elif mutation == "wrong-role-unit":
        payload["unit"] = closer
    else:
        payload["actor"]["unified_cgroup"] = "/system.slice//supervisor"
        payload["actor"]["proc_cgroup_raw"] = "0::/system.slice//supervisor\n"
    _write(acquisition.armed_receipt_path, payload)
    try:
        with pytest.raises(harness.HarnessError):
            harness._armed_identity(
                acquisition.armed_receipt_path,
                acquisition,
                static_authority,
                run_unit=run,
                closer_unit=closer,
                policy=policy,
            )
    finally:
        static_authority.plan_asset.close()
        static_authority.program_asset.close()


def test_h12_rejects_actor_with_same_pid_and_starttime() -> None:
    frozen = [
        {
            "role": "run-main",
            "unit": "scion-w3-h12.service",
            "schema": "scion.generic_backend.systemd_observer_armed.v1",
            "identity": {"pid": 123, "starttime": 456},
        }
    ]
    with pytest.raises(harness.HarnessError):
        harness._prove_actor_absence(frozen, lambda pid: 456)


def test_h12_accepts_pid_reuse_and_proc_enoent_without_truncation() -> None:
    frozen = [
        {
            "role": role,
            "unit": "scion-w3-h12.service",
            "schema": "scion.generic_backend.systemd_observer_armed.v1",
            "identity": {"pid": pid, "starttime": starttime},
        }
        for role, pid, starttime in (
            ("run-main", 123, 456),
            ("exec-stop-post", 124, 457),
        )
    ]
    records = harness._prove_actor_absence(
        frozen, lambda pid: 999 if pid == 123 else None
    )
    assert [record["absence_proof"] for record in records] == [
        "pid-reused-with-different-starttime",
        "proc-entry-absent",
    ]
    assert [record["role"] for record in records] == ["run-main", "exec-stop-post"]


@pytest.mark.parametrize(
    "field",
    [
        "LoadState",
        "ActiveState",
        "SubState",
        "Result",
        "ExecMainCode",
        "ExecMainStatus",
        "ExecStopPost",
    ],
)
def test_closer_terminal_policy_rejects_each_semantic_mutation(
    tmp_path: Path, field: str
) -> None:
    run = "scion-w3-terminal.service"
    closer = "scion-w3-terminal-close.service"
    manager = FakeManager(
        run,
        closer,
        (),
        {run: bytes.fromhex("11" * 16), closer: bytes.fromhex("22" * 16)},
        "H1",
    )
    receipt = harness.query_unit_properties(
        manager,
        unit=closer,
        peer_unit=run,
        boot_id="12345678-1234-1234-1234-123456789abc",
        receipt_path=tmp_path / "unused.json",
        publish=False,
    )
    interface = (
        harness.UNIT_INTERFACE
        if field in {"LoadState", "ActiveState", "SubState"}
        else harness.SERVICE_INTERFACE
    )
    encoded = harness._encoded_property(receipt, interface, field)
    if field == "ExecStopPost":
        encoded["items"] = [{"kind": "unexpected"}]
    elif field in {"ExecMainCode", "ExecMainStatus"}:
        encoded["value"] = "61" if field == "ExecMainStatus" else "2"
    else:
        encoded["value"] = {
            "LoadState": "not-found",
            "ActiveState": "failed",
            "SubState": "failed",
            "Result": "exit-code",
        }[field]
    with pytest.raises(harness.HarnessError):
        harness._closer_terminal_policy(
            receipt,
            expected_unit=closer,
            expected=harness._SCENARIO_POLICIES["H1"].terminal.closer,
        )


def test_h9_closer_terminal_accepts_only_failed_status_61(tmp_path: Path) -> None:
    run = "scion-w3-h9-terminal.service"
    closer = "scion-w3-h9-terminal-close.service"
    manager = FakeManager(
        run,
        closer,
        (),
        {run: bytes.fromhex("11" * 16), closer: bytes.fromhex("22" * 16)},
        "H1",
    )
    receipt = harness.query_unit_properties(
        manager,
        unit=closer,
        peer_unit=run,
        boot_id="12345678-1234-1234-1234-123456789abc",
        receipt_path=tmp_path / "unused.json",
        publish=False,
    )
    for interface, field, value in (
        (harness.UNIT_INTERFACE, "ActiveState", "failed"),
        (harness.UNIT_INTERFACE, "SubState", "failed"),
        (harness.SERVICE_INTERFACE, "Result", "exit-code"),
        (harness.SERVICE_INTERFACE, "ExecMainStatus", "61"),
    ):
        harness._encoded_property(receipt, interface, field)["value"] = value
    accepted = harness._closer_terminal_policy(
        receipt,
        expected_unit=closer,
        expected=harness._SCENARIO_POLICIES["H9"].terminal.closer,
    )
    assert accepted.semantic_tuple() == (
        "loaded",
        "failed",
        "failed",
        "exit-code",
        1,
        61,
    )


def test_four_typed_decoder_rejections_are_fail_closed() -> None:
    with pytest.raises(Exception):
        harness._normalize_configured_properties(unit="scion-w3-x.service", peer_unit=None, raw_values={"CollectMode": "inactive", "Restart": "no"})
    malformed = {"properties": [{"interface": harness.SERVICE_INTERFACE, "property": "ExecStopPost", "value": {"signature": "a(sasbttttuii)", "kind": "array", "items": []}}]}
    with pytest.raises(harness.HarnessError):
        harness._final_exec_stop_post(malformed)
    from scion.runtime.execution.systemd255 import (
        ConfiguredUnitProperties,
        InvocationLineage,
        StopPostEnvironment,
        StopPostTopology,
        UnitHandoffProperties,
        UnitRole,
    )
    with pytest.raises(Exception):
        ConfiguredUnitProperties.from_receipts(
            UnitRole.RUN, {}, {}, expected_unit="scion-w3-x.service", expected_peer="scion-w3-y.service"
        )
    with pytest.raises(Exception):
        InvocationLineage.from_properties({"BootID": "bad"})
    with pytest.raises(Exception):
        StopPostEnvironment.from_environment({"INVOCATION_ID": "bad"})
    with pytest.raises(Exception):
        StopPostTopology.from_mapping({"ServiceControlGroup": "/bad"})
    with pytest.raises(Exception):
        UnitHandoffProperties.from_properties({}, expected_unit="scion-w3-x.service")


def test_static_assets_and_sources_close_forbidden_operations() -> None:
    run = (FIXTURES / "generic-backend-run.service.in").read_text()
    close = (FIXTURES / "generic-backend-close.service.in").read_text()
    negative = (FIXTURES / "generic-backend-gc-negative.service.in").read_text()
    assert "ExecStart=/usr/bin/python3.12 -I -B @RUN_PROGRAM@ --plan @RUN_PLAN@" in run
    assert "ExecStopPost=/usr/bin/python3.12 -I -B @STOP_PROGRAM@ --plan @STOP_PLAN@" in run
    assert "CollectMode=inactive\n" in close
    assert "CollectMode=inactive-or-failed\n" in negative
    wrapper = (FIXTURES / "generic-backend-formal-wrapper.sh").read_text()
    for forbidden in ("freeze)", "mv -T", "mktemp", "trap", "rm -rf"):
        assert forbidden not in wrapper
    for name in ("generic_backend_systemd_harness.py", "generic_backend_root_installer.py"):
        source = (FIXTURES / name).read_text()
        tree = ast.parse(source)
        qualified = {(node.func.value.id, node.func.attr) for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)}
        assert not ({("subprocess", "Popen"), ("subprocess", "run"), ("os", "fork"), ("os", "kill"), ("os", "waitpid"), ("time", "sleep")} & qualified)
        assert "systemctl" not in source and "systemd-run" not in source


def test_no_replace_fsyncs_parent_after_file_is_frozen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "receipt.json"
    observed: list[Path] = []

    def observe_parent(path: Path) -> None:
        assert path == tmp_path
        assert destination.read_bytes() == _canonical({"state": "frozen"})
        assert stat.S_IMODE(destination.lstat().st_mode) == 0o444
        observed.append(path)

    monkeypatch.setattr(harness, "_fsync_directory", observe_parent)
    harness._write_no_replace(destination, {"state": "frozen"})
    assert observed == [tmp_path]


def test_b7_supervisor_extra_task_reuses_identity_pinned_blocked_child() -> None:
    source = (FIXTURES / "generic_backend_systemd_harness.py").read_text(
        encoding="ascii"
    )
    start = source.index('elif variant == "supervisor-extra-task":')
    end = source.index("\n            else:", start)
    branch = source[start:end]
    assert 'child_pid = armed["process"].pid' in branch
    assert 'child_starttime = armed["process"].proc_starttime_ticks' in branch
    assert branch.count("self.proc_starttime_reader(child_pid)") == 2
    assert 'f"{child_pid}\\n".encode("ascii")' in branch
    assert "os.fork" not in source


@pytest.mark.parametrize("member", ("UnitNew", "UnitRemoved"))
@pytest.mark.parametrize(
    ("unit", "object_path"),
    (
        ("scion-w3-extra.service", "/org/freedesktop/systemd1/unit/extra"),
        ("scion-w3-owned.service", "/org/freedesktop/systemd1/unit/wrong"),
    ),
)
def test_unit_signals_reject_every_extra_or_wrong_installer_object(
    member: str, unit: str, object_path: str
) -> None:
    manager = NoExternalCalls()
    runner = harness.FormalSystemHarness(None, manager, NoExternalCalls())
    runner._installer_authority = {
        "objects": {
            "scion-w3-owned.service": (
                "/org/freedesktop/systemd1/unit/scion_2dw3_2downed.service"
            )
        }
    }
    with pytest.raises(harness.HarnessError, match="exact installer object mapping"):
        runner._record_signal(
            harness.ManagerSignal(
                1,
                member,
                "so",
                (unit, object_path),
                harness.MANAGER_PATH,
                manager.owner,
            )
        )
    assert runner.signals == []

    transport = object.__new__(harness.DBusSystemManager)
    transport.owner = manager.owner
    transport._callback = lambda _signal: None
    transport._allowed_unit_objects = dict(runner._installer_authority["objects"])
    transport._ordinal = 0
    transport._loop = None
    transport._predicate = None
    with pytest.raises(harness.HarnessError, match="installer unit/object authority"):
        transport._emit(
            member,
            (unit, object_path),
            harness.MANAGER_PATH,
            manager.owner,
        )
    assert transport._ordinal == 0
