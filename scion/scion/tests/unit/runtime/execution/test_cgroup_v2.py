from __future__ import annotations

import copy
import os
import pickle
from pathlib import Path

import pytest

from scion.runtime.execution import cgroup_v2
from scion.runtime.execution.cgroup_v2 import (
    CgroupIntegrityError,
    CgroupStateError,
    CgroupValidationError,
    ServiceCgroup,
)
from scion.runtime.execution.model import JobCgroupKey
from scion.runtime.execution.systemd255 import (
    ConfiguredUnitProperties,
    InvocationLineage,
    Systemd255ContractError,
    UnitRole,
)


_UNIT = "scion-test.service"
_CLOSER = "scion-close.service"
_BOOT_ID = "12345678-1234-1234-1234-123456789abc"
_INVOCATION_ID = "a" * 32
_REAL_MKDIR_JOB_AT = cgroup_v2._mkdir_job_at
_REAL_RMDIR_JOB_AT = cgroup_v2._rmdir_job_at


def _configured_run() -> ConfiguredUnitProperties:
    return ConfiguredUnitProperties.from_receipts(
        UnitRole.RUN,
        {
            "Delegate": "pids",
            "DelegateSubgroup": "supervisor",
            "CollectMode": "inactive",
            "Restart": "no",
            "KillMode": "control-group",
            "TimeoutStopSec": "infinity",
            "OnSuccess": _CLOSER,
            "OnFailure": _CLOSER,
        },
        {
            "Id": _UNIT,
            "Delegate": "yes",
            "DelegateControllers": "pids",
            "DelegateSubgroup": "supervisor",
            "CollectMode": "inactive",
            "Restart": "no",
            "KillMode": "control-group",
            "TimeoutStopUSec": "infinity",
            "OnSuccess": _CLOSER,
            "OnFailure": _CLOSER,
        },
        expected_unit=_UNIT,
        expected_peer=_CLOSER,
    )


class _SyntheticDelegation:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.service = root / "test.slice" / _UNIT
        self.supervisor = self.service / "supervisor"
        self.proc_cgroup = root / "proc-self-cgroup"
        self.service.mkdir(parents=True)
        self.supervisor.mkdir()
        (root / "cgroup.controllers").write_bytes(b"pids cpu\n")
        (self.service / "cgroup.controllers").write_bytes(b"pids cpu\n")
        (self.service / "cgroup.subtree_control").write_bytes(b"pids\n")
        (self.service / "cgroup.procs").write_bytes(b"")
        (self.supervisor / "cgroup.procs").write_bytes(
            f"{os.getpid()}\n".encode("ascii")
        )
        self.proc_cgroup.write_bytes(
            f"0::/test.slice/{_UNIT}/supervisor\n".encode("ascii")
        )

    def lineage(
        self,
        *,
        pid: int | None = None,
        starttime: int | None = None,
        control_group: str | None = None,
    ) -> InvocationLineage:
        service_stat = self.service.stat()
        supervisor_stat = self.supervisor.stat()
        return InvocationLineage(
            boot_id=_BOOT_ID,
            unit=_UNIT,
            invocation_id=_INVOCATION_ID,
            control_group=control_group or f"/test.slice/{_UNIT}",
            service_device=service_stat.st_dev,
            service_inode=service_stat.st_ino,
            supervisor_device=supervisor_stat.st_dev,
            supervisor_inode=supervisor_stat.st_ino,
            main_pid=os.getpid() if pid is None else pid,
            main_starttime=(
                cgroup_v2._current_starttime() if starttime is None else starttime
            ),
        )

    def install_job_emulation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def mkdir_job(parent_fd: int, name: str) -> None:
            _REAL_MKDIR_JOB_AT(parent_fd, name)
            job = self.service / name
            (job / "cgroup.events").write_bytes(b"populated 0\nfrozen 0\n")
            (job / "cgroup.procs").write_bytes(b"")
            (job / "cgroup.kill").write_bytes(b"")

        def rmdir_job(parent_fd: int, name: str) -> None:
            job = self.service / name
            for child in job.iterdir():
                child.unlink()
            _REAL_RMDIR_JOB_AT(parent_fd, name)

        monkeypatch.setattr(cgroup_v2, "_mkdir_job_at", mkdir_job)
        monkeypatch.setattr(cgroup_v2, "_rmdir_job_at", rmdir_job)

    def reset_supervisor_pid(self, pid: int) -> None:
        (self.supervisor / "cgroup.procs").write_bytes(f"{pid}\n".encode("ascii"))


@pytest.fixture
def delegated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> _SyntheticDelegation:
    value = _SyntheticDelegation(tmp_path / "cgroup2")
    monkeypatch.setattr(cgroup_v2, "_CGROUP_ROOT", str(value.root))
    monkeypatch.setattr(cgroup_v2, "_PROC_SELF_CGROUP", str(value.proc_cgroup))
    return value


def _key(ordinal: int = 0) -> JobCgroupKey:
    return JobCgroupKey.create(ordinal=ordinal, invocation_nonce="b" * 64)


def test_open_current_pins_service_root_and_supervisor(
    delegated: _SyntheticDelegation,
) -> None:
    service = ServiceCgroup.open_current(_configured_run(), delegated.lineage())
    try:
        assert service.copied_lineage.service_name == _UNIT
        assert service.copied_lineage.supervisor_name == "supervisor"
        assert service.copied_lineage.service_relative_lineage == (
            _UNIT,
            "supervisor",
        )
        assert service.invocation_lineage.control_group == f"/test.slice/{_UNIT}"
        assert service.available_controllers == ("pids", "cpu")
        with pytest.raises(TypeError):
            copy.copy(service)
        with pytest.raises(TypeError):
            copy.deepcopy(service)
        with pytest.raises(TypeError):
            pickle.dumps(service)
    finally:
        service.close_unconsumed()
    with pytest.raises(CgroupStateError):
        service.close_unconsumed()


def test_control_group_receipt_is_service_root_not_supervisor_leaf(
    delegated: _SyntheticDelegation,
) -> None:
    with pytest.raises(Systemd255ContractError, match="service root"):
        delegated.lineage(
            control_group=f"/test.slice/{_UNIT}/supervisor",
        )


@pytest.mark.parametrize(
    ("relative_file", "data", "message"),
    [
        ("cgroup.procs", b"17\n", "service-root"),
        ("cgroup.subtree_control", b"pids cpu\n", "only pids"),
        ("supervisor/cgroup.procs", b"17\n", "supervisor"),
    ],
)
def test_open_rejects_invalid_delegated_boundary(
    delegated: _SyntheticDelegation,
    relative_file: str,
    data: bytes,
    message: str,
) -> None:
    (delegated.service / relative_file).write_bytes(data)
    with pytest.raises(CgroupValidationError, match=message):
        ServiceCgroup.open_current(_configured_run(), delegated.lineage())


def test_consume_invalidates_every_service_alias_and_job_removal_is_reusable(
    delegated: _SyntheticDelegation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delegated.install_job_emulation(monkeypatch)
    service = ServiceCgroup.open_current(_configured_run(), delegated.lineage())
    alias = service
    authority = service._consume()
    with pytest.raises(CgroupStateError):
        alias.copied_lineage

    job = authority._create_job(_key())
    assert job.key == _key()
    assert job.identity.service_relative_lineage == (_UNIT, _key().rendered_name)
    assert job.initial_events.populated == 0
    assert os.fstat(job._events_fileno()).st_ino > 0
    with pytest.raises(TypeError):
        copy.copy(job)
    with pytest.raises(TypeError):
        pickle.dumps(job)
    borrowed = job._consume_spawn_dirfd_borrow()
    assert os.fstat(borrowed).st_ino == job.identity.job_inode
    with pytest.raises(CgroupStateError, match="already"):
        job._consume_spawn_dirfd_borrow()

    assert job.remove_empty().populated == 0
    with pytest.raises(CgroupStateError):
        job._read_events()

    second = authority._create_job(_key(1))
    assert second.remove_empty().frozen == 0
    authority._close()


def test_events_kill_and_empty_proof_are_independent(
    delegated: _SyntheticDelegation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delegated.install_job_emulation(monkeypatch)
    service = ServiceCgroup.open_current(_configured_run(), delegated.lineage())
    authority = service._consume()
    job = authority._create_job(_key())
    job_path = delegated.service / job.identity.job_name
    (job_path / "cgroup.events").write_bytes(b"populated 1\nfrozen 0\npressure 7\n")
    events = job._read_events()
    assert events.populated == 1
    assert events.fields[-1] == ("pressure", 7)
    with pytest.raises(CgroupIntegrityError, match="not empty"):
        job.remove_empty()
    job._kill()
    assert (job_path / "cgroup.kill").read_bytes() == b"1\n"
    (job_path / "cgroup.events").write_bytes(b"populated 0\nfrozen 0\n")
    job.remove_empty()
    authority._close()


def test_blocked_leader_membership_is_checked_only_through_job_capability(
    delegated: _SyntheticDelegation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delegated.install_job_emulation(monkeypatch)
    service = ServiceCgroup.open_current(_configured_run(), delegated.lineage())
    authority = service._consume()
    job = authority._create_job(_key())
    job_path = delegated.service / job.identity.job_name
    borrowed = job._consume_spawn_dirfd_borrow()
    assert os.fstat(borrowed).st_ino == job.identity.job_inode
    procs = job_path / "cgroup.procs"
    procs.write_bytes(b"731\n")
    (job_path / "cgroup.events").write_bytes(b"populated 1\nfrozen 0\n")
    job._require_blocked_leader(731)
    with pytest.raises(TypeError, match="exact int"):
        job._require_blocked_leader(True)
    with pytest.raises(ValueError, match="positive"):
        job._require_blocked_leader(0)
    procs.write_bytes(b"731\n732\n")
    with pytest.raises(CgroupIntegrityError, match="only the exact blocked leader"):
        job._require_blocked_leader(731)
    procs.write_bytes(b"")
    (job_path / "cgroup.events").write_bytes(b"populated 0\nfrozen 0\n")
    job.remove_empty()
    authority._close()


def test_spawn_dirfd_borrow_rejects_drift_without_consuming_one_shot(
    delegated: _SyntheticDelegation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delegated.install_job_emulation(monkeypatch)
    authority = ServiceCgroup.open_current(
        _configured_run(), delegated.lineage()
    )._consume()
    job = authority._create_job(_key())
    job_path = delegated.service / job.identity.job_name

    (job_path / "cgroup.events").write_bytes(b"populated 1\nfrozen 0\n")
    with pytest.raises(CgroupIntegrityError, match="pre-native"):
        job._consume_spawn_dirfd_borrow()
    (job_path / "cgroup.events").write_bytes(b"populated 0\nfrozen 0\n")

    (job_path / "cgroup.procs").write_bytes(b"731\n")
    with pytest.raises(CgroupIntegrityError, match="unexpectedly has a process"):
        job._consume_spawn_dirfd_borrow()
    (job_path / "cgroup.procs").write_bytes(b"")

    nested = job_path / "nested"
    nested.mkdir()
    with pytest.raises(CgroupIntegrityError, match="nested"):
        job._consume_spawn_dirfd_borrow()
    nested.rmdir()

    delegated.reset_supervisor_pid(999)
    with pytest.raises(CgroupIntegrityError, match="supervisor process"):
        job._consume_spawn_dirfd_borrow()
    delegated.reset_supervisor_pid(os.getpid())

    assert job._consume_spawn_dirfd_borrow() == job._job_fd
    job.remove_empty()
    authority._close()


def test_blocked_leader_requires_borrow_events_topology_and_inventory(
    delegated: _SyntheticDelegation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delegated.install_job_emulation(monkeypatch)
    authority = ServiceCgroup.open_current(
        _configured_run(), delegated.lineage()
    )._consume()
    job = authority._create_job(_key())
    job_path = delegated.service / job.identity.job_name

    with pytest.raises(CgroupStateError, match="was not issued"):
        job._require_blocked_leader(731)
    job._consume_spawn_dirfd_borrow()
    (job_path / "cgroup.procs").write_bytes(b"731\n")
    with pytest.raises(CgroupIntegrityError, match="events"):
        job._require_blocked_leader(731)

    (job_path / "cgroup.events").write_bytes(b"populated 1\nfrozen 1\n")
    with pytest.raises(CgroupIntegrityError, match="events"):
        job._require_blocked_leader(731)
    (job_path / "cgroup.events").write_bytes(b"populated 1\nfrozen 0\n")

    nested = job_path / "nested"
    nested.mkdir()
    with pytest.raises(CgroupIntegrityError, match="nested"):
        job._require_blocked_leader(731)
    nested.rmdir()

    delegated.reset_supervisor_pid(999)
    with pytest.raises(CgroupIntegrityError, match="supervisor process"):
        job._require_blocked_leader(731)
    delegated.reset_supervisor_pid(os.getpid())

    job._require_blocked_leader(731)
    (job_path / "cgroup.procs").write_bytes(b"")
    (job_path / "cgroup.events").write_bytes(b"populated 0\nfrozen 0\n")
    job.remove_empty()
    authority._close()


def test_active_job_guard_is_checked_before_close_or_remove_mutation(
    delegated: _SyntheticDelegation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delegated.install_job_emulation(monkeypatch)
    authority = ServiceCgroup.open_current(
        _configured_run(), delegated.lineage()
    )._consume()
    job = authority._create_job(_key())
    job_path = delegated.service / job.identity.job_name
    job_fd = job._job_fd

    authority._active_job_id = id(job) + 1
    with pytest.raises(CgroupIntegrityError, match="not the active"):
        job.remove_empty()
    assert job_path.is_dir()
    assert os.fstat(job_fd).st_ino == job.identity.job_inode
    with pytest.raises(CgroupIntegrityError, match="not the active"):
        job.close_retained()
    assert job_path.is_dir()
    assert os.fstat(job_fd).st_ino == job.identity.job_inode

    authority._active_job_id = id(job)
    job.remove_empty()
    authority._close()


def test_close_retained_keeps_exact_name_and_permanently_prevents_reuse(
    delegated: _SyntheticDelegation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delegated.install_job_emulation(monkeypatch)
    service = ServiceCgroup.open_current(_configured_run(), delegated.lineage())
    authority = service._consume()
    job = authority._create_job(_key())
    job_name = job.identity.job_name
    assert job.close_retained().populated == 0
    assert (delegated.service / job_name).is_dir()
    with pytest.raises(CgroupStateError):
        authority._create_job(_key(1))
    (delegated.supervisor / "cgroup.procs").write_bytes(b"999\n")
    with pytest.raises(CgroupIntegrityError, match="supervisor process inventory drifted"):
        authority._close()
    delegated.reset_supervisor_pid(os.getpid())
    nested = delegated.supervisor / "unexpected"
    nested.mkdir()
    with pytest.raises(CgroupIntegrityError, match="supervisor gained"):
        authority._close()
    nested.rmdir()
    original = delegated.service / job_name
    hidden = delegated.root / "retained-original"
    original.rename(hidden)
    original.mkdir()
    with pytest.raises(CgroupIntegrityError, match="retained job cgroup identity drifted"):
        authority._close()
    original.rmdir()
    hidden.rename(original)
    authority._close()
    for child in (delegated.service / job_name).iterdir():
        child.unlink()
    (delegated.service / job_name).rmdir()


def test_mkdir_failure_before_creation_leaves_service_authority_reusable(
    delegated: _SyntheticDelegation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ServiceCgroup.open_current(_configured_run(), delegated.lineage())
    authority = service._consume()

    def denied(_parent_fd: int, _name: str) -> None:
        raise PermissionError(13, "denied before mkdir")

    monkeypatch.setattr(cgroup_v2, "_mkdir_job_at", denied)
    with pytest.raises(PermissionError):
        authority._create_job(_key())
    assert tuple(
        sorted(path.name for path in delegated.service.iterdir() if path.is_dir())
    ) == ("supervisor",)

    delegated.install_job_emulation(monkeypatch)
    job = authority._create_job(_key())
    job.remove_empty()
    authority._close()


def test_pinned_job_identity_drift_is_rejected_without_path_adoption(
    delegated: _SyntheticDelegation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delegated.install_job_emulation(monkeypatch)
    service = ServiceCgroup.open_current(_configured_run(), delegated.lineage())
    authority = service._consume()
    job = authority._create_job(_key())
    original = delegated.service / job.identity.job_name
    hidden = delegated.service / "hidden-original"
    original.rename(hidden)
    original.mkdir()
    try:
        with pytest.raises(CgroupIntegrityError, match="identity drifted"):
            job._read_events()
    finally:
        original.rmdir()
        hidden.rename(original)
    job.remove_empty()
    authority._close()


def test_partial_creation_enters_integrity_hold_and_cannot_be_retried(
    delegated: _SyntheticDelegation,
) -> None:
    child = os.fork()
    if child == 0:
        try:
            delegated.reset_supervisor_pid(os.getpid())
            lineage = delegated.lineage(
                pid=os.getpid(), starttime=cgroup_v2._current_starttime()
            )
            service = ServiceCgroup.open_current(_configured_run(), lineage)
            authority = service._consume()
            try:
                authority._create_job(_key())
            except CgroupIntegrityError as error:
                if "after exclusive mkdir" not in str(error):
                    os._exit(21)
            else:
                os._exit(22)
            try:
                authority._create_job(_key(1))
            except CgroupStateError:
                pass
            else:
                os._exit(23)
            try:
                authority._close()
            except CgroupIntegrityError:
                pass
            else:
                os._exit(24)
            os._exit(0)
        except BaseException:
            os._exit(25)
    waited, status = os.waitpid(child, 0)
    assert waited == child
    assert os.waitstatus_to_exitcode(status) == 0
    delegated.reset_supervisor_pid(os.getpid())


def test_mkdir_create_then_raise_is_integrity_hold_not_ordinary_create_failure(
    delegated: _SyntheticDelegation,
) -> None:
    child = os.fork()
    if child == 0:
        try:
            delegated.reset_supervisor_pid(os.getpid())
            lineage = delegated.lineage(
                pid=os.getpid(), starttime=cgroup_v2._current_starttime()
            )
            service = ServiceCgroup.open_current(_configured_run(), lineage)
            authority = service._consume()

            def create_then_raise(parent_fd: int, name: str) -> None:
                _REAL_MKDIR_JOB_AT(parent_fd, name)
                raise PermissionError(13, "injected after mkdir")

            cgroup_v2._mkdir_job_at = create_then_raise
            try:
                authority._create_job(_key())
            except CgroupIntegrityError as error:
                if "name is present" not in str(error):
                    os._exit(41)
            else:
                os._exit(42)
            try:
                authority._create_job(_key(1))
            except CgroupStateError:
                pass
            else:
                os._exit(43)
            try:
                authority._close()
            except CgroupIntegrityError:
                pass
            else:
                os._exit(44)
            os._exit(0)
        except BaseException:
            os._exit(45)
    waited, status = os.waitpid(child, 0)
    assert waited == child
    assert os.waitstatus_to_exitcode(status) == 0
    delegated.reset_supervisor_pid(os.getpid())


def test_creator_binding_rejects_fork_alias_without_closing_parent_authority(
    delegated: _SyntheticDelegation,
) -> None:
    service = ServiceCgroup.open_current(_configured_run(), delegated.lineage())
    child = os.fork()
    if child == 0:
        try:
            service.copied_lineage
        except CgroupStateError:
            os._exit(0)
        os._exit(31)
    waited, status = os.waitpid(child, 0)
    assert waited == child
    assert os.waitstatus_to_exitcode(status) == 0
    assert service.copied_lineage.service_name == _UNIT
    service.close_unconsumed()


def test_live_types_are_not_publicly_constructible_or_subclassable() -> None:
    with pytest.raises(TypeError):
        ServiceCgroup()
    with pytest.raises(TypeError):

        class Derived(ServiceCgroup):
            pass


def test_production_source_has_no_path_reopen_poll_timeout_or_sleep() -> None:
    source = Path(cgroup_v2.__file__).read_text(encoding="utf-8")
    assert "time.sleep" not in source
    assert "timeout" not in source.lower()
    assert "subprocess" not in source
    assert "killpg" not in source
    assert "cgroup.procs\", _OPEN_WRITE_FLAGS" not in source
    assert "os.path" not in source
