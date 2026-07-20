from __future__ import annotations

import ast
import errno
import hashlib
import io
import importlib.util
import inspect
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
import textwrap
import threading
import tokenize
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


def _prepare_fifo_rows(
    root: Path,
    *ordinary: tuple[str, str],
) -> list[dict[str, str]]:
    rows = [
        {
            "role": "h11-permit-commit",
            "path": str(root / "fifo" / "h11-permit-committed.fifo"),
            "owner": "root",
        },
        {
            "role": "h11-ready-commit",
            "path": str(root / "fifo" / "h11-ready-committed.fifo"),
            "owner": "root",
        },
        *(
            {"role": role, "path": str(root / "fifo" / name), "owner": "fixture"}
            for role, name in ordinary
        ),
    ]
    return sorted(rows, key=lambda item: item["role"])


def _static_authority_chain(
    tmp_path: Path,
    *,
    fragment_mutation: str | None = None,
    ordinary_fifos: tuple[tuple[str, str], ...] = (("run-ready", "run-ready"),),
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
            "fifos": _prepare_fifo_rows(root, *ordinary_fifos),
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


def _run_static_preflight(
    chain: dict[str, Any],
    *,
    work_owner: str | None = None,
) -> subprocess.CompletedProcess[str]:
    tree = json.loads(chain["tree_receipt"].read_text(encoding="ascii"))
    fixture_owner = f"{tree['fixture_uid']}:{tree['fixture_gid']}"
    ownership_arguments = [
        work_owner or fixture_owner,
        str(chain["root"] / "work"),
        *(
            argument
            for item in tree["fifos"]
            for argument in (f"{item['uid']}:{item['gid']}", item["path"])
        ),
    ]
    result = subprocess.run(
        [
            "fakeroot",
            "sh",
            "-c",
            "while [ \"$1\" != -- ]; do chown \"$1\" \"$2\"; shift 2; done; "
            "shift; exec sh \"$1\" preflight \"$2\" \"$3\"",
            "fifo-preflight",
            *ownership_arguments,
            "--",
            str(FIXTURES / "generic-backend-formal-wrapper.sh"),
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


def _rewrite_tree_and_seal_bindings(
    chain: dict[str, Any],
    tree: dict[str, Any],
) -> None:
    tree_path = chain["tree_receipt"]
    tree_path.chmod(0o644)
    _write(tree_path, tree)
    tree_path.chmod(0o444)
    tree_binding = installer._asset_reference(tree_path)

    inventory_path = chain["inventory"]
    lines = inventory_path.read_text(encoding="ascii").splitlines(keepends=True)
    assert lines[5].startswith("tree_receipt\t")
    lines[5] = "tree_receipt\t" + "\t".join(
        tree_binding[key]
        for key in ("path", "sha256", "device", "inode", "mode")
    ) + "\n"
    inventory_path.chmod(0o644)
    inventory_path.write_text("".join(lines), encoding="ascii")
    inventory_path.chmod(0o444)
    inventory_binding = installer._asset_reference(inventory_path)

    seal_path = chain["seal_receipt"]
    seal = json.loads(seal_path.read_text(encoding="ascii"))
    seal["tree_receipt"] = installer._file_reference(tree_path)
    inventory_rows = [
        item
        for item in seal["files"]
        if item["role"] == "preflight-manifest"
    ]
    assert len(inventory_rows) == 1
    inventory_rows[0].update(inventory_binding)
    seal_path.chmod(0o644)
    _write(seal_path, seal)
    seal_path.chmod(0o444)


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
            "fifos": json.loads(
                chain["tree_receipt"].read_text(encoding="ascii")
            )["fifos"],
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
            "fifos": _prepare_fifo_rows(root, ("run-ready", fifo.name)),
            "receipt_path": str(tree_receipt),
        },
    )
    prepared = installer.prepare_tree(prepare, require_root=False)
    assert [item["role"] for item in prepared["fifos"]] == [
        "h11-permit-commit",
        "h11-ready-commit",
        "run-ready",
    ]
    assert prepared["fifos"][-1] == {
        "role": "run-ready",
        "path": str(fifo),
        "owner": "fixture",
        "uid": str(os.getuid()),
        "gid": str(os.getgid()),
        "mode": "0600",
        "device": str(fifo.lstat().st_dev),
        "inode": str(fifo.lstat().st_ino),
    }
    for role, name in (
        ("h11-permit-commit", "h11-permit-committed.fifo"),
        ("h11-ready-commit", "h11-ready-committed.fifo"),
    ):
        row = next(item for item in prepared["fifos"] if item["role"] == role)
        assert row["path"] == str(root / "fifo" / name)
        assert (row["owner"], row["uid"], row["gid"], row["mode"]) == (
            "root",
            "0",
            "0",
            "0600",
        )
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


@pytest.mark.parametrize(
    "mutation",
    (
        "missing-owner",
        "extra-key",
        "unknown-owner",
        "ordinary-root-owner",
        "reserved-fixture-owner",
        "reserved-path-drift",
        "missing-reserved-peer",
        "unsorted",
    ),
)
def test_prepare_tree_rejects_noncanonical_fifo_authority_before_root_creation(
    tmp_path: Path,
    mutation: str,
) -> None:
    user = pwd.getpwuid(os.getuid()).pw_name
    group = grp.getgrgid(os.getgid()).gr_name
    root = tmp_path / "formal"
    rows = _prepare_fifo_rows(root, ("run-ready", "run-ready"))
    if mutation == "missing-owner":
        rows[-1].pop("owner")
    elif mutation == "extra-key":
        rows[-1]["unexpected"] = "value"
    elif mutation == "unknown-owner":
        rows[-1]["owner"] = "operator"
    elif mutation == "ordinary-root-owner":
        rows[-1]["owner"] = "root"
    elif mutation == "reserved-fixture-owner":
        rows[0]["owner"] = "fixture"
    elif mutation == "reserved-path-drift":
        rows[0]["path"] = str(root / "fifo" / "wrong.fifo")
    elif mutation == "missing-reserved-peer":
        rows.pop(0)
    else:
        rows.reverse()
    manifest = tmp_path / "prepare-invalid.json"
    _write(
        manifest,
        {
            "schema": installer.PREPARE_SCHEMA,
            "formal_root": str(root),
            "fixture_user": user,
            "fixture_group": group,
            "fifos": rows,
            "receipt_path": str(root / "authority" / "tree.json"),
        },
    )
    with pytest.raises(installer.InstallerError):
        installer.prepare_tree(manifest, require_root=False)
    assert not root.exists()


def test_prepare_tree_rejects_root_as_fixture_identity(tmp_path: Path) -> None:
    root = tmp_path / "formal"
    manifest = tmp_path / "prepare-root-fixture.json"
    _write(
        manifest,
        {
            "schema": installer.PREPARE_SCHEMA,
            "formal_root": str(root),
            "fixture_user": pwd.getpwuid(0).pw_name,
            "fixture_group": grp.getgrgid(0).gr_name,
            "fifos": _prepare_fifo_rows(root, ("run-ready", "run-ready")),
            "receipt_path": str(root / "authority" / "tree.json"),
        },
    )
    with pytest.raises(installer.InstallerError, match="must not be root"):
        installer.prepare_tree(manifest, require_root=False)
    assert not root.exists()


@pytest.mark.parametrize(
    "mutation",
    ("owner", "uid", "gid", "mode", "device", "inode", "order"),
)
def test_tree_receipt_rejects_fifo_full_reference_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    chain = _static_authority_chain(tmp_path)
    receipt = json.loads(chain["tree_receipt"].read_text(encoding="ascii"))
    if mutation == "order":
        receipt["fifos"].reverse()
    else:
        row = receipt["fifos"][0]
        row[mutation] = {
            "owner": "fixture",
            "uid": str(os.getuid()),
            "gid": str(os.getgid()),
            "mode": "0644",
            "device": str(int(row["device"]) + 1),
            "inode": str(int(row["inode"]) + 1),
        }[mutation]
    with pytest.raises(installer.InstallerError):
        installer._validate_tree_receipt(
            receipt,
            root=chain["root"],
            receipt_path=chain["tree_receipt"],
            require_root=False,
            sealed=True,
        )


def test_tree_receipt_rejects_prepare_fifo_inventory_mismatch(
    tmp_path: Path,
) -> None:
    chain = _static_authority_chain(tmp_path)
    receipt = json.loads(chain["tree_receipt"].read_text(encoding="ascii"))
    prepare_path = Path(receipt["prepare_manifest"]["path"])
    prepare = json.loads(prepare_path.read_text(encoding="ascii"))
    prepare["fifos"][-1]["role"] = "renamed-ready"
    _write(prepare_path, prepare)
    receipt["prepare_manifest"] = installer._file_reference(prepare_path)
    with pytest.raises(installer.InstallerError, match="prepare manifest"):
        installer._validate_tree_receipt(
            receipt,
            root=chain["root"],
            receipt_path=chain["tree_receipt"],
            require_root=False,
            sealed=True,
        )


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
    tree = json.loads(chain["tree_receipt"].read_text(encoding="ascii"))
    assert preflight["fifos"] == tree["fifos"]
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


@pytest.mark.parametrize("mutation", ("mode", "inode", "missing"))
def test_wrapper_rejects_tree_bound_fifo_drift_before_preflight_receipt(
    tmp_path: Path,
    mutation: str,
) -> None:
    chain = _static_authority_chain(tmp_path)
    tree = json.loads(chain["tree_receipt"].read_text(encoding="ascii"))
    fifo = Path(tree["fifos"][0]["path"])
    if mutation == "mode":
        fifo.chmod(0o644)
    else:
        if mutation == "inode":
            replacement = fifo.with_name(f"{fifo.name}.replacement")
            os.mkfifo(replacement, 0o600)
            assert replacement.lstat().st_ino != fifo.lstat().st_ino
            fifo.unlink()
            replacement.rename(fifo)
        else:
            fifo.unlink()
    result = _run_static_preflight(chain)
    assert result.returncode != 0
    assert "FIFO" in result.stderr
    assert not chain["destination"].exists()
    assert not (chain["destination"] / "PREFLIGHT.json").exists()


def test_wrapper_rejects_root_fixture_fifo_forgery_with_rebound_tree_and_seal(
    tmp_path: Path,
) -> None:
    chain = _static_authority_chain(tmp_path)
    tree = json.loads(chain["tree_receipt"].read_text(encoding="ascii"))
    tree["fixture_uid"] = "0"
    tree["fixture_gid"] = "0"
    for row in tree["fifos"]:
        if row["owner"] == "fixture":
            row["uid"] = "0"
            row["gid"] = "0"
    _rewrite_tree_and_seal_bindings(chain, tree)

    result = _run_static_preflight(chain)

    assert result.returncode != 0
    assert "non-root authority" in result.stderr
    assert not chain["destination"].exists()
    assert not (chain["destination"] / "PREFLIGHT.json").exists()


def test_wrapper_rejects_work_owner_drift_before_preflight_receipt(
    tmp_path: Path,
) -> None:
    chain = _static_authority_chain(tmp_path)

    result = _run_static_preflight(chain, work_owner="0:0")

    assert result.returncode != 0
    assert "work root" in result.stderr
    assert not chain["destination"].exists()
    assert not (chain["destination"] / "PREFLIGHT.json").exists()


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


@pytest.mark.parametrize(
    "mutation",
    ("missing", "extra", "order", "owner", "uid", "gid", "mode", "device", "inode"),
)
def test_install_rejects_preflight_fifo_authority_drift_before_mutation(
    tmp_path: Path,
    mutation: str,
) -> None:
    chain = _static_authority_chain(tmp_path)
    preflight_path = _publish_test_preflight(chain)
    preflight = json.loads(preflight_path.read_text(encoding="ascii"))
    if mutation == "missing":
        preflight["fifos"].pop()
    elif mutation == "extra":
        extra = dict(preflight["fifos"][-1])
        extra["role"] = "unexpected-ready"
        preflight["fifos"].append(extra)
    elif mutation == "order":
        preflight["fifos"].reverse()
    else:
        row = preflight["fifos"][0]
        row[mutation] = {
            "owner": "fixture",
            "uid": str(os.getuid()),
            "gid": str(os.getgid()),
            "mode": "0644",
            "device": str(int(row["device"]) + 1),
            "inode": str(int(row["inode"]) + 1),
        }[mutation]
    preflight_path.chmod(0o644)
    _write(preflight_path, preflight)
    preflight_path.chmod(0o444)
    unit_directory = tmp_path / "units"
    unit_directory.mkdir()
    manifest, receipt_path = _install_plan(chain, tmp_path)
    manager = FakeInstallerManager(unit_directory)
    original_file = installer.__file__
    installer.__file__ = str(chain["paths"]["installer-program"])
    try:
        with pytest.raises(installer.InstallerError, match="FIFO authority"):
            installer.install_units(
                manifest,
                manager=manager,
                require_root=False,
                unit_directory=unit_directory,
            )
    finally:
        installer.__file__ = original_file
    assert manager.calls == []
    assert list(unit_directory.iterdir()) == []
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
            receipt_path=chain["tree_receipt"],
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


# H11 closed absence-authority manifest/prevalidation block.

def _h11_manifest_authority_model(
    tmp_path: Path,
) -> tuple[
    dict[str, Any],
    harness.ExecutionManifestSource,
    tuple[harness.OutputPath, ...],
    dict[str, Any],
]:
    root = tmp_path / "h11-formal"
    authority = root / "authority"
    harness_root = authority / "harness"
    scenario_root = harness_root / "H11"
    input_root = root / "input"
    receipt_root = scenario_root / "receipts"
    fifo_root = root / "fifo"
    for path, mode in (
        (root, 0o711),
        (authority, 0o700),
        (harness_root, 0o700),
        (scenario_root, 0o700),
        (input_root, 0o555),
        (receipt_root, 0o555),
        (fifo_root, 0o711),
    ):
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(mode)
    manifest_path = scenario_root / "MANIFEST.json"
    _write(
        manifest_path,
        {"schema": harness.MANIFEST_SCHEMA, "scenario": "H11"},
    )
    manifest_path.chmod(0o444)
    source, _raw = harness.ExecutionManifestSource.open_once(
        manifest_path, require_root=False
    )

    def directory_reference(role: str, path: Path) -> dict[str, str]:
        info = path.lstat()
        return {
            "role": role,
            "path": str(path),
            "device": str(info.st_dev),
            "inode": str(info.st_ino),
            "mode": format(stat.S_IMODE(info.st_mode), "04o"),
            "uid": str(info.st_uid),
            "gid": str(info.st_gid),
        }

    directory_chain = [
        directory_reference(role, path)
        for role, path in (
            ("formal-root", root),
            ("authority-root", authority),
            ("harness-root", harness_root),
            ("scenario-root", scenario_root),
            ("input-root", input_root),
            ("receipt-root", receipt_root),
            ("fifo-root", fifo_root),
        )
    ]

    def fifo_reference(name: str) -> dict[str, str]:
        path = fifo_root / name
        os.mkfifo(path, 0o600)
        path.chmod(0o600)
        info = path.lstat()
        return {
            "path": str(path),
            "device": str(info.st_dev),
            "inode": str(info.st_ino),
            "mode": "0600",
            "uid": str(info.st_uid),
            "gid": str(info.st_gid),
        }

    ready_fifo = fifo_reference("h11-ready-committed.fifo")
    permit_fifo = fifo_reference("h11-permit-committed.fifo")
    policy = harness._SCENARIO_POLICIES["H11"]
    outputs = tuple(
        harness.OutputPath(
            role,
            (input_root if role == "run-main-properties" else receipt_root)
            / f"{role}.json",
        )
        for role in sorted(policy.required_outputs)
    )
    present_roles = list(policy.pre_permit_present_roles)
    future = [
        {"role": item.role, "path": str(item.path)}
        for item in outputs
        if item.role not in present_roles
    ]
    future.append({"role": "frozen-root", "path": str(root / "frozen")})
    future.sort(key=lambda item: item["role"])
    payload = {
        "schema": harness.H11_PERMIT_AUTHORITY_SCHEMA,
        "scenario": "H11",
        "run_unit": "scion-w3-h11-model.service",
        "permit_path": str(scenario_root / "PERMIT.json"),
        "permit_parent": {
            key: value
            for key, value in directory_chain[3].items()
            if key != "role"
        },
        "permit_ready_path": str(scenario_root / "PERMIT_READY.json"),
        "permit_ledger_path": str(scenario_root / "PERMIT-LEDGER.json"),
        "permit_ready_staging_path": str(scenario_root / "PERMIT_READY.pending"),
        "permit_staging_path": str(scenario_root / "PERMIT.pending"),
        "permit_ledger_staging_path": str(
            scenario_root / "PERMIT-LEDGER.pending"
        ),
        "directory_chain": directory_chain,
        "ready_commit_fifo": ready_fifo,
        "permit_commit_fifo": permit_fifo,
        "present_prerequisite_roles": present_roles,
        "future_absence_inventory": future,
    }
    fifo_rows = sorted(
        (
            {"role": "h11-ready-commit", "owner": "root", **ready_fifo},
            {"role": "h11-permit-commit", "owner": "root", **permit_fifo},
        ),
        key=lambda item: item["role"],
    )
    installer_authority = {
        "tree_receipt": {"fifos": json.loads(json.dumps(fifo_rows))},
        "preflight_receipt": {"fifos": json.loads(json.dumps(fifo_rows))},
    }
    return payload, source, outputs, installer_authority


def _decode_h11_authority_model(
    payload: dict[str, Any],
    source: harness.ExecutionManifestSource,
    outputs: tuple[harness.OutputPath, ...],
) -> harness.H11PermitAuthoritySpec:
    return harness.H11PermitAuthoritySpec.decode(
        payload,
        source=source,
        scenario="H11",
        run_unit="scion-w3-h11-model.service",
        input_root=source.path.parents[3] / "input",
        receipt_root=source.path.parent / "receipts",
        outputs=outputs,
        policy=harness._SCENARIO_POLICIES["H11"],
    )


def test_h11_manifest_authority_validates_and_retains_the_closed_model(
    tmp_path: Path,
) -> None:
    payload, source, outputs, installer_authority = (
        _h11_manifest_authority_model(tmp_path)
    )
    try:
        spec = _decode_h11_authority_model(payload, source, outputs)
        retained = spec.retain_and_prevalidate(
            source=source,
            installer_authority=installer_authority,
            outputs=outputs,
            acquisitions=(),
            require_root=False,
        )
        assert spec.present_prerequisite_roles == ("h0", "run-main-properties")
        assert tuple(item.role for item in spec.future_absence_inventory) == tuple(
            sorted(
                (harness._SCENARIO_POLICIES["H11"].required_outputs - {"h0", "run-main-properties"})
                | {"frozen-root"}
            )
        )
        assert len(spec.transaction_paths) == 7
        retained.revalidate(require_root=False)
        retained.close()
        assert all(item.descriptor == -1 for item in retained.owned_directories)
        assert all(item.descriptor == -1 for item in retained.commit_fifos)
        assert source.descriptor >= 0
    finally:
        source.close()


@pytest.mark.parametrize(
    "mutation",
    (
        "extra-field",
        "directory-order",
        "directory-parent",
        "directory-reference-field",
        "present-order",
        "future-order",
        "future-omission",
        "future-duplicate-path",
        "transaction-layout",
        "fifo-layout",
        "fifo-duplicate-identity",
    ),
)
def test_h11_manifest_authority_rejects_field_order_parent_and_duplicate_drift(
    tmp_path: Path, mutation: str
) -> None:
    payload, source, outputs, _installer_authority = (
        _h11_manifest_authority_model(tmp_path)
    )
    try:
        if mutation == "extra-field":
            payload["caller_inventory"] = []
        elif mutation == "directory-order":
            payload["directory_chain"][0], payload["directory_chain"][1] = (
                payload["directory_chain"][1],
                payload["directory_chain"][0],
            )
        elif mutation == "directory-parent":
            payload["directory_chain"][5]["path"] = str(
                source.path.parents[3] / "receipts"
            )
        elif mutation == "directory-reference-field":
            payload["directory_chain"][4].pop("gid")
        elif mutation == "present-order":
            payload["present_prerequisite_roles"].reverse()
        elif mutation == "future-order":
            payload["future_absence_inventory"].reverse()
        elif mutation == "future-omission":
            payload["future_absence_inventory"].pop()
        elif mutation == "future-duplicate-path":
            payload["future_absence_inventory"][1]["path"] = payload[
                "future_absence_inventory"
            ][0]["path"]
        elif mutation == "transaction-layout":
            payload["permit_ledger_staging_path"] = str(
                source.path.parent / "LEDGER.pending"
            )
        elif mutation == "fifo-layout":
            payload["ready_commit_fifo"]["path"] = str(
                source.path.parents[3] / "fifo" / "ready.fifo"
            )
        else:
            payload["permit_commit_fifo"]["device"] = payload[
                "ready_commit_fifo"
            ]["device"]
            payload["permit_commit_fifo"]["inode"] = payload[
                "ready_commit_fifo"
            ]["inode"]
        with pytest.raises(harness.HarnessError):
            _decode_h11_authority_model(payload, source, outputs)
    finally:
        source.close()


def test_h11_manifest_authority_rejects_output_outside_exact_parent(
    tmp_path: Path,
) -> None:
    payload, source, outputs, _installer_authority = (
        _h11_manifest_authority_model(tmp_path)
    )
    mutated = tuple(
        harness.OutputPath(item.role, tmp_path / "outside.json")
        if item.role == "final"
        else item
        for item in outputs
    )
    for item in payload["future_absence_inventory"]:
        if item["role"] == "final":
            item["path"] = str(tmp_path / "outside.json")
    try:
        with pytest.raises(harness.HarnessError, match="outside its exact parent"):
            _decode_h11_authority_model(payload, source, mutated)
    finally:
        source.close()


@pytest.mark.parametrize("mutation", ("tree", "preflight", "directory", "fifo"))
def test_h11_prevalidation_rejects_directory_or_fifo_authority_drift(
    tmp_path: Path, mutation: str
) -> None:
    payload, source, outputs, installer_authority = (
        _h11_manifest_authority_model(tmp_path)
    )
    try:
        spec = _decode_h11_authority_model(payload, source, outputs)
        if mutation == "tree":
            installer_authority["tree_receipt"]["fifos"][0]["inode"] = "1"
        elif mutation == "preflight":
            installer_authority["preflight_receipt"] = {"fifos": []}
        elif mutation == "directory":
            source.path.parent.chmod(0o755)
        else:
            Path(payload["ready_commit_fifo"]["path"]).chmod(0o644)
        with pytest.raises(harness.HarnessError):
            spec.retain_and_prevalidate(
                source=source,
                installer_authority=installer_authority,
                outputs=outputs,
                acquisitions=(),
                require_root=False,
            )
    finally:
        source.close()


@pytest.mark.parametrize("created", ("output", "transaction", "frozen"))
def test_h11_prevalidation_rejects_every_initial_presence(
    tmp_path: Path, created: str
) -> None:
    payload, source, outputs, installer_authority = (
        _h11_manifest_authority_model(tmp_path)
    )
    try:
        spec = _decode_h11_authority_model(payload, source, outputs)
        if created == "output":
            path = outputs[0].path
        elif created == "transaction":
            path = source.path.parent / "AUTHORIZE-RELEASE.json"
        else:
            path = source.path.parents[3] / "frozen"
        if created == "frozen":
            path.mkdir()
        else:
            parent_mode = stat.S_IMODE(path.parent.lstat().st_mode)
            path.parent.chmod(0o755)
            path.write_text("present\n", encoding="ascii")
            path.parent.chmod(parent_mode)
        with pytest.raises(harness.HarnessError, match="exists before StartUnit"):
            spec.retain_and_prevalidate(
                source=source,
                installer_authority=installer_authority,
                outputs=outputs,
                acquisitions=(),
                require_root=False,
            )
    finally:
        source.close()


def _post_open_decode_payload(scenario: str) -> dict[str, Any]:
    keys = (harness._MANIFEST_KEYS - {"descriptor_path", "boot_id_path"}) | {
        "descriptor",
        "installer_receipt",
        "harness_program",
        "boot_id_file",
    }
    if scenario == "H11":
        keys.add("permit_authority")
    payload = {key: None for key in keys}
    payload.update(
        {
            "schema": harness.MANIFEST_SCHEMA,
            "scenario": scenario,
            "run_unit": f"scion-w3-{scenario.lower()}-decode.service",
            "closer_unit": None,
            "input_root": "/sys",
            "receipt_root": "/proc",
            "acquisitions": [],
            "outputs": [{"role": "final", "path": "/proc/scion-final.json"}],
            "scenario_input": None,
            "formal_actions": [],
            "static_roles": [],
        }
    )
    if scenario == "H11":
        payload["permit_authority"] = {}
    return payload


@pytest.mark.parametrize(
    ("failure", "message"),
    (
        ("canonical-json", "strict UTF-8 JSON"),
        ("non-h11-extra", "unknown=.*permit_authority"),
        ("h11-missing", "missing=.*permit_authority"),
        ("h11-extra", "unknown=.*unexpected_h11_field"),
        ("permit-inner", "H11 permit_authority keys mismatch"),
    ),
)
def test_decode_manifest_closes_fake_source_for_every_post_open_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    message: str,
) -> None:
    scenario = "H10" if failure == "non-h11-extra" else "H11"
    payload = _post_open_decode_payload(scenario)
    if failure == "canonical-json":
        raw = b'{"schema":'
    else:
        if failure == "non-h11-extra":
            payload["permit_authority"] = {}
        elif failure == "h11-missing":
            payload.pop("permit_authority")
        elif failure == "h11-extra":
            payload["unexpected_h11_field"] = None
        else:
            payload["permit_authority"] = {"unexpected": None}
        raw = _canonical(payload)

    class FakeSource:
        def __init__(self) -> None:
            self.close_calls = 0

        def close(self) -> None:
            self.close_calls += 1

    source = FakeSource()
    monkeypatch.setattr(
        harness.ExecutionManifestSource,
        "open_once",
        classmethod(lambda cls, path, require_root: (source, raw)),
    )
    with pytest.raises(harness.HarnessError, match=message):
        harness.decode_manifest(tmp_path / "unused.json")
    assert source.close_calls == 1


def test_decode_manifest_closes_every_real_source_fd_after_post_open_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _payload, source, _outputs, _installer_authority = (
        _h11_manifest_authority_model(tmp_path)
    )
    descriptors = [source.descriptor, *(item.descriptor for item in source.directories)]
    monkeypatch.setattr(
        harness.ExecutionManifestSource,
        "open_once",
        classmethod(lambda cls, path, require_root: (source, b'{"schema":')),
    )
    with pytest.raises(harness.HarnessError, match="strict UTF-8 JSON"):
        harness.decode_manifest(tmp_path / "unused.json")
    assert source.descriptor == -1
    assert all(item.descriptor == -1 for item in source.directories)
    for descriptor in descriptors:
        with pytest.raises(OSError):
            os.fstat(descriptor)


def test_decode_manifest_transfers_source_only_on_success_and_reraises_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeSource:
        def __init__(self) -> None:
            self.close_calls = 0

        def close(self) -> None:
            self.close_calls += 1

    source = FakeSource()
    monkeypatch.setattr(
        harness.ExecutionManifestSource,
        "open_once",
        classmethod(lambda cls, path, require_root: (source, b"opened")),
    )
    transferred = object()
    monkeypatch.setattr(
        harness,
        "_decode_open_manifest",
        lambda opened_source, raw: transferred,
    )
    assert harness.decode_manifest(tmp_path / "unused.json") is transferred
    assert source.close_calls == 0

    failure = RuntimeError("original post-open failure")

    def reject(opened_source: Any, raw: bytes) -> Any:
        raise failure

    monkeypatch.setattr(harness, "_decode_open_manifest", reject)
    with pytest.raises(RuntimeError) as caught:
        harness.decode_manifest(tmp_path / "unused.json")
    assert caught.value is failure
    assert source.close_calls == 1


@pytest.mark.parametrize("failure", ("receipt-child", "permit-commit-fifo"))
def test_h11_retain_rolls_back_every_opened_child_fd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    payload, source, outputs, installer_authority = (
        _h11_manifest_authority_model(tmp_path)
    )
    spec = _decode_h11_authority_model(payload, source, outputs)
    original_open = os.open
    opened: list[int] = []

    def failing_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        leaf = os.fsdecode(path)
        if (
            (failure == "receipt-child" and leaf == "receipts")
            or (
                failure == "permit-commit-fifo"
                and leaf == "h11-permit-committed.fifo"
            )
        ):
            raise OSError("injected retained-child open failure")
        descriptor = (
            original_open(path, flags, mode)
            if dir_fd is None
            else original_open(path, flags, mode, dir_fd=dir_fd)
        )
        if leaf in {
            "input",
            "receipts",
            "fifo",
            "h11-ready-committed.fifo",
        }:
            opened.append(descriptor)
        return descriptor

    monkeypatch.setattr(os, "open", failing_open)
    try:
        with pytest.raises(OSError, match="injected retained-child open failure"):
            spec.retain_and_prevalidate(
                source=source,
                installer_authority=installer_authority,
                outputs=outputs,
                acquisitions=(),
                require_root=False,
            )
        assert opened
        for descriptor in opened:
            with pytest.raises(OSError):
                os.fstat(descriptor)
        assert source.descriptor >= 0
    finally:
        source.close()


def _retained_h11_runtime_model(
    tmp_path: Path,
) -> tuple[harness.ExecutionManifestSource, harness.RetainedH11PermitAuthority]:
    payload, source, outputs, installer_authority = (
        _h11_manifest_authority_model(tmp_path)
    )
    spec = _decode_h11_authority_model(payload, source, outputs)
    retained = spec.retain_and_prevalidate(
        source=source,
        installer_authority=installer_authority,
        outputs=outputs,
        acquisitions=(),
        require_root=False,
    )
    return source, retained


def _publish_watched_transaction(
    watch: harness.AuthorityDirectoryWatch,
    parent: Path,
    pending_name: str,
    final_name: str,
    *,
    retained_publisher: bool,
) -> int:
    pending = parent / pending_name
    pending.write_bytes(b"{}\n")
    pending.chmod(0o444)
    descriptor = os.open(pending, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    if retained_publisher:
        watch.bind_retained_publication(
            pending_name=pending_name,
            final_name=final_name,
            descriptor=descriptor,
        )
    pending.rename(parent / final_name)
    return descriptor


def test_h11_runtime_watch_records_closed_real_event_chronology(
    tmp_path: Path,
) -> None:
    source, retained = _retained_h11_runtime_model(tmp_path)
    runtime = retained.open_runtime_authority()
    scenario_root = source.path.parent
    descriptors: list[int] = []
    try:
        h0 = next(item.path for item in retained.outputs if item.role == "h0")
        receipt_mode = stat.S_IMODE(h0.parent.lstat().st_mode)
        h0.parent.chmod(0o755)
        h0.write_bytes(b"{}\n")
        h0.chmod(0o444)
        h0.parent.chmod(receipt_mode)
        h0_rows = runtime.drain("receipt-root")
        assert h0_rows == (
            {
                "ordinal": "1",
                "parent_role": "receipt-root",
                "name": h0.name,
                "mask": "CREATE",
                "cookie": "0",
                "device": str(h0.lstat().st_dev),
                "inode": str(h0.lstat().st_ino),
            },
        )

        scenario_watch = runtime.watches["scenario-root"]
        ready_descriptor = _publish_watched_transaction(
            scenario_watch,
            scenario_root,
            "PERMIT_READY.pending",
            "PERMIT_READY.json",
            retained_publisher=True,
        )
        descriptors.append(ready_descriptor)
        ready_rows = runtime.drain("scenario-root")
        assert [item["ordinal"] for item in ready_rows] == ["2", "3", "4"]
        assert [item["mask"] for item in ready_rows] == [
            "CREATE",
            "MOVED_FROM",
            "MOVED_TO",
        ]
        assert ready_rows[0]["cookie"] == "0"
        assert ready_rows[1]["cookie"] == ready_rows[2]["cookie"] != "0"
        assert len({(item["device"], item["inode"]) for item in ready_rows}) == 1

        authorization = scenario_root / "AUTHORIZE-RELEASE.json"
        authorization.write_bytes(b"{}\n")
        authorization.chmod(0o444)
        assert runtime.drain("scenario-root")[0] == {
            "ordinal": "5",
            "parent_role": "scenario-root",
            "name": authorization.name,
            "mask": "CREATE",
            "cookie": "0",
            "device": str(authorization.lstat().st_dev),
            "inode": str(authorization.lstat().st_ino),
        }

        permit_descriptor = _publish_watched_transaction(
            scenario_watch,
            scenario_root,
            "PERMIT.pending",
            "PERMIT.json",
            retained_publisher=False,
        )
        descriptors.append(permit_descriptor)
        permit_rows = runtime.drain(
            "scenario-root", external_permit_descriptor=permit_descriptor
        )
        assert [item["ordinal"] for item in permit_rows] == ["6", "7", "8"]
        assert [item["mask"] for item in permit_rows] == [
            "CREATE",
            "MOVED_FROM",
            "MOVED_TO",
        ]
        assert permit_rows[1]["cookie"] == permit_rows[2]["cookie"] != "0"
        assert len({(item["device"], item["inode"]) for item in permit_rows}) == 1

        ledger_descriptor = _publish_watched_transaction(
            scenario_watch,
            scenario_root,
            "PERMIT-LEDGER.pending",
            "PERMIT-LEDGER.json",
            retained_publisher=True,
        )
        descriptors.append(ledger_descriptor)
        ledger_rows = runtime.drain("scenario-root")
        assert [item["ordinal"] for item in ledger_rows] == ["9", "10", "11"]
        assert [item["mask"] for item in ledger_rows] == [
            "CREATE",
            "MOVED_FROM",
            "MOVED_TO",
        ]
        assert tuple(item["ordinal"] for item in runtime.events) == tuple(
            str(index) for index in range(1, 12)
        )
    finally:
        for descriptor in descriptors:
            os.close(descriptor)
        runtime.close()
        retained.close()
        source.close()


@pytest.mark.parametrize(
    "failure",
    (
        "fatal-delete",
        "fatal-delete-self",
        "fatal-move-self",
        "fatal-overflow",
        "fatal-ignored",
        "fatal-unmount",
        "unknown",
        "mask",
        "order",
        "cookie",
        "publisher-inode",
    ),
)
def test_h11_runtime_watch_rejects_event_mask_order_cookie_and_inode_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    source, retained = _retained_h11_runtime_model(tmp_path)
    runtime = retained.open_runtime_authority()
    watch = runtime.watches["scenario-root"]
    publisher = -1
    try:
        if failure.startswith("fatal-"):
            fatal_mask = {
                "fatal-delete": watch._DELETE,
                "fatal-delete-self": watch._DELETE_SELF,
                "fatal-move-self": watch._MOVE_SELF,
                "fatal-overflow": watch._Q_OVERFLOW,
                "fatal-ignored": watch._IGNORED,
                "fatal-unmount": watch._UNMOUNT,
            }[failure]
            events = (
                harness._AuthorityInotifyEvent(
                    watch.watch,
                    fatal_mask,
                    0,
                    "PERMIT_READY.json",
                ),
            )
        elif failure == "unknown":
            events = (
                harness._AuthorityInotifyEvent(
                    watch.watch, watch._CREATE, 0, "UNKNOWN.json"
                ),
            )
        elif failure == "mask":
            events = (
                harness._AuthorityInotifyEvent(
                    watch.watch,
                    watch._CREATE | watch._MOVED_TO,
                    0,
                    "PERMIT_READY.pending",
                ),
            )
        else:
            pending = source.path.parent / "PERMIT_READY.pending"
            pending.write_bytes(b"old\n")
            pending.chmod(0o444)
            publisher = os.open(
                pending, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
            )
            watch.bind_retained_publication(
                pending_name="PERMIT_READY.pending",
                final_name="PERMIT_READY.json",
                descriptor=publisher,
            )
            pending.rename(source.path.parent / "PERMIT_READY.json")
            if failure == "publisher-inode":
                replacement = tmp_path / "replacement-ready.json"
                replacement.write_bytes(b"old\n")
                replacement.chmod(0o444)
                os.replace(replacement, source.path.parent / "PERMIT_READY.json")
            second_mask = (
                watch._MOVED_TO if failure == "order" else watch._MOVED_FROM
            )
            third_mask = (
                watch._MOVED_FROM if failure == "order" else watch._MOVED_TO
            )
            second_name = (
                "PERMIT_READY.json"
                if failure == "order"
                else "PERMIT_READY.pending"
            )
            third_name = (
                "PERMIT_READY.pending"
                if failure == "order"
                else "PERMIT_READY.json"
            )
            events = (
                harness._AuthorityInotifyEvent(
                    watch.watch, watch._CREATE, 0, "PERMIT_READY.pending"
                ),
                harness._AuthorityInotifyEvent(
                    watch.watch, second_mask, 17, second_name
                ),
                harness._AuthorityInotifyEvent(
                    watch.watch,
                    third_mask,
                    18 if failure == "cookie" else 17,
                    third_name,
                ),
            )
        monkeypatch.setattr(watch, "_read_raw_events", lambda: events)
        with pytest.raises(harness.HarnessError):
            runtime.drain("scenario-root")
        assert runtime.events == ()
    finally:
        if publisher >= 0:
            os.close(publisher)
        runtime.close()
        retained.close()
        source.close()


def test_h11_runtime_watch_rejects_external_permit_descriptor_inode_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, retained = _retained_h11_runtime_model(tmp_path)
    runtime = retained.open_runtime_authority()
    watch = runtime.watches["scenario-root"]
    permit = source.path.parent / "PERMIT.json"
    permit.write_bytes(b"permit\n")
    permit.chmod(0o444)
    decoy = tmp_path / "permit-decoy.json"
    decoy.write_bytes(permit.read_bytes())
    decoy.chmod(0o444)
    descriptor = os.open(decoy, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    events = (
        harness._AuthorityInotifyEvent(
            watch.watch, watch._CREATE, 0, "PERMIT.pending"
        ),
        harness._AuthorityInotifyEvent(
            watch.watch, watch._MOVED_FROM, 23, "PERMIT.pending"
        ),
        harness._AuthorityInotifyEvent(
            watch.watch, watch._MOVED_TO, 23, "PERMIT.json"
        ),
    )
    monkeypatch.setattr(watch, "_read_raw_events", lambda: events)
    try:
        with pytest.raises(harness.HarnessError, match="pinned publisher inode"):
            runtime.drain(
                "scenario-root", external_permit_descriptor=descriptor
            )
        assert runtime.events == ()
    finally:
        os.close(descriptor)
        runtime.close()
        retained.close()
        source.close()


@pytest.mark.parametrize(
    ("fifo_name", "first_direction"),
    (
        ("ready", "reader"),
        ("ready", "writer"),
        ("permit", "reader"),
        ("permit", "writer"),
    ),
)
def test_h11_commit_fifo_accepts_both_blocking_endpoint_schedules(
    tmp_path: Path,
    fifo_name: str,
    first_direction: str,
) -> None:
    source, retained = _retained_h11_runtime_model(tmp_path)
    fifo = (
        retained.commit_fifos[0]
        if retained.commit_fifos[0].role == f"h11-{fifo_name}-commit"
        else retained.commit_fifos[1]
    )
    reader_actor = "authorizer" if fifo_name == "ready" else "harness"
    writer_actor = "harness" if fifo_name == "ready" else "authorizer"
    result: dict[str, Any] = {}
    entered = threading.Event()

    def first_endpoint() -> None:
        entered.set()
        try:
            if first_direction == "reader":
                result["payload"] = fifo.read_commit(actor=reader_actor)
            else:
                fifo.write_commit(actor=writer_actor)
                result["written"] = True
        except BaseException as exc:
            result["error"] = exc

    thread = threading.Thread(target=first_endpoint)
    thread.start()
    entered.wait()
    try:
        if first_direction == "reader":
            fifo.write_commit(actor=writer_actor)
        else:
            result["payload"] = fifo.read_commit(actor=reader_actor)
        thread.join()
        assert "error" not in result
        assert result["payload"] == fifo.expected_payload
    finally:
        retained.close()
        source.close()


@pytest.mark.parametrize("mutation", ("prefix", "suffix", "duplicate"))
def test_h11_commit_fifo_rejects_nonexact_frame_at_eof(
    tmp_path: Path, mutation: str
) -> None:
    source, retained = _retained_h11_runtime_model(tmp_path)
    fifo = next(
        item for item in retained.commit_fifos if item.role == "h11-ready-commit"
    )
    writer_entered = threading.Event()
    writer_error: list[BaseException] = []

    def malformed_writer() -> None:
        try:
            descriptor, direction = fifo._open_endpoint("harness")
            assert direction == "writer"
            writer_entered.set()
            try:
                if mutation == "prefix":
                    os.write(descriptor, fifo.expected_payload[:-1])
                elif mutation == "suffix":
                    os.write(descriptor, fifo.expected_payload + b"X")
                else:
                    os.write(descriptor, fifo.expected_payload)
                    os.write(descriptor, fifo.expected_payload)
            finally:
                os.close(descriptor)
        except BaseException as exc:
            writer_error.append(exc)

    thread = threading.Thread(target=malformed_writer)
    thread.start()
    try:
        with pytest.raises(harness.HarnessError, match="differs before EOF"):
            fifo.read_commit(actor="authorizer")
        thread.join()
        assert not writer_error
        assert writer_entered.is_set()
    finally:
        retained.close()
        source.close()


def test_h11_commit_fifo_rejects_path_replacement_and_stage_b_ast_closes(
    tmp_path: Path,
) -> None:
    source, retained = _retained_h11_runtime_model(tmp_path)
    fifo = next(
        item for item in retained.commit_fifos if item.role == "h11-ready-commit"
    )
    displaced = fifo.reference.path.with_name("displaced-ready-commit.fifo")
    fifo.reference.path.rename(displaced)
    os.mkfifo(fifo.reference.path, 0o600)
    fifo.reference.path.chmod(0o600)
    try:
        with pytest.raises(harness.HarnessError, match="one writer"):
            fifo.write_commit(actor="authorizer")
        with pytest.raises(harness.HarnessError, match="drifted"):
            fifo.revalidate(require_root=False)
        for class_object in (
            harness.AuthorityDirectoryWatch,
            harness.PinnedCommitFifo,
            harness.H11RuntimeOpenAuthority,
        ):
            source_text = inspect.getsource(class_object)
            tree = ast.parse(source_text)
            assert "O_NONBLOCK" not in source_text
            assert not any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"poll", "sleep"}
                for node in ast.walk(tree)
            )
            assert not any(
                isinstance(node, ast.keyword) and node.arg == "timeout"
                for node in ast.walk(tree)
            )
    finally:
        retained.close()
        source.close()


def _root_c1a_authority_model(
    tmp_path: Path,
    *,
    ordinary_fifos: tuple[tuple[str, str], ...] = (("run-ready", "run-ready"),),
) -> tuple[Path, dict[str, Path]]:
    chain = _static_authority_chain(tmp_path, ordinary_fifos=ordinary_fifos)
    preflight_path = _publish_test_preflight(chain)
    unit_directory = tmp_path / "c1a-units"
    unit_directory.mkdir()
    install_manifest_path, install_receipt_path = _install_plan(chain, tmp_path)
    install_manifest_path.chmod(0o444)
    manager = FakeInstallerManager(unit_directory)
    original_file = installer.__file__
    installer.__file__ = str(chain["paths"]["installer-program"])
    try:
        installer.install_units(
            install_manifest_path,
            manager=manager,
            require_root=False,
            unit_directory=unit_directory,
        )
    finally:
        installer.__file__ = original_file

    root = chain["root"]
    harness_root = root / "authority" / "harness"
    scenario_root = harness_root / "H11"
    receipt_root = scenario_root / "receipts"
    harness_root.mkdir(mode=0o700)
    scenario_root.mkdir(mode=0o700)
    receipt_root.mkdir(mode=0o555)
    receipt_root.chmod(0o555)
    input_root = root / "input"
    fifo_root = root / "fifo"

    def directory_reference(role: str, path: Path) -> dict[str, str]:
        info = path.lstat()
        return {
            "role": role,
            "path": str(path),
            "device": str(info.st_dev),
            "inode": str(info.st_ino),
            "mode": format(stat.S_IMODE(info.st_mode), "04o"),
            "uid": str(info.st_uid),
            "gid": str(info.st_gid),
        }

    directory_chain = [
        directory_reference(role, path)
        for role, path in (
            ("formal-root", root),
            ("authority-root", root / "authority"),
            ("harness-root", harness_root),
            ("scenario-root", scenario_root),
            ("input-root", input_root),
            ("receipt-root", receipt_root),
            ("fifo-root", fifo_root),
        )
    ]
    tree_receipt = json.loads(chain["tree_receipt"].read_text(encoding="ascii"))

    def fifo_reference(role: str) -> dict[str, str]:
        row = next(item for item in tree_receipt["fifos"] if item["role"] == role)
        return {
            key: row[key]
            for key in ("path", "device", "inode", "mode", "uid", "gid")
        }

    ready_fifo = fifo_reference("h11-ready-commit")
    permit_fifo = fifo_reference("h11-permit-commit")
    policy = harness._SCENARIO_POLICIES["H11"]
    outputs = [
        {
            "role": role,
            "path": str(
                (input_root if role == "run-main-properties" else receipt_root)
                / f"{role}.json"
            ),
        }
        for role in sorted(policy.required_outputs)
    ]
    future = [
        dict(item)
        for item in outputs
        if item["role"] not in policy.pre_permit_present_roles
    ]
    future.append({"role": "frozen-root", "path": str(root / "frozen")})
    future.sort(key=lambda item: item["role"])
    permit_authority = {
        "schema": harness.H11_PERMIT_AUTHORITY_SCHEMA,
        "scenario": "H11",
        "run_unit": chain["run_unit"],
        "permit_path": str(scenario_root / "PERMIT.json"),
        "permit_parent": {
            key: value
            for key, value in directory_chain[3].items()
            if key != "role"
        },
        "permit_ready_path": str(scenario_root / "PERMIT_READY.json"),
        "permit_ledger_path": str(scenario_root / "PERMIT-LEDGER.json"),
        "permit_ready_staging_path": str(scenario_root / "PERMIT_READY.pending"),
        "permit_staging_path": str(scenario_root / "PERMIT.pending"),
        "permit_ledger_staging_path": str(
            scenario_root / "PERMIT-LEDGER.pending"
        ),
        "directory_chain": directory_chain,
        "ready_commit_fifo": ready_fifo,
        "permit_commit_fifo": permit_fifo,
        "present_prerequisite_roles": list(policy.pre_permit_present_roles),
        "future_absence_inventory": future,
    }
    manifest_path = scenario_root / "MANIFEST.json"
    manifest = {
        key: None for key in installer._H11_HARNESS_MANIFEST_KEYS
    }
    manifest.update(
        {
            "schema": "scion.generic_backend.systemd_harness_manifest.v1",
            "scenario": "H11",
            "run_unit": permit_authority["run_unit"],
            "closer_unit": chain["close_unit"],
            "input_root": str(input_root),
            "receipt_root": str(receipt_root),
            "acquisitions": [],
            "outputs": outputs,
            "scenario_input": None,
            "formal_actions": [],
            "static_roles": [],
            "permit_authority": permit_authority,
            "installer_receipt": {
                "path": str(install_receipt_path),
                "sha256": _sha(install_receipt_path),
            },
            "preflight_receipt": {
                "path": str(preflight_path),
                "sha256": _sha(preflight_path),
            },
        }
    )
    _write(manifest_path, manifest)
    manifest_path.chmod(0o444)
    return manifest_path, {
        "install_receipt": install_receipt_path,
        "install_manifest": install_manifest_path,
        "tree_receipt": chain["tree_receipt"],
        "seal_receipt": chain["seal_receipt"],
        "preflight_receipt": preflight_path,
    }


@pytest.mark.parametrize("replacement", ("receipt-directory", "ready-fifo"))
def test_root_c1a_revalidate_rejects_chain_or_fifo_replacement(
    tmp_path: Path, replacement: str
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)
    authority = installer.H11RootRetainedAuthority.open(
        manifest_path,
        require_root=False,
    )
    try:
        if replacement == "receipt-directory":
            path = authority.directories[5].reference.path
            displaced = path.with_name("receipts-displaced")
            path.rename(displaced)
            path.mkdir(mode=0o555)
            path.chmod(0o555)
        else:
            path = authority.commit_fifos[0].reference.path
            displaced = path.with_name("ready-fifo-displaced")
            path.rename(displaced)
            os.mkfifo(path, 0o600)
            path.chmod(0o600)
        with pytest.raises(installer.InstallerError, match="drifted"):
            authority.revalidate(require_root=False)
    finally:
        authority.close()


def test_root_c1a_rejects_tree_preflight_fifo_receipt_mismatch(
    tmp_path: Path,
) -> None:
    manifest_path, sources = _root_c1a_authority_model(tmp_path)
    preflight_path = sources["preflight_receipt"]
    preflight_receipt = json.loads(preflight_path.read_text(encoding="ascii"))
    preflight_receipt["fifos"][0]["inode"] = "1"
    preflight_path.chmod(0o644)
    _write(preflight_path, preflight_receipt)
    preflight_path.chmod(0o444)

    install_manifest_path = sources["install_manifest"]
    install_manifest = json.loads(
        install_manifest_path.read_text(encoding="ascii")
    )
    install_manifest["preflight_receipt"] = installer._file_reference(
        preflight_path
    )
    install_manifest_path.chmod(0o644)
    _write(install_manifest_path, install_manifest)
    install_manifest_path.chmod(0o444)

    install_receipt_path = sources["install_receipt"]
    install_receipt = json.loads(install_receipt_path.read_text(encoding="ascii"))
    install_receipt["preflight_receipt"] = installer._file_reference(
        preflight_path
    )
    install_receipt["install_manifest"] = installer._asset_reference(
        install_manifest_path
    )
    install_receipt_path.chmod(0o644)
    _write(install_receipt_path, install_receipt)
    install_receipt_path.chmod(0o444)

    manifest = json.loads(manifest_path.read_text(encoding="ascii"))
    manifest["installer_receipt"] = {
        "path": str(install_receipt_path),
        "sha256": _sha(install_receipt_path),
    }
    manifest["preflight_receipt"] = {
        "path": str(preflight_path),
        "sha256": _sha(preflight_path),
    }
    manifest_path.chmod(0o644)
    _write(manifest_path, manifest)
    manifest_path.chmod(0o444)
    with pytest.raises(
        installer.InstallerError,
        match="TREE/install authority|inventories differ",
    ):
        installer.H11RootRetainedAuthority.open(
            manifest_path,
            require_root=False,
        )


def test_root_c1a_rejects_manifest_preflight_split_brain(tmp_path: Path) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="ascii"))
    manifest["preflight_receipt"] = {
        "path": str(tmp_path / "wrong" / "PREFLIGHT.json"),
        "sha256": "0" * 64,
    }
    manifest_path.chmod(0o644)
    _write(manifest_path, manifest)
    manifest_path.chmod(0o444)
    with pytest.raises(installer.InstallerError, match="manifest preflight authority"):
        installer.H11RootRetainedAuthority.open(
            manifest_path,
            require_root=False,
        )


@pytest.mark.parametrize("field", ("input_root", "receipt_root"))
def test_root_c1a_rejects_manifest_output_root_split_brain(
    tmp_path: Path, field: str
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="ascii"))
    manifest[field] = str(tmp_path / f"wrong-{field}")
    manifest_path.chmod(0o644)
    _write(manifest_path, manifest)
    manifest_path.chmod(0o444)
    with pytest.raises(installer.InstallerError, match="output roots"):
        installer.H11RootRetainedAuthority.open(
            manifest_path,
            require_root=False,
        )


def test_root_c1a_rejects_coherently_rebound_tree_outside_authority(
    tmp_path: Path,
) -> None:
    manifest_path, sources = _root_c1a_authority_model(tmp_path)
    original_tree_path = sources["tree_receipt"]
    tree = json.loads(original_tree_path.read_text(encoding="ascii"))
    prepare_path = Path(tree["prepare_manifest"]["path"])
    prepare = json.loads(prepare_path.read_text(encoding="ascii"))
    external_tree_path = tmp_path / "external-tree.json"
    prepare["receipt_path"] = str(external_tree_path)
    prepare_path.chmod(0o644)
    _write(prepare_path, prepare)
    prepare_path.chmod(0o444)
    tree["prepare_manifest"] = installer._file_reference(prepare_path)
    _write(external_tree_path, tree)
    external_tree_path.chmod(0o444)

    seal_path = sources["seal_receipt"]
    seal = json.loads(seal_path.read_text(encoding="ascii"))
    seal["tree_receipt"] = installer._file_reference(external_tree_path)
    seal_path.chmod(0o644)
    _write(seal_path, seal)
    seal_path.chmod(0o444)

    preflight_path = sources["preflight_receipt"]
    preflight = json.loads(preflight_path.read_text(encoding="ascii"))
    preflight["tree_receipt"] = installer._asset_reference(external_tree_path)
    preflight["seal_receipt"] = installer._asset_reference(seal_path)
    preflight_path.chmod(0o644)
    _write(preflight_path, preflight)
    preflight_path.chmod(0o444)

    install_manifest_path = sources["install_manifest"]
    install_manifest = json.loads(
        install_manifest_path.read_text(encoding="ascii")
    )
    install_manifest["tree_receipt"] = installer._file_reference(
        external_tree_path
    )
    install_manifest["seal_receipt"] = installer._file_reference(seal_path)
    install_manifest["preflight_receipt"] = installer._file_reference(
        preflight_path
    )
    install_manifest_path.chmod(0o644)
    _write(install_manifest_path, install_manifest)
    install_manifest_path.chmod(0o444)

    install_receipt_path = sources["install_receipt"]
    install_receipt = json.loads(install_receipt_path.read_text(encoding="ascii"))
    install_receipt["tree_receipt"] = installer._file_reference(external_tree_path)
    install_receipt["seal_receipt"] = installer._file_reference(seal_path)
    install_receipt["preflight_receipt"] = installer._file_reference(
        preflight_path
    )
    install_receipt["install_manifest"] = installer._asset_reference(
        install_manifest_path
    )
    install_receipt_path.chmod(0o644)
    _write(install_receipt_path, install_receipt)
    install_receipt_path.chmod(0o444)

    manifest = json.loads(manifest_path.read_text(encoding="ascii"))
    manifest["installer_receipt"] = {
        "path": str(install_receipt_path),
        "sha256": _sha(install_receipt_path),
    }
    manifest["preflight_receipt"] = {
        "path": str(preflight_path),
        "sha256": _sha(preflight_path),
    }
    manifest_path.chmod(0o644)
    _write(manifest_path, manifest)
    manifest_path.chmod(0o444)

    with pytest.raises(installer.InstallerError, match="TREE receipt.*authority root"):
        installer.H11RootRetainedAuthority.open(
            manifest_path,
            require_root=False,
        )


def test_root_c1a_revalidate_rejects_same_byte_seal_replacement(
    tmp_path: Path,
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)
    authority = installer.H11RootRetainedAuthority.open(
        manifest_path,
        require_root=False,
    )
    seal = next(
        item for item in authority.bound_sources if item.label == "H11 seal_receipt"
    )
    displaced = seal.path.with_name("seal-displaced.json")
    raw = seal.path.read_bytes()
    seal.path.rename(displaced)
    seal.path.write_bytes(raw)
    seal.path.chmod(0o444)
    try:
        with pytest.raises(installer.InstallerError, match="retained H11 seal_receipt"):
            authority.revalidate(require_root=False)
    finally:
        authority.close()


def test_root_c1a_rejects_coherently_rebound_preflight_seal_split(
    tmp_path: Path,
) -> None:
    manifest_path, sources = _root_c1a_authority_model(tmp_path)
    seal_path = sources["seal_receipt"]
    decoy_seal_path = tmp_path / "decoy-seal.json"
    decoy_seal_path.write_bytes(seal_path.read_bytes())
    decoy_seal_path.chmod(0o444)

    preflight_path = sources["preflight_receipt"]
    preflight = json.loads(preflight_path.read_text(encoding="ascii"))
    preflight["seal_receipt"] = installer._asset_reference(decoy_seal_path)
    preflight_path.chmod(0o644)
    _write(preflight_path, preflight)
    preflight_path.chmod(0o444)

    install_manifest_path = sources["install_manifest"]
    install_manifest = json.loads(
        install_manifest_path.read_text(encoding="ascii")
    )
    install_manifest["preflight_receipt"] = installer._file_reference(
        preflight_path
    )
    install_manifest_path.chmod(0o644)
    _write(install_manifest_path, install_manifest)
    install_manifest_path.chmod(0o444)

    install_receipt_path = sources["install_receipt"]
    install_receipt = json.loads(install_receipt_path.read_text(encoding="ascii"))
    install_receipt["preflight_receipt"] = installer._file_reference(
        preflight_path
    )
    install_receipt["install_manifest"] = installer._asset_reference(
        install_manifest_path
    )
    install_receipt_path.chmod(0o644)
    _write(install_receipt_path, install_receipt)
    install_receipt_path.chmod(0o444)

    manifest = json.loads(manifest_path.read_text(encoding="ascii"))
    manifest["installer_receipt"] = {
        "path": str(install_receipt_path),
        "sha256": _sha(install_receipt_path),
    }
    manifest["preflight_receipt"] = {
        "path": str(preflight_path),
        "sha256": _sha(preflight_path),
    }
    manifest_path.chmod(0o644)
    _write(manifest_path, manifest)
    manifest_path.chmod(0o444)

    with pytest.raises(installer.InstallerError, match="TREE/install authority"):
        installer.H11RootRetainedAuthority.open(
            manifest_path,
            require_root=False,
        )


@pytest.mark.parametrize("failure", ("receipt-child", "permit-fifo"))
def test_root_c1a_partial_open_failure_rolls_back_every_descriptor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)
    original_open = os.open
    opened: list[int] = []

    def failing_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        leaf = os.fsdecode(path)
        if (
            (failure == "receipt-child" and leaf == "receipts")
            or (
                failure == "permit-fifo"
                and leaf == "h11-permit-committed.fifo"
            )
        ):
            raise OSError("injected C1a retained open failure")
        descriptor = (
            original_open(path, flags, mode)
            if dir_fd is None
            else original_open(path, flags, mode, dir_fd=dir_fd)
        )
        opened.append(descriptor)
        return descriptor

    monkeypatch.setattr(os, "open", failing_open)
    with pytest.raises(OSError, match="injected C1a retained open failure"):
        installer.H11RootRetainedAuthority.open(
            manifest_path,
            require_root=False,
        )
    assert opened
    for descriptor in opened:
        with pytest.raises(OSError):
            os.fstat(descriptor)


def _rewrite_root_h11_manifest(
    manifest_path: Path, mutate: Callable[[dict[str, Any]], None]
) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="ascii"))
    mutate(manifest)
    manifest_path.chmod(0o644)
    _write(manifest_path, manifest)
    manifest_path.chmod(0o444)


def test_root_c1b1_derives_canonical_partition_from_reordered_outputs(
    tmp_path: Path,
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)
    _rewrite_root_h11_manifest(
        manifest_path, lambda manifest: manifest["outputs"].reverse()
    )
    authority = installer.H11RootRetainedAuthority.open(
        manifest_path, require_root=False
    )
    try:
        partition = authority.derive_closed_partition()
        assert [item.role for item in partition.present_prerequisites] == [
            "h0",
            "run-main-properties",
        ]
        assert [item.role for item in partition.future_absence_inventory] == [
            "closer-properties",
            "exec-stop-post-properties",
            "final",
            "final-closer-properties",
            "final-run-properties",
            "frozen-root",
            "h12-absence",
            "journal",
            "manager-events",
            "signals",
            "source-selector",
        ]
        assert len(
            {
                item.path
                for item in (
                    *partition.present_prerequisites,
                    *partition.future_absence_inventory,
                )
            }
        ) == 13
    finally:
        authority.close()


@pytest.mark.parametrize(
    "mutation",
    (
        "omitted-role",
        "extra-role",
        "duplicate-role",
        "duplicate-path",
        "wrong-role",
        "wrong-parent",
        "transaction-alias",
    ),
)
def test_root_c1b1_rejects_nonclosed_manifest_output_inventory(
    tmp_path: Path, mutation: str
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)

    def mutate(manifest: dict[str, Any]) -> None:
        outputs = manifest["outputs"]
        if mutation == "omitted-role":
            outputs.pop()
        elif mutation == "extra-role":
            outputs.append(
                {"role": "extra-role", "path": outputs[-1]["path"] + ".extra"}
            )
        elif mutation == "duplicate-role":
            outputs[1]["role"] = outputs[0]["role"]
        elif mutation == "duplicate-path":
            outputs[1]["path"] = outputs[0]["path"]
        elif mutation == "wrong-role":
            outputs[0]["role"] = "unknown-role"
        elif mutation == "wrong-parent":
            outputs[0]["path"] = str(tmp_path / "outside.json")
        else:
            outputs[0]["path"] = manifest["permit_authority"]["permit_path"]

    _rewrite_root_h11_manifest(manifest_path, mutate)
    authority = installer.H11RootRetainedAuthority.open(
        manifest_path, require_root=False
    )
    try:
        with pytest.raises(installer.InstallerError, match="outputs|output"):
            authority.derive_closed_partition()
    finally:
        authority.close()


@pytest.mark.parametrize(
    "mutation",
    ("present-missing", "present-extra", "present-reordered", "present-wrong"),
)
def test_root_c1b1_rejects_declared_present_partition_drift(
    tmp_path: Path, mutation: str
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)

    def mutate(manifest: dict[str, Any]) -> None:
        present = manifest["permit_authority"]["present_prerequisite_roles"]
        if mutation == "present-missing":
            present.pop()
        elif mutation == "present-extra":
            present.append("signals")
        elif mutation == "present-reordered":
            present.reverse()
        else:
            present[0] = "signals"

    _rewrite_root_h11_manifest(manifest_path, mutate)
    authority = installer.H11RootRetainedAuthority.open(
        manifest_path, require_root=False
    )
    try:
        with pytest.raises(installer.InstallerError, match="present prerequisites"):
            authority.derive_closed_partition()
    finally:
        authority.close()


@pytest.mark.parametrize(
    "mutation",
    ("future-missing", "future-extra", "future-reordered", "future-duplicate", "future-wrong"),
)
def test_root_c1b1_rejects_declared_future_partition_drift(
    tmp_path: Path, mutation: str
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)

    def mutate(manifest: dict[str, Any]) -> None:
        future = manifest["permit_authority"]["future_absence_inventory"]
        if mutation == "future-missing":
            future.pop()
        elif mutation == "future-extra":
            future.append({"role": "extra-role", "path": str(tmp_path / "extra")})
        elif mutation == "future-reordered":
            future.reverse()
        elif mutation == "future-duplicate":
            future[1] = dict(future[0])
        else:
            future[0]["path"] = str(tmp_path / "wrong-future")

    _rewrite_root_h11_manifest(manifest_path, mutate)
    authority = installer.H11RootRetainedAuthority.open(
        manifest_path, require_root=False
    )
    try:
        with pytest.raises(installer.InstallerError, match="future absence"):
            authority.derive_closed_partition()
    finally:
        authority.close()


def test_root_c1b1_revalidates_retained_sources_before_derivation(
    tmp_path: Path,
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)
    authority = installer.H11RootRetainedAuthority.open(
        manifest_path, require_root=False
    )
    seal = next(
        item for item in authority.bound_sources if item.label == "H11 seal_receipt"
    )
    displaced = seal.path.with_name("derive-seal-displaced.json")
    raw = seal.path.read_bytes()
    seal.path.rename(displaced)
    seal.path.write_bytes(raw)
    seal.path.chmod(0o444)
    try:
        with pytest.raises(installer.InstallerError, match="retained H11 seal_receipt"):
            authority.derive_closed_partition()
    finally:
        authority.close()


@pytest.mark.parametrize("mutation", ("path-alias", "source-inode-alias"))
def test_root_c1b1_defensive_authority_alias_invariants(
    tmp_path: Path,
    mutation: str,
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)
    authority = installer.H11RootRetainedAuthority.open(
        manifest_path, require_root=False
    )
    # C1a makes these states unreachable from a valid filesystem tree.  Mutate
    # only the retained in-memory model to keep the C1b1 defensive branches live.
    authority.revalidate = lambda *, require_root: None  # type: ignore[method-assign]
    try:
        if mutation == "path-alias":
            authority.bound_sources[0].path = authority.manifest_path
            expected = "path authority aliases"
        else:
            first = authority.bound_sources[0].source
            second = authority.bound_sources[1].source
            second["device"] = first["device"]
            second["inode"] = first["inode"]
            expected = "retained regular source aliases"
        with pytest.raises(installer.InstallerError, match=expected):
            authority.derive_closed_partition()
    finally:
        authority.close()


def test_root_c1b1_rejects_declared_transaction_path_drift(
    tmp_path: Path,
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)
    _rewrite_root_h11_manifest(
        manifest_path,
        lambda manifest: manifest["permit_authority"].__setitem__(
            "permit_path", str(tmp_path / "wrong-permit.json")
        ),
    )
    authority = installer.H11RootRetainedAuthority.open(
        manifest_path, require_root=False
    )
    try:
        with pytest.raises(installer.InstallerError, match="seven-path layout"):
            authority.derive_closed_partition()
    finally:
        authority.close()


_ROOT_C1B2_LAYOUT = (
    ("authorization", "AUTHORIZE-RELEASE.json"),
    ("permit-ready-staging", "PERMIT_READY.pending"),
    ("permit-ready", "PERMIT_READY.json"),
    ("permit-staging", "PERMIT.pending"),
    ("permit", "PERMIT.json"),
    ("permit-ledger-staging", "PERMIT-LEDGER.pending"),
    ("permit-ledger", "PERMIT-LEDGER.json"),
)
_ROOT_C1B2_PHASES = {
    "pre-start": ("absent",) * 7,
    "ready-visible": (
        "absent", "absent", "present", "absent", "absent", "absent", "absent"
    ),
    "authorizer-input": (
        "present", "absent", "present", "absent", "absent", "absent", "absent"
    ),
    "permit-committed": (
        "present", "absent", "present", "absent", "present", "absent", "absent"
    ),
    "ledger-committed": (
        "present", "absent", "present", "absent", "present", "absent", "present"
    ),
}


def _materialize_root_c1b2_phase(
    authority: installer.H11RootRetainedAuthority,
    phase: str,
) -> dict[str, Path]:
    scenario_root = authority.directories[3].reference.path
    paths = {
        role: scenario_root / leaf
        for role, leaf in _ROOT_C1B2_LAYOUT
    }
    for (role, _leaf), state in zip(
        _ROOT_C1B2_LAYOUT,
        _ROOT_C1B2_PHASES[phase],
    ):
        if state == "present":
            paths[role].write_bytes(b"{}\n")
            paths[role].chmod(0o444)
    return paths


@pytest.mark.parametrize("phase", tuple(_ROOT_C1B2_PHASES))
def test_root_c1b2_accepts_each_exact_transaction_phase(
    tmp_path: Path,
    phase: str,
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)
    authority = installer.H11RootRetainedAuthority.open(
        manifest_path, require_root=False
    )
    try:
        assert installer._H11_TRANSACTION_LAYOUT == _ROOT_C1B2_LAYOUT
        assert installer._H11_TRANSACTION_PHASES == _ROOT_C1B2_PHASES
        _materialize_root_c1b2_phase(authority, phase)
        rows = authority.validate_transaction_phase(phase)
        scenario_root = authority.directories[3].reference.path
        assert [row.reference for row in rows] == [
            {
                "role": role,
                "path": str(scenario_root / leaf),
                "state": state,
            }
            for (role, leaf), state in zip(
                _ROOT_C1B2_LAYOUT,
                _ROOT_C1B2_PHASES[phase],
            )
        ]
    finally:
        authority.close()


def test_root_c1b2_rejects_unknown_phase_before_leaf_lookup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)
    authority = installer.H11RootRetainedAuthority.open(
        manifest_path, require_root=False
    )
    leaf_lookups: list[object] = []
    revalidations: list[bool] = []

    def unexpected_stat(*args: object, **kwargs: object) -> os.stat_result:
        leaf_lookups.append((args, kwargs))
        raise AssertionError("unknown phase reached a filesystem lookup")

    monkeypatch.setattr(os, "stat", unexpected_stat)
    monkeypatch.setattr(
        authority,
        "revalidate",
        lambda *, require_root: revalidations.append(require_root),
    )
    try:
        with pytest.raises(installer.InstallerError, match="outside the exact phase"):
            authority.validate_transaction_phase("unknown-phase")
        assert leaf_lookups == []
        assert revalidations == []
    finally:
        authority.close()


@pytest.mark.parametrize("phase", tuple(_ROOT_C1B2_PHASES))
def test_root_c1b2_rejects_each_wrong_transaction_state_bit(
    tmp_path: Path,
    phase: str,
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)
    authority = installer.H11RootRetainedAuthority.open(
        manifest_path, require_root=False
    )
    try:
        paths = _materialize_root_c1b2_phase(authority, phase)
        for (role, _leaf), expected_state in zip(
            _ROOT_C1B2_LAYOUT,
            _ROOT_C1B2_PHASES[phase],
        ):
            path = paths[role]
            if expected_state == "absent":
                path.write_bytes(b"{}\n")
                path.chmod(0o444)
            else:
                path.unlink()
            with pytest.raises(installer.InstallerError, match="state differs"):
                authority.validate_transaction_phase(phase)
            if expected_state == "absent":
                path.unlink()
            else:
                path.write_bytes(b"{}\n")
                path.chmod(0o444)
    finally:
        authority.close()


@pytest.mark.parametrize(
    "mutation",
    (
        "symlink",
        "directory",
        "fifo",
        "mode",
        "owner",
        "transaction-inode-alias",
        "retained-source-alias",
    ),
)
def test_root_c1b2_rejects_invalid_present_transaction_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)
    authority = installer.H11RootRetainedAuthority.open(
        manifest_path, require_root=False
    )
    paths = _materialize_root_c1b2_phase(authority, "authorizer-input")
    target = paths["authorization"]
    ready = paths["permit-ready"]
    try:
        if mutation != "owner":
            target.unlink()
        if mutation == "symlink":
            target.symlink_to(manifest_path)
        elif mutation == "directory":
            target.mkdir(mode=0o700)
        elif mutation == "fifo":
            os.mkfifo(target, 0o600)
        elif mutation == "mode":
            target.write_bytes(b"{}\n")
            target.chmod(0o644)
        elif mutation == "transaction-inode-alias":
            os.link(ready, target)
        elif mutation == "retained-source-alias":
            os.link(manifest_path, target)
        else:
            original_stat = os.stat

            def wrong_owner_stat(
                path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
                *args: object,
                **kwargs: object,
            ) -> os.stat_result | SimpleNamespace:
                info = original_stat(path, *args, **kwargs)
                if (
                    os.fsdecode(path) == "AUTHORIZE-RELEASE.json"
                    and kwargs.get("dir_fd")
                    == authority.directories[3].descriptor
                ):
                    return SimpleNamespace(
                        st_mode=info.st_mode,
                        st_dev=info.st_dev,
                        st_ino=info.st_ino,
                        st_uid=info.st_uid + 1,
                        st_gid=info.st_gid,
                    )
                return info

            monkeypatch.setattr(os, "stat", wrong_owner_stat)
        expected = (
            "retained source"
            if mutation == "retained-source-alias"
            else "present transaction inodes alias"
            if mutation == "transaction-inode-alias"
            else "type/mode/owner"
        )
        with pytest.raises(installer.InstallerError, match=expected):
            authority.validate_transaction_phase("authorizer-input")
    finally:
        authority.close()


def test_root_c1b2_non_enoent_leaf_error_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)
    authority = installer.H11RootRetainedAuthority.open(
        manifest_path, require_root=False
    )
    original_stat = os.stat

    def denied_leaf_stat(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        *args: object,
        **kwargs: object,
    ) -> os.stat_result:
        if (
            os.fsdecode(path) == "AUTHORIZE-RELEASE.json"
            and kwargs.get("dir_fd") == authority.directories[3].descriptor
        ):
            raise PermissionError("injected transaction authority denial")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(os, "stat", denied_leaf_stat)
    try:
        with pytest.raises(
            installer.InstallerError, match="cannot validate.*AUTHORIZE"
        ) as caught:
            authority.validate_transaction_phase("pre-start")
        assert isinstance(caught.value.__cause__, PermissionError)
    finally:
        authority.close()


def test_root_c1b2_uses_seven_ordered_relative_leaf_lookups(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)
    authority = installer.H11RootRetainedAuthority.open(
        manifest_path, require_root=False
    )
    original_stat = os.stat
    calls: list[tuple[str, int | None, bool | None]] = []

    def recording_stat(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        *args: object,
        **kwargs: object,
    ) -> os.stat_result:
        if kwargs.get("dir_fd") == authority.directories[3].descriptor:
            leaf = os.fsdecode(path)
            if leaf in {item[1] for item in _ROOT_C1B2_LAYOUT}:
                calls.append(
                    (leaf, kwargs.get("dir_fd"), kwargs.get("follow_symlinks"))
                )
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(os, "stat", recording_stat)
    try:
        authority.validate_transaction_phase("pre-start")
        assert calls == [
            (leaf, authority.directories[3].descriptor, False)
            for _role, leaf in _ROOT_C1B2_LAYOUT
        ]
    finally:
        authority.close()


@pytest.mark.parametrize("mutation", ("move-away-replacement", "closed"))
def test_root_c1b2_rejects_replaced_or_closed_retained_scenario_directory(
    tmp_path: Path,
    mutation: str,
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)
    authority = installer.H11RootRetainedAuthority.open(
        manifest_path, require_root=False
    )
    scenario = authority.directories[3]
    try:
        if mutation == "move-away-replacement":
            displaced = scenario.reference.path.with_name("H11-displaced")
            scenario.reference.path.rename(displaced)
            scenario.reference.path.mkdir(mode=0o700)
        else:
            os.close(scenario.descriptor)
            scenario.descriptor = -1
        with pytest.raises(
            installer.InstallerError, match="cannot revalidate|drifted|closed"
        ):
            authority.validate_transaction_phase("pre-start")
    finally:
        authority.close()


def test_root_c1b2_validator_ast_uses_only_retained_dirfd_nofollow_stat() -> None:
    source = inspect.getsource(installer.H11RootRetainedAuthority)
    tree = ast.parse(source)
    method = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "validate_transaction_phase"
    )
    stat_calls = [
        node
        for node in ast.walk(method)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "os"
        and node.func.attr == "stat"
    ]
    assert len(stat_calls) == 1
    assert isinstance(stat_calls[0].args[0], ast.Name)
    assert stat_calls[0].args[0].id == "leaf"
    keywords = {item.arg: item.value for item in stat_calls[0].keywords}
    assert "dir_fd" in keywords
    assert isinstance(keywords["dir_fd"], ast.Attribute)
    assert keywords["dir_fd"].attr == "descriptor"
    assert isinstance(keywords["dir_fd"].value, ast.Name)
    assert keywords["dir_fd"].value.id == "scenario_directory"
    assert isinstance(keywords.get("follow_symlinks"), ast.Constant)
    assert keywords["follow_symlinks"].value is False
    assert not any(
        isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == "open")
            or (
                isinstance(node.func, ast.Attribute)
                and node is not stat_calls[0]
                and node.func.attr in {"open", "exists", "lstat", "stat", "access"}
            )
        )
        for node in ast.walk(method)
    )


_ROOT_C1C_EXACT_PAIRS = {
    "PERMIT_READY.pending": "PERMIT_READY.json",
    "PERMIT.pending": "PERMIT.json",
    "PERMIT-LEDGER.pending": "PERMIT-LEDGER.json",
}


@pytest.mark.parametrize(
    ("staging_name", "final_name"),
    tuple(_ROOT_C1C_EXACT_PAIRS.items()),
)
def test_root_c1c_publishes_each_exact_pair_and_retains_final_inode(
    tmp_path: Path,
    staging_name: str,
    final_name: str,
) -> None:
    assert installer._H11_PUBLICATION_PAIRS == _ROOT_C1C_EXACT_PAIRS
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)
    authority = installer.H11RootRetainedAuthority.open(
        manifest_path, require_root=False
    )
    parent = authority.directories[3]
    publication = installer._publish_h11_named_staging(
        parent,
        staging_name,
        final_name,
        {"schema": "scion.test.h11-publication.v1", "name": final_name},
        require_root=False,
    )
    descriptor = publication.descriptor
    try:
        assert not (parent.reference.path / staging_name).exists()
        assert (parent.reference.path / final_name).read_bytes() == publication.raw
        assert set(publication.reference) == {
            "path",
            "sha256",
            "device",
            "inode",
            "mode",
            "uid",
            "gid",
        }
        assert publication.reference["path"] == str(
            parent.reference.path / final_name
        )
        publication.revalidate()
    finally:
        publication.close()
        authority.close()
    with pytest.raises(OSError):
        os.fstat(descriptor)


def test_root_c1c_existing_pending_sentinel_is_unchanged_by_o_excl(
    tmp_path: Path,
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)
    authority = installer.H11RootRetainedAuthority.open(
        manifest_path, require_root=False
    )
    parent = authority.directories[3]
    pending = parent.reference.path / "PERMIT.pending"
    sentinel = b"preexisting-poison\n"
    pending.write_bytes(sentinel)
    pending.chmod(0o444)
    before = pending.lstat()
    try:
        with pytest.raises(FileExistsError) as error:
            installer._publish_h11_named_staging(
                parent,
                "PERMIT.pending",
                "PERMIT.json",
                {"must": "not-write"},
                require_root=False,
            )
        assert error.value.errno == errno.EEXIST
        after = pending.lstat()
        assert (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino)
        assert pending.read_bytes() == sentinel
        assert not (parent.reference.path / "PERMIT.json").exists()
    finally:
        authority.close()


def test_root_c1c_duplicate_publication_is_no_replace_and_poisoned(
    tmp_path: Path,
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)
    authority = installer.H11RootRetainedAuthority.open(
        manifest_path, require_root=False
    )
    parent = authority.directories[3]
    first = installer._publish_h11_named_staging(
        parent,
        "PERMIT.pending",
        "PERMIT.json",
        {"ordinal": "1"},
        require_root=False,
    )
    try:
        with pytest.raises(installer.InstallerError, match="no-replace"):
            installer._publish_h11_named_staging(
                parent,
                "PERMIT.pending",
                "PERMIT.json",
                {"ordinal": "2"},
                require_root=False,
            )
        assert (parent.reference.path / "PERMIT.json").read_bytes() == first.raw
        assert (parent.reference.path / "PERMIT.pending").is_file()
        first.revalidate()
    finally:
        first.close()
        authority.close()


def test_root_c1c_rename_failure_is_not_retried_or_cleaned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)
    authority = installer.H11RootRetainedAuthority.open(
        manifest_path, require_root=False
    )
    parent = authority.directories[3]
    opened = _capture_root_c1c_staging_descriptor(
        monkeypatch,
        parent_descriptor=parent.descriptor,
        staging_name="PERMIT.pending",
    )
    calls = 0

    class FailingRenameAt2:
        argtypes: Any = None
        restype: Any = None

        def __call__(self, *args: Any) -> int:
            nonlocal calls
            calls += 1
            installer.ctypes.set_errno(errno.EIO)
            return -1

    class FailingLibc:
        renameat2 = FailingRenameAt2()

    monkeypatch.setattr(installer.ctypes, "CDLL", lambda *args, **kwargs: FailingLibc())
    try:
        with pytest.raises(installer.InstallerError, match="cannot publish no-replace"):
            installer._publish_h11_named_staging(
                parent,
                "PERMIT.pending",
                "PERMIT.json",
                {"failure": "rename"},
                require_root=False,
            )
        assert calls == 1
        assert (parent.reference.path / "PERMIT.pending").is_file()
        assert not (parent.reference.path / "PERMIT.json").exists()
        _assert_root_c1c_descriptors_closed(opened)
    finally:
        authority.close()


def _capture_root_c1c_staging_descriptor(
    monkeypatch: pytest.MonkeyPatch,
    *,
    parent_descriptor: int,
    staging_name: str,
) -> list[int]:
    original_open = os.open
    opened: list[int] = []

    def recording_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        descriptor = (
            original_open(path, flags, mode)
            if dir_fd is None
            else original_open(path, flags, mode, dir_fd=dir_fd)
        )
        if os.fsdecode(path) == staging_name and dir_fd == parent_descriptor:
            opened.append(descriptor)
        return descriptor

    monkeypatch.setattr(os, "open", recording_open)
    return opened


def _assert_root_c1c_descriptors_closed(opened: list[int]) -> None:
    assert len(opened) == 1
    with pytest.raises(OSError):
        os.fstat(opened[0])


def test_root_c1c_pre_rename_failure_poison_pending_and_closes_fd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)
    authority = installer.H11RootRetainedAuthority.open(
        manifest_path, require_root=False
    )
    parent = authority.directories[3]
    opened = _capture_root_c1c_staging_descriptor(
        monkeypatch,
        parent_descriptor=parent.descriptor,
        staging_name="PERMIT.pending",
    )
    try:
        with pytest.raises(
            installer.InstallerError, match="failure before rename"
        ):
            installer._publish_h11_named_staging(
                parent,
                "PERMIT.pending",
                "PERMIT.json",
                {"failure": "pre-rename"},
                require_root=False,
                _test_failure="pre-rename",
            )
        assert (parent.reference.path / "PERMIT.pending").is_file()
        assert not (parent.reference.path / "PERMIT.json").exists()
        _assert_root_c1c_descriptors_closed(opened)
    finally:
        authority.close()


@pytest.mark.parametrize("failure", ("readback", "mode", "owner"))
def test_root_c1c_real_readback_or_staging_metadata_failure_poison_pending(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)
    authority = installer.H11RootRetainedAuthority.open(
        manifest_path, require_root=False
    )
    parent = authority.directories[3]
    opened = _capture_root_c1c_staging_descriptor(
        monkeypatch,
        parent_descriptor=parent.descriptor,
        staging_name="PERMIT_READY.pending",
    )
    original_read = os.read
    original_fstat = os.fstat
    corrupted = False

    def faulting_read(descriptor: int, count: int) -> bytes:
        nonlocal corrupted
        data = original_read(descriptor, count)
        if (
            failure == "readback"
            and opened
            and descriptor == opened[0]
            and data
            and not corrupted
        ):
            corrupted = True
            return bytes((data[0] ^ 1,)) + data[1:]
        return data

    def faulting_fstat(descriptor: int) -> os.stat_result | SimpleNamespace:
        info = original_fstat(descriptor)
        if opened and descriptor == opened[0] and failure in {"mode", "owner"}:
            return SimpleNamespace(
                st_mode=(
                    (info.st_mode & ~0o777) | 0o644
                    if failure == "mode"
                    else info.st_mode
                ),
                st_size=info.st_size,
                st_dev=info.st_dev,
                st_ino=info.st_ino,
                st_uid=info.st_uid + (1 if failure == "owner" else 0),
                st_gid=info.st_gid,
            )
        return info

    monkeypatch.setattr(os, "read", faulting_read)
    monkeypatch.setattr(os, "fstat", faulting_fstat)
    try:
        with pytest.raises(installer.InstallerError, match="readback or metadata"):
            installer._publish_h11_named_staging(
                parent,
                "PERMIT_READY.pending",
                "PERMIT_READY.json",
                {"failure": failure},
                require_root=False,
            )
        assert (parent.reference.path / "PERMIT_READY.pending").is_file()
        assert not (parent.reference.path / "PERMIT_READY.json").exists()
        _assert_root_c1c_descriptors_closed(opened)
    finally:
        authority.close()


def test_root_c1c_real_parent_fsync_failure_poison_final_and_closes_fd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)
    authority = installer.H11RootRetainedAuthority.open(
        manifest_path, require_root=False
    )
    parent = authority.directories[3]
    opened = _capture_root_c1c_staging_descriptor(
        monkeypatch,
        parent_descriptor=parent.descriptor,
        staging_name="PERMIT.pending",
    )
    original_fsync = os.fsync
    injected = OSError(errno.EIO, "injected parent fsync failure")

    def faulting_fsync(descriptor: int) -> None:
        if descriptor == parent.descriptor:
            raise injected
        original_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", faulting_fsync)
    try:
        with pytest.raises(OSError) as error:
            installer._publish_h11_named_staging(
                parent,
                "PERMIT.pending",
                "PERMIT.json",
                {"failure": "parent-fsync"},
                require_root=False,
            )
        assert error.value is injected
        assert not (parent.reference.path / "PERMIT.pending").exists()
        assert (parent.reference.path / "PERMIT.json").is_file()
        _assert_root_c1c_descriptors_closed(opened)
    finally:
        authority.close()


@pytest.mark.parametrize("failure", ("identity", "owner"))
def test_root_c1c_real_final_proof_failure_poison_final_and_closes_fd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)
    authority = installer.H11RootRetainedAuthority.open(
        manifest_path, require_root=False
    )
    parent = authority.directories[3]
    opened = _capture_root_c1c_staging_descriptor(
        monkeypatch,
        parent_descriptor=parent.descriptor,
        staging_name="PERMIT-LEDGER.pending",
    )
    original_stat = os.stat

    def faulting_stat(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        *args: object,
        **kwargs: object,
    ) -> os.stat_result | SimpleNamespace:
        info = original_stat(path, *args, **kwargs)
        if (
            os.fsdecode(path) == "PERMIT-LEDGER.json"
            and kwargs.get("dir_fd") == parent.descriptor
            and kwargs.get("follow_symlinks") is False
        ):
            return SimpleNamespace(
                st_mode=info.st_mode,
                st_dev=info.st_dev,
                st_ino=info.st_ino + (1 if failure == "identity" else 0),
                st_uid=info.st_uid + (1 if failure == "owner" else 0),
                st_gid=info.st_gid,
            )
        return info

    monkeypatch.setattr(os, "stat", faulting_stat)
    try:
        with pytest.raises(installer.InstallerError, match="retained inode"):
            installer._publish_h11_named_staging(
                parent,
                "PERMIT-LEDGER.pending",
                "PERMIT-LEDGER.json",
                {"failure": failure},
                require_root=False,
            )
        assert not (parent.reference.path / "PERMIT-LEDGER.pending").exists()
        assert (parent.reference.path / "PERMIT-LEDGER.json").is_file()
        _assert_root_c1c_descriptors_closed(opened)
    finally:
        authority.close()


def test_root_c1c_revalidate_rejects_same_byte_final_replacement(
    tmp_path: Path,
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)
    authority = installer.H11RootRetainedAuthority.open(
        manifest_path, require_root=False
    )
    parent = authority.directories[3]
    publication = installer._publish_h11_named_staging(
        parent,
        "PERMIT-LEDGER.pending",
        "PERMIT-LEDGER.json",
        {"ledger": "same-bytes"},
        require_root=False,
    )
    final_path = parent.reference.path / "PERMIT-LEDGER.json"
    displaced = final_path.with_name("PERMIT-LEDGER.displaced")
    try:
        final_path.rename(displaced)
        final_path.write_bytes(publication.raw)
        final_path.chmod(0o444)
        with pytest.raises(installer.InstallerError, match="drifted"):
            publication.revalidate()
    finally:
        publication.close()
        authority.close()


@pytest.mark.parametrize(
    ("staging_name", "final_name"),
    (
        ("PERMIT.pending", "PERMIT_READY.json"),
        ("UNKNOWN.pending", "PERMIT.json"),
        ("PERMIT.pending/child", "PERMIT.json"),
    ),
)
def test_root_c1c_rejects_nonexact_leaf_pair_before_mutation(
    tmp_path: Path,
    staging_name: str,
    final_name: str,
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)
    authority = installer.H11RootRetainedAuthority.open(
        manifest_path, require_root=False
    )
    parent = authority.directories[3]
    try:
        with pytest.raises(installer.InstallerError, match="leaf pair"):
            installer._publish_h11_named_staging(
                parent,
                staging_name,
                final_name,
                {"invalid": True},
                require_root=False,
            )
        assert not any(
            path.name.startswith(("PERMIT", "UNKNOWN"))
            for path in parent.reference.path.iterdir()
            if path.name != "MANIFEST.json"
        )
    finally:
        authority.close()


def test_root_c1c_privileged_mode_rejects_test_injection_before_mutation(
    tmp_path: Path,
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)
    authority = installer.H11RootRetainedAuthority.open(
        manifest_path, require_root=False
    )
    parent = authority.directories[3]
    try:
        with pytest.raises(installer.InstallerError, match="forbids test"):
            installer._publish_h11_named_staging(
                parent,
                "PERMIT.pending",
                "PERMIT.json",
                {"invalid": True},
                require_root=True,
                _test_failure="pre-rename",
            )
        assert not (parent.reference.path / "PERMIT.pending").exists()
        assert not (parent.reference.path / "PERMIT.json").exists()
    finally:
        authority.close()


def test_root_c1c_syscall_order_and_same_fd_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, _sources = _root_c1a_authority_model(tmp_path)
    authority = installer.H11RootRetainedAuthority.open(
        manifest_path, require_root=False
    )
    parent = authority.directories[3]
    payload = {"schema": "scion.test.h11-order.v1"}
    expected_raw = _canonical(payload)
    events: list[tuple[Any, ...]] = []
    staging_descriptor = -1
    original_open = os.open
    original_write = os.write
    original_fchmod = os.fchmod
    original_lseek = os.lseek
    original_read = os.read
    original_fstat = os.fstat
    original_fsync = os.fsync
    original_stat = os.stat
    original_cdll = installer.ctypes.CDLL

    def spy_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal staging_descriptor
        descriptor = (
            original_open(path, flags, mode)
            if dir_fd is None
            else original_open(path, flags, mode, dir_fd=dir_fd)
        )
        if os.fsdecode(path) == "PERMIT.pending":
            staging_descriptor = descriptor
            events.append(("open", descriptor, flags, mode, dir_fd))
        return descriptor

    def spy_write(descriptor: int, data: bytes | memoryview) -> int:
        if descriptor == staging_descriptor:
            events.append(("write", descriptor, bytes(data)))
        return original_write(descriptor, data)

    def spy_fchmod(descriptor: int, mode: int) -> None:
        if descriptor == staging_descriptor:
            events.append(("fchmod", descriptor, mode))
        original_fchmod(descriptor, mode)

    def spy_lseek(descriptor: int, offset: int, whence: int) -> int:
        if descriptor == staging_descriptor:
            events.append(("lseek", descriptor, offset, whence))
        return original_lseek(descriptor, offset, whence)

    def spy_read(descriptor: int, count: int) -> bytes:
        data = original_read(descriptor, count)
        if descriptor == staging_descriptor:
            events.append(("read", descriptor, data))
        return data

    def spy_fstat(descriptor: int) -> os.stat_result:
        if descriptor == staging_descriptor:
            events.append(("fstat", descriptor))
        return original_fstat(descriptor)

    def spy_fsync(descriptor: int) -> None:
        if descriptor == staging_descriptor:
            events.append(("file-fsync", descriptor))
        elif descriptor == parent.descriptor:
            events.append(("parent-fsync", descriptor))
        original_fsync(descriptor)

    def spy_stat(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        *args: object,
        **kwargs: object,
    ) -> os.stat_result:
        if (
            os.fsdecode(path) == "PERMIT.json"
            and kwargs.get("dir_fd") == parent.descriptor
        ):
            events.append(
                (
                    "final-stat",
                    kwargs.get("dir_fd"),
                    kwargs.get("follow_symlinks"),
                )
            )
        return original_stat(path, *args, **kwargs)

    class RenameAt2Spy:
        def __init__(self, function: Any) -> None:
            self.function = function

        @property
        def argtypes(self) -> Any:
            return self.function.argtypes

        @argtypes.setter
        def argtypes(self, value: Any) -> None:
            self.function.argtypes = value

        @property
        def restype(self) -> Any:
            return self.function.restype

        @restype.setter
        def restype(self, value: Any) -> None:
            self.function.restype = value

        def __call__(self, *args: Any) -> int:
            events.append(("renameat2", *args))
            return int(self.function(*args))

    class LibcSpy:
        def __init__(self, library: Any) -> None:
            self.renameat2 = RenameAt2Spy(library.renameat2)

    def spy_cdll(*args: Any, **kwargs: Any) -> LibcSpy:
        return LibcSpy(original_cdll(*args, **kwargs))

    monkeypatch.setattr(os, "open", spy_open)
    monkeypatch.setattr(os, "write", spy_write)
    monkeypatch.setattr(os, "fchmod", spy_fchmod)
    monkeypatch.setattr(os, "lseek", spy_lseek)
    monkeypatch.setattr(os, "read", spy_read)
    monkeypatch.setattr(os, "fstat", spy_fstat)
    monkeypatch.setattr(os, "fsync", spy_fsync)
    monkeypatch.setattr(os, "stat", spy_stat)
    monkeypatch.setattr(installer.ctypes, "CDLL", spy_cdll)
    publication = installer._publish_h11_named_staging(
        parent,
        "PERMIT.pending",
        "PERMIT.json",
        payload,
        require_root=False,
    )
    try:
        names = [event[0] for event in events]
        assert names[:13] == [
            "open",
            "write",
            "fchmod",
            "lseek",
            "read",
            "read",
            "lseek",
            "fstat",
            "file-fsync",
            "renameat2",
            "parent-fsync",
            "final-stat",
            "fstat",
        ]
        opened = events[0]
        expected_flags = (
            os.O_RDWR
            | os.O_CREAT
            | os.O_EXCL
            | os.O_NOFOLLOW
            | os.O_CLOEXEC
        )
        assert opened[1:] == (
            staging_descriptor,
            expected_flags,
            0o444,
            parent.descriptor,
        )
        assert events[1] == ("write", staging_descriptor, expected_raw)
        assert events[2] == ("fchmod", staging_descriptor, 0o444)
        assert all(
            event[1] == staging_descriptor
            for event in events[:9]
            if event[0] not in {"open"}
        )
        rename = events[9]
        assert rename[1:] == (
            parent.descriptor,
            b"PERMIT.pending",
            parent.descriptor,
            b"PERMIT.json",
            1,
        )
        assert events[10] == ("parent-fsync", parent.descriptor)
        assert events[11] == ("final-stat", parent.descriptor, False)
    finally:
        publication.close()
        authority.close()


def test_root_c1c_publication_ast_closes_path_retry_and_callback_escape() -> None:
    wrapper_source = inspect.getsource(installer._publish_h11_named_staging)
    wrapper_tree = ast.parse(wrapper_source)
    signature = inspect.signature(installer._publish_h11_named_staging)
    assert tuple(signature.parameters) == (
        "parent",
        "staging_name",
        "final_name",
        "payload",
        "require_root",
        "_test_failure",
    )
    assert signature.parameters["require_root"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["_test_failure"].kind is inspect.Parameter.KEYWORD_ONLY
    wrapper_calls = [
        node.func.id
        for node in ast.walk(wrapper_tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert wrapper_calls == [
        "_prepare_h11_named_staging",
        "_open_h11_named_staging",
        "_complete_h11_named_staging",
    ]
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "os"
        for node in ast.walk(wrapper_tree)
    )

    open_source = inspect.getsource(installer._open_h11_named_staging)
    open_tree = ast.parse(open_source)
    open_calls = [
        node
        for node in ast.walk(open_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "os"
        and node.func.attr == "open"
    ]
    assert len(open_calls) == 1
    open_call = open_calls[0]
    assert isinstance(open_call.args[0], ast.Attribute)
    assert ast.unparse(open_call.args[0]) == "plan.staging_name"
    assert ast.unparse(open_call.args[1]) == (
        "os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC"
    )
    assert isinstance(open_call.args[2], ast.Constant)
    assert open_call.args[2].value == 0o444
    open_keywords = {item.arg: item.value for item in open_call.keywords}
    assert isinstance(open_keywords.get("dir_fd"), ast.Attribute)
    assert open_keywords["dir_fd"].attr == "descriptor"
    assert ast.unparse(open_keywords["dir_fd"]) == "plan.parent.descriptor"
    assert [
        ast.unparse(node.func)
        for node in ast.walk(open_tree)
        if isinstance(node, ast.Call)
    ] == ["os.open"]

    core_source = inspect.getsource(installer._complete_h11_named_staging)
    core_tree = ast.parse(core_source)
    rename_calls = [
        node
        for node in ast.walk(core_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "renameat2"
    ]
    assert len(rename_calls) == 1
    rename_call = rename_calls[0]
    assert len(rename_call.args) == 5
    assert ast.dump(rename_call.args[0]) == ast.dump(rename_call.args[2])
    assert isinstance(rename_call.args[4], ast.Constant)
    assert rename_call.args[4].value == 1
    parents = {
        child: parent
        for parent in ast.walk(core_tree)
        for child in ast.iter_child_nodes(parent)
    }
    ancestor = parents.get(rename_call)
    while ancestor is not None:
        assert not isinstance(ancestor, (ast.For, ast.AsyncFor, ast.While))
        ancestor = parents.get(ancestor)
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_publish_h11_named_staging"
        for node in ast.walk(core_tree)
    )
    assert not any(
        isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == "open")
            or (
                isinstance(node.func, ast.Attribute)
                and node.func.attr
                in {
                    "open",
                    "rename",
                    "replace",
                    "unlink",
                    "remove",
                    "removedirs",
                    "rmdir",
                    "rmtree",
                    "sleep",
                    "poll",
                    "exists",
                    "lstat",
                    "retry",
                }
            )
        )
        for node in ast.walk(core_tree)
    )
    assert not any(
        isinstance(node, ast.keyword)
        and node.arg in {"callback", "timeout", "deadline", "retry"}
        for node in ast.walk(core_tree)
    )


def _root_c2a_full_reference(path: Path) -> dict[str, str]:
    info = path.lstat()
    return {
        "path": str(path),
        "sha256": _sha(path),
        "device": str(info.st_dev),
        "inode": str(info.st_ino),
        "mode": format(stat.S_IMODE(info.st_mode), "04o"),
        "uid": str(info.st_uid),
        "gid": str(info.st_gid),
    }


def _root_c2a_write_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        path.chmod(0o644)
    _write(path, value)
    path.chmod(0o444)


def _root_c2a_session_model(
    tmp_path: Path, *, extra_ordinary_fifo: bool = False
) -> dict[str, Path]:
    ordinary_fifos = tuple(
        (f"{role}-{kind}", f"c2a-{role}-{kind}.fifo")
        for role in ("run-main", "exec-stop-post", "closer")
        for kind in ("ready", "release")
    )
    if extra_ordinary_fifo:
        ordinary_fifos += (("unused-extra", "c2a-unused-extra.fifo"),)
    manifest_path, sources = _root_c1a_authority_model(
        tmp_path, ordinary_fifos=ordinary_fifos
    )
    root = manifest_path.parents[3]
    scenario_root = manifest_path.parent
    work_root = root / "work"
    armed_path = work_root / "RUN-MAIN-ARMED.json"
    manifest = json.loads(manifest_path.read_text(encoding="ascii"))
    tree_receipt = json.loads(
        sources["tree_receipt"].read_text(encoding="ascii")
    )

    def acquisition_fifo(role: str, kind: str) -> dict[str, str]:
        row = next(
            item
            for item in tree_receipt["fifos"]
            if item["role"] == f"{role}-{kind}"
        )
        return {
            key: row[key] for key in ("path", "device", "inode")
        }

    acquisitions: list[dict[str, Any]] = []
    for role in ("run-main", "exec-stop-post", "closer"):
        acquisitions.append(
            {
                "role": role,
                "armed_receipt_path": str(
                    armed_path
                    if role == "run-main"
                    else work_root / f"{role}-ARMED.json"
                ),
                "ready_fifo": acquisition_fifo(role, "ready"),
                "release_fifo": acquisition_fifo(role, "release"),
            }
        )
    acquisition = acquisitions[0]
    manifest["acquisitions"] = acquisitions
    static_specs = (
        (
            "run-main",
            manifest["run_unit"],
            "adversary",
            "h11-unbounded-hold",
            root / "sealed" / "run-plan.json",
            root / "sealed" / "run-program.py",
        ),
        (
            "exec-stop-post",
            manifest["run_unit"],
            "observer",
            "exec-stop-post",
            root / "sealed" / "stop-plan.json",
            root / "sealed" / "stop-program.py",
        ),
        (
            "closer",
            manifest["closer_unit"],
            "observer",
            "closer",
            root / "sealed" / "close-plan.json",
            root / "sealed" / "close-program.py",
        ),
    )
    manifest["static_roles"] = [
        {
            "role": role,
            "unit": unit,
            "owner": owner,
            "mode": mode,
            "plan": {"path": str(plan_path), "sha256": _sha(plan_path)},
            "program": {
                "path": str(program_path),
                "sha256": _sha(program_path),
            },
        }
        for role, unit, owner, mode, plan_path, program_path in static_specs
    ]
    seal_receipt = json.loads(
        sources["seal_receipt"].read_text(encoding="ascii")
    )
    seal_rows = {row["role"]: row for row in seal_receipt["files"]}
    for field, role in (
        ("descriptor", "start-descriptor"),
        ("harness_program", "harness-program"),
        ("static_inventory", "preflight-manifest"),
    ):
        row = seal_rows[role]
        manifest[field] = {
            "path": row["path"],
            "sha256": row["sha256"],
        }
    _root_c2a_write_json(manifest_path, manifest)

    boot_id = "11111111-1111-1111-1111-111111111111"
    invocation_id = "a" * 32
    request_path = work_root / "c2a-request.json"
    _write(
        request_path,
        {
            "schema": "scion.generic_backend.systemd_adversary_request.v1",
            "scenario": "h11-unbounded-hold",
            "unit": manifest["run_unit"],
        },
    )
    request_path.chmod(0o600)
    run_plan = Path(manifest["static_roles"][0]["plan"]["path"])
    run_program = Path(manifest["static_roles"][0]["program"]["path"])
    program_info = run_program.lstat()
    armed = {
        "schema": "scion.generic_backend.systemd_adversary_armed.v1",
        "scenario": "h11-unbounded-hold",
        "unit": manifest["run_unit"],
        "actor": {
            "boot_id": boot_id,
            "invocation_id": invocation_id,
            "pid": 101,
            "proc_cgroup_raw": "0::/system.slice/c2a.scope\n",
            "session_id": 101,
            "starttime": 202,
            "stop_selector_environment": {},
            "unified_cgroup": "/system.slice/c2a.scope",
        },
        "plan_path": str(run_plan),
        "plan_sha256": _sha(run_plan),
        "program": {
            "path": str(run_program),
            "sha256": _sha(run_program),
            "identity": {
                "device": program_info.st_dev,
                "inode": program_info.st_ino,
                "mode": stat.S_IMODE(program_info.st_mode),
            },
        },
        "request_path": str(request_path),
        "request_sha256": _sha(request_path),
        "receipt_path": str(work_root / "c2a-receipt.json"),
        "ready_fifo": dict(acquisition["ready_fifo"]),
        "release_fifo": dict(acquisition["release_fifo"]),
        "ready_sha256": hashlib.sha256(
            b"SCION_GENERIC_BACKEND_READY_V1\n"
        ).hexdigest(),
        "release_sha256": hashlib.sha256(
            b"SCION_GENERIC_BACKEND_RELEASE_V1\n"
        ).hexdigest(),
    }
    _write(armed_path, armed)
    armed_path.chmod(0o600)

    ready_path = scenario_root / "PERMIT_READY.json"
    harness_reference = _root_c2a_full_reference(manifest_path)
    armed_reference = _root_c2a_full_reference(armed_path)
    present_outputs: list[dict[str, str]] = []
    output_by_role = {
        item["role"]: Path(item["path"])
        for item in manifest["outputs"]
    }
    for role in ("h0", "run-main-properties"):
        output_path = output_by_role[role]
        output_path.parent.chmod(0o755)
        _write(
            output_path,
            {
                "schema": "scion.test.h11-present-output.v1",
                "role": role,
            },
        )
        output_path.chmod(0o444)
        output_path.parent.chmod(0o555)
        present_outputs.append(
            {"role": role, **_root_c2a_full_reference(output_path)}
        )
    ready = {
        "schema": installer.H11_PERMIT_READY_SCHEMA,
        "scenario": "H11",
        "run_unit": manifest["run_unit"],
        "boot_id": boot_id,
        "invocation_id": invocation_id,
        "harness_manifest": harness_reference,
        "run_armed": armed_reference,
        "permit_authority": manifest["permit_authority"],
        "present_outputs": present_outputs,
        "absent_paths": manifest["permit_authority"]["future_absence_inventory"],
        "phase": "h11-permit-ready",
    }
    _root_c2a_write_json(ready_path, ready)

    authorization_path = scenario_root / "AUTHORIZE-RELEASE.json"
    authorization = {
        "schema": installer.H11_AUTHORIZATION_SCHEMA,
        "formal_root": str(root),
        "harness_manifest": harness_reference,
        "permit_ready": _root_c2a_full_reference(ready_path),
        "run_armed": armed_reference,
        "permit_path": str(scenario_root / "PERMIT.json"),
    }
    _root_c2a_write_json(authorization_path, authorization)
    return {
        "authorization": authorization_path,
        "manifest": manifest_path,
        "ready": ready_path,
        "armed": armed_path,
        "request": request_path,
        "run_plan": run_plan,
        "run_program": run_program,
        "h0": output_by_role["h0"],
        "run_main_properties": output_by_role["run-main-properties"],
        "ready_fifo": Path(acquisition["ready_fifo"]["path"]),
        "release_fifo": Path(acquisition["release_fifo"]["path"]),
    }


def _root_c2a_rebind_sources(paths: dict[str, Path]) -> None:
    ready = json.loads(paths["ready"].read_text(encoding="ascii"))
    ready["harness_manifest"] = _root_c2a_full_reference(paths["manifest"])
    ready["run_armed"] = _root_c2a_full_reference(paths["armed"])
    _root_c2a_write_json(paths["ready"], ready)
    authorization = json.loads(
        paths["authorization"].read_text(encoding="ascii")
    )
    authorization["harness_manifest"] = _root_c2a_full_reference(
        paths["manifest"]
    )
    authorization["permit_ready"] = _root_c2a_full_reference(paths["ready"])
    authorization["run_armed"] = _root_c2a_full_reference(paths["armed"])
    _root_c2a_write_json(paths["authorization"], authorization)


def _root_c2a_run_public_authorization_flow(
    paths: dict[str, Path],
) -> tuple[
    installer.H11RootAuthorizationFlow,
    installer.H11RootCommitReceipt,
    tuple[bytes, ...],
]:
    frames: list[bytes] = []
    errors: list[BaseException] = []
    peer = threading.Thread(
        target=_root_c2d_public_fifo_peer,
        args=(paths, frames, errors),
    )
    peer.start()
    flow = installer.H11RootAuthorizationFlow(
        paths["authorization"],
        require_root=False,
    )
    try:
        receipt = flow.authorize_once()
    finally:
        flow.close()
    peer.join()
    assert errors == []
    return flow, receipt, tuple(frames)


def _root_c2a_run_public_pre_ready_rejection(
    paths: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    *,
    authorization_path: Path | None = None,
    error_match: str | None = None,
) -> tuple[str, ...]:
    original_open = os.open
    opened_paths: list[str] = []

    def guarded_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        decoded = os.fsdecode(path)
        observed = Path(decoded)
        if dir_fd is not None and not observed.is_absolute():
            observed = Path(os.readlink(f"/proc/self/fd/{dir_fd}")) / observed
        opened_paths.append(str(observed))
        if (
            decoded.startswith("/proc/self/fd/")
            and flags & os.O_ACCMODE == os.O_RDONLY
            and not flags & os.O_PATH
        ):
            raise AssertionError(
                "pre-READY rejection reached the blocking READY FIFO open"
            )
        return (
            original_open(path, flags, mode)
            if dir_fd is None
            else original_open(path, flags, mode, dir_fd=dir_fd)
        )

    monkeypatch.setattr(os, "open", guarded_open)
    flow = installer.H11RootAuthorizationFlow(
        authorization_path or paths["authorization"],
        require_root=False,
    )
    with pytest.raises(installer.InstallerError, match=error_match):
        flow.authorize_once()
    assert flow.state is installer.H11RootAuthorizationState.FAILED_PREWRITE
    assert not (paths["authorization"].parent / "PERMIT.pending").exists()
    assert not (paths["authorization"].parent / "PERMIT.json").exists()
    return tuple(opened_paths)


def test_root_c2a_public_flow_accepts_exact_read_only_authority(
    tmp_path: Path,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    flow, receipt, frames = _root_c2a_run_public_authorization_flow(paths)
    assert flow.state is installer.H11RootAuthorizationState.COMPLETE
    assert frames == (installer.H11_PERMIT_COMMITTED_BYTES,)
    assert receipt.phase == "permit-committed"
    assert receipt.fifo.path == (
        paths["authorization"].parents[3]
        / "fifo"
        / "h11-permit-committed.fifo"
    )
    assert receipt.payload_sha256 == hashlib.sha256(
        installer.H11_PERMIT_COMMITTED_BYTES
    ).hexdigest()
    assert receipt.byte_count == str(len(installer.H11_PERMIT_COMMITTED_BYTES))
    assert receipt.reference == {
        "schema": installer.H11_COMMIT_FIFO_RECEIPT_SCHEMA,
        "phase": "permit-committed",
        "fifo": receipt.fifo.reference,
        "payload_sha256": hashlib.sha256(
            installer.H11_PERMIT_COMMITTED_BYTES
        ).hexdigest(),
        "byte_count": str(len(installer.H11_PERMIT_COMMITTED_BYTES)),
    }


def test_root_c2a_does_not_open_static_plan_program_or_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    authority = installer.H11RootRetainedAuthority.open(
        paths["manifest"], require_root=False
    )
    monkeypatch.setattr(
        installer.H11RootRetainedAuthority,
        "open",
        classmethod(
            lambda cls, manifest_path, *, require_root=True: authority
        ),
    )
    forbidden = {paths["run_plan"], paths["run_program"], paths["request"]}
    original_open = os.open
    forbidden_opens: list[Path] = []

    def recording_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        decoded = Path(os.fsdecode(path))
        if dir_fd is None and decoded in forbidden:
            forbidden_opens.append(decoded)
        return (
            original_open(path, flags, mode)
            if dir_fd is None
            else original_open(path, flags, mode, dir_fd=dir_fd)
        )

    monkeypatch.setattr(os, "open", recording_open)
    session = installer.H11RootAuthorizerSession.open(
        paths["authorization"], require_root=False
    )
    session.close()
    assert forbidden_opens == []


@pytest.mark.parametrize(
    "mutation",
    (
        "missing-key",
        "extra-key",
        "short-reference",
        "wrong-root",
        "wrong-permit-path",
    ),
)
def test_root_c2a_rejects_authorization_schema_reference_or_layout_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    authorization = json.loads(paths["authorization"].read_text())
    if mutation == "missing-key":
        authorization.pop("permit_ready")
    elif mutation == "extra-key":
        authorization["extra"] = True
    elif mutation == "short-reference":
        authorization["harness_manifest"].pop("uid")
        authorization["harness_manifest"].pop("gid")
    elif mutation == "wrong-root":
        authorization["formal_root"] = str(tmp_path / "wrong-root")
    else:
        authorization["permit_path"] = str(tmp_path / "wrong-permit.json")
    _root_c2a_write_json(paths["authorization"], authorization)
    _root_c2a_run_public_pre_ready_rejection(paths, monkeypatch)


def test_root_c2a_rejects_authorization_outside_exact_scenario_layout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    wrong = paths["authorization"].with_name("WRONG-AUTHORIZE.json")
    wrong.write_bytes(paths["authorization"].read_bytes())
    wrong.chmod(0o444)
    _root_c2a_run_public_pre_ready_rejection(
        paths,
        monkeypatch,
        authorization_path=wrong,
        error_match="authorization path",
    )


def test_root_c2a_rejects_caller_selected_run_armed_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    decoy = paths["armed"].with_name("CALLER-SELECTED-ARMED.json")
    decoy.write_bytes(paths["armed"].read_bytes())
    decoy.chmod(0o600)
    decoy_reference = _root_c2a_full_reference(decoy)
    ready = json.loads(paths["ready"].read_text())
    ready["run_armed"] = decoy_reference
    _root_c2a_write_json(paths["ready"], ready)
    authorization = json.loads(paths["authorization"].read_text())
    authorization["run_armed"] = decoy_reference
    authorization["permit_ready"] = _root_c2a_full_reference(paths["ready"])
    _root_c2a_write_json(paths["authorization"], authorization)
    _root_c2a_run_public_pre_ready_rejection(
        paths,
        monkeypatch,
        error_match="cannot select",
    )


def test_root_c2a_rejects_decoy_ready_before_any_decoy_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    decoy = paths["ready"].with_name("DECOY-PERMIT_READY.json")
    decoy.write_bytes(paths["ready"].read_bytes())
    decoy.chmod(0o444)
    authorization = json.loads(paths["authorization"].read_text())
    authorization["permit_ready"] = _root_c2a_full_reference(decoy)
    _root_c2a_write_json(paths["authorization"], authorization)
    opened_paths = _root_c2a_run_public_pre_ready_rejection(
        paths,
        monkeypatch,
        error_match="PERMIT_READY path",
    )
    assert str(decoy) not in opened_paths


@pytest.mark.parametrize(
    "mutation",
    (
        "missing",
        "reordered",
        "extra-acquisition",
        "duplicate-run-main",
        "fifo-identity",
        "extra-field",
        "commit-fifo-alias",
    ),
)
def test_root_c2a_rejects_wrong_acquisition_tuple_or_fifo_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    manifest = json.loads(paths["manifest"].read_text())
    acquisitions = manifest["acquisitions"]
    if mutation == "missing":
        acquisitions.pop()
    elif mutation == "reordered":
        acquisitions[0], acquisitions[1] = acquisitions[1], acquisitions[0]
    elif mutation == "extra-acquisition":
        acquisitions.append(dict(acquisitions[-1]))
    elif mutation == "duplicate-run-main":
        acquisitions[1]["role"] = "run-main"
    elif mutation == "fifo-identity":
        acquisitions[0]["ready_fifo"]["inode"] = "1"
    elif mutation == "extra-field":
        acquisitions[0]["extra"] = True
    else:
        acquisitions[0]["ready_fifo"] = {
            key: manifest["permit_authority"]["ready_commit_fifo"][key]
            for key in ("path", "device", "inode")
        }
    _root_c2a_write_json(paths["manifest"], manifest)
    _root_c2a_rebind_sources(paths)
    _root_c2a_run_public_pre_ready_rejection(
        paths,
        monkeypatch,
        error_match="acquisition",
    )


def test_root_c2a_rejects_extra_tree_fifo_outside_closed_acquisitions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _root_c2a_session_model(tmp_path, extra_ordinary_fifo=True)
    _root_c2a_run_public_pre_ready_rejection(
        paths,
        monkeypatch,
        error_match="TREE/PREFLIGHT FIFO inventory drifted",
    )


@pytest.mark.parametrize(
    "mutation",
    (
        "missing",
        "reordered",
        "extra",
        "program-none",
        "program-nested-extra",
        "wrong-plan-bind",
        "wrong-program-bind",
    ),
)
def test_root_c2a_rejects_static_role_or_run_binding_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    manifest = json.loads(paths["manifest"].read_text())
    static_roles = manifest["static_roles"]
    if mutation == "missing":
        static_roles.pop()
    elif mutation == "reordered":
        static_roles[0], static_roles[1] = static_roles[1], static_roles[0]
    elif mutation == "extra":
        static_roles.append(dict(static_roles[-1]))
    elif mutation == "program-none":
        static_roles[0]["program"] = None
    elif mutation == "program-nested-extra":
        static_roles[0]["program"]["extra"] = True
    elif mutation == "wrong-plan-bind":
        static_roles[0]["plan"] = dict(static_roles[1]["plan"])
    else:
        static_roles[0]["program"] = dict(static_roles[1]["program"])
    _root_c2a_write_json(paths["manifest"], manifest)
    _root_c2a_rebind_sources(paths)
    _root_c2a_run_public_pre_ready_rejection(
        paths,
        monkeypatch,
        error_match="static",
    )


@pytest.mark.parametrize(
    ("index", "field", "value"),
    (
        (1, "unit", "scion-w3-wrong-stop.service"),
        (1, "owner", "adversary"),
        (1, "mode", "closer"),
        (2, "unit", "scion-w3-wrong-closer.service"),
        (2, "owner", "formal"),
        (2, "mode", "exec-stop-post"),
    ),
)
def test_root_c2a_rejects_literal_stop_and_closer_static_tuple_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    index: int,
    field: str,
    value: str,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    manifest = json.loads(paths["manifest"].read_text())
    manifest["static_roles"][index][field] = value
    _root_c2a_write_json(paths["manifest"], manifest)
    _root_c2a_rebind_sources(paths)
    _root_c2a_run_public_pre_ready_rejection(
        paths,
        monkeypatch,
        error_match="static role tuple",
    )


def test_root_c2a_rejects_coherent_closer_unit_rebind_from_preflight_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    manifest = json.loads(paths["manifest"].read_text())
    manifest["closer_unit"] = manifest["run_unit"]
    manifest["static_roles"][2]["unit"] = manifest["run_unit"]
    _root_c2a_write_json(paths["manifest"], manifest)
    _root_c2a_rebind_sources(paths)
    _root_c2a_run_public_pre_ready_rejection(
        paths,
        monkeypatch,
        error_match="preflight receipt",
    )


@pytest.mark.parametrize(
    "mutation",
    (
        "missing-present-outputs",
        "extra-key",
        "schema",
        "scenario",
        "unit",
        "permit-authority-crossbind",
    ),
)
def test_root_c2a_rejects_ready_schema_or_crossbind_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    ready = json.loads(paths["ready"].read_text())
    if mutation == "missing-present-outputs":
        ready.pop("present_outputs")
    elif mutation == "extra-key":
        ready["extra"] = True
    elif mutation == "schema":
        ready["schema"] = "scion.test.wrong.v1"
    elif mutation == "scenario":
        ready["scenario"] = "H10"
    elif mutation == "unit":
        ready["run_unit"] = "scion-w3-wrong.service"
    else:
        ready["permit_authority"] = {"wrong": True}
    _root_c2a_write_json(paths["ready"], ready)
    _root_c2a_rebind_sources(paths)
    with pytest.raises(installer.InstallerError):
        installer.H11RootAuthorizerSession.open(
            paths["authorization"], require_root=False
        )


@pytest.mark.parametrize(
    "mutation",
    (
        "missing-key",
        "schema",
        "scenario",
        "unit",
        "actor-extra",
        "actor-boot",
        "stop-environment",
        "cgroup-noncanonical",
        "cgroup-raw",
        "ready-fifo",
        "release-fifo",
        "program-none",
        "program-extra",
        "program-identity-extra",
        "program-mode-text",
        "program-path-bind",
        "plan-path-bind",
        "plan-sha",
        "request-type",
        "request-sha",
        "ready-digest",
        "release-digest",
    ),
)
def test_root_c2a_rejects_armed_schema_actor_or_fifo_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    armed = json.loads(paths["armed"].read_text())
    if mutation == "missing-key":
        armed.pop("request_sha256")
    elif mutation == "schema":
        armed["schema"] = "scion.test.wrong-armed.v1"
    elif mutation == "scenario":
        armed["scenario"] = "h10-gc-negative"
    elif mutation == "unit":
        armed["unit"] = "scion-w3-wrong.service"
    elif mutation == "actor-extra":
        armed["actor"]["extra"] = True
    elif mutation == "actor-boot":
        armed["actor"]["boot_id"] = "22222222-2222-2222-2222-222222222222"
    elif mutation == "stop-environment":
        armed["actor"]["stop_selector_environment"] = {"INVOCATION_ID": "a" * 32}
    elif mutation == "cgroup-noncanonical":
        armed["actor"]["unified_cgroup"] = "/system.slice//c2a.scope"
        armed["actor"]["proc_cgroup_raw"] = "0::/system.slice//c2a.scope\n"
    elif mutation == "cgroup-raw":
        armed["actor"]["proc_cgroup_raw"] = "0::/wrong.scope\n"
    elif mutation in {"ready-fifo", "release-fifo"}:
        armed[mutation.replace("-", "_")]["inode"] = "1"
    elif mutation == "program-none":
        armed["program"] = None
    elif mutation == "program-extra":
        armed["program"]["extra"] = True
    elif mutation == "program-identity-extra":
        armed["program"]["identity"]["extra"] = 1
    elif mutation == "program-mode-text":
        armed["program"]["identity"]["mode"] = "0444"
    elif mutation == "program-path-bind":
        armed["program"]["path"] = str(paths["run_plan"])
    elif mutation == "plan-path-bind":
        armed["plan_path"] = str(paths["run_program"])
    elif mutation == "plan-sha":
        armed["plan_sha256"] = "A" * 64
    elif mutation == "request-type":
        armed["request_path"] = 1
    elif mutation == "request-sha":
        armed["request_sha256"] = "f" * 63
    elif mutation == "ready-digest":
        armed["ready_sha256"] = "f" * 64
    else:
        armed["release_sha256"] = "e" * 64
    paths["armed"].chmod(0o600)
    _write(paths["armed"], armed)
    paths["armed"].chmod(0o600)
    _root_c2a_rebind_sources(paths)
    with pytest.raises(installer.InstallerError):
        installer.H11RootAuthorizerSession.open(
            paths["authorization"], require_root=False
        )


def test_root_c2a_rejects_pinned_armed_owner_outside_fixture_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    original_pin = installer._pin_h11_json_source

    def wrong_owner_pin(*args: Any, **kwargs: Any) -> tuple[Any, ...]:
        result = original_pin(*args, **kwargs)
        if kwargs.get("label") == "H11 run ARMED":
            source = dict(result[3])
            source["uid"] = str(int(source["uid"]) + 1)
            result = (*result[:3], source)
        return result

    monkeypatch.setattr(installer, "_pin_h11_json_source", wrong_owner_pin)
    with pytest.raises(installer.InstallerError, match="ARMED owner"):
        installer.H11RootAuthorizerSession.open(
            paths["authorization"], require_root=False
        )


def test_root_c2a_rejects_authorizer_regular_source_inode_alias(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    original_pin = installer._pin_h11_json_source
    authorization_identity: tuple[str, str] | None = None

    def aliasing_pin(*args: Any, **kwargs: Any) -> tuple[Any, ...]:
        nonlocal authorization_identity
        result = original_pin(*args, **kwargs)
        label = kwargs.get("label")
        if label == "H11 authorization manifest":
            authorization_identity = (result[3]["device"], result[3]["inode"])
        elif label == "H11 PERMIT_READY":
            assert authorization_identity is not None
            source = dict(result[3])
            source["device"], source["inode"] = authorization_identity
            result = (*result[:3], source)
        return result

    monkeypatch.setattr(installer, "_pin_h11_json_source", aliasing_pin)
    with pytest.raises(installer.InstallerError, match="regular source aliases"):
        installer.H11RootAuthorizerSession.open(
            paths["authorization"], require_root=False
        )


@pytest.mark.parametrize(
    "mutation",
    ("armed-output", "request-transaction", "static-plan-transaction"),
)
def test_root_c2a_rejects_global_path_authority_alias(
    tmp_path: Path,
    mutation: str,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    manifest = json.loads(paths["manifest"].read_text())
    armed = json.loads(paths["armed"].read_text())
    if mutation == "armed-output":
        manifest["acquisitions"][1]["armed_receipt_path"] = manifest["outputs"][0][
            "path"
        ]
    elif mutation == "request-transaction":
        armed["request_path"] = manifest["permit_authority"]["permit_staging_path"]
    else:
        manifest["static_roles"][1]["plan"] = {
            "path": manifest["permit_authority"]["permit_ledger_staging_path"],
            "sha256": "f" * 64,
        }
    _root_c2a_write_json(paths["manifest"], manifest)
    paths["armed"].chmod(0o600)
    _write(paths["armed"], armed)
    paths["armed"].chmod(0o600)
    _root_c2a_rebind_sources(paths)
    with pytest.raises(installer.InstallerError, match="path authority aliases"):
        installer.H11RootAuthorizerSession.open(
            paths["authorization"], require_root=False
        )


@pytest.mark.parametrize("mutation", ("armed", "request"))
def test_root_c2a_rejects_frozen_root_alias_from_runtime_authority(
    tmp_path: Path,
    mutation: str,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    manifest = json.loads(paths["manifest"].read_text())
    frozen_root = paths["manifest"].parents[3] / "frozen"
    if mutation == "armed":
        manifest["acquisitions"][1]["armed_receipt_path"] = str(frozen_root)
        _root_c2a_write_json(paths["manifest"], manifest)
    else:
        armed = json.loads(paths["armed"].read_text())
        armed["request_path"] = str(frozen_root)
        paths["armed"].chmod(0o600)
        _write(paths["armed"], armed)
        paths["armed"].chmod(0o600)
    _root_c2a_rebind_sources(paths)
    with pytest.raises(installer.InstallerError, match="frozen-root"):
        installer.H11RootAuthorizerSession.open(
            paths["authorization"], require_root=False
        )


@pytest.mark.parametrize("source", ("authorization", "manifest", "ready", "armed"))
def test_root_c2a_revalidate_rejects_same_byte_source_replacement(
    tmp_path: Path,
    source: str,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    session = installer.H11RootAuthorizerSession.open(
        paths["authorization"], require_root=False
    )
    path = paths[source]
    displaced = path.with_name(f"{path.name}.displaced")
    raw = path.read_bytes()
    mode = stat.S_IMODE(path.lstat().st_mode)
    path.rename(displaced)
    path.write_bytes(raw)
    path.chmod(mode)
    try:
        with pytest.raises(installer.InstallerError, match="revalidate|drifted"):
            session.revalidate()
    finally:
        session.close()


@pytest.mark.parametrize("failure", ("manifest", "ready", "armed"))
def test_root_c2a_partial_open_failure_rolls_back_every_descriptor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    target = {
        "manifest": "MANIFEST.json",
        "ready": "PERMIT_READY.json",
        "armed": "RUN-MAIN-ARMED.json",
    }[failure]
    original_open = os.open
    opened: list[int] = []

    def failing_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        if Path(os.fsdecode(path)).name == target:
            raise OSError("injected C2a pin failure")
        descriptor = (
            original_open(path, flags, mode)
            if dir_fd is None
            else original_open(path, flags, mode, dir_fd=dir_fd)
        )
        opened.append(descriptor)
        return descriptor

    monkeypatch.setattr(os, "open", failing_open)
    with pytest.raises(installer.InstallerError, match="cannot pin") as error:
        installer.H11RootAuthorizerSession.open(
            paths["authorization"], require_root=False
        )
    assert isinstance(error.value.__cause__, OSError)
    assert "injected C2a" in str(error.value.__cause__)
    assert opened
    for descriptor in opened:
        with pytest.raises(OSError):
            os.fstat(descriptor)
    assert not (paths["authorization"].parent / "PERMIT.json").exists()


def _root_c2b_ready_fifo(
    session: installer.H11RootAuthorizerSession,
) -> installer.RetainedH11RootFifo:
    matches = tuple(
        item
        for item in session.authority.commit_fifos
        if item.role == "h11-ready-commit"
    )
    assert len(matches) == 1
    return matches[0]


def _root_c2b_write_ready_frame(
    fifo: installer.RetainedH11RootFifo,
    payload: bytes,
    entered: threading.Event,
    errors: list[BaseException],
) -> None:
    entered.set()
    descriptor = -1
    try:
        descriptor = os.open(
            f"/proc/self/fd/{fifo.descriptor}",
            os.O_WRONLY | os.O_CLOEXEC,
        )
        fifo.reference.prove(
            os.fstat(descriptor),
            require_root=False,
            label="test H11 READY commit writer",
        )
        if payload and os.write(descriptor, payload) != len(payload):
            raise AssertionError("test READY frame write was incomplete")
    except BaseException as exc:
        errors.append(exc)
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _root_c2b_consume_with_writer(
    paths: dict[str, Path],
    *,
    payload: bytes = installer.H11_READY_COMMITTED_BYTES,
) -> installer.H11RootAuthorizerReadyClosure:
    session = installer.H11RootAuthorizerSession.open(
        paths["authorization"], require_root=False
    )
    entered = threading.Event()
    errors: list[BaseException] = []
    writer = threading.Thread(
        target=_root_c2b_write_ready_frame,
        args=(_root_c2b_ready_fifo(session), payload, entered, errors),
    )
    writer.start()
    entered.wait()
    try:
        result = installer.H11RootAuthorizerReadyClosure.consume(session)
    finally:
        writer.join()
    assert errors == []
    return result


@pytest.mark.parametrize("first_endpoint", ("reader", "writer"))
def test_root_c2b_consumes_ready_commit_in_either_blocking_schedule(
    tmp_path: Path,
    first_endpoint: str,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    session = installer.H11RootAuthorizerSession.open(
        paths["authorization"], require_root=False
    )
    fifo = _root_c2b_ready_fifo(session)
    entered = threading.Event()
    errors: list[BaseException] = []
    result: dict[str, Any] = {}

    def consume() -> None:
        entered.set()
        try:
            result["closure"] = installer.H11RootAuthorizerReadyClosure.consume(
                session
            )
        except BaseException as exc:
            errors.append(exc)

    if first_endpoint == "reader":
        worker = threading.Thread(target=consume)
        worker.start()
        entered.wait()
        _root_c2b_write_ready_frame(
            fifo,
            installer.H11_READY_COMMITTED_BYTES,
            threading.Event(),
            errors,
        )
        worker.join()
        closure = result["closure"]
    else:
        worker = threading.Thread(
            target=_root_c2b_write_ready_frame,
            args=(
                fifo,
                installer.H11_READY_COMMITTED_BYTES,
                entered,
                errors,
            ),
        )
        worker.start()
        entered.wait()
        closure = installer.H11RootAuthorizerReadyClosure.consume(session)
        worker.join()
    assert errors == []
    try:
        assert closure.ready_commit.reference == {
            "schema": "scion.generic_backend.h11_commit_fifo_receipt.v1",
            "phase": "ready-committed",
            "fifo": fifo.reference.reference,
            "payload_sha256": hashlib.sha256(
                b"SCION_H11_READY_COMMITTED_V1\n"
            ).hexdigest(),
            "byte_count": str(len(b"SCION_H11_READY_COMMITTED_V1\n")),
        }
        assert [item["role"] for item in closure.present_outputs] == [
            "h0",
            "run-main-properties",
        ]
        assert [
            item["role"] for item in closure.future_absence_inventory
        ] == [
            "closer-properties",
            "exec-stop-post-properties",
            "final",
            "final-closer-properties",
            "final-run-properties",
            "frozen-root",
            "h12-absence",
            "journal",
            "manager-events",
            "signals",
            "source-selector",
        ]
        literal_present = (
            json.dumps(
                closure.present_outputs,
                ensure_ascii=True,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("ascii")
        literal_future = (
            json.dumps(
                closure.future_absence_inventory,
                ensure_ascii=True,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("ascii")
        assert closure.present_outputs_sha256 == hashlib.sha256(
            literal_present
        ).hexdigest()
        assert closure.future_absence_sha256 == hashlib.sha256(
            literal_future
        ).hexdigest()
        exposed_present = closure.present_outputs
        exposed_present[0]["role"] = "caller-mutated-copy"
        exposed_commit = closure.ready_commit.reference
        exposed_commit["fifo"]["inode"] = "1"
        assert closure.present_outputs[0]["role"] == "h0"
        assert closure.ready_commit.reference["fifo"] == fifo.reference.reference
        closure.revalidate()
    finally:
        descriptors = [
            *(item.descriptor for item in closure.present_sources),
            closure.session.authorization.descriptor,
            closure.session.permit_ready.descriptor,
            closure.session.run_armed.descriptor,
        ]
        closure.close()
    assert closure.closed is True
    assert all(item.descriptor == -1 for item in closure.present_sources)
    for descriptor in descriptors:
        with pytest.raises(OSError):
            os.fstat(descriptor)


@pytest.mark.parametrize("primary_site", ("fstat", "read"))
def test_root_c2b_reader_primary_survives_endpoint_close_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    primary_site: str,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    session = installer.H11RootAuthorizerSession.open(
        paths["authorization"], require_root=False
    )
    fifo = _root_c2b_ready_fifo(session)
    peer_entered = threading.Event()
    release_peer = threading.Event()
    peer_errors: list[BaseException] = []
    real_open = os.open
    real_close = os.close
    real_fstat = os.fstat
    real_read = os.read

    def hold_writer() -> None:
        descriptor = -1
        peer_entered.set()
        try:
            descriptor = real_open(
                f"/proc/self/fd/{fifo.descriptor}",
                os.O_WRONLY | os.O_CLOEXEC,
            )
            release_peer.wait()
        except BaseException as exc:
            peer_errors.append(exc)
        finally:
            if descriptor >= 0:
                real_close(descriptor)

    peer = threading.Thread(target=hold_writer)
    peer.start()
    peer_entered.wait()
    reader_descriptor = -1
    close_counts: dict[int, int] = {}
    primary_error = OSError(
        errno.EIO,
        f"injected READY reader {primary_site} failure",
    )
    close_error = OSError(errno.EBADF, "injected READY reader close failure")

    def capture_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        nonlocal reader_descriptor
        descriptor = real_open(path, flags, *args, **kwargs)
        if (
            os.fsdecode(path) == f"/proc/self/fd/{fifo.descriptor}"
            and flags == os.O_RDONLY | os.O_CLOEXEC
        ):
            reader_descriptor = descriptor
        return descriptor

    def failing_fstat(descriptor: int) -> os.stat_result:
        if primary_site == "fstat" and descriptor == reader_descriptor:
            raise primary_error
        return real_fstat(descriptor)

    def failing_read(descriptor: int, size: int) -> bytes:
        if primary_site == "read" and descriptor == reader_descriptor:
            raise primary_error
        return real_read(descriptor, size)

    def close_then_fail(descriptor: int) -> None:
        close_counts[descriptor] = close_counts.get(descriptor, 0) + 1
        real_close(descriptor)
        if descriptor == reader_descriptor:
            raise close_error

    monkeypatch.setattr(os, "open", capture_open)
    monkeypatch.setattr(os, "fstat", failing_fstat)
    monkeypatch.setattr(os, "read", failing_read)
    monkeypatch.setattr(os, "close", close_then_fail)
    result: dict[str, installer.H11RootCommitReceipt] = {}
    try:
        with pytest.raises(OSError) as caught:
            result["receipt"] = fifo.read_ready_commit(require_root=False)
    finally:
        release_peer.set()
        peer.join()
    assert caught.value is primary_error
    assert result == {}
    assert peer_errors == []
    assert primary_error.__notes__ == [
        "H11 ownership teardown secondary: "
        f"{type(close_error).__name__}: {close_error}"
    ]
    assert close_counts[reader_descriptor] == 1
    with pytest.raises(OSError):
        real_fstat(reader_descriptor)
    session.close()


def test_root_c2b_reader_eof_close_failure_is_primary_without_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    session = installer.H11RootAuthorizerSession.open(
        paths["authorization"], require_root=False
    )
    fifo = _root_c2b_ready_fifo(session)
    entered = threading.Event()
    peer_errors: list[BaseException] = []
    peer = threading.Thread(
        target=_root_c2b_write_ready_frame,
        args=(fifo, installer.H11_READY_COMMITTED_BYTES, entered, peer_errors),
    )
    peer.start()
    entered.wait()
    real_open = os.open
    real_close = os.close
    real_fstat = os.fstat
    real_read = os.read
    reader_descriptor = -1
    close_counts: dict[int, int] = {}
    reads: list[bytes] = []
    close_error = OSError(errno.EIO, "injected READY reader EOF close failure")

    def capture_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        nonlocal reader_descriptor
        descriptor = real_open(path, flags, *args, **kwargs)
        if (
            os.fsdecode(path) == f"/proc/self/fd/{fifo.descriptor}"
            and flags == os.O_RDONLY | os.O_CLOEXEC
        ):
            reader_descriptor = descriptor
        return descriptor

    def recording_read(descriptor: int, size: int) -> bytes:
        chunk = real_read(descriptor, size)
        if descriptor == reader_descriptor:
            reads.append(chunk)
        return chunk

    def close_then_fail(descriptor: int) -> None:
        close_counts[descriptor] = close_counts.get(descriptor, 0) + 1
        real_close(descriptor)
        if descriptor == reader_descriptor:
            raise close_error

    monkeypatch.setattr(os, "open", capture_open)
    monkeypatch.setattr(os, "read", recording_read)
    monkeypatch.setattr(os, "close", close_then_fail)
    result: dict[str, installer.H11RootCommitReceipt] = {}
    with pytest.raises(OSError) as caught:
        result["receipt"] = fifo.read_ready_commit(require_root=False)
    peer.join()
    assert caught.value is close_error
    assert result == {}
    assert peer_errors == []
    assert reads[-1] == b""
    assert b"".join(reads[:-1]) == installer.H11_READY_COMMITTED_BYTES
    assert getattr(close_error, "__notes__", []) == []
    assert close_counts[reader_descriptor] == 1
    with pytest.raises(OSError):
        real_fstat(reader_descriptor)
    session.close()


@pytest.mark.parametrize(
    "payload",
    (
        b"",
        b"SCION_H11_READY_COMMITTED_V1",
        b"SCION_H11_READY_COMMITTED_V1\nX",
        b"SCION_H11_READY_COMMITTED_V1\nSCION_H11_READY_COMMITTED_V1\n",
    ),
)
def test_root_c2b_rejects_missing_wrong_or_duplicate_ready_frame(
    tmp_path: Path,
    payload: bytes,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    session = installer.H11RootAuthorizerSession.open(
        paths["authorization"], require_root=False
    )
    entered = threading.Event()
    errors: list[BaseException] = []
    writer = threading.Thread(
        target=_root_c2b_write_ready_frame,
        args=(_root_c2b_ready_fifo(session), payload, entered, errors),
    )
    writer.start()
    entered.wait()
    with pytest.raises(installer.InstallerError, match="frame differs"):
        installer.H11RootAuthorizerReadyClosure.consume(session)
    writer.join()
    assert errors == []
    assert session.authorization.descriptor == -1


@pytest.mark.parametrize(
    "mutation",
    (
        "present-missing",
        "present-extra",
        "present-reordered",
        "present-duplicate",
        "present-wrong-role",
        "future-missing",
        "future-extra",
        "future-reordered",
        "future-duplicate",
        "future-wrong-path",
    ),
)
def test_root_c2b_rejects_ready_partition_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    ready = json.loads(paths["ready"].read_text())
    present = ready["present_outputs"]
    future = ready["absent_paths"]
    if mutation == "present-missing":
        present.pop()
    elif mutation == "present-extra":
        present.append(dict(present[-1]))
    elif mutation == "present-reordered":
        present.reverse()
    elif mutation == "present-duplicate":
        present[1] = dict(present[0])
    elif mutation == "present-wrong-role":
        present[0]["role"] = "signals"
    elif mutation == "future-missing":
        future.pop()
    elif mutation == "future-extra":
        future.append({"role": "extra", "path": str(tmp_path / "extra")})
    elif mutation == "future-reordered":
        future.reverse()
    elif mutation == "future-duplicate":
        future[1] = dict(future[0])
    else:
        future[0]["path"] = str(tmp_path / "wrong-future")
    _root_c2a_write_json(paths["ready"], ready)
    _root_c2a_rebind_sources(paths)
    with pytest.raises(installer.InstallerError, match="partition|2-present"):
        _root_c2b_consume_with_writer(paths)


def test_root_c2b_rejects_omitted_future_role_even_when_it_exists(
    tmp_path: Path,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    ready = json.loads(paths["ready"].read_text())
    omitted = ready["absent_paths"].pop(0)
    omitted_path = Path(omitted["path"])
    omitted_path.parent.chmod(0o755)
    _write(omitted_path, {"schema": "scion.test.unexpected-future.v1"})
    omitted_path.chmod(0o444)
    omitted_path.parent.chmod(0o555)
    _root_c2a_write_json(paths["ready"], ready)
    _root_c2a_rebind_sources(paths)
    with pytest.raises(installer.InstallerError, match="2-present/11-future"):
        _root_c2b_consume_with_writer(paths)


@pytest.mark.parametrize(
    ("role", "mutation"),
    (
        ("h0", "missing"),
        ("run-main-properties", "missing"),
        ("h0", "mode"),
        ("run-main-properties", "owner-reference"),
        ("h0", "same-byte-replacement"),
        ("h0", "missing-key"),
        ("run-main-properties", "extra-key"),
        ("h0", "symlink"),
    ),
)
def test_root_c2b_rejects_present_source_absence_metadata_or_replacement(
    tmp_path: Path,
    role: str,
    mutation: str,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    ready = json.loads(paths["ready"].read_text())
    reference = next(
        item for item in ready["present_outputs"] if item["role"] == role
    )
    path = Path(reference["path"])
    if mutation == "missing":
        path.parent.chmod(0o755)
        path.unlink()
        path.parent.chmod(0o555)
    elif mutation == "mode":
        path.chmod(0o644)
    elif mutation == "owner-reference":
        reference["uid"] = str(int(reference["uid"]) + 1)
        _root_c2a_write_json(paths["ready"], ready)
        _root_c2a_rebind_sources(paths)
    elif mutation == "missing-key":
        reference.pop("sha256")
        _root_c2a_write_json(paths["ready"], ready)
        _root_c2a_rebind_sources(paths)
    elif mutation == "extra-key":
        reference["extra"] = True
        _root_c2a_write_json(paths["ready"], ready)
        _root_c2a_rebind_sources(paths)
    elif mutation == "symlink":
        raw = path.read_bytes()
        target = path.with_name(path.name + ".symlink-target")
        path.parent.chmod(0o755)
        path.rename(target)
        path.symlink_to(target.name)
        target.chmod(0o444)
        path.parent.chmod(0o555)
        assert target.read_bytes() == raw
    else:
        raw = path.read_bytes()
        displaced = path.with_name(path.name + ".displaced")
        path.parent.chmod(0o755)
        path.rename(displaced)
        path.write_bytes(raw)
        path.chmod(0o444)
        path.parent.chmod(0o555)
    with pytest.raises(installer.InstallerError):
        _root_c2b_consume_with_writer(paths)


@pytest.mark.parametrize("source_name", ("authorization", "ready"))
def test_root_c2b_binds_same_byte_transaction_leaf_to_retained_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_name: str,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    session = installer.H11RootAuthorizerSession.open(
        paths["authorization"], require_root=False
    )
    retained = (
        session.authorization
        if source_name == "authorization"
        else session.permit_ready
    )
    raw = retained.path.read_bytes()
    displaced = retained.path.with_name(retained.path.name + ".bound-displaced")
    retained.path.rename(displaced)
    retained.path.write_bytes(raw)
    retained.path.chmod(0o444)
    monkeypatch.setattr(retained, "revalidate", lambda: None)
    entered = threading.Event()
    errors: list[BaseException] = []
    writer = threading.Thread(
        target=_root_c2b_write_ready_frame,
        args=(
            _root_c2b_ready_fifo(session),
            installer.H11_READY_COMMITTED_BYTES,
            entered,
            errors,
        ),
    )
    writer.start()
    entered.wait()
    with pytest.raises(installer.InstallerError, match="leaf identity"):
        installer.H11RootAuthorizerReadyClosure.consume(session)
    writer.join()
    assert errors == []


def test_root_c2b_revalidate_rejects_same_byte_present_replacement(
    tmp_path: Path,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    closure = _root_c2b_consume_with_writer(paths)
    source = closure.present_sources[0]
    raw = source.path.read_bytes()
    displaced = source.path.with_name(source.path.name + ".after-commit")
    source.path.parent.chmod(0o755)
    source.path.rename(displaced)
    source.path.write_bytes(raw)
    source.path.chmod(0o444)
    source.path.parent.chmod(0o555)
    try:
        with pytest.raises(installer.InstallerError, match="drifted"):
            closure.revalidate()
    finally:
        closure.poison()
    assert closure.poisoned is True
    assert closure.closed is True


def test_root_c2b_rejects_present_output_inode_alias(tmp_path: Path) -> None:
    paths = _root_c2a_session_model(tmp_path)
    ready = json.loads(paths["ready"].read_text())
    h0 = next(item for item in ready["present_outputs"] if item["role"] == "h0")
    run = next(
        item
        for item in ready["present_outputs"]
        if item["role"] == "run-main-properties"
    )
    run_path = Path(run["path"])
    run_path.parent.chmod(0o755)
    run_path.unlink()
    os.link(Path(h0["path"]), run_path)
    run_path.parent.chmod(0o555)
    run.update(
        {
            "sha256": _sha(run_path),
            "device": str(run_path.lstat().st_dev),
            "inode": str(run_path.lstat().st_ino),
        }
    )
    _root_c2a_write_json(paths["ready"], ready)
    _root_c2a_rebind_sources(paths)
    with pytest.raises(installer.InstallerError, match="identities alias"):
        _root_c2b_consume_with_writer(paths)


def test_root_c2b_rejects_present_output_hardlink_to_retained_source(
    tmp_path: Path,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    ready = json.loads(paths["ready"].read_text())
    h0_index = next(
        index
        for index, item in enumerate(ready["present_outputs"])
        if item["role"] == "h0"
    )
    h0_path = Path(ready["present_outputs"][h0_index]["path"])
    h0_path.parent.chmod(0o755)
    h0_path.unlink()
    os.link(paths["manifest"], h0_path)
    h0_path.parent.chmod(0o555)
    ready["present_outputs"][h0_index] = {
        "role": "h0",
        **_root_c2a_full_reference(h0_path),
    }
    _root_c2a_write_json(paths["ready"], ready)
    _root_c2a_rebind_sources(paths)
    with pytest.raises(
        installer.InstallerError,
        match="identities alias retained authority",
    ):
        _root_c2b_consume_with_writer(paths)


@pytest.mark.parametrize(
    "role",
    (
        "permit-ready-staging",
        "permit-staging",
        "permit",
        "permit-ledger-staging",
        "permit-ledger",
    ),
)
def test_root_c2b_rejects_each_wrong_absent_authorizer_phase_bit(
    tmp_path: Path,
    role: str,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    scenario = paths["authorization"].parent
    leaf = dict(_ROOT_C1B2_LAYOUT)[role]
    path = scenario / leaf
    _root_c2a_write_json(path, {"schema": "scion.test.wrong-phase.v1"})
    with pytest.raises(installer.InstallerError, match="state differs"):
        _root_c2b_consume_with_writer(paths)


def test_root_c2b_partial_present_pin_failure_closes_every_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    session = installer.H11RootAuthorizerSession.open(
        paths["authorization"], require_root=False
    )
    session_descriptors = [
        session.authorization.descriptor,
        session.permit_ready.descriptor,
        session.run_armed.descriptor,
        session.authority.manifest_descriptor,
    ]
    original_open = os.open
    pinned_present: list[int] = []

    def failing_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        leaf = os.fsdecode(path)
        if leaf == paths["run_main_properties"].name and dir_fd is not None:
            raise OSError("injected C2b second present pin failure")
        descriptor = (
            original_open(path, flags, mode)
            if dir_fd is None
            else original_open(path, flags, mode, dir_fd=dir_fd)
        )
        if leaf == paths["h0"].name and dir_fd is not None:
            pinned_present.append(descriptor)
        return descriptor

    monkeypatch.setattr(os, "open", failing_open)
    entered = threading.Event()
    errors: list[BaseException] = []
    writer = threading.Thread(
        target=_root_c2b_write_ready_frame,
        args=(
            _root_c2b_ready_fifo(session),
            installer.H11_READY_COMMITTED_BYTES,
            entered,
            errors,
        ),
    )
    writer.start()
    entered.wait()
    with pytest.raises(installer.InstallerError, match="cannot pin") as caught:
        installer.H11RootAuthorizerReadyClosure.consume(session)
    writer.join()
    assert errors == []
    assert isinstance(caught.value.__cause__, OSError)
    assert "injected C2b" in str(caught.value.__cause__)
    assert pinned_present
    for descriptor in (*session_descriptors, *pinned_present):
        with pytest.raises(OSError):
            os.fstat(descriptor)


def test_root_c2b_ast_closes_mutation_publication_and_wait_escape() -> None:
    fifo_source = inspect.getsource(installer.RetainedH11RootFifo)
    fifo_tree = ast.parse(fifo_source)
    assert "O_NONBLOCK" not in fifo_source
    assert "timeout" not in fifo_source
    assert "poll" not in fifo_source
    assert "sleep" not in fifo_source
    fifo_class = next(
        node for node in fifo_tree.body if isinstance(node, ast.ClassDef)
    )
    fifo_methods = {
        node.name: node
        for node in fifo_class.body
        if isinstance(node, ast.FunctionDef)
    }
    reader = fifo_methods["read_ready_commit"]
    writer = fifo_methods["open_permit_commit_writer"]
    for endpoint in (reader, writer):
        assert not any(
            isinstance(node, ast.Try)
            and any(
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and ast.unparse(child.func) == "os.close"
                for statement in node.finalbody
                for child in ast.walk(statement)
            )
            for node in ast.walk(endpoint)
        )
    reader_open_calls = [
        node
        for node in ast.walk(reader)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "os"
        and node.func.attr == "open"
    ]
    assert len(reader_open_calls) == 1
    open_call = reader_open_calls[0]
    assert len(open_call.args) == 2
    assert open_call.keywords == []
    expected_descriptor_path = ast.parse(
        'f"/proc/self/fd/{self.descriptor}"', mode="eval"
    ).body
    assert ast.dump(open_call.args[0]) == ast.dump(expected_descriptor_path)
    assert [
        ast.unparse(node.value)
        for node in ast.walk(open_call.args[0])
        if isinstance(node, ast.FormattedValue)
    ] == ["self.descriptor"]
    flags = ast.unparse(open_call.args[1])
    assert flags == "os.O_RDONLY | os.O_CLOEXEC"
    reader_try = next(
        node for node in reader.body if isinstance(node, ast.Try)
    )
    reader_close_index = next(
        index
        for index, node in enumerate(reader_try.body)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and ast.unparse(node.value.func) == "os.close"
    )
    assert [
        ast.unparse(node)
        for node in reader_try.body[reader_close_index - 2 : reader_close_index + 1]
    ] == [
        "closing_descriptor = descriptor",
        "descriptor = -1",
        "os.close(closing_descriptor)",
    ]
    writer_calls = [
        node
        for node in ast.walk(writer)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "os"
    ]
    assert [node.func.attr for node in writer_calls] == ["open", "fstat"]
    writer_open = writer_calls[0]
    assert ast.dump(writer_open.args[0]) == ast.dump(expected_descriptor_path)
    assert ast.unparse(writer_open.args[1]) == (
        "os.O_WRONLY | os.O_CLOEXEC"
    )
    assert writer_open.keywords == []
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"read", "write", "writev"}
        for node in ast.walk(writer)
    )

    sources = "\n".join(
        (
            fifo_source,
            *(
                inspect.getsource(item)
                for item in (
                    installer.H11RootCommitReceipt,
                    installer.RetainedH11RootPresentOutput,
                    installer._bind_h11_authorizer_transaction_sources,
                    installer.H11RootAuthorizerReadyClosure,
                )
            ),
        )
    )
    tree = ast.parse(sources)
    assert not any(
        token in sources
        for token in (
            "O_NONBLOCK",
            "timeout",
            "deadline",
            "retry",
            "callback",
            "budget",
            "cap",
            "truncate",
            "truncation",
            "cleanup",
            "watchdog",
            "poll",
            "sleep",
            "authorize_h11_release",
            "_publish_h11",
            "write_commit",
            "H11_RELEASE_BYTES",
        )
    )
    direct_name_calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert direct_name_calls == {
        "InstallerError",
        "_bind_h11_authorizer_transaction_sources",
        "_canonical",
        "_close_h11_ownership",
        "_exact",
        "_fail",
        "_path",
        "_text",
        "_uint",
        "any",
        "cls",
        "dataclass",
        "dict",
        "enumerate",
        "format",
        "len",
        "reversed",
        "set",
        "sorted",
        "str",
        "tuple",
        "type",
        "zip",
    }
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr
        in {
            "write",
            "write_bytes",
            "write_text",
            "retry",
            "fsync",
            "fdatasync",
            "ftruncate",
            "truncate",
            "fchmod",
            "fchown",
            "mkdir",
            "unlink",
            "rename",
            "replace",
            "remove",
            "rmdir",
            "chmod",
            "chown",
            "link",
            "symlink",
        }
        for node in ast.walk(tree)
    )


def test_root_c2c_publishes_exact_permit_and_retains_owner_lifecycle(
    tmp_path: Path,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    closure = _root_c2b_consume_with_writer(paths)
    retained_ready = json.loads(closure.session.permit_ready.raw.decode("ascii"))
    permit = installer.H11RootAuthorizedPermit.publish(closure)
    publication_descriptor = permit.publication.descriptor
    try:
        payload = json.loads(permit.publication.raw.decode("ascii"))
        assert set(payload) == {
            "schema",
            "scenario",
            "run_unit",
            "boot_id",
            "invocation_id",
            "authorization_manifest",
            "harness_manifest",
            "permit_ready",
            "run_armed",
            "ready_commit",
            "present_outputs_sha256",
            "future_absence_sha256",
            "phase",
        }
        expected_payload = {
            "schema": installer.H11_PERMIT_SCHEMA,
            "scenario": "H11",
            "run_unit": retained_ready["run_unit"],
            "boot_id": retained_ready["boot_id"],
            "invocation_id": retained_ready["invocation_id"],
            "authorization_manifest": closure.session.authorization.source,
            "harness_manifest": closure.session.authority.manifest_source,
            "permit_ready": closure.session.permit_ready.source,
            "run_armed": closure.session.run_armed.source,
            "ready_commit": closure.ready_commit.reference,
            "present_outputs_sha256": closure.present_outputs_sha256,
            "future_absence_sha256": closure.future_absence_sha256,
            "phase": "operator-release-authorized",
        }
        assert payload == expected_payload
        expected_raw = (
            json.dumps(
                expected_payload,
                ensure_ascii=True,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("ascii")
        assert permit.publication.raw == expected_raw
        assert permit.publication.reference["path"] == str(
            paths["authorization"].parent / "PERMIT.json"
        )
        assert permit.publication.descriptor >= 0
        assert permit.barrier.directory_chain == tuple(
            item.reference for item in closure.session.authority.directories
        )
        assert permit.barrier.transaction_state == closure.transaction_state
        assert permit.barrier.present_outputs_sha256 == (
            closure.present_outputs_sha256
        )
        assert permit.barrier.future_absence_sha256 == (
            closure.future_absence_sha256
        )
        assert [item.state for item in permit.transaction_state] == [
            "present",
            "absent",
            "present",
            "absent",
            "present",
            "absent",
            "absent",
        ]
        permit.revalidate()
    finally:
        permit.close()
    assert permit.closed is True
    assert permit.publication.descriptor == -1
    assert closure.closed is True
    with pytest.raises(OSError):
        os.fstat(publication_descriptor)


@pytest.mark.parametrize(
    ("field", "cache_only_value"),
    (
        ("run_unit", "scion-w3-cache-only.service"),
        ("boot_id", "22222222-2222-2222-2222-222222222222"),
        ("invocation_id", "b" * 32),
    ),
)
def test_root_c2c_uses_retained_ready_not_mutable_decoded_cache(
    tmp_path: Path,
    field: str,
    cache_only_value: str,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    closure = _root_c2b_consume_with_writer(paths)
    retained_ready = json.loads(closure.session.permit_ready.raw.decode("ascii"))
    assert cache_only_value != retained_ready[field]
    closure.session.ready_receipt[field] = cache_only_value
    permit = installer.H11RootAuthorizedPermit.publish(closure)
    try:
        payload = json.loads(permit.publication.raw.decode("ascii"))
        expected_payload = {
            "schema": installer.H11_PERMIT_SCHEMA,
            "scenario": "H11",
            "run_unit": retained_ready["run_unit"],
            "boot_id": retained_ready["boot_id"],
            "invocation_id": retained_ready["invocation_id"],
            "authorization_manifest": closure.session.authorization.source,
            "harness_manifest": closure.session.authority.manifest_source,
            "permit_ready": closure.session.permit_ready.source,
            "run_armed": closure.session.run_armed.source,
            "ready_commit": closure.ready_commit.reference,
            "present_outputs_sha256": closure.present_outputs_sha256,
            "future_absence_sha256": closure.future_absence_sha256,
            "phase": "operator-release-authorized",
        }
        expected_raw = (
            json.dumps(
                expected_payload,
                ensure_ascii=True,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("ascii")
        assert payload[field] == retained_ready[field]
        assert payload[field] != cache_only_value
        assert permit.publication.raw == expected_raw
    finally:
        permit.close()


def _root_c2c_owned_descriptors(
    permit: installer.H11RootAuthorizedPermit,
) -> tuple[int, ...]:
    closure = permit.closure
    session = closure.session
    authority = session.authority
    return (
        permit.publication.descriptor,
        *(item.descriptor for item in closure.present_sources),
        session.authorization.descriptor,
        session.permit_ready.descriptor,
        session.run_armed.descriptor,
        authority.manifest_descriptor,
        *(item.descriptor for item in authority.bound_sources),
        *(item.descriptor for item in authority.directories),
        *(item.descriptor for item in authority.commit_fifos),
    )


def _assert_root_c2c_poisoned_owner_closed(
    permit: installer.H11RootAuthorizedPermit,
    descriptors: tuple[int, ...],
) -> None:
    closure = permit.closure
    session = closure.session
    authority = session.authority
    assert permit.poisoned is True
    assert permit.closed is True
    assert permit.publication.descriptor == -1
    assert closure.closed is True
    assert all(item.descriptor == -1 for item in closure.present_sources)
    assert session.authorization.descriptor == -1
    assert session.permit_ready.descriptor == -1
    assert session.run_armed.descriptor == -1
    assert authority.manifest_descriptor == -1
    assert all(item.descriptor == -1 for item in authority.bound_sources)
    assert all(item.descriptor == -1 for item in authority.directories)
    assert all(item.descriptor == -1 for item in authority.commit_fifos)
    for descriptor in descriptors:
        with pytest.raises(OSError):
            os.fstat(descriptor)


def test_root_c2c_same_byte_final_replacement_auto_poisons_all_owners(
    tmp_path: Path,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    closure = _root_c2b_consume_with_writer(paths)
    permit = installer.H11RootAuthorizedPermit.publish(closure)
    descriptors = _root_c2c_owned_descriptors(permit)
    scenario = paths["authorization"].parent
    final = scenario / "PERMIT.json"
    final_raw = final.read_bytes()
    displaced = scenario / "PERMIT.same-byte-displaced.json"
    final.rename(displaced)
    final.write_bytes(final_raw)
    final.chmod(0o444)
    with pytest.raises(installer.InstallerError, match="publication drifted"):
        permit.revalidate()
    _assert_root_c2c_poisoned_owner_closed(permit, descriptors)
    assert final.read_bytes() == final_raw
    assert displaced.read_bytes() == final_raw
    assert not (scenario / "PERMIT.pending").exists()
    assert not (scenario / "PERMIT-LEDGER.pending").exists()
    assert not (scenario / "PERMIT-LEDGER.json").exists()


@pytest.mark.parametrize(
    "role",
    ("permit-ledger-staging", "permit-ledger"),
)
def test_root_c2c_transaction_phase_drift_auto_poisons_all_owners(
    tmp_path: Path,
    role: str,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    closure = _root_c2b_consume_with_writer(paths)
    permit = installer.H11RootAuthorizedPermit.publish(closure)
    descriptors = _root_c2c_owned_descriptors(permit)
    scenario = paths["authorization"].parent
    final = scenario / "PERMIT.json"
    final_raw = final.read_bytes()
    drift_path = scenario / dict(_ROOT_C1B2_LAYOUT)[role]
    _root_c2a_write_json(
        drift_path,
        {"schema": "scion.test.post-permit-transaction-drift.v1"},
    )
    with pytest.raises(installer.InstallerError, match="state differs"):
        permit.revalidate()
    _assert_root_c2c_poisoned_owner_closed(permit, descriptors)
    assert final.read_bytes() == final_raw
    assert drift_path.is_file()
    assert not (scenario / "PERMIT.pending").exists()
    other_role = (
        "permit-ledger"
        if role == "permit-ledger-staging"
        else "permit-ledger-staging"
    )
    assert not (scenario / dict(_ROOT_C1B2_LAYOUT)[other_role]).exists()


def test_root_c2c_post_success_drift_poison_closes_but_retains_final(
    tmp_path: Path,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    closure = _root_c2b_consume_with_writer(paths)
    permit = installer.H11RootAuthorizedPermit.publish(closure)
    final = paths["authorization"].parent / "PERMIT.json"
    final_raw = final.read_bytes()
    publication_descriptor = permit.publication.descriptor
    present_descriptor = closure.present_sources[0].descriptor
    h0 = paths["h0"]
    h0_raw = h0.read_bytes()
    displaced = h0.with_name(h0.name + ".post-permit-displaced")
    h0.parent.chmod(0o755)
    h0.rename(displaced)
    h0.write_bytes(h0_raw)
    h0.chmod(0o444)
    h0.parent.chmod(0o555)
    with pytest.raises(installer.InstallerError, match="drifted"):
        permit.revalidate()
    assert permit.poisoned is True
    assert permit.closed is True
    assert permit.publication.descriptor == -1
    assert closure.closed is True
    assert final.read_bytes() == final_raw
    assert not (final.parent / "PERMIT.pending").exists()
    for descriptor in (publication_descriptor, present_descriptor):
        with pytest.raises(OSError):
            os.fstat(descriptor)


@pytest.mark.parametrize(
    "role",
    (
        "closer-properties",
        "exec-stop-post-properties",
        "final",
        "final-closer-properties",
        "final-run-properties",
        "frozen-root",
        "h12-absence",
        "journal",
        "manager-events",
        "signals",
        "source-selector",
    ),
)
def test_root_c2c_final_barrier_rejects_each_future_output(
    tmp_path: Path,
    role: str,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    closure = _root_c2b_consume_with_writer(paths)
    item = next(
        item
        for item in closure.partition.future_absence_inventory
        if item.role == role
    )
    if role == "frozen-root":
        item.path.mkdir(mode=0o700)
    else:
        item.path.parent.chmod(0o755)
        _root_c2a_write_json(
            item.path,
            {"schema": "scion.test.unexpected-future.v1", "role": role},
        )
        item.path.parent.chmod(0o555)
    with pytest.raises(installer.InstallerError, match="exists before permit"):
        installer.H11RootAuthorizedPermit.publish(closure)
    assert closure.poisoned is True
    assert not (paths["authorization"].parent / "PERMIT.pending").exists()
    assert not (paths["authorization"].parent / "PERMIT.json").exists()


@pytest.mark.parametrize(
    "role",
    (
        "permit-ready-staging",
        "permit-staging",
        "permit",
        "permit-ledger-staging",
        "permit-ledger",
    ),
)
def test_root_c2c_rejects_each_absent_authorizer_transaction_bit(
    tmp_path: Path,
    role: str,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    closure = _root_c2b_consume_with_writer(paths)
    leaf = dict(_ROOT_C1B2_LAYOUT)[role]
    _root_c2a_write_json(
        paths["authorization"].parent / leaf,
        {"schema": "scion.test.unexpected-transaction.v1", "role": role},
    )
    with pytest.raises(installer.InstallerError, match="state differs"):
        installer.H11RootAuthorizedPermit.publish(closure)
    assert closure.poisoned is True


@pytest.mark.parametrize(
    "drift",
    (
        "authorization",
        "ready",
        "manifest",
        "present",
        "directory",
        "fifo",
    ),
)
def test_root_c2c_rejects_retained_authority_drift_before_open(
    tmp_path: Path,
    drift: str,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    closure = _root_c2b_consume_with_writer(paths)
    if drift in {"authorization", "ready", "manifest", "present"}:
        target = (
            paths["h0"] if drift == "present" else paths[drift]
        )
        raw = target.read_bytes()
        displaced = target.with_name(target.name + ".c2c-displaced")
        if drift == "present":
            target.parent.chmod(0o755)
        target.rename(displaced)
        target.write_bytes(raw)
        target.chmod(0o444)
        if drift == "present":
            target.parent.chmod(0o555)
    elif drift == "directory":
        target = closure.session.authority.directories[5].reference.path
        displaced = target.with_name("receipts-c2c-displaced")
        target.rename(displaced)
        target.mkdir(mode=0o555)
        target.chmod(0o555)
    else:
        target = closure.session.authority.commit_fifos[0].reference.path
        displaced = target.with_name("ready-commit-c2c-displaced.fifo")
        target.rename(displaced)
        os.mkfifo(target, 0o600)
        target.chmod(0o600)
    with pytest.raises(installer.InstallerError):
        installer.H11RootAuthorizedPermit.publish(closure)
    assert closure.poisoned is True
    assert not (paths["authorization"].parent / "PERMIT.pending").exists()
    assert not (paths["authorization"].parent / "PERMIT.json").exists()


def test_root_c2c_pending_sentinel_fails_before_staging_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    closure = _root_c2b_consume_with_writer(paths)
    pending = paths["authorization"].parent / "PERMIT.pending"
    sentinel = b"preexisting-c2c-pending\n"
    pending.write_bytes(sentinel)
    pending.chmod(0o444)
    opens: list[object] = []
    monkeypatch.setattr(
        installer,
        "_open_h11_named_staging",
        lambda plan: opens.append(plan),
    )
    with pytest.raises(installer.InstallerError, match="state differs"):
        installer.H11RootAuthorizedPermit.publish(closure)
    assert opens == []
    assert pending.read_bytes() == sentinel
    assert closure.poisoned is True


def test_root_c2c_final_race_remains_no_replace_and_poisoned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    closure = _root_c2b_consume_with_writer(paths)
    scenario = paths["authorization"].parent
    final = scenario / "PERMIT.json"
    pending = scenario / "PERMIT.pending"
    sentinel = b"racing-final-sentinel\n"
    original_open = os.open

    def racing_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        if os.fsdecode(path) == "PERMIT.pending" and dir_fd == (
            closure.session.authority.directories[3].descriptor
        ):
            final.write_bytes(sentinel)
            final.chmod(0o444)
        return (
            original_open(path, flags, mode)
            if dir_fd is None
            else original_open(path, flags, mode, dir_fd=dir_fd)
        )

    monkeypatch.setattr(os, "open", racing_open)
    with pytest.raises(installer.InstallerError, match="no-replace"):
        installer.H11RootAuthorizedPermit.publish(closure)
    assert final.read_bytes() == sentinel
    assert pending.is_file()
    assert closure.poisoned is True


def test_root_c2c_syscall_pre_rename_failure_poison_pending_and_fd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    closure = _root_c2b_consume_with_writer(paths)
    parent = closure.session.authority.directories[3]
    opened = _capture_root_c1c_staging_descriptor(
        monkeypatch,
        parent_descriptor=parent.descriptor,
        staging_name="PERMIT.pending",
    )

    class FailingRenameAt2:
        argtypes: Any = None
        restype: Any = None

        def __call__(self, *args: Any) -> int:
            installer.ctypes.set_errno(errno.EIO)
            return -1

    class FailingLibc:
        renameat2 = FailingRenameAt2()

    monkeypatch.setattr(
        installer.ctypes,
        "CDLL",
        lambda *args, **kwargs: FailingLibc(),
    )
    with pytest.raises(installer.InstallerError, match="no-replace"):
        installer.H11RootAuthorizedPermit.publish(closure)
    assert (parent.reference.path / "PERMIT.pending").is_file()
    assert not (parent.reference.path / "PERMIT.json").exists()
    _assert_root_c1c_descriptors_closed(opened)
    assert closure.poisoned is True


def test_root_c2c_syscall_post_rename_failure_poison_final_and_fd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    closure = _root_c2b_consume_with_writer(paths)
    parent = closure.session.authority.directories[3]
    opened = _capture_root_c1c_staging_descriptor(
        monkeypatch,
        parent_descriptor=parent.descriptor,
        staging_name="PERMIT.pending",
    )
    original_fsync = os.fsync
    injected = OSError(errno.EIO, "injected C2c parent fsync failure")

    def faulting_fsync(descriptor: int) -> None:
        if descriptor == parent.descriptor:
            raise injected
        original_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", faulting_fsync)
    with pytest.raises(OSError) as caught:
        installer.H11RootAuthorizedPermit.publish(closure)
    assert caught.value is injected
    assert not (parent.reference.path / "PERMIT.pending").exists()
    assert (parent.reference.path / "PERMIT.json").is_file()
    _assert_root_c1c_descriptors_closed(opened)
    assert closure.poisoned is True


def test_root_c2c_final_pending_probe_catches_second_lookup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    closure = _root_c2b_consume_with_writer(paths)
    scenario_fd = closure.session.authority.directories[3].descriptor
    original_stat = os.stat
    pending_lookups = 0
    opens: list[object] = []

    def second_lookup_present(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        *args: object,
        **kwargs: object,
    ) -> os.stat_result | SimpleNamespace:
        nonlocal pending_lookups
        if (
            os.fsdecode(path) == "PERMIT.pending"
            and kwargs.get("dir_fd") == scenario_fd
            and kwargs.get("follow_symlinks") is False
        ):
            pending_lookups += 1
            if pending_lookups == 2:
                return SimpleNamespace()
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(os, "stat", second_lookup_present)
    monkeypatch.setattr(
        installer,
        "_open_h11_named_staging",
        lambda plan: opens.append(plan),
    )
    with pytest.raises(installer.InstallerError, match="final pre-publication"):
        installer.H11RootAuthorizedPermit.publish(closure)
    assert pending_lookups == 2
    assert opens == []
    assert closure.poisoned is True


def test_root_c2c_ast_freezes_barrier_open_and_phase_call_graph() -> None:
    prepare_source = inspect.getsource(installer._prepare_h11_named_staging)
    prepare_tree = ast.parse(prepare_source)
    opener_source = inspect.getsource(installer._open_h11_named_staging)
    opener_tree = ast.parse(opener_source)
    opener_calls = [
        node
        for node in ast.walk(opener_tree)
        if isinstance(node, ast.Call)
    ]
    assert [ast.unparse(node.func) for node in opener_calls] == ["os.open"]
    open_call = opener_calls[0]
    assert ast.unparse(open_call.args[0]) == "plan.staging_name"
    assert ast.unparse(open_call.args[1]) == (
        "os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC"
    )
    assert isinstance(open_call.args[2], ast.Constant)
    assert open_call.args[2].value == 0o444
    assert {
        keyword.arg: ast.unparse(keyword.value)
        for keyword in open_call.keywords
    } == {"dir_fd": "plan.parent.descriptor"}

    core_source = inspect.getsource(installer._complete_h11_named_staging)
    core_tree = ast.parse(core_source)
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "open"
        for node in ast.walk(core_tree)
    )
    assert not any(
        token in core_source
        for token in (
            "callback",
            "retry",
            "cleanup",
            "timeout",
            "poll",
            "sleep",
        )
    )
    helper_trees = {
        "prepare": prepare_tree,
        "open": opener_tree,
        "complete": core_tree,
    }
    assert {
        name: {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
        }
        for name, tree in helper_trees.items()
    } == {
        "prepare": {
            "H11RootNamedStagingPlan",
            "_canonical",
            "_fail",
            "type",
        },
        "open": set(),
        "complete": {
            "InstallerError",
            "RetainedH11RootPublication",
            "_close_h11_ownership",
            "_fail",
            "len",
            "memoryview",
            "renameat2",
            "str",
        },
    }
    mutation_attrs = {
        "open",
        "write",
        "write_bytes",
        "write_text",
        "fsync",
        "fdatasync",
        "ftruncate",
        "truncate",
        "fchmod",
        "fchown",
        "mkdir",
        "unlink",
        "rename",
        "replace",
        "remove",
        "rmdir",
        "chmod",
        "chown",
        "link",
        "symlink",
        "close",
    }
    assert {
        name: {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in mutation_attrs
        }
        for name, tree in helper_trees.items()
    } == {
        "prepare": set(),
        "open": {"open"},
        "complete": {"write", "fsync", "fchmod"},
    }
    complete_os_calls = {
        node.func.attr
        for node in ast.walk(core_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "os"
    }
    assert complete_os_calls == {
        "fchmod",
        "fstat",
        "fsync",
        "lseek",
        "read",
        "stat",
        "strerror",
        "write",
    }
    assert sum(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "renameat2"
        for node in ast.walk(core_tree)
    ) == 1

    permit_source = inspect.getsource(installer.H11RootAuthorizedPermit)
    permit_tree = ast.parse(permit_source)
    publish = next(
        node
        for node in ast.walk(permit_tree)
        if isinstance(node, ast.FunctionDef) and node.name == "publish"
    )
    try_body = next(
        node.body
        for node in publish.body
        if isinstance(node, ast.Try)
    )
    barrier_index = next(
        index
        for index, node in enumerate(try_body)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "barrier"
            for target in node.targets
        )
    )
    retained_ready_index = next(
        index
        for index, node in enumerate(try_body)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "retained_ready"
            for target in node.targets
        )
    )
    retained_ready_assignment = try_body[retained_ready_index]
    assert isinstance(retained_ready_assignment, ast.Assign)
    assert isinstance(retained_ready_assignment.value, ast.Call)
    assert ast.unparse(retained_ready_assignment.value.func) == (
        "_decode_canonical_object"
    )
    assert ast.unparse(retained_ready_assignment.value.args[0]) == (
        "session.permit_ready.raw"
    )
    assert retained_ready_index < barrier_index
    assert "ready_receipt" not in ast.unparse(publish)
    assert isinstance(try_body[barrier_index + 1], ast.Assign)
    assert [
        target.id
        for target in try_body[barrier_index + 1].targets
        if isinstance(target, ast.Name)
    ] == ["descriptor"]
    assert isinstance(try_body[barrier_index + 1].value, ast.Call)
    assert ast.unparse(try_body[barrier_index + 1].value.func) == (
        "_open_h11_named_staging"
    )
    publish_signature = inspect.signature(
        installer.H11RootAuthorizedPermit.publish
    )
    assert tuple(publish_signature.parameters) == ("closure",)
    expected_state_assignment = next(
        node
        for node in try_body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name)
            and target.id == "expected_transaction_state"
            for target in node.targets
        )
    )
    expected_state_source = ast.unparse(expected_state_assignment.value)
    assert "closure.transaction_state" in expected_state_source
    assert "permit-committed" in expected_state_source
    assert ".manifest" not in expected_state_source

    barrier_source = inspect.getsource(installer.H11RootPrePermitBarrier)
    barrier_tree = ast.parse(barrier_source)
    stat_calls = [
        node
        for node in ast.walk(barrier_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and ast.unparse(node.func) == "os.stat"
    ]
    assert len(stat_calls) == 2
    pending_stat = next(
        node
        for node in stat_calls
        if isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "PERMIT.pending"
    )
    assert {
        item.arg: ast.unparse(item.value)
        for item in pending_stat.keywords
    } == {
        "dir_fd": "plan.parent.descriptor",
        "follow_symlinks": "False",
    }
    filesystem_calls = [
        node
        for node in ast.walk(barrier_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr
        in {"open", "stat", "lstat", "fstat", "access", "readlink"}
    ]
    assert max(filesystem_calls, key=lambda node: node.lineno) is pending_stat
    assert "watch_events" not in barrier_source
    assert "absence_barrier" not in barrier_source
    assert {
        name: {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
        }
        for name, tree in {
            "permit": permit_tree,
            "barrier": barrier_tree,
        }.items()
    } == {
        "permit": {
            "H11RootTransactionState",
            "_complete_h11_named_staging",
            "_close_h11_ownership",
            "_decode_canonical_object",
            "_fail",
            "_open_h11_named_staging",
            "_prepare_h11_named_staging",
            "cls",
            "dict",
            "tuple",
            "zip",
        },
        "barrier": {
            "InstallerError",
            "_fail",
            "cls",
            "dataclass",
            "len",
            "tuple",
        },
    }

    revalidate = next(
        node
        for node in ast.walk(permit_tree)
        if isinstance(node, ast.FunctionDef) and node.name == "revalidate"
    )
    revalidate_calls = [
        ast.unparse(node.func)
        for node in ast.walk(revalidate)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
    ]
    assert "self.closure.revalidate" not in revalidate_calls
    assert {
        "self.closure._revalidate_retained_common",
        "self.closure._validate_exact_transaction_phase",
        "self.publication.revalidate",
    }.issubset(revalidate_calls)
    close_method = next(
        node
        for node in ast.walk(permit_tree)
        if isinstance(node, ast.FunctionDef) and node.name == "close"
    )
    close_calls = [
        ast.unparse(node.value.func)
        for node in close_method.body
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
    ]
    assert close_calls == ["_close_h11_ownership"]
    close_call = next(
        node.value
        for node in close_method.body
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
    )
    assert ast.unparse(close_call.args[0]) == (
        "(self.publication, self.closure)"
    )

    module_tree = ast.parse(
        Path(installer.__file__).read_text(encoding="utf-8")
    )
    parents = {
        child: parent
        for parent in ast.walk(module_tree)
        for child in ast.iter_child_nodes(parent)
    }
    helper_callsites = {
        name: []
        for name in (
            "_prepare_h11_named_staging",
            "_open_h11_named_staging",
            "_complete_h11_named_staging",
        )
    }
    for node in ast.walk(module_tree):
        if (
            not isinstance(node, ast.Call)
            or not isinstance(node.func, ast.Name)
            or node.func.id not in helper_callsites
        ):
            continue
        owner = parents[node]
        while not isinstance(owner, (ast.FunctionDef, ast.AsyncFunctionDef)):
            owner = parents[owner]
        scope = parents[owner]
        while not isinstance(scope, (ast.ClassDef, ast.Module)):
            scope = parents[scope]
        qualified_owner = (
            f"{scope.name}.{owner.name}"
            if isinstance(scope, ast.ClassDef)
            else owner.name
        )
        helper_callsites[node.func.id].append(qualified_owner)
    assert helper_callsites == {
        "_prepare_h11_named_staging": [
            "_publish_h11_named_staging",
            "H11RootAuthorizedPermit.publish",
        ],
        "_open_h11_named_staging": [
            "_publish_h11_named_staging",
            "H11RootAuthorizedPermit.publish",
        ],
        "_complete_h11_named_staging": [
            "_publish_h11_named_staging",
            "H11RootAuthorizedPermit.publish",
        ],
    }

    helper_source = "\n".join(
        (prepare_source, opener_source, core_source)
    )
    combined = "\n".join(
        (
            inspect.getsource(installer.H11RootAuthorizerReadyClosure),
            permit_source,
            barrier_source,
            helper_source,
        )
    )
    combined_tree = ast.parse(combined)
    phase_calls = [
        node
        for node in ast.walk(combined_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_validate_exact_transaction_phase"
    ]
    assert [ast.literal_eval(node.args[0]) for node in phase_calls] == [
        "authorizer-input",
        "permit-committed",
    ]
    forbidden_seam_tokens = {
        "authorize_h11_release",
        "_publish_h11_permit",
        "read_ready_commit",
        "write_commit",
        "commit_fifos",
        "governance",
        "callback",
        "hook",
        "timeout",
        "deadline",
        "poll",
        "sleep",
        "retry",
        "budget",
        "cap",
        "truncate",
        "truncation",
        "watchdog",
        "cleanup",
    }
    seam_source = "\n".join((permit_source, barrier_source, helper_source))
    seam_name_tokens = {
        item.string
        for item in tokenize.generate_tokens(io.StringIO(seam_source).readline)
        if item.type == tokenize.NAME
    }
    assert forbidden_seam_tokens.isdisjoint(seam_name_tokens)


def _root_c2d_permit_fifo(
    permit: installer.H11RootAuthorizedPermit,
) -> installer.RetainedH11RootFifo:
    matches = tuple(
        item
        for item in permit.closure.session.authority.commit_fifos
        if item.role == "h11-permit-commit"
    )
    assert len(matches) == 1
    return matches[0]


def _root_c2d_read_permit_frame(
    fifo: installer.RetainedH11RootFifo,
    entered: threading.Event,
    payloads: list[bytes],
    errors: list[BaseException],
) -> None:
    descriptor = -1
    entered.set()
    try:
        descriptor = os.open(
            f"/proc/self/fd/{fifo.descriptor}",
            os.O_RDONLY | os.O_CLOEXEC,
        )
        fifo.reference.prove(
            os.fstat(descriptor),
            require_root=False,
            label="test H11 PERMIT commit reader",
        )
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, select.PIPE_BUF)
            if not chunk:
                break
            chunks.append(chunk)
        payloads.append(b"".join(chunks))
    except BaseException as exc:
        errors.append(exc)
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def test_root_c2d_permit_commit_receipt_is_exact(tmp_path: Path) -> None:
    paths = _root_c2a_session_model(tmp_path)
    session = installer.H11RootAuthorizerSession.open(
        paths["authorization"], require_root=False
    )
    try:
        fifo = next(
            item
            for item in session.authority.commit_fifos
            if item.role == "h11-permit-commit"
        )
        receipt = installer.H11RootCommitReceipt.permit_committed(
            fifo,
            installer.H11_PERMIT_COMMITTED_BYTES,
        )
        assert len(installer.H11_PERMIT_COMMITTED_BYTES) == 30
        assert receipt.reference == {
            "schema": installer.H11_COMMIT_FIFO_RECEIPT_SCHEMA,
            "phase": "permit-committed",
            "fifo": fifo.reference.reference,
            "payload_sha256": hashlib.sha256(
                b"SCION_H11_PERMIT_COMMITTED_V1\n"
            ).hexdigest(),
            "byte_count": "30",
        }
    finally:
        session.close()


@pytest.mark.parametrize(
    ("role", "payload"),
    (
        ("h11-ready-commit", b"SCION_H11_PERMIT_COMMITTED_V1\n"),
        ("h11-permit-commit", b"SCION_H11_PERMIT_COMMITTED_V1"),
        ("h11-permit-commit", b"SCION_H11_PERMIT_COMMITTED_V1\nX"),
        (
            "h11-permit-commit",
            b"SCION_H11_PERMIT_COMMITTED_V1\n" * 2,
        ),
    ),
)
def test_root_c2d_permit_commit_receipt_rejects_nonexact_source(
    tmp_path: Path,
    role: str,
    payload: bytes,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    session = installer.H11RootAuthorizerSession.open(
        paths["authorization"], require_root=False
    )
    try:
        fifo = next(
            item
            for item in session.authority.commit_fifos
            if item.role == role
        )
        with pytest.raises(installer.InstallerError, match="exact committed"):
            installer.H11RootCommitReceipt.permit_committed(fifo, payload)
    finally:
        session.close()


@pytest.mark.parametrize("invalid", ("wrong-role", "closed"))
def test_root_c2d_writer_rejects_wrong_role_or_closed_before_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    invalid: str,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    session = installer.H11RootAuthorizerSession.open(
        paths["authorization"], require_root=False
    )
    fifo = next(
        item
        for item in session.authority.commit_fifos
        if item.role
        == (
            "h11-ready-commit"
            if invalid == "wrong-role"
            else "h11-permit-commit"
        )
    )
    if invalid == "closed":
        fifo.close()
    opens: list[object] = []
    monkeypatch.setattr(os, "open", lambda *args, **kwargs: opens.append(args))
    try:
        with pytest.raises(installer.InstallerError):
            fifo.open_permit_commit_writer(require_root=False)
        assert opens == []
    finally:
        session.close()


@pytest.mark.parametrize("first_direction", ("writer", "reader"))
def test_root_c2d_writer_accepts_both_blocking_endpoint_schedules(
    tmp_path: Path,
    first_direction: str,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    closure = _root_c2b_consume_with_writer(paths)
    permit = installer.H11RootAuthorizedPermit.publish(closure)
    fifo = _root_c2d_permit_fifo(permit)
    entered = threading.Event()
    result: dict[str, int | BaseException] = {}

    def first_endpoint() -> None:
        entered.set()
        try:
            if first_direction == "writer":
                result["descriptor"] = fifo.open_permit_commit_writer(
                    require_root=False
                )
            else:
                result["descriptor"] = os.open(
                    f"/proc/self/fd/{fifo.descriptor}",
                    os.O_RDONLY | os.O_CLOEXEC,
                )
        except BaseException as exc:
            result["error"] = exc

    thread = threading.Thread(target=first_endpoint)
    thread.start()
    entered.wait()
    second = -1
    try:
        if first_direction == "writer":
            second = os.open(
                f"/proc/self/fd/{fifo.descriptor}",
                os.O_RDONLY | os.O_CLOEXEC,
            )
        else:
            second = fifo.open_permit_commit_writer(require_root=False)
        thread.join()
        assert "error" not in result
        assert isinstance(result["descriptor"], int)
    finally:
        if second >= 0:
            os.close(second)
        if isinstance(result.get("descriptor"), int):
            os.close(result["descriptor"])
        permit.close()


def test_root_c2d_writer_endpoint_uses_exact_path_flags_and_fstat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    closure = _root_c2b_consume_with_writer(paths)
    permit = installer.H11RootAuthorizedPermit.publish(closure)
    fifo = _root_c2d_permit_fifo(permit)
    reader_entered = threading.Event()
    payloads: list[bytes] = []
    errors: list[BaseException] = []
    reader = threading.Thread(
        target=_root_c2d_read_permit_frame,
        args=(fifo, reader_entered, payloads, errors),
    )
    reader.start()
    reader_entered.wait()
    original_open = os.open
    original_fstat = os.fstat
    expected_path = f"/proc/self/fd/{fifo.descriptor}"
    opened: list[tuple[str, int]] = []
    proven: list[int] = []

    def recording_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        descriptor = original_open(path, flags, *args, **kwargs)
        if os.fsdecode(path) == expected_path:
            opened.append((os.fsdecode(path), flags))
        return descriptor

    def recording_fstat(descriptor: int) -> os.stat_result:
        proven.append(descriptor)
        return original_fstat(descriptor)

    monkeypatch.setattr(os, "open", recording_open)
    monkeypatch.setattr(os, "fstat", recording_fstat)
    descriptor = fifo.open_permit_commit_writer(require_root=False)
    os.close(descriptor)
    reader.join()
    permit.close()
    assert opened == [
        (
            expected_path,
            os.O_WRONLY | os.O_CLOEXEC,
        )
    ]
    assert descriptor in proven
    assert payloads == [b""]
    assert errors == []


@pytest.mark.parametrize("primary_site", ("fstat", "prove"))
def test_root_c2d_writer_primary_survives_endpoint_close_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    primary_site: str,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    session = installer.H11RootAuthorizerSession.open(
        paths["authorization"], require_root=False
    )
    fifo = next(
        item
        for item in session.authority.commit_fifos
        if item.role == "h11-permit-commit"
    )
    entered = threading.Event()
    payloads: list[bytes] = []
    peer_errors: list[BaseException] = []
    peer = threading.Thread(
        target=_root_c2d_read_permit_frame,
        args=(fifo, entered, payloads, peer_errors),
    )
    peer.start()
    entered.wait()
    real_open = os.open
    real_close = os.close
    real_fstat = os.fstat
    original_prove = installer.H11RootFifoReference.prove
    writer_descriptor = -1
    close_counts: dict[int, int] = {}
    primary_error: BaseException = (
        OSError(errno.EIO, "injected PERMIT writer fstat failure")
        if primary_site == "fstat"
        else RuntimeError("injected PERMIT writer prove failure")
    )
    close_error = OSError(errno.EBADF, "injected PERMIT writer close failure")

    def capture_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        nonlocal writer_descriptor
        descriptor = real_open(path, flags, *args, **kwargs)
        if (
            os.fsdecode(path) == f"/proc/self/fd/{fifo.descriptor}"
            and flags == os.O_WRONLY | os.O_CLOEXEC
        ):
            writer_descriptor = descriptor
        return descriptor

    def failing_fstat(descriptor: int) -> os.stat_result:
        if primary_site == "fstat" and descriptor == writer_descriptor:
            raise primary_error
        return real_fstat(descriptor)

    def failing_prove(
        self: installer.H11RootFifoReference,
        info: os.stat_result,
        *,
        require_root: bool,
        label: str,
    ) -> None:
        if primary_site == "prove" and label == "H11 permit-commit writer":
            raise primary_error
        original_prove(
            self,
            info,
            require_root=require_root,
            label=label,
        )

    def close_then_fail(descriptor: int) -> None:
        close_counts[descriptor] = close_counts.get(descriptor, 0) + 1
        real_close(descriptor)
        if descriptor == writer_descriptor:
            raise close_error

    monkeypatch.setattr(os, "open", capture_open)
    monkeypatch.setattr(os, "fstat", failing_fstat)
    monkeypatch.setattr(installer.H11RootFifoReference, "prove", failing_prove)
    monkeypatch.setattr(os, "close", close_then_fail)
    result: dict[str, int] = {}
    with pytest.raises(BaseException) as caught:
        result["descriptor"] = fifo.open_permit_commit_writer(
            require_root=False
        )
    peer.join()
    if primary_site == "fstat":
        assert isinstance(caught.value, installer.InstallerError)
        assert caught.value.__cause__ is primary_error
        final_error = caught.value
    else:
        assert caught.value is primary_error
        final_error = primary_error
    assert result == {}
    assert peer_errors == []
    assert payloads == [b""]
    assert final_error.__notes__ == [
        "H11 ownership teardown secondary: "
        f"{type(close_error).__name__}: {close_error}"
    ]
    assert close_counts[writer_descriptor] == 1
    with pytest.raises(OSError):
        real_fstat(writer_descriptor)
    session.close()


@pytest.mark.parametrize("first_direction", ("reader", "writer"))
def test_root_c2d_commit_single_write_eof_and_live_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    first_direction: str,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    closure = _root_c2b_consume_with_writer(paths)
    permit = installer.H11RootAuthorizedPermit.publish(closure)
    fifo = _root_c2d_permit_fifo(permit)
    descriptors = _root_c2c_owned_descriptors(permit)
    publication_descriptor = permit.publication.descriptor
    payloads: list[bytes] = []
    errors: list[BaseException] = []
    entered = threading.Event()
    writes: list[tuple[int, bytes]] = []
    original_write = os.write

    def recording_write(descriptor: int, payload: bytes) -> int:
        if payload == installer.H11_PERMIT_COMMITTED_BYTES:
            os.fstat(publication_descriptor)
            assert permit.closed is False
            writes.append((descriptor, payload))
        return original_write(descriptor, payload)

    monkeypatch.setattr(os, "write", recording_write)
    result: dict[str, Any] = {}
    if first_direction == "reader":
        peer = threading.Thread(
            target=_root_c2d_read_permit_frame,
            args=(fifo, entered, payloads, errors),
        )
        peer.start()
        entered.wait()
        result["receipt"] = installer._commit_h11_authorized_permit(permit)
    else:
        original_endpoint = fifo.open_permit_commit_writer

        def entered_endpoint(*, require_root: bool) -> int:
            entered.set()
            return original_endpoint(require_root=require_root)

        monkeypatch.setattr(
            fifo,
            "open_permit_commit_writer",
            entered_endpoint,
        )

        def commit_actor() -> None:
            try:
                result["receipt"] = (
                    installer._commit_h11_authorized_permit(permit)
                )
            except BaseException as exc:
                errors.append(exc)

        peer = threading.Thread(target=commit_actor)
        peer.start()
        entered.wait()
        _root_c2d_read_permit_frame(
            fifo,
            threading.Event(),
            payloads,
            errors,
        )
    peer.join()
    assert errors == []
    assert payloads == [installer.H11_PERMIT_COMMITTED_BYTES]
    assert len(writes) == 1
    assert writes[0][1] == installer.H11_PERMIT_COMMITTED_BYTES
    receipt = result["receipt"]
    assert isinstance(receipt, installer.H11RootCommitReceipt)
    assert receipt.phase == "permit-committed"
    assert receipt.byte_count == "30"
    assert permit.commit_started is True
    assert permit.closed is True
    assert permit.poisoned is False
    assert permit.publication.descriptor == -1
    for descriptor in descriptors:
        with pytest.raises(OSError):
            os.fstat(descriptor)


@pytest.mark.parametrize(
    "drift",
    ("fifo", "permit", "source", "transaction"),
)
def test_root_c2d_blocked_open_drift_revalidates_before_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    closure = _root_c2b_consume_with_writer(paths)
    permit = installer.H11RootAuthorizedPermit.publish(closure)
    fifo = _root_c2d_permit_fifo(permit)
    descriptors = _root_c2c_owned_descriptors(permit)
    final = paths["authorization"].parent / "PERMIT.json"
    final_raw = final.read_bytes()
    entered = threading.Event()
    errors: list[BaseException] = []
    writes: list[bytes] = []
    original_endpoint = fifo.open_permit_commit_writer

    def entered_endpoint(*, require_root: bool) -> int:
        entered.set()
        return original_endpoint(require_root=require_root)

    monkeypatch.setattr(fifo, "open_permit_commit_writer", entered_endpoint)
    original_write = os.write

    def recording_write(descriptor: int, payload: bytes) -> int:
        if payload == installer.H11_PERMIT_COMMITTED_BYTES:
            writes.append(payload)
        return original_write(descriptor, payload)

    monkeypatch.setattr(os, "write", recording_write)

    def commit_actor() -> None:
        try:
            installer._commit_h11_authorized_permit(permit)
        except BaseException as exc:
            errors.append(exc)

    actor = threading.Thread(target=commit_actor)
    actor.start()
    entered.wait()
    reader_path = fifo.reference.path
    if drift == "fifo":
        displaced = reader_path.with_name("permit-commit-displaced.fifo")
        reader_path.rename(displaced)
        os.mkfifo(reader_path, 0o600)
        reader_path.chmod(0o600)
        reader_path = displaced
    elif drift == "permit":
        displaced = final.with_name("PERMIT.c2d-displaced.json")
        final.rename(displaced)
        final.write_bytes(final_raw)
        final.chmod(0o444)
    elif drift == "source":
        source = paths["h0"]
        raw = source.read_bytes()
        displaced = source.with_name("h0.c2d-displaced.json")
        source.parent.chmod(0o755)
        source.rename(displaced)
        source.write_bytes(raw)
        source.chmod(0o444)
        source.parent.chmod(0o555)
    else:
        _root_c2a_write_json(
            final.with_name("PERMIT-LEDGER.pending"),
            {"schema": "scion.test.c2d-transaction-drift.v1"},
        )
    reader = os.open(reader_path, os.O_RDONLY | os.O_CLOEXEC)
    os.close(reader)
    actor.join()
    assert len(errors) == 1
    assert writes == []
    _assert_root_c2c_poisoned_owner_closed(permit, descriptors)
    assert final.read_bytes() == final_raw


@pytest.mark.parametrize(
    "failure",
    ("open", "fstat", "epipe", "short-write", "close"),
)
def test_root_c2d_handoff_failure_poisons_all_owners_and_retains_final(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    closure = _root_c2b_consume_with_writer(paths)
    permit = installer.H11RootAuthorizedPermit.publish(closure)
    fifo = _root_c2d_permit_fifo(permit)
    descriptors = _root_c2c_owned_descriptors(permit)
    final = paths["authorization"].parent / "PERMIT.json"
    final_raw = final.read_bytes()
    payloads: list[bytes] = []
    peer_errors: list[BaseException] = []
    opened_endpoints: list[int] = []
    real_fstat = os.fstat
    real_open = os.open
    real_close = os.close
    entered = threading.Event()
    peer = threading.Thread(
        target=_root_c2d_read_permit_frame,
        args=(fifo, entered, payloads, peer_errors),
    )
    peer.start()
    entered.wait()

    if failure == "open":
        monkeypatch.setattr(
            fifo,
            "open_permit_commit_writer",
            lambda *, require_root: (_ for _ in ()).throw(
                OSError(errno.EIO, "injected C2d open failure")
            ),
        )
    elif failure == "fstat":
        endpoint = -1

        def endpoint_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
            nonlocal endpoint
            if (
                os.fsdecode(path) == f"/proc/self/fd/{fifo.descriptor}"
                and flags == os.O_WRONLY | os.O_CLOEXEC
            ):
                endpoint = os.dup(fifo.descriptor)
                opened_endpoints.append(endpoint)
                return endpoint
            return real_open(path, flags, *args, **kwargs)

        def failing_fstat(descriptor: int) -> os.stat_result:
            if descriptor == endpoint:
                raise OSError(errno.EIO, "injected C2d fstat failure")
            return real_fstat(descriptor)

        monkeypatch.setattr(os, "open", endpoint_open)
        monkeypatch.setattr(os, "fstat", failing_fstat)
    else:
        def recording_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
            descriptor = real_open(path, flags, *args, **kwargs)
            if (
                os.fsdecode(path) == f"/proc/self/fd/{fifo.descriptor}"
                and flags == os.O_WRONLY | os.O_CLOEXEC
            ):
                opened_endpoints.append(descriptor)
            return descriptor

        monkeypatch.setattr(os, "open", recording_open)
        if failure in {"epipe", "short-write"}:
            original_write = os.write

            def failing_write(descriptor: int, payload: bytes) -> int:
                if payload == installer.H11_PERMIT_COMMITTED_BYTES:
                    if failure == "epipe":
                        raise BrokenPipeError(errno.EPIPE, "injected C2d EPIPE")
                    return len(payload) - 1
                return original_write(descriptor, payload)

            monkeypatch.setattr(os, "write", failing_write)
        else:
            original_endpoint = fifo.open_permit_commit_writer
            writer_descriptor = -1

            def capture_endpoint(*, require_root: bool) -> int:
                nonlocal writer_descriptor
                writer_descriptor = original_endpoint(
                    require_root=require_root
                )
                return writer_descriptor

            def failing_close(descriptor: int) -> None:
                real_close(descriptor)
                if descriptor == writer_descriptor:
                    raise OSError(errno.EIO, "injected C2d close failure")

            monkeypatch.setattr(
                fifo,
                "open_permit_commit_writer",
                capture_endpoint,
            )
            monkeypatch.setattr(os, "close", failing_close)

    with pytest.raises(BaseException):
        installer._commit_h11_authorized_permit(permit)
    if failure in {"open", "fstat"}:
        writer = real_open(
            fifo.reference.path,
            os.O_WRONLY | os.O_CLOEXEC,
        )
        real_close(writer)
    peer.join()
    assert peer_errors == []
    assert payloads == [
        (
            installer.H11_PERMIT_COMMITTED_BYTES
            if failure == "close"
            else b""
        )
    ]
    for descriptor in opened_endpoints:
        with pytest.raises(OSError):
            real_fstat(descriptor)
    _assert_root_c2c_poisoned_owner_closed(permit, descriptors)
    assert final.read_bytes() == final_raw
    assert permit.commit_started is True


@pytest.mark.parametrize(
    "failure_owner",
    ("publication", "present-source", "authority"),
)
def test_root_c2d_teardown_rethrows_first_error_after_closing_full_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_owner: str,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    closure = _root_c2b_consume_with_writer(paths)
    permit = installer.H11RootAuthorizedPermit.publish(closure)
    fifo = _root_c2d_permit_fifo(permit)
    descriptors = _root_c2c_owned_descriptors(permit)
    final = paths["authorization"].parent / "PERMIT.json"
    final_raw = final.read_bytes()
    targets = {
        "publication": permit.publication.descriptor,
        "present-source": closure.present_sources[1].descriptor,
        "authority": closure.session.authority.directories[3].descriptor,
    }
    target = targets[failure_owner]
    payloads: list[bytes] = []
    peer_errors: list[BaseException] = []
    entered = threading.Event()
    peer = threading.Thread(
        target=_root_c2d_read_permit_frame,
        args=(fifo, entered, payloads, peer_errors),
    )
    peer.start()
    entered.wait()
    real_close = os.close
    injected = OSError(errno.EIO, f"injected {failure_owner} close failure")
    raised = False

    def close_then_fail(descriptor: int) -> None:
        nonlocal raised
        real_close(descriptor)
        if descriptor == target and not raised:
            raised = True
            raise injected

    monkeypatch.setattr(os, "close", close_then_fail)
    with pytest.raises(OSError) as caught:
        installer._commit_h11_authorized_permit(permit)
    peer.join()
    assert caught.value is injected
    assert raised is True
    assert peer_errors == []
    assert payloads == [installer.H11_PERMIT_COMMITTED_BYTES]
    _assert_root_c2c_poisoned_owner_closed(permit, descriptors)
    assert final.read_bytes() == final_raw
    assert permit.poisoned is True


def test_root_c2d_teardown_preserves_first_error_and_visits_later_owners() -> None:
    events: list[str] = []
    first = RuntimeError("first teardown failure")
    second = OSError(errno.EIO, "second teardown failure")

    class Owner:
        def __init__(self, name: str, failure: BaseException | None) -> None:
            self.name = name
            self.failure = failure

        def close(self) -> None:
            events.append(self.name)
            if self.failure is not None:
                raise self.failure

    with pytest.raises(RuntimeError) as caught:
        installer._close_h11_ownership(
            (
                Owner("first", first),
                Owner("second", second),
                Owner("third", None),
            )
        )
    assert caught.value is first
    assert events == ["first", "second", "third"]


def test_root_c2d_commit_double_close_failure_preserves_writer_primary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    closure = _root_c2b_consume_with_writer(paths)
    permit = installer.H11RootAuthorizedPermit.publish(closure)
    fifo = _root_c2d_permit_fifo(permit)
    descriptors = _root_c2c_owned_descriptors(permit)
    publication_descriptor = permit.publication.descriptor
    payloads: list[bytes] = []
    peer_errors: list[BaseException] = []
    entered = threading.Event()
    peer = threading.Thread(
        target=_root_c2d_read_permit_frame,
        args=(fifo, entered, payloads, peer_errors),
    )
    peer.start()
    entered.wait()
    real_close = os.close
    original_endpoint = fifo.open_permit_commit_writer
    writer_descriptor = -1
    close_counts: dict[int, int] = {}
    writer_error = OSError(errno.EIO, "injected writer close failure")
    publication_error = OSError(
        errno.EIO,
        "injected publication close failure",
    )

    def capture_endpoint(*, require_root: bool) -> int:
        nonlocal writer_descriptor
        writer_descriptor = original_endpoint(require_root=require_root)
        return writer_descriptor

    def close_then_fail(descriptor: int) -> None:
        close_counts[descriptor] = close_counts.get(descriptor, 0) + 1
        real_close(descriptor)
        if descriptor == writer_descriptor:
            raise writer_error
        if descriptor == publication_descriptor:
            raise publication_error

    monkeypatch.setattr(fifo, "open_permit_commit_writer", capture_endpoint)
    monkeypatch.setattr(os, "close", close_then_fail)
    result: dict[str, installer.H11RootCommitReceipt] = {}
    with pytest.raises(OSError) as caught:
        result["receipt"] = installer._commit_h11_authorized_permit(permit)
    peer.join()
    assert caught.value is writer_error
    assert result == {}
    assert peer_errors == []
    assert payloads == [installer.H11_PERMIT_COMMITTED_BYTES]
    assert writer_error.__notes__ == [
        "H11 ownership teardown secondary: "
        f"{type(publication_error).__name__}: {publication_error}"
    ]
    assert len(set(descriptors)) == len(descriptors)
    assert close_counts[writer_descriptor] == 1
    assert all(close_counts[descriptor] == 1 for descriptor in descriptors)
    _assert_root_c2c_poisoned_owner_closed(permit, descriptors)


def test_root_c2d_prewrite_primary_survives_writer_close_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    closure = _root_c2b_consume_with_writer(paths)
    permit = installer.H11RootAuthorizedPermit.publish(closure)
    fifo = _root_c2d_permit_fifo(permit)
    descriptors = _root_c2c_owned_descriptors(permit)
    payloads: list[bytes] = []
    peer_errors: list[BaseException] = []
    entered = threading.Event()
    peer = threading.Thread(
        target=_root_c2d_read_permit_frame,
        args=(fifo, entered, payloads, peer_errors),
    )
    peer.start()
    entered.wait()
    real_close = os.close
    original_endpoint = fifo.open_permit_commit_writer
    original_write = os.write
    writer_descriptor = -1
    close_counts: dict[int, int] = {}
    primary_error = RuntimeError("injected pre-linearization write failure")
    writer_error = OSError(errno.EIO, "injected writer close failure")

    def capture_endpoint(*, require_root: bool) -> int:
        nonlocal writer_descriptor
        writer_descriptor = original_endpoint(require_root=require_root)
        return writer_descriptor

    def fail_before_write(descriptor: int, payload: bytes) -> int:
        if payload == installer.H11_PERMIT_COMMITTED_BYTES:
            raise primary_error
        return original_write(descriptor, payload)

    def close_then_fail(descriptor: int) -> None:
        close_counts[descriptor] = close_counts.get(descriptor, 0) + 1
        real_close(descriptor)
        if descriptor == writer_descriptor:
            raise writer_error

    monkeypatch.setattr(fifo, "open_permit_commit_writer", capture_endpoint)
    monkeypatch.setattr(os, "write", fail_before_write)
    monkeypatch.setattr(os, "close", close_then_fail)
    result: dict[str, installer.H11RootCommitReceipt] = {}
    with pytest.raises(RuntimeError) as caught:
        result["receipt"] = installer._commit_h11_authorized_permit(permit)
    peer.join()
    assert caught.value is primary_error
    assert result == {}
    assert peer_errors == []
    assert payloads == [b""]
    assert primary_error.__notes__ == [
        "H11 ownership teardown secondary: "
        f"{type(writer_error).__name__}: {writer_error}"
    ]
    assert len(set(descriptors)) == len(descriptors)
    assert close_counts[writer_descriptor] == 1
    assert all(close_counts[descriptor] == 1 for descriptor in descriptors)
    _assert_root_c2c_poisoned_owner_closed(permit, descriptors)


def test_root_c2d_duplicate_commit_rejects_before_endpoint_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    closure = _root_c2b_consume_with_writer(paths)
    permit = installer.H11RootAuthorizedPermit.publish(closure)
    fifo = _root_c2d_permit_fifo(permit)
    entered = threading.Event()
    payloads: list[bytes] = []
    errors: list[BaseException] = []
    peer = threading.Thread(
        target=_root_c2d_read_permit_frame,
        args=(fifo, entered, payloads, errors),
    )
    peer.start()
    entered.wait()
    installer._commit_h11_authorized_permit(permit)
    peer.join()
    assert errors == []
    opens: list[bool] = []
    monkeypatch.setattr(
        installer.RetainedH11RootFifo,
        "open_permit_commit_writer",
        lambda self, *, require_root: opens.append(require_root),
    )
    with pytest.raises(installer.InstallerError, match="another commit"):
        installer._commit_h11_authorized_permit(permit)
    assert opens == []
    assert permit.poisoned is True


def _root_c2d_public_fifo_peer(
    paths: dict[str, Path],
    frames: list[bytes],
    errors: list[BaseException],
) -> None:
    root = paths["authorization"].parents[3]
    ready_path = root / "fifo" / "h11-ready-committed.fifo"
    permit_path = root / "fifo" / "h11-permit-committed.fifo"
    descriptor = -1
    try:
        descriptor = os.open(ready_path, os.O_WRONLY | os.O_CLOEXEC)
        if os.write(descriptor, installer.H11_READY_COMMITTED_BYTES) != len(
            installer.H11_READY_COMMITTED_BYTES
        ):
            raise AssertionError("public READY peer write was incomplete")
        os.close(descriptor)
        descriptor = os.open(permit_path, os.O_RDONLY | os.O_CLOEXEC)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, select.PIPE_BUF)
            if not chunk:
                break
            chunks.append(chunk)
        frames.append(b"".join(chunks))
    except BaseException as exc:
        errors.append(exc)
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _root_c2e_atomic_flow_distribution_model(
    tmp_path: Path,
    *,
    n_input: int,
) -> tuple[dict[str, Path], tuple[str, ...]]:
    assert n_input in range(11)
    paths = _root_c2a_session_model(tmp_path)
    future_roles = (
        "closer-properties",
        "exec-stop-post-properties",
        "final",
        "final-closer-properties",
        "final-run-properties",
        "h12-absence",
        "journal",
        "manager-events",
        "signals",
        "source-selector",
    )
    manifest = json.loads(paths["manifest"].read_text(encoding="ascii"))
    input_root = Path(manifest["input_root"])
    receipt_root = Path(manifest["receipt_root"])
    for ordinal, role in enumerate(future_roles):
        matches = tuple(
            row for row in manifest["outputs"] if row["role"] == role
        )
        assert len(matches) == 1
        matches[0]["path"] = str(
            (input_root if ordinal < n_input else receipt_root)
            / f"{role}.json"
        )
    future_inventory = [
        {
            "role": role,
            "path": next(
                row["path"]
                for row in manifest["outputs"]
                if row["role"] == role
            ),
        }
        for role in future_roles
    ]
    future_inventory.append(
        {
            "role": "frozen-root",
            "path": str(paths["authorization"].parents[3] / "frozen"),
        }
    )
    future_inventory.sort(key=lambda row: row["role"])
    manifest["permit_authority"]["future_absence_inventory"] = (
        future_inventory
    )
    _root_c2a_write_json(paths["manifest"], manifest)

    ready = json.loads(paths["ready"].read_text(encoding="ascii"))
    ready["permit_authority"] = manifest["permit_authority"]
    ready["absent_paths"] = future_inventory
    _root_c2a_write_json(paths["ready"], ready)
    _root_c2a_rebind_sources(paths)

    reparsed_manifest = json.loads(
        paths["manifest"].read_text(encoding="ascii")
    )
    reparsed_ready = json.loads(paths["ready"].read_text(encoding="ascii"))
    reparsed_authorization = json.loads(
        paths["authorization"].read_text(encoding="ascii")
    )
    assert reparsed_manifest["permit_authority"] == reparsed_ready[
        "permit_authority"
    ]
    assert reparsed_manifest["permit_authority"][
        "future_absence_inventory"
    ] == reparsed_ready["absent_paths"]
    assert reparsed_ready["harness_manifest"] == _root_c2a_full_reference(
        paths["manifest"]
    )
    assert reparsed_authorization[
        "harness_manifest"
    ] == _root_c2a_full_reference(paths["manifest"])
    assert reparsed_authorization["permit_ready"] == _root_c2a_full_reference(
        paths["ready"]
    )
    return paths, future_roles


@pytest.mark.parametrize("n_input", range(11))
def test_root_c2e_atomic_flow_future_parent_distribution_e2e(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    n_input: int,
) -> None:
    paths, future_roles = _root_c2e_atomic_flow_distribution_model(
        tmp_path,
        n_input=n_input,
    )
    manifest = json.loads(paths["manifest"].read_text(encoding="ascii"))
    manifest_role_paths = tuple(
        (row["role"], Path(row["path"])) for row in manifest["outputs"]
    )
    assert tuple(role for role, _path in manifest_role_paths) == (
        "closer-properties",
        "exec-stop-post-properties",
        "final",
        "final-closer-properties",
        "final-run-properties",
        "h0",
        "h12-absence",
        "journal",
        "manager-events",
        "run-main-properties",
        "signals",
        "source-selector",
    )
    future_role_paths = tuple(
        (
            role,
            next(path for item_role, path in manifest_role_paths if item_role == role),
        )
        for role in future_roles
    )
    present_role_paths = tuple(
        (
            role,
            next(path for item_role, path in manifest_role_paths if item_role == role),
        )
        for role in ("h0", "run-main-properties")
    )
    frames: list[bytes] = []
    errors: list[BaseException] = []
    peer = threading.Thread(
        target=_root_c2d_public_fifo_peer,
        args=(paths, frames, errors),
    )
    peer.start()
    flow = installer.H11RootAuthorizationFlow(
        paths["authorization"],
        require_root=False,
    )
    future_leaf_roles = {
        path.name: role for role, path in future_role_paths
    }
    future_stat_calls: list[
        tuple[str, str, int | None, str, int | None]
    ] = []
    input_ordinal = 0
    receipt_ordinal = 0
    original_stat = os.stat

    def recording_stat(
        path: os.PathLike[str] | str | bytes,
        *args: Any,
        **kwargs: Any,
    ) -> os.stat_result:
        nonlocal input_ordinal, receipt_ordinal
        path_text = os.fsdecode(path)
        dir_fd = kwargs.get("dir_fd")
        slot_index = next(
            (
                index
                for index in (15, 11, 10)
                if flow._slots[index]._descriptor >= 0
                and dir_fd == flow._slots[index]._descriptor
            ),
            None,
        )
        if path_text == "frozen" or path_text in future_leaf_roles:
            role = (
                "frozen-root"
                if path_text == "frozen"
                else future_leaf_roles[path_text]
            )
            if slot_index == 15:
                future_stat_calls.append(
                    (role, path_text, slot_index, "frozen", None)
                )
            elif slot_index == 11:
                future_stat_calls.append(
                    (role, path_text, slot_index, "input", input_ordinal)
                )
                input_ordinal += 1
            elif slot_index == 10:
                future_stat_calls.append(
                    (role, path_text, slot_index, "receipt", receipt_ordinal)
                )
                receipt_ordinal += 1
            else:
                future_stat_calls.append(
                    (role, path_text, slot_index, "unexpected", None)
                )
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(os, "stat", recording_stat)
    receipt = flow.authorize_once()
    peer.join()

    assert errors == []
    assert frames == [installer.H11_PERMIT_COMMITTED_BYTES]
    assert type(receipt) is installer.H11RootCommitReceipt
    assert receipt.phase == "permit-committed"
    assert flow.state is installer.H11RootAuthorizationState.COMPLETE
    assert type(flow._phase_data) is installer.H11RootPermitPhaseData
    partition = flow._phase_data.ready_data.partition
    assert type(partition) is installer.H11RootClosedPartition
    assert tuple(partition.__dataclass_fields__) == (
        "present_prerequisites",
        "future_absence_inventory",
        "frozen_root",
        "input_future_absence",
        "receipt_future_absence",
    )
    assert type(partition.present_prerequisites) is tuple
    assert type(partition.future_absence_inventory) is tuple
    assert type(partition.input_future_absence) is tuple
    assert type(partition.receipt_future_absence) is tuple
    assert tuple(item.role for item in partition.present_prerequisites) == (
        "h0",
        "run-main-properties",
    )
    assert tuple(
        (item.role, item.path) for item in partition.present_prerequisites
    ) == present_role_paths
    assert tuple(item.role for item in partition.future_absence_inventory) == (
        "closer-properties",
        "exec-stop-post-properties",
        "final",
        "final-closer-properties",
        "final-run-properties",
        "frozen-root",
        "h12-absence",
        "journal",
        "manager-events",
        "signals",
        "source-selector",
    )
    assert partition.frozen_root is partition.future_absence_inventory[5]
    output_inventory = (
        partition.future_absence_inventory[:5]
        + partition.future_absence_inventory[6:]
    )
    assert tuple(
        (item.role, item.path) for item in output_inventory
    ) == future_role_paths
    assert tuple(
        (item.role, item.path) for item in partition.input_future_absence
    ) == future_role_paths[:n_input]
    assert tuple(
        (item.role, item.path) for item in partition.receipt_future_absence
    ) == future_role_paths[n_input:]
    assert len(partition.input_future_absence) + len(
        partition.receipt_future_absence
    ) == 10
    projected = (
        partition.input_future_absence + partition.receipt_future_absence
    )
    assert all(
        projected[ordinal] is output_inventory[ordinal]
        for ordinal in range(10)
    )
    assert all(
        item.path.parent == Path(manifest["input_root"])
        for item in partition.input_future_absence
    )
    assert all(
        item.path.parent == Path(manifest["receipt_root"])
        for item in partition.receipt_future_absence
    )
    assert partition.frozen_root.path == (
        paths["authorization"].parents[3] / "frozen"
    )
    expected_future_stat_calls = (
        ("frozen-root", "frozen", 15, "frozen", None),
        *(
            (role, path.name, 11, "input", ordinal)
            for ordinal, (role, path) in enumerate(
                future_role_paths[:n_input]
            )
        ),
        *(
            (role, path.name, 10, "receipt", ordinal)
            for ordinal, (role, path) in enumerate(
                future_role_paths[n_input:]
            )
        ),
    )
    assert len(future_stat_calls) == 11
    assert tuple(future_stat_calls) == expected_future_stat_calls
    assert all(slot._descriptor == -1 for slot in flow._slots)


def _root_c2e_atomic_flow_ready_only_peer(
    paths: dict[str, Path],
    errors: list[BaseException],
) -> None:
    ready_path = (
        paths["authorization"].parents[3]
        / "fifo"
        / "h11-ready-committed.fifo"
    )
    descriptor = -1
    try:
        descriptor = os.open(ready_path, os.O_WRONLY | os.O_CLOEXEC)
        if os.write(descriptor, installer.H11_READY_COMMITTED_BYTES) != len(
            installer.H11_READY_COMMITTED_BYTES
        ):
            raise AssertionError("atomic Flow READY peer write was incomplete")
    except BaseException as exc:
        errors.append(exc)
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def test_root_c2e_atomic_flow_rejects_same_parent_decoy_future_leaf(
    tmp_path: Path,
) -> None:
    paths, _future_roles = _root_c2e_atomic_flow_distribution_model(
        tmp_path,
        n_input=0,
    )
    ready = json.loads(paths["ready"].read_text(encoding="ascii"))
    original = Path(ready["absent_paths"][0]["path"])
    decoy = original.with_name(f"decoy-{original.name}")
    assert decoy.parent == original.parent
    ready["absent_paths"][0]["path"] = str(decoy)
    _root_c2a_write_json(paths["ready"], ready)
    _root_c2a_rebind_sources(paths)

    peer_errors: list[BaseException] = []
    peer = threading.Thread(
        target=_root_c2e_atomic_flow_ready_only_peer,
        args=(paths, peer_errors),
    )
    peer.start()
    flow = installer.H11RootAuthorizationFlow(
        paths["authorization"],
        require_root=False,
    )
    with pytest.raises(
        installer.InstallerError,
        match="future inventory differs from sealed authority",
    ):
        flow.authorize_once()
    peer.join()
    assert peer_errors == []
    assert flow.state is installer.H11RootAuthorizationState.FAILED_PREWRITE
    assert all(slot._descriptor == -1 for slot in flow._slots)
    assert not (paths["authorization"].parent / "PERMIT.json").exists()


@pytest.mark.parametrize("failure_kind", ("missing", "exists", "oserror"))
@pytest.mark.parametrize("target_index", range(11))
@pytest.mark.parametrize("n_input", range(11))
def test_root_c2e_atomic_flow_future_stat_focused_faults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    n_input: int,
    target_index: int,
    failure_kind: str,
) -> None:
    paths, future_roles = _root_c2e_atomic_flow_distribution_model(
        tmp_path,
        n_input=n_input,
    )
    manifest = json.loads(paths["manifest"].read_text(encoding="ascii"))
    future_role_paths = tuple(
        (
            role,
            Path(
                next(
                    row["path"]
                    for row in manifest["outputs"]
                    if row["role"] == role
                )
            ),
        )
        for role in future_roles
    )
    global_ordinals = (0, 1, 2, 3, 4, 6, 7, 8, 9, 10)
    expected_identities = (
        (
            "FUTURE_FROZEN_SLOT15",
            "frozen-root",
            15,
            "frozen",
            None,
            5,
        ),
        *(
            (
                "FUTURE_INPUT_SLOT11",
                role,
                11,
                "input",
                ordinal,
                global_ordinals[ordinal],
            )
            for ordinal, (role, _path) in enumerate(
                future_role_paths[:n_input]
            )
        ),
        *(
            (
                "FUTURE_RECEIPT_SLOT10",
                role,
                10,
                "receipt",
                ordinal,
                global_ordinals[ordinal + n_input],
            )
            for ordinal, (role, _path) in enumerate(
                future_role_paths[n_input:]
            )
        ),
    )
    expected_leaves = (
        "frozen",
        *(path.name for _role, path in future_role_paths[:n_input]),
        *(path.name for _role, path in future_role_paths[n_input:]),
    )
    assert len(expected_identities) == len(expected_leaves) == 11
    assert {row[5] for row in expected_identities} == set(range(11))

    flow = installer.H11RootAuthorizationFlow(
        paths["authorization"],
        require_root=False,
    )
    expected_by_leaf = {
        leaf: (identity[1], identity[5])
        for identity, leaf in zip(expected_identities, expected_leaves)
    }
    actual_identities: list[
        tuple[str, str, int | None, str, int | None, int]
    ] = []
    actual_leaves: list[str] = []
    stat_after_target: list[tuple[str, int | None]] = []
    target_state: installer.H11RootAuthorizationState | None = None
    target_bitmap: tuple[bool, ...] | None = None
    target_descriptors: tuple[int, ...] | None = None
    target_fired = False
    input_ordinal = 0
    receipt_ordinal = 0
    primary_error = OSError(errno.EIO, "focused future stat failure")
    missing_error = FileNotFoundError(
        errno.ENOENT,
        "focused future stat expected absence",
    )
    original_stat = os.stat
    close_counts: dict[int, int] = {}
    original_close = os.close

    def focused_stat(
        path: os.PathLike[str] | str | bytes,
        *args: Any,
        **kwargs: Any,
    ) -> os.stat_result:
        nonlocal input_ordinal, receipt_ordinal
        nonlocal target_bitmap, target_descriptors, target_fired, target_state
        path_text = os.fsdecode(path)
        dir_fd = kwargs.get("dir_fd")
        if target_fired:
            stat_after_target.append((path_text, dir_fd))
        slot_index = next(
            (
                index
                for index in (15, 11, 10)
                if flow._slots[index]._descriptor >= 0
                and dir_fd == flow._slots[index]._descriptor
            ),
            None,
        )
        if path_text in expected_by_leaf:
            role, global_ordinal = expected_by_leaf[path_text]
            if slot_index == 15:
                static_site = "FUTURE_FROZEN_SLOT15"
                partition_kind = "frozen"
                partition_ordinal = None
            elif slot_index == 11:
                static_site = "FUTURE_INPUT_SLOT11"
                partition_kind = "input"
                partition_ordinal = input_ordinal
                input_ordinal += 1
            elif slot_index == 10:
                static_site = "FUTURE_RECEIPT_SLOT10"
                partition_kind = "receipt"
                partition_ordinal = receipt_ordinal
                receipt_ordinal += 1
            else:
                static_site = "UNEXPECTED"
                partition_kind = "unexpected"
                partition_ordinal = None
            actual_identities.append(
                (
                    static_site,
                    role,
                    slot_index,
                    partition_kind,
                    partition_ordinal,
                    global_ordinal,
                )
            )
            actual_leaves.append(path_text)
            if len(actual_identities) - 1 == target_index:
                target_fired = True
                target_state = flow.state
                target_bitmap = tuple(
                    slot._descriptor >= 0 for slot in flow._slots
                )
                target_descriptors = tuple(
                    slot._descriptor
                    for slot in flow._slots
                    if slot._descriptor >= 0
                )
                close_counts.clear()
                if failure_kind == "missing":
                    raise missing_error
                if failure_kind == "exists":
                    return os.stat_result(
                        (stat.S_IFREG | 0o444, 0, 0, 1, 0, 0, 0, 0, 0, 0)
                    )
                raise primary_error
        return original_stat(path, *args, **kwargs)

    def counting_close(descriptor: int) -> None:
        close_counts[descriptor] = close_counts.get(descriptor, 0) + 1
        original_close(descriptor)

    monkeypatch.setattr(os, "stat", focused_stat)
    monkeypatch.setattr(os, "close", counting_close)
    frames: list[bytes] = []
    peer_errors: list[BaseException] = []
    peer = threading.Thread(
        target=(
            _root_c2d_public_fifo_peer
            if failure_kind == "missing"
            else _root_c2e_atomic_flow_ready_only_peer
        ),
        args=(
            (paths, frames, peer_errors)
            if failure_kind == "missing"
            else (paths, peer_errors)
        ),
    )
    peer.start()
    if failure_kind == "missing":
        receipt = flow.authorize_once()
        peer.join()
        assert peer_errors == []
        assert frames == [installer.H11_PERMIT_COMMITTED_BYTES]
        assert type(receipt) is installer.H11RootCommitReceipt
        assert receipt.phase == "permit-committed"
        assert target_fired is True
        assert target_state is installer.H11RootAuthorizationState.READY_CONSUMED
        assert target_bitmap == (False, False, False, *(True for _index in range(20)))
        assert target_descriptors is not None
        assert len(target_descriptors) == len(set(target_descriptors)) == 20
        assert tuple(actual_identities) == expected_identities
        assert tuple(actual_leaves) == expected_leaves
        assert flow.state is installer.H11RootAuthorizationState.COMPLETE
        assert (paths["authorization"].parent / "PERMIT.json").is_file()
        assert all(
            close_counts[descriptor] == 1 for descriptor in target_descriptors
        )
    else:
        if failure_kind == "exists":
            with pytest.raises(installer.InstallerError) as propagated:
                flow.authorize_once()
            expected_role = expected_identities[target_index][1]
            assert str(propagated.value) == (
                f"H11 future output {expected_role} exists before permit"
            )
        else:
            with pytest.raises(OSError) as propagated:
                flow.authorize_once()
            assert propagated.value is primary_error
        peer.join()
        assert peer_errors == []
        assert target_fired is True
        assert target_state is installer.H11RootAuthorizationState.READY_CONSUMED
        assert target_bitmap == (False, False, False, *(True for _index in range(20)))
        assert target_descriptors is not None
        assert len(target_descriptors) == len(set(target_descriptors)) == 20
        assert tuple(actual_identities) == expected_identities[: target_index + 1]
        assert tuple(actual_leaves) == expected_leaves[: target_index + 1]
        assert stat_after_target == []
        assert flow.state is installer.H11RootAuthorizationState.FAILED_PREWRITE
        assert all(
            close_counts[descriptor] == 1 for descriptor in target_descriptors
        )
        for leaf in (
            "PERMIT.pending",
            "PERMIT.json",
            "PERMIT-LEDGER.pending",
            "PERMIT-LEDGER.json",
        ):
            assert not (paths["authorization"].parent / leaf).exists()
    assert all(slot._descriptor == -1 for slot in flow._slots)


def test_root_c2d_public_chain_returns_exact_receipt_and_closes_all(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _root_c2a_session_model(tmp_path)
    sessions: list[installer.H11RootAuthorizerSession] = []
    closures: list[installer.H11RootAuthorizerReadyClosure] = []
    permits: list[installer.H11RootAuthorizedPermit] = []
    original_open = installer.H11RootAuthorizerSession.open.__func__
    original_consume = installer.H11RootAuthorizerReadyClosure.consume.__func__
    original_publish = installer.H11RootAuthorizedPermit.publish.__func__

    def capturing_open(
        cls: type[installer.H11RootAuthorizerSession],
        manifest_path: Path,
        *,
        require_root: bool = True,
    ) -> installer.H11RootAuthorizerSession:
        session = original_open(
            cls,
            manifest_path,
            require_root=require_root,
        )
        sessions.append(session)
        return session

    def capturing_consume(
        cls: type[installer.H11RootAuthorizerReadyClosure],
        session: installer.H11RootAuthorizerSession,
    ) -> installer.H11RootAuthorizerReadyClosure:
        closure = original_consume(cls, session)
        closures.append(closure)
        return closure

    def capturing_publish(
        cls: type[installer.H11RootAuthorizedPermit],
        closure: installer.H11RootAuthorizerReadyClosure,
    ) -> installer.H11RootAuthorizedPermit:
        permit = original_publish(cls, closure)
        permits.append(permit)
        return permit

    monkeypatch.setattr(
        installer.H11RootAuthorizerSession,
        "open",
        classmethod(capturing_open),
    )
    monkeypatch.setattr(
        installer.H11RootAuthorizerReadyClosure,
        "consume",
        classmethod(capturing_consume),
    )
    monkeypatch.setattr(
        installer.H11RootAuthorizedPermit,
        "publish",
        classmethod(capturing_publish),
    )
    frames: list[bytes] = []
    errors: list[BaseException] = []
    peer = threading.Thread(
        target=_root_c2d_public_fifo_peer,
        args=(paths, frames, errors),
    )
    peer.start()
    receipt = installer.authorize_h11_release(
        paths["authorization"],
        require_root=False,
    )
    peer.join()
    assert errors == []
    assert frames == [installer.H11_PERMIT_COMMITTED_BYTES]
    assert receipt == {
        "schema": installer.H11_COMMIT_FIFO_RECEIPT_SCHEMA,
        "phase": "permit-committed",
        "fifo": next(
            item.reference.reference
            for item in sessions[0].authority.commit_fifos
            if item.role == "h11-permit-commit"
        ),
        "payload_sha256": hashlib.sha256(
            installer.H11_PERMIT_COMMITTED_BYTES
        ).hexdigest(),
        "byte_count": "30",
    }
    assert capsys.readouterr() == ("", "")
    assert len(sessions) == len(closures) == len(permits) == 1
    permit = permits[0]
    assert permit.closed is True
    assert permit.poisoned is False
    assert permit.publication.descriptor == -1
    assert closures[0].closed is True
    assert sessions[0].authorization.descriptor == -1
    assert sessions[0].permit_ready.descriptor == -1
    assert sessions[0].run_armed.descriptor == -1
    assert sessions[0].authority.manifest_descriptor == -1
    assert all(
        item.descriptor == -1
        for item in sessions[0].authority.bound_sources
    )
    assert all(
        item.descriptor == -1
        for item in sessions[0].authority.directories
    )
    assert all(
        item.descriptor == -1
        for item in sessions[0].authority.commit_fifos
    )


@pytest.mark.parametrize("failure", ("consume", "publish", "commit"))
def test_root_c2d_public_handoff_failure_closes_only_current_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    class FakeOwner:
        def __init__(self) -> None:
            self.close_count = 0

        def close(self) -> None:
            self.close_count += 1

    session = FakeOwner()
    closure = FakeOwner()
    permit = FakeOwner()
    monkeypatch.setattr(
        installer.H11RootAuthorizerSession,
        "open",
        classmethod(lambda cls, path, *, require_root=True: session),
    )

    def consume_owner(cls: Any, owner: Any) -> FakeOwner:
        assert owner is session
        if failure == "consume":
            raise RuntimeError("injected consume handoff failure")
        return closure

    def publish_owner(cls: Any, owner: Any) -> FakeOwner:
        assert owner is closure
        if failure == "publish":
            raise RuntimeError("injected publish handoff failure")
        return permit

    def commit_owner(owner: Any) -> installer.H11RootCommitReceipt:
        assert owner is permit
        raise RuntimeError("injected commit handoff failure")

    monkeypatch.setattr(
        installer.H11RootAuthorizerReadyClosure,
        "consume",
        classmethod(consume_owner),
    )
    monkeypatch.setattr(
        installer.H11RootAuthorizedPermit,
        "publish",
        classmethod(publish_owner),
    )
    monkeypatch.setattr(installer, "_commit_h11_authorized_permit", commit_owner)
    with pytest.raises(RuntimeError, match="handoff failure"):
        installer.authorize_h11_release(
            tmp_path / "AUTHORIZE-RELEASE.json",
            require_root=False,
        )
    expected = {
        "consume": (1, 0, 0),
        "publish": (0, 1, 0),
        "commit": (0, 0, 1),
    }[failure]
    assert (
        session.close_count,
        closure.close_count,
        permit.close_count,
    ) == expected


def test_root_c2d_ast_freezes_commit_and_public_ownership_seams() -> None:
    module_source = Path(installer.__file__).read_text(encoding="utf-8")
    module_tree = ast.parse(module_source)
    assert "_publish_h11_permit" not in module_source
    assert "absent_paths_sha256" not in module_source

    writer_source = inspect.getsource(
        installer.RetainedH11RootFifo.open_permit_commit_writer
    )
    writer_tree = ast.parse(textwrap.dedent(writer_source))
    writer_function = next(
        node
        for node in ast.walk(writer_tree)
        if isinstance(node, ast.FunctionDef)
    )
    writer_try = next(
        node for node in writer_function.body if isinstance(node, ast.Try)
    )
    assert isinstance(writer_try.body[0], ast.Assign)
    writer_open = writer_try.body[0].value
    assert isinstance(writer_open, ast.Call)
    assert ast.unparse(writer_open.func) == "os.open"
    assert ast.unparse(writer_open.args[0]) == (
        "f'/proc/self/fd/{self.descriptor}'"
    )
    assert ast.unparse(writer_open.args[1]) == (
        "os.O_WRONLY | os.O_CLOEXEC"
    )
    assert writer_open.keywords == []
    assert isinstance(writer_try.body[1], ast.Expr)
    assert "os.fstat(descriptor)" in ast.unparse(writer_try.body[1])
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"read", "write", "writev"}
        for node in ast.walk(writer_tree)
    )

    helper_source = inspect.getsource(installer._commit_h11_authorized_permit)
    helper_tree = ast.parse(helper_source)
    helper_function = next(
        node
        for node in ast.walk(helper_tree)
        if isinstance(node, ast.FunctionDef)
    )
    helper_try = next(
        node for node in helper_function.body if isinstance(node, ast.Try)
    )
    write_calls = [
        node
        for node in ast.walk(helper_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and ast.unparse(node.func) == "os.write"
    ]
    assert len(write_calls) == 1
    assert [ast.unparse(item) for item in write_calls[0].args] == [
        "descriptor",
        "H11_PERMIT_COMMITTED_BYTES",
    ]
    assert not any(
        isinstance(node, (ast.For, ast.AsyncFor, ast.While))
        for node in ast.walk(helper_tree)
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "writev"
        for node in ast.walk(helper_tree)
    )
    endpoint_index = next(
        index
        for index, node in enumerate(helper_try.body)
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and ast.unparse(node.value.func) == "fifo.open_permit_commit_writer"
    )
    receipt_index = next(
        index
        for index, node in enumerate(helper_try.body)
        if isinstance(node, ast.Assign)
        and ast.unparse(node.targets[0]) == "receipt"
    )
    assert receipt_index == endpoint_index - 1
    assert ast.unparse(helper_try.body[receipt_index].value) == (
        "H11RootCommitReceipt.permit_committed(fifo, "
        "H11_PERMIT_COMMITTED_BYTES)"
    )
    assert ast.unparse(helper_try.body[endpoint_index + 1]) == (
        "permit.revalidate()"
    )
    assert isinstance(helper_try.body[endpoint_index + 2], ast.Assign)
    assert helper_try.body[endpoint_index + 2].value is write_calls[0]
    assert ast.unparse(helper_try.body[1]) == "permit.commit_started = True"
    assert ast.unparse(helper_try.body[2]) == "permit.revalidate()"
    assert len(helper_try.handlers) == 1
    unwind = helper_try.handlers[0]
    assert ast.unparse(unwind.type) == "BaseException"
    assert unwind.name == "exc"
    assert [ast.unparse(node) for node in unwind.body] == [
        "closing_descriptor = descriptor",
        "descriptor = -1",
        "permit.poisoned = True",
        "_close_h11_ownership((permit,), active_error=exc, "
        "initial_descriptor=closing_descriptor)",
        "raise",
    ]
    assert {
        node.func.id
        for node in ast.walk(helper_tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    } == {"_close_h11_ownership", "_fail", "len", "tuple"}

    public_source = inspect.getsource(installer.authorize_h11_release)
    public_tree = ast.parse(public_source)
    public_function = next(
        node
        for node in ast.walk(public_tree)
        if isinstance(node, ast.FunctionDef)
    )
    public_try = next(
        node for node in public_function.body if isinstance(node, ast.Try)
    )
    public_calls = [
        ast.unparse(node.value.func)
        for node in public_try.body
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
    ]
    assert public_calls == [
        "H11RootAuthorizerSession.open",
        "H11RootAuthorizerReadyClosure.consume",
        "H11RootAuthorizedPermit.publish",
        "_commit_h11_authorized_permit",
    ]
    assert len(public_try.finalbody) == 1
    assert ast.unparse(public_try.finalbody[0]) == (
        "if owner is not None:\n    owner.close()"
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in {"os", "Path"}
        for node in ast.walk(public_tree)
    )

    parents = {
        child: parent
        for parent in ast.walk(module_tree)
        for child in ast.iter_child_nodes(parent)
    }

    def qualified_owner(call: ast.Call) -> str:
        owner = parents[call]
        while not isinstance(owner, (ast.FunctionDef, ast.AsyncFunctionDef)):
            owner = parents[owner]
        scope = parents[owner]
        while not isinstance(scope, (ast.ClassDef, ast.Module)):
            scope = parents[scope]
        if isinstance(scope, ast.ClassDef):
            return f"{scope.name}.{owner.name}"
        return owner.name

    endpoint_callsites = [
        qualified_owner(node)
        for node in ast.walk(module_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "open_permit_commit_writer"
    ]
    commit_callsites = [
        qualified_owner(node)
        for node in ast.walk(module_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_commit_h11_authorized_permit"
    ]
    assert endpoint_callsites == ["_commit_h11_authorized_permit"]
    assert commit_callsites == ["authorize_h11_release"]

    seam_source = "\n".join((writer_source, helper_source, public_source))
    seam_tokens = {
        item.string
        for item in tokenize.generate_tokens(io.StringIO(seam_source).readline)
        if item.type == tokenize.NAME
    }
    assert {
        "O_NONBLOCK",
        "timeout",
        "deadline",
        "poll",
        "sleep",
        "retry",
        "budget",
        "cap",
        "truncate",
        "truncation",
        "watchdog",
        "cleanup",
        "watch",
        "ledger",
        "release",
        "H11_RELEASE_BYTES",
    }.isdisjoint(seam_tokens)


def test_root_c2d_ast_freezes_exhaustive_nonretrying_teardown() -> None:
    teardown_source = inspect.getsource(installer._close_h11_ownership)
    teardown_tree = ast.parse(teardown_source)
    teardown_function = next(
        node
        for node in ast.walk(teardown_tree)
        if isinstance(node, ast.FunctionDef)
    )
    assert [item.arg for item in teardown_function.args.args] == ["owners"]
    assert [item.arg for item in teardown_function.args.kwonlyargs] == [
        "active_error",
        "initial_descriptor",
        "final_descriptor",
    ]
    loops = [
        node for node in ast.walk(teardown_tree) if isinstance(node, ast.For)
    ]
    assert len(loops) == 1
    assert ast.unparse(loops[0].target) == "owner"
    assert ast.unparse(loops[0].iter) == "owners"
    assert not any(
        isinstance(node, (ast.Break, ast.Continue, ast.Return))
        for node in ast.walk(loops[0])
    )
    teardown_calls = [
        ast.unparse(node.func)
        for node in ast.walk(teardown_tree)
        if isinstance(node, ast.Call)
    ]
    assert teardown_calls.count("os.close") == 2
    assert teardown_calls.count("owner.close") == 1
    assert teardown_calls.count("active_error.add_note") == 1
    assert teardown_calls.count("type") == 1
    raises = [
        node for node in ast.walk(teardown_tree) if isinstance(node, ast.Raise)
    ]
    assert len(raises) == 1
    assert ast.unparse(raises[0].exc) == "first_error"
    final_branch = teardown_function.body[-1]
    assert isinstance(final_branch, ast.If)
    assert ast.unparse(final_branch.test) == "first_error is not None"
    assert isinstance(final_branch.body[0], ast.If)
    assert ast.unparse(final_branch.body[0].test) == "active_error is None"
    assert ast.unparse(final_branch.body[1].value.func) == (
        "active_error.add_note"
    )
    assert not any(
        isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign))
        and any(
            isinstance(target, ast.Name) and target.id == "active_error"
            for target in (
                node.targets
                if isinstance(node, ast.Assign)
                else (node.target,)
            )
        )
        for node in ast.walk(teardown_tree)
    )

    expected_composite_calls = {
        installer.H11RootRetainedAuthority: (
            "(*reversed(self.commit_fifos), *reversed(self.directories), "
            "*reversed(self.bound_sources))",
            "descriptor",
        ),
        installer.H11RootAuthorizerSession: (
            "(self.run_armed, self.permit_ready, self.authority, "
            "self.authorization)",
            None,
        ),
        installer.H11RootAuthorizerReadyClosure: (
            "(*reversed(self.present_sources), self.session)",
            None,
        ),
        installer.H11RootAuthorizedPermit: (
            "(self.publication, self.closure)",
            None,
        ),
    }
    for owner_type, (expected_owners, expected_descriptor) in (
        expected_composite_calls.items()
    ):
        close_source = inspect.getsource(owner_type.close)
        close_tree = ast.parse(textwrap.dedent(close_source))
        calls = [
            node
            for node in ast.walk(close_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_close_h11_ownership"
        ]
        assert len(calls) == 1
        call = calls[0]
        assert ast.unparse(call.args[0]) == expected_owners
        keywords = {
            item.arg: ast.unparse(item.value) for item in call.keywords
        }
        assert keywords == (
            {"final_descriptor": expected_descriptor}
            if expected_descriptor is not None
            else {}
        )

    for leaf_type in (
        installer.RetainedH11RootDirectory,
        installer.RetainedH11RootFifo,
        installer.RetainedH11RootJsonSource,
        installer.RetainedH11RootPresentOutput,
        installer.RetainedH11RootPublication,
    ):
        close_source = inspect.getsource(leaf_type.close)
        close_tree = ast.parse(textwrap.dedent(close_source))
        guard = next(
            node for node in ast.walk(close_tree) if isinstance(node, ast.If)
        )
        assert [ast.unparse(node) for node in guard.body] == [
            "descriptor = self.descriptor",
            "self.descriptor = -1",
            "os.close(descriptor)",
        ]
        assert "os.close(self.descriptor)" not in close_source

    rollback_targets = (
        (installer._pin_h11_json_source, 1),
        (installer.RetainedH11RootFifo.read_ready_commit, 1),
        (installer.RetainedH11RootFifo.open_permit_commit_writer, 2),
        (installer.H11RootRetainedAuthority.open, 1),
        (installer.H11RootAuthorizerSession.open, 1),
        (installer.RetainedH11RootPresentOutput.pin, 3),
        (installer.H11RootAuthorizerReadyClosure.consume, 1),
        (installer._complete_h11_named_staging, 1),
        (installer.H11RootAuthorizedPermit.publish, 1),
        (installer.H11RootAuthorizedPermit.revalidate, 1),
        (installer._commit_h11_authorized_permit, 1),
    )
    rollback_sources = [teardown_source]
    for target, expected_count in rollback_targets:
        source = inspect.getsource(target)
        tree = ast.parse(textwrap.dedent(source))
        active_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_close_h11_ownership"
            and any(item.arg == "active_error" for item in node.keywords)
        ]
        assert len(active_calls) == expected_count
        rollback_sources.append(source)

    rollback_tokens = {
        item.string
        for item in tokenize.generate_tokens(
            io.StringIO("\n".join(rollback_sources)).readline
        )
        if item.type == tokenize.NAME
    }
    assert {"callback", "cleanup", "retry"}.isdisjoint(rollback_tokens)


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
