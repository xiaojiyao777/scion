from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scion.postrun.inventory import PreparedRunContractInventoryPort
from scion.postrun.inventory import prepared_contract


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


def test_prepared_contract_port_source_is_problem_neutral() -> None:
    source = Path(prepared_contract.__file__).read_text(encoding="utf-8").lower()

    forbidden_tokens = (
        "cvrp",
        "vrp",
        "cmt",
        "large_twoopt",
        "large-twoopt",
        "alns",
        "vns",
        "warehouse",
        "plateau",
    )
    assert not [token for token in forbidden_tokens if token in source]


def test_prepared_contract_port_builds_legacy_generic_contract(tmp_path: Path) -> None:
    repo_dir = Path(__file__).resolve().parents[4]
    scion_project_dir = repo_dir / "scion"
    run_root = tmp_path / "prepared-run"
    campaign_dir = run_root / "campaign"
    config_dir = run_root / "config"
    campaign_dir.mkdir(parents=True)
    config_dir.mkdir()
    for name in ("problem.yaml", "protocol.yaml", "split.yaml", "seeds.yaml"):
        (config_dir / name).write_text("ok: true\n", encoding="utf-8")

    command = (
        f"python -m scion.cli.main run "
        f"--problem {config_dir / 'problem.yaml'} "
        f"--protocol {config_dir / 'protocol.yaml'} "
        f"--split {config_dir / 'split.yaml'} "
        f"--seeds {config_dir / 'seeds.yaml'} "
        f"--campaign-dir {campaign_dir} --rounds 1 --disable-early-stop"
    )
    manifest_path = run_root / "prepared_run_manifest.v1.json"
    manifest = {
        "schema_version": "scion.launcher_prepared_run_manifest.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
        "run_root": str(run_root),
        "campaign_dir": str(campaign_dir),
        "analysis_intent": "Prepared generic analysis intent.",
        "acceptance_focus": ["Keep evidence out of DecisionFeatures."],
        "command": command,
        "model": {"name": "gpt-5.5", "completion_preflight": True},
        "git": {
            "commit": _git_head_short(repo_dir),
            "runtime_guard_paths": "scion/tools",
        },
        "config": {
            "problem": str(config_dir / "problem.yaml"),
            "protocol": str(config_dir / "protocol.yaml"),
            "split": str(config_dir / "split.yaml"),
            "seeds": str(config_dir / "seeds.yaml"),
        },
        "execution": {"rounds": 1, "disable_early_stop": True},
        "report_metadata": {
            "control_pair_key": "fixture.prepared:rep01",
            "postrun_reports": True,
            "postrun_acceptance_families": list(POSTRUN_REPORT_DIRS),
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (run_root / "command.txt").write_text(
        f"PREPARED_RUN_MANIFEST={manifest_path}\n\ncommand:\n{command}\n",
        encoding="utf-8",
    )

    result = PreparedRunContractInventoryPort(
        repo_dir=repo_dir,
        scion_project_dir=scion_project_dir,
        postrun_report_dirs=POSTRUN_REPORT_DIRS,
    ).build(
        run_root,
        inferred_problem_family={
            "problem_family": "fixture_problem",
            "source": "fixture",
            "evidence": "unit",
        },
    )

    contract = result.contract
    assert contract["schema_version"] == "scion.prepared_run_contract_inventory.v1"
    assert contract["report_only"] is True
    assert contract["quality_judgment"] is False
    assert contract["decision_features_excluded"] is True
    assert contract["contract_complete"] is True
    assert contract["problem_family"] == "fixture_problem"
    assert contract["problem_family_inferred"] is True
    assert contract["model"] == "gpt-5.5"
    assert contract["execution"]["rounds"] == 1
    assert contract["checks"]["manifest_schema"]["passed"] is True
    assert contract["checks"]["config_paths_resolvable"]["passed"] is True
    assert contract["checks"]["git_runtime_consistent"]["passed"] is True


def _git_head_short(repo_dir: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_dir), "rev-parse", "--short", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()
