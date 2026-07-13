import hashlib
import importlib.util
import json
import re
import stat
import subprocess
import sys
from pathlib import Path

import yaml


SCION_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
LAUNCHER = SCION_DIR / "tools" / "launch_warehouse_direct_campaign.py"


def _use_clean_git_guard_root(launch_env_path: Path, tmp_path: Path) -> None:
    """Point wrapper-only guard tests at an isolated clean Git root."""

    repo = tmp_path / "clean-runtime-root"
    repo.mkdir()
    (repo / "README.md").write_text("runtime guard fixture\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "fixture"], cwd=repo, check=True)
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()

    text = launch_env_path.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^REPO_ROOT=.*$", f"REPO_ROOT={repo}", text)
    text = re.sub(r"(?m)^GIT_COMMIT=.*$", f"GIT_COMMIT={commit}", text)
    launch_env_path.write_text(text, encoding="utf-8")


def test_warehouse_direct_launcher_help() -> None:
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
    assert "--warehouse-data-root" in result.stdout
    assert "--resume-from-campaign" in result.stdout
    assert "--problem-v1" in result.stdout
    assert "--measurement-governance" not in result.stdout
    assert "--proposal-context-ablation" not in result.stdout
    assert "--control-pair-key" in result.stdout


def test_warehouse_launcher_rejects_launch_without_completion_preflight(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "formal-without-preflight",
            "--experiments-root",
            str(tmp_path / "experiments"),
            "--warehouse-data-root",
            str(tmp_path / "data"),
            "--launch",
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "--launch requires --completion-preflight" in result.stderr


def test_warehouse_launcher_rejects_resume_for_completion_preflight(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "resumed-formal",
            "--experiments-root",
            str(tmp_path / "experiments"),
            "--warehouse-data-root",
            str(tmp_path / "data"),
            "--completion-preflight",
            "--resume-from-campaign",
            str(tmp_path / "prior-campaign"),
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "requires a fresh campaign" in result.stderr


def test_warehouse_launcher_rejects_skipped_postrun_for_completion_preflight(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "postrun-skipped-formal",
            "--experiments-root",
            str(tmp_path / "experiments"),
            "--warehouse-data-root",
            str(tmp_path / "data"),
            "--completion-preflight",
            "--skip-postrun-reports",
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "requires strict postrun reports" in result.stderr


def test_warehouse_launcher_rejects_enabled_parameter_search(
    tmp_path: Path,
) -> None:
    problem = tmp_path / "problem.yaml"
    problem_v1 = tmp_path / "problem-v1.yaml"
    problem.write_text("parameter_search:\n  enabled: false\n", encoding="utf-8")
    problem_v1.write_text("parameter_search:\n  enabled: true\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "hidden-weight-search",
            "--experiments-root",
            str(tmp_path / "experiments"),
            "--warehouse-data-root",
            str(tmp_path / "data"),
            "--problem",
            str(problem),
            "--problem-v1",
            str(problem_v1),
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "parameter_search.enabled=false" in result.stderr


def test_warehouse_direct_launcher_prepare_writes_rewritten_run_files(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "scion-data"

    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "6",
            "--label",
            "unit-warehouse",
            "--experiments-root",
            str(tmp_path / "experiments"),
            "--warehouse-data-root",
            str(data_root),
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

    assert run_root.parent == tmp_path / "experiments"
    assert run_root.name.startswith("unit-warehouse-6r-gpt55-")
    assert (run_root / "campaign").is_dir()
    assert (run_root / "config").is_dir()
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
    assert prepare_status["proposal_runtime_mode"] == "direct_v3"
    assert not any("agentic" in key for key in prepare_status)

    launch_env_path = run_root / "launch.env"
    launch_env = launch_env_path.read_text(encoding="utf-8")
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
    assert prepared_manifest["problem_family"] == "warehouse_delivery"
    assert prepared_manifest["execution"]["proposal_runtime_mode"] == "direct_v3"
    assert "PROPOSAL_RUNTIME_MODE" not in launch_env
    assert "MEASUREMENT_GOVERNANCE" not in launch_env
    assert "PROPOSAL_CONTEXT_ABLATION" not in launch_env
    assert "DISABLE_EARLY_STOP" not in launch_env
    assert "SCION_SDK_MAX_RETRIES" not in launch_env
    assert "SCION_LLM_MAX_RETRIES" not in launch_env
    assert "- proposal_runtime_mode: `direct_v3`" in prepared_manifest_md
    typed_contract = prepared_manifest["research_guidance_contract"]
    assert typed_contract["schema_version"] == (
        "scion.warehouse_research_guidance_contract.v2"
    )
    assert typed_contract["problem_family"] == "warehouse_delivery"
    assert typed_contract["proposal_visibility_only"] is True
    assert typed_contract["decision_features_excluded"] is True
    assert any(
        block["block_id"] == "warehouse_open_research_surfaces"
        for block in typed_contract["guidance_blocks"]
    )
    assert prepared_manifest["research_focus"]["scope"] == (
        "report_only_prepared_handoff"
    )
    assert "DecisionFeatures" in prepared_manifest["research_focus"][
        "decision_boundary"
    ]
    assert prepared_manifest["execution"]["rounds"] == 6
    assert prepared_manifest["config"]["warehouse_data_root"] == str(data_root)
    assert prepared_manifest["config"]["problem_v1"] == str(
        run_root / "config" / "problem-v1.yaml"
    )
    assert prepared_manifest["report_metadata"]["postrun_acceptance_families"] == [
        "summaries",
        "failures",
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
        == "warehouse.unit-warehouse:prepared"
    )
    assert "SCION_API_KEY" not in json.dumps(prepared_manifest, sort_keys=True)
    assert stat.S_IMODE(launch_env_path.stat().st_mode) == 0o600
    assert f"REPO_ROOT={PROJECT_ROOT}" in launch_env
    assert f"SCION_DIR={SCION_DIR}" in launch_env
    assert f"PYTHONPATH={SCION_DIR}" in launch_env
    assert f"SCION_WAREHOUSE_DATA_ROOT={data_root}" in launch_env
    assert f"SCION_PROBLEM_DATA_ROOT={data_root}" in launch_env
    assert "SCION_MODEL=gpt-5.5" in launch_env
    assert "SCION_BASE_URL=http://127.0.0.1:8080" in launch_env
    assert "SCION_API_KEY=pwd" in launch_env
    assert "SCION_API_KEY_ENV=''" in launch_env
    assert (
        f"PREPARED_RUN_MANIFEST={run_root / 'prepared_run_manifest.v1.json'}"
        in launch_env
    )
    assert "COMPLETION_PREFLIGHT=0" in launch_env
    assert "POSTRUN_REPORTS=1" in launch_env
    assert "CONTROL_PAIR_KEY=warehouse.unit-warehouse:prepared" in launch_env
    run_script_sha256 = hashlib.sha256(
        (run_root / "run.sh").read_bytes()
    ).hexdigest()
    assert f"RUN_SCRIPT_SHA256={run_script_sha256}" in launch_env
    assert prepared_manifest["run_script"] == {
        "path": str(run_root / "run.sh"),
        "sha256": run_script_sha256,
    }
    assert (
        "GIT_RUNTIME_GUARD_PATHS="
        "'scion/scion :(exclude)scion/scion/tests "
        "scion/tools scion/problems/warehouse_delivery surrogate'" in launch_env
    )
    assert "ROUNDS=6" in launch_env
    assert "RESUME_FROM_CAMPAIGN=''" in launch_env
    assert f"PROBLEM={run_root / 'config' / 'problem.yaml'}" in launch_env
    assert f"PROBLEM_V1={run_root / 'config' / 'problem-v1.yaml'}" in launch_env
    assert f"PROTOCOL={run_root / 'config' / 'protocol_prod.yaml'}" in launch_env
    assert f"SPLIT={run_root / 'config' / 'split_manifest_prod.yaml'}" in launch_env
    assert f"SEEDS={run_root / 'config' / 'seed_ledger.yaml'}" in launch_env

    problem = yaml.safe_load(
        (run_root / "config" / "problem.yaml").read_text(encoding="utf-8")
    )
    problem_v1 = yaml.safe_load(
        (run_root / "config" / "problem-v1.yaml").read_text(encoding="utf-8")
    )
    split = yaml.safe_load(
        (run_root / "config" / "split_manifest_prod.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert problem_v1["root_dir"] == str(PROJECT_ROOT / "surrogate")
    assert problem["parameter_search"]["enabled"] is False
    assert problem_v1["parameter_search"]["enabled"] is False
    assert problem_v1["canary_case_path"] == str(
        PROJECT_ROOT / "surrogate" / "data" / "instance_small_1.json"
    )
    assert split["safe_data_roots"] == [str(data_root)]
    assert all(str(case).startswith(str(data_root)) for case in split["canary"])
    assert all(str(case).startswith(str(data_root)) for case in split["screening"])
    assert all(str(case).startswith(str(data_root)) for case in split["validation"])
    assert all(str(case).startswith(str(data_root)) for case in split["frozen"])

    run_sh = run_root / "run.sh"
    run_sh_text = run_sh.read_text(encoding="utf-8")
    command_txt = (run_root / "command.txt").read_text(encoding="utf-8")
    assert 'cd "$SCION_DIR"' in run_sh_text
    assert "LAUNCH_ENV_MISSING" in run_sh_text
    assert '"launch_env_missing"' in run_sh_text
    assert "PREPARED_RUN_MANIFEST" in run_sh_text
    assert "SCION_SDK_MAX_RETRIES" not in run_sh_text
    assert "SCION_LLM_MAX_RETRIES" not in run_sh_text
    assert "GIT_RUNTIME_DIRTY" in run_sh_text
    assert "GIT_COMMIT_MISMATCH" in run_sh_text
    assert "GIT_COMMIT_DOC_ONLY_MISMATCH_ALLOWED" not in run_sh_text
    assert "WAREHOUSE_DATA_ROOT_MISSING" in run_sh_text
    assert "tools/check_completion_proxy.py" in run_sh_text
    assert "--login-url-on-failure" in run_sh_text
    assert "--json" in run_sh_text
    assert "pre_campaign_completion_preflight.v1.json" in run_sh_text
    assert "tools/write_completion_preflight_status.py" in run_sh_text
    assert "campaign_execution_marker.v1.json" in run_sh_text
    assert "scion.launcher_campaign_execution_marker.v1" in run_sh_text
    assert "CAMPAIGN_EXECUTION_MARKER:" in run_sh_text
    assert "write_postrun_acceptance_reports() {" in run_sh_text
    assert "--output \"$RUN_ROOT/run_status.json\"" in run_sh_text
    assert "--exit-code \"$PREFLIGHT_STATUS\"" in run_sh_text
    assert "--detail \"$PREFLIGHT_DETAIL\"" in run_sh_text
    assert "postrun_acceptance" in run_sh_text
    assert "tools/rebuild_postrun_acceptance.py" in run_sh_text
    assert "tools/check_postrun_acceptance.py" in run_sh_text
    assert "tools/write_postrun_wrapper_status.py" in run_sh_text
    assert "--strict" in run_sh_text
    assert "$REPORT_DIR/readiness/$REPORT_STEM.postrun_acceptance_readiness.v1.json" in (
        run_sh_text
    )
    assert "--require-current-run-ready" in run_sh_text
    assert '--report-stem "$REPORT_STEM"' in run_sh_text
    assert "--observed-control-arm" not in run_sh_text
    assert 'REPORT_STEM="warehouse_direct_v3"' in run_sh_text
    assert 'rebuild_args+=(--control-pair-key "$CONTROL_PAIR_KEY")' in run_sh_text
    assert "POSTRUN_REPORTS_EXIT_STATUS:$POSTRUN_STATUS" in run_sh_text
    assert "POSTRUN_READINESS_EXIT_STATUS:$POSTRUN_READINESS_STATUS" in run_sh_text
    assert "POSTRUN_ACCEPTANCE_FAILED:$POSTRUN_ACCEPTANCE_STATUS" in run_sh_text
    for removed_option in (
        "--proposal-runtime-mode",
        "--measurement-governance",
        "--proposal-context-ablation",
        "--disable-early-stop",
    ):
        assert removed_option not in command_txt
        assert removed_option not in run_sh_text
    assert "SCION_API_KEY=<set>" in command_txt
    assert (
        "GIT_RUNTIME_GUARD_PATHS="
        "scion/scion :(exclude)scion/scion/tests "
        "scion/tools scion/problems/warehouse_delivery surrogate" in command_txt
    )
    assert "POSTRUN_REPORTS=1" in command_txt
    assert "PROPOSAL_RUNTIME_MODE=direct_v3" in command_txt
    assert "CONTROL_PAIR_KEY=warehouse.unit-warehouse:prepared" in command_txt
    assert f"POSTRUN_REPORT_DIR={run_root / 'postrun_acceptance'}" in command_txt
    assert (
        f"PREPARED_RUN_MANIFEST={run_root / 'prepared_run_manifest.v1.json'}"
        in command_txt
    )
    assert f"PREPARED_HANDOFF_DIR={run_root / 'prepared_handoff'}" in command_txt

    prepared_handoff = run_root / "prepared_handoff"
    brief_json = (
        prepared_handoff
        / "analysis_brief"
        / "warehouse_direct_v3.prepared_analysis_brief.v1.json"
    )
    brief_md = (
        prepared_handoff
        / "analysis_brief"
        / "warehouse_direct_v3.prepared_analysis_brief.md"
    )
    inventory_json = (
        prepared_handoff
        / "inventory"
        / "warehouse_direct_v3.prepared_artifact_inventory.v1.json"
    )
    inventory_md = (
        prepared_handoff
        / "inventory"
        / "warehouse_direct_v3.prepared_artifact_inventory.md"
    )
    readiness_json = (
        prepared_handoff
        / "launch_readiness"
        / "warehouse_direct_v3.prepared_launch_readiness.v1.json"
    )
    readiness_md = (
        prepared_handoff
        / "launch_readiness"
        / "warehouse_direct_v3.prepared_launch_readiness.md"
    )
    prompt_context_json = (
        prepared_handoff
        / "prompt_context_readiness"
        / "warehouse_direct_v3.prepared_prompt_context_readiness.v1.json"
    )
    prompt_context_md = (
        prepared_handoff
        / "prompt_context_readiness"
        / "warehouse_direct_v3.prepared_prompt_context_readiness.md"
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
    assert prepared_brief["prepared_run_contract"][
        "problem_family"
    ] == "warehouse_delivery"
    assert prepared_brief["prepared_run_contract"]["research_focus"][
        "scope"
    ] == "report_only_prepared_handoff"
    assert prepared_inventory["lifecycle"]["prepared_only"] is True
    assert prepared_inventory["launcher"]["artifacts"]["prepared_handoff"] is True
    assert prepared_inventory["launcher"]["prepared_run_contract"]["checks"][
        "control_pair_key_present"
    ]["passed"] is True
    assert prepared_readiness["schema_version"] == "scion.launch_readiness.v1"
    assert prepared_readiness["static_ready"] is False
    assert prepared_readiness["launch_ready"] is False
    assert prepared_readiness["guarded_wrapper_launch_ready"] is False
    assert prepared_readiness["checks"]["prepared_contract_complete"][
        "status"
    ] == "failed"
    assert prepared_readiness["checks"]["completion_preflight"]["status"] == "skipped"
    assert prepared_prompt_context["schema_version"] == (
        "scion.prepared_prompt_context_readiness.v1"
    )
    assert prepared_prompt_context["report_only"] is True
    assert prepared_prompt_context["proposal_runtime"]["resolved_mode"] == (
        "direct_v3"
    )
    prompt_projection = prepared_prompt_context["signals"][
        "prepared_research_focus_projection"
    ]
    assert prompt_projection["required"] is True
    prompt_summary = prompt_projection["detail"]
    assert prompt_summary["contract_present"] is True
    assert prompt_summary["contract_source"] == "typed_manifest"
    assert prompt_summary["schema_valid"] is True
    assert prompt_summary["contract_schema_version"] == (
        "scion.warehouse_research_guidance_contract.v2"
    )
    assert prompt_summary["missing_rendered_paths"] == []
    assert (
        "guidance_blocks.warehouse_open_research_surfaces"
        in prompt_summary["rendered_paths"]
    )
    assert prepared_rebuild["schema_version"] == "scion.prepared_handoff_rebuild.v1"
    assert prepared_rebuild["complete"] is True
    assert prepared_rebuild["families"]["inventory"]["status"] == "ok"
    assert (
        prepared_rebuild["families"]["prompt_context_readiness"]["status"] == "ok"
    )
    readiness_text = readiness_md.read_text(encoding="utf-8")
    assert "guarded_wrapper_launch_ready=true" in readiness_text
    assert "duplicates the provider request" in readiness_text
    brief_md_text = brief_md.read_text(encoding="utf-8")
    assert "## Prepared Run Contract" in brief_md_text
    assert "## Launcher Artifacts" in inventory_md.read_text(encoding="utf-8")

    subprocess.run(["bash", "-n", str(run_sh)], check=True)


def test_warehouse_direct_launcher_can_copy_resume_campaign(tmp_path: Path) -> None:
    source_campaign = tmp_path / "source-campaign"
    (source_campaign / "champions" / "champion_v2").mkdir(parents=True)
    (source_campaign / "champions" / "champion_v2" / "registry.yaml").write_text(
        "operators: {}\n",
        encoding="utf-8",
    )
    (source_campaign / "scion.db").write_text("fake-db", encoding="utf-8")
    (source_campaign / "run_status.json").write_text(
        json.dumps({"status": "finished", "wrapper_exit_status": 0}),
        encoding="utf-8",
    )
    (source_campaign / "campaign_summary.json").write_text(
        json.dumps(
            {
                "run_complete": True,
                "branches": [{"id": "branch-a"}],
            }
        ),
        encoding="utf-8",
    )
    (source_campaign / "status.json").write_text(
        json.dumps(
            {
                "branches": [{"id": "branch-a"}],
                "cross_branch_research_summary": {
                    "research_shape_diagnostics": {
                        "schema_version": "campaign_research_shape_diagnostics.v1",
                        "policy": "summary_status_observability_only",
                        "advisory_only": True,
                        "decision_features_excluded": True,
                        "max_branch_depth": 2,
                        "mechanism_family_breadth": {
                            "family_count": 1,
                            "families": {"warehouse_route_rebalance": 1},
                        },
                        "active_research_shape_signal": {
                            "shape": "deep_focused",
                            "active_branch_count": 1,
                            "active_mechanism_families": [
                                "warehouse_route_rebalance"
                            ],
                        },
                        "proposal_guidance": [
                            "continue warehouse route rebalance evidence"
                        ],
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "2",
            "--label",
            "unit-warehouse-resume",
            "--experiments-root",
            str(tmp_path / "experiments"),
            "--warehouse-data-root",
            str(tmp_path / "data"),
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

    assert (run_root / "campaign" / "scion.db").read_text(encoding="utf-8") == "fake-db"
    assert (
        run_root / "campaign" / "champions" / "champion_v2" / "registry.yaml"
    ).is_file()
    assert not (run_root / "campaign" / "run_status.json").exists()
    assert not (run_root / "campaign" / "campaign_summary.json").exists()
    resume_snapshot = run_root / "resume_snapshot"
    assert (resume_snapshot / "campaign" / "run_status.json").is_file()
    assert (resume_snapshot / "campaign" / "campaign_summary.json").is_file()
    assert (resume_snapshot / "resume_source_manifest.v1.json").is_file()
    prepare_status = json.loads(
        (run_root / "run_status.json").read_text(encoding="utf-8")
    )
    assert prepare_status["status"] == "prepared"
    assert prepare_status["prepared_only"] is True
    assert prepare_status["resume_from_campaign"] == str(source_campaign)
    assert (
        prepare_status["resume_snapshot_ref"]
        == "resume_snapshot/resume_source_manifest.v1.json"
    )
    assert prepare_status["copied_campaign_status_present"] is True
    assert prepare_status["copied_campaign_summary_present"] is True
    prompt_context = json.loads(
        (
            run_root
            / "prepared_handoff"
            / "prompt_context_readiness"
            / "warehouse_direct_v3.prepared_prompt_context_readiness.v1.json"
        ).read_text(encoding="utf-8")
    )
    assert prompt_context["proposal_runtime"]["resolved_mode"] == "direct_v3"
    assert (
        prompt_context["signals"]["copied_campaign_status"]["detail"]["source_kind"]
        == "resume_snapshot"
    )
    assert (
        prompt_context["signals"]["copied_campaign_summary"]["detail"]["source_kind"]
        == "resume_snapshot"
    )
    launch_env = (run_root / "launch.env").read_text(encoding="utf-8")
    command_txt = (run_root / "command.txt").read_text(encoding="utf-8")
    assert f"RESUME_FROM_CAMPAIGN={source_campaign}" in launch_env
    assert f"RESUME_FROM_CAMPAIGN={source_campaign}" in command_txt


def test_warehouse_direct_launcher_api_key_env_avoids_secret_file(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "unit-warehouse-env",
            "--experiments-root",
            str(tmp_path),
            "--warehouse-data-root",
            str(tmp_path / "data"),
            "--api-key-env",
            "SCION_API_KEY",
            "--completion-preflight",
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
    assert "SCION_API_KEY=''" in launch_env
    assert "SCION_API_KEY_ENV=SCION_API_KEY" in launch_env
    assert "COMPLETION_PREFLIGHT=1" in launch_env
    assert "SCION_API_KEY=<from-env:SCION_API_KEY>" in command_txt
    run_sh_text = (run_root / "run.sh").read_text(encoding="utf-8")
    assert "tools/check_completion_proxy.py" in run_sh_text
    assert "pre_campaign_completion_preflight.v1.json" in run_sh_text
    assert "tools/write_completion_preflight_status.py" in run_sh_text


def test_warehouse_direct_launcher_api_key_env_missing_writes_valid_status(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "unit-warehouse-missing-key-env",
            "--experiments-root",
            str(tmp_path / "runs"),
            "--warehouse-data-root",
            str(tmp_path / "data"),
            "--api-key-env",
            "SCION_MISSING_TEST_KEY",
            "--python",
            sys.executable,
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


def test_warehouse_direct_launcher_missing_data_root_writes_valid_status(
    tmp_path: Path,
) -> None:
    missing_data_root = tmp_path / "missing-data-root"
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "unit-warehouse-missing-data",
            "--experiments-root",
            str(tmp_path / "runs"),
            "--warehouse-data-root",
            str(missing_data_root),
            "--python",
            sys.executable,
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
    _use_clean_git_guard_root(launch_env, tmp_path)

    run_result = subprocess.run(
        ["bash", str(run_root / "run.sh")],
        text=True,
        capture_output=True,
    )

    assert run_result.returncode == 64
    assert f"WAREHOUSE_DATA_ROOT_MISSING:{missing_data_root}" in (
        run_root / "exit.txt"
    ).read_text(encoding="utf-8")
    status = json.loads((run_root / "run_status.json").read_text(encoding="utf-8"))
    assert status["wrapper_exit_status"] == 64
    assert status["warehouse_data_root_missing"] is True
    run_log = (run_root / "run.log").read_text(encoding="utf-8")
    assert "POSTRUN_REPORTS_EXIT_STATUS:" in run_log
    assert "POSTRUN_READINESS_EXIT_STATUS:" in run_log
    readiness_dir = run_root / "postrun_acceptance" / "readiness"
    assert list(readiness_dir.glob("*.postrun_acceptance_readiness.v1.json"))


def test_warehouse_direct_launcher_can_skip_postrun_reports(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "unit-warehouse-no-reports",
            "--experiments-root",
            str(tmp_path),
            "--warehouse-data-root",
            str(tmp_path / "data"),
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


def test_warehouse_direct_launcher_fails_on_postrun_readiness_failure(
    tmp_path: Path,
) -> None:
    fake_python = tmp_path / "fake-python"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        "set -u\n"
        "if [[ \"${1:-}\" == \"-m\" ]]; then\n"
        "  exit 0\n"
        "fi\n"
        "case \"${1:-}\" in\n"
        "  */rebuild_postrun_acceptance.py)\n"
        "    exit 0\n"
        "    ;;\n"
        "  */check_postrun_acceptance.py)\n"
        "    if [[ \"$*\" == *\"--require-current-run-ready\"* ]]; then\n"
        "      printf '{\"current_run_analysis_ready\":false}\\n'\n"
        "      exit 64\n"
        "    fi\n"
        "    printf '# not ready\\n'\n"
        "    exit 0\n"
        "    ;;\n"
        "  */write_postrun_wrapper_status.py)\n"
        f"    exec {sys.executable} \"$@\"\n"
        "    ;;\n"
        "esac\n"
        "exit 0\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    data_root = tmp_path / "scion-data"
    (data_root / "production" / "generated").mkdir(parents=True)
    (data_root / "production" / "converted").mkdir(parents=True)

    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "unit-warehouse-postrun-not-ready",
            "--experiments-root",
            str(tmp_path / "runs"),
            "--warehouse-data-root",
            str(data_root),
            "--python",
            str(fake_python),
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
    _use_clean_git_guard_root(launch_env, tmp_path)

    run_result = subprocess.run(
        ["bash", str(run_root / "run.sh")],
        text=True,
        capture_output=True,
    )

    assert run_result.returncode == 64
    exit_text = (run_root / "exit.txt").read_text(encoding="utf-8")
    assert "WRAPPER_EXIT_STATUS:0" in exit_text
    assert "POSTRUN_ACCEPTANCE_FAILED:64" in exit_text
    assert "WRAPPER_EXIT_STATUS_EFFECTIVE:64" in exit_text
    status = json.loads((run_root / "run_status.json").read_text(encoding="utf-8"))
    assert status["wrapper_exit_status"] == 64
    assert status["campaign_wrapper_exit_status"] == 0
    assert status["postrun_acceptance_failed"] is True
    assert status["postrun_acceptance_status"] == "failed"
    assert status["postrun_reports_exit_status"] == 0
    assert status["postrun_readiness_exit_status"] == 64


def test_warehouse_direct_launcher_rejects_invalid_api_key_env() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "bad-env",
            "--api-key-env",
            "bad-name",
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "--api-key-env must be a valid shell environment variable name" in (
        result.stderr
    )
