"""Strict, acquisition-free systemd 255 execution facts.

This module deliberately contains no systemd client.  Its inputs are copied
property/environment receipts acquired by a higher layer; it only decodes and
validates those receipts against the execution contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Iterable, Mapping, Optional, Tuple, Union


class Systemd255ContractError(ValueError):
    """A copied systemd fact does not satisfy the systemd-255 contract."""


class UnitRole(str, Enum):
    """The two unit roles participating in the run-to-close handoff."""

    RUN = "RUN"
    CLOSER = "CLOSER"


PropertyPairs = Union[Mapping[str, str], Iterable[Tuple[str, str]]]

_INVOCATION_ID_RE = re.compile(r"[0-9a-f]{32}\Z")
_BOOT_ID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z"
)
_UNIT_RE = re.compile(r"[A-Za-z0-9:_.@-]+\.service\Z")
_DEPENDENCY_UNIT_RE = re.compile(r"[A-Za-z0-9:_.@-]+\.[A-Za-z0-9_-]+\Z")
_TOKEN_RE = re.compile(r"[A-Za-z0-9_.+@:-]+\Z")
_JOB_CGROUP_RE = re.compile(r"job-(0|[1-9][0-9]{0,19})-[0-9a-f]{16}\Z")


def _raise(message: str) -> None:
    raise Systemd255ContractError(message)


def _pairs(
    source: PropertyPairs,
    *,
    expected: frozenset[str],
    receipt: str,
) -> dict[str, str]:
    if isinstance(source, Mapping):
        items = source.items()
    else:
        if isinstance(source, (str, bytes, bytearray)):
            _raise(f"{receipt} must be a mapping or iterable of key/value pairs")
        items = source

    decoded: dict[str, str] = {}
    try:
        for item in items:
            if not isinstance(item, tuple) or len(item) != 2:
                _raise(f"{receipt} contains a non-pair entry")
            key, value = item
            if type(key) is not str or type(value) is not str:
                _raise(f"{receipt} keys and values must be exact strings")
            _canonical_text(key, field=f"{receipt} key", allow_empty=False)
            _canonical_text(value, field=f"{receipt}.{key}", allow_empty=True)
            if key in decoded:
                _raise(f"{receipt} contains duplicate key {key!r}")
            decoded[key] = value
    except Systemd255ContractError:
        raise
    except (TypeError, ValueError) as exc:
        raise Systemd255ContractError(f"{receipt} is not a property receipt") from exc

    actual = frozenset(decoded)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing or unknown:
        _raise(f"{receipt} schema mismatch: missing={missing!r}, unknown={unknown!r}")
    return decoded


def _canonical_text(value: str, *, field: str, allow_empty: bool) -> str:
    if type(value) is not str:
        _raise(f"{field} must be an exact string")
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise Systemd255ContractError(f"{field} is not valid UTF-8 text") from exc
    if not allow_empty and not encoded:
        _raise(f"{field} must be nonempty")
    if any(byte < 0x20 or byte == 0x7F for byte in encoded):
        _raise(f"{field} contains a forbidden control character")
    return value


def _ascii(value: str, *, field: str, allow_empty: bool = False) -> str:
    _canonical_text(value, field=field, allow_empty=allow_empty)
    try:
        value.encode("ascii", "strict")
    except UnicodeError as exc:
        raise Systemd255ContractError(f"{field} must be canonical ASCII") from exc
    return value


def _unit(value: str, *, field: str) -> str:
    _ascii(value, field=field)
    if _UNIT_RE.fullmatch(value) is None:
        _raise(f"{field} must be a canonical .service unit name")
    return value


def _invocation_id(value: str, *, field: str) -> str:
    _ascii(value, field=field)
    if _INVOCATION_ID_RE.fullmatch(value) is None:
        _raise(f"{field} must be 32 lowercase hexadecimal characters")
    return value


def _boot_id(value: str, *, field: str) -> str:
    _ascii(value, field=field)
    if _BOOT_ID_RE.fullmatch(value) is None:
        _raise(f"{field} must be a canonical lowercase boot UUID")
    return value


def _token(value: str, *, field: str) -> str:
    _ascii(value, field=field)
    if _TOKEN_RE.fullmatch(value) is None:
        _raise(f"{field} must be one canonical systemd token")
    return value


def _uint(value: str, *, field: str, positive: bool = False) -> int:
    _ascii(value, field=field)
    if value == "0":
        number = 0
    elif value and value[0] in "123456789" and value.isascii() and value.isdecimal():
        number = int(value, 10)
    else:
        _raise(f"{field} must be canonical unsigned decimal")
    if number > (1 << 64) - 1:
        _raise(f"{field} exceeds uint64")
    if positive and number == 0:
        _raise(f"{field} must be positive")
    return number


def _absolute_cgroup(value: str, *, field: str) -> str:
    _ascii(value, field=field)
    if not value.startswith("/") or value == "/" or value.endswith("/"):
        _raise(f"{field} must be a non-root absolute cgroup lineage")
    components = value.split("/")[1:]
    if any(not component or component in {".", ".."} for component in components):
        _raise(f"{field} is not a canonical cgroup lineage")
    return value


def _unit_list(value: str, *, field: str, allow_empty: bool) -> tuple[str, ...]:
    _ascii(value, field=field, allow_empty=allow_empty)
    if value == "":
        return ()
    if value != value.strip() or "  " in value or "\t" in value:
        _raise(f"{field} is not a canonical space-separated unit list")
    units = tuple(value.split(" "))
    for unit in units:
        _ascii(unit, field=field)
        if _DEPENDENCY_UNIT_RE.fullmatch(unit) is None:
            _raise(f"{field} contains a noncanonical systemd unit name")
    if len(set(units)) != len(units):
        _raise(f"{field} contains a duplicate unit")
    return units


def _controller_list(value: str, *, field: str) -> tuple[str, ...]:
    _ascii(value, field=field)
    if value != value.strip() or "  " in value or "\t" in value:
        _raise(f"{field} is not a canonical space-separated controller list")
    controllers = tuple(value.split(" "))
    for controller in controllers:
        _token(controller, field=field)
    if len(set(controllers)) != len(controllers):
        _raise(f"{field} contains a duplicate controller")
    return controllers


def _pid_list(value: str, *, field: str) -> tuple[int, ...]:
    _ascii(value, field=field, allow_empty=True)
    if value == "":
        return ()
    if value != value.strip() or "  " in value or "\t" in value:
        _raise(f"{field} is not a canonical space-separated PID list")
    pids = tuple(_uint(part, field=field, positive=True) for part in value.split(" "))
    if tuple(sorted(pids)) != pids or len(set(pids)) != len(pids):
        _raise(f"{field} must be strictly increasing")
    return pids


def _job_list(value: str, *, field: str) -> tuple[str, ...]:
    _ascii(value, field=field, allow_empty=True)
    if value == "":
        return ()
    if value != value.strip() or "  " in value or "\t" in value:
        _raise(f"{field} is not a canonical space-separated job-cgroup list")
    jobs = tuple(value.split(" "))
    for job in jobs:
        _job_cgroup_name(job, field=field)
    if tuple(sorted(jobs)) != jobs or len(set(jobs)) != len(jobs):
        _raise(f"{field} must be unique and sorted")
    return jobs


def _job_cgroup_name(value: str, *, field: str) -> str:
    _ascii(value, field=field)
    match = _JOB_CGROUP_RE.fullmatch(value)
    if match is None or int(match.group(1), 10) > (1 << 64) - 1:
        _raise(f"{field} contains a noncanonical job cgroup")
    return value


@dataclass(frozen=True, slots=True)
class ConfiguredUnitProperties:
    """One raw configured-directive receipt bound to its expanded properties.

    ``delegate`` and ``timeout_*_sec`` are literal unit directives.  The
    ``*_effective``/``*_usec`` fields are the corresponding systemd-255
    expanded values, so the type never conflates manager properties with the
    raw directive spelling.
    """

    role: UnitRole
    unit: str
    peer_unit: str
    configured_directives: tuple[tuple[str, str], ...]
    collect_mode: str
    restart: str
    timeout_start_sec: Optional[str]
    timeout_stop_sec: Optional[str]
    timeout_start_usec: Optional[str]
    timeout_stop_usec: Optional[str]
    delegate: Optional[str]
    delegate_effective: Optional[str]
    delegate_controllers: tuple[str, ...]
    delegate_subgroup: Optional[str]
    kill_mode: Optional[str]
    on_success: tuple[str, ...]
    on_failure: tuple[str, ...]
    after: tuple[str, ...]

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("ConfiguredUnitProperties is final")

    def __post_init__(self) -> None:
        if type(self.role) is not UnitRole:
            _raise("role must be an exact UnitRole")
        _unit(self.unit, field="unit")
        _unit(self.peer_unit, field="peer_unit")
        if self.unit == self.peer_unit:
            _raise("unit and peer_unit must differ")
        if type(self.configured_directives) is not tuple or any(
            type(item) is not tuple
            or len(item) != 2
            or type(item[0]) is not str
            or type(item[1]) is not str
            for item in self.configured_directives
        ):
            _raise("configured_directives must be an exact tuple of string pairs")
        if tuple(sorted(self.configured_directives)) != self.configured_directives:
            _raise("configured_directives must be unique and sorted")
        configured_keys = tuple(key for key, _ in self.configured_directives)
        if len(set(configured_keys)) != len(configured_keys):
            _raise("configured_directives contains a duplicate directive")
        for field_name in (
            "collect_mode",
            "restart",
            "timeout_start_sec",
            "timeout_stop_sec",
            "timeout_start_usec",
            "timeout_stop_usec",
            "delegate",
            "delegate_effective",
            "delegate_subgroup",
            "kill_mode",
        ):
            value = getattr(self, field_name)
            if value is not None:
                _ascii(value, field=field_name)
        if type(self.delegate_controllers) is not tuple:
            _raise("delegate_controllers must be an exact tuple")
        for controller in self.delegate_controllers:
            _token(controller, field="delegate_controllers")
        if len(set(self.delegate_controllers)) != len(self.delegate_controllers):
            _raise("delegate_controllers contains a duplicate")
        for field_name in ("on_success", "on_failure", "after"):
            value = getattr(self, field_name)
            if type(value) is not tuple:
                _raise(f"{field_name} must be an exact tuple")
            for unit in value:
                if field_name == "after":
                    _ascii(unit, field=field_name)
                    if _DEPENDENCY_UNIT_RE.fullmatch(unit) is None:
                        _raise("after contains a noncanonical systemd unit name")
                else:
                    _unit(unit, field=field_name)
            if len(set(value)) != len(value):
                _raise(f"{field_name} contains a duplicate unit")

        if self.collect_mode != "inactive" or self.restart != "no":
            _raise("CollectMode=inactive and Restart=no are mandatory")
        if self.role is UnitRole.RUN:
            expected_configured = tuple(
                sorted(
                    {
                        "CollectMode": "inactive",
                        "Delegate": "pids",
                        "DelegateSubgroup": "supervisor",
                        "KillMode": "control-group",
                        "OnFailure": self.peer_unit,
                        "OnSuccess": self.peer_unit,
                        "Restart": "no",
                        "TimeoutStopSec": "infinity",
                    }.items()
                )
            )
            if (
                self.configured_directives != expected_configured
                or self.timeout_start_sec is not None
                or self.timeout_stop_sec != "infinity"
                or self.timeout_start_usec is not None
                or self.timeout_stop_usec != "infinity"
                or self.delegate != "pids"
                or self.delegate_effective != "yes"
                or self.delegate_controllers != ("pids",)
                or self.delegate_subgroup != "supervisor"
                or self.kill_mode != "control-group"
                or self.on_success != (self.peer_unit,)
                or self.on_failure != (self.peer_unit,)
                or self.after
            ):
                _raise("run-unit properties do not match the exact systemd-255 contract")
        else:
            expected_configured = tuple(
                sorted(
                    {
                        "After": self.peer_unit,
                        "CollectMode": "inactive",
                        "Restart": "no",
                        "TimeoutStartSec": "infinity",
                    }.items()
                )
            )
            if (
                self.configured_directives != expected_configured
                or self.timeout_start_usec != "infinity"
                or self.timeout_start_sec != "infinity"
                or self.timeout_stop_sec is not None
                or self.timeout_stop_usec is not None
                or self.delegate is not None
                or self.delegate_effective is not None
                or self.delegate_controllers
                or self.delegate_subgroup is not None
                or self.kill_mode is not None
                or self.on_success
                or self.on_failure
                or self.peer_unit not in self.after
            ):
                _raise("closer-unit properties do not match the exact systemd-255 contract")

    @classmethod
    def from_receipts(
        cls,
        role: UnitRole,
        configured_directives: PropertyPairs,
        expanded_properties: PropertyPairs,
        *,
        expected_unit: str,
        expected_peer: str,
    ) -> "ConfiguredUnitProperties":
        if type(role) is not UnitRole:
            _raise("role must be an exact UnitRole")
        _unit(expected_unit, field="expected_unit")
        _unit(expected_peer, field="expected_peer")

        if role is UnitRole.RUN:
            configured = _pairs(
                configured_directives,
                expected=frozenset(
                    {
                        "Delegate",
                        "DelegateSubgroup",
                        "CollectMode",
                        "Restart",
                        "KillMode",
                        "TimeoutStopSec",
                        "OnSuccess",
                        "OnFailure",
                    }
                ),
                receipt="run configured directives",
            )
            expanded = _pairs(
                expanded_properties,
                expected=frozenset(
                    {
                        "Id",
                        "Delegate",
                        "DelegateControllers",
                        "DelegateSubgroup",
                        "CollectMode",
                        "Restart",
                        "KillMode",
                        "TimeoutStopUSec",
                        "OnSuccess",
                        "OnFailure",
                    }
                ),
                receipt="run expanded properties",
            )
            if expanded["Id"] != expected_unit:
                _raise("run Id does not match expected_unit")
            return cls(
                role=role,
                unit=expanded["Id"],
                peer_unit=expected_peer,
                configured_directives=tuple(sorted(configured.items())),
                collect_mode=expanded["CollectMode"],
                restart=expanded["Restart"],
                timeout_start_sec=None,
                timeout_stop_sec=configured["TimeoutStopSec"],
                timeout_start_usec=None,
                timeout_stop_usec=expanded["TimeoutStopUSec"],
                delegate=configured["Delegate"],
                delegate_effective=expanded["Delegate"],
                delegate_controllers=_controller_list(
                    expanded["DelegateControllers"], field="DelegateControllers"
                ),
                delegate_subgroup=expanded["DelegateSubgroup"],
                kill_mode=expanded["KillMode"],
                on_success=_unit_list(
                    expanded["OnSuccess"], field="OnSuccess", allow_empty=False
                ),
                on_failure=_unit_list(
                    expanded["OnFailure"], field="OnFailure", allow_empty=False
                ),
                after=(),
            )

        configured = _pairs(
            configured_directives,
            expected=frozenset(
                {"CollectMode", "Restart", "TimeoutStartSec", "After"}
            ),
            receipt="closer configured directives",
        )
        expanded = _pairs(
            expanded_properties,
            expected=frozenset(
                {"Id", "CollectMode", "Restart", "TimeoutStartUSec", "After"}
            ),
            receipt="closer expanded properties",
        )
        if expanded["Id"] != expected_unit:
            _raise("closer Id does not match expected_unit")
        return cls(
            role=role,
            unit=expanded["Id"],
            peer_unit=expected_peer,
            configured_directives=tuple(sorted(configured.items())),
            collect_mode=expanded["CollectMode"],
            restart=expanded["Restart"],
            timeout_start_sec=configured["TimeoutStartSec"],
            timeout_stop_sec=None,
            timeout_start_usec=expanded["TimeoutStartUSec"],
            timeout_stop_usec=None,
            delegate=None,
            delegate_effective=None,
            delegate_controllers=(),
            delegate_subgroup=None,
            kill_mode=None,
            on_success=(),
            on_failure=(),
            after=_unit_list(expanded["After"], field="After", allow_empty=False),
        )


def validate_run_close_pair(
    run: ConfiguredUnitProperties,
    closer: ConfiguredUnitProperties,
) -> None:
    """Require an exact reciprocal run/closer configuration."""

    if (
        type(run) is not ConfiguredUnitProperties
        or type(closer) is not ConfiguredUnitProperties
    ):
        _raise("run and closer must be exact ConfiguredUnitProperties")
    if run.role is not UnitRole.RUN or closer.role is not UnitRole.CLOSER:
        _raise("configured pair must be ordered RUN, CLOSER")
    if run.peer_unit != closer.unit or closer.peer_unit != run.unit:
        _raise("configured run/closer peers do not match")
    if run.on_success != (closer.unit,) or run.on_failure != (closer.unit,):
        _raise("run handoff targets do not name the exact closer")
    if run.unit not in closer.after:
        _raise("closer After does not contain the exact run unit")


@dataclass(frozen=True, slots=True)
class InvocationLineage:
    """Copied identity tying a process and two cgroups to one invocation."""

    boot_id: str
    unit: str
    invocation_id: str
    control_group: str
    service_device: int
    service_inode: int
    supervisor_device: int
    supervisor_inode: int
    main_pid: int
    main_starttime: int

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("InvocationLineage is final")

    def __post_init__(self) -> None:
        _boot_id(self.boot_id, field="boot_id")
        _unit(self.unit, field="unit")
        _invocation_id(self.invocation_id, field="invocation_id")
        _absolute_cgroup(self.control_group, field="control_group")
        if self.control_group.endswith("/supervisor"):
            _raise("control_group must identify the service root, not supervisor")
        for field_name in (
            "service_device",
            "service_inode",
            "supervisor_device",
            "supervisor_inode",
            "main_pid",
            "main_starttime",
        ):
            value = getattr(self, field_name)
            if type(value) is not int or value <= 0 or value > (1 << 64) - 1:
                _raise(f"{field_name} must be a positive uint64")
        if (
            self.service_device == self.supervisor_device
            and self.service_inode == self.supervisor_inode
        ):
            _raise("service and supervisor identities must differ")

    @classmethod
    def from_properties(cls, properties: PropertyPairs) -> "InvocationLineage":
        values = _pairs(
            properties,
            expected=frozenset(
                {
                    "BootID",
                    "Id",
                    "InvocationID",
                    "ControlGroup",
                    "ServiceDevice",
                    "ServiceInode",
                    "SupervisorDevice",
                    "SupervisorInode",
                    "MainPID",
                    "MainStartTime",
                }
            ),
            receipt="invocation lineage",
        )
        return cls(
            boot_id=values["BootID"],
            unit=values["Id"],
            invocation_id=values["InvocationID"],
            control_group=values["ControlGroup"],
            service_device=_uint(
                values["ServiceDevice"], field="ServiceDevice", positive=True
            ),
            service_inode=_uint(
                values["ServiceInode"], field="ServiceInode", positive=True
            ),
            supervisor_device=_uint(
                values["SupervisorDevice"], field="SupervisorDevice", positive=True
            ),
            supervisor_inode=_uint(
                values["SupervisorInode"], field="SupervisorInode", positive=True
            ),
            main_pid=_uint(values["MainPID"], field="MainPID", positive=True),
            main_starttime=_uint(
                values["MainStartTime"], field="MainStartTime", positive=True
            ),
        )


@dataclass(frozen=True, slots=True)
class StopPostEnvironment:
    """Literal selector environment copied inside ExecStopPost."""

    invocation_id: str
    service_result: str
    exit_code: str
    exit_status: str

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("StopPostEnvironment is final")

    def __post_init__(self) -> None:
        _invocation_id(self.invocation_id, field="invocation_id")
        _token(self.service_result, field="service_result")
        _token(self.exit_code, field="exit_code")
        _token(self.exit_status, field="exit_status")

    @classmethod
    def from_environment(cls, environment: PropertyPairs) -> "StopPostEnvironment":
        values = _pairs(
            environment,
            expected=frozenset(
                {"INVOCATION_ID", "SERVICE_RESULT", "EXIT_CODE", "EXIT_STATUS"}
            ),
            receipt="stop-post environment",
        )
        return cls(
            invocation_id=values["INVOCATION_ID"],
            service_result=values["SERVICE_RESULT"],
            exit_code=values["EXIT_CODE"],
            exit_status=values["EXIT_STATUS"],
        )


@dataclass(frozen=True, slots=True)
class StopPostTopology:
    """Copied topology while the sole ExecStopPost sealer is running."""

    service_control_group: str
    control_group: str
    sealer_pid: int
    sealer_starttime: int
    control_pids: tuple[int, ...]
    supervisor_pids: tuple[int, ...]
    job_cgroups: tuple[str, ...]
    job_pids: tuple[int, ...]

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("StopPostTopology is final")

    def __post_init__(self) -> None:
        _absolute_cgroup(self.service_control_group, field="service_control_group")
        _absolute_cgroup(self.control_group, field="control_group")
        if self.control_group != f"{self.service_control_group}/.control":
            _raise("control_group must be the service .control cgroup")
        for field_name in ("sealer_pid", "sealer_starttime"):
            value = getattr(self, field_name)
            if type(value) is not int or value <= 0 or value > (1 << 64) - 1:
                _raise(f"{field_name} must be a positive uint64")
        for field_name in ("control_pids", "supervisor_pids", "job_pids"):
            value = getattr(self, field_name)
            if type(value) is not tuple or any(
                type(pid) is not int or pid <= 0 or pid > (1 << 64) - 1
                for pid in value
            ):
                _raise(f"{field_name} must be an exact tuple of positive PIDs")
            if tuple(sorted(value)) != value or len(set(value)) != len(value):
                _raise(f"{field_name} must be strictly increasing")
        if self.control_pids != (self.sealer_pid,):
            _raise(".control must contain only the exact sealer PID")
        if self.supervisor_pids or self.job_pids:
            _raise("supervisor and job cgroups must contain no processes")
        if type(self.job_cgroups) is not tuple:
            _raise("job_cgroups must be an exact tuple")
        if (
            tuple(sorted(self.job_cgroups)) != self.job_cgroups
            or len(set(self.job_cgroups)) != len(self.job_cgroups)
        ):
            _raise("job_cgroups must be unique and sorted")
        for job in self.job_cgroups:
            _job_cgroup_name(job, field="job_cgroups")

    @classmethod
    def from_mapping(cls, topology: PropertyPairs) -> "StopPostTopology":
        values = _pairs(
            topology,
            expected=frozenset(
                {
                    "ServiceControlGroup",
                    "ControlGroup",
                    "SealerPID",
                    "SealerStartTime",
                    "ControlPIDs",
                    "SupervisorPIDs",
                    "JobCgroups",
                    "JobPIDs",
                }
            ),
            receipt="stop-post topology",
        )
        return cls(
            service_control_group=values["ServiceControlGroup"],
            control_group=values["ControlGroup"],
            sealer_pid=_uint(values["SealerPID"], field="SealerPID", positive=True),
            sealer_starttime=_uint(
                values["SealerStartTime"], field="SealerStartTime", positive=True
            ),
            control_pids=_pid_list(values["ControlPIDs"], field="ControlPIDs"),
            supervisor_pids=_pid_list(values["SupervisorPIDs"], field="SupervisorPIDs"),
            job_cgroups=_job_list(values["JobCgroups"], field="JobCgroups"),
            job_pids=_pid_list(values["JobPIDs"], field="JobPIDs"),
        )


@dataclass(frozen=True, slots=True)
class UnitHandoffProperties:
    """Final source-unit facts copied by the already-queued closer.

    The ``ExecStopPostCode`` and ``ExecStopPostStatus`` input fields are the
    acquisition layer's normalized extraction of the manager's structured
    ExecStopPost property.  They are not claimed to be standalone raw manager
    property names.
    """

    unit: str
    invocation_id: str
    load_state: str
    active_state: str
    sub_state: str
    result: str
    exec_main_code: int
    exec_main_status: int
    exec_stop_post_code: int
    exec_stop_post_status: int

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("UnitHandoffProperties is final")

    def __post_init__(self) -> None:
        _unit(self.unit, field="unit")
        _invocation_id(self.invocation_id, field="invocation_id")
        for field_name in ("load_state", "active_state", "sub_state", "result"):
            _token(getattr(self, field_name), field=field_name)
        if self.load_state != "loaded":
            _raise("handoff source must remain loaded while its closer reads it")
        if self.active_state not in {"inactive", "failed"}:
            _raise("handoff source is not in a final active state")
        if self.sub_state not in {"dead", "failed"}:
            _raise("handoff source is not in a final substate")
        for field_name in (
            "exec_main_code",
            "exec_main_status",
            "exec_stop_post_code",
            "exec_stop_post_status",
        ):
            value = getattr(self, field_name)
            if type(value) is not int or value < 0 or value > 255:
                _raise(f"{field_name} must be an unsigned status byte")
        if self.exec_main_code not in {1, 2, 3}:
            _raise("ExecMainCode is not a terminal exited/killed/dumped wait code")
        if self.exec_stop_post_code not in {1, 2, 3}:
            _raise("ExecStopPostCode is not a terminal exited/killed/dumped wait code")
        if self.exec_main_code in {2, 3} and not 1 <= self.exec_main_status <= 64:
            _raise("killed/dumped ExecMainCode requires a valid signal status")
        if self.exec_stop_post_code in {2, 3} and not 1 <= self.exec_stop_post_status <= 64:
            _raise("killed/dumped ExecStopPostCode requires a valid signal status")

        main_succeeded = self.exec_main_code == 1 and self.exec_main_status == 0
        stop_post_succeeded = (
            self.exec_stop_post_code == 1 and self.exec_stop_post_status == 0
        )
        if self.result == "success":
            if (
                self.active_state != "inactive"
                or self.sub_state != "dead"
                or not main_succeeded
                or not stop_post_succeeded
            ):
                _raise("successful unit handoff has incoherent final facts")
        elif (
            self.active_state != "failed"
            or self.sub_state != "failed"
            or (main_succeeded and stop_post_succeeded)
        ):
            _raise("failed unit handoff lacks coherent non-success facts")

    @classmethod
    def from_properties(
        cls,
        properties: PropertyPairs,
        *,
        expected_unit: str,
    ) -> "UnitHandoffProperties":
        _unit(expected_unit, field="expected_unit")
        values = _pairs(
            properties,
            expected=frozenset(
                {
                    "Id",
                    "InvocationID",
                    "LoadState",
                    "ActiveState",
                    "SubState",
                    "Result",
                    "ExecMainCode",
                    "ExecMainStatus",
                    "ExecStopPostCode",
                    "ExecStopPostStatus",
                }
            ),
            receipt="unit handoff properties",
        )
        if values["Id"] != expected_unit:
            _raise("handoff Id does not match expected_unit")
        return cls(
            unit=values["Id"],
            invocation_id=values["InvocationID"],
            load_state=values["LoadState"],
            active_state=values["ActiveState"],
            sub_state=values["SubState"],
            result=values["Result"],
            exec_main_code=_uint(values["ExecMainCode"], field="ExecMainCode"),
            exec_main_status=_uint(values["ExecMainStatus"], field="ExecMainStatus"),
            exec_stop_post_code=_uint(
                values["ExecStopPostCode"], field="ExecStopPostCode"
            ),
            exec_stop_post_status=_uint(
                values["ExecStopPostStatus"], field="ExecStopPostStatus"
            ),
        )


def validate_same_invocation(
    lineage: InvocationLineage,
    stop_post: StopPostEnvironment,
    handoff: UnitHandoffProperties,
) -> None:
    """Reject empty, mismatched or cross-unit run-to-close facts."""

    if type(lineage) is not InvocationLineage:
        _raise("lineage must be an exact InvocationLineage")
    if type(stop_post) is not StopPostEnvironment:
        _raise("stop_post must be an exact StopPostEnvironment")
    if type(handoff) is not UnitHandoffProperties:
        _raise("handoff must be an exact UnitHandoffProperties")
    if lineage.unit != handoff.unit:
        _raise("lineage and handoff source units differ")
    invocation_ids = {
        lineage.invocation_id,
        stop_post.invocation_id,
        handoff.invocation_id,
    }
    if len(invocation_ids) != 1:
        _raise("run-to-close facts do not belong to the same invocation")


__all__ = [
    "ConfiguredUnitProperties",
    "InvocationLineage",
    "StopPostEnvironment",
    "StopPostTopology",
    "Systemd255ContractError",
    "UnitHandoffProperties",
    "UnitRole",
    "validate_run_close_pair",
    "validate_same_invocation",
]
