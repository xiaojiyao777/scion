"""Non-root Warehouse W3 candidate-environment preparation.

This module owns only the fixed offline venv/install/copy/normalization
sequence.  Its production entrypoint uses fixed command and probe adapters;
the lower-level builder retains narrow caller-supplied seams for tests.
"""

from __future__ import annotations

import csv
import hashlib
import io
import os
import re
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol

from scion.runtime.execution.environment_integrity import (
    EnvironmentContentReceipt,
    EnvironmentIntegrityError,
    verify_environment_content,
)

RUNTIME_PYTHON = "/usr/bin/python3.12"
_SITE_PACKAGES = PurePosixPath("lib/python3.12/site-packages")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_DBUS_BINDINGS_RE = re.compile(r"_dbus_bindings\.cpython-312-[A-Za-z0-9_.-]+\.so\Z")
_DBUS_GLIB_BINDINGS_RE = re.compile(
    r"_dbus_glib_bindings\.cpython-312-[A-Za-z0-9_.-]+\.so\Z"
)
_YAML_BINDINGS_RE = re.compile(r"_yaml\.cpython-312-[A-Za-z0-9_.-]+\.so\Z")
_DBUS_METADATA_RE = re.compile(r"dbus_python-[A-Za-z0-9][A-Za-z0-9.!+_-]*\.egg-info\Z")
_YAML_METADATA_RE = re.compile(r"PyYAML-[A-Za-z0-9][A-Za-z0-9.!+_-]*\.dist-info\Z")
_ACTIVATION_NAMES = (
    "activate",
    "activate.csh",
    "activate.fish",
    "Activate.ps1",
)
_READ_SIZE = 1024 * 1024


class WarehouseW3EnvironmentError(RuntimeError):
    """The fixed non-root W3 environment transaction is invalid."""


class EnvironmentCommandRunner(Protocol):
    """The complete command surface used by the environment builder."""

    def run(self, argv: tuple[str, ...]) -> None:
        """Run one exact argv and raise on any nonzero or ambiguous result."""


class EnvironmentSmokeProbe(Protocol):
    """A caller-owned, read-only import/relocation smoke seam."""

    def probe(self, environment_root: Path, *, phase: str) -> None:
        """Verify one exact environment at staging, candidate, or relocation."""


class SubprocessEnvironmentCommandRunner:
    """Final no-shell, no-network runner for the two fixed build commands."""

    __slots__ = ()

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("SubprocessEnvironmentCommandRunner is final")

    def run(self, argv: tuple[str, ...]) -> None:
        if type(argv) is not tuple or any(
            type(item) is not str or not item for item in argv
        ):
            raise TypeError("environment command argv differs")
        if len(argv) == 6 and argv[:5] == (
            RUNTIME_PYTHON,
            "-m",
            "venv",
            "--without-pip",
            "--copies",
        ):
            _absolute_path(Path(argv[5]), field="venv destination")
        elif len(argv) == 10 and argv[:4] == (
            RUNTIME_PYTHON,
            "-m",
            "pip",
            "--python",
        ):
            environment_python = Path(
                _absolute_path(Path(argv[4]), field="pip environment Python")
            )
            wheel = Path(_absolute_path(Path(argv[9]), field="pip wheel"))
            if (
                environment_python.name != "python"
                or environment_python.parent.name != "bin"
                or argv[5:9]
                != (
                    "install",
                    "--no-compile",
                    "--no-deps",
                    "--no-index",
                )
            ):
                raise WarehouseW3EnvironmentError(
                    "fixed environment install command differs"
                )
        else:
            raise WarehouseW3EnvironmentError("environment command is not fixed")
        bwrap = Path("/usr/bin/bwrap")
        try:
            metadata = os.lstat(bwrap)
        except OSError as exc:
            raise WarehouseW3EnvironmentError(
                "fixed bubblewrap runner is unavailable"
            ) from exc
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != 0
            or metadata.st_mode & 0o111 == 0
        ):
            raise WarehouseW3EnvironmentError(
                "fixed bubblewrap runner identity differs"
            )
        try:
            completed = subprocess.run(
                (
                    str(bwrap),
                    "--unshare-net",
                    "--die-with-parent",
                    "--bind",
                    "/",
                    "/",
                    "--",
                    *argv,
                ),
                env={
                    "HOME": "/nonexistent",
                    "LANG": "C.UTF-8",
                    "LC_ALL": "C.UTF-8",
                    "PATH": "/usr/bin:/bin",
                    "PIP_CONFIG_FILE": "/dev/null",
                    "PIP_DISABLE_PIP_VERSION_CHECK": "1",
                    "PIP_NO_INDEX": "1",
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONNOUSERSITE": "1",
                    "TMPDIR": "/tmp",
                    "TZ": "UTC",
                },
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
                check=False,
                timeout=300,
                umask=0o077,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise WarehouseW3EnvironmentError(
                "fixed environment command could not run"
            ) from exc
        if completed.returncode != 0:
            raise WarehouseW3EnvironmentError("fixed environment command failed")


def _absolute_path(path: Path, *, field: str) -> str:
    if not isinstance(path, Path):
        raise TypeError(f"{field} must be Path")
    text = str(path)
    pure = PurePosixPath(text)
    if (
        not pure.is_absolute()
        or text == "/"
        or text.startswith("//")
        or str(pure) != text
        or any(part in {"", ".", ".."} for part in pure.parts[1:])
    ):
        raise WarehouseW3EnvironmentError(f"{field} is not a canonical absolute path")
    return text


def validate_runtime_python(runtime_python: Path) -> Path:
    """Validate the fixed runtime interpreter before any preparation effect."""

    if not isinstance(runtime_python, Path):
        raise TypeError("runtime_python must be Path")
    if _absolute_path(runtime_python, field="runtime_python") != RUNTIME_PYTHON:
        raise WarehouseW3EnvironmentError("runtime_python differs from fixed runtime")
    return runtime_python


def dbus_metadata_installation_path(dbus_metadata: Path) -> str:
    """Derive the exact copied Debian D-Bus metadata file path."""

    if not isinstance(dbus_metadata, Path):
        raise TypeError("dbus_metadata must be Path")
    if _DBUS_METADATA_RE.fullmatch(dbus_metadata.name) is None:
        raise WarehouseW3EnvironmentError("dbus metadata basename differs")
    return (_SITE_PACKAGES / dbus_metadata.name / "PKG-INFO").as_posix()


def is_dbus_metadata_installation_path(path: str) -> bool:
    """Return whether one inventory path is the fixed copied metadata file."""

    if type(path) is not str:
        return False
    pure = PurePosixPath(path)
    return (
        str(pure) == path
        and pure.name == "PKG-INFO"
        and pure.parent.parent == _SITE_PACKAGES
        and _DBUS_METADATA_RE.fullmatch(pure.parent.name) is not None
    )


def _sha256_text(value: object, *, field: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise WarehouseW3EnvironmentError(f"{field} is not one SHA-256 value")
    return value


def _paths_overlap(first: Path, second: Path) -> bool:
    for child, parent in ((first, second), (second, first)):
        try:
            child.relative_to(parent)
        except ValueError:
            continue
        return True
    return False


def _stat_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _hash_regular(path: Path) -> str:
    try:
        before = os.lstat(path)
    except OSError as exc:
        raise WarehouseW3EnvironmentError(
            f"cannot inspect regular file: {path}"
        ) from exc
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise WarehouseW3EnvironmentError(f"path is not one regular file: {path}")
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise WarehouseW3EnvironmentError(f"cannot open regular file: {path}") from exc
    digest = hashlib.sha256()
    try:
        opened_before = os.fstat(descriptor)
        if _stat_identity(opened_before) != _stat_identity(before):
            raise WarehouseW3EnvironmentError(
                f"regular file identity changed before read: {path}"
            )
        while True:
            chunk = os.read(descriptor, _READ_SIZE)
            if not chunk:
                break
            digest.update(chunk)
        opened_after = os.fstat(descriptor)
    except OSError as exc:
        raise WarehouseW3EnvironmentError(f"cannot read regular file: {path}") from exc
    finally:
        os.close(descriptor)
    try:
        named_after = os.lstat(path)
    except OSError as exc:
        raise WarehouseW3EnvironmentError(
            f"cannot reopen regular file: {path}"
        ) from exc
    if _stat_identity(before) != _stat_identity(opened_after) or _stat_identity(
        opened_after
    ) != _stat_identity(named_after):
        raise WarehouseW3EnvironmentError(f"regular file changed during read: {path}")
    return digest.hexdigest()


def _children(path: Path) -> tuple[tuple[str, os.stat_result], ...]:
    try:
        with os.scandir(path) as iterator:
            items = tuple(
                sorted(
                    (
                        (item.name, item.stat(follow_symlinks=False))
                        for item in iterator
                    ),
                    key=lambda item: os.fsencode(item[0]),
                )
            )
    except OSError as exc:
        raise WarehouseW3EnvironmentError(f"cannot scan directory: {path}") from exc
    return items


def _write_all(descriptor: int, data: bytes) -> None:
    view = memoryview(data)
    offset = 0
    while offset < len(view):
        try:
            written = os.write(descriptor, view[offset:])
        except OSError as exc:
            raise WarehouseW3EnvironmentError(
                "cannot write copied runtime file"
            ) from exc
        if written <= 0:
            raise WarehouseW3EnvironmentError("copied runtime write made no progress")
        offset += written


def _copy_regular(source: Path, destination: Path, expected: os.stat_result) -> None:
    if not stat.S_ISREG(expected.st_mode) or stat.S_ISLNK(expected.st_mode):
        raise WarehouseW3EnvironmentError(f"copy source is not regular: {source}")
    source_flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        source_flags |= os.O_NOFOLLOW
    destination_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        destination_flags |= os.O_NOFOLLOW
    try:
        source_fd = os.open(source, source_flags)
    except OSError as exc:
        raise WarehouseW3EnvironmentError(
            f"cannot open runtime copy source: {source}"
        ) from exc
    destination_fd = -1
    try:
        opened_before = os.fstat(source_fd)
        if _stat_identity(opened_before) != _stat_identity(expected):
            raise WarehouseW3EnvironmentError(
                f"runtime copy source identity changed: {source}"
            )
        try:
            destination_fd = os.open(
                destination,
                destination_flags,
                0o600,
            )
        except OSError as exc:
            raise WarehouseW3EnvironmentError(
                f"cannot create runtime copy destination: {destination}"
            ) from exc
        while True:
            chunk = os.read(source_fd, _READ_SIZE)
            if not chunk:
                break
            _write_all(destination_fd, chunk)
        opened_after = os.fstat(source_fd)
        named_after = os.lstat(source)
        if _stat_identity(opened_before) != _stat_identity(
            opened_after
        ) or _stat_identity(opened_after) != _stat_identity(named_after):
            raise WarehouseW3EnvironmentError(
                f"runtime copy source changed during read: {source}"
            )
    except OSError as exc:
        raise WarehouseW3EnvironmentError(
            f"cannot copy runtime source: {source}"
        ) from exc
    finally:
        if destination_fd >= 0:
            os.close(destination_fd)
        os.close(source_fd)


def _copy_tree(source: Path, destination: Path) -> None:
    try:
        source_stat = os.lstat(source)
    except OSError as exc:
        raise WarehouseW3EnvironmentError(
            f"cannot inspect runtime package source: {source}"
        ) from exc
    if stat.S_ISLNK(source_stat.st_mode) or not stat.S_ISDIR(source_stat.st_mode):
        raise WarehouseW3EnvironmentError(
            f"runtime package source is not a directory: {source}"
        )
    try:
        destination.mkdir(mode=0o700)
    except OSError as exc:
        raise WarehouseW3EnvironmentError(
            f"cannot create runtime package destination: {destination}"
        ) from exc
    for name, metadata in _children(source):
        child_source = source / name
        child_destination = destination / name
        if stat.S_ISLNK(metadata.st_mode):
            raise WarehouseW3EnvironmentError(
                f"runtime package contains a symlink: {child_source}"
            )
        if name == "__pycache__":
            if not stat.S_ISDIR(metadata.st_mode):
                raise WarehouseW3EnvironmentError(
                    f"runtime package cache is not a directory: {child_source}"
                )
            continue
        if name.endswith((".pyc", ".pyo")):
            if not stat.S_ISREG(metadata.st_mode):
                raise WarehouseW3EnvironmentError(
                    f"runtime bytecode path is not regular: {child_source}"
                )
            continue
        if stat.S_ISDIR(metadata.st_mode):
            _copy_tree(child_source, child_destination)
        elif stat.S_ISREG(metadata.st_mode):
            _copy_regular(child_source, child_destination, metadata)
        else:
            raise WarehouseW3EnvironmentError(
                f"runtime package contains a special file: {child_source}"
            )
    try:
        after = os.lstat(source)
    except OSError as exc:
        raise WarehouseW3EnvironmentError(
            f"cannot reopen runtime package source: {source}"
        ) from exc
    if _stat_identity(source_stat) != _stat_identity(after):
        raise WarehouseW3EnvironmentError(
            f"runtime package source changed during copy: {source}"
        )


@dataclass(frozen=True, slots=True)
class WarehouseRuntimeSources:
    """Caller-closed system package files copied into the candidate."""

    dbus_package: Path
    dbus_bindings: Path
    dbus_glib_bindings: Path
    dbus_metadata: Path
    yaml_package: Path
    yaml_metadata: Path

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("WarehouseRuntimeSources is final")

    def validate(self) -> None:
        def require_kind(path: Path, *, directory: bool, label: str) -> None:
            try:
                metadata = os.lstat(path)
            except OSError as exc:
                raise WarehouseW3EnvironmentError(f"{label} is absent") from exc
            expected_kind = (
                stat.S_ISDIR(metadata.st_mode)
                if directory
                else stat.S_ISREG(metadata.st_mode)
            )
            if stat.S_ISLNK(metadata.st_mode) or not expected_kind:
                raise WarehouseW3EnvironmentError(f"{label} identity differs")

        for field, path in (
            ("dbus_package", self.dbus_package),
            ("dbus_bindings", self.dbus_bindings),
            ("dbus_glib_bindings", self.dbus_glib_bindings),
            ("dbus_metadata", self.dbus_metadata),
            ("yaml_package", self.yaml_package),
            ("yaml_metadata", self.yaml_metadata),
        ):
            _absolute_path(path, field=field)
        if self.dbus_package.name != "dbus" or self.yaml_package.name != "yaml":
            raise WarehouseW3EnvironmentError("runtime package source basenames differ")
        if _DBUS_BINDINGS_RE.fullmatch(self.dbus_bindings.name) is None:
            raise WarehouseW3EnvironmentError("dbus bindings basename differs")
        if _DBUS_GLIB_BINDINGS_RE.fullmatch(self.dbus_glib_bindings.name) is None:
            raise WarehouseW3EnvironmentError("dbus GLib bindings basename differs")
        if _DBUS_METADATA_RE.fullmatch(self.dbus_metadata.name) is None:
            raise WarehouseW3EnvironmentError("dbus metadata basename differs")
        if not is_dbus_metadata_installation_path(
            dbus_metadata_installation_path(self.dbus_metadata)
        ):
            raise WarehouseW3EnvironmentError("dbus metadata installation path differs")
        if _YAML_METADATA_RE.fullmatch(self.yaml_metadata.name) is None:
            raise WarehouseW3EnvironmentError("YAML metadata basename differs")
        for label, path in (
            ("dbus package", self.dbus_package),
            ("dbus metadata", self.dbus_metadata),
            ("YAML package", self.yaml_package),
            ("YAML metadata", self.yaml_metadata),
        ):
            require_kind(path, directory=True, label=label)
        for label, path in (
            ("dbus bindings", self.dbus_bindings),
            ("dbus GLib bindings", self.dbus_glib_bindings),
            ("dbus PKG-INFO", self.dbus_metadata / "PKG-INFO"),
            ("YAML METADATA", self.yaml_metadata / "METADATA"),
            ("YAML WHEEL", self.yaml_metadata / "WHEEL"),
            ("YAML INSTALLER", self.yaml_metadata / "INSTALLER"),
        ):
            require_kind(path, directory=False, label=label)
        try:
            yaml_bindings = tuple(
                item
                for item in self.yaml_package.iterdir()
                if _YAML_BINDINGS_RE.fullmatch(item.name) is not None
            )
        except OSError as exc:
            raise WarehouseW3EnvironmentError(
                "cannot inspect YAML package bindings"
            ) from exc
        if len(yaml_bindings) != 1:
            raise WarehouseW3EnvironmentError(
                "YAML package lacks one exact CPython 3.12 extension"
            )
        require_kind(
            yaml_bindings[0],
            directory=False,
            label="YAML bindings",
        )


def _copy_runtime_sources(
    environment_root: Path,
    sources: WarehouseRuntimeSources,
) -> None:
    if type(sources) is not WarehouseRuntimeSources:
        raise TypeError("runtime_sources must be exact WarehouseRuntimeSources")
    sources.validate()
    site_packages = environment_root / _SITE_PACKAGES
    try:
        site_stat = os.lstat(site_packages)
    except OSError as exc:
        raise WarehouseW3EnvironmentError(
            "venv lacks the exact Python 3.12 site-packages directory"
        ) from exc
    if not stat.S_ISDIR(site_stat.st_mode) or stat.S_ISLNK(site_stat.st_mode):
        raise WarehouseW3EnvironmentError("venv site-packages path is not a directory")
    _copy_tree(sources.dbus_package, site_packages / "dbus")
    _copy_regular(
        sources.dbus_bindings,
        site_packages / sources.dbus_bindings.name,
        os.lstat(sources.dbus_bindings),
    )
    _copy_regular(
        sources.dbus_glib_bindings,
        site_packages / sources.dbus_glib_bindings.name,
        os.lstat(sources.dbus_glib_bindings),
    )
    _copy_tree(
        sources.dbus_metadata,
        site_packages / sources.dbus_metadata.name,
    )
    _copy_tree(sources.yaml_package, site_packages / "yaml")
    _copy_tree(
        sources.yaml_metadata,
        site_packages / sources.yaml_metadata.name,
    )


def _unlink_exact_regular(path: Path, *, label: str) -> None:
    try:
        metadata = os.lstat(path)
    except OSError as exc:
        raise WarehouseW3EnvironmentError(f"{label} is absent") from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_nlink != 1
    ):
        raise WarehouseW3EnvironmentError(f"{label} identity differs")
    try:
        path.unlink()
    except OSError as exc:
        raise WarehouseW3EnvironmentError(f"cannot remove {label}") from exc


def _remove_tree(path: Path) -> None:
    metadata = os.lstat(path)
    if stat.S_ISLNK(metadata.st_mode):
        raise WarehouseW3EnvironmentError(f"cache contains a symlink: {path}")
    if stat.S_ISDIR(metadata.st_mode):
        for name, _child in _children(path):
            _remove_tree(path / name)
        path.rmdir()
        return
    if stat.S_ISREG(metadata.st_mode):
        if metadata.st_nlink != 1:
            raise WarehouseW3EnvironmentError(f"cache file is multiply linked: {path}")
        path.unlink()
        return
    raise WarehouseW3EnvironmentError(f"cache contains a special file: {path}")


def _purge_caches(path: Path) -> None:
    for name, metadata in _children(path):
        child = path / name
        if stat.S_ISLNK(metadata.st_mode):
            raise WarehouseW3EnvironmentError(
                f"environment contains an unexpected symlink: {child}"
            )
        if name == "__pycache__":
            if not stat.S_ISDIR(metadata.st_mode):
                raise WarehouseW3EnvironmentError(
                    f"environment cache is not a directory: {child}"
                )
            _remove_tree(child)
        elif name.endswith((".pyc", ".pyo")):
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise WarehouseW3EnvironmentError(
                    f"environment bytecode identity differs: {child}"
                )
            child.unlink()
        elif stat.S_ISDIR(metadata.st_mode):
            _purge_caches(child)
        elif not stat.S_ISREG(metadata.st_mode):
            raise WarehouseW3EnvironmentError(
                f"environment contains a special file: {child}"
            )


def _remove_candidate_command(environment_root: Path) -> None:
    config = environment_root / "pyvenv.cfg"
    try:
        metadata = os.lstat(config)
        raw = config.read_bytes()
    except OSError as exc:
        raise WarehouseW3EnvironmentError("cannot read pyvenv.cfg") from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_nlink != 1
    ):
        raise WarehouseW3EnvironmentError("pyvenv.cfg identity differs")
    lines = raw.splitlines(keepends=True)
    command_lines = [line for line in lines if line.startswith(b"command = ")]
    if len(command_lines) != 1:
        raise WarehouseW3EnvironmentError("pyvenv.cfg lacks one candidate command line")
    rewritten = b"".join(line for line in lines if not line.startswith(b"command = "))
    if not rewritten or rewritten == raw:
        raise WarehouseW3EnvironmentError("pyvenv.cfg command purge failed")
    flags = os.O_WRONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(config, flags)
    try:
        if _stat_identity(os.fstat(descriptor)) != _stat_identity(metadata):
            raise WarehouseW3EnvironmentError(
                "pyvenv.cfg identity changed before rewrite"
            )
        os.ftruncate(descriptor, 0)
        _write_all(descriptor, rewritten)
    finally:
        os.close(descriptor)


def _clean_install_metadata(environment_root: Path) -> None:
    site_packages = environment_root / _SITE_PACKAGES
    dist_infos: list[Path] = []
    for name, metadata in _children(site_packages):
        if not name.startswith("scion-") or not name.endswith(".dist-info"):
            continue
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise WarehouseW3EnvironmentError(
                "installed Scion dist-info identity differs"
            )
        dist_infos.append(site_packages / name)
    if len(dist_infos) != 1:
        raise WarehouseW3EnvironmentError(
            "installed environment lacks one Scion dist-info directory"
        )
    dist_info = dist_infos[0]
    direct_url = dist_info / "direct_url.json"
    record = dist_info / "RECORD"
    _unlink_exact_regular(direct_url, label="Scion direct_url.json")
    try:
        metadata = os.lstat(record)
        raw = record.read_bytes()
    except OSError as exc:
        raise WarehouseW3EnvironmentError("cannot read Scion RECORD") from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_nlink != 1
    ):
        raise WarehouseW3EnvironmentError("Scion RECORD identity differs")
    try:
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8", "strict"))))
    except (UnicodeError, csv.Error) as exc:
        raise WarehouseW3EnvironmentError("Scion RECORD is malformed") from exc
    direct_name = f"{dist_info.name}/direct_url.json"
    kept: list[list[str]] = []
    removed_script = 0
    removed_direct = 0
    for row in rows:
        if len(row) != 3:
            raise WarehouseW3EnvironmentError("Scion RECORD row shape differs")
        if row[0] == "../../../bin/scion":
            removed_script += 1
        elif row[0] == direct_name:
            removed_direct += 1
        else:
            kept.append(row)
    if removed_script != 1 or removed_direct != 1:
        raise WarehouseW3EnvironmentError("Scion RECORD cleanup inventory differs")
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerows(kept)
    rewritten = output.getvalue().encode("utf-8", "strict")
    flags = os.O_WRONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(record, flags)
    try:
        if _stat_identity(os.fstat(descriptor)) != _stat_identity(metadata):
            raise WarehouseW3EnvironmentError(
                "Scion RECORD identity changed before rewrite"
            )
        os.ftruncate(descriptor, 0)
        _write_all(descriptor, rewritten)
    finally:
        os.close(descriptor)


def _purge_generated_paths(environment_root: Path) -> None:
    bin_root = environment_root / "bin"
    for name in _ACTIVATION_NAMES:
        _unlink_exact_regular(bin_root / name, label=f"activation script {name}")
    _unlink_exact_regular(bin_root / "scion", label="unused Scion console script")
    lib64 = environment_root / "lib64"
    try:
        lib64_stat = os.lstat(lib64)
    except OSError as exc:
        raise WarehouseW3EnvironmentError("venv lib64 alias is absent") from exc
    if not stat.S_ISLNK(lib64_stat.st_mode) or os.readlink(lib64) != "lib":
        raise WarehouseW3EnvironmentError("venv lib64 alias differs")
    lib64.unlink()
    _clean_install_metadata(environment_root)
    _purge_caches(environment_root)
    _remove_candidate_command(environment_root)


def _normalize_modes(environment_root: Path) -> None:
    executable_paths = {
        "bin/python",
        "bin/python3",
        "bin/python3.12",
    }

    def visit(path: Path, relative: str) -> None:
        metadata = os.lstat(path)
        if stat.S_ISLNK(metadata.st_mode):
            raise WarehouseW3EnvironmentError(
                f"environment contains a symlink: {relative}"
            )
        if stat.S_ISDIR(metadata.st_mode):
            for name, _child in _children(path):
                child_relative = name if relative == "." else f"{relative}/{name}"
                visit(path / name, child_relative)
            path.chmod(0o555)
            return
        if stat.S_ISREG(metadata.st_mode):
            if metadata.st_nlink != 1:
                raise WarehouseW3EnvironmentError(
                    f"environment file is multiply linked: {relative}"
                )
            path.chmod(0o555 if relative in executable_paths else 0o444)
            return
        raise WarehouseW3EnvironmentError(
            f"environment contains a special file: {relative}"
        )

    visit(environment_root, ".")


def _require_non_root() -> None:
    if os.geteuid() == 0:
        raise WarehouseW3EnvironmentError(
            "W3 candidate environment preparation rejects effective UID zero"
        )


def _run_exact(runner: EnvironmentCommandRunner, argv: tuple[str, ...]) -> None:
    method = getattr(runner, "run", None)
    if not callable(method):
        raise TypeError("runner must expose run(argv)")
    try:
        result = method(argv)
    except Exception as exc:
        raise WarehouseW3EnvironmentError(
            f"environment command failed: {argv[0]}"
        ) from exc
    if result is not None:
        raise WarehouseW3EnvironmentError(
            "environment runner returned an ambiguous result"
        )


def _probe(
    smoke_probe: EnvironmentSmokeProbe,
    environment_root: Path,
    *,
    phase: str,
) -> None:
    if phase not in {"staging", "candidate", "relocation"}:
        raise WarehouseW3EnvironmentError("environment smoke phase differs")
    method = getattr(smoke_probe, "probe", None)
    if not callable(method):
        raise TypeError("smoke_probe must expose probe(root, phase=...)")
    try:
        result = method(environment_root, phase=phase)
    except Exception as exc:
        raise WarehouseW3EnvironmentError(f"environment {phase} smoke failed") from exc
    if result is not None:
        raise WarehouseW3EnvironmentError(
            "environment smoke probe returned an ambiguous result"
        )


@dataclass(frozen=True, slots=True)
class WarehouseEnvironmentBuild:
    """One completed, still non-authoritative candidate environment."""

    environment_root: Path
    wheel_sha256: str
    venv_argv: tuple[str, ...]
    install_argv: tuple[str, ...]
    receipt: EnvironmentContentReceipt

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("WarehouseEnvironmentBuild is final")


@dataclass(frozen=True, slots=True)
class ProductionWarehouseEnvironmentBuild:
    """A production-built environment plus its discovered external closure."""

    build: WarehouseEnvironmentBuild
    external_runtime_paths: tuple[Path, ...]

    def __post_init__(self) -> None:
        if type(self.build) is not WarehouseEnvironmentBuild:
            raise TypeError("build must be exact WarehouseEnvironmentBuild")
        if (
            type(self.external_runtime_paths) is not tuple
            or not self.external_runtime_paths
            or any(not isinstance(path, Path) for path in self.external_runtime_paths)
        ):
            raise TypeError(
                "external_runtime_paths must be one nonempty exact Path tuple"
            )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("ProductionWarehouseEnvironmentBuild is final")


def _materialize_warehouse_environment(
    environment_root: Path,
    *,
    wheel_path: Path,
    wheel_sha256: str,
    runtime_sources: WarehouseRuntimeSources,
    candidate_root: Path,
    selection_root: Path,
    runner: EnvironmentCommandRunner,
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """Execute the fixed build and return its exact command facts."""

    _require_non_root()
    environment_text = _absolute_path(environment_root, field="environment_root")
    _absolute_path(candidate_root, field="candidate_root")
    _absolute_path(selection_root, field="selection_root")
    if _paths_overlap(environment_root, candidate_root) or _paths_overlap(
        environment_root,
        selection_root,
    ):
        raise WarehouseW3EnvironmentError(
            "staging environment overlaps candidate or selection authority"
        )
    if os.path.lexists(environment_root):
        raise WarehouseW3EnvironmentError("environment_root is already present")
    _absolute_path(wheel_path, field="wheel_path")
    expected_wheel_sha256 = _sha256_text(
        wheel_sha256,
        field="wheel_sha256",
    )
    if _hash_regular(wheel_path) != expected_wheel_sha256:
        raise WarehouseW3EnvironmentError("wheel SHA-256 differs")
    runtime_sources.validate()
    venv_argv = (
        RUNTIME_PYTHON,
        "-m",
        "venv",
        "--without-pip",
        "--copies",
        environment_text,
    )
    install_argv = (
        RUNTIME_PYTHON,
        "-m",
        "pip",
        "--python",
        f"{environment_text}/bin/python",
        "install",
        "--no-compile",
        "--no-deps",
        "--no-index",
        str(wheel_path),
    )
    _run_exact(runner, venv_argv)
    _run_exact(runner, install_argv)
    _copy_runtime_sources(environment_root, runtime_sources)
    _purge_generated_paths(environment_root)
    _normalize_modes(environment_root)
    return expected_wheel_sha256, venv_argv, install_argv


def prepare_warehouse_environment(
    environment_root: Path,
    *,
    wheel_path: Path,
    wheel_sha256: str,
    runtime_sources: WarehouseRuntimeSources,
    external_runtime_paths: tuple[Path, ...],
    candidate_root: Path,
    selection_root: Path,
    runner: EnvironmentCommandRunner,
    smoke_probe: EnvironmentSmokeProbe,
) -> WarehouseEnvironmentBuild:
    """Build and freeze one exact non-root W3 staging environment."""

    if type(external_runtime_paths) is not tuple or not external_runtime_paths:
        raise TypeError("external_runtime_paths must be one nonempty exact tuple")
    expected_wheel_sha256, venv_argv, install_argv = _materialize_warehouse_environment(
        environment_root,
        wheel_path=wheel_path,
        wheel_sha256=wheel_sha256,
        runtime_sources=runtime_sources,
        candidate_root=candidate_root,
        selection_root=selection_root,
        runner=runner,
    )
    try:
        receipt = EnvironmentContentReceipt.create(
            environment_root,
            external_runtime_paths=external_runtime_paths,
            candidate_root=candidate_root,
            selection_root=selection_root,
        )
        _probe(
            smoke_probe,
            environment_root,
            phase="staging",
        )
        verify_environment_content(
            environment_root,
            receipt,
            external_runtime_paths=external_runtime_paths,
            candidate_root=candidate_root,
            selection_root=selection_root,
        )
    except EnvironmentIntegrityError as exc:
        raise WarehouseW3EnvironmentError(
            "candidate environment integrity differs"
        ) from exc
    return WarehouseEnvironmentBuild(
        environment_root=environment_root,
        wheel_sha256=expected_wheel_sha256,
        venv_argv=venv_argv,
        install_argv=install_argv,
        receipt=receipt,
    )


def prepare_production_warehouse_environment(
    environment_root: Path,
    *,
    wheel_path: Path,
    wheel_sha256: str,
    runtime_sources: WarehouseRuntimeSources,
    candidate_root: Path,
    selection_root: Path,
    runtime_python: Path,
) -> ProductionWarehouseEnvironmentBuild:
    """Build through fixed runners and discover the exact live external closure."""

    validate_runtime_python(runtime_python)
    expected_wheel_sha256, venv_argv, install_argv = _materialize_warehouse_environment(
        environment_root,
        wheel_path=wheel_path,
        wheel_sha256=wheel_sha256,
        runtime_sources=runtime_sources,
        candidate_root=candidate_root,
        selection_root=selection_root,
        runner=SubprocessEnvironmentCommandRunner(),
    )
    from .w3_environment_receipts import SubprocessEnvironmentProbeReader

    reader = SubprocessEnvironmentProbeReader()
    external_runtime_paths = reader.discover_external_runtime_paths(environment_root)
    try:
        receipt = EnvironmentContentReceipt.create(
            environment_root,
            external_runtime_paths=external_runtime_paths,
            candidate_root=candidate_root,
            selection_root=selection_root,
        )
        verify_environment_content(
            environment_root,
            receipt,
            external_runtime_paths=external_runtime_paths,
            candidate_root=candidate_root,
            selection_root=selection_root,
        )
        reader._observe(environment_root)
        verify_environment_content(
            environment_root,
            receipt,
            external_runtime_paths=external_runtime_paths,
            candidate_root=candidate_root,
            selection_root=selection_root,
        )
    except EnvironmentIntegrityError as exc:
        raise WarehouseW3EnvironmentError(
            "production environment integrity differs"
        ) from exc
    build = WarehouseEnvironmentBuild(
        environment_root=environment_root,
        wheel_sha256=expected_wheel_sha256,
        venv_argv=venv_argv,
        install_argv=install_argv,
        receipt=receipt,
    )
    return ProductionWarehouseEnvironmentBuild(
        build=build,
        external_runtime_paths=external_runtime_paths,
    )


def materialize_simulated_warehouse_environment(
    source_root: Path,
    destination_root: Path,
    receipt: EnvironmentContentReceipt,
    *,
    external_runtime_paths: tuple[Path, ...],
    candidate_root: Path,
    selection_root: Path,
) -> None:
    """No-follow copy one frozen environment to its non-root simulated path."""

    _require_non_root()
    _absolute_path(source_root, field="source_root")
    _absolute_path(destination_root, field="destination_root")
    if os.path.lexists(destination_root):
        raise WarehouseW3EnvironmentError(
            "simulated environment destination already exists"
        )
    try:
        verify_environment_content(
            source_root,
            receipt,
            external_runtime_paths=external_runtime_paths,
            candidate_root=candidate_root,
            selection_root=selection_root,
        )
        _copy_tree(source_root, destination_root)
        _normalize_modes(destination_root)
        verify_environment_content(
            destination_root,
            receipt,
            external_runtime_paths=external_runtime_paths,
            candidate_root=candidate_root,
            selection_root=selection_root,
        )
    except EnvironmentIntegrityError as exc:
        raise WarehouseW3EnvironmentError(
            "simulated environment integrity differs"
        ) from exc


def verify_warehouse_environment(
    environment_root: Path,
    receipt: EnvironmentContentReceipt,
    *,
    wheel_path: Path,
    wheel_sha256: str,
    external_runtime_paths: tuple[Path, ...],
    candidate_root: Path,
    selection_root: Path,
    smoke_probe: EnvironmentSmokeProbe,
    smoke_phase: str,
) -> None:
    """Rehash and smoke one candidate or simulated-relocation environment."""

    _require_non_root()
    _absolute_path(environment_root, field="environment_root")
    _absolute_path(candidate_root, field="candidate_root")
    _absolute_path(selection_root, field="selection_root")
    _absolute_path(wheel_path, field="wheel_path")
    expected_wheel_sha256 = _sha256_text(
        wheel_sha256,
        field="wheel_sha256",
    )
    if _hash_regular(wheel_path) != expected_wheel_sha256:
        raise WarehouseW3EnvironmentError("wheel SHA-256 differs")
    try:
        verify_environment_content(
            environment_root,
            receipt,
            external_runtime_paths=external_runtime_paths,
            candidate_root=candidate_root,
            selection_root=selection_root,
        )
        _probe(
            smoke_probe,
            environment_root,
            phase=smoke_phase,
        )
        verify_environment_content(
            environment_root,
            receipt,
            external_runtime_paths=external_runtime_paths,
            candidate_root=candidate_root,
            selection_root=selection_root,
        )
    except EnvironmentIntegrityError as exc:
        raise WarehouseW3EnvironmentError(
            "verified environment integrity differs"
        ) from exc


__all__ = [
    "EnvironmentCommandRunner",
    "EnvironmentSmokeProbe",
    "ProductionWarehouseEnvironmentBuild",
    "RUNTIME_PYTHON",
    "SubprocessEnvironmentCommandRunner",
    "WarehouseEnvironmentBuild",
    "WarehouseRuntimeSources",
    "WarehouseW3EnvironmentError",
    "dbus_metadata_installation_path",
    "is_dbus_metadata_installation_path",
    "materialize_simulated_warehouse_environment",
    "prepare_production_warehouse_environment",
    "prepare_warehouse_environment",
    "validate_runtime_python",
    "verify_warehouse_environment",
]
