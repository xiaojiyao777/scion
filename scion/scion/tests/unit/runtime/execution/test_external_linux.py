from __future__ import annotations

import ast
import json
import os
import stat
from pathlib import Path

import pytest

import scion.runtime.execution.external_linux as external_linux
from scion.runtime.execution.external_linux import (
    CanonicalImportReceiptError,
    ExternalLinuxError,
    ImmutableTreeImportReceipt,
    LinuxMutationHold,
    LinuxRootAdapter,
    MountNamespacePair,
    NamespaceIdentity,
    TreeImportHold,
    acquire_mount_namespace_pair,
    attach_cloned_mount,
    parse_fdinfo_mount_id,
    pin_absolute_directory,
    publish_noreplace,
)


def _open_directory(path: Path) -> int:
    return os.open(
        path,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode()


def _import_for_test(
    source: Path,
    staging_parent: Path,
    leaf: str,
    *,
    observer=None,
) -> ImmutableTreeImportReceipt:
    for directory, names, files in os.walk(source, topdown=False):
        directory_path = Path(directory)
        for name in files:
            path = directory_path / name
            metadata = os.lstat(path)
            if stat.S_ISREG(metadata.st_mode):
                path.chmod(0o555 if metadata.st_mode & 0o111 else 0o444)
        for name in names:
            path = directory_path / name
            if not stat.S_ISLNK(os.lstat(path).st_mode):
                path.chmod(0o555)
        directory_path.chmod(0o555)
    source_fd = _open_directory(source)
    staging_parent_fd = _open_directory(staging_parent)
    try:
        owner = os.fstat(staging_parent_fd)
        return external_linux._import_immutable_tree(
            source_fd,
            staging_parent_fd,
            leaf,
            target_uid=owner.st_uid,
            target_gid=owner.st_gid,
            observer=observer,
        )
    finally:
        os.close(staging_parent_fd)
        os.close(source_fd)


def test_componentwise_pin_retains_and_revalidates_every_directory(
    tmp_path: Path,
) -> None:
    target = tmp_path / "one" / "two"
    target.mkdir(parents=True)

    pinned = pin_absolute_directory(str(target))
    try:
        assert pinned.path == str(target)
        assert stat.S_ISDIR(os.fstat(pinned.fd).st_mode)
        assert tuple(component.name for component in pinned.components[-2:]) == (
            "one",
            "two",
        )
        pinned.revalidate()

        original = tmp_path / "one" / "two-original"
        target.rename(original)
        target.mkdir()
        with pytest.raises(ExternalLinuxError, match="drifted"):
            pinned.revalidate()
    finally:
        pinned.close()


def test_componentwise_pin_rejects_symlink_component(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)

    with pytest.raises(OSError):
        pin_absolute_directory(str(alias))


def test_nonprivileged_import_seam_copies_exact_immutable_tree_and_roundtrips(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    staging_parent = tmp_path / "staging"
    source.mkdir()
    staging_parent.mkdir()
    (source / "data.txt").write_bytes(b"alpha\n")
    script = source / "tool"
    script.write_bytes(b"#!/bin/sh\nexit 0\n")
    script.chmod(0o755)
    nested = source / "nested"
    nested.mkdir()
    (nested / "payload.bin").write_bytes(b"\x00\x01\x02")

    receipt = _import_for_test(source, staging_parent, "hold")
    imported = staging_parent / "hold"

    assert (imported / "data.txt").read_bytes() == b"alpha\n"
    assert (imported / "nested" / "payload.bin").read_bytes() == b"\x00\x01\x02"
    assert stat.S_IMODE((imported / "data.txt").stat().st_mode) == 0o444
    assert stat.S_IMODE((imported / "tool").stat().st_mode) == 0o555
    assert stat.S_IMODE((imported / "nested").stat().st_mode) == 0o555
    assert stat.S_IMODE(imported.stat().st_mode) == 0o555
    assert tuple(entry.path for entry in receipt.entries) == (
        "data.txt",
        "nested",
        "nested/payload.bin",
        "tool",
    )
    assert ImmutableTreeImportReceipt.from_bytes(receipt.raw) == receipt
    assert len(receipt.tree_sha256) == 64
    assert len(receipt.raw_sha256) == 64


def test_import_rejects_mutable_source_mode(tmp_path: Path) -> None:
    source = tmp_path / "source"
    staging_parent = tmp_path / "staging"
    source.mkdir()
    staging_parent.mkdir()
    (source / "data").write_bytes(b"data")
    source.chmod(0o555)
    source_fd = _open_directory(source)
    staging_parent_fd = _open_directory(staging_parent)
    try:
        owner = os.fstat(staging_parent_fd)
        with pytest.raises(TreeImportHold):
            external_linux._import_immutable_tree(
                source_fd,
                staging_parent_fd,
                "hold",
                target_uid=owner.st_uid,
                target_gid=owner.st_gid,
            )
    finally:
        os.close(staging_parent_fd)
        os.close(source_fd)


def test_import_receipt_rejects_noncanonical_and_semantic_drift(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    staging_parent = tmp_path / "staging"
    source.mkdir()
    staging_parent.mkdir()
    (source / "data").write_bytes(b"data")
    receipt = _import_for_test(source, staging_parent, "hold")

    with pytest.raises(CanonicalImportReceiptError, match="not canonical"):
        ImmutableTreeImportReceipt.from_bytes(receipt.raw.rstrip(b"\n"))

    drift = json.loads(receipt.raw)
    drift["entries"][0]["mode"] = 0o666
    inventory = {
        "schema": "scion.immutable-tree-inventory.v1",
        "entries": drift["entries"],
    }
    drift["tree_sha256"] = external_linux.hashlib.sha256(
        external_linux._canonical_json(inventory)
    ).hexdigest()
    with pytest.raises(CanonicalImportReceiptError, match="binding differs"):
        ImmutableTreeImportReceipt.from_bytes(_canonical(drift))

    mutable_root = json.loads(receipt.raw)
    mutable_root["source_root"]["mode"] = (
        mutable_root["source_root"]["mode"] & ~0o7777
    ) | 0o755
    with pytest.raises(CanonicalImportReceiptError, match="immutable directory"):
        ImmutableTreeImportReceipt.from_bytes(_canonical(mutable_root))


@pytest.mark.parametrize("kind", ("symlink", "fifo", "hardlink"))
def test_import_rejects_unsafe_entry_and_preserves_staging_hold(
    tmp_path: Path,
    kind: str,
) -> None:
    source = tmp_path / f"source-{kind}"
    staging_parent = tmp_path / f"staging-{kind}"
    source.mkdir()
    staging_parent.mkdir()
    if kind == "symlink":
        (source / "target").write_bytes(b"x")
        (source / "bad").symlink_to("target")
    elif kind == "fifo":
        os.mkfifo(source / "bad")
    else:
        (source / "first").write_bytes(b"x")
        os.link(source / "first", source / "second")

    try:
        with pytest.raises(TreeImportHold):
            _import_for_test(source, staging_parent, "hold")

        assert (staging_parent / "hold").is_dir()
    finally:
        source.chmod(0o755)
        hold = staging_parent / "hold"
        if hold.is_dir():
            hold.chmod(0o755)


def test_import_detects_source_identity_drift_and_leaves_partial_hold(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    staging_parent = tmp_path / "staging"
    source.mkdir()
    staging_parent.mkdir()
    data = source / "data"
    data.write_bytes(b"before")

    def mutate(phase: str, relative: str) -> None:
        if phase == "after-file-copy" and relative == "data":
            data.write_bytes(b"after-and-different")

    with pytest.raises(TreeImportHold) as captured:
        _import_for_test(source, staging_parent, "hold", observer=mutate)

    assert captured.value.staging_leaf == "hold"
    assert (staging_parent / "hold" / "data").exists()


def test_public_root_import_checks_real_euid_before_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source"
    staging = tmp_path / "staging"
    source.mkdir()
    staging.mkdir()
    with (
        pin_absolute_directory(str(source)) as pinned_source,
        pin_absolute_directory(str(staging)) as pinned_staging,
    ):
        monkeypatch.setattr(external_linux.os, "geteuid", lambda: 1001)
        with pytest.raises(PermissionError, match="effective UID 0"):
            external_linux.import_root_owned_tree(
                pinned_source,
                pinned_staging,
                "hold",
            )
    assert not (staging / "hold").exists()


class _FakeAdapter:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []
        self.rename_error: Exception | None = None
        self.fsync_error: Exception | None = None
        self.private_error: Exception | None = None
        self.empty = True
        self.pre_mount_id = 20
        self._leaf_mount_reads = 0
        self.namespaces = {
            "self": NamespaceIdentity(device=4, inode=100),
            "pid1": NamespaceIdentity(device=4, inode=100),
        }

    def rename_noreplace(
        self,
        source_parent_fd: int,
        source_leaf: str,
        destination_parent_fd: int,
        destination_leaf: str,
    ) -> None:
        self.calls.append(
            (
                "rename_noreplace",
                source_parent_fd,
                source_leaf,
                destination_parent_fd,
                destination_leaf,
            )
        )
        if self.rename_error is not None:
            raise self.rename_error

    def fsync(self, descriptor: int) -> None:
        self.calls.append(("fsync", descriptor))
        if self.fsync_error is not None:
            raise self.fsync_error

    def open_tree_clone(self, source_fd: int) -> int:
        self.calls.append(("open_tree_clone", source_fd))
        return 90

    def move_mount_attach(
        self,
        tree_fd: int,
        destination_parent_fd: int,
        destination_leaf: str,
    ) -> None:
        self.calls.append(
            ("move_mount_attach", tree_fd, destination_parent_fd, destination_leaf)
        )

    def open_directory_at(self, parent_fd: int, leaf: str) -> int:
        self.calls.append(("open_directory_at", parent_fd, leaf))
        return 91

    def directory_is_empty(self, descriptor: int) -> bool:
        self.calls.append(("directory_is_empty", descriptor))
        return self.empty

    def make_private_recursive(self, descriptor: int) -> None:
        self.calls.append(("make_private_recursive", descriptor))
        if self.private_error is not None:
            raise self.private_error

    def remount_read_only(self, descriptor: int) -> None:
        self.calls.append(("remount_read_only", descriptor))

    def mount_id_for_fd(self, descriptor: int) -> int:
        self.calls.append(("mount_id_for_fd", descriptor))
        if descriptor == 50:
            return 12
        if descriptor == 60:
            return 20
        self._leaf_mount_reads += 1
        return self.pre_mount_id if self._leaf_mount_reads == 1 else 37

    def namespace_identity(self, subject: str) -> NamespaceIdentity:
        self.calls.append(("namespace_identity", subject))
        return self.namespaces[subject]

    def close_fd(self, descriptor: int) -> None:
        self.calls.append(("close_fd", descriptor))


def test_publish_noreplace_uses_exact_fds_and_fsyncs_both_parents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(external_linux.os, "geteuid", lambda: 0)
    adapter = _FakeAdapter()

    publish_noreplace(
        adapter,
        source_parent_fd=10,
        source_leaf="staged",
        destination_parent_fd=20,
        destination_leaf="final",
    )

    assert adapter.calls == [
        ("rename_noreplace", 10, "staged", 20, "final"),
        ("fsync", 20),
        ("fsync", 10),
    ]


def test_publish_noreplace_never_repairs_or_overwrites(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(external_linux.os, "geteuid", lambda: 0)
    adapter = _FakeAdapter()
    adapter.rename_error = FileExistsError("final")

    with pytest.raises(FileExistsError):
        publish_noreplace(
            adapter,
            source_parent_fd=10,
            source_leaf="staged",
            destination_parent_fd=20,
            destination_leaf="final",
        )

    assert adapter.calls == [
        ("rename_noreplace", 10, "staged", 20, "final"),
    ]

    durability_failure = _FakeAdapter()
    durability_failure.fsync_error = OSError("fsync failed")
    with pytest.raises(LinuxMutationHold, match="held at final"):
        publish_noreplace(
            durability_failure,
            source_parent_fd=10,
            source_leaf="staged",
            destination_parent_fd=20,
            destination_leaf="final",
        )
    assert durability_failure.calls == [
        ("rename_noreplace", 10, "staged", 20, "final"),
        ("fsync", 20),
    ]


def test_fd_bound_mount_attach_is_private_distinct_and_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(external_linux.os, "geteuid", lambda: 0)
    adapter = _FakeAdapter()

    attached = attach_cloned_mount(
        adapter,
        source_fd=50,
        destination_parent_fd=60,
        destination_leaf="sealed",
        read_only=True,
    )

    assert attached.source_mount_id == 12
    assert attached.destination_parent_mount_id == 20
    assert attached.destination_pre_mount_id == 20
    assert attached.destination_mount_id == 37
    assert attached.read_only
    assert adapter.calls == [
        ("mount_id_for_fd", 50),
        ("mount_id_for_fd", 60),
        ("open_directory_at", 60, "sealed"),
        ("directory_is_empty", 91),
        ("mount_id_for_fd", 91),
        ("close_fd", 91),
        ("open_tree_clone", 50),
        ("move_mount_attach", 90, 60, "sealed"),
        ("open_directory_at", 60, "sealed"),
        ("make_private_recursive", 91),
        ("remount_read_only", 91),
        ("mount_id_for_fd", 91),
        ("close_fd", 91),
        ("close_fd", 90),
    ]


def test_rw_mount_skips_ro_remount_and_post_attach_failure_is_hold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(external_linux.os, "geteuid", lambda: 0)
    rw_adapter = _FakeAdapter()
    attached = attach_cloned_mount(
        rw_adapter,
        source_fd=50,
        destination_parent_fd=60,
        destination_leaf="run",
        read_only=False,
    )
    assert not attached.read_only
    assert not any(call[0] == "remount_read_only" for call in rw_adapter.calls)

    failing = _FakeAdapter()
    failing.private_error = OSError("private propagation failed")
    with pytest.raises(LinuxMutationHold, match="held at sealed"):
        attach_cloned_mount(
            failing,
            source_fd=50,
            destination_parent_fd=60,
            destination_leaf="sealed",
            read_only=True,
        )
    assert failing.calls[-2:] == [("close_fd", 91), ("close_fd", 90)]


def test_mount_attach_rejects_nonempty_or_already_mounted_leaf_before_clone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(external_linux.os, "geteuid", lambda: 0)
    nonempty = _FakeAdapter()
    nonempty.empty = False
    with pytest.raises(ExternalLinuxError, match="not empty"):
        attach_cloned_mount(
            nonempty,
            source_fd=50,
            destination_parent_fd=60,
            destination_leaf="sealed",
            read_only=True,
        )
    assert not any(call[0] == "open_tree_clone" for call in nonempty.calls)

    mounted = _FakeAdapter()
    mounted.pre_mount_id = 99
    with pytest.raises(ExternalLinuxError, match="already a mount"):
        attach_cloned_mount(
            mounted,
            source_fd=50,
            destination_parent_fd=60,
            destination_leaf="sealed",
            read_only=True,
        )
    assert not any(call[0] == "open_tree_clone" for call in mounted.calls)


def test_mutation_checks_real_euid_before_fake_syscall(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(external_linux.os, "geteuid", lambda: 1001)
    adapter = _FakeAdapter()

    with pytest.raises(PermissionError, match="effective UID 0"):
        attach_cloned_mount(
            adapter,
            source_fd=50,
            destination_parent_fd=60,
            destination_leaf="sealed",
            read_only=True,
        )
    assert adapter.calls == []


def test_namespace_pair_and_fdinfo_mount_id_are_strict() -> None:
    adapter = _FakeAdapter()
    pair = acquire_mount_namespace_pair(adapter)
    assert pair == MountNamespacePair(
        self_namespace=NamespaceIdentity(device=4, inode=100),
        pid1_namespace=NamespaceIdentity(device=4, inode=100),
    )
    assert pair.matches
    assert parse_fdinfo_mount_id(b"pos:\t0\nflags:\t0100000\nmnt_id:\t37\n") == 37

    adapter.namespaces["pid1"] = NamespaceIdentity(device=4, inode=101)
    with pytest.raises(ExternalLinuxError, match="namespaces differ"):
        acquire_mount_namespace_pair(adapter)
    assert not acquire_mount_namespace_pair(adapter, require_same=False).matches

    with pytest.raises(ExternalLinuxError, match="one mount ID"):
        parse_fdinfo_mount_id(b"pos:\t0\n")
    with pytest.raises(ExternalLinuxError, match="one mount ID"):
        parse_fdinfo_mount_id(b"mnt_id:\t1\nmnt_id:\t2\n")


def test_production_adapter_is_final_and_has_no_rollback_surface() -> None:
    adapter = LinuxRootAdapter()
    with pytest.raises(TypeError, match="final"):
        type("Derived", (LinuxRootAdapter,), {})

    public_methods = {
        node.name
        for node in ast.walk(
            ast.parse(
                (
                    Path(__file__).parents[4]
                    / "runtime"
                    / "execution"
                    / "external_linux.py"
                ).read_text(encoding="utf-8")
            )
        )
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }
    assert "unmount" not in public_methods
    assert "cleanup" not in public_methods
    assert "overwrite" not in public_methods
    assert "remove" not in public_methods
    assert "unlink" not in public_methods
    assert "rmdir" not in public_methods
    assert not hasattr(adapter, "unmount")
