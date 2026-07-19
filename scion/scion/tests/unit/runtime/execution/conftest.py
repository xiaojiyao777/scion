"""Install an inert native ABI while collecting source-only execution tests."""

from __future__ import annotations

import sys
import types


class _NativeBlockedChild:
    pass


def _native_not_configured(*_args: object, **_kwargs: object) -> object:
    raise AssertionError("native spawn was not configured by the test")


_extension = types.ModuleType("scion.runtime.native._spawn_into_cgroup")
_constants: dict[str, object] = {
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
    "BlockedChild": _NativeBlockedChild,
    "spawn_blocked": _native_not_configured,
}
for _name, _value in _constants.items():
    setattr(_extension, _name, _value)
sys.modules.setdefault("scion.runtime.native._spawn_into_cgroup", _extension)
