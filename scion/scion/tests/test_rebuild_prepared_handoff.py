from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

from scion.research_guidance import (
    legacy_research_focus_to_contract,
    research_guidance_contract_to_dict,
)
from scion.postrun.handoff import prompt_context_readiness


TOOL_PATH = Path(__file__).parents[2] / "tools" / "rebuild_prepared_handoff.py"
SPEC = importlib.util.spec_from_file_location("rebuild_prepared_handoff", TOOL_PATH)
assert SPEC is not None
rebuild_tool = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(rebuild_tool)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_rebuild_tool_delegates_prompt_context_readiness_to_package_module() -> None:
    assert (
        rebuild_tool.build_prepared_prompt_context_readiness
        is prompt_context_readiness.build_prepared_prompt_context_readiness
    )
    assert (
        rebuild_tool.render_prompt_context_readiness_markdown
        is prompt_context_readiness.render_prompt_context_readiness_markdown
    )


def test_rebuild_fails_closed_when_proposal_runtime_mode_is_unknown(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_root = tmp_path / "unknown-mode-prepared"
    run_root.mkdir()
    _write_json(
        run_root / "prepared_run_manifest.v1.json",
        {"execution": {}, "problem_family": "fixture"},
    )
    monkeypatch.setattr(
        rebuild_tool,
        "_write_family",
        lambda _paths, _writer: {"status": "ok", "artifacts": []},
    )

    result = rebuild_tool.rebuild_prepared_handoff(run_root)

    assert result["proposal_runtime"]["status"] == "invalid"
    assert result["proposal_runtime"]["resolved_mode"] is None
    assert result["proposal_runtime"]["fail_closed"] is True
    assert result["complete"] is False


def test_rebuild_prepared_handoff_refreshes_direct_v3_handoff(
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
        f"--campaign-dir {campaign_dir} --rounds 1 --time-limit-sec 30"
    )
    research_focus = _cvrp_research_focus()
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
            "research_focus": research_focus,
            "research_guidance_contract": research_guidance_contract_to_dict(
                legacy_research_focus_to_contract(
                    research_focus,
                    problem_family="cvrp",
                )
            ),
            "resume_from_campaign": "/tmp/source-campaign",
            "command": command,
            "execution": {
                "proposal_runtime_mode": "direct_v3",
                "rounds": 1,
                "time_limit_sec": 30,
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
    (run_root / "launch.env").write_text(
        f"PREPARED_RUN_MANIFEST={run_root / 'prepared_run_manifest.v1.json'}\n",
        encoding="utf-8",
    )
    (run_root / "run.sh").write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "source launch.env",
                "export PYTHONPATH SCION_MODEL PREPARED_RUN_MANIFEST",
                "python -m scion.cli.main run",
                "",
            ]
        ),
        encoding="utf-8",
    )
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
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "branches": [{"id": "branch-a"}],
            "proposal_accounting": {
                "last_prompt_manifest": "traces/branch-a/prompt_manifest.json",
            },
        },
    )
    _write_json(
        campaign_dir / "status.json",
        {
            "branches": [{"id": "branch-a"}],
            "proposal_accounting": {
                "last_code_prompt_manifest": (
                    "traces/branch-a/code_prompt_manifest.json"
                ),
            },
            "cross_branch_research_summary": {
                "schema_version": "cross_branch_research_summary.v1",
                "research_shape_diagnostics": {
                    "schema_version": "campaign_research_shape_diagnostics.v1",
                    "policy": "summary_status_observability_only",
                    "advisory_only": True,
                    "decision_features_excluded": True,
                    "decision_input_policy": "excluded_from_decision_features",
                    "max_branch_depth": 2,
                    "mean_branch_depth": 1.5,
                    "branch_depth_distribution": {"1": 1, "2": 1},
                    "mechanism_family_breadth": {
                        "family_count": 1,
                        "families": {"prepared_audit_family": 2},
                    },
                    "active_research_shape_signal": {
                        "shape": "low_followup_depth",
                        "active_branch_count": 1,
                        "active_mechanism_families": [
                            "prepared_audit_family"
                        ],
                    },
                },
            },
        },
    )
    stale = run_root / "prepared_handoff" / "analysis_brief" / (
        "cvrp_direct_v3.prepared_analysis_brief.v1.json"
    )
    _write_json(
        stale,
        {"phase4_evidence_coverage": {"problem_specific_requirements": {}}},
    )
    stale_prompt = (
        run_root
        / "prepared_handoff"
        / "prompt_context_readiness"
        / "zz_stale.prepared_prompt_context_readiness.v1.json"
    )
    _write_json(stale_prompt, {"schema_version": "stale.test"})
    stale_readiness_md = (
        run_root
        / "prepared_handoff"
        / "launch_readiness"
        / "zz_stale.prepared_launch_readiness.md"
    )
    stale_readiness_md.parent.mkdir(parents=True)
    stale_readiness_md.write_text("stale", encoding="utf-8")

    manifest = rebuild_tool.rebuild_prepared_handoff(
        run_root,
        report_stem="cvrp_direct_v3",
        strict=True,
    )

    handoff_dir = run_root / "prepared_handoff"
    brief = json.loads(stale.read_text(encoding="utf-8"))
    inventory = json.loads(
        (
            handoff_dir
            / "inventory"
            / "cvrp_direct_v3.prepared_artifact_inventory.v1.json"
        ).read_text(encoding="utf-8")
    )
    prompt_context = json.loads(
        (
            handoff_dir
            / "prompt_context_readiness"
            / "cvrp_direct_v3.prepared_prompt_context_readiness.v1.json"
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
    assert all(
        all(result["outputs_present"].values())
        for result in manifest["families"].values()
    )
    assert prompt_context["schema_version"] == (
        "scion.prepared_prompt_context_readiness.v1"
    )
    assert prompt_context["report_only"] is True
    assert prompt_context["raw_provider_prompt_rendered"] is False
    assert prompt_context["readiness"]["ready_for_launch_prompt_audit"] is True
    assert (
        prompt_context["signals"]["prepared_research_focus"]["available"] is True
    )
    assert (
        prompt_context["signals"]["copied_campaign_summary"]["available"] is True
    )
    assert prompt_context["signals"]["prompt_manifest_history"]["available"] is True
    projection = prompt_context["signals"]["prepared_research_focus_projection"]
    assert projection["available"] is True
    assert projection["required"] is True
    assert projection["runtime_generated_after_launch"] is False
    projection_detail = projection["detail"]
    assert projection_detail["schema_version"] == (
        "scion.prepared_research_focus_projection_summary.v1"
    )
    assert projection_detail["available"] is True
    assert projection_detail["raw_prompt_excluded"] is True
    assert projection_detail["decision_features_excluded"] is True
    assert projection_detail["contract_present"] is True
    assert projection_detail["schema_valid"] is True
    assert projection_detail["missing_rendered_paths"] == []
    assert (
        projection_detail["rendered_paths"]
        == projection_detail["expected_rendered_paths"]
    )
    assert not stale_prompt.exists()
    assert not stale_readiness_md.exists()
    assert not any("prompt_bridge" in name for name in prompt_context["signals"])
    assert (
        manifest["families"]["prompt_context_readiness"]["status"] == "ok"
    )


def test_rebuild_prompt_context_readiness_accepts_no_resume_without_copied_campaign(
    tmp_path: Path,
) -> None:
    run_root = _write_rebuild_fixture_root(
        tmp_path,
        problem_family="cvrp",
        report_stem="cvrp_direct_v3",
        research_focus=_cvrp_research_focus(),
        control_pair_key="cvrp.prepared:rep01",
        resume_from_campaign="",
    )
    (run_root / "campaign" / "campaign_summary.json").unlink()
    (run_root / "campaign" / "status.json").unlink()

    prompt_context = rebuild_tool.build_prepared_prompt_context_readiness(run_root)

    assert prompt_context["readiness"]["ready_for_launch_prompt_audit"] is True
    assert prompt_context["readiness"]["missing_required"] == []
    copied_summary = prompt_context["signals"]["copied_campaign_summary"]
    copied_status = prompt_context["signals"]["copied_campaign_status"]
    assert copied_summary["available"] is False
    assert copied_summary["required"] is False
    assert copied_summary["detail"]["resume_from_campaign"] == ""
    assert copied_status["available"] is False
    assert copied_status["required"] is False
    assert copied_status["detail"]["resume_from_campaign"] == ""


def test_rebuild_prompt_context_readiness_reads_resume_snapshot(
    tmp_path: Path,
) -> None:
    run_root = _write_rebuild_fixture_root(
        tmp_path,
        problem_family="cvrp",
        report_stem="cvrp_direct_v3",
        research_focus=_cvrp_research_focus(),
        control_pair_key="cvrp.prepared:rep01",
        resume_from_campaign="/tmp/source-campaign",
    )
    campaign_dir = run_root / "campaign"
    snapshot_dir = run_root / "resume_snapshot" / "campaign"
    snapshot_dir.mkdir(parents=True)
    for ref in ("campaign_summary.json", "status.json"):
        (snapshot_dir / ref).write_text(
            (campaign_dir / ref).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (campaign_dir / ref).unlink()

    snapshot_manifest = run_root / "resume_snapshot" / "resume_source_manifest.v1.json"
    _write_json(
        snapshot_manifest,
        {
            "schema_version": "scion.launcher_resume_preparation.v1",
            "terminal_artifacts": [
                {
                    "original_ref": "campaign_summary.json",
                    "snapshot_ref": "resume_snapshot/campaign/campaign_summary.json",
                },
                {
                    "original_ref": "status.json",
                    "snapshot_ref": "resume_snapshot/campaign/status.json",
                },
            ],
        },
    )
    manifest_path = run_root / "prepared_run_manifest.v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["resume_snapshot_ref"] = (
        "resume_snapshot/resume_source_manifest.v1.json"
    )
    _write_json(manifest_path, manifest)

    prompt_context = rebuild_tool.build_prepared_prompt_context_readiness(run_root)

    assert prompt_context["readiness"]["ready_for_launch_prompt_audit"] is True
    assert prompt_context["readiness"]["missing_required"] == []
    copied_summary = prompt_context["signals"]["copied_campaign_summary"]
    copied_status = prompt_context["signals"]["copied_campaign_status"]
    assert copied_summary["available"] is True
    assert copied_summary["detail"]["source_kind"] == "resume_snapshot"
    assert copied_status["available"] is True
    assert copied_status["detail"]["source_kind"] == "resume_snapshot"


def test_rebuild_prepared_handoff_cli_uses_current_checkout_without_pythonpath(
    tmp_path: Path,
) -> None:
    run_root = _write_rebuild_fixture_root(
        tmp_path,
        problem_family="warehouse_delivery",
        report_stem="warehouse_direct_v3",
        research_focus=_warehouse_research_focus(),
        control_pair_key="warehouse.prepared:rep01",
    )
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [
            sys.executable,
            str(TOOL_PATH),
            str(run_root),
            "--report-stem",
            "warehouse_direct_v3",
            "--strict",
            "--format",
            "json",
        ],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    prompt_context = json.loads(
        (
            run_root
            / "prepared_handoff"
            / "prompt_context_readiness"
            / "warehouse_direct_v3.prepared_prompt_context_readiness.v1.json"
        ).read_text(encoding="utf-8")
    )
    projection = prompt_context["signals"]["prepared_research_focus_projection"]
    assert projection["available"] is True
    assert projection["detail"]["contract_source"] == "typed_manifest"
    assert not any("prompt_bridge" in name for name in prompt_context["signals"])


def _write_rebuild_fixture_root(
    tmp_path: Path,
    *,
    problem_family: str,
    report_stem: str,
    research_focus: dict[str, object],
    control_pair_key: str,
    resume_from_campaign: str = "/tmp/source-campaign",
) -> Path:
    run_root = tmp_path / f"{report_stem}-prepared-root"
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
        f"--campaign-dir {campaign_dir} --rounds 1 --time-limit-sec 30"
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
            "problem_family": problem_family,
            "analysis_intent": "Prepared handoff rebuild fixture.",
            "acceptance_focus": ["Keep handoff report-only."],
            "research_focus": research_focus,
            "research_guidance_contract": research_guidance_contract_to_dict(
                legacy_research_focus_to_contract(
                    research_focus,
                    problem_family=problem_family,
                )
            ),
            "resume_from_campaign": resume_from_campaign,
            "command": command,
            "execution": {
                "proposal_runtime_mode": "direct_v3",
                "rounds": 1,
                "time_limit_sec": 30,
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
                "control_pair_key": control_pair_key,
                "postrun_reports": True,
                "postrun_acceptance_families": [
                    "summaries",
                    "failures",
                    "research_efficiency",
                    "manifests",
                    "analysis_brief",
                    "inventory",
                    "readiness",
                    "rebuild",
                ],
            },
        },
    )
    (run_root / "prepared_run_manifest.md").write_text("# prepared\n", encoding="utf-8")
    (run_root / "launch.env").write_text(
        f"PREPARED_RUN_MANIFEST={run_root / 'prepared_run_manifest.v1.json'}\n",
        encoding="utf-8",
    )
    (run_root / "run.sh").write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "source launch.env",
                "export PYTHONPATH SCION_MODEL PREPARED_RUN_MANIFEST",
                "python -m scion.cli.main run",
                "",
            ]
        ),
        encoding="utf-8",
    )
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
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "branches": [{"id": "branch-a"}],
            "proposal_accounting": {
                "last_prompt_manifest": "traces/branch-a/prompt_manifest.json",
            },
        },
    )
    _write_json(
        campaign_dir / "status.json",
        {
            "branches": [{"id": "branch-a"}],
            "proposal_accounting": {
                "last_code_prompt_manifest": (
                    "traces/branch-a/code_prompt_manifest.json"
                ),
            },
            "cross_branch_research_summary": {
                "schema_version": "cross_branch_research_summary.v1",
                "research_shape_diagnostics": {
                    "schema_version": "campaign_research_shape_diagnostics.v1",
                    "policy": "summary_status_observability_only",
                    "advisory_only": True,
                    "decision_features_excluded": True,
                    "decision_input_policy": "excluded_from_decision_features",
                    "max_branch_depth": 2,
                    "mean_branch_depth": 1.5,
                    "branch_depth_distribution": {"1": 1, "2": 1},
                    "mechanism_family_breadth": {
                        "family_count": 1,
                        "families": {"prepared_audit_family": 2},
                    },
                    "active_research_shape_signal": {
                        "shape": "low_followup_depth",
                        "active_branch_count": 1,
                        "active_mechanism_families": [
                            "prepared_audit_family"
                        ],
                    },
                },
            },
        },
    )
    return run_root


def _cvrp_research_focus() -> dict[str, object]:
    return {
        "schema_version": "scion.cvrp_research_focus.v3",
        "scope": "report_only",
        "current_question": "Improve final total_distance within the CVRP-owned source boundary.",
        "decision_boundary": (
            "Proposal guidance only; Protocol and DecisionFeatures remain authoritative."
        ),
    }


def _warehouse_research_focus() -> dict[str, object]:
    return {
        "schema_version": "scion.warehouse_research_focus.v1",
        "scope": "report_only_prepared_handoff",
        "measurement_opportunity_diagnostics": {
            "schema_version": "warehouse_measurement_runtime_handoff.v1",
            "source": "problem_v1.measurement.calibration_ref",
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
            "metric": "total_cost",
            "unit": "raw_delta",
            "runtime_model": "comparative",
            "pairing_validity": "trajectory_divergent",
            "practical_screen_delta": 0.001,
            "practical_validate_delta": 0.001,
            "screening_mde_at_power_80": 577.5,
            "measurement_readiness": {
                "status": "ready",
                "reason_code": "ok",
                "calibration_age_days": 8,
                "calibration_max_age_days": 90,
                "n_pairs": 36,
                "mde_at_power_80": 577.5,
                "noise_band_p90_abs": 8500.0,
                "effect_to_mde_ratio": 1.7316017316017316e-06,
                "signal_to_noise_tier": "low_power",
                "decision_features_excluded": True,
                "calibration_ref": "calibration/aa_noise_floor.json",
            },
            "calibration": {
                "schema": "scion.aa_noise_floor.v1",
                "ref": "calibration/aa_noise_floor.json",
                "path": "/tmp/warehouse/calibration/aa_noise_floor.json",
                "calibrated_at": "2026-06-11T16:47:24.372634+00:00",
                "n_pairs": 36,
                "decision_features_excluded": True,
                "calibration_run_action": "modify",
            },
            "reason_codes": [
                "WAREHOUSE_MDE_EXCEEDS_PRACTICAL_DELTA",
                "TRAJECTORY_DIVERGENT_LOW_SNR",
                "WAREHOUSE_COMPARATIVE_RUNTIME_REPORT_ONLY",
            ],
            "opportunity_projection_source": (
                "problem_adapter.render_problem_measurement_diagnostics"
            ),
            "adapter_payload_schema": "warehouse_validation_transfer_diagnostic.v1",
            "transfer_risk": {
                "risk_model": "screening-positive changes can miss validation transfer",
                "historical_pattern": "screening positive but no hierarchical gain",
                "latest_field_gate_pattern": "cost-only compression can regress holdout",
                "latest_formal_no_gain_pattern": "validation no-gain plateau caveat",
                "required_hypothesis_claims": [
                    "why the mechanism transfers beyond screening",
                    "what activation counter becomes positive",
                ],
            },
            "required_diagnostics": {
                "activation": [
                    "operator_invocations",
                    "eligible_vehicle_or_order_groups_seen",
                    "accepted_moves",
                ],
                "effect": [
                    "split_delta_sum",
                    "cost_delta_sum",
                    "improving_move_count",
                ],
            },
            "measurable_opportunity_classes": [
                {
                    "mechanism_family": "validation_transfer_continuation",
                    "required_evidence": (
                        "bounded operator activation/effect evidence before plateau"
                    ),
                }
            ],
            "opportunity_diagnostics": [
                {
                    "diagnostic_type": "post_promotion_followup",
                    "surface": "warehouse_operator",
                    "mechanism_family": "validation_transfer_continuation",
                    "metric": "lexicographic_objective",
                    "summary": "champion-v2 follow-up must test continuous improvement",
                    "recommended_action": (
                        "require protocol-evaluated split/cost, runtime-feedback, "
                        "and branch-continuity evidence before plateau"
                    ),
                    "confidence": "medium",
                    "reason_codes": [
                        "WAREHOUSE_V2_FOLLOWUP_CONTINUOUS_RESEARCH",
                        "PLATEAU_REQUIRES_PROTOCOL_EVIDENCE",
                        "SCREENING_ONLY_NOT_PLATEAU_EVIDENCE",
                    ],
                }
            ],
            "policy": (
                "Use these diagnostics to shape warehouse proposals before "
                "code generation; they are not DecisionFeatures."
            ),
            "recommended_min_seeds": 4,
            "related_calibrations": [
                {
                    "action": "create_new",
                    "n_pairs": 60,
                    "mde_at_power_80": 1725.0,
                }
            ],
        },
        "accepted_checkpoint": "Champion v2 promoted.",
        "current_question": (
            "Can warehouse v2 plateau be advanced with one bounded follow-up?"
        ),
        "required_evidence": [
            "preserve promotion behavior",
            "branch transfer evidence",
            "quality-blocked and protocol-evaluated branches separated",
            "cost_delta and split_delta diagnostics exported",
            "fast completion runtime retained",
        ],
        "default_avoid_directions": [
            "restart from baseline",
            "proposal-quality only claims",
            "fast completion without current-run evidence",
            "accept split_delta_sum==0 as success",
            "broad warehouse matrix before v2 follow-up",
        ],
        "decision_boundary": (
            "Keep warehouse follow-up evidence out of DecisionFeatures, Protocol, "
            "promotion, and scheduler state."
        ),
    }


def _git_head_short() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"],
        text=True,
    ).strip()
