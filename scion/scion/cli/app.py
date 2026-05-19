"""Typer app wiring for the Scion CLI."""

from __future__ import annotations

import typer

from scion.cli.commands.init_run import register_init_run_commands
from scion.cli.commands.inspect import register_inspect_commands
from scion.cli.commands.postmortem import register_postmortem_command
from scion.cli.commands.reports import register_report_commands
from scion.cli.commands.weights import register_weight_commands


app = typer.Typer(
    name="scion",
    help="Scion - autonomous operator optimisation framework.",
    no_args_is_help=True,
)

inspect_app = typer.Typer(
    help="Inspect campaign artefacts (branches, hypotheses).",
    no_args_is_help=True,
)
report_app = typer.Typer(
    help="Generate campaign summary reports.",
    no_args_is_help=True,
)

app.add_typer(inspect_app, name="inspect")
app.add_typer(report_app, name="report")

register_init_run_commands(app)
register_weight_commands(app)
register_postmortem_command(app)
register_inspect_commands(inspect_app)
register_report_commands(report_app)


__all__ = ["app", "inspect_app", "report_app"]
