from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest

from scion.problems.warehouse_delivery.w3_environment import (
    RUNTIME_PYTHON,
    WHEEL_INSTALLATION_MANIFEST_PATH,
    WarehouseRuntimeSources,
    WarehouseWheelInstallationInput,
    WarehouseW3EnvironmentError,
    prepare_warehouse_environment,
    verify_warehouse_environment,
)


class FakeRunner:
    def __init__(
        self,
        *,
        hardlink_candidate: bool = False,
        leak_bytes: bytes | None = None,
        manifest_collision: bool = False,
        special_candidate: bool = False,
    ) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.hardlink_candidate = hardlink_candidate
        self.leak_bytes = leak_bytes
        self.manifest_collision = manifest_collision
        self.special_candidate = special_candidate

    def run(self, argv: tuple[str, ...]) -> None:
        self.calls.append(argv)
        if argv[1:5] == ("-m", "venv", "--without-pip", "--copies"):
            root = Path(argv[5])
            (root / "bin").mkdir(parents=True)
            (root / "include" / "python3.12").mkdir(parents=True)
            (root / "lib" / "python3.12" / "site-packages").mkdir(parents=True)
            for name in ("python", "python3", "python3.12"):
                (root / "bin" / name).write_bytes(b"python executable\n")
                (root / "bin" / name).chmod(0o755)
            for name in ("activate", "activate.csh", "activate.fish", "Activate.ps1"):
                (root / "bin" / name).write_text(f"VIRTUAL_ENV={root}\n")
            (root / "lib64").symlink_to("lib")
            (root / "pyvenv.cfg").write_text(
                "home = /usr/bin\n"
                "include-system-site-packages = false\n"
                "version = 3.12.3\n"
                "executable = /usr/bin/python3.12\n"
                f"command = /usr/bin/python3.12 -m venv --without-pip "
                f"--copies {root}\n"
            )
            return
        root = Path(argv[4]).parents[1]
        site = root / "lib" / "python3.12" / "site-packages"
        package = site / "scion"
        dist_info = site / "scion-0.1.0.dist-info"
        package.mkdir()
        dist_info.mkdir()
        payload = (
            self.leak_bytes if self.leak_bytes is not None else b"SCION = 'installed'\n"
        )
        (package / "__init__.py").write_bytes(payload)
        if self.hardlink_candidate:
            os.link(package / "__init__.py", package / "hardlink.py")
        if self.special_candidate:
            os.mkfifo(package / "special")
        cache = package / "__pycache__"
        cache.mkdir()
        (cache / "__init__.cpython-312.pyc").write_bytes(b"bytecode")
        (root / "bin" / "scion").write_text(f"#!{root}/bin/python\n")
        (root / "bin" / "scion").chmod(0o755)
        direct_url = {
            "archive_info": {"hashes": {"sha256": "f" * 64}},
            "url": f"file://{argv[-1]}",
        }
        (dist_info / "direct_url.json").write_text(
            json.dumps(direct_url, sort_keys=True)
        )
        (dist_info / "INSTALLER").write_bytes(b"pip\n")
        (dist_info / "REQUESTED").write_bytes(b"")

        def record_row(relative: str, physical: Path) -> str:
            raw = physical.read_bytes()
            digest = (
                base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
                .rstrip(b"=")
                .decode("ascii")
            )
            return f"{relative},sha256={digest},{len(raw)}\n"

        (dist_info / "RECORD").write_text(
            record_row("../../../bin/scion", root / "bin" / "scion")
            + record_row("scion/__init__.py", package / "__init__.py")
            + record_row(
                f"{dist_info.name}/INSTALLER",
                dist_info / "INSTALLER",
            )
            + record_row(
                f"{dist_info.name}/REQUESTED",
                dist_info / "REQUESTED",
            )
            + f"{dist_info.name}/RECORD,,\n"
            + record_row(
                f"{dist_info.name}/direct_url.json",
                dist_info / "direct_url.json",
            )
        )
        if self.manifest_collision:
            (root / ".scion").mkdir()
            (root / ".scion" / "w3-wheel-installation.json").write_bytes(b"collision\n")


class FakeSmoke:
    def __init__(self, *, mutate: bool = False) -> None:
        self.calls: list[tuple[Path, str]] = []
        self.mutate = mutate

    def probe(self, environment_root: Path, *, phase: str) -> None:
        self.calls.append((environment_root, phase))
        site = environment_root / "lib" / "python3.12" / "site-packages"
        assert (site / "scion" / "__init__.py").is_file()
        assert (site / "dbus" / "__init__.py").is_file()
        assert (site / "yaml" / "__init__.py").is_file()
        if self.mutate:
            target = site / "scion" / "__init__.py"
            target.chmod(0o644)
            target.write_bytes(b"mutated by smoke\n")
            target.chmod(0o444)


@pytest.fixture
def preparation_inputs(
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> dict[str, object]:
    candidate = tmp_path / "candidate"
    selection = tmp_path / ".scion-w3-selections" / ("a" * 64)
    selection.mkdir(parents=True)
    sources = tmp_path / "system-sources"
    dbus = sources / "dbus"
    yaml = sources / "yaml"
    (dbus / "mainloop").mkdir(parents=True)
    (dbus / "__pycache__").mkdir()
    (dbus / "__init__.py").write_bytes(b"DBUS = 'system copy'\n")
    (dbus / "mainloop" / "__init__.py").write_bytes(b"")
    (dbus / "__pycache__" / "__init__.cpython-312.pyc").write_bytes(b"cache")
    yaml.mkdir()
    (yaml / "__init__.py").write_bytes(b"YAML = 'system copy'\n")
    yaml_extension = yaml / "_yaml.cpython-312-x86_64-linux-gnu.so"
    yaml_extension.write_bytes(b"yaml extension")
    dbus_bindings = sources / "_dbus_bindings.cpython-312-x86_64-linux-gnu.so"
    dbus_glib = sources / "_dbus_glib_bindings.cpython-312-x86_64-linux-gnu.so"
    dbus_bindings.write_bytes(b"dbus bindings")
    dbus_glib.write_bytes(b"dbus glib bindings")
    dbus_metadata = sources / "dbus_python-1.3.2.egg-info"
    dbus_metadata.mkdir()
    (dbus_metadata / "PKG-INFO").write_bytes(
        b"Metadata-Version: 2.1\nName: dbus-python\nVersion: 1.3.2\n"
    )
    (dbus_metadata / "top_level.txt").write_bytes(b"_dbus_bindings\ndbus\n")
    yaml_metadata = sources / "PyYAML-6.0.1.dist-info"
    yaml_metadata.mkdir()
    (yaml_metadata / "METADATA").write_bytes(
        b"Metadata-Version: 2.1\nName: PyYAML\nVersion: 6.0.1\n"
    )
    (yaml_metadata / "WHEEL").write_bytes(b"Wheel-Version: 1.0\n")
    (yaml_metadata / "INSTALLER").write_bytes(b"apt\n")
    wheel = tmp_path / "scion.whl"
    wheel.write_bytes(b"exact wheel bytes")
    wheel_sha256 = hashlib.sha256(wheel.read_bytes()).hexdigest()
    external = tmp_path / "external-runtime"
    external.write_bytes(b"external runtime bytes")
    external.chmod(0o444)

    def restore_writable() -> None:
        for directory in sorted(
            (item for item in tmp_path.rglob("*") if item.is_dir()),
            key=lambda item: len(item.parts),
        ):
            directory.chmod(0o755)
        for item in tmp_path.rglob("*"):
            if item.is_file():
                item.chmod(0o644)

    request.addfinalizer(restore_writable)
    return {
        "candidate": candidate,
        "environment": tmp_path / "built-environment",
        "selection": selection,
        "wheel": wheel,
        "wheel_sha256": wheel_sha256,
        "wheel_installation": WarehouseWheelInstallationInput(
            wheel_receipt_sha256="e" * 64,
            wheel_sha256=wheel_sha256,
            wheel_member_paths=(
                "scion-0.1.0.dist-info/RECORD",
                "scion/__init__.py",
            ),
        ),
        "external": external,
        "runtime_sources": WarehouseRuntimeSources(
            dbus_package=dbus,
            dbus_bindings=dbus_bindings,
            dbus_glib_bindings=dbus_glib,
            dbus_metadata=dbus_metadata,
            yaml_package=yaml,
            yaml_metadata=yaml_metadata,
        ),
    }


def _prepare(
    inputs: dict[str, object],
    *,
    runner: FakeRunner | None = None,
    smoke: FakeSmoke | None = None,
):
    actual_runner = FakeRunner() if runner is None else runner
    actual_smoke = FakeSmoke() if smoke is None else smoke
    build = prepare_warehouse_environment(
        inputs["environment"],
        wheel_path=inputs["wheel"],
        wheel_sha256=inputs["wheel_sha256"],
        wheel_installation=inputs["wheel_installation"],
        runtime_sources=inputs["runtime_sources"],
        external_runtime_paths=(inputs["external"],),
        candidate_root=inputs["candidate"],
        selection_root=inputs["selection"],
        runner=actual_runner,
        smoke_probe=actual_smoke,
    )
    return build, actual_runner, actual_smoke


def test_prepare_uses_exact_offline_commands_and_freezes_environment(
    preparation_inputs: dict[str, object],
) -> None:
    build, runner, smoke = _prepare(preparation_inputs)
    environment = preparation_inputs["environment"]
    wheel = preparation_inputs["wheel"]

    assert runner.calls == [
        (
            RUNTIME_PYTHON,
            "-m",
            "venv",
            "--without-pip",
            "--copies",
            str(environment),
        ),
        (
            RUNTIME_PYTHON,
            "-m",
            "pip",
            "--python",
            f"{environment}/bin/python",
            "install",
            "--no-compile",
            "--no-deps",
            "--no-index",
            str(wheel),
        ),
    ]
    assert smoke.calls == [(environment, "staging")]
    assert build.venv_argv == runner.calls[0]
    assert build.install_argv == runner.calls[1]
    assert build.receipt.raw_sha256
    assert not (environment / "bin" / "activate").exists()
    assert not (environment / "bin" / "scion").exists()
    assert not (environment / "lib64").exists()
    assert not tuple(environment.rglob("__pycache__"))
    assert not tuple(environment.rglob("*.pyc"))
    assert (
        environment
        / "lib"
        / "python3.12"
        / "site-packages"
        / "_dbus_bindings.cpython-312-x86_64-linux-gnu.so"
    ).is_file()
    assert (
        environment
        / "lib"
        / "python3.12"
        / "site-packages"
        / "yaml"
        / "_yaml.cpython-312-x86_64-linux-gnu.so"
    ).is_file()
    assert (
        (
            environment
            / "lib"
            / "python3.12"
            / "site-packages"
            / "dbus_python-1.3.2.egg-info"
            / "PKG-INFO"
        )
        .read_bytes()
        .endswith(b"Version: 1.3.2\n")
    )
    assert (
        environment
        / "lib"
        / "python3.12"
        / "site-packages"
        / "PyYAML-6.0.1.dist-info"
        / "INSTALLER"
    ).read_bytes() == b"apt\n"
    installation = json.loads(
        (environment / WHEEL_INSTALLATION_MANIFEST_PATH).read_bytes()
    )
    assert installation["schema"] == "scion.w3-wheel-installation-map.v1"
    assert installation["wheel_receipt_sha256"] == "e" * 64
    assert tuple(
        item["wheel_member_path"] for item in installation["installed_members"]
    ) == (
        "scion-0.1.0.dist-info/RECORD",
        "scion/__init__.py",
    )
    assert b"command = " not in (environment / "pyvenv.cfg").read_bytes()
    dist_info = (
        environment / "lib" / "python3.12" / "site-packages" / "scion-0.1.0.dist-info"
    )
    assert not (dist_info / "direct_url.json").exists()
    record = (dist_info / "RECORD").read_text()
    assert "bin/scion" not in record
    assert "direct_url.json" not in record
    assert stat_mode(environment) == 0o555
    assert stat_mode(environment / "bin" / "python") == 0o555
    assert (
        stat_mode(
            environment
            / "lib"
            / "python3.12"
            / "site-packages"
            / "scion"
            / "__init__.py"
        )
        == 0o444
    )


def stat_mode(path: Path) -> int:
    return os.stat(path, follow_symlinks=False).st_mode & 0o7777


def test_verify_exposes_candidate_and_relocation_smoke_seam(
    preparation_inputs: dict[str, object],
    tmp_path: Path,
) -> None:
    build, _runner, _smoke = _prepare(preparation_inputs)
    candidate_environment = preparation_inputs["candidate"] / "environment"
    candidate_environment.parent.mkdir()
    shutil.copytree(preparation_inputs["environment"], candidate_environment)
    relocation_environment = (
        tmp_path
        / "var"
        / "lib"
        / "scion"
        / "environments"
        / "w3"
        / build.receipt.raw_sha256
    )
    relocation_environment.parent.mkdir(parents=True)
    shutil.copytree(preparation_inputs["environment"], relocation_environment)
    smoke = FakeSmoke()

    verify_warehouse_environment(
        candidate_environment,
        build.receipt,
        wheel_path=preparation_inputs["wheel"],
        wheel_sha256=preparation_inputs["wheel_sha256"],
        external_runtime_paths=(preparation_inputs["external"],),
        candidate_root=preparation_inputs["candidate"],
        selection_root=preparation_inputs["selection"],
        smoke_probe=smoke,
        smoke_phase="candidate",
    )
    verify_warehouse_environment(
        relocation_environment,
        build.receipt,
        wheel_path=preparation_inputs["wheel"],
        wheel_sha256=preparation_inputs["wheel_sha256"],
        external_runtime_paths=(preparation_inputs["external"],),
        candidate_root=preparation_inputs["candidate"],
        selection_root=preparation_inputs["selection"],
        smoke_probe=smoke,
        smoke_phase="relocation",
    )

    assert smoke.calls == [
        (candidate_environment, "candidate"),
        (relocation_environment, "relocation"),
    ]


def test_receipt_binds_copied_runtime_version_metadata(
    preparation_inputs: dict[str, object],
) -> None:
    build, _runner, _smoke = _prepare(preparation_inputs)
    metadata = (
        preparation_inputs["environment"]
        / "lib"
        / "python3.12"
        / "site-packages"
        / "dbus_python-1.3.2.egg-info"
        / "PKG-INFO"
    )
    metadata.chmod(0o644)
    metadata.write_bytes(
        b"Metadata-Version: 2.1\nName: dbus-python\nVersion: changed\n"
    )
    metadata.chmod(0o444)

    with pytest.raises(WarehouseW3EnvironmentError, match="integrity differs"):
        verify_warehouse_environment(
            preparation_inputs["environment"],
            build.receipt,
            wheel_path=preparation_inputs["wheel"],
            wheel_sha256=preparation_inputs["wheel_sha256"],
            external_runtime_paths=(preparation_inputs["external"],),
            candidate_root=preparation_inputs["candidate"],
            selection_root=preparation_inputs["selection"],
            smoke_probe=FakeSmoke(),
            smoke_phase="candidate",
        )


def test_builder_rejects_candidate_path_leak(
    preparation_inputs: dict[str, object],
) -> None:
    with pytest.raises(
        WarehouseW3EnvironmentError,
        match="integrity differs",
    ):
        _prepare(
            preparation_inputs,
            runner=FakeRunner(
                leak_bytes=str(preparation_inputs["candidate"]).encode(),
            ),
        )


def test_builder_rejects_candidate_hardlink(
    preparation_inputs: dict[str, object],
) -> None:
    with pytest.raises(WarehouseW3EnvironmentError, match="multiply linked"):
        _prepare(
            preparation_inputs,
            runner=FakeRunner(hardlink_candidate=True),
        )


def test_builder_rejects_candidate_special_file(
    preparation_inputs: dict[str, object],
) -> None:
    with pytest.raises(WarehouseW3EnvironmentError, match="special file"):
        _prepare(
            preparation_inputs,
            runner=FakeRunner(special_candidate=True),
        )


def test_builder_rejects_preexisting_installation_manifest(
    preparation_inputs: dict[str, object],
) -> None:
    with pytest.raises(
        WarehouseW3EnvironmentError,
        match="manifest cannot be published",
    ):
        _prepare(
            preparation_inputs,
            runner=FakeRunner(manifest_collision=True),
        )


def test_builder_rejects_runtime_source_symlink(
    preparation_inputs: dict[str, object],
) -> None:
    sources = preparation_inputs["runtime_sources"]
    link = sources.dbus_package / "link.py"
    link.symlink_to("__init__.py")

    with pytest.raises(
        WarehouseW3EnvironmentError,
        match="runtime package contains a symlink",
    ):
        _prepare(preparation_inputs)


def test_builder_rejects_wrong_wheel_before_runner(
    preparation_inputs: dict[str, object],
) -> None:
    runner = FakeRunner()
    with pytest.raises(WarehouseW3EnvironmentError, match="wheel SHA-256 differs"):
        prepare_warehouse_environment(
            preparation_inputs["environment"],
            wheel_path=preparation_inputs["wheel"],
            wheel_sha256="0" * 64,
            wheel_installation=preparation_inputs["wheel_installation"],
            runtime_sources=preparation_inputs["runtime_sources"],
            external_runtime_paths=(preparation_inputs["external"],),
            candidate_root=preparation_inputs["candidate"],
            selection_root=preparation_inputs["selection"],
            runner=runner,
            smoke_probe=FakeSmoke(),
        )
    assert runner.calls == []


def test_builder_rejects_effective_uid_zero_before_runner(
    preparation_inputs: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = FakeRunner()
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    with pytest.raises(WarehouseW3EnvironmentError, match="effective UID zero"):
        prepare_warehouse_environment(
            preparation_inputs["environment"],
            wheel_path=preparation_inputs["wheel"],
            wheel_sha256=preparation_inputs["wheel_sha256"],
            wheel_installation=preparation_inputs["wheel_installation"],
            runtime_sources=preparation_inputs["runtime_sources"],
            external_runtime_paths=(preparation_inputs["external"],),
            candidate_root=preparation_inputs["candidate"],
            selection_root=preparation_inputs["selection"],
            runner=runner,
            smoke_probe=FakeSmoke(),
        )
    assert runner.calls == []


def test_builder_staging_root_cannot_overlap_candidate_or_selection(
    preparation_inputs: dict[str, object],
) -> None:
    for environment_root in (
        preparation_inputs["candidate"] / "environment",
        preparation_inputs["selection"] / "environment",
    ):
        runner = FakeRunner()
        with pytest.raises(WarehouseW3EnvironmentError, match="overlaps"):
            prepare_warehouse_environment(
                environment_root,
                wheel_path=preparation_inputs["wheel"],
                wheel_sha256=preparation_inputs["wheel_sha256"],
                wheel_installation=preparation_inputs["wheel_installation"],
                runtime_sources=preparation_inputs["runtime_sources"],
                external_runtime_paths=(preparation_inputs["external"],),
                candidate_root=preparation_inputs["candidate"],
                selection_root=preparation_inputs["selection"],
                runner=runner,
                smoke_probe=FakeSmoke(),
            )
        assert runner.calls == []


def test_verify_uses_only_caller_closed_external_runtime_paths(
    preparation_inputs: dict[str, object],
    tmp_path: Path,
) -> None:
    build, _runner, _smoke = _prepare(preparation_inputs)
    alternate = tmp_path / "alternate-runtime"
    alternate.write_bytes(b"alternate")
    alternate.chmod(0o444)

    with pytest.raises(WarehouseW3EnvironmentError, match="integrity differs"):
        verify_warehouse_environment(
            preparation_inputs["environment"],
            build.receipt,
            wheel_path=preparation_inputs["wheel"],
            wheel_sha256=preparation_inputs["wheel_sha256"],
            external_runtime_paths=(alternate,),
            candidate_root=preparation_inputs["candidate"],
            selection_root=preparation_inputs["selection"],
            smoke_probe=FakeSmoke(),
            smoke_phase="candidate",
        )


def test_smoke_mutation_is_detected_by_post_probe_rehash(
    preparation_inputs: dict[str, object],
) -> None:
    with pytest.raises(WarehouseW3EnvironmentError, match="integrity differs"):
        _prepare(
            preparation_inputs,
            smoke=FakeSmoke(mutate=True),
        )
