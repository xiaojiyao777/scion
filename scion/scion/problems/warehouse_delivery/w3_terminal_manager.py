"""Problem-owned manager pinning for read-only W3 terminal acquisition."""

from __future__ import annotations

import importlib
import re
from typing import Mapping

from scion.runtime.execution.systemd_acquisition import (
    SystemdAcquisitionError,
    SystemdDbusPropertyReader,
)

_UNIT_RE = re.compile(r"[A-Za-z0-9:_.@-]+\.service\Z")
_SYSTEMD_DESTINATION = "org.freedesktop.systemd1"
_MANAGER_PATH = "/org/freedesktop/systemd1"
_MANAGER_INTERFACE = "org.freedesktop.systemd1.Manager"


class WarehouseW3TerminalManagerError(RuntimeError):
    """The exact manager reference or read-only property surface differs."""


class WarehouseW3TerminalManager:
    """Final RefUnit/UnrefUnit plus read-only acquisition adapter.

    The manager object is private and this class deliberately exposes no load,
    start, stop, restart, reset, reload, enable, or generic method passthrough.
    """

    __slots__ = ("_manager", "_owner", "_reader")

    def __init__(self) -> None:
        try:
            reader = SystemdDbusPropertyReader()
            owner = reader.get_unique_owner()
            dbus = importlib.import_module("dbus")
            bus = dbus.SystemBus()
            manager_object = bus.get_object(owner, _MANAGER_PATH)
            manager = dbus.Interface(
                manager_object,
                dbus_interface=_MANAGER_INTERFACE,
            )
            if reader.get_unique_owner() != owner:
                raise WarehouseW3TerminalManagerError(
                    "systemd manager changed during terminal adapter acquisition"
                )
        except WarehouseW3TerminalManagerError:
            raise
        except Exception as exc:
            raise WarehouseW3TerminalManagerError(
                "cannot acquire W3 terminal manager adapter"
            ) from exc
        self._reader = reader
        self._owner = owner
        self._manager = manager

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("WarehouseW3TerminalManager is final")

    @staticmethod
    def _unit(unit: str) -> str:
        if type(unit) is not str or _UNIT_RE.fullmatch(unit) is None:
            raise WarehouseW3TerminalManagerError(
                "terminal manager unit is not canonical"
            )
        return unit

    def _require_owner(self) -> None:
        try:
            current = self._reader.get_unique_owner()
        except Exception as exc:
            raise WarehouseW3TerminalManagerError(
                "cannot reacquire terminal manager owner"
            ) from exc
        if current != self._owner:
            raise WarehouseW3TerminalManagerError(
                "systemd manager changed during terminal acquisition"
            )

    def get_unique_owner(self) -> str:
        self._require_owner()
        return self._owner

    def get_manager_version(self, expected_owner: str) -> str:
        if expected_owner != self._owner:
            raise WarehouseW3TerminalManagerError(
                "terminal manager expected owner differs"
            )
        self._require_owner()
        try:
            version = self._reader.get_manager_version(expected_owner)
        except SystemdAcquisitionError as exc:
            raise WarehouseW3TerminalManagerError(
                "cannot acquire terminal manager version"
            ) from exc
        self._require_owner()
        return version

    def read_properties(
        self,
        unit: str,
        names: tuple[str, ...],
    ) -> Mapping[str, object]:
        unit_name = self._unit(unit)
        self._require_owner()
        try:
            copied = self._reader.read_properties(unit_name, names)
        except SystemdAcquisitionError as exc:
            raise WarehouseW3TerminalManagerError(
                f"cannot acquire terminal properties for {unit_name}"
            ) from exc
        self._require_owner()
        return copied

    def ref_unit(self, unit: str) -> None:
        unit_name = self._unit(unit)
        self._require_owner()
        try:
            self._manager.RefUnit(unit_name)
        except Exception as exc:
            raise WarehouseW3TerminalManagerError(
                f"cannot reference terminal unit {unit_name}"
            ) from exc
        self._require_owner()

    def unref_unit(self, unit: str) -> None:
        unit_name = self._unit(unit)
        self._require_owner()
        try:
            self._manager.UnrefUnit(unit_name)
        except Exception as exc:
            raise WarehouseW3TerminalManagerError(
                f"cannot release terminal unit {unit_name}"
            ) from exc
        self._require_owner()


__all__ = [
    "WarehouseW3TerminalManager",
    "WarehouseW3TerminalManagerError",
]
