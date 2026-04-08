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

inspect_app = typer.Typer(help="Inspect campaign artefacts (branches, hypotheses).", no_args_is_help=True)
report_app = typer.Typer(help="Generate campaign summary reports.", no_args_is_help=True)

app.add_typer(inspect_app, name="inspect")
app.add_typer(report_app, name="report")


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
# scion inspect (sub-commands)
# ---------------------------------------------------------------------------

def _get_registry(campaign_dir: str):
    """Open LineageRegistry from scion.db in campaign_dir."""
    from scion.lineage.registry import LineageRegistry
    db_path = Path(campaign_dir).resolve() / "scion.db"
    if not db_path.exists():
        typer.echo(f"ERROR: scion.db not found at {db_path}", err=True)
        raise typer.Exit(code=1)
    return LineageRegistry(str(db_path))


@inspect_app.command("campaign")
def inspect_campaign(
    campaign_dir: str = typer.Option("campaign_out", "--campaign-dir", help="Campaign directory"),
) -> None:
    """Campaign overview: total events, branches, champions, gate stats."""
    registry = _get_registry(campaign_dir)
    summary = registry.get_campaign_summary()
    typer.echo(json.dumps(summary, indent=2))


@inspect_app.command("branch")
def inspect_branch(
    branch_id: str = typer.Argument(..., help="Branch ID to inspect"),
    campaign_dir: str = typer.Option("campaign_out", "--campaign-dir", help="Campaign directory"),
) -> None:
    """Branch details: all experiment events and hypotheses for a branch."""
    registry = _get_registry(campaign_dir)
    from scion.lineage.branch_store import BranchStore, HypothesisStore

    branch_store = BranchStore(registry)
    hyp_store = HypothesisStore(registry)

    branch = branch_store.load(branch_id)
    if branch is None:
        typer.echo(f"WARNING: branch {branch_id!r} not found in branches table", err=True)

    events = registry.query_by_branch(branch_id)
    hypotheses = hyp_store.get_by_branch(branch_id)

    output = {
        "branch_id": branch_id,
        "branch": {
            "state": branch.state.value if branch else None,
            "base_champion_id": branch.base_champion_id if branch else None,
            "retry_count": branch.retry_count if branch else None,
            "created_at": branch.created_at.isoformat() if branch else None,
        },
        "experiment_events": events,
        "hypotheses": [
            {
                "hypothesis_id": h.hypothesis_id,
                "action": h.action,
                "change_locus": h.change_locus,
                "target_file": h.target_file,
                "status": h.status,
                "hypothesis_text": (h.hypothesis_text or "")[:300],
                "created_at": h.created_at.isoformat(),
            }
            for h in hypotheses
        ],
    }
    typer.echo(json.dumps(output, indent=2, default=str))


@inspect_app.command("hypothesis")
def inspect_hypothesis(
    hyp_id: str = typer.Argument(..., help="Hypothesis ID to inspect"),
    campaign_dir: str = typer.Option("campaign_out", "--campaign-dir", help="Campaign directory"),
) -> None:
    """Hypothesis details: full record for a single hypothesis."""
    registry = _get_registry(campaign_dir)
    from scion.lineage.branch_store import HypothesisStore

    store = HypothesisStore(registry)
    hyp = store.get_one(hyp_id)
    if hyp is None:
        typer.echo(f"ERROR: hypothesis {hyp_id!r} not found", err=True)
        raise typer.Exit(code=1)

    output = {
        "hypothesis_id": hyp.hypothesis_id,
        "branch_id": hyp.branch_id,
        "action": hyp.action,
        "change_locus": hyp.change_locus,
        "target_file": hyp.target_file,
        "status": hyp.status,
        "hypothesis_text": hyp.hypothesis_text,
        "suggested_weight": hyp.suggested_weight,
        "parent_hypothesis_id": hyp.parent_hypothesis_id,
        "created_at": hyp.created_at.isoformat(),
    }
    typer.echo(json.dumps(output, indent=2))

    # Also show related experiment events
    events = registry.query_by_branch(hyp.branch_id)
    hyp_events = [e for e in events if e.get("hypothesis_id") == hyp_id]
    if hyp_events:
        typer.echo("\nRelated experiment events:")
        typer.echo(json.dumps(hyp_events, indent=2, default=str))


# ---------------------------------------------------------------------------
# scion report (sub-commands)
# ---------------------------------------------------------------------------

@report_app.command("summary")
def report_summary(
    campaign_dir: str = typer.Option("campaign_out", "--campaign-dir", help="Campaign directory"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Write JSON report to file"),
) -> None:
    """Campaign summary: total rounds, champion version, gate intercept rates."""
    campaign_path = Path(campaign_dir).resolve()
    db_path = campaign_path / "scion.db"
    state_file = campaign_path / ".scion_state.json"
    meta = json.loads(state_file.read_text()) if state_file.exists() else {}

    if db_path.exists():
        from scion.lineage.registry import LineageRegistry
        registry = LineageRegistry(str(db_path))
        db_summary = registry.get_campaign_summary()
        total_events = db_summary.get("total_events", 0)
        n_champions = db_summary.get("n_champions", 0)
        contract_failures = db_summary.get("contract_failures", 0)
        verification_failures = db_summary.get("verification_failures", 0)
        by_decision = db_summary.get("by_decision", {})
    else:
        total_events = n_champions = contract_failures = verification_failures = 0
        by_decision = {}

    v_intercept = round(verification_failures / total_events, 4) if total_events > 0 else 0.0
    c_intercept = round(contract_failures / total_events, 4) if total_events > 0 else 0.0
    screening_pass = by_decision.get("queue_validate", 0)
    screening_total = sum(by_decision.get(d, 0) for d in [
        "continue_explore", "expand_screening", "queue_validate"
    ])
    screening_pass_rate = round(screening_pass / screening_total, 4) if screening_total > 0 else 0.0
    promoted = by_decision.get("promote", 0)

    report = {
        "campaign_dir": str(campaign_path),
        "problem_name": meta.get("problem_name", "unknown"),
        "total_experiments": total_events,
        "champion_promotions": promoted,
        "latest_champion_version": n_champions,
        "contract_intercept_rate": c_intercept,
        "verification_intercept_rate": v_intercept,
        "screening_pass_rate": screening_pass_rate,
        "by_decision": by_decision,
    }

    report_json = json.dumps(report, indent=2)
    if output:
        Path(output).write_text(report_json)
        typer.echo(f"Report written to {output}")
    else:
        typer.echo(report_json)


@report_app.command("failures")
def report_failures(
    campaign_dir: str = typer.Option("campaign_out", "--campaign-dir", help="Campaign directory"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Write JSON report to file"),
) -> None:
    """Failure distribution: breakdown by failure type (contract vs verification)."""
    registry = _get_registry(campaign_dir)

    all_failures = registry.query_failures()

    # Group by failure type
    by_type: dict = {}
    for evt in all_failures:
        contract_failed = evt.get("contract_result") == "failed"
        verification_failed = evt.get("verification_result") == "failed"
        v_check = evt.get("verification_result", "")

        if contract_failed:
            key = "contract"
        elif verification_failed:
            # Try to extract check name from verification_result value
            key = f"verification:{v_check}" if v_check and v_check != "failed" else "verification"
        else:
            key = "other"

        by_type[key] = by_type.get(key, 0) + 1

    report = {
        "total_failures": len(all_failures),
        "by_type": by_type,
        "recent_failures": [
            {
                "event_id": e.get("event_id"),
                "branch_id": e.get("branch_id"),
                "timestamp": e.get("timestamp"),
                "contract_result": e.get("contract_result"),
                "verification_result": e.get("verification_result"),
                "decision": e.get("decision"),
            }
            for e in all_failures[:20]  # most recent 20
        ],
    }

    report_json = json.dumps(report, indent=2, default=str)
    if output:
        Path(output).write_text(report_json)
        typer.echo(f"Failure report written to {output}")
    else:
        typer.echo(report_json)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    app()


if __name__ == "__main__":
    main()
