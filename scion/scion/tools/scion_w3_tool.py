"""Fixed-argument Warehouse W3 systemd entrypoint."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from scion.problems.warehouse_delivery.w3_composition import (
    dispatch_installed_launch,
)
from scion.problems.warehouse_delivery.w3_start_gate import (
    WarehouseW3EnvironmentIntegrityRefused,
    WarehouseW3InstalledIdentityRefused,
    WarehouseW3StartPermitRefused,
    WarehouseW3SystemdLineageRefused,
)

_PRECLAIM_EXIT_STATUS = {
    WarehouseW3StartPermitRefused: 70,
    WarehouseW3EnvironmentIntegrityRefused: 71,
    WarehouseW3InstalledIdentityRefused: 72,
    WarehouseW3SystemdLineageRefused: 73,
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scion-w3-tool")
    parser.add_argument(
        "command",
        choices=("run", "seal-unit-drained", "close"),
    )
    parser.add_argument("launch_id")
    arguments = parser.parse_args(argv)
    try:
        dispatch_installed_launch(arguments.command, arguments.launch_id)
    except tuple(_PRECLAIM_EXIT_STATUS) as exc:
        status = _PRECLAIM_EXIT_STATUS.get(type(exc))
        if status is None:
            raise
        return status
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
