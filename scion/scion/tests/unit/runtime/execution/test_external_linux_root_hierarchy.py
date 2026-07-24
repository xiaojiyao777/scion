from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

import scion.runtime.execution.external_linux as external_linux
from scion.runtime.execution.external_linux import (
    ExternalLinuxError,
    FreshDirectorySpec,
    RegularPublicationSpec,
    RootDirectoryHierarchy,
    RootHierarchyHold,
    pin_absolute_directory,
)


@pytest.fixture(autouse=True)
def _root_euid_test_seam(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(external_linux.os, "geteuid", lambda: 0)


def _directory_specs() -> tuple[FreshDirectorySpec, ...]:
    uid = os.getuid()
    gid = os.getgid()
    return (
        FreshDirectorySpec(
            role="launch",
            parent_role=None,
            leaf="launch",
            mode=0o755,
            uid=uid,
            gid=gid,
        ),
        FreshDirectorySpec(
            role="receipts",
            parent_role="launch",
            leaf="receipts",
            mode=0o755,
            uid=uid,
            gid=gid,
        ),
    )


def _publication(
    *,
    raw: bytes = b'{"phase":"prepared"}\n',
) -> RegularPublicationSpec:
    return RegularPublicationSpec(
        role="phase",
        parent_role="receipts",
        leaf="phase.json",
        raw=raw,
        maximum=4096,
    )


def _create(anchor_path: Path) -> RootDirectoryHierarchy:
    with pin_absolute_directory(str(anchor_path)) as anchor:
        return RootDirectoryHierarchy.create_fresh(
            anchor,
            _directory_specs(),
        )


def test_create_publish_seal_and_read_only_reopen_are_exact(
    tmp_path: Path,
) -> None:
    anchor_path = tmp_path / "anchor"
    anchor_path.mkdir()
    specs = _directory_specs()
    publication = _publication()

    hierarchy = _create(anchor_path)
    try:
        launch = hierarchy.directory_observation("launch")
        receipts = hierarchy.directory_observation("receipts")
        assert not launch.sealed
        assert not receipts.sealed
        assert stat.S_IMODE(launch.identity.mode) == 0o755
        assert stat.S_IMODE(receipts.identity.mode) == 0o755
        assert (launch.identity.uid, launch.identity.gid) == (
            os.getuid(),
            os.getgid(),
        )

        published = hierarchy.publish_regular_noreplace(publication)
        assert published.identity.size == len(publication.raw)
        assert published.identity.link_count == 1
        assert stat.S_IMODE(published.identity.mode) == 0o444
        assert (anchor_path / "launch" / "receipts" / "phase.json").read_bytes() == (
            publication.raw
        )

        sealed = hierarchy.seal("receipts", ("phase.json",))
        assert sealed.sealed
        assert stat.S_IMODE(sealed.identity.mode) == 0o555
        directory_observations = (
            hierarchy.directory_observation("launch"),
            hierarchy.directory_observation("receipts"),
        )
        regular_observations = (hierarchy.regular_observation("phase"),)
    finally:
        hierarchy.close()

    with pin_absolute_directory(str(anchor_path)) as anchor:
        reopened = RootDirectoryHierarchy.reopen_exact(
            anchor,
            specs,
            directory_observations=directory_observations,
            regular_specs=(publication,),
            regular_observations=regular_observations,
        )
    try:
        assert reopened.directory_observation("receipts").sealed
        assert reopened.regular_observation("phase") == regular_observations[0]
    finally:
        reopened.close()


def test_create_requires_real_root_by_default_before_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    anchor_path = tmp_path / "anchor"
    anchor_path.mkdir()
    monkeypatch.setattr(external_linux.os, "geteuid", lambda: 1001)

    with pin_absolute_directory(str(anchor_path)) as anchor:
        with pytest.raises(PermissionError, match="effective UID 0"):
            RootDirectoryHierarchy.create_fresh(anchor, _directory_specs())

    assert tuple(anchor_path.iterdir()) == ()


def test_pinned_directory_opens_child_through_retained_parent(
    tmp_path: Path,
) -> None:
    parent_path = tmp_path / "parent"
    child_path = parent_path / "child"
    parent_path.mkdir()
    child_path.mkdir()

    with pin_absolute_directory(str(parent_path)) as parent:
        child = parent.open_child_directory("child")
    try:
        assert child.path == str(child_path)
        assert child.components[-1].name == "child"
        child.revalidate()

        moved = parent_path / "moved"
        child_path.rename(moved)
        child_path.mkdir()
        with pytest.raises(ExternalLinuxError, match="directory identity drifted"):
            child.revalidate()
    finally:
        child.close()


def test_production_hierarchy_rechecks_root_for_each_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    anchor_path = tmp_path / "anchor"
    anchor_path.mkdir()
    monkeypatch.setattr(external_linux.os, "geteuid", lambda: 0)
    with pin_absolute_directory(str(anchor_path)) as anchor:
        hierarchy = RootDirectoryHierarchy.create_fresh(anchor, _directory_specs())
    monkeypatch.setattr(external_linux.os, "geteuid", lambda: 1001)
    try:
        with pytest.raises(PermissionError, match="effective UID 0"):
            hierarchy.publish_regular_noreplace(_publication())
        assert not (anchor_path / "launch" / "receipts" / "phase.json").exists()
        with pytest.raises(PermissionError, match="effective UID 0"):
            hierarchy.seal("receipts", ())
        assert (
            stat.S_IMODE((anchor_path / "launch" / "receipts").stat().st_mode) == 0o755
        )
    finally:
        hierarchy.close()


def test_directory_topology_is_fully_validated_before_mkdir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    anchor_path = tmp_path / "anchor"
    anchor_path.mkdir()
    uid = os.getuid()
    gid = os.getgid()
    invalid = (
        FreshDirectorySpec(
            role="child",
            parent_role="missing",
            leaf="child",
            mode=0o755,
            uid=uid,
            gid=gid,
        ),
    )

    def forbidden_mkdir(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("mkdir must not run")

    monkeypatch.setattr(external_linux.os, "mkdir", forbidden_mkdir)
    with pin_absolute_directory(str(anchor_path)) as anchor:
        with pytest.raises(ExternalLinuxError, match="topological"):
            RootDirectoryHierarchy.create_fresh(
                anchor,
                invalid,
            )


@pytest.mark.parametrize("field", ("uid", "gid"))
@pytest.mark.parametrize("value", ((1 << 32) - 1, 1 << 100))
def test_owner_id_is_rejected_before_any_directory_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: int,
) -> None:
    anchor_path = tmp_path / "anchor"
    anchor_path.mkdir()

    def forbidden_mkdir(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("mkdir must not run")

    monkeypatch.setattr(external_linux.os, "mkdir", forbidden_mkdir)
    values = {
        "role": "launch",
        "parent_role": None,
        "leaf": "launch",
        "mode": 0o755,
        "uid": os.getuid(),
        "gid": os.getgid(),
    }
    values[field] = value
    with pytest.raises(ExternalLinuxError, match="uid_t/gid_t"):
        FreshDirectorySpec(**values)

    assert tuple(anchor_path.iterdir()) == ()


@pytest.mark.parametrize("collision", ("directory", "symlink"))
def test_create_collision_is_typed_hold_without_repair(
    tmp_path: Path,
    collision: str,
) -> None:
    anchor_path = tmp_path / "anchor"
    anchor_path.mkdir()
    collided = anchor_path / "launch"
    if collision == "directory":
        collided.mkdir()
    else:
        target = tmp_path / "target"
        target.mkdir()
        collided.symlink_to(target, target_is_directory=True)

    with pin_absolute_directory(str(anchor_path)) as anchor:
        with pytest.raises(RootHierarchyHold, match="create.*launch:launch"):
            RootDirectoryHierarchy.create_fresh(
                anchor,
                _directory_specs(),
            )

    assert os.path.lexists(collided)
    if collision == "symlink":
        assert collided.is_symlink()


def test_partial_directory_failure_is_held_and_never_cleaned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    anchor_path = tmp_path / "anchor"
    anchor_path.mkdir()
    real_mkdir = external_linux.os.mkdir
    calls = 0

    def fail_second(
        path: str,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected second mkdir failure")
        real_mkdir(path, mode, dir_fd=dir_fd)

    monkeypatch.setattr(external_linux.os, "mkdir", fail_second)
    with pin_absolute_directory(str(anchor_path)) as anchor:
        with pytest.raises(RootHierarchyHold, match="create.*receipts"):
            RootDirectoryHierarchy.create_fresh(
                anchor,
                _directory_specs(),
            )

    assert (anchor_path / "launch").is_dir()
    assert not (anchor_path / "launch" / "receipts").exists()


@pytest.mark.parametrize("collision", ("file", "symlink"))
def test_regular_collision_is_typed_hold_and_never_overwrites(
    tmp_path: Path,
    collision: str,
) -> None:
    anchor_path = tmp_path / "anchor"
    anchor_path.mkdir()
    hierarchy = _create(anchor_path)
    destination = anchor_path / "launch" / "receipts" / "phase.json"
    if collision == "file":
        destination.write_bytes(b"existing\n")
    else:
        target = tmp_path / "target"
        target.write_bytes(b"target\n")
        destination.symlink_to(target)
    try:
        with pytest.raises(RootHierarchyHold, match="publish.*phase:phase.json"):
            hierarchy.publish_regular_noreplace(_publication())
        if collision == "file":
            assert destination.read_bytes() == b"existing\n"
        else:
            assert destination.is_symlink()
            assert target.read_bytes() == b"target\n"
    finally:
        hierarchy.close()


def test_short_write_leaves_partial_file_and_holds_capability(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    anchor_path = tmp_path / "anchor"
    anchor_path.mkdir()
    hierarchy = _create(anchor_path)
    real_write = external_linux.os.write
    calls = 0

    def short_write(descriptor: int, raw: bytes) -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            return real_write(descriptor, raw[:1])
        return 0

    monkeypatch.setattr(external_linux.os, "write", short_write)
    try:
        with pytest.raises(RootHierarchyHold, match="publish.*phase:phase.json"):
            hierarchy.publish_regular_noreplace(_publication(raw=b"payload\n"))
        partial = anchor_path / "launch" / "receipts" / "phase.json"
        assert partial.read_bytes() == b"p"
        assert hierarchy.held
        with pytest.raises(RootHierarchyHold, match="reuse"):
            hierarchy.publish_regular_noreplace(
                RegularPublicationSpec(
                    role="later",
                    parent_role="receipts",
                    leaf="later",
                    raw=b"later\n",
                    maximum=16,
                )
            )
    finally:
        hierarchy.close()


def test_anchor_named_replacement_holds_before_publication(
    tmp_path: Path,
) -> None:
    anchor_path = tmp_path / "anchor"
    anchor_path.mkdir()
    hierarchy = _create(anchor_path)
    moved = tmp_path / "anchor-original"
    anchor_path.rename(moved)
    anchor_path.mkdir()
    try:
        with pytest.raises(RootHierarchyHold, match="publish.*phase"):
            hierarchy.publish_regular_noreplace(_publication())
        assert not (anchor_path / "launch").exists()
        assert not (moved / "launch" / "receipts" / "phase.json").exists()
        assert hierarchy.held
    finally:
        hierarchy.close()


def test_regular_identity_drift_and_hardlink_are_rejected(
    tmp_path: Path,
) -> None:
    anchor_path = tmp_path / "anchor"
    anchor_path.mkdir()
    hierarchy = _create(anchor_path)
    publication = _publication()
    hierarchy.publish_regular_noreplace(publication)
    destination = anchor_path / "launch" / "receipts" / publication.leaf
    hardlink = tmp_path / "hardlink"
    os.link(destination, hardlink)
    try:
        with pytest.raises(ExternalLinuxError, match="drifted"):
            hierarchy.regular_observation(publication.role)
        with pytest.raises(RootHierarchyHold, match="seal"):
            hierarchy.seal("receipts", ("phase.json",))
        assert destination.exists()
        assert hardlink.exists()
    finally:
        hierarchy.close()


def test_regular_named_replacement_during_read_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    anchor_path = tmp_path / "anchor"
    anchor_path.mkdir()
    hierarchy = _create(anchor_path)
    publication = _publication(raw=b"accepted\n")
    hierarchy.publish_regular_noreplace(publication)
    destination = anchor_path / "launch" / "receipts" / publication.leaf
    moved = tmp_path / "phase-original"
    real_read = external_linux.os.read
    swapped = False

    def swap_then_read(descriptor: int, count: int) -> bytes:
        nonlocal swapped
        if not swapped:
            swapped = True
            destination.rename(moved)
            destination.write_bytes(b"replaced\n")
            destination.chmod(0o444)
        return real_read(descriptor, count)

    monkeypatch.setattr(external_linux.os, "read", swap_then_read)
    try:
        with pytest.raises(ExternalLinuxError, match="drifted"):
            hierarchy.regular_observation(publication.role)
        assert moved.read_bytes() == publication.raw
        assert destination.read_bytes() == b"replaced\n"
    finally:
        hierarchy.close()


def test_parent_directory_replacement_during_write_is_held(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    anchor_path = tmp_path / "anchor"
    anchor_path.mkdir()
    hierarchy = _create(anchor_path)
    publication = _publication(raw=b"accepted\n")
    receipts = anchor_path / "launch" / "receipts"
    moved = tmp_path / "receipts-original"
    real_write = external_linux.os.write
    swapped = False

    def swap_then_write(descriptor: int, raw: bytes) -> int:
        nonlocal swapped
        if not swapped:
            swapped = True
            receipts.rename(moved)
            receipts.mkdir(mode=0o755)
        return real_write(descriptor, raw)

    monkeypatch.setattr(external_linux.os, "write", swap_then_write)
    try:
        with pytest.raises(RootHierarchyHold, match="publish.*phase"):
            hierarchy.publish_regular_noreplace(publication)
        assert not (receipts / publication.leaf).exists()
        assert (moved / publication.leaf).read_bytes() == publication.raw
        assert hierarchy.held
    finally:
        hierarchy.close()


def test_parent_directory_replacement_during_read_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    anchor_path = tmp_path / "anchor"
    anchor_path.mkdir()
    hierarchy = _create(anchor_path)
    publication = _publication(raw=b"accepted\n")
    hierarchy.publish_regular_noreplace(publication)
    receipts = anchor_path / "launch" / "receipts"
    moved = tmp_path / "receipts-original"
    real_read = external_linux.os.read
    swapped = False

    def swap_then_read(descriptor: int, count: int) -> bytes:
        nonlocal swapped
        if not swapped:
            swapped = True
            receipts.rename(moved)
            receipts.mkdir(mode=0o755)
        return real_read(descriptor, count)

    monkeypatch.setattr(external_linux.os, "read", swap_then_read)
    try:
        with pytest.raises(ExternalLinuxError, match="drifted"):
            hierarchy.regular_observation(publication.role)
        assert not (receipts / publication.leaf).exists()
        assert (moved / publication.leaf).read_bytes() == publication.raw
    finally:
        hierarchy.close()


def test_seal_rejects_inventory_drift_without_repair(
    tmp_path: Path,
) -> None:
    anchor_path = tmp_path / "anchor"
    anchor_path.mkdir()
    hierarchy = _create(anchor_path)
    publication = _publication()
    hierarchy.publish_regular_noreplace(publication)
    receipts = anchor_path / "launch" / "receipts"
    unexpected = receipts / "unexpected"
    unexpected.write_bytes(b"drift\n")
    try:
        with pytest.raises(RootHierarchyHold, match="seal.*receipts"):
            hierarchy.seal("receipts", ("phase.json",))
        assert unexpected.read_bytes() == b"drift\n"
        assert stat.S_IMODE(receipts.stat().st_mode) == 0o755
    finally:
        hierarchy.close()


def test_parent_seal_requires_every_child_directory_sealed(
    tmp_path: Path,
) -> None:
    anchor_path = tmp_path / "anchor"
    anchor_path.mkdir()
    hierarchy = _create(anchor_path)
    launch_path = anchor_path / "launch"
    try:
        with pytest.raises(ExternalLinuxError, match="unsealed child"):
            hierarchy.seal("launch", ("receipts",))
        assert stat.S_IMODE(launch_path.stat().st_mode) == 0o755

        hierarchy.seal("receipts", ())
        hierarchy.seal("launch", ("receipts",))
        assert stat.S_IMODE(launch_path.stat().st_mode) == 0o555
    finally:
        hierarchy.close()


def test_reopen_rejects_sealed_parent_with_unsealed_child(
    tmp_path: Path,
) -> None:
    anchor_path = tmp_path / "anchor"
    anchor_path.mkdir()
    specs = _directory_specs()
    hierarchy = _create(anchor_path)
    hierarchy.close()
    (anchor_path / "launch").chmod(0o555)
    observations = (
        _fresh_directory_observation(
            anchor_path,
            specs,
            role="launch",
            sealed=True,
        ),
        _fresh_directory_observation(
            anchor_path,
            specs,
            role="receipts",
            sealed=False,
        ),
    )

    with pin_absolute_directory(str(anchor_path)) as anchor:
        with pytest.raises(ExternalLinuxError, match="unsealed child"):
            RootDirectoryHierarchy.reopen_exact(
                anchor,
                specs,
                directory_observations=observations,
            )


def test_post_chmod_seal_failure_keeps_0555_partial_hold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    anchor_path = tmp_path / "anchor"
    anchor_path.mkdir()
    hierarchy = _create(anchor_path)
    receipts = anchor_path / "launch" / "receipts"

    def fail_fsync(descriptor: int) -> None:
        del descriptor
        raise OSError("injected durability failure")

    monkeypatch.setattr(external_linux.os, "fsync", fail_fsync)
    try:
        with pytest.raises(RootHierarchyHold, match="seal.*receipts"):
            hierarchy.seal("receipts", ())
        assert stat.S_IMODE(receipts.stat().st_mode) == 0o555
        assert hierarchy.held
    finally:
        hierarchy.close()


def test_reopen_rejects_symlink_and_extra_inventory(
    tmp_path: Path,
) -> None:
    anchor_path = tmp_path / "anchor"
    anchor_path.mkdir()
    specs = _directory_specs()
    hierarchy = _create(anchor_path)
    observations = (
        hierarchy.directory_observation("launch"),
        hierarchy.directory_observation("receipts"),
    )
    hierarchy.close()

    receipts = anchor_path / "launch" / "receipts"
    moved = anchor_path / "launch" / "receipts-original"
    receipts.rename(moved)
    receipts.symlink_to(moved, target_is_directory=True)
    with pin_absolute_directory(str(anchor_path)) as anchor:
        with pytest.raises(OSError):
            RootDirectoryHierarchy.reopen_exact(
                anchor,
                specs,
                directory_observations=observations,
            )

    receipts.unlink()
    moved.rename(receipts)
    (receipts / "unexpected").write_bytes(b"x")
    fresh_observations = list(observations)
    fresh_observations[0] = _fresh_directory_observation(
        anchor_path,
        specs,
        role="launch",
        sealed=False,
    )
    fresh_observations[1] = _fresh_directory_observation(
        anchor_path,
        specs,
        role="receipts",
        sealed=False,
    )
    with pin_absolute_directory(str(anchor_path)) as anchor:
        with pytest.raises(ExternalLinuxError, match="inventory"):
            RootDirectoryHierarchy.reopen_exact(
                anchor,
                specs,
                directory_observations=tuple(fresh_observations),
            )


def _fresh_directory_observation(
    anchor_path: Path,
    specs: tuple[FreshDirectorySpec, ...],
    *,
    role: str,
    sealed: bool,
) -> external_linux.DirectoryObservation:
    path_by_role = {
        "launch": anchor_path / "launch",
        "receipts": anchor_path / "launch" / "receipts",
    }
    spec = next(item for item in specs if item.role == role)
    return external_linux.DirectoryObservation(
        role=role,
        parent_role=spec.parent_role,
        leaf=spec.leaf,
        identity=external_linux.FileIdentity.from_stat(path_by_role[role].stat()),
        sealed=sealed,
    )
