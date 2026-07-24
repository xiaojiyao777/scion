from __future__ import annotations

from pathlib import Path

import pytest

import scion.problems.warehouse_delivery.w3_terminal_manager as terminal_manager
from scion.problems.warehouse_delivery.w3_terminal_manager import (
    WarehouseW3TerminalManager,
    WarehouseW3TerminalManagerError,
)

RUN = "scion-w3@" + "1" * 64 + ".service"
CLOSE = "scion-w3-close@" + "1" * 64 + ".service"


def test_terminal_manager_exposes_only_reference_and_read_acquisition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[object, ...]] = []

    class Reader:
        owner = ":1.42"

        def get_unique_owner(self):
            events.append(("owner", self.owner))
            return self.owner

        def get_manager_version(self, owner):
            events.append(("version", owner))
            return "255.4"

        def read_properties(self, unit, names):
            events.append(("properties", unit, names))
            return {"Id": unit}

    reader = Reader()

    class Manager:
        def RefUnit(self, unit):
            events.append(("ref", unit))

        def UnrefUnit(self, unit):
            events.append(("unref", unit))

    manager = Manager()

    class Bus:
        def get_object(self, owner, path):
            events.append(("manager-object", owner, path))
            return manager

    class Dbus:
        @staticmethod
        def SystemBus():
            return Bus()

        @staticmethod
        def Interface(value, *, dbus_interface):
            events.append(("manager-interface", dbus_interface))
            return value

    monkeypatch.setattr(
        terminal_manager,
        "SystemdDbusPropertyReader",
        lambda: reader,
    )
    monkeypatch.setattr(
        terminal_manager.importlib,
        "import_module",
        lambda name: Dbus if name == "dbus" else None,
    )

    adapter = WarehouseW3TerminalManager()
    adapter.ref_unit(RUN)
    assert adapter.read_properties(RUN, ("Id",)) == {"Id": RUN}
    assert adapter.get_manager_version(":1.42") == "255.4"
    adapter.unref_unit(RUN)

    assert ("ref", RUN) in events
    assert ("unref", RUN) in events
    assert ("properties", RUN, ("Id",)) in events
    assert not hasattr(adapter, "start_unit")
    assert not hasattr(adapter, "load_unit")
    assert not hasattr(adapter, "reload")


def test_terminal_manager_rejects_owner_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Reader:
        owner = ":1.42"

        def get_unique_owner(self):
            return self.owner

    reader = Reader()

    class Dbus:
        @staticmethod
        def SystemBus():
            return type(
                "Bus",
                (),
                {"get_object": lambda self, owner, path: object()},
            )()

        @staticmethod
        def Interface(value, *, dbus_interface):
            return type(
                "Manager",
                (),
                {
                    "RefUnit": lambda self, unit: None,
                    "UnrefUnit": lambda self, unit: None,
                },
            )()

    monkeypatch.setattr(
        terminal_manager,
        "SystemdDbusPropertyReader",
        lambda: reader,
    )
    monkeypatch.setattr(
        terminal_manager.importlib,
        "import_module",
        lambda name: Dbus if name == "dbus" else None,
    )
    adapter = WarehouseW3TerminalManager()
    reader.owner = ":1.99"

    with pytest.raises(
        WarehouseW3TerminalManagerError,
        match="changed",
    ):
        adapter.ref_unit(RUN)


def test_terminal_manager_source_has_no_launch_or_generic_mutation_surface() -> None:
    source = Path(terminal_manager.__file__).read_text(encoding="utf-8")

    for forbidden in (
        "StartUnit",
        "StopUnit",
        "RestartUnit",
        "KillUnit",
        "ResetFailedUnit",
        "LoadUnit",
        "Reload(",
        "sudo",
        "subprocess",
    ):
        assert forbidden not in source
