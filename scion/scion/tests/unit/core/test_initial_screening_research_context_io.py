from __future__ import annotations

import fcntl
import os
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from scion.core import initial_screening_research_context_io as io_module
from scion.core.initial_screening_problem_spec_io import _publish_third_control
from scion.core.initial_screening_research_context import (
    _ERROR,
    _InitialScreeningResearchContextError,
)
from scion.core.initial_screening_research_context_io import (
    _publish_fourth_control,
    _validate_fourth_control_publication,
)
from scion.core.initial_screening_study_controls_io import (
    _ControlsPublication,
    _leaf_fingerprint,
    _publish_attached_control,
    _publish_controls,
)

_FIRST = "initial_screening_study_controls.json"
_SECOND = "initial_screening_provider_policy.json"
_THIRD = "initial_screening_problem_spec.json"
_FOURTH = "initial_screening_research_context.json"
_FIRST_PAYLOAD = b'{"leaf":1}\n'
_SECOND_PAYLOAD = b'{"leaf":2}\n'
_THIRD_PAYLOAD = b'{"leaf":3}\n'
_FOURTH_PAYLOAD = b'{"leaf":4}\n'
_MAX_BYTES = 64 << 20


@dataclass(frozen=True)
class _ThreeLeaves:
    root: Path
    publication: _ControlsPublication
    second_fingerprint: tuple[int, int, int, int]
    third_fingerprint: tuple[int, int, int, int]

    def publish_kwargs(self) -> dict[str, Any]:
        return {
            "first_filename": _FIRST,
            "first_payload": _FIRST_PAYLOAD,
            "second_filename": _SECOND,
            "second_payload": _SECOND_PAYLOAD,
            "second_fingerprint": self.second_fingerprint,
            "third_filename": _THIRD,
            "third_payload": _THIRD_PAYLOAD,
            "third_fingerprint": self.third_fingerprint,
            "filename": _FOURTH,
            "payload": _FOURTH_PAYLOAD,
            "max_bytes": _MAX_BYTES,
        }


class _InjectedFailure(Exception):
    pass


def _publish_three(tmp_path: Path) -> _ThreeLeaves:
    root = tmp_path / "campaign"
    publication = _publish_controls(
        str(root),
        _FIRST_PAYLOAD,
        protected_roots=(),
        filename=_FIRST,
        max_bytes=len(_FIRST_PAYLOAD),
    )
    second_fingerprint = _publish_attached_control(
        publication,
        _SECOND_PAYLOAD,
        filename=_SECOND,
        first_filename=_FIRST,
        max_bytes=len(_SECOND_PAYLOAD),
    )
    third_fingerprint = _publish_third_control(
        publication,
        first_filename=_FIRST,
        first_payload=_FIRST_PAYLOAD,
        second_filename=_SECOND,
        second_payload=_SECOND_PAYLOAD,
        second_fingerprint=second_fingerprint,
        filename=_THIRD,
        payload=_THIRD_PAYLOAD,
        max_bytes=len(_THIRD_PAYLOAD),
    )
    return _ThreeLeaves(
        root=root,
        publication=publication,
        second_fingerprint=second_fingerprint,
        third_fingerprint=third_fingerprint,
    )


def _publish_four(setup: _ThreeLeaves) -> tuple[int, int, int, int]:
    return _publish_fourth_control(setup.publication, **setup.publish_kwargs())


def _validate_four(
    setup: _ThreeLeaves,
    fingerprint: tuple[int, int, int, int],
    *,
    require_exact_names: bool,
) -> None:
    _validate_fourth_control_publication(
        setup.publication,
        **setup.publish_kwargs(),
        fingerprint=fingerprint,
        require_exact_names=require_exact_names,
    )


def _assert_fixed_failure(call: Callable[[], Any]) -> None:
    with pytest.raises(_InitialScreeningResearchContextError) as caught:
        call()
    error = caught.value
    assert type(error) is _InitialScreeningResearchContextError
    assert error.args == (_ERROR,)
    assert str(error) == _ERROR
    assert error.__cause__ is None
    assert error.__context__ is None


def _assert_prior_three_unchanged(setup: _ThreeLeaves) -> None:
    assert (setup.root / _FIRST).read_bytes() == _FIRST_PAYLOAD
    assert (setup.root / _SECOND).read_bytes() == _SECOND_PAYLOAD
    assert (setup.root / _THIRD).read_bytes() == _THIRD_PAYLOAD
    assert _leaf_fingerprint((setup.root / _FIRST).stat()) == (
        setup.publication.leaf_fingerprint
    )
    assert _leaf_fingerprint((setup.root / _SECOND).stat()) == (
        setup.second_fingerprint
    )
    assert _leaf_fingerprint((setup.root / _THIRD).stat()) == (setup.third_fingerprint)


def _assert_prior_three_exact(setup: _ThreeLeaves) -> None:
    assert {path.name for path in setup.root.iterdir()} == {_FIRST, _SECOND, _THIRD}
    _assert_prior_three_unchanged(setup)


def _assert_fourth_reserved(setup: _ThreeLeaves, payload: bytes) -> None:
    _assert_prior_three_unchanged(setup)
    leaf = setup.root / _FOURTH
    assert leaf.exists()
    assert leaf.read_bytes() == payload
    assert {_FIRST, _SECOND, _THIRD, _FOURTH}.issubset(
        {path.name for path in setup.root.iterdir()}
    )


def _replace_leaf(path: Path, replacement: Path, payload: bytes) -> None:
    replacement.write_bytes(payload)
    replacement.chmod(0o600)
    os.replace(replacement, path)


def test_publish_fourth_leaf_and_fresh_validator_accept_exact_carrier(
    tmp_path: Path,
) -> None:
    setup = _publish_three(tmp_path)

    fingerprint = _publish_four(setup)
    leaf = setup.root / _FOURTH

    assert leaf.read_bytes() == _FOURTH_PAYLOAD
    assert stat.S_IMODE(leaf.stat().st_mode) == 0o600
    assert leaf.stat().st_uid == os.geteuid()
    assert leaf.stat().st_nlink == 1
    assert _leaf_fingerprint(leaf.stat()) == fingerprint
    identities = {
        (setup.root.stat().st_dev, setup.root.stat().st_ino),
        setup.publication.leaf_fingerprint[:2],
        setup.second_fingerprint[:2],
        setup.third_fingerprint[:2],
        fingerprint[:2],
    }
    assert len(identities) == 5
    _validate_four(setup, fingerprint, require_exact_names=True)


def test_fresh_validator_can_allow_later_root_artifacts(tmp_path: Path) -> None:
    setup = _publish_three(tmp_path)
    fingerprint = _publish_four(setup)
    (setup.root / "later-runtime-artifact.json").write_bytes(b"{}\n")

    _validate_four(setup, fingerprint, require_exact_names=False)
    with pytest.raises(ValueError):
        _validate_four(setup, fingerprint, require_exact_names=True)


@pytest.mark.parametrize(
    "change",
    ["missing", "extra", "root_permissions", "leaf_permissions", "prior_swap"],
)
def test_failure_before_create_has_no_fourth_leaf(
    tmp_path: Path,
    change: str,
) -> None:
    setup = _publish_three(tmp_path)
    if change == "missing":
        (setup.root / _THIRD).unlink()
    elif change == "extra":
        (setup.root / "unexpected.json").write_bytes(b"{}\n")
    elif change == "root_permissions":
        setup.root.chmod(0o755)
    elif change == "leaf_permissions":
        (setup.root / _SECOND).chmod(0o640)
    else:
        _replace_leaf(
            setup.root / _SECOND,
            tmp_path / "replacement-provider.json",
            _SECOND_PAYLOAD,
        )

    _assert_fixed_failure(lambda: _publish_four(setup))

    assert not (setup.root / _FOURTH).exists()


def test_create_rejects_root_with_different_effective_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = _publish_three(tmp_path)
    actual_euid = os.geteuid()
    monkeypatch.setattr(io_module.os, "geteuid", lambda: actual_euid + 1)

    _assert_fixed_failure(lambda: _publish_four(setup))

    assert not (setup.root / _FOURTH).exists()


@pytest.mark.parametrize("entry_kind", ["symlink", "fifo", "directory"])
def test_create_refuses_existing_fourth_entry_without_removing_it(
    tmp_path: Path,
    entry_kind: str,
) -> None:
    setup = _publish_three(tmp_path)
    leaf = setup.root / _FOURTH
    if entry_kind == "symlink":
        leaf.symlink_to(setup.root / _FIRST)
    elif entry_kind == "fifo":
        os.mkfifo(leaf, mode=0o600)
    else:
        leaf.mkdir(mode=0o700)

    _assert_fixed_failure(lambda: _publish_four(setup))

    assert os.path.lexists(leaf)


def test_create_rejects_hardlinked_prior_leaf_without_removing_it(
    tmp_path: Path,
) -> None:
    setup = _publish_three(tmp_path)
    hardlink = setup.root / "linked-control.json"
    os.link(setup.root / _FIRST, hardlink)

    _assert_fixed_failure(lambda: _publish_four(setup))

    assert hardlink.samefile(setup.root / _FIRST)
    assert not (setup.root / _FOURTH).exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("filename", _THIRD),
        ("second_fingerprint", (1, 2, 3)),
        ("third_fingerprint", (1, 2, 3, True)),
        ("max_bytes", True),
        ("max_bytes", _MAX_BYTES + 1),
        ("max_bytes", len(_FOURTH_PAYLOAD) - 1),
    ],
)
def test_invalid_inputs_fail_privately_before_fourth_creation(
    tmp_path: Path,
    field: str,
    value: Any,
) -> None:
    setup = _publish_three(tmp_path)
    kwargs = setup.publish_kwargs()
    kwargs[field] = value

    _assert_fixed_failure(lambda: _publish_fourth_control(setup.publication, **kwargs))

    _assert_prior_three_exact(setup)


def test_write_all_accepts_partial_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = _publish_three(tmp_path)
    original_write = os.write
    partial_calls = 0

    def partial_write(fd: int, payload: bytes) -> int:
        nonlocal partial_calls
        partial_calls += 1
        return original_write(fd, payload[:2])

    monkeypatch.setattr(io_module.os, "write", partial_write)

    fingerprint = _publish_four(setup)

    assert partial_calls > 1
    assert (setup.root / _FOURTH).read_bytes() == _FOURTH_PAYLOAD
    assert _leaf_fingerprint((setup.root / _FOURTH).stat()) == fingerprint


@pytest.mark.parametrize("written_prefix", [0, 3])
def test_write_failure_retains_irreversible_fourth_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    written_prefix: int,
) -> None:
    setup = _publish_three(tmp_path)
    original_write = os.write
    calls = 0

    def fail_write(fd: int, payload: bytes) -> int:
        nonlocal calls
        calls += 1
        if calls == 1 and written_prefix:
            return original_write(fd, payload[:written_prefix])
        raise _InjectedFailure("private write detail")

    monkeypatch.setattr(io_module.os, "write", fail_write)

    _assert_fixed_failure(lambda: _publish_four(setup))

    _assert_fourth_reserved(setup, _FOURTH_PAYLOAD[:written_prefix])


def test_fchmod_failure_retains_irreversible_fourth_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = _publish_three(tmp_path)

    def fail_fchmod(_fd: int, _mode: int) -> None:
        raise _InjectedFailure("private fchmod detail")

    monkeypatch.setattr(io_module.os, "fchmod", fail_fchmod)

    _assert_fixed_failure(lambda: _publish_four(setup))

    _assert_fourth_reserved(setup, b"")


def test_fourth_fstat_failure_retains_irreversible_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = _publish_three(tmp_path)
    original_fstat = os.fstat

    def fail_fourth_fstat(fd: int) -> os.stat_result:
        try:
            target = os.readlink(f"/proc/self/fd/{fd}")
        except OSError:
            target = ""
        if target.endswith(f"/{_FOURTH}"):
            raise _InjectedFailure("private fstat detail")
        return original_fstat(fd)

    monkeypatch.setattr(io_module.os, "fstat", fail_fourth_fstat)

    _assert_fixed_failure(lambda: _publish_four(setup))

    _assert_fourth_reserved(setup, b"")


@pytest.mark.parametrize("failure_call", [1, 2])
def test_leaf_or_root_fsync_failure_retains_fourth_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_call: int,
) -> None:
    setup = _publish_three(tmp_path)
    original_fsync = os.fsync
    calls = 0

    def fail_selected_fsync(fd: int) -> None:
        nonlocal calls
        calls += 1
        if calls == failure_call:
            raise _InjectedFailure("private fsync detail")
        original_fsync(fd)

    monkeypatch.setattr(io_module.os, "fsync", fail_selected_fsync)

    _assert_fixed_failure(lambda: _publish_four(setup))

    _assert_fourth_reserved(setup, _FOURTH_PAYLOAD)


@pytest.mark.parametrize("validation_call", [1, 2, 3])
def test_held_or_fresh_validation_failure_retains_fourth_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    validation_call: int,
) -> None:
    setup = _publish_three(tmp_path)
    original_verify = io_module._verify_all_four
    calls = 0

    def fail_selected_validation(*args: Any, **kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        if calls == validation_call:
            raise _InjectedFailure("private validation detail")
        original_verify(*args, **kwargs)

    monkeypatch.setattr(io_module, "_verify_all_four", fail_selected_validation)

    _assert_fixed_failure(lambda: _publish_four(setup))

    assert calls == validation_call
    _assert_fourth_reserved(setup, _FOURTH_PAYLOAD)


def test_postcreate_identity_failure_retains_fourth_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = _publish_three(tmp_path)
    original_validate = io_module._validate_identity_separation
    calls = 0

    def fail_second_identity(*args: Any, **kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise _InjectedFailure("private identity detail")
        original_validate(*args, **kwargs)

    monkeypatch.setattr(
        io_module,
        "_validate_identity_separation",
        fail_second_identity,
    )

    _assert_fixed_failure(lambda: _publish_four(setup))

    assert calls == 2
    _assert_fourth_reserved(setup, _FOURTH_PAYLOAD)


@pytest.mark.parametrize("open_call", [2, 3])
def test_fresh_rewalk_open_failure_retains_fourth_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    open_call: int,
) -> None:
    setup = _publish_three(tmp_path)
    original_open_root = io_module._open_expected_root
    calls = 0

    def fail_selected_open(*args: Any, **kwargs: Any) -> int:
        nonlocal calls
        calls += 1
        if calls == open_call:
            raise _InjectedFailure("private rewalk detail")
        return original_open_root(*args, **kwargs)

    monkeypatch.setattr(io_module, "_open_expected_root", fail_selected_open)

    _assert_fixed_failure(lambda: _publish_four(setup))

    assert calls == open_call
    _assert_fourth_reserved(setup, _FOURTH_PAYLOAD)


def test_foreign_replacement_after_check_survives_and_unlink_is_never_called(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = _publish_three(tmp_path)
    replacement = tmp_path / "foreign-fourth.json"
    replacement.write_bytes(b"foreign fourth\n")
    replacement.chmod(0o600)
    unlink_calls = 0

    def replace_then_fail(*_args: Any, **_kwargs: Any) -> None:
        os.replace(replacement, setup.root / _FOURTH)
        raise _InjectedFailure("private post-check detail")

    def count_unlink(*_args: Any, **_kwargs: Any) -> None:
        nonlocal unlink_calls
        unlink_calls += 1
        raise AssertionError("publisher must not unlink after O_EXCL")

    monkeypatch.setattr(io_module, "_verify_all_four", replace_then_fail)
    monkeypatch.setattr(io_module.os, "unlink", count_unlink)

    _assert_fixed_failure(lambda: _publish_four(setup))

    assert unlink_calls == 0
    assert (setup.root / _FOURTH).read_bytes() == b"foreign fourth\n"
    _assert_prior_three_unchanged(setup)


def test_residual_fourth_reservation_makes_second_setup_fail_privately(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = _publish_three(tmp_path)
    original_write = os.write

    def fail_write(_fd: int, _payload: bytes) -> int:
        raise _InjectedFailure("private first attempt detail")

    monkeypatch.setattr(io_module.os, "write", fail_write)
    _assert_fixed_failure(lambda: _publish_four(setup))
    retained = (setup.root / _FOURTH).stat()
    monkeypatch.setattr(io_module.os, "write", original_write)

    _assert_fixed_failure(lambda: _publish_four(setup))

    current = (setup.root / _FOURTH).stat()
    assert _leaf_fingerprint(current) == _leaf_fingerprint(retained)
    _assert_fourth_reserved(setup, b"")


def test_prior_replacement_at_create_boundary_keeps_fourth_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = _publish_three(tmp_path)
    replacement = tmp_path / "create-boundary-provider.json"
    replacement.write_bytes(b"changed at create\n")
    replacement.chmod(0o600)
    original_open = os.open
    changed = False

    def replace_before_fourth_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal changed
        if path == _FOURTH and flags & os.O_CREAT and not changed:
            changed = True
            os.replace(replacement, setup.root / _SECOND)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(io_module.os, "open", replace_before_fourth_open)

    _assert_fixed_failure(lambda: _publish_four(setup))

    assert changed
    assert (setup.root / _SECOND).read_bytes() == b"changed at create\n"
    assert (setup.root / _FOURTH).read_bytes() == _FOURTH_PAYLOAD


def test_root_path_replacement_before_rewalk_keeps_held_root_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = _publish_three(tmp_path)
    parked = tmp_path / "parked-campaign"
    original_validate = io_module._validate_fourth_control_publication

    def replace_root_then_validate(*args: Any, **kwargs: Any) -> None:
        setup.root.rename(parked)
        setup.root.mkdir(mode=0o700)
        original_validate(*args, **kwargs)

    monkeypatch.setattr(
        io_module,
        "_validate_fourth_control_publication",
        replace_root_then_validate,
    )

    _assert_fixed_failure(lambda: _publish_four(setup))

    assert {path.name for path in parked.iterdir()} == {
        _FIRST,
        _SECOND,
        _THIRD,
        _FOURTH,
    }
    assert (parked / _FOURTH).read_bytes() == _FOURTH_PAYLOAD
    assert list(setup.root.iterdir()) == []


@pytest.mark.parametrize("close_target", ["attached", "root"])
def test_postcommit_close_errors_do_not_revoke_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    close_target: str,
) -> None:
    setup = _publish_three(tmp_path)
    original_close = os.close
    attached_closed = False
    failures: list[str] = []

    def close_with_postcommit_error(fd: int) -> None:
        nonlocal attached_closed
        try:
            target = os.readlink(f"/proc/self/fd/{fd}")
            access_mode = fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE
        except OSError:
            target = ""
            access_mode = -1
        original_close(fd)
        if (
            not failures
            and target.endswith(f"/{_FOURTH}")
            and access_mode == os.O_WRONLY
        ):
            attached_closed = True
            if close_target == "attached":
                failures.append(close_target)
                raise OSError("private attached close detail")
        elif (
            close_target == "root"
            and attached_closed
            and not failures
            and target.endswith("/campaign")
        ):
            failures.append(close_target)
            raise OSError("private root close detail")

    monkeypatch.setattr(io_module.os, "close", close_with_postcommit_error)

    fingerprint = _publish_four(setup)

    assert failures == [close_target]
    assert _leaf_fingerprint((setup.root / _FOURTH).stat()) == fingerprint
    assert (setup.root / _FOURTH).read_bytes() == _FOURTH_PAYLOAD


def test_fresh_rewalk_close_errors_do_not_revoke_publish_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = _publish_three(tmp_path)
    original_close = os.close
    fresh_close_failures = 0
    attached_closed = False

    def close_with_fresh_error(fd: int) -> None:
        nonlocal attached_closed, fresh_close_failures
        try:
            target = os.readlink(f"/proc/self/fd/{fd}")
            access_mode = fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE
        except OSError:
            target = ""
            access_mode = -1
        original_close(fd)
        if target.endswith(f"/{_FOURTH}") and access_mode == os.O_WRONLY:
            attached_closed = True
        elif (
            not attached_closed
            and target.endswith("/campaign")
            and access_mode == os.O_RDONLY
        ):
            fresh_close_failures += 1
            raise OSError("private fresh close detail")

    monkeypatch.setattr(io_module.os, "close", close_with_fresh_error)

    fingerprint = _publish_four(setup)

    assert fresh_close_failures == 2
    assert _leaf_fingerprint((setup.root / _FOURTH).stat()) == fingerprint


def test_cleanup_close_error_does_not_replace_fixed_precommit_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = _publish_three(tmp_path)
    original_close = os.close

    def fail_validation(*_args: Any, **_kwargs: Any) -> None:
        raise _InjectedFailure("private validation detail")

    def close_with_cleanup_error(fd: int) -> None:
        access_mode = fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE
        original_close(fd)
        if access_mode == os.O_WRONLY:
            raise OSError("private cleanup close detail")

    monkeypatch.setattr(io_module, "_verify_all_four", fail_validation)
    monkeypatch.setattr(io_module.os, "close", close_with_cleanup_error)

    _assert_fixed_failure(lambda: _publish_four(setup))

    _assert_fourth_reserved(setup, _FOURTH_PAYLOAD)


def test_fresh_validator_rejects_changed_fourth_leaf(tmp_path: Path) -> None:
    setup = _publish_three(tmp_path)
    fingerprint = _publish_four(setup)
    (setup.root / _FOURTH).write_bytes(b"changed\n")

    with pytest.raises(ValueError):
        _validate_four(setup, fingerprint, require_exact_names=False)


def test_root_identity_cannot_alias_any_leaf_identity_before_create(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = _publish_three(tmp_path)
    monkeypatch.setattr(
        io_module,
        "_fingerprint",
        lambda _root_stat: setup.publication.leaf_fingerprint[:2],
    )

    _assert_fixed_failure(lambda: _publish_four(setup))

    _assert_prior_three_exact(setup)
