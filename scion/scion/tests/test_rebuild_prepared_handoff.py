from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


TOOL_PATH = Path(__file__).parents[2] / "tools" / "rebuild_prepared_handoff.py"
SPEC = importlib.util.spec_from_file_location("rebuild_prepared_handoff", TOOL_PATH)
assert SPEC is not None
rebuild_tool = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(rebuild_tool)


def test_rebuild_prepared_handoff_refreshes_problem_specific_coverage(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "prepared-root"
    campaign_dir = run_root / "campaign"
    config_dir = run_root / "config"
    campaign_dir.mkdir(parents=True)
    config_dir.mkdir()
    for name in ("problem.yaml", "protocol.yaml", "split.yaml", "seeds.yaml"):
        (config_dir / name).write_text("ok: true\n", encoding="utf-8")

    command = (
        f"{sys.executable} -m scion.cli.main run "
        f"--problem {config_dir / 'problem.yaml'} "
        f"--protocol {config_dir / 'protocol.yaml'} "
        f"--split {config_dir / 'split.yaml'} "
        f"--seeds {config_dir / 'seeds.yaml'} "
        f"--campaign-dir {campaign_dir} --rounds 1 --agentic-proposal"
    )
    _write_json(
        run_root / "run_status.json",
        {
            "schema": "scion.launcher_prepare.v1",
            "status": "prepared",
            "prepared_only": True,
            "run_root": str(run_root),
            "campaign_dir": str(campaign_dir),
        },
    )
    _write_json(
        run_root / "prepared_run_manifest.v1.json",
        {
            "schema_version": "scion.launcher_prepared_run_manifest.v1",
            "report_only": True,
            "quality_judgment": False,
            "decision_features_excluded": True,
            "campaign_state_mutated": False,
            "scheduler_state_mutated": False,
            "promotion_state_mutated": False,
            "run_root": str(run_root),
            "campaign_dir": str(campaign_dir),
            "problem_family": "cvrp",
            "analysis_intent": "Prepared handoff rebuild fixture.",
            "acceptance_focus": ["Keep handoff report-only."],
            "research_focus": _cvrp_research_focus(),
            "resume_from_campaign": "/tmp/source-campaign",
            "command": command,
            "execution": {
                "measurement_governance": "on",
                "proposal_context_ablation": "full",
            },
            "model": {
                "name": "gpt-5.5",
                "base_url": "http://127.0.0.1:8080",
                "completion_preflight": True,
            },
            "git": {
                "commit": _git_head_short(),
                "runtime_guard_paths": "scion/tools",
            },
            "config": {
                "problem": str(config_dir / "problem.yaml"),
                "protocol": str(config_dir / "protocol.yaml"),
                "split": str(config_dir / "split.yaml"),
                "seeds": str(config_dir / "seeds.yaml"),
            },
            "report_metadata": {
                "control_pair_key": "cvrp.prepared:rep01",
                "postrun_reports": True,
                "postrun_acceptance_families": [
                    "summaries",
                    "failures",
                    "research_efficiency",
                    "manifests",
                    "analysis_brief",
                    "inventory",
                    "rebuild",
                ],
            },
        },
    )
    (run_root / "prepared_run_manifest.md").write_text("# prepared\n", encoding="utf-8")
    (run_root / "command.txt").write_text(
        "\n".join(
            [
                "report_metadata:",
                f"PREPARED_RUN_MANIFEST={run_root / 'prepared_run_manifest.v1.json'}",
                "",
                "command:",
                command,
            ]
        ),
        encoding="utf-8",
    )
    stale = run_root / "prepared_handoff" / "analysis_brief" / (
        "cvrp_on_full.prepared_analysis_brief.v1.json"
    )
    _write_json(
        stale,
        {"phase4_evidence_coverage": {"problem_specific_requirements": {}}},
    )

    manifest = rebuild_tool.rebuild_prepared_handoff(
        run_root,
        report_stem="cvrp_on_full",
        strict=True,
    )

    handoff_dir = run_root / "prepared_handoff"
    brief = json.loads(stale.read_text(encoding="utf-8"))
    inventory = json.loads(
        (
            handoff_dir
            / "inventory"
            / "cvrp_on_full.prepared_artifact_inventory.v1.json"
        ).read_text(encoding="utf-8")
    )
    rebuild_manifest = json.loads(
        (
            handoff_dir / "rebuild" / "prepared_handoff_rebuild.v1.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["schema_version"] == "scion.prepared_handoff_rebuild.v1"
    assert manifest["complete"] is True
    assert rebuild_manifest["complete"] is True
    assert brief["phase4_evidence_coverage"]["problem_specific_requirements"][
        "cvrp_default_avoid_handoff"
    ]["available"] is True
    assert inventory["phase4_evidence_coverage"]["problem_specific_requirements"][
        "cvrp_direct_effect_rules_handoff"
    ]["available"] is True


def _cvrp_research_focus() -> dict[str, object]:
    return {
        "schema_version": "scion.cvrp_research_focus.v1",
        "scope": "report_only_prepared_handoff",
        "measurement_opportunity_diagnostics": {
            "schema_version": "cvrp_measurement_opportunity_handoff.v1",
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
            "practical_screen_delta": 2.0,
            "screening_mde_at_power_80": 9.9,
            "reason_codes": [
                "CVRP_MDE_EXCEEDS_PRACTICAL_DELTA",
                "TRAJECTORY_DIVERGENT_LOW_SNR",
            ],
        },
        "measurable_opportunity_classes": [
            "construction_seed_portfolio",
            "destroy_repair_selection",
            "bounded_local_search_variant",
            "acceptance_or_adaptive_weighting",
        ],
        "default_avoid_directions": [
            "unchanged broad VNS removal",
            "pure ALNS/no-polish",
            "simple initial-VNS disablement",
            "raw cadence-2",
            "tested share70 cap/rescue variants",
            "route-merge absorption",
            "demand-slack regret insertion",
            "cross-route 2-opt reconnect",
            "cluster-biased worst removal",
            "route-limit seed diversification",
        ],
        "route_merge_exception_rule": (
            "Only continue route_merge_repair with direct objective evidence."
        ),
        "construction_seed_rule": (
            "Require same-run seed baseline or same-mechanism accepted delta."
        ),
        "decision_boundary": (
            "This focus must not enter DecisionFeatures, Protocol gates, "
            "promotion input, or scheduler state."
        ),
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _git_head_short() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"],
        text=True,
    ).strip()
