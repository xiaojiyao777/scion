"""Fixed-argument Warehouse W3 systemd entrypoint."""

from __future__ import annotations

import argparse

from scion.problems.warehouse_delivery.w3_composition import (
    dispatch_installed_launch,
)


def main() -> int:
    parser = argparse.ArgumentParser(prog="scion-w3-tool")
    parser.add_argument(
        "command",
        choices=("run", "seal-unit-drained", "close"),
    )
    parser.add_argument("launch_id")
    arguments = parser.parse_args()
    dispatch_installed_launch(arguments.command, arguments.launch_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
