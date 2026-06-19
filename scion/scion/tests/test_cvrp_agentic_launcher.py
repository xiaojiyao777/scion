import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


SCION_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
LAUNCHER = SCION_DIR / "tools" / "launch_cvrp_agentic_campaign.py"


def _load_launcher_module():
    spec = importlib.util.spec_from_file_location("cvrp_agentic_launcher", LAUNCHER)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cvrp_agentic_launcher_help() -> None:
    result = subprocess.run(
        [sys.executable, str(LAUNCHER), "--help"],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "--rounds" in result.stdout
    assert "--launch" in result.stdout
    assert "--base-url" in result.stdout
    assert "--api-key" in result.stdout
    assert "--api-key-env" in result.stdout
    assert "--completion-preflight" in result.stdout
    assert "--skip-postrun-reports" in result.stdout
    assert "--python" in result.stdout
    assert "--problem" in result.stdout
    assert "--protocol" in result.stdout
    assert "--split" in result.stdout
    assert "--seeds" in result.stdout
    assert "--measurement-governance" in result.stdout
    assert "--proposal-context-ablation" in result.stdout
    assert "--control-pair-key" in result.stdout
    assert "--agentic-tool-max-steps" in result.stdout
    assert "--agentic-tool-max-calls" in result.stdout
    assert "--agentic-code-tool-max-calls" in result.stdout
    assert "--agentic-observation-max-chars" in result.stdout
    assert "--proposal-attempt-limit" in result.stdout
    assert "--proposal-quality-loop-limit" in result.stdout
    assert "--stage-transition-drain-limit" in result.stdout
    assert "--resume-from-campaign" in result.stdout


def test_cvrp_agentic_launcher_prepare_writes_run_files(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "4",
            "--label",
            "unit-cvrp",
            "--experiments-root",
            str(tmp_path),
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
        check=True,
    )

    run_root_line = next(
        line for line in result.stdout.splitlines() if line.startswith("RUN_ROOT=")
    )
    run_root = Path(run_root_line.removeprefix("RUN_ROOT="))

    assert run_root.parent == tmp_path
    assert run_root.name.startswith("unit-cvrp-4r-gpt55-")
    assert (run_root / "campaign").is_dir()
    assert not (run_root / "pid").exists()
    prepare_status = json.loads(
        (run_root / "run_status.json").read_text(encoding="utf-8")
    )
    assert prepare_status["schema"] == "scion.launcher_prepare.v1"
    assert prepare_status["status"] == "prepared"
    assert prepare_status["prepared_only"] is True
    assert prepare_status["campaign_dir"] == str(run_root / "campaign")
    assert prepare_status["resume_from_campaign"] == ""
    assert prepare_status["copied_campaign_status_present"] is False
    assert prepare_status["completion_preflight"] is False
    assert prepare_status["postrun_reports"] is True
    assert prepare_status["agentic_session_timeout_sec"] == 3600
    assert prepare_status["agentic_tool_max_steps"] == 240
    assert prepare_status["agentic_tool_max_calls"] == 200
    assert prepare_status["agentic_code_tool_max_calls"] == 200
    assert prepare_status["agentic_observation_max_chars"] == 2000000
    assert prepare_status["proposal_attempt_limit"] == 64
    assert prepare_status["proposal_quality_loop_limit"] == 64

    launch_env = (run_root / "launch.env").read_text(encoding="utf-8")
    prepared_manifest = json.loads(
        (run_root / "prepared_run_manifest.v1.json").read_text(encoding="utf-8")
    )
    prepared_manifest_md = (run_root / "prepared_run_manifest.md").read_text(
        encoding="utf-8"
    )
    assert prepared_manifest["schema_version"] == (
        "scion.launcher_prepared_run_manifest.v1"
    )
    assert prepared_manifest["report_only"] is True
    assert prepared_manifest["decision_features_excluded"] is True
    assert prepared_manifest["problem_family"] == "cvrp"
    assert prepared_manifest["research_focus"]["scope"] == (
        "report_only_prepared_handoff"
    )
    assert "route-merge absorption" in prepared_manifest["research_focus"][
        "default_avoid_directions"
    ]
    assert any(
        "unbounded large-instance two-opt fallback" in item
        for item in prepared_manifest["research_focus"]["default_avoid_directions"]
    )
    measurement = prepared_manifest["research_focus"][
        "measurement_opportunity_diagnostics"
    ]
    assert measurement["screening_mde_at_power_80"] == 9.9
    assert measurement["practical_screen_delta"] == 2.0
    assert measurement["source"] == "problem_v1.measurement.calibration_ref"
    assert measurement["calibration"]["schema"] == "scion.aa_noise_floor.v1"
    assert measurement["calibration"]["decision_features_excluded"] is True
    assert measurement["measurement_readiness"]["status"] == "ready"
    assert "CVRP_MDE_EXCEEDS_PRACTICAL_DELTA" in measurement["reason_codes"]
    assert any(
        "construction_seed_portfolio" in item
        for item in prepared_manifest["research_focus"][
            "measurable_opportunity_classes"
        ]
    )
    assert "large-instance intra-route two-opt seed" in prepared_manifest[
        "research_focus"
    ]["current_question"]
    assert any(
        "large_instance_intra_route_two_opt_seed" in item
        and "deadline-aware bounded search effort" in item
        and "v04-vrp-large-instance-two-opt-seed-evidence-20260618.md" in item
        for item in prepared_manifest["research_focus"][
            "measurable_opportunity_classes"
        ]
    )
    large_twoopt = prepared_manifest["research_focus"][
        "large_instance_two_opt_constraints"
    ]
    assert large_twoopt["schema_version"] == (
        "scion.cvrp_large_instance_two_opt_constraints.v1"
    )
    assert large_twoopt["proposal_visibility_only"] is True
    assert large_twoopt["decision_features_excluded"] is True
    assert "v04-vrp-large-instance-two-opt-seed-evidence-20260618.md" in (
        large_twoopt["seed_report"]
    )
    assert any(
        "deadline" in item and "wall-clock" in item
        for item in large_twoopt["implementation_constraints"]
    )
    assert any(
        "two_opt_intra" in item and "unbounded" in item
        for item in large_twoopt["implementation_constraints"]
    )
    assert any(
        "total_distance" in item for item in large_twoopt["required_pair_evidence"]
    )
    assert any(
        "activation" in item for item in large_twoopt["default_reject_directions"]
    )
    assert "DecisionFeatures" in prepared_manifest["research_focus"][
        "decision_boundary"
    ]
    assert prepared_manifest["execution"]["rounds"] == 4
    assert prepared_manifest["execution"]["agentic_session_timeout_sec"] == 3600
    assert prepared_manifest["execution"]["agentic_tool_max_steps"] == 240
    assert prepared_manifest["execution"]["agentic_tool_max_calls"] == 200
    assert prepared_manifest["execution"]["agentic_code_tool_max_calls"] == 200
    assert (
        prepared_manifest["execution"]["agentic_observation_max_chars"]
        == 2000000
    )
    assert prepared_manifest["execution"]["proposal_attempt_limit"] == 64
    assert prepared_manifest["execution"]["proposal_quality_loop_limit"] == 64
    assert prepared_manifest["execution"]["stage_transition_drain_limit"] == 4
    assert prepared_manifest["config"]["problem"] == "scion/problems/cvrp/problem.yaml"
    assert prepared_manifest["report_metadata"]["postrun_acceptance_families"] == [
        "summaries",
        "failures",
        "research_efficiency",
        "manifests",
        "analysis_brief",
        "inventory",
        "readiness",
        "rebuild",
    ]
    assert prepared_manifest["report_metadata"]["prepared_handoff_dir"] == str(
        run_root / "prepared_handoff"
    )
    assert prepared_manifest["report_metadata"]["prepared_handoff_families"] == [
        "analysis_brief",
        "inventory",
        "prompt_context_readiness",
        "launch_readiness",
        "rebuild",
    ]
    assert (
        prepared_manifest["report_metadata"]["control_pair_key"]
        == "cvrp.unit-cvrp:prepared"
    )
    assert "SCION_API_KEY" not in json.dumps(prepared_manifest, sort_keys=True)
    assert "CVRP post-pivot" in prepared_manifest_md
    assert "## Current Research Focus" in prepared_manifest_md
    assert "screening_mde_at_power_80: 9.9" in prepared_manifest_md
    assert "CVRP_MDE_EXCEEDS_PRACTICAL_DELTA" in prepared_manifest_md
    assert "route-merge absorption" in prepared_manifest_md
    assert "large_instance_intra_route_two_opt_seed" in prepared_manifest_md
    assert "unbounded large-instance two-opt fallback" in prepared_manifest_md
    assert "Large-instance two-opt constraints" in prepared_manifest_md
    assert "two_opt_intra" in prepared_manifest_md
    assert f"SCION_DIR={SCION_DIR}" in launch_env
    assert f"PY={sys.executable}" in launch_env
    assert f"PYTHONPATH={SCION_DIR}" in launch_env
    assert f"SCION_PROBLEM_DATA_ROOT={PROJECT_ROOT / 'vrp'}" in launch_env
    assert "SCION_MODEL=gpt-5.5" in launch_env
    assert "SCION_BASE_URL=http://127.0.0.1:8080" in launch_env
    assert "SCION_API_KEY=pwd" in launch_env
    assert "SCION_API_KEY_ENV=''" in launch_env
    assert "COMPLETION_PREFLIGHT=0" in launch_env
    assert "POSTRUN_REPORTS=1" in launch_env
    assert (
        "GIT_RUNTIME_GUARD_PATHS="
        "'scion/scion :(exclude)scion/scion/tests "
        "scion/tools scion/problems/cvrp vrp'"
        in launch_env
    )
    assert "SCION_STAGE_TRANSITION_DRAIN_LIMIT=4" in launch_env
    assert "AGENTIC_SESSION_TIMEOUT_SEC=3600" in launch_env
    assert "AGENTIC_TOOL_MAX_STEPS=240" in launch_env
    assert "AGENTIC_TOOL_MAX_CALLS=200" in launch_env
    assert "AGENTIC_CODE_TOOL_MAX_CALLS=200" in launch_env
    assert "AGENTIC_OBSERVATION_MAX_CHARS=2000000" in launch_env
    assert "PROPOSAL_ATTEMPT_LIMIT=64" in launch_env
    assert "PROPOSAL_QUALITY_LOOP_LIMIT=64" in launch_env
    assert (
        f"PREPARED_RUN_MANIFEST={run_root / 'prepared_run_manifest.v1.json'}"
        in launch_env
    )
    assert "RESUME_FROM_CAMPAIGN=''" in launch_env
    assert "ROUNDS=4" in launch_env
    assert "PROBLEM=scion/problems/cvrp/problem.yaml" in launch_env
    assert "PROTOCOL=scion/problems/cvrp/formal/protocol.yaml" in launch_env
    assert "SPLIT=scion/problems/cvrp/formal/split_manifest.yaml" in launch_env
    assert "SEEDS=scion/problems/cvrp/formal/seed_ledger.yaml" in launch_env
    assert "MEASUREMENT_GOVERNANCE=on" in launch_env
    assert "PROPOSAL_CONTEXT_ABLATION=full" in launch_env
    assert "CONTROL_PAIR_KEY=cvrp.unit-cvrp:prepared" in launch_env

    run_sh = run_root / "run.sh"
    run_sh_text = run_sh.read_text(encoding="utf-8")
    command_txt = (run_root / "command.txt").read_text(encoding="utf-8")
    assert 'cd "$SCION_DIR"' in run_sh_text
    assert "LAUNCH_ENV_MISSING" in run_sh_text
    assert '"launch_env_missing"' in run_sh_text
    assert "export PYTHONPATH SCION_MODEL SCION_BASE_URL SCION_API_KEY" in run_sh_text
    assert "PREPARED_RUN_MANIFEST" in run_sh_text
    assert "SCION_STAGE_TRANSITION_DRAIN_LIMIT" in run_sh_text
    assert "OMP_NUM_THREADS=1" in run_sh_text
    assert "GIT_RUNTIME_DIRTY" in run_sh_text
    assert "GIT_COMMIT_MISMATCH" in run_sh_text
    assert "GIT_COMMIT_DOC_ONLY_MISMATCH_ALLOWED" in run_sh_text
    assert "tools/check_gpt55_proxy.py" in run_sh_text
    assert "--login-url-on-failure" in run_sh_text
    assert "--json" in run_sh_text
    assert "pre_campaign_completion_preflight.v1.json" in run_sh_text
    assert "tools/write_completion_preflight_status.py" in run_sh_text
    assert "write_postrun_acceptance_reports() {" in run_sh_text
    assert "--output \"$RUN_ROOT/run_status.json\"" in run_sh_text
    assert "--exit-code \"$PREFLIGHT_STATUS\"" in run_sh_text
    assert "--detail \"$PREFLIGHT_DETAIL\"" in run_sh_text
    assert 'cp "$CAMPAIGN_DIR/run_status.json" "$RUN_ROOT/run_status.json"' in (
        run_sh_text
    )
    assert "postrun_acceptance" in run_sh_text
    assert "tools/rebuild_postrun_acceptance.py" in run_sh_text
    assert "tools/check_postrun_acceptance.py" in run_sh_text
    assert "--strict" in run_sh_text
    assert "$REPORT_DIR/readiness/$REPORT_STEM.postrun_acceptance_readiness.v1.json" in (
        run_sh_text
    )
    assert "--require-current-run-ready" in run_sh_text
    assert '--report-stem "$REPORT_STEM"' in run_sh_text
    assert '--observed-control-arm "$OBSERVED_CONTROL_ARM"' in run_sh_text
    assert 'OBSERVED_CONTROL_ARM="${MEASUREMENT_GOVERNANCE//-/_}"' in run_sh_text
    assert 'rebuild_args+=(--control-pair-key "$CONTROL_PAIR_KEY")' in run_sh_text
    assert "POSTRUN_REPORTS_EXIT_STATUS:$POSTRUN_STATUS" in run_sh_text
    assert "POSTRUN_READINESS_EXIT_STATUS:$POSTRUN_READINESS_STATUS" in run_sh_text
    assert "SCION_BASE_URL=http://127.0.0.1:8080" in command_txt
    assert "SCION_STAGE_TRANSITION_DRAIN_LIMIT=4" in command_txt
    assert "AGENTIC_SESSION_TIMEOUT_SEC=3600" in command_txt
    assert "AGENTIC_TOOL_MAX_STEPS=240" in command_txt
    assert "AGENTIC_TOOL_MAX_CALLS=200" in command_txt
    assert "AGENTIC_CODE_TOOL_MAX_CALLS=200" in command_txt
    assert "AGENTIC_OBSERVATION_MAX_CHARS=2000000" in command_txt
    assert "PROPOSAL_ATTEMPT_LIMIT=64" in command_txt
    assert "PROPOSAL_QUALITY_LOOP_LIMIT=64" in command_txt
    assert "SCION_API_KEY=<set>" in command_txt
    assert "COMPLETION_PREFLIGHT=0" in command_txt
    assert (
        "GIT_RUNTIME_GUARD_PATHS="
        "scion/scion :(exclude)scion/scion/tests "
        "scion/tools scion/problems/cvrp vrp"
        in command_txt
    )
    assert "POSTRUN_REPORTS=1" in command_txt
    assert "CONTROL_PAIR_KEY=cvrp.unit-cvrp:prepared" in command_txt
    assert f"POSTRUN_REPORT_DIR={run_root / 'postrun_acceptance'}" in command_txt
    assert (
        f"PREPARED_RUN_MANIFEST={run_root / 'prepared_run_manifest.v1.json'}"
        in command_txt
    )
    assert f"PREPARED_HANDOFF_DIR={run_root / 'prepared_handoff'}" in command_txt
    assert "RESUME_FROM_CAMPAIGN=" in command_txt
    assert "--agentic-proposal" in command_txt
    assert "--agentic-session-timeout-sec 3600" in command_txt
    assert "--agentic-tool-max-steps 240" in command_txt
    assert "--agentic-tool-max-calls 200" in command_txt
    assert "--agentic-code-tool-max-calls 200" in command_txt
    assert "--agentic-observation-max-chars 2000000" in command_txt
    assert "--proposal-attempt-limit 64" in command_txt
    assert "--proposal-quality-loop-limit 64" in command_txt
    assert "--measurement-governance on" in command_txt
    assert "--proposal-context-ablation full" in command_txt
    assert '--measurement-governance "$MEASUREMENT_GOVERNANCE"' in run_sh_text
    assert '--agentic-tool-max-steps "$AGENTIC_TOOL_MAX_STEPS"' in run_sh_text
    assert '--agentic-tool-max-calls "$AGENTIC_TOOL_MAX_CALLS"' in run_sh_text
    assert (
        '--agentic-code-tool-max-calls "$AGENTIC_CODE_TOOL_MAX_CALLS"'
        in run_sh_text
    )
    assert (
        '--agentic-observation-max-chars "$AGENTIC_OBSERVATION_MAX_CHARS"'
        in run_sh_text
    )
    assert '--proposal-attempt-limit "$PROPOSAL_ATTEMPT_LIMIT"' in run_sh_text
    assert (
        '--proposal-quality-loop-limit "$PROPOSAL_QUALITY_LOOP_LIMIT"'
        in run_sh_text
    )
    assert '--proposal-context-ablation "$PROPOSAL_CONTEXT_ABLATION"' in run_sh_text
    assert "nohup setsid bash run.sh > nohup.log 2>&1 &" in command_txt

    prepared_handoff = run_root / "prepared_handoff"
    brief_json = (
        prepared_handoff
        / "analysis_brief"
        / "cvrp_on_full.prepared_analysis_brief.v1.json"
    )
    brief_md = (
        prepared_handoff
        / "analysis_brief"
        / "cvrp_on_full.prepared_analysis_brief.md"
    )
    inventory_json = (
        prepared_handoff
        / "inventory"
        / "cvrp_on_full.prepared_artifact_inventory.v1.json"
    )
    inventory_md = (
        prepared_handoff
        / "inventory"
        / "cvrp_on_full.prepared_artifact_inventory.md"
    )
    readiness_json = (
        prepared_handoff
        / "launch_readiness"
        / "cvrp_on_full.prepared_launch_readiness.v1.json"
    )
    readiness_md = (
        prepared_handoff
        / "launch_readiness"
        / "cvrp_on_full.prepared_launch_readiness.md"
    )
    prompt_context_json = (
        prepared_handoff
        / "prompt_context_readiness"
        / "cvrp_on_full.prepared_prompt_context_readiness.v1.json"
    )
    prompt_context_md = (
        prepared_handoff
        / "prompt_context_readiness"
        / "cvrp_on_full.prepared_prompt_context_readiness.md"
    )
    rebuild_json = (
        prepared_handoff / "rebuild" / "prepared_handoff_rebuild.v1.json"
    )
    assert brief_json.is_file()
    assert brief_md.is_file()
    assert inventory_json.is_file()
    assert inventory_md.is_file()
    assert readiness_json.is_file()
    assert readiness_md.is_file()
    assert prompt_context_json.is_file()
    assert prompt_context_md.is_file()
    assert rebuild_json.is_file()
    prepared_brief = json.loads(brief_json.read_text(encoding="utf-8"))
    prepared_inventory = json.loads(inventory_json.read_text(encoding="utf-8"))
    prepared_readiness = json.loads(readiness_json.read_text(encoding="utf-8"))
    prepared_prompt_context = json.loads(
        prompt_context_json.read_text(encoding="utf-8")
    )
    prepared_rebuild = json.loads(rebuild_json.read_text(encoding="utf-8"))
    assert prepared_brief["schema_version"] == "scion.postrun_analysis_brief.v1"
    assert prepared_brief["report_only"] is True
    assert prepared_brief["lifecycle"]["prepared_only"] is True
    assert prepared_brief["validity"]["run_validity_status"] == "prepared_only"
    assert prepared_brief["counters"]["effective_rounds_completed"] == 0
    assert any(
        "PREPARED-ONLY ROOT" in item
        for item in prepared_brief["stop_conditions"]
    )
    assert prepared_brief["prepared_run_contract"]["problem_family"] == "cvrp"
    assert "CVRP post-pivot" in prepared_brief["prepared_run_contract"][
        "analysis_intent"
    ]
    assert prepared_brief["prepared_run_contract"]["research_focus"][
        "scope"
    ] == "report_only_prepared_handoff"
    assert "route-merge absorption" in prepared_brief["prepared_run_contract"][
        "research_focus"
    ]["default_avoid_directions"]
    assert any(
        "large_instance_intra_route_two_opt_seed" in item
        for item in prepared_brief["prepared_run_contract"]["research_focus"][
            "measurable_opportunity_classes"
        ]
    )
    assert prepared_brief["prepared_run_contract"]["research_focus"][
        "measurement_opportunity_diagnostics"
    ]["screening_mde_at_power_80"] == 9.9
    assert prepared_brief["prepared_run_contract"]["research_focus"][
        "measurement_opportunity_diagnostics"
    ]["source"] == "problem_v1.measurement.calibration_ref"
    cvrp_checks = prepared_brief["prepared_run_contract"]["checks"]
    assert cvrp_checks["cvrp_measurement_handoff_present"]["passed"] is True
    assert (
        cvrp_checks["cvrp_measurement_handoff_problem_owned_source"]["passed"]
        is True
    )
    assert cvrp_checks["cvrp_default_avoid_directions_present"]["passed"] is True
    assert cvrp_checks["cvrp_direct_effect_rules_present"]["passed"] is True
    assert (
        cvrp_checks["cvrp_large_twoopt_bounded_constraints_present"]["passed"]
        is True
    )
    assert cvrp_checks["cvrp_handoff_decision_boundary_present"]["passed"] is True
    assert any(
        "Decision input" in item
        for item in prepared_brief["prepared_run_contract"]["acceptance_focus"]
    )
    assert any(
        "large-instance two-opt seed" in item and "deadline-aware" in item
        for item in prepared_brief["prepared_run_contract"]["acceptance_focus"]
    )
    problem_specific = prepared_brief["phase4_evidence_coverage"][
        "problem_specific_requirements"
    ]
    for key in (
        "cvrp_measurement_mde_handoff",
        "cvrp_low_snr_reason_handoff",
        "cvrp_measurable_opportunity_handoff",
        "cvrp_default_avoid_handoff",
        "cvrp_large_twoopt_seed_handoff",
        "cvrp_large_twoopt_unbounded_default_avoid_handoff",
        "cvrp_large_twoopt_bounded_constraints_handoff",
        "cvrp_direct_effect_rules_handoff",
        "cvrp_decision_boundary_handoff",
    ):
        assert problem_specific[key]["available"] is True
    assert prepared_inventory["lifecycle"]["prepared_only"] is True
    assert prepared_inventory["launcher"]["artifacts"]["prepared_handoff"] is True
    assert prepared_inventory["launcher"]["prepared_run_contract"]["checks"][
        "control_pair_key_present"
    ]["passed"] is True
    assert prepared_inventory["launcher"]["prepared_run_contract"]["checks"][
        "cvrp_default_avoid_directions_present"
    ]["passed"] is True
    assert prepared_readiness["schema_version"] == "scion.launch_readiness.v1"
    assert prepared_readiness["static_ready"] is False
    assert prepared_readiness["launch_ready"] is False
    assert prepared_readiness["checks"]["prepared_contract_complete"][
        "status"
    ] == "failed"
    assert prepared_readiness["checks"]["completion_preflight"]["status"] == "skipped"
    assert prepared_prompt_context["schema_version"] == (
        "scion.prepared_prompt_context_readiness.v1"
    )
    assert prepared_prompt_context["report_only"] is True
    assert (
        prepared_prompt_context["readiness"]["ready_for_launch_prompt_audit"]
        is False
    )
    assert "copied_campaign_summary" in prepared_prompt_context["readiness"][
        "missing_required"
    ]
    assert (
        prepared_prompt_context["signals"]["research_shape_prompt_signal"][
            "available"
        ]
        is True
    )
    assert (
        prepared_prompt_context["signals"]["cvrp_measurement_opportunity_handoff"][
            "available"
        ]
        is True
    )
    assert (
        prepared_prompt_context["signals"]["cvrp_large_twoopt_bounded_constraints"][
            "available"
        ]
        is True
    )
    assert prepared_rebuild["schema_version"] == "scion.prepared_handoff_rebuild.v1"
    assert prepared_rebuild["complete"] is True
    assert prepared_rebuild["families"]["analysis_brief"]["status"] == "ok"
    assert (
        prepared_rebuild["families"]["prompt_context_readiness"]["status"] == "ok"
    )
    assert (
        "## Prepared Run Contract"
        in brief_md.read_text(encoding="utf-8")
    )
    brief_text = brief_md.read_text(encoding="utf-8")
    inventory_text = inventory_md.read_text(encoding="utf-8")
    assert "Current research focus" in brief_text
    assert "screening_mde_at_power_80: 9.9" in brief_text
    assert "TRAJECTORY_DIVERGENT_LOW_SNR" in brief_text
    assert "### Problem-Specific Phase 4 Evidence Coverage" in brief_text
    assert "cvrp_direct_effect_rules_handoff" in brief_text
    assert "cvrp_large_twoopt_seed_handoff" in brief_text
    assert "cvrp_large_twoopt_unbounded_default_avoid_handoff" in brief_text
    assert "cvrp_large_twoopt_bounded_constraints_handoff" in brief_text
    assert (
        "## Launcher Artifacts"
        in inventory_text
    )
    assert "### Prepared Research Focus" in inventory_text
    assert "construction_seed_portfolio" in inventory_text
    assert "CVRP_MDE_EXCEEDS_PRACTICAL_DELTA" in inventory_text
    assert "cvrp_default_avoid_handoff" in inventory_text
    assert "cvrp_large_twoopt_seed_handoff" in inventory_text
    assert "cvrp_large_twoopt_unbounded_default_avoid_handoff" in inventory_text
    assert "cvrp_large_twoopt_bounded_constraints_handoff" in inventory_text
    assert "copied_campaign_summary" in prompt_context_md.read_text(
        encoding="utf-8"
    )
    assert "Launch only after rerunning this tool" in readiness_md.read_text(
        encoding="utf-8"
    )

    subprocess.run(["bash", "-n", str(run_sh)], check=True)


def test_cvrp_agentic_launcher_can_copy_resume_campaign(tmp_path: Path) -> None:
    source_campaign = tmp_path / "source-campaign"
    (source_campaign / "champions" / "champion_v3").mkdir(parents=True)
    (source_campaign / "champions" / "champion_v3" / "registry.yaml").write_text(
        "operators: {}\n",
        encoding="utf-8",
    )
    (source_campaign / "scion.db").write_text("fake-cvrp-db", encoding="utf-8")
    (source_campaign / "run_status.json").write_text(
        json.dumps({"status": "finished", "wrapper_exit_status": 0}),
        encoding="utf-8",
    )
    (source_campaign / "campaign_summary.json").write_text(
        json.dumps({"run_complete": True}),
        encoding="utf-8",
    )
    (source_campaign / "artifacts" / "branch_evidence").mkdir(parents=True)
    (
        source_campaign / "artifacts" / "branch_evidence" / "branch-a.json"
    ).write_text("{}", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "2",
            "--label",
            "unit-cvrp-resume",
            "--experiments-root",
            str(tmp_path / "experiments"),
            "--resume-from-campaign",
            str(source_campaign),
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
        check=True,
    )
    run_root_line = next(
        line for line in result.stdout.splitlines() if line.startswith("RUN_ROOT=")
    )
    run_root = Path(run_root_line.removeprefix("RUN_ROOT="))

    assert (
        run_root / "campaign" / "scion.db"
    ).read_text(encoding="utf-8") == "fake-cvrp-db"
    assert (
        run_root / "campaign" / "champions" / "champion_v3" / "registry.yaml"
    ).is_file()
    assert (
        run_root / "campaign" / "artifacts" / "branch_evidence" / "branch-a.json"
    ).is_file()
    prepare_status = json.loads(
        (run_root / "run_status.json").read_text(encoding="utf-8")
    )
    assert prepare_status["status"] == "prepared"
    assert prepare_status["prepared_only"] is True
    assert prepare_status["resume_from_campaign"] == str(source_campaign)
    assert prepare_status["copied_campaign_status_present"] is True
    assert prepare_status["copied_campaign_summary_present"] is True
    launch_env = (run_root / "launch.env").read_text(encoding="utf-8")
    command_txt = (run_root / "command.txt").read_text(encoding="utf-8")
    assert f"RESUME_FROM_CAMPAIGN={source_campaign}" in launch_env
    assert f"RESUME_FROM_CAMPAIGN={source_campaign}" in command_txt


def test_cvrp_agentic_launcher_prepare_accepts_custom_phase_b_flags(
    tmp_path: Path,
) -> None:
    baseline_root = tmp_path / "copied-baseline"
    formal_dir = baseline_root / "formal"
    formal_dir.mkdir(parents=True)
    problem = SCION_DIR / "scion/problems/cvrp/problem.yaml"
    protocol = formal_dir / "matched-protocol.yaml"
    split = formal_dir / "matched-split.yaml"
    seeds = formal_dir / "matched-seeds.yaml"

    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "2",
            "--label",
            "unit-cvrp-phase-b",
            "--problem",
            str(problem),
            "--protocol",
            str(protocol),
            "--split",
            str(split),
            "--seeds",
            str(seeds),
            "--measurement-governance",
            "record-only",
            "--proposal-context-ablation",
            "compact-measurement-diagnostics",
            "--control-pair-key",
            "pair-a-vs-b",
            "--stage-transition-drain-limit",
            "2",
            "--proposal-attempt-limit",
            "17",
            "--proposal-quality-loop-limit",
            "19",
            "--python",
            str(tmp_path / "python-bin"),
            "--experiments-root",
            str(tmp_path / "runs"),
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
        check=True,
    )

    run_root_line = next(
        line for line in result.stdout.splitlines() if line.startswith("RUN_ROOT=")
    )
    run_root = Path(run_root_line.removeprefix("RUN_ROOT="))
    launch_env = (run_root / "launch.env").read_text(encoding="utf-8")
    run_sh_text = (run_root / "run.sh").read_text(encoding="utf-8")
    command_txt = (run_root / "command.txt").read_text(encoding="utf-8")

    assert f"PROBLEM={problem}" in launch_env
    assert f"PY={tmp_path / 'python-bin'}" in launch_env
    assert f"PROTOCOL={protocol}" in launch_env
    assert f"SPLIT={split}" in launch_env
    assert f"SEEDS={seeds}" in launch_env
    assert "MEASUREMENT_GOVERNANCE=record-only" in launch_env
    assert (
        "PROPOSAL_CONTEXT_ABLATION=compact-measurement-diagnostics" in launch_env
    )
    assert "CONTROL_PAIR_KEY=pair-a-vs-b" in launch_env
    assert "SCION_STAGE_TRANSITION_DRAIN_LIMIT=2" in launch_env
    assert "PROPOSAL_ATTEMPT_LIMIT=17" in launch_env
    assert "PROPOSAL_QUALITY_LOOP_LIMIT=19" in launch_env
    assert f"--problem {problem}" in command_txt
    assert f"--protocol {protocol}" in command_txt
    assert f"--split {split}" in command_txt
    assert f"--seeds {seeds}" in command_txt
    assert "--measurement-governance record-only" in command_txt
    assert (
        "--proposal-context-ablation compact-measurement-diagnostics" in command_txt
    )
    assert "CONTROL_PAIR_KEY=pair-a-vs-b" in command_txt
    assert "SCION_STAGE_TRANSITION_DRAIN_LIMIT=2" in command_txt
    assert "PROPOSAL_ATTEMPT_LIMIT=17" in command_txt
    assert "PROPOSAL_QUALITY_LOOP_LIMIT=19" in command_txt
    assert "--proposal-attempt-limit 17" in command_txt
    assert "--proposal-quality-loop-limit 19" in command_txt
    assert "--control-pair-key" not in command_txt
    run_command_block = run_sh_text.split(
        '"$PY" -m scion.cli.main run \\', maxsplit=1
    )[1].split("STATUS=$?", maxsplit=1)[0]
    assert "--control-pair-key" not in run_command_block
    assert '--proposal-attempt-limit "$PROPOSAL_ATTEMPT_LIMIT"' in run_command_block
    assert (
        '--proposal-quality-loop-limit "$PROPOSAL_QUALITY_LOOP_LIMIT"'
        in run_command_block
    )
    assert 'rebuild_args+=(--control-pair-key "$CONTROL_PAIR_KEY")' in run_sh_text

    subprocess.run(["bash", "-n", str(run_root / "run.sh")], check=True)


def test_cvrp_agentic_launcher_prepare_accepts_base_url_override(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "unit-cvrp-base",
            "--base-url",
            "http://127.0.0.1:18080/v1",
            "--experiments-root",
            str(tmp_path),
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
        check=True,
    )

    run_root_line = next(
        line for line in result.stdout.splitlines() if line.startswith("RUN_ROOT=")
    )
    run_root = Path(run_root_line.removeprefix("RUN_ROOT="))
    launch_env = (run_root / "launch.env").read_text(encoding="utf-8")
    command_txt = (run_root / "command.txt").read_text(encoding="utf-8")

    assert "SCION_BASE_URL=http://127.0.0.1:18080/v1" in launch_env
    assert "SCION_BASE_URL=http://127.0.0.1:18080/v1" in command_txt
    assert "SCION_API_KEY=''" in launch_env
    assert "SCION_API_KEY=<unset>" in command_txt


def test_cvrp_agentic_launcher_prepare_accepts_api_key_override(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "unit-cvrp-key",
            "--base-url",
            "http://127.0.0.1:18080/v1",
            "--api-key",
            "test-proxy-key",
            "--experiments-root",
            str(tmp_path),
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
        check=True,
    )

    run_root_line = next(
        line for line in result.stdout.splitlines() if line.startswith("RUN_ROOT=")
    )
    run_root = Path(run_root_line.removeprefix("RUN_ROOT="))
    launch_env = (run_root / "launch.env").read_text(encoding="utf-8")
    command_txt = (run_root / "command.txt").read_text(encoding="utf-8")

    assert "SCION_API_KEY=test-proxy-key" in launch_env
    assert "test-proxy-key" not in command_txt
    assert "SCION_API_KEY=<set>" in command_txt


def test_cvrp_agentic_launcher_prepare_accepts_api_key_env_without_secret(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "unit-cvrp-key-env",
            "--base-url",
            "https://aihubmix.com",
            "--api-key-env",
            "SCION_API_KEY",
            "--experiments-root",
            str(tmp_path),
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
        check=True,
    )

    run_root_line = next(
        line for line in result.stdout.splitlines() if line.startswith("RUN_ROOT=")
    )
    run_root = Path(run_root_line.removeprefix("RUN_ROOT="))
    launch_env_path = run_root / "launch.env"
    launch_env = launch_env_path.read_text(encoding="utf-8")
    run_sh_text = (run_root / "run.sh").read_text(encoding="utf-8")
    command_txt = (run_root / "command.txt").read_text(encoding="utf-8")

    assert "SCION_BASE_URL=https://aihubmix.com" in launch_env
    assert "SCION_API_KEY=''" in launch_env
    assert "SCION_API_KEY_ENV=SCION_API_KEY" in launch_env
    assert "SCION_API_KEY=<from-env:SCION_API_KEY>" in command_txt
    assert '_INHERITED_SCION_API_KEY="${SCION_API_KEY:-}"' in run_sh_text
    assert '_RESOLVED_SCION_API_KEY="${!SCION_API_KEY_ENV:-}"' in run_sh_text
    assert "SCION_API_KEY_ENV_MISSING" in run_sh_text
    assert oct(launch_env_path.stat().st_mode & 0o777) == "0o600"

    subprocess.run(["bash", "-n", str(run_root / "run.sh")], check=True)


def test_cvrp_agentic_launcher_can_skip_postrun_reports(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "unit-cvrp-no-reports",
            "--experiments-root",
            str(tmp_path),
            "--skip-postrun-reports",
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
        check=True,
    )
    run_root_line = next(
        line for line in result.stdout.splitlines() if line.startswith("RUN_ROOT=")
    )
    run_root = Path(run_root_line.removeprefix("RUN_ROOT="))

    launch_env = (run_root / "launch.env").read_text(encoding="utf-8")
    command_txt = (run_root / "command.txt").read_text(encoding="utf-8")
    assert "POSTRUN_REPORTS=0" in launch_env
    assert "POSTRUN_REPORTS=0" in command_txt


def test_cvrp_agentic_launcher_api_key_env_missing_fails_before_campaign(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "unit-cvrp-missing-key-env",
            "--api-key-env",
            "SCION_MISSING_TEST_KEY",
            "--python",
            sys.executable,
            "--experiments-root",
            str(tmp_path),
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
        check=True,
    )
    run_root_line = next(
        line for line in result.stdout.splitlines() if line.startswith("RUN_ROOT=")
    )
    run_root = Path(run_root_line.removeprefix("RUN_ROOT="))

    run_result = subprocess.run(
        ["bash", str(run_root / "run.sh")],
        text=True,
        capture_output=True,
    )

    assert run_result.returncode == 64
    assert not (run_root / "campaign" / "campaign_summary.json").exists()
    assert "SCION_API_KEY_ENV_MISSING:SCION_MISSING_TEST_KEY" in (
        run_root / "exit.txt"
    ).read_text(encoding="utf-8")
    status = json.loads((run_root / "run_status.json").read_text(encoding="utf-8"))
    assert status["wrapper_exit_status"] == 64
    assert status["api_key_env_missing"] == "SCION_MISSING_TEST_KEY"
    run_log = (run_root / "run.log").read_text(encoding="utf-8")
    assert "POSTRUN_REPORTS_EXIT_STATUS:" in run_log
    assert "POSTRUN_READINESS_EXIT_STATUS:" in run_log
    readiness_dir = run_root / "postrun_acceptance" / "readiness"
    assert list(readiness_dir.glob("*.postrun_acceptance_readiness.v1.json"))


def test_cvrp_agentic_launcher_api_key_env_preserves_inherited_scion_key(
    tmp_path: Path,
) -> None:
    fake_python = tmp_path / "fake-python"
    seen_env = tmp_path / "seen-env.txt"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' \"$SCION_API_KEY\" > {seen_env}\n"
        "exit 0\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "unit-cvrp-inherited-key-env",
            "--api-key-env",
            "SCION_API_KEY",
            "--python",
            str(fake_python),
            "--experiments-root",
            str(tmp_path / "runs"),
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
        check=True,
    )
    run_root_line = next(
        line for line in result.stdout.splitlines() if line.startswith("RUN_ROOT=")
    )
    run_root = Path(run_root_line.removeprefix("RUN_ROOT="))
    launch_env = run_root / "launch.env"
    launch_env.write_text(
        launch_env.read_text(encoding="utf-8").replace(
            "GIT_RUNTIME_GUARD_PATHS="
            "'scion/scion :(exclude)scion/scion/tests "
            "scion/tools scion/problems/cvrp vrp'",
            "GIT_RUNTIME_GUARD_PATHS=scion/design/scion-architecture-v3.md",
        ),
        encoding="utf-8",
    )

    run_result = subprocess.run(
        ["bash", str(run_root / "run.sh")],
        env={"SCION_API_KEY": "fake-inherited-secret"},
        text=True,
        capture_output=True,
    )

    assert run_result.returncode == 0
    assert seen_env.read_text(encoding="utf-8").strip() == "fake-inherited-secret"
    assert "SCION_API_KEY_ENV_MISSING" not in (
        run_root / "exit.txt"
    ).read_text(encoding="utf-8")


def test_cvrp_agentic_launcher_prepare_writes_completion_preflight(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "unit-cvrp-preflight",
            "--completion-preflight",
            "--experiments-root",
            str(tmp_path),
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
        check=True,
    )

    run_root_line = next(
        line for line in result.stdout.splitlines() if line.startswith("RUN_ROOT=")
    )
    run_root = Path(run_root_line.removeprefix("RUN_ROOT="))
    launch_env = (run_root / "launch.env").read_text(encoding="utf-8")
    run_sh_text = (run_root / "run.sh").read_text(encoding="utf-8")
    command_txt = (run_root / "command.txt").read_text(encoding="utf-8")

    assert "COMPLETION_PREFLIGHT=1" in launch_env
    assert "COMPLETION_PREFLIGHT=1" in command_txt
    assert "tools/check_gpt55_proxy.py" in run_sh_text
    assert "--base-url \"$SCION_BASE_URL\"" in run_sh_text
    assert "--model \"$SCION_MODEL\"" in run_sh_text
    assert "--api-key \"$SCION_API_KEY\"" in run_sh_text
    assert "--login-url-on-failure" in run_sh_text
    assert "--json" in run_sh_text
    assert "pre_campaign_completion_preflight.v1.json" in run_sh_text
    assert "tools/write_completion_preflight_status.py" in run_sh_text
    assert "pre_campaign_completion_preflight" in run_sh_text
    assert "/v1/models" not in run_sh_text
    assert "openai.OpenAI" not in run_sh_text

    subprocess.run(["bash", "-n", str(run_root / "run.sh")], check=True)


def test_cvrp_agentic_launcher_rejects_api_key_and_api_key_env(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "unit-cvrp-key-conflict",
            "--api-key",
            "test-key",
            "--api-key-env",
            "SCION_API_KEY",
            "--experiments-root",
            str(tmp_path),
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "--api-key and --api-key-env are mutually exclusive" in result.stderr


def test_cvrp_agentic_launcher_rejects_invalid_api_key_env(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "unit-cvrp-key-invalid",
            "--api-key-env",
            "not-valid-name",
            "--experiments-root",
            str(tmp_path),
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "--api-key-env must be a valid shell environment variable name" in (
        result.stderr
    )


def test_cvrp_agentic_launcher_preflight_rejects_parameter_search_enabled(
    tmp_path: Path,
) -> None:
    module = _load_launcher_module()
    problem = tmp_path / "problem.yaml"
    problem_v1 = tmp_path / "problem-v1.yaml"
    problem.write_text("parameter_search:\n  enabled: false\n", encoding="utf-8")
    problem_v1.write_text("parameter_search:\n  enabled: true\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        module._preflight_cvrp_parameter_search_disabled(SCION_DIR, str(problem))

    assert exc_info.value.code != 0
    assert "CVRP agentic launcher requires parameter_search.enabled=false" in str(
        exc_info.value
    )
    assert "problem-v1.yaml" in str(exc_info.value)


def test_cvrp_agentic_launcher_preflight_rejects_custom_problem_path(
    tmp_path: Path,
) -> None:
    module = _load_launcher_module()
    problem = tmp_path / "custom-problem.yaml"
    problem.write_text("parameter_search:\n  enabled: true\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        module._preflight_cvrp_parameter_search_disabled(SCION_DIR, str(problem))

    assert exc_info.value.code != 0
    assert "CVRP agentic launcher requires parameter_search.enabled=false" in str(
        exc_info.value
    )
    assert str(problem) in str(exc_info.value)
