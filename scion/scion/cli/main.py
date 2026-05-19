"""Scion CLI executable entrypoint.

The command implementations live under :mod:`scion.cli.commands`; this module
keeps the historical import and ``python -m scion.cli.main`` entry surfaces.
"""

from __future__ import annotations

from scion.cli.app import app, inspect_app, report_app
from scion.cli.commands.common import get_registry as _get_registry
from scion.cli.commands.common import (
    validate_cli_forced_surface as _validate_cli_forced_surface,
)


def main() -> None:
    app()


if __name__ == "__main__":
    main()


__all__ = [
    "app",
    "inspect_app",
    "report_app",
    "main",
    "_get_registry",
    "_validate_cli_forced_surface",
]
