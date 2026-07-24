from __future__ import annotations

import base64
import hashlib
import json
import stat
import sys
import tarfile
import types
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

# Importing the exact Git receipt reaches the execution package.  This
# source-only wheel test keeps the native extension fail-on-use.
_native_extension = types.ModuleType("scion.runtime.native._spawn_into_cgroup")
for _name, _value in {
    "CHILD_EXEC_ERROR_FD": 198,
    "CHILD_RELEASE_FD": 199,
    "CHILD_STDERR_FD": 197,
    "CHILD_STDIN_FD": 195,
    "CHILD_STDOUT_FD": 196,
    "CLONE_ARGS_SIZE": 88,
    "CLONE_FLAGS": 0,
    "ERROR_RECORD_MAGIC": b"SCXE",
    "ERROR_RECORD_FORMAT": "<4sBBHI",
    "ERROR_RECORD_SIZE": 12,
    "ERROR_RECORD_VERSION": 1,
    "ERROR_STAGE_CHDIR": 12,
    "ERROR_STAGE_CLOSE_RANGE": 10,
    "ERROR_STAGE_DUP_EXEC_ERROR": 8,
    "ERROR_STAGE_DUP_RELEASE": 9,
    "ERROR_STAGE_DUP_STDERR": 7,
    "ERROR_STAGE_DUP_STDIN": 5,
    "ERROR_STAGE_DUP_STDOUT": 6,
    "ERROR_STAGE_EXECVE": 13,
    "ERROR_STAGE_RELEASE_BYTE": 4,
    "ERROR_STAGE_RELEASE_CLOSE": 3,
    "ERROR_STAGE_RELEASE_READ": 2,
    "ERROR_STAGE_SIGNAL_DISPOSITIONS": 11,
    "ERROR_STAGE_SIGNAL_MASK": 1,
    "EXIT_SIGNAL": 17,
    "RELEASE_BYTE": b"\x01",
    "WAIT_RESULT_FIELDS": (
        "pid",
        "uid",
        "si_code",
        "si_status",
        "wait_status",
        "return_code",
        "signal",
        "core_dumped",
    ),
    "BlockedChild": type("_BlockedChild", (), {}),
    "spawn_blocked": lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("native spawn was not configured by this test")
    ),
}.items():
    setattr(_native_extension, _name, _value)
sys.modules.setdefault(
    "scion.runtime.native._spawn_into_cgroup",
    _native_extension,
)

from scion.problems.warehouse_delivery import w3_wheel
from scion.problems.warehouse_delivery.w3_installation import (
    GitBlobIdentity,
    GitSourceReceipt,
)
from scion.problems.warehouse_delivery.w3_wheel import (
    BWRAP,
    BUILDER_ARGV_TEMPLATE,
    BUILDER_PYTHON,
    FIXED_REQUIRED_WHEEL_MEMBERS,
    ImmutableGitArchive,
    OfflineDoubleWheelArtifact,
    OfflineDoubleWheelReceipt,
    SubprocessLocalGitReader,
    SubprocessWheelRunner,
    W3_TOOL_MEMBER,
    WarehouseW3WheelError,
    build_offline_double_wheel,
    verify_offline_double_wheel_artifact,
)

COMMIT = "0123456789abcdef0123456789abcdef01234567"
TREE = "89abcdef0123456789abcdef0123456789abcdef"
EPOCH = 1_725_000_000
NATIVE_PATH = (
    "scion/runtime/native/" "_spawn_into_cgroup.cpython-312-x86_64-linux-gnu.so"
)
NATIVE_BYTES = b"\x7fELFfixture accepted native bytes\n"
WHEEL_NAME = "scion-0.1.0-cp312-cp312-linux_x86_64.whl"


def _source_members(
    *,
    extra: tuple[tuple[str, bytes], ...] = (),
    omit: str | None = None,
) -> dict[str, bytes]:
    members = {
        "pyproject.toml": (
            b"[build-system]\nrequires=[]\n" b'build-backend="setuptools.build_meta"\n'
        ),
        **{
            path: (
                b"[Unit]\nDescription=fixture\n"
                if path.endswith(".service")
                else f"# fixture source: {path}\n".encode()
            )
            for path in FIXED_REQUIRED_WHEEL_MEMBERS
        },
        "scion/core/extra_launch_module.py": b"VALUE = 'complete closure'\n",
    }
    members.update(extra)
    if omit is not None:
        del members[omit]
    return members


def _write_archive(
    path: Path,
    *,
    extra: tuple[tuple[str, bytes], ...] = (),
    omit: str | None = None,
    extra_directory: str | None = None,
) -> ImmutableGitArchive:
    members = _source_members(extra=extra, omit=omit)
    with tarfile.open(path, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        directories = {
            parent.as_posix()
            for name in members
            for parent in Path(name).parents
            if parent.as_posix() != "."
        }
        if extra_directory is not None:
            directories.add(extra_directory)
        for name in sorted(directories):
            info = tarfile.TarInfo(name)
            info.type = tarfile.DIRTYPE
            info.mode = 0o755
            info.mtime = EPOCH
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            archive.addfile(info)
        for name, raw in sorted(members.items()):
            info = tarfile.TarInfo(name)
            info.mode = 0o644
            info.mtime = EPOCH
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.size = len(raw)
            archive.addfile(info, fileobj=_BytesReader(raw))
    path.chmod(0o444)
    blobs = tuple(
        GitBlobIdentity(
            logical_path=name,
            mode="100644",
            blob_oid=hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest(),
            sha256=hashlib.sha256(raw).hexdigest(),
            size_bytes=len(raw),
        )
        for name, raw in sorted(members.items())
    )
    source_receipt = GitSourceReceipt.create(
        source_commit=COMMIT,
        source_tree=TREE,
        remote_name="origin",
        remote_url="ssh://fixture.invalid/scion.git",
        remote_ref="refs/heads/test",
        remote_tracking_ref="refs/remotes/origin/test",
        blobs=blobs,
    )
    return ImmutableGitArchive(
        path=path,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        source_receipt=source_receipt,
    )


class _BytesReader:
    def __init__(self, raw: bytes) -> None:
        self._raw = raw
        self._offset = 0

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self._raw) - self._offset
        result = self._raw[self._offset : self._offset + size]
        self._offset += len(result)
        return result


def _zip_info(path: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, date_time=(2024, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


class FakeWheelRunner:
    def __init__(
        self,
        *,
        missing_member: str | None = None,
        native_bytes: bytes = NATIVE_BYTES,
        second_comment: bool = False,
        leak_work_root: bool = False,
        changed_source_member: str | None = None,
        wheel_only_python: bool = False,
    ) -> None:
        self.calls: list[tuple[tuple[str, ...], Path, dict[str, str], int]] = []
        self.missing_member = missing_member
        self.native_bytes = native_bytes
        self.second_comment = second_comment
        self.leak_work_root = leak_work_root
        self.changed_source_member = changed_source_member
        self.wheel_only_python = wheel_only_python

    def run(
        self,
        argv: tuple[str, ...],
        *,
        cwd: Path,
        environment: dict[str, str],
        umask: int,
    ) -> None:
        self.calls.append((argv, cwd, dict(environment), umask))
        members = {
            item.relative_to(cwd).as_posix(): item.read_bytes()
            for item in cwd.rglob("*")
            if item.is_file()
            and (
                item.suffix == ".py"
                or item.name
                in {
                    "scion-w3@.service",
                    "scion-w3-close@.service",
                }
            )
        }
        members[NATIVE_PATH] = self.native_bytes
        members["scion-0.1.0.dist-info/WHEEL"] = (
            b"Wheel-Version: 1.0\n"
            b"Generator: fixture\n"
            b"Root-Is-Purelib: false\n"
            b"Tag: cp312-cp312-linux_x86_64\n"
        )
        members["scion-0.1.0.dist-info/METADATA"] = (
            b"Metadata-Version: 2.1\nName: scion\nVersion: 0.1.0\n"
        )
        members["scion-0.1.0.dist-info/entry_points.txt"] = (
            b"[console_scripts]\nscion-w3-install=scion.tools.scion_w3_install:main\n"
        )
        members["scion-0.1.0.dist-info/top_level.txt"] = b"scion\n"
        if self.missing_member is not None:
            members.pop(self.missing_member, None)
        if self.leak_work_root:
            members["scion/leak.py"] = str(cwd.parents[1]).encode()
        if self.changed_source_member is not None:
            members[self.changed_source_member] = b"# wheel-only changed bytes\n"
        if self.wheel_only_python:
            members["scion/wheel_only.py"] = b"EXECUTABLE = True\n"
        record_path = "scion-0.1.0.dist-info/RECORD"
        record_rows = []
        for name, raw in sorted(members.items()):
            encoded = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(
                b"="
            )
            record_rows.append(f"{name},sha256={encoded.decode('ascii')},{len(raw)}\n")
        record_rows.append(f"{record_path},,\n")
        members[record_path] = "".join(record_rows).encode("ascii")
        wheel_path = Path(argv[8]) / WHEEL_NAME
        with zipfile.ZipFile(
            wheel_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            for name, raw in sorted(members.items()):
                archive.writestr(_zip_info(name), raw)
            if self.second_comment and len(self.calls) == 2:
                archive.comment = b"second build differs only in ZIP bytes"


class FakeLocalGitReader:
    def __init__(
        self,
        archive: ImmutableGitArchive,
        *,
        commit: str = COMMIT,
        tree: str = TREE,
        epoch: int = EPOCH,
    ) -> None:
        self.commit = commit
        self.tree = tree
        self.epoch = epoch
        self.calls: list[tuple[str, ...]] = []
        with tarfile.open(archive.path, mode="r:") as source:
            by_path = {
                item.name: source.extractfile(item).read()
                for item in source.getmembers()
                if item.isfile()
            }
        self.blobs = {
            item.blob_oid: by_path[item.logical_path]
            for item in archive.source_receipt.blobs
        }
        self.entries = {
            item.logical_path: item for item in archive.source_receipt.blobs
        }

    def read(self, argv: tuple[str, ...], *, repo_root: Path) -> bytes:
        assert repo_root.is_dir()
        self.calls.append(argv)
        if argv[1:3] == ("rev-parse", "--verify"):
            return (
                f"{self.tree}\n".encode()
                if argv[3].endswith("^{tree}")
                else f"{self.commit}\n".encode()
            )
        if argv[1:4] == ("show", "-s", "--format=%ct"):
            return f"{self.epoch}\n".encode()
        if argv[1:4] == ("ls-tree", "-z", "--full-tree"):
            item = self.entries[argv[-1]]
            return (
                f"{item.mode} blob {item.blob_oid}\t" f"{item.logical_path}\0"
            ).encode()
        if argv[1:3] == ("cat-file", "blob"):
            return self.blobs[argv[3]]
        raise AssertionError(f"unexpected Git command: {argv!r}")


def _build(
    archives: tuple[ImmutableGitArchive, ImmutableGitArchive],
    *,
    work_root: Path,
    runner: FakeWheelRunner,
    git_reader: FakeLocalGitReader | None = None,
) -> object:
    return w3_wheel._build_offline_double_wheel_for_test(
        archives,
        repo_root=archives[0].path.parent,
        work_root=work_root,
        runner=runner,
        git_reader=git_reader or FakeLocalGitReader(archives[0]),
    )


def _verify_test_artifact(artifact: object):
    return w3_wheel._verify_offline_double_wheel_artifact_for_test(
        artifact,
        git_reader=FakeLocalGitReader(artifact.archives[0]),
    )


@pytest.fixture
def archives(tmp_path: Path) -> tuple[ImmutableGitArchive, ImmutableGitArchive]:
    return (
        _write_archive(tmp_path / "source-one.tar"),
        _write_archive(tmp_path / "source-two.tar"),
    )


def _accept_fixture_native(monkeypatch: pytest.MonkeyPatch) -> str:
    value = hashlib.sha256(NATIVE_BYTES).hexdigest()
    monkeypatch.setattr(w3_wheel, "ACCEPTED_NATIVE_ELF_SHA256", value)
    return value


def test_double_build_uses_exact_offline_contract_and_canonical_receipt(
    archives: tuple[ImmutableGitArchive, ImmutableGitArchive],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native_sha = _accept_fixture_native(monkeypatch)
    runner = FakeWheelRunner()
    work_root = tmp_path / "wheel-work"

    artifact = _build(
        archives,
        work_root=work_root,
        runner=runner,
    )

    assert len(runner.calls) == 2
    assert artifact.build_argv == tuple(call[0] for call in runner.calls)
    for index, (argv, cwd, environment, umask) in enumerate(runner.calls, 1):
        assert argv == BUILDER_ARGV_TEMPLATE[:8] + (
            f"{work_root}/build-{index}/wheel",
            ".",
        )
        assert cwd == work_root / f"build-{index}" / "source"
        assert environment["PATH"] == "/usr/bin:/bin"
        assert environment["PIP_NO_INDEX"] == "1"
        assert environment["PIP_CONFIG_FILE"] == "/dev/null"
        assert environment["SOURCE_DATE_EPOCH"] == str(EPOCH)
        assert "http_proxy" not in environment
        assert umask == 0o077
    assert artifact.wheel_path.name == WHEEL_NAME
    assert artifact.wheel_path.stat().st_mode & 0o777 == 0o444
    assert artifact.wheel_identity == artifact.receipt.wheel_identity
    assert (
        artifact.receipt.source_receipt_sha256 == archives[0].source_receipt.raw_sha256
    )
    assert artifact.receipt.native_elf_sha256 == native_sha
    assert (
        "scion/core/extra_launch_module.py" in artifact.receipt.required_module_members
    )
    assert OfflineDoubleWheelReceipt.from_bytes(artifact.receipt.raw) == (
        artifact.receipt
    )
    assert artifact.receipt.archive_sha256 == (
        archives[0].sha256,
        archives[1].sha256,
    )
    assert tuple(item.path for item in artifact.receipt.member_inventory) == tuple(
        sorted(item.path for item in artifact.receipt.member_inventory)
    )


def test_archive_inputs_must_have_equal_complete_source_inventory(
    tmp_path: Path,
) -> None:
    first = _write_archive(tmp_path / "source-one.tar")
    second = _write_archive(
        tmp_path / "source-two.tar",
        extra=(("scion/only_second.py", b"SECOND = True\n"),),
    )
    runner = FakeWheelRunner()

    with pytest.raises(
        WarehouseW3WheelError,
        match="source identities|inventories",
    ):
        _build(
            (first, second),
            work_root=tmp_path / "work",
            runner=runner,
        )

    assert runner.calls == []


def test_archive_cannot_add_files_outside_exact_source_receipt(
    tmp_path: Path,
) -> None:
    base = _write_archive(tmp_path / "base.tar")
    first_raw = _write_archive(
        tmp_path / "source-one.tar",
        extra=(("setup.cfg", b"[metadata]\nname=scion\n"),),
    )
    second_raw = _write_archive(
        tmp_path / "source-two.tar",
        extra=(("setup.cfg", b"[metadata]\nname=scion\n"),),
    )
    archives = (
        ImmutableGitArchive(
            path=first_raw.path,
            sha256=first_raw.sha256,
            source_receipt=base.source_receipt,
        ),
        ImmutableGitArchive(
            path=second_raw.path,
            sha256=second_raw.sha256,
            source_receipt=base.source_receipt,
        ),
    )
    with pytest.raises(WarehouseW3WheelError, match="exact source receipt"):
        _build(
            archives,
            work_root=tmp_path / "work",
            runner=FakeWheelRunner(),
            git_reader=FakeLocalGitReader(base),
        )


def test_archive_must_contain_fixed_tool_templates_and_runtime_source(
    tmp_path: Path,
) -> None:
    first = _write_archive(
        tmp_path / "source-one.tar",
        omit="scion/runtime/execution/spawn_backend.py",
    )
    second = _write_archive(
        tmp_path / "source-two.tar",
        omit="scion/runtime/execution/spawn_backend.py",
    )
    runner = FakeWheelRunner()

    with pytest.raises(WarehouseW3WheelError, match="fixed W3/runtime source"):
        _build(
            (first, second),
            work_root=tmp_path / "work",
            runner=runner,
        )

    assert runner.calls == []


def test_wheel_rejects_missing_required_member(
    archives: tuple[ImmutableGitArchive, ImmutableGitArchive],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _accept_fixture_native(monkeypatch)
    runner = FakeWheelRunner(missing_member=W3_TOOL_MEMBER)

    with pytest.raises(WarehouseW3WheelError, match="member allowlist"):
        _build(
            archives,
            work_root=tmp_path / "work",
            runner=runner,
        )

    assert len(runner.calls) == 1


def test_wheel_rejects_native_elf_hash_drift(
    archives: tuple[ImmutableGitArchive, ImmutableGitArchive],
    tmp_path: Path,
) -> None:
    assert w3_wheel.ACCEPTED_NATIVE_ELF_SHA256 == (
        "3d747973bc2eb3b0f6fda68f288987c7b988820eb24df2ff617aa567071803fc"
    )
    runner = FakeWheelRunner()

    with pytest.raises(WarehouseW3WheelError, match="native ELF SHA-256"):
        _build(
            archives,
            work_root=tmp_path / "work",
            runner=runner,
        )

    assert len(runner.calls) == 1


def test_double_build_requires_byte_identity_even_when_members_match(
    archives: tuple[ImmutableGitArchive, ImmutableGitArchive],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _accept_fixture_native(monkeypatch)
    runner = FakeWheelRunner(second_comment=True)

    with pytest.raises(WarehouseW3WheelError, match="bytes are not identical"):
        _build(
            archives,
            work_root=tmp_path / "work",
            runner=runner,
        )

    assert len(runner.calls) == 2


def test_wheel_rejects_disposable_path_leak(
    archives: tuple[ImmutableGitArchive, ImmutableGitArchive],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _accept_fixture_native(monkeypatch)
    runner = FakeWheelRunner(leak_work_root=True)

    with pytest.raises(WarehouseW3WheelError, match="disposable path"):
        _build(
            archives,
            work_root=tmp_path / "work",
            runner=runner,
        )


@pytest.mark.parametrize(
    ("commit", "tree", "epoch", "message"),
    (
        ("f" * 40, TREE, EPOCH, "commit, tree, or timestamp"),
        (COMMIT, "e" * 40, EPOCH, "commit, tree, or timestamp"),
        (COMMIT, TREE, EPOCH + 1, "SOURCE_DATE_EPOCH"),
    ),
)
def test_local_git_revalidation_rejects_forged_commit_tree_or_epoch(
    archives: tuple[ImmutableGitArchive, ImmutableGitArchive],
    tmp_path: Path,
    commit: str,
    tree: str,
    epoch: int,
    message: str,
) -> None:
    reader = FakeLocalGitReader(
        archives[0],
        commit=commit,
        tree=tree,
        epoch=epoch,
    )
    with pytest.raises(WarehouseW3WheelError, match=message):
        _build(
            archives,
            work_root=tmp_path / "work",
            runner=FakeWheelRunner(),
            git_reader=reader,
        )


def test_local_git_revalidation_rejects_blob_not_at_receipt_tree_path(
    archives: tuple[ImmutableGitArchive, ImmutableGitArchive],
    tmp_path: Path,
) -> None:
    reader = FakeLocalGitReader(archives[0])
    path = next(iter(reader.entries))
    entry = reader.entries[path]
    reader.entries[path] = SimpleNamespace(
        mode=entry.mode,
        blob_oid="c" * 40,
        logical_path=entry.logical_path,
    )
    with pytest.raises(WarehouseW3WheelError, match="tree entry differs"):
        _build(
            archives,
            work_root=tmp_path / "work",
            runner=FakeWheelRunner(),
            git_reader=reader,
        )


@pytest.mark.parametrize(
    "runner",
    (
        FakeWheelRunner(changed_source_member="scion/core/extra_launch_module.py"),
        FakeWheelRunner(wheel_only_python=True),
    ),
)
def test_wheel_payload_is_exactly_the_git_python_and_template_bytes(
    archives: tuple[ImmutableGitArchive, ImmutableGitArchive],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runner: FakeWheelRunner,
) -> None:
    _accept_fixture_native(monkeypatch)
    with pytest.raises(
        WarehouseW3WheelError,
        match="Python/template|member allowlist",
    ):
        _build(
            archives,
            work_root=tmp_path / "work",
            runner=runner,
        )


def test_final_reopen_rejects_replacement_after_inventory(
    archives: tuple[ImmutableGitArchive, ImmutableGitArchive],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _accept_fixture_native(monkeypatch)

    def replace_after_inventory(first: Path, second: Path) -> bool:
        replacement = first.with_name("replacement.whl")
        replacement.write_bytes(second.read_bytes())
        replacement.chmod(0o444)
        replacement.replace(first)
        return True

    monkeypatch.setattr(w3_wheel, "_files_equal", replace_after_inventory)
    with pytest.raises(WarehouseW3WheelError, match="inode was replaced"):
        _build(
            archives,
            work_root=tmp_path / "work",
            runner=FakeWheelRunner(),
        )


def test_receipt_parser_rejects_unknown_and_native_drift(
    archives: tuple[ImmutableGitArchive, ImmutableGitArchive],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _accept_fixture_native(monkeypatch)
    artifact = _build(
        archives,
        work_root=tmp_path / "work",
        runner=FakeWheelRunner(),
    )
    value = json.loads(artifact.receipt.raw)
    value["unknown"] = True
    with pytest.raises(WarehouseW3WheelError, match="fields differ"):
        OfflineDoubleWheelReceipt.from_bytes(
            (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
        )

    value.pop("unknown")
    value["native_elf_sha256"] = "0" * 64
    with pytest.raises(WarehouseW3WheelError, match="authority differs"):
        OfflineDoubleWheelReceipt.from_bytes(
            (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
        )


def test_actual_runner_is_narrow_no_shell_and_closed_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cwd = tmp_path / "source"
    wheel_dir = tmp_path / "wheel"
    home = tmp_path / "home"
    temporary = tmp_path / "tmp"
    for directory in (cwd, wheel_dir, home, temporary):
        directory.mkdir()
    environment = dict(w3_wheel._ENVIRONMENT_TEMPLATE)
    environment["HOME"] = str(home)
    environment["TMPDIR"] = str(temporary)
    environment["SOURCE_DATE_EPOCH"] = str(EPOCH)
    captured: dict[str, object] = {}

    def fake_run(argv: tuple[str, ...], **kwargs: object) -> SimpleNamespace:
        captured["argv"] = argv
        captured.update(kwargs)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(w3_wheel.subprocess, "run", fake_run)
    argv = BUILDER_ARGV_TEMPLATE[:8] + (str(wheel_dir), ".")

    SubprocessWheelRunner().run(
        argv,
        cwd=cwd,
        environment=environment,
        umask=0o077,
    )

    assert captured["argv"] == (
        BWRAP,
        "--unshare-net",
        "--die-with-parent",
        "--bind",
        "/",
        "/",
        "--chdir",
        str(cwd),
        "--",
        *argv,
    )
    assert captured["shell"] is False
    assert captured["env"] == environment
    assert captured["umask"] == 0o077
    assert captured["stdin"] is w3_wheel.subprocess.DEVNULL


def test_local_git_reader_disables_replace_objects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run(argv: tuple[str, ...], **kwargs: object) -> SimpleNamespace:
        captured["argv"] = argv
        captured.update(kwargs)
        return SimpleNamespace(returncode=0, stdout=f"{COMMIT}\n".encode())

    monkeypatch.setattr(w3_wheel.subprocess, "run", fake_run)
    result = SubprocessLocalGitReader().read(
        ("git", "rev-parse", "--verify", f"{COMMIT}^{{commit}}"),
        repo_root=tmp_path,
    )

    assert result == f"{COMMIT}\n".encode()
    environment = captured["env"]
    assert type(environment) is dict
    assert environment["GIT_NO_REPLACE_OBJECTS"] == "1"
    assert environment["GIT_CONFIG_NOSYSTEM"] == "1"
    assert captured["shell"] is False


def test_builder_rejects_effective_uid_zero_before_artifact_creation(
    archives: tuple[ImmutableGitArchive, ImmutableGitArchive],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(w3_wheel.os, "geteuid", lambda: 0)
    work_root = tmp_path / "work"

    with pytest.raises(WarehouseW3WheelError, match="effective UID zero"):
        _build(
            archives,
            work_root=work_root,
            runner=FakeWheelRunner(),
        )

    assert not work_root.exists()


def test_artifact_verifier_reopens_exact_wheel_bytes_and_full_inventory(
    archives: tuple[ImmutableGitArchive, ImmutableGitArchive],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _accept_fixture_native(monkeypatch)
    artifact = _build(
        archives,
        work_root=tmp_path / "verified-work",
        runner=FakeWheelRunner(),
    )

    with pytest.raises(TypeError, match="production OfflineDoubleWheelArtifact"):
        verify_offline_double_wheel_artifact(artifact)
    assert _verify_test_artifact(artifact) == artifact.receipt

    artifact.wheel_path.chmod(0o644)
    raw = artifact.wheel_path.read_bytes()
    artifact.wheel_path.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
    artifact.wheel_path.chmod(0o444)
    with pytest.raises(
        WarehouseW3WheelError,
        match="replaced|changed|differs|inspect",
    ):
        _verify_test_artifact(artifact)


def test_artifact_verifier_rejects_fake_receipt_and_named_inode_replacement(
    archives: tuple[ImmutableGitArchive, ImmutableGitArchive],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _accept_fixture_native(monkeypatch)
    artifact = _build(
        archives,
        work_root=tmp_path / "replacement-work",
        runner=FakeWheelRunner(),
    )
    changed = json.loads(artifact.receipt.raw)
    changed["wheel_sha256"] = hashlib.sha256(b"fake wheel").hexdigest()
    fake_receipt = OfflineDoubleWheelReceipt.from_bytes(
        (json.dumps(changed, sort_keys=True, separators=(",", ":")) + "\n").encode()
    )
    fake_evidence = w3_wheel._OfflineDoubleWheelBuildEvidence(
        repo_root=artifact.repo_root,
        archives=artifact.archives,
        wheel_paths=(artifact.wheel_path, artifact.second_wheel_path),
        wheel_identities=(
            artifact.wheel_identity,
            artifact.second_wheel_identity,
        ),
        receipt=fake_receipt,
        build_argv=artifact.build_argv,
    )
    fake_artifact = w3_wheel._TestOfflineDoubleWheelArtifact.from_evidence(
        fake_evidence
    )
    with pytest.raises(WarehouseW3WheelError, match="differs"):
        _verify_test_artifact(fake_artifact)

    original = artifact.wheel_path.with_suffix(".original")
    artifact.wheel_path.rename(original)
    artifact.wheel_path.write_bytes(original.read_bytes())
    artifact.wheel_path.chmod(0o444)
    with pytest.raises(WarehouseW3WheelError, match="replaced"):
        _verify_test_artifact(artifact)


def test_artifact_verifier_reopens_after_files_equal_race_window(
    archives: tuple[ImmutableGitArchive, ImmutableGitArchive],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _accept_fixture_native(monkeypatch)
    artifact = _build(
        archives,
        work_root=tmp_path / "files-equal-race-work",
        runner=FakeWheelRunner(),
    )
    original_files_equal = w3_wheel._files_equal

    def racing_files_equal(first: Path, second: Path) -> bool:
        size = first.stat().st_size
        replacement = b"X" * size
        for path in (first, second):
            path.chmod(0o644)
            path.write_bytes(replacement)
            path.chmod(0o444)
        return original_files_equal(first, second)

    monkeypatch.setattr(w3_wheel, "_files_equal", racing_files_equal)
    with pytest.raises(
        WarehouseW3WheelError,
        match="replaced|changed|provenance",
    ):
        _verify_test_artifact(artifact)


def test_production_builder_has_no_injected_runner_or_git_reader_and_argv_is_fixed(
    archives: tuple[ImmutableGitArchive, ImmutableGitArchive],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert "runner" not in build_offline_double_wheel.__annotations__
    assert "git_reader" not in build_offline_double_wheel.__annotations__
    assert set(w3_wheel._build_offline_double_wheel_for_test.__annotations__) == {
        "archives",
        "repo_root",
        "work_root",
        "runner",
        "git_reader",
        "return",
    }

    _accept_fixture_native(monkeypatch)
    artifact = _build(
        archives,
        work_root=tmp_path / "fixed-argv-work",
        runner=FakeWheelRunner(),
    )
    neutral = w3_wheel._OfflineDoubleWheelBuildEvidence(
        repo_root=artifact.repo_root,
        archives=artifact.archives,
        wheel_paths=(artifact.wheel_path, artifact.second_wheel_path),
        wheel_identities=(
            artifact.wheel_identity,
            artifact.second_wheel_identity,
        ),
        receipt=artifact.receipt,
        build_argv=artifact.build_argv,
    )
    with pytest.raises(TypeError, match="production build evidence type differs"):
        OfflineDoubleWheelArtifact._from_production_build(neutral)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="production OfflineDoubleWheelArtifact"):
        verify_offline_double_wheel_artifact(artifact)
    with pytest.raises(TypeError, match="build-owner constructed"):
        OfflineDoubleWheelArtifact(
            wheel_path=artifact.wheel_path,
            wheel_identity=artifact.wheel_identity,
            receipt=artifact.receipt,
            build_argv=(("arbitrary",), ("arbitrary",)),
        )


def test_archive_rejects_extra_empty_directory_outside_blob_parent_closure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _accept_fixture_native(monkeypatch)
    first = _write_archive(
        tmp_path / "source-extra-directory.tar",
        extra_directory="unowned-empty-directory",
    )
    second = _write_archive(tmp_path / "source-exact.tar")

    with pytest.raises(
        WarehouseW3WheelError,
        match="exact source receipt",
    ):
        _build(
            (first, second),
            work_root=tmp_path / "extra-directory-work",
            runner=FakeWheelRunner(),
            git_reader=FakeLocalGitReader(first),
        )
