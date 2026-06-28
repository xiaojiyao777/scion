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


def test_rebuild_tool_delegates_prompt_context_readiness_to_package_module() -> None:
    assert (
        rebuild_tool.build_prepared_prompt_context_readiness
        is prompt_context_readiness.build_prepared_prompt_context_readiness
    )
    assert (
        rebuild_tool.render_prompt_context_readiness_markdown
        is prompt_context_readiness.render_prompt_context_readiness_markdown
    )


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
            "agentic_session_trace_index": {
                "sessions": [
                    {
                        "call_kind": "hypothesis",
                        "prompt_manifest": "traces/branch-a/prompt_manifest.json",
                    }
                ]
            },
            "branches": [{"id": "branch-a"}],
            "proposal_accounting": {
                "last_prompt_manifest": "traces/branch-a/prompt_manifest.json",
            },
        },
    )
    _write_json(
        campaign_dir / "status.json",
        {
            "agentic_session_trace_index": {
                "sessions": [
                    {
                        "call_kind": "code",
                        "prompt_manifest_path": "traces/branch-a/code_prompt_manifest.json",
                    }
                ]
            },
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
        "cvrp_on_full.prepared_analysis_brief.v1.json"
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
    prompt_context = json.loads(
        (
            handoff_dir
            / "prompt_context_readiness"
            / "cvrp_on_full.prepared_prompt_context_readiness.v1.json"
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
    assert brief["phase4_evidence_coverage"]["problem_specific_requirements"][
        "cvrp_default_avoid_handoff"
    ]["available"] is True
    assert inventory["phase4_evidence_coverage"]["problem_specific_requirements"][
        "cvrp_direct_effect_rules_handoff"
    ]["available"] is True
    assert inventory["phase4_evidence_coverage"]["problem_specific_requirements"][
        "cvrp_large_twoopt_bounded_constraints_handoff"
    ]["available"] is True
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
    assert (
        prompt_context["signals"]["research_shape_prompt_signal"]["available"] is True
    )
    shape_detail = prompt_context["signals"]["research_shape_prompt_signal"]["detail"]
    shape_summary = shape_detail["prompt_summary"]
    assert shape_detail["markers"] == {
        "context_builder": True,
        "prompt_renderer": True,
        "shape_builder": True,
    }
    assert shape_summary["schema_version"] == (
        "scion.prepared_research_shape_prompt_summary.v1"
    )
    assert shape_summary["available"] is True
    assert shape_summary["report_only"] is True
    assert shape_summary["decision_features_excluded"] is True
    assert shape_summary["raw_prompt_excluded"] is True
    assert shape_summary["copied_campaign_payload_present"] is True
    assert shape_summary["payload_source"] == "copied_campaign_status"
    assert shape_summary["payload_schema_version"] == (
        "campaign_research_shape_diagnostics.v1"
    )
    assert shape_summary["prompt_section_present"] is True
    assert shape_summary["compact_prompt_value_present"] is True
    assert shape_summary["research_shape_key_present"] is True
    assert shape_summary["payload_schema_present"] is True
    assert shape_summary["branch_depth_signal_present"] is True
    assert shape_summary["mechanism_family_signal_present"] is True
    assert shape_summary["shape_guidance_present"] is True
    assert shape_summary["decision_features_exclusion_present"] is True
    assert shape_summary["forbidden_prompt_tokens_present"] == []
    assert (
        prompt_context["signals"]["prepared_research_focus_prompt_bridge"][
            "available"
        ]
        is True
    )
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
    case_protection = prompt_context["signals"]["cvrp_case_protection_requirements"]
    assert case_protection["available"] is True
    assert case_protection["required"] is True
    assert case_protection["detail"]["protected_cases"] == ["CMT2", "CMT4"]
    resume_continuity = prompt_context["signals"][
        "cvrp_resume_continuity_requirements"
    ]
    assert resume_continuity["available"] is True
    assert resume_continuity["required"] is True
    assert resume_continuity["detail"]["fallback_source_count"] == 3
    assert not stale_prompt.exists()
    assert not stale_readiness_md.exists()
    assert (
        prompt_context["signals"]["prepared_research_focus_prompt_bridge"][
            "required"
        ]
        is True
    )
    bridge_detail = prompt_context["signals"][
        "prepared_research_focus_prompt_bridge"
    ]["detail"]
    assert bridge_detail["source_markers"] == {
        "context_payload": True,
        "manifest_env_reader": True,
        "prompt_renderer": True,
    }
    assert bridge_detail["launch_markers"] == {
        "launch_env_assignment": True,
        "prepared_manifest_exists": True,
        "run_sh_exports_manifest": True,
    }
    prompt_summary = bridge_detail["prompt_summary"]
    assert prompt_summary["schema_version"] == (
        "scion.prepared_research_focus_prompt_summary.v1"
    )
    assert prompt_summary["available"] is True
    assert prompt_summary["report_only"] is True
    assert prompt_summary["decision_features_excluded"] is True
    assert prompt_summary["raw_prompt_excluded"] is True
    assert prompt_summary["launch_focus_schema_present"] is True
    assert prompt_summary["launch_focus_taint_present"] is True
    assert prompt_summary["prompt_section_present"] is True
    assert prompt_summary["compact_prompt_value_present"] is True
    assert prompt_summary["launch_research_focus_key_present"] is True
    assert prompt_summary["contract_present"] is True
    assert prompt_summary["schema_valid"] is True
    assert prompt_summary["guidance_text_digest_present"] is True
    assert prompt_summary["missing_rendered_paths"] == []
    assert prompt_summary["forbidden_prompt_tokens_present"] == []
    code_bridge = prompt_context["signals"][
        "cvrp_active_subject_code_constraints_prompt_bridge"
    ]
    assert code_bridge["available"] is True
    assert code_bridge["required"] is True
    assert code_bridge["runtime_generated_after_launch"] is False
    assert code_bridge["detail"]["source_markers"] == {
        "code_prompt_renderer": True,
        "context_key": True,
        "context_provider_payload": True,
    }
    assert code_bridge["detail"]["provider_markers"] == {
        "large_twoopt_runtime_guard": True,
        "provider_hook": True,
        "unbounded_twoopt_reject": True,
    }
    provider_payload = code_bridge["detail"]["provider_payload"]
    assert provider_payload["schema_version"] == (
        "scion.active_subject_code_constraints_provider_payload_summary.v1"
    )
    assert provider_payload["available"] is True
    assert provider_payload["version"] == "cvrp_solver_design_code_constraints.v1"
    assert provider_payload["constraint_count"] == 2
    assert provider_payload["forbidden_pattern_count"] >= 1
    assert provider_payload["decision_features_excluded"] is True
    assert provider_payload["raw_payload_excluded"] is True
    code_summary = code_bridge["detail"]["code_prompt_summary"]
    assert code_summary["schema_version"] == (
        "scion.active_subject_code_constraints_prompt_summary.v1"
    )
    assert code_summary["available"] is True
    assert code_summary["report_only"] is True
    assert code_summary["decision_features_excluded"] is True
    assert code_summary["raw_payload_excluded"] is True
    assert code_summary["problem_family"] == "cvrp"
    assert code_summary["surface"] == "solver_design"
    assert code_summary["payload_version"] == "cvrp_solver_design_code_constraints.v1"
    assert code_summary["subject_id"] == "cvrp.solver_design.active_baseline"
    assert code_summary["prompt_section_present"] is True
    assert code_summary["compact_prompt_value_present"] is True
    assert code_summary["payload_version_present"] is True
    assert code_summary["subject_id_present"] is True
    assert code_summary["surface_present"] is True
    assert code_summary["decision_features_exclusion_present"] is True
    assert code_summary["constraint_count"] == 2
    assert code_summary["constraint_id_rendered_count"] == 2
    assert code_summary["constraint_ids_all_present"] is True
    assert code_summary["api_contract_count"] == 2
    assert code_summary["api_contract_ids_all_present"] is True
    assert code_summary["forbidden_pattern_count"] >= 1
    assert code_summary["forbidden_patterns_all_present"] is True
    assert code_summary["large_twoopt_runtime_guard_present"] is True
    assert code_summary["unbounded_twoopt_reject_present"] is True
    diagnostic_bridge = prompt_context["signals"][
        "cvrp_problem_measurement_diagnostics_prompt_bridge"
    ]
    assert diagnostic_bridge["available"] is True
    assert diagnostic_bridge["required"] is True
    assert diagnostic_bridge["runtime_generated_after_launch"] is False
    assert diagnostic_bridge["detail"]["source_markers"] == {
        "adapter_hook": True,
        "context_payload": True,
        "profile_projection": True,
        "prompt_renderer": True,
    }
    diagnostic_summary = diagnostic_bridge["detail"]["diagnostic_summary"]
    assert diagnostic_summary["schema_version"] == (
        "scion.problem_measurement_diagnostics_prompt_summary.v1"
    )
    assert diagnostic_summary["available"] is True
    assert diagnostic_summary["report_only"] is True
    assert diagnostic_summary["decision_features_excluded"] is True
    assert diagnostic_summary["raw_payload_excluded"] is True
    assert diagnostic_summary["raw_prompt_excluded"] is True
    assert diagnostic_summary["adapter_schema_present"] is True
    assert diagnostic_summary["prompt_section_present"] is True
    assert diagnostic_summary["screening_headroom_present"] is True
    assert diagnostic_summary["measurable_opportunity_classes_present"] is True
    assert diagnostic_summary["mechanism_effect_ranking_present"] is True
    assert diagnostic_summary["highest_current_followup_present"] is False
    assert diagnostic_summary["highest_current_successor_present"] is False
    assert diagnostic_summary["successor_rotation_direction_present"] is True
    assert diagnostic_summary["highest_current_rank_signal_present"] is True
    assert diagnostic_summary["mechanism_rank_count"] >= 1
    assert diagnostic_summary["forbidden_prompt_tokens_present"] == []
    assert (
        prompt_context["signals"]["cvrp_measurement_opportunity_handoff"][
            "available"
        ]
        is True
    )
    measurement_signal = prompt_context["signals"]["cvrp_measurement_opportunity_handoff"]
    assert measurement_signal["detail"]["screening_headroom_present"] is True
    assert measurement_signal["detail"]["mechanism_rank_count"] == 1
    assert measurement_signal["detail"]["opportunity_diagnostic_count"] == 1
    assert (
        prompt_context["signals"]["cvrp_large_twoopt_bounded_constraints"][
            "available"
        ]
        is True
    )
    assert (
        manifest["families"]["prompt_context_readiness"]["status"] == "ok"
    )


def test_rebuild_prepared_handoff_adds_warehouse_code_constraint_bridge(
    tmp_path: Path,
) -> None:
    run_root = _write_rebuild_fixture_root(
        tmp_path,
        problem_family="warehouse_delivery",
        report_stem="warehouse_on_full",
        research_focus=_warehouse_research_focus(),
        control_pair_key="warehouse.prepared:rep01",
    )

    manifest = rebuild_tool.rebuild_prepared_handoff(
        run_root,
        report_stem="warehouse_on_full",
        strict=True,
    )

    prompt_context = json.loads(
        (
            run_root
            / "prepared_handoff"
            / "prompt_context_readiness"
            / "warehouse_on_full.prepared_prompt_context_readiness.v1.json"
        ).read_text(encoding="utf-8")
    )
    code_bridge = prompt_context["signals"][
        "warehouse_active_subject_code_constraints_prompt_bridge"
    ]
    diagnostic_bridge = prompt_context["signals"][
        "warehouse_problem_measurement_diagnostics_prompt_bridge"
    ]

    assert manifest["complete"] is True
    assert prompt_context["problem_family"] == "warehouse_delivery"
    focus_bridge = prompt_context["signals"]["prepared_research_focus_prompt_bridge"]
    focus_summary = focus_bridge["detail"]["prompt_summary"]
    assert focus_bridge["available"] is True
    assert focus_summary["schema_version"] == (
        "scion.prepared_research_focus_prompt_summary.v1"
    )
    assert focus_summary["available"] is True
    assert focus_summary["report_only"] is True
    assert focus_summary["decision_features_excluded"] is True
    assert focus_summary["raw_prompt_excluded"] is True
    assert focus_summary["launch_focus_schema_present"] is True
    assert focus_summary["launch_focus_taint_present"] is True
    assert focus_summary["prompt_section_present"] is True
    assert focus_summary["compact_prompt_value_present"] is True
    assert focus_summary["launch_research_focus_key_present"] is True
    assert focus_summary["contract_present"] is True
    assert focus_summary["schema_valid"] is True
    assert focus_summary["guidance_text_digest_present"] is True
    assert focus_summary["missing_rendered_paths"] == []
    assert focus_summary["forbidden_prompt_tokens_present"] == []
    measurement_signal = prompt_context["signals"][
        "warehouse_measurement_runtime_handoff"
    ]
    assert measurement_signal["available"] is True
    assert measurement_signal["detail"]["transfer_risk_present"] is True
    assert measurement_signal["detail"]["required_diagnostics_present"] is True
    assert measurement_signal["detail"]["measurable_opportunity_count"] == 1
    assert measurement_signal["detail"]["opportunity_diagnostic_count"] == 1
    assert diagnostic_bridge["available"] is True
    assert diagnostic_bridge["required"] is True
    assert diagnostic_bridge["runtime_generated_after_launch"] is False
    assert diagnostic_bridge["detail"]["source_markers"] == {
        "adapter_hook": True,
        "context_payload": True,
        "profile_projection": True,
        "prompt_renderer": True,
    }
    diagnostic_summary = diagnostic_bridge["detail"]["diagnostic_summary"]
    assert diagnostic_summary["schema_version"] == (
        "scion.problem_measurement_diagnostics_prompt_summary.v1"
    )
    assert diagnostic_summary["available"] is True
    assert diagnostic_summary["report_only"] is True
    assert diagnostic_summary["decision_features_excluded"] is True
    assert diagnostic_summary["raw_payload_excluded"] is True
    assert diagnostic_summary["raw_prompt_excluded"] is True
    assert diagnostic_summary["adapter_schema_present"] is True
    assert diagnostic_summary["prompt_section_present"] is True
    assert diagnostic_summary["warehouse_transfer_risk_present"] is True
    assert diagnostic_summary["warehouse_required_diagnostics_present"] is True
    assert diagnostic_summary["warehouse_followup_opportunity_present"] is True
    assert diagnostic_summary["warehouse_plateau_guard_present"] is True
    assert diagnostic_summary["warehouse_v2_followup_present"] is True
    assert diagnostic_summary["opportunity_diagnostic_count"] >= 1
    assert diagnostic_summary["forbidden_prompt_tokens_present"] == []
    assert code_bridge["available"] is True
    assert code_bridge["required"] is True
    assert code_bridge["runtime_generated_after_launch"] is False
    assert code_bridge["detail"]["source_markers"] == {
        "code_prompt_renderer": True,
        "context_key": True,
        "context_provider_payload": True,
    }
    assert code_bridge["detail"]["provider_markers"] == {
        "bounded_scan_guard": True,
        "diagnostics_contract": True,
        "lexicographic_guard": True,
        "provider_hook": True,
    }
    provider_payload = code_bridge["detail"]["provider_payload"]
    assert provider_payload["schema_version"] == (
        "scion.active_subject_code_constraints_provider_payload_summary.v1"
    )
    assert provider_payload["available"] is True
    assert (
        provider_payload["version"]
        == "warehouse_operator_validation_transfer_code_constraints.v1"
    )
    assert provider_payload["constraint_count"] >= 3
    assert provider_payload["forbidden_pattern_count"] >= 1
    assert provider_payload["decision_features_excluded"] is True
    assert provider_payload["raw_payload_excluded"] is True
    code_summary = code_bridge["detail"]["code_prompt_summary"]
    assert code_summary["schema_version"] == (
        "scion.active_subject_code_constraints_prompt_summary.v1"
    )
    assert code_summary["available"] is True
    assert code_summary["report_only"] is True
    assert code_summary["decision_features_excluded"] is True
    assert code_summary["raw_payload_excluded"] is True
    assert code_summary["problem_family"] == "warehouse_delivery"
    assert code_summary["surface"] == "order_level"
    assert (
        code_summary["payload_version"]
        == "warehouse_operator_validation_transfer_code_constraints.v1"
    )
    assert (
        code_summary["subject_id"]
        == "warehouse_delivery.operator.validation_transfer"
    )
    assert code_summary["prompt_section_present"] is True
    assert code_summary["compact_prompt_value_present"] is True
    assert code_summary["payload_version_present"] is True
    assert code_summary["subject_id_present"] is True
    assert code_summary["surface_present"] is True
    assert code_summary["decision_features_exclusion_present"] is True
    assert code_summary["constraint_count"] >= 3
    assert code_summary["constraint_ids_all_present"] is True
    assert code_summary["forbidden_pattern_count"] >= 1
    assert code_summary["forbidden_patterns_all_present"] is True
    assert code_summary["warehouse_validation_transfer_diagnostics_present"] is True
    assert code_summary["warehouse_lexicographic_guard_present"] is True


def test_rebuild_prompt_context_readiness_accepts_no_resume_without_copied_campaign(
    tmp_path: Path,
) -> None:
    run_root = _write_rebuild_fixture_root(
        tmp_path,
        problem_family="cvrp",
        report_stem="cvrp_on_full",
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
        report_stem="cvrp_on_full",
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
    shape_detail = prompt_context["signals"]["research_shape_prompt_signal"]["detail"]
    assert shape_detail["prompt_summary"]["payload_source"] == "copied_campaign_status"


def test_rebuild_prepared_handoff_cli_uses_current_checkout_without_pythonpath(
    tmp_path: Path,
) -> None:
    run_root = _write_rebuild_fixture_root(
        tmp_path,
        problem_family="warehouse_delivery",
        report_stem="warehouse_on_full",
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
            "warehouse_on_full",
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
            / "warehouse_on_full.prepared_prompt_context_readiness.v1.json"
        ).read_text(encoding="utf-8")
    )
    provider_payload = prompt_context["signals"][
        "warehouse_active_subject_code_constraints_prompt_bridge"
    ]["detail"]["provider_payload"]
    assert provider_payload["available"] is True
    assert (
        provider_payload["version"]
        == "warehouse_operator_validation_transfer_code_constraints.v1"
    )
    assert provider_payload["constraint_count"] >= 3
    assert provider_payload["forbidden_pattern_count"] >= 1
    code_summary = prompt_context["signals"][
        "warehouse_active_subject_code_constraints_prompt_bridge"
    ]["detail"]["code_prompt_summary"]
    assert code_summary["available"] is True
    assert code_summary["warehouse_validation_transfer_diagnostics_present"] is True
    assert code_summary["warehouse_lexicographic_guard_present"] is True


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
            "agentic_session_trace_index": {
                "sessions": [
                    {
                        "call_kind": "hypothesis",
                        "prompt_manifest": "traces/branch-a/prompt_manifest.json",
                    }
                ]
            },
            "branches": [{"id": "branch-a"}],
            "proposal_accounting": {
                "last_prompt_manifest": "traces/branch-a/prompt_manifest.json",
            },
        },
    )
    _write_json(
        campaign_dir / "status.json",
        {
            "agentic_session_trace_index": {
                "sessions": [
                    {
                        "call_kind": "code",
                        "prompt_manifest_path": (
                            "traces/branch-a/code_prompt_manifest.json"
                        ),
                    }
                ]
            },
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
        "schema_version": "scion.cvrp_research_focus.v1",
        "scope": "report_only_prepared_handoff",
        "next_required_direction": (
            "First attempt large_instance_intra_route_two_opt_seed."
        ),
        "required_mechanism_ids": [
            "large_instance_intra_route_two_opt_seed",
        ],
        "measurement_opportunity_diagnostics": {
            "schema_version": "cvrp_measurement_opportunity_handoff.v1",
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
            "practical_screen_delta": 2.0,
            "screening_mde_at_power_80": 9.9,
            "opportunity_projection_source": (
                "problem_adapter.render_problem_measurement_diagnostics"
            ),
            "adapter_payload_schema": "cvrp_measurement_opportunity_diagnostic.v1",
            "screening_headroom": {
                "scope": "formal_screening_aggregate",
                "metric": "distance_gap_pct_to_reference",
                "case_count": 16,
                "gap_pct_min": 2.5,
                "gap_pct_max": 10.0,
                "case_count_gap_pct_at_least_3": 12,
                "case_details_omitted": True,
                "planning_use": "proposal-only screening headroom",
            },
            "measurable_opportunity_classes": [
                {
                    "mechanism_family": "large_instance_intra_route_two_opt_seed",
                    "required_evidence": "bounded direct objective-effect evidence",
                    "reason_codes": ["BOUNDED_DEADLINE_REQUIRED"],
                }
            ],
            "mechanism_effect_ranking": [
                {
                    "rank": 1,
                    "mechanism_family": "large_instance_intra_route_two_opt_seed",
                    "opportunity_status": "highest_current_followup",
                    "summary": "strongest current proposal seed",
                    "recommended_action": "use bounded deadline-aware two-opt",
                    "reason_codes": ["CVRP_LARGE_INSTANCE_TWO_OPT_SEED"],
                }
            ],
            "opportunity_diagnostics": [
                {
                    "diagnostic_type": "measurement_power",
                    "surface": "solver_design",
                    "mechanism_family": "all",
                    "metric": "total_distance",
                    "summary": "low-SNR proposal-only guidance",
                    "recommended_action": "prefer direct objective-effect evidence",
                    "confidence": "high",
                    "reason_codes": ["CVRP_MDE_EXCEEDS_PRACTICAL_DELTA"],
                }
            ],
            "reason_codes": [
                "CVRP_MDE_EXCEEDS_PRACTICAL_DELTA",
                "TRAJECTORY_DIVERGENT_LOW_SNR",
                "BUDGET_EXHAUSTING_RUNTIME_REPORT_ONLY",
            ],
        },
        "measurable_opportunity_classes": [
            "construction_seed_portfolio",
            "destroy_repair_selection",
            "bounded_local_search_variant",
            "large_instance_intra_route_two_opt_seed",
            "acceptance_or_adaptive_weighting",
        ],
        "default_avoid_directions": [
            "unchanged broad VNS removal",
            "pure ALNS/no-polish",
            "simple initial-VNS disablement",
            "unbounded large-instance two-opt fallback without deadline or wall-clock evidence",
            "raw cadence-2",
            "tested share70 cap/rescue variants",
            "route-merge absorption",
            "demand-slack regret insertion",
            "cross-route 2-opt reconnect",
            "cluster-biased worst removal",
            "route-limit seed diversification",
        ],
        "large_instance_two_opt_constraints": _large_twoopt_constraints(),
        "case_protection_requirements": _cmt_case_protection_requirements(),
        "resume_continuity_requirements": _resume_continuity_requirements(),
        "route_merge_exception_rule": (
            "Only continue route_merge_repair when the proposal names a causal "
            "path beyond tested variants and defines direct activation-to-objective-effect evidence."
        ),
        "construction_seed_rule": (
            "Require same-run seed baseline or same-mechanism accepted delta "
            "for construction seed objective-effect claims."
        ),
        "missing_primary_telemetry_rule": (
            "If telemetry says the declared primary mechanism is "
            "not_evaluated/not_triggered or missing, treat weak_positive "
            "sparse two-opt feedback as missing primary mechanism telemetry; "
            "do not continue without active large_instance_intra_route_two_opt_seed "
            "evidence."
        ),
        "decision_boundary": (
            "This focus must not enter DecisionFeatures, Protocol gates, "
            "promotion input, or scheduler state."
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


def _large_twoopt_constraints() -> dict[str, object]:
    return {
        "schema_version": "scion.cvrp_large_instance_two_opt_constraints.v1",
        "scope": "proposal_only_prepared_handoff",
        "seed_report": (
            "scion/docs/experiments/v0.4/"
            "v04-vrp-large-instance-two-opt-seed-evidence-20260618.md"
        ),
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
        "implementation_constraints": [
            "derive a deadline from the solver time_limit and monotonic start time",
            "check wall-clock remaining time before each route and sweep",
            "do not call unbounded two_opt_intra above the vns_threshold",
        ],
        "required_pair_evidence": [
            "total_distance delta by case and seed",
            "feasibility before and after",
            "route count before and after",
            "wall-clock elapsed status",
        ],
        "default_reject_directions": [
            "unbounded two_opt_intra fallback",
            "activation claims without wall-clock evidence",
        ],
    }


def _cmt_case_protection_requirements() -> dict[str, object]:
    return {
        "schema_version": "scion.cvrp_case_protection_requirements.v1",
        "scope": "proposal_only_prepared_handoff",
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
        "protected_cases": ["CMT2", "CMT4"],
        "rules": [
            "Target intent or hypothesis must name the CMT2/CMT4 protection plan.",
            "Same-branch follow-up should keep CMT2 and CMT4 in formal coverage.",
        ],
        "required_evidence": [
            "live target-intent or hypothesis trace mentions CMT2/CMT4 protection",
            "case-level total_distance deltas for CMT2 and CMT4",
        ],
    }


def _resume_continuity_requirements() -> dict[str, object]:
    return {
        "schema_version": "scion.cvrp_resume_continuity_requirements.v1",
        "scope": "proposal_only_prepared_handoff",
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
        "fallback_sources": [
            "prepared_research_focus",
            "copied_agentic_session_trace_index",
            "copied_target_intent_or_hypothesis_traces",
        ],
        "rules": [
            (
                "A sparse resume with zero branch cards must use copied "
                "target-intent or hypothesis traces before treating the run "
                "as empty."
            ),
            (
                "First CVRP branch must continue bounded large-instance "
                "two-opt with CMT2/CMT4 protection or name a different "
                "problem-owned causal path."
            ),
        ],
        "required_evidence": [
            (
                "live hypothesis references copied target-intent or "
                "hypothesis evidence when branch cards are absent"
            ),
            "branch-continuity caveat is recorded if copied branch cards remain absent",
        ],
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _git_head_short() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"],
        text=True,
    ).strip()
