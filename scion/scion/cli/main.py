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

    # Build real Runner + ExperimentProtocol + VerificationGate
    from scion.runtime.subprocess_runner import LocalSubprocessRunner
    from scion.protocol.experiment import ExperimentProtocol, SplitManager, SeedLedger
    from scion.verification.gate import VerificationGate

    metrics_dir = str(campaign_path / "metrics")
    runner = LocalSubprocessRunner()
    split_manager = SplitManager(split_manifest)
    seed_ledger_obj = SeedLedger(seed_ledger)
    experiment_protocol = ExperimentProtocol(
        proto_cfg, split_manager, seed_ledger_obj, runner,
        metrics_dir=metrics_dir,
    )
    verification_gate = VerificationGate(spec, runner, metrics_dir=metrics_dir)

    # Build initial champion — load operator_pool from registry.yaml if available
    from scion.core.models import ChampionState
    from scion.runtime.workspace import WorkspaceMaterializer
    from scion.runtime.pool_manager import read_registry

    materializer = WorkspaceMaterializer(
        str(campaign_path),
        frozen_patterns=frozenset(spec.search_space.frozen) if spec.search_space.frozen else None,
    )
    code_hash = materializer.compute_snapshot_hash(spec.root_dir)

    registry_path = os.path.join(spec.root_dir, "registry.yaml")
    if os.path.exists(registry_path):
        try:
            operator_pool = read_registry(registry_path)
        except Exception as exc:
            typer.echo(f"WARNING: could not load registry.yaml: {exc}", err=True)
            operator_pool = {}
    else:
        operator_pool = {}

    champion = ChampionState(
        version=1,
        operator_pool=operator_pool,
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
        verification_gate=verification_gate,
        experiment_protocol=experiment_protocol,
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


@inspect_app.command("weights")
def inspect_weights(
    campaign_dir: str = typer.Option("campaign_out", "--campaign-dir", help="Campaign directory"),
) -> None:
    """Show current champion operator weights from registry.yaml."""
    campaign_path = Path(campaign_dir).resolve()
    state_file = campaign_path / ".scion_state.json"

    # Find registry.yaml: check champions table first, then fall back to problem root_dir
    registry_path: Optional[Path] = None

    db_path = campaign_path / "scion.db"
    if db_path.exists():
        import sqlite3 as _sqlite3
        try:
            with _sqlite3.connect(str(db_path)) as conn:
                row = conn.execute(
                    "SELECT code_snapshot_path FROM champions ORDER BY version DESC LIMIT 1"
                ).fetchone()
                if row and row[0]:
                    candidate = Path(row[0]) / "registry.yaml"
                    if candidate.exists():
                        registry_path = candidate
        except Exception:
            pass

    if registry_path is None and state_file.exists():
        try:
            state = json.loads(state_file.read_text())
            problem_yaml = state.get("problem_yaml", "")
            if problem_yaml:
                problem_dir = Path(problem_yaml).parent
                candidate = problem_dir / "registry.yaml"
                if candidate.exists():
                    registry_path = candidate
        except Exception:
            pass

    if registry_path is None:
        typer.echo("ERROR: no registry.yaml found (run 'scion init' and ensure registry.yaml exists)", err=True)
        raise typer.Exit(code=1)

    try:
        from scion.runtime.pool_manager import read_registry
        pool = read_registry(str(registry_path))
    except Exception as exc:
        typer.echo(f"ERROR: failed to read registry.yaml: {exc}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Operator weights ({registry_path}):")
    typer.echo(f"  {'Name':<30} {'Weight':>8}  {'Category':<20}  File")
    typer.echo(f"  {'-'*30} {'-'*8}  {'-'*20}  {'-'*40}")
    for name, op in sorted(pool.items(), key=lambda x: -x[1].weight):
        typer.echo(f"  {name:<30} {op.weight:>8.4f}  {(op.category or ''):<20}  {op.file_path}")


# ---------------------------------------------------------------------------
# scion optimize-weights
# ---------------------------------------------------------------------------

@app.command("optimize-weights")
def optimize_weights(
    campaign_dir: str = typer.Option("campaign_out", "--campaign-dir", help="Campaign directory"),
    problem: Optional[str] = typer.Option(None, "--problem", help="Path to problem.yaml (overrides state file)"),
    protocol: Optional[str] = typer.Option(None, "--protocol", help="Path to protocol.yaml"),
    split: Optional[str] = typer.Option(None, "--split", help="Path to split_manifest.yaml"),
    seeds: Optional[str] = typer.Option(None, "--seeds", help="Path to seed_ledger.yaml"),
) -> None:
    """Manually trigger weight optimisation on the latest champion snapshot."""
    campaign_path = Path(campaign_dir).resolve()
    state_file = campaign_path / ".scion_state.json"

    if problem:
        problem_yaml = Path(problem).resolve()
    elif state_file.exists():
        state = json.loads(state_file.read_text())
        problem_yaml = Path(state["problem_yaml"])
    else:
        typer.echo("ERROR: no campaign state found — run 'scion init' first", err=True)
        raise typer.Exit(code=1)

    if not problem_yaml.exists():
        typer.echo(f"ERROR: problem.yaml not found: {problem_yaml}", err=True)
        raise typer.Exit(code=1)

    from scion.config.problem import ProblemSpec, ProtocolConfig, SplitManifest, SeedLedgerConfig
    from scion.runtime.subprocess_runner import LocalSubprocessRunner
    from scion.runtime.pool_manager import read_registry, read_weights
    from scion.parameter.optimizer import RandomLocalWeightOptimizer
    from scion.parameter.evaluator import collect_baseline, evaluate_weights
    from scion.parameter.search_space import ParameterSearchSpace

    spec = ProblemSpec.from_yaml(str(problem_yaml))
    problem_dir = problem_yaml.parent

    if protocol:
        proto_cfg = ProtocolConfig.from_yaml(protocol)
    else:
        proto_path = problem_dir / "protocol.yaml"
        proto_cfg = ProtocolConfig.from_yaml(str(proto_path)) if proto_path.exists() else ProtocolConfig()

    if split:
        split_manifest = SplitManifest.from_yaml(split)
    else:
        split_path = problem_dir / "split_manifest.yaml"
        split_manifest = SplitManifest.from_yaml(str(split_path)) if split_path.exists() else SplitManifest(screening=[], validation=[], frozen=[])

    if seeds:
        seed_ledger = SeedLedgerConfig.from_yaml(seeds)
    else:
        seed_path = problem_dir / "seed_ledger.yaml"
        seed_ledger = SeedLedgerConfig.from_yaml(str(seed_path)) if seed_path.exists() else SeedLedgerConfig(screening=[42], validation=[1, 2], frozen=[10])

    # Find latest champion snapshot
    db_path = campaign_path / "scion.db"
    snapshot_path: Optional[Path] = None
    champion_version = 0
    if db_path.exists():
        import sqlite3 as _sqlite3
        try:
            with _sqlite3.connect(str(db_path)) as conn:
                row = conn.execute(
                    "SELECT version, code_snapshot_path FROM champions ORDER BY version DESC LIMIT 1"
                ).fetchone()
                if row:
                    champion_version = row[0]
                    snapshot_path = Path(row[1]) if row[1] else None
        except Exception:
            pass

    if snapshot_path is None:
        # Fall back to problem root_dir
        snapshot_path = Path(spec.root_dir)
        typer.echo(f"WARNING: no champion in DB; using root_dir as snapshot: {snapshot_path}", err=True)

    registry_path = snapshot_path / "registry.yaml"
    if not registry_path.exists():
        typer.echo(f"ERROR: registry.yaml not found at {registry_path}", err=True)
        raise typer.Exit(code=1)

    try:
        current_weights = read_weights(str(registry_path))
    except Exception as exc:
        typer.echo(f"ERROR: failed to read weights: {exc}", err=True)
        raise typer.Exit(code=1)

    if not current_weights:
        typer.echo("ERROR: no operators in registry — nothing to optimise", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Optimising weights for champion v{champion_version} at {snapshot_path}")
    typer.echo(f"  Operators: {list(current_weights.keys())}")

    param_cfg = spec.parameter_search
    runner = LocalSubprocessRunner()

    eval_cases = list(param_cfg.eval_cases)
    if not eval_cases:
        eval_cases = list(split_manifest.screening)
    resolved_cases = [
        os.path.join(spec.root_dir, c) if not os.path.isabs(c) else c
        for c in eval_cases
    ]
    if not resolved_cases:
        typer.echo("WARNING: no eval cases configured; using registry-only optimisation skipped", err=True)
        raise typer.Exit(code=1)

    eval_seeds = list(seed_ledger.screening)[:param_cfg.n_eval_seeds]
    time_limit = getattr(getattr(spec, 'solver', None), 'time_limit_sec', 300)
    artifacts_dir = str(campaign_path / "artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)

    import shutil
    eval_ws = str(campaign_path / f"weight_opt_manual_v{champion_version}")
    if os.path.exists(eval_ws):
        shutil.rmtree(eval_ws)
    shutil.copytree(str(snapshot_path), eval_ws)
    import stat
    for root, dirs, files in os.walk(eval_ws):
        for d in dirs:
            os.chmod(os.path.join(root, d), 0o755)
        for f in files:
            os.chmod(os.path.join(root, f), 0o644)

    typer.echo(f"  Eval cases: {resolved_cases}")
    typer.echo(f"  Eval seeds: {eval_seeds}")

    baseline = collect_baseline(eval_ws, resolved_cases, eval_seeds, runner, time_limit)
    operator_names = tuple(current_weights.keys())

    search_space = ParameterSearchSpace(
        operator_names=operator_names,
        weight_bounds=param_cfg.weight_bounds,
        n_initial_random=param_cfg.n_initial_random,
        n_iterations=param_cfg.n_iterations,
        n_eval_seeds=param_cfg.n_eval_seeds,
        eval_cases=tuple(resolved_cases),
    )

    def _eval_fn(weights):
        return evaluate_weights(
            weights=weights,
            workspace=eval_ws,
            cases=resolved_cases,
            seeds=eval_seeds,
            runner=runner,
            time_limit_sec=time_limit,
            baseline_objectives=baseline,
        )

    optimizer = RandomLocalWeightOptimizer(search_space, _eval_fn, seed=champion_version)
    result = optimizer.optimize(current_weights, artifacts_dir=artifacts_dir)

    typer.echo(f"\nOptimisation complete:")
    typer.echo(f"  baseline_score : {result.baseline_score:.6f}")
    typer.echo(f"  best_score     : {result.best_score:.6f}")
    typer.echo(f"  improved       : {result.improved}")
    typer.echo(f"  n_evaluations  : {result.n_evaluations}")

    if result.improved:
        typer.echo(f"\nBest weights:")
        for name, w in result.best_weights.items():
            typer.echo(f"  {name}: {w:.6f}")
        typer.echo(
            "\nTo apply: manually update registry.yaml in the champion snapshot with the above weights."
        )
    else:
        typer.echo("\nNo improvement found over baseline — champion weights unchanged.")

    # Cleanup eval workspace
    try:
        shutil.rmtree(eval_ws)
    except Exception:
        pass


@inspect_app.command("campaign")
def inspect_campaign(
    campaign_dir: str = typer.Option("campaign_out", "--campaign-dir", help="Campaign directory"),
) -> None:
    """Campaign overview: total events, branches, champions, gate stats, weight optimizations."""
    registry = _get_registry(campaign_dir)
    summary = registry.get_campaign_summary()

    # Enrich with weight optimization history
    weight_opts = registry.query_weight_optimizations()
    if weight_opts:
        import json as _json
        latest = weight_opts[-1]
        best_weights = {}
        try:
            best_weights = _json.loads(latest.get("best_weights_json") or "{}")
        except Exception:
            pass
        summary["weight_optimization"] = {
            "total_runs": len(weight_opts),
            "latest_champion_version": latest.get("champion_version"),
            "latest_improved": bool(latest.get("improved")),
            "latest_baseline_score": latest.get("baseline_score"),
            "latest_best_score": latest.get("best_score"),
            "latest_best_weights": best_weights,
        }
    else:
        summary["weight_optimization"] = None

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
    markdown: bool = typer.Option(False, "--markdown", "-m", help="Output as markdown instead of JSON"),
) -> None:
    """Campaign summary: total rounds, champion version, gate intercept rates.

    Includes family distribution, stagnation signals, verification failure
    breakdown, and weight optimization results when available.
    """
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

        # Family distribution from hypotheses.change_locus
        import sqlite3 as _sqlite3
        family_dist: dict = {}
        with _sqlite3.connect(str(db_path)) as conn:
            for row in conn.execute(
                "SELECT change_locus, COUNT(*) FROM hypotheses "
                "WHERE change_locus IS NOT NULL GROUP BY change_locus ORDER BY 2 DESC"
            ).fetchall():
                family_dist[row[0]] = row[1]

        # Weight optimization results
        weight_opt_records = registry.query_weight_optimizations()
        weight_opt_summary = None
        if weight_opt_records:
            improved_count = sum(1 for r in weight_opt_records if r.get("improved"))
            latest = weight_opt_records[-1]
            weight_opt_summary = {
                "total_runs": len(weight_opt_records),
                "improved_count": improved_count,
                "latest_baseline_score": latest.get("baseline_score"),
                "latest_best_score": latest.get("best_score"),
                "latest_improved": bool(latest.get("improved")),
            }

        # Stagnation signals from campaign_summary.json (if present)
        stagnation_signals: list = []
        summary_file = campaign_path / "campaign_summary.json"
        if summary_file.exists():
            try:
                cs = json.loads(summary_file.read_text())
                stagnation_signals = cs.get("stagnation_signals", [])
            except Exception:
                pass

        # Verification failure breakdown
        vfail_breakdown: dict = {}
        all_failures = registry.query_failures()
        for evt in all_failures:
            if evt.get("verification_result") == "failed":
                stage = evt.get("decision_reason") or "unknown"
                vfail_breakdown[stage] = vfail_breakdown.get(stage, 0) + 1
    else:
        total_events = n_champions = contract_failures = verification_failures = 0
        by_decision = {}
        family_dist = {}
        weight_opt_summary = None
        stagnation_signals = []
        vfail_breakdown = {}

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
        "family_distribution": family_dist,
        "verification_failure_breakdown": vfail_breakdown,
        "weight_optimization": weight_opt_summary,
        "stagnation_signals": stagnation_signals,
    }

    if markdown:
        lines = [
            f"# Campaign Report: {meta.get('problem_name', 'unknown')}",
            "",
            "## Overview",
            f"- Total experiments: {total_events}",
            f"- Champion promotions: {promoted}",
            f"- Latest champion version: {n_champions}",
            f"- Contract intercept rate: {c_intercept:.1%}",
            f"- Verification intercept rate: {v_intercept:.1%}",
            f"- Screening pass rate: {screening_pass_rate:.1%}",
            "",
        ]
        if family_dist:
            lines.append("## Hypothesis Family Distribution")
            for fam, cnt in family_dist.items():
                lines.append(f"- {fam}: {cnt}")
            lines.append("")
        if vfail_breakdown:
            lines.append("## Verification Failure Breakdown")
            for reason, cnt in sorted(vfail_breakdown.items(), key=lambda x: -x[1]):
                lines.append(f"- {reason}: {cnt}")
            lines.append("")
        if weight_opt_summary:
            lines.append("## Weight Optimization")
            lines.append(f"- Runs: {weight_opt_summary['total_runs']}")
            lines.append(f"- Improved: {weight_opt_summary['improved_count']}")
            lines.append(f"- Latest baseline score: {weight_opt_summary['latest_baseline_score']}")
            lines.append(f"- Latest best score: {weight_opt_summary['latest_best_score']}")
            lines.append("")
        if stagnation_signals:
            lines.append("## Stagnation Signals")
            for sig in stagnation_signals:
                lines.append(
                    f"- [{sig.get('severity', '?').upper()}] {sig.get('kind', '?')}: "
                    f"{sig.get('detail', '')}"
                )
            lines.append("")
        report_text = "\n".join(lines)
        if output:
            Path(output).write_text(report_text)
            typer.echo(f"Report written to {output}")
        else:
            typer.echo(report_text)
        return

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
# scion postmortem (T24)
# ---------------------------------------------------------------------------

@app.command()
def postmortem(
    campaign_dir: str = typer.Argument(..., help="Campaign directory containing campaign_summary.json"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Write report to file"),
    json_output: bool = typer.Option(False, "--json", help="Output machine-readable JSON instead of markdown"),
) -> None:
    """Generate a postmortem analysis report from campaign artifacts.

    Reads campaign_summary.json and formats a markdown (or JSON with --json) report with:
    - Campaign summary (rounds, duration, budget used)
    - Hypothesis family distribution
    - Failure breakdown by type
    - Stagnation signals (if any)
    - Promoted operators (if any)
    - Recommendations for next campaign
    - Comparison across campaigns if multiple found in directory
    """
    campaign_path = Path(campaign_dir).resolve()
    summary_file = campaign_path / "campaign_summary.json"

    if not summary_file.exists():
        typer.echo(f"ERROR: campaign_summary.json not found at {summary_file}", err=True)
        raise typer.Exit(code=1)

    try:
        summary = json.loads(summary_file.read_text())
    except Exception as exc:
        typer.echo(f"ERROR: failed to read campaign_summary.json: {exc}", err=True)
        raise typer.Exit(code=1)

    lines: list = ["# Scion Campaign Postmortem", ""]

    # 1. Campaign summary
    lines.append("## Campaign Summary")
    lines.append(f"- Campaign ID: {summary.get('campaign_id', 'unknown')}")
    lines.append(f"- Total rounds: {summary.get('total_rounds', 0)}")
    lines.append(f"- Champion version: {summary.get('champion_version', 0)}")
    budget_util = summary.get("budget_utilization", 0.0)
    lines.append(f"- Budget utilization: {budget_util:.1%}")
    lines.append("")

    # 2. Hypothesis family distribution
    family_coverage = summary.get("family_coverage", {})
    if family_coverage:
        lines.append("## Hypothesis Family Distribution")
        for family, count in sorted(family_coverage.items(), key=lambda x: -x[1]):
            lines.append(f"- {family}: {count} hypothesis(es)")
        lines.append("")

    # 3. Failure breakdown
    vfail = summary.get("verification_failure_breakdown", {})
    action_locus = summary.get("action_locus_coverage", {})
    steps = summary.get("steps", [])
    total_steps = len(steps)
    n_failed = sum(1 for s in steps if s.get("failure_stage"))
    n_promoted = sum(1 for s in steps if s.get("decision") == "promote")

    lines.append("## Failure Breakdown")
    lines.append(f"- Total steps: {total_steps}")
    lines.append(f"- Failures: {n_failed}")
    lines.append(f"- Promotions: {n_promoted}")
    if vfail:
        lines.append("- Verification failures by type:")
        for vtype, count in sorted(vfail.items(), key=lambda x: -x[1]):
            lines.append(f"  - {vtype}: {count}")
    # Failure stage breakdown
    failure_stages: dict = {}
    for s in steps:
        fs = s.get("failure_stage")
        if fs:
            failure_stages[fs] = failure_stages.get(fs, 0) + 1
    if failure_stages:
        lines.append("- Failure stages:")
        for stage, count in sorted(failure_stages.items(), key=lambda x: -x[1]):
            lines.append(f"  - {stage}: {count}")
    lines.append("")

    # 4. Action/locus coverage
    if action_locus:
        lines.append("## Action/Locus Coverage")
        for combo, count in sorted(action_locus.items(), key=lambda x: -x[1]):
            lines.append(f"- {combo}: {count}")
        lines.append("")

    # 5. Cache stats
    cache_stats = summary.get("cache_stats", {})
    if cache_stats:
        lines.append("## LLM Cache Statistics")
        lines.append(f"- Total tokens: {cache_stats.get('total_tokens', 0)}")
        lines.append(f"- Cache read tokens: {cache_stats.get('cache_read_tokens', 0)}")
        lines.append(f"- Cache hit rate: {cache_stats.get('cache_hit_rate', 0.0):.1%}")
        lines.append("")

    # 6. Stagnation signals
    signals = summary.get("stagnation_signals", [])
    if signals:
        lines.append("## Stagnation Signals")
        for sig in signals:
            lines.append(f"- [{sig.get('severity', '?').upper()}] {sig.get('kind', '?')}: {sig.get('detail', '')}")
            lines.append(f"  Suggested action: {sig.get('suggested_action', '')}")
        lines.append("")

    # 7. Diagnostics
    diagnostics = summary.get("diagnostics", [])
    if diagnostics:
        lines.append("## Campaign Diagnostics")
        for diag in diagnostics:
            lines.append(f"- Round {diag.get('round_num', '?')}: {diag.get('recommendation', '?')}")
        lines.append("")

    # 8. Promoted operators
    promoted_steps = [s for s in steps if s.get("decision") == "promote"]
    if promoted_steps:
        lines.append("## Promoted Operators")
        for s in promoted_steps:
            hyp = s.get("hypothesis", {})
            pr = s.get("protocol_result", {})
            wr = pr.get("win_rate", "?") if pr else "?"
            lines.append(
                f"- Round {s.get('round', '?')}: {hyp.get('action', '?')} {hyp.get('target_file', '?')}"
                f" (win_rate={wr})"
            )
            lines.append(f"  Hypothesis: {(hyp.get('text') or '')[:120]}")
        lines.append("")

    # 9. Recommendations for next campaign
    lines.append("## Recommendations for Next Campaign")
    # Derive recommendations from what we see
    diagnostics_recs = [d.get("recommendation", "") for d in diagnostics]
    if "check_environment" in diagnostics_recs:
        lines.append("- **Critical**: Check execution environment — cascading failures detected.")
    if "diversify_locus" in diagnostics_recs:
        lines.append("- Diversify operator locus — oscillation pattern suggests current locus is stale.")
    if "switch_action" in diagnostics_recs:
        lines.append("- Switch mechanism family — plateau detected with same approach.")
    if not diagnostics_recs:
        if n_promoted == 0:
            lines.append("- No operators promoted. Consider increasing max_rounds or exploring new mechanism families.")
        else:
            lines.append(f"- {n_promoted} operator(s) promoted. Continue refining promoted mechanisms.")
    if family_coverage:
        dominant_family = max(family_coverage, key=lambda k: family_coverage[k])
        lines.append(f"- Dominant family was '{dominant_family}' — consider diversifying.")
    lines.append("")

    # 10. Comparison with sibling campaigns
    parent = campaign_path.parent
    sibling_summaries = []
    for sibling in sorted(parent.iterdir()):
        if sibling == campaign_path or not sibling.is_dir():
            continue
        sib_file = sibling / "campaign_summary.json"
        if sib_file.exists():
            try:
                sib_data = json.loads(sib_file.read_text())
                sibling_summaries.append((sibling.name, sib_data))
            except Exception:
                pass

    if sibling_summaries:
        lines.append("## Comparison with Other Campaigns")
        lines.append(
            f"| Campaign | Rounds | Champion | Promotions | Budget |"
        )
        lines.append("|---|---|---|---|---|")
        # Current campaign row
        this_name = campaign_path.name
        this_rounds = summary.get("total_rounds", 0)
        this_champ = summary.get("champion_version", 0)
        this_prom = n_promoted
        this_budget = f"{summary.get('budget_utilization', 0.0):.1%}"
        lines.append(f"| **{this_name}** | {this_rounds} | {this_champ} | {this_prom} | {this_budget} |")
        for sib_name, sib in sibling_summaries:
            sib_steps = sib.get("steps", [])
            sib_prom = sum(1 for s in sib_steps if s.get("decision") == "promote")
            lines.append(
                f"| {sib_name} | {sib.get('total_rounds', 0)} | "
                f"{sib.get('champion_version', 0)} | {sib_prom} | "
                f"{sib.get('budget_utilization', 0.0):.1%} |"
            )
        lines.append("")

    md_report = "\n".join(lines)

    if json_output:
        # Build structured JSON postmortem
        json_report = {
            "campaign_id": summary.get("campaign_id", "unknown"),
            "campaign_dir": str(campaign_path),
            "total_rounds": summary.get("total_rounds", 0),
            "champion_version": summary.get("champion_version", 0),
            "budget_utilization": summary.get("budget_utilization", 0.0),
            "total_steps": total_steps,
            "n_failed": n_failed,
            "n_promoted": n_promoted,
            "family_coverage": family_coverage,
            "verification_failure_breakdown": vfail,
            "failure_stages": failure_stages,
            "action_locus_coverage": action_locus,
            "stagnation_signals": signals,
            "diagnostics": diagnostics,
            "cache_stats": cache_stats,
            "comparisons": [
                {
                    "name": sib_name,
                    "total_rounds": sib.get("total_rounds", 0),
                    "champion_version": sib.get("champion_version", 0),
                    "budget_utilization": sib.get("budget_utilization", 0.0),
                }
                for sib_name, sib in sibling_summaries
            ],
        }
        report_text = json.dumps(json_report, indent=2)
        if output:
            Path(output).write_text(report_text)
            typer.echo(f"Postmortem JSON written to {output}")
        else:
            typer.echo(report_text)
        return

    if output:
        Path(output).write_text(md_report)
        typer.echo(f"Postmortem report written to {output}")
    else:
        typer.echo(md_report)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    app()


if __name__ == "__main__":
    main()
