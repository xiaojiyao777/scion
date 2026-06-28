"""Constants for report-only postrun artifact inventory loading."""

from __future__ import annotations

HANDOFF_DOC = "scion/docs/operations/postrun-analysis-handoff.md"
LAUNCHER_ARTIFACTS = (
    "run.sh",
    "launch.env",
    "command.txt",
    "prepared_run_manifest.v1.json",
    "prepared_run_manifest.md",
    "prepared_handoff",
    "pre_campaign_completion_preflight.v1.json",
    "campaign_execution_marker.v1.json",
    "run.log",
    "exit.txt",
)
CAMPAIGN_EXECUTION_ARTIFACTS = (
    ("campaign_run_status", "run_status.json"),
    ("campaign_status", "status.json"),
    ("campaign_summary", "campaign_summary.json"),
)
LAUNCHER_STATUS_KEYS = (
    "wrapper_exit_status",
    "pre_campaign_completion_preflight",
    "pre_campaign_completion_preflight_active_accounts",
    "pre_campaign_completion_preflight_authenticated",
    "pre_campaign_completion_preflight_classification",
    "pre_campaign_completion_preflight_code",
    "pre_campaign_completion_preflight_detail_file",
    "pre_campaign_completion_preflight_http_status",
    "pre_campaign_completion_preflight_login_url_present",
    "pre_campaign_completion_preflight_operator_action",
    "pre_campaign_completion_preflight_refreshing_accounts",
    "api_key_env_missing",
    "launch_env_missing",
    "launcher_running_status_write_failed",
    "scion_dir_missing",
    "git_runtime_dirty",
    "git_runtime_commit_mismatch",
    "campaign_wrapper_exit_status",
    "postrun_acceptance_failed",
    "postrun_acceptance_readiness_file",
    "postrun_acceptance_readiness_path",
    "postrun_acceptance_report_dir",
    "postrun_acceptance_status",
    "postrun_readiness_exit_status",
    "postrun_reports_exit_status",
)
PRE_CAMPAIGN_INFRA_FAILURE_KEYS = (
    "api_key_env_missing",
    "launch_env_missing",
    "launcher_running_status_write_failed",
    "scion_dir_missing",
    "git_runtime_dirty",
    "git_runtime_commit_mismatch",
)
RUN_LOG_MARKERS = (
    "COMPLETION_PREFLIGHT_DETAIL",
    "COMPLETION_PREFLIGHT_FAILED",
    "COMPLETION_PREFLIGHT_OK",
    "GIT_COMMIT_DOC_ONLY_MISMATCH_ALLOWED",
    "GIT_COMMIT_MISMATCH",
    "GIT_RUNTIME_DIRTY",
    "LAUNCH_ENV_MISSING",
    "POSTRUN_REPORT_DIR",
    "POSTRUN_REPORTS_EXIT_STATUS",
    "POSTRUN_REPORTS_FINISHED_AT",
    "POSTRUN_REPORTS_STARTED_AT",
    "POSTRUN_READINESS_EXIT_STATUS",
    "POSTRUN_STATUS_WRITE_EXIT_STATUS",
    "SCION_DIR_MISSING",
)
EXIT_MARKERS = (
    "POSTRUN_ACCEPTANCE_DIR",
    "POSTRUN_ACCEPTANCE_FAILED",
    "POSTRUN_READINESS_EFFECTIVE_EXIT_STATUS",
    "POSTRUN_REPORTS_EFFECTIVE_EXIT_STATUS",
    "PRE_CAMPAIGN_COMPLETION_PREFLIGHT_FAILED",
    "WRAPPER_EXIT_STATUS",
    "WRAPPER_EXIT_STATUS_EFFECTIVE",
)
POSTRUN_REPORT_DIRS = (
    "summaries",
    "failures",
    "research_efficiency",
    "manifests",
    "analysis_brief",
    "inventory",
    "readiness",
    "rebuild",
)
