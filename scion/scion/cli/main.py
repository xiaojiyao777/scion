"""Scion CLI — T21: typer-based command-line interface."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(
    name="scion",
    help="Scion — autonomous operator optimisation framework.",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# scion init
# ---------------------------------------------------------------------------

@app.command()
def init(
    problem: str = typer.Option(..., "--problem", help="Path to problem.yaml"),
    campaign_dir: str = typer.Option("campaign_out", "--campaign-dir", help="Output directory for campaign artefacts"),
) -> None:
    """Initialise a Scion campaign from a problem.yaml specification."""
    problem_path = Path(problem).resolve()
    if not problem_path.exists():
        typer.echo(f"ERROR: problem file not found: {problem_path}", err=True)
        raise typer.Exit(code=1)

    campaign_path = Path(campaign_dir).resolve()
    campaign_path.mkdir(parents=True, exist_ok=True)

    # Validate the YAML can be loaded
    try:
        from scion.config.problem import ProblemSpec
        spec = ProblemSpec.from_yaml(str(problem_path))
    except Exception as exc:
        typer.echo(f"ERROR: failed to parse problem.yaml: {exc}", err=True)
        raise typer.Exit(code=1)

    # Write a state file so subsequent commands know about this campaign
    state = {
        "problem_yaml": str(problem_path),
        "campaign_dir": str(campaign_path),
        "problem_name": spec.name,
    }
    state_file = campaign_path / ".scion_state.json"
    state_file.write_text(json.dumps(state, indent=2))

    typer.echo(f"Campaign initialised: {campaign_path}")
    typer.echo(f"  problem : {spec.name}")
    typer.echo(f"  root_dir: {spec.root_dir}")


# ---------------------------------------------------------------------------
# scion run
# ---------------------------------------------------------------------------

@app.command()
def run(
    mock_llm: bool = typer.Option(False, "--mock-llm", help="Use MockLLMClient (no real API calls)"),
    rounds: int = typer.Option(10, "--rounds", help="Maximum number of campaign rounds"),
    campaign_dir: str = typer.Option("campaign_out", "--campaign-dir", help="Campaign directory (from scion init)"),
    problem: Optional[str] = typer.Option(None, "--problem", help="Path to problem.yaml (overrides state file)"),
    protocol: Optional[str] = typer.Option(None, "--protocol", help="Path to protocol.yaml"),
    split: Optional[str] = typer.Option(None, "--split", help="Path to split_manifest.yaml"),
    seeds: Optional[str] = typer.Option(None, "--seeds", help="Path to seed_ledger.yaml"),
) -> None:
    """Run the Scion main loop.

    Use --mock-llm for local testing (no API key required).
    """
    campaign_path = Path(campaign_dir).resolve()
    state_file = campaign_path / ".scion_state.json"

    # Resolve problem.yaml path
    if problem:
        problem_yaml = Path(problem).resolve()
    elif state_file.exists():
        state = json.loads(state_file.read_text())
        problem_yaml = Path(state["problem_yaml"])
    else:
        typer.echo("ERROR: no campaign state found — run 'scion init --problem <yaml>' first", err=True)
        raise typer.Exit(code=1)

    if not problem_yaml.exists():
        typer.echo(f"ERROR: problem.yaml not found: {problem_yaml}", err=True)
        raise typer.Exit(code=1)

    from scion.config.problem import ProblemSpec, ProtocolConfig, SplitManifest, SeedLedgerConfig

    spec = ProblemSpec.from_yaml(str(problem_yaml))
    problem_dir = problem_yaml.parent

    # Protocol config
    if protocol:
        proto_cfg = ProtocolConfig.from_yaml(protocol)
    else:
        proto_path = problem_dir / "protocol.yaml"
        if proto_path.exists():
            proto_cfg = ProtocolConfig.from_yaml(str(proto_path))
        else:
            proto_cfg = ProtocolConfig()

    # Split manifest
    if split:
        split_manifest = SplitManifest.from_yaml(split)
    else:
        split_path = problem_dir / "split_manifest.yaml"
        if split_path.exists():
            split_manifest = SplitManifest.from_yaml(str(split_path))
        else:
            split_manifest = SplitManifest(screening=[], validation=[], frozen=[])

    # Seed ledger
    if seeds:
        seed_ledger = SeedLedgerConfig.from_yaml(seeds)
    else:
        seed_path = problem_dir / "seed_ledger.yaml"
        if seed_path.exists():
            seed_ledger = SeedLedgerConfig.from_yaml(str(seed_path))
        else:
            seed_ledger = SeedLedgerConfig(screening=[42], validation=[1, 2], frozen=[10])

    # LLM client
    if mock_llm:
        from scion.proposal.mock_client import MockLLMClient
        llm_client = MockLLMClient(mode="success")
    else:
        try:
            from scion.proposal.llm_client import LLMClient
            llm_client = LLMClient()
        except Exception as exc:
            typer.echo(f"ERROR: failed to create LLMClient: {exc}", err=True)
            raise typer.Exit(code=1)

    # Build a minimal champion from spec root_dir
    from scion.core.models import ChampionState
    from scion.runtime.workspace import WorkspaceMaterializer

    materializer = WorkspaceMaterializer(
        str(campaign_path),
        frozen_patterns=frozenset(spec.search_space.frozen) if spec.search_space.frozen else None,
    )
    code_hash = materializer.compute_code_hash(spec.root_dir)
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="initial",
        code_snapshot_path=spec.root_dir,
        code_snapshot_hash=code_hash,
    )

    from scion.core.campaign import CampaignManager

    mgr = CampaignManager(
        problem_spec=spec,
        protocol_config=proto_cfg,
        split_manifest=split_manifest,
        seed_ledger=seed_ledger,
        llm_client=llm_client,
        champion=champion,
        campaign_dir=str(campaign_path),
    )

    typer.echo(f"Starting campaign: {spec.name} (max_rounds={rounds}, mock_llm={mock_llm})")
    mgr.run(max_rounds=rounds)

    state_data = mgr.get_state()
    typer.echo(f"Campaign finished.")
    typer.echo(f"  experiments  : {state_data['n_experiments']}")
    typer.echo(f"  champion ver : {state_data['champion_version']}")
    typer.echo(f"  active branches: {state_data['n_active_branches']}")


# ---------------------------------------------------------------------------
# scion inspect
# ---------------------------------------------------------------------------

@app.command()
def inspect(
    branch: str = typer.Option(..., "--branch", help="Branch ID to inspect"),
    campaign_dir: str = typer.Option("campaign_out", "--campaign-dir", help="Campaign directory"),
) -> None:
    """Query the state of a specific branch."""
    campaign_path = Path(campaign_dir).resolve()
    if not campaign_path.exists():
        typer.echo(f"ERROR: campaign directory not found: {campaign_path}", err=True)
        raise typer.Exit(code=1)

    # Look for lineage data stored by campaign
    lineage_file = campaign_path / "lineage" / f"{branch}.json"
    if lineage_file.exists():
        data = json.loads(lineage_file.read_text())
        typer.echo(json.dumps(data, indent=2))
        return

    # Try to find branch info in the campaign directory structure
    branch_dir = campaign_path / "branches" / branch
    if branch_dir.exists():
        typer.echo(f"Branch directory: {branch_dir}")
        for item in branch_dir.iterdir():
            typer.echo(f"  {item.name}")
        return

    typer.echo(f"Branch {branch!r} not found in campaign at {campaign_path}", err=True)
    raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# scion report
# ---------------------------------------------------------------------------

@app.command()
def report(
    campaign_dir: str = typer.Option("campaign_out", "--campaign-dir", help="Campaign directory"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Write JSON report to file"),
) -> None:
    """Output a summary of the campaign results."""
    campaign_path = Path(campaign_dir).resolve()
    if not campaign_path.exists():
        typer.echo(f"ERROR: campaign directory not found: {campaign_path}", err=True)
        raise typer.Exit(code=1)

    state_file = campaign_path / ".scion_state.json"
    meta: dict = {}
    if state_file.exists():
        meta = json.loads(state_file.read_text())

    # Collect champion snapshots
    champ_dir = campaign_path / "champions"
    champion_versions: list = []
    if champ_dir.exists():
        champion_versions = sorted(str(p.name) for p in champ_dir.iterdir() if p.is_dir())

    # Collect branch info
    branch_dir = campaign_path / "branches"
    branch_count = 0
    if branch_dir.exists():
        branch_count = sum(1 for p in branch_dir.iterdir() if p.is_dir())

    report_data = {
        "campaign_dir": str(campaign_path),
        "problem_name": meta.get("problem_name", "unknown"),
        "problem_yaml": meta.get("problem_yaml", "unknown"),
        "champion_versions": champion_versions,
        "branch_count": branch_count,
    }

    report_json = json.dumps(report_data, indent=2)
    if output:
        Path(output).write_text(report_json)
        typer.echo(f"Report written to {output}")
    else:
        typer.echo(report_json)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    app()


if __name__ == "__main__":
    main()
