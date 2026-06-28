from pathlib import Path

from scion.launcher.lifecycle import (
    CampaignCommandPlan,
    LauncherLifecyclePlan,
    PreCampaignGuard,
    render_run_sh,
)


def test_render_run_sh_wraps_dummy_command_with_lifecycle_markers(
    tmp_path: Path,
) -> None:
    plan = LauncherLifecyclePlan(
        run_root=tmp_path / "run",
        campaign_dir=tmp_path / "run" / "campaign",
        repo_root=tmp_path / "repo",
        scion_dir=tmp_path / "repo" / "scion",
        python=Path("/usr/bin/python"),
        git_commit="abc1234",
        model="dummy-model",
        scion_base_url="http://127.0.0.1:9999",
        api_key_env_binding="SCION_API_KEY",
        postrun_report_stem_prefix="dummy",
        fallback_assignments=(
            ("RUN_ROOT", tmp_path / "run"),
            ("PY", "/usr/bin/python"),
            ("SCION_DIR", tmp_path / "repo" / "scion"),
            ("MEASUREMENT_GOVERNANCE", "record-only"),
            ("PROPOSAL_CONTEXT_ABLATION", "minimal-research-context"),
            ("CONTROL_PAIR_KEY", "dummy:prepared"),
            ("POSTRUN_REPORTS", 1),
        ),
        exported_env_names=(
            "PYTHONPATH",
            "SCION_MODEL",
            "SCION_BASE_URL",
            "SCION_API_KEY",
            "SCION_SDK_MAX_RETRIES",
            "SCION_LLM_MAX_RETRIES",
            "SCION_FRESH_RUNTIME_REPLAY_DRAIN_LIMIT",
            "SCION_STAGE_TRANSITION_DRAIN_LIMIT",
            "PREPARED_RUN_MANIFEST",
        ),
        command=CampaignCommandPlan(
            command_log="dummy campaign command",
            command_body='echo "DUMMY_COMMAND_EXECUTED" >> "$RUN_ROOT/run.log"',
            exported_env_names=("DUMMY_DATA_ROOT",),
        ),
        pre_campaign_guards=(
            PreCampaignGuard(
                failure_key="DUMMY_GUARD_FAILED",
                condition='[[ ! -f "$DUMMY_DATA_ROOT/ready" ]]',
                detail="$DUMMY_DATA_ROOT",
                status_fields={"dummy_guard_failed": True},
            ),
        ),
    )

    run_sh = render_run_sh(plan)

    assert run_sh.startswith("#!/usr/bin/env bash")
    assert "export PYTHONPATH" in run_sh
    assert "DUMMY_DATA_ROOT" in run_sh
    assert "DUMMY_GUARD_FAILED:$DUMMY_DATA_ROOT" in run_sh
    assert '"dummy_guard_failed":true' in run_sh
    assert 'REPORT_STEM="dummy_${MEASUREMENT_GOVERNANCE//-/_}' in run_sh

    command_log = run_sh.index('echo "COMMAND:dummy campaign command"')
    guard = run_sh.index("DUMMY_GUARD_FAILED:$DUMMY_DATA_ROOT")
    running_status = run_sh.index("tools/write_launcher_running_status.py")
    completion_preflight = run_sh.index("tools/write_completion_preflight_status.py")
    campaign_marker = run_sh.index("CAMPAIGN_EXECUTION_MARKER_STARTED_AT")
    dummy_command = run_sh.index("DUMMY_COMMAND_EXECUTED")
    postrun_call = run_sh.index(
        "write_postrun_acceptance_reports || POSTRUN_ACCEPTANCE_STATUS=$?"
    )
    postrun_status = run_sh.index("tools/write_postrun_wrapper_status.py")

    assert command_log < guard
    assert guard < running_status
    assert running_status < completion_preflight
    assert completion_preflight < campaign_marker
    assert campaign_marker < dummy_command
    assert dummy_command < postrun_call
    assert postrun_call < postrun_status
    assert '--resume-from-campaign "$RESUME_FROM_CAMPAIGN"' in run_sh
    assert '--resume-snapshot-ref "$RESUME_SNAPSHOT_MANIFEST_REF"' in run_sh
    assert (
        '--copied-campaign-status-present '
        '"$RESUME_COPIED_CAMPAIGN_STATUS_PRESENT"'
    ) in run_sh
    assert (
        '--copied-campaign-summary-present '
        '"$RESUME_COPIED_CAMPAIGN_SUMMARY_PRESENT"'
    ) in run_sh
