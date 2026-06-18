#!/usr/bin/env python3
"""Rebuild report-only postrun acceptance artifacts for a Scion run root."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TOOLS_DIR = Path(__file__).resolve().parent
SCION_PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(SCION_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(SCION_PROJECT_DIR))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from postrun_analysis_brief import build_brief, render_markdown  # noqa: E402
from postrun_artifact_inventory import build_inventory, render_markdown as render_inventory_markdown  # noqa: E402
from scion.core.proposal_trajectory_artifacts import write_proposal_trajectory_manifest  # noqa: E402
from scion.core.research_efficiency_report import write_research_efficiency_report  # noqa: E402


SCHEMA_VERSION = "scion.postrun_acceptance_rebuild.v1"
DEFAULT_FAMILIES = (
    "summaries",
    "failures",
    "research_efficiency",
    "manifests",
    "analysis_brief",
    "inventory",
)
OBSERVED_CONTROL_ARMS = {"on", "record_only"}


def rebuild_postrun_acceptance(
    run_root: Path | str,
    *,
    report_stem: str | None = None,
    observed_control_arm: str | None = None,
    control_pair_key: str | None = None,
    strict: bool = False,
) -> dict[str, Any]:
    """Rebuild the standard postrun acceptance bundle for a run root.

    The rebuilt artifacts are report-only. Failures are recorded in the rebuild
    manifest instead of being silently treated as complete evidence.
    """

    resolved = _resolve_run_paths(Path(run_root).expanduser().resolve())
    root = resolved["run_root"]
    campaign_dir = resolved["campaign_dir"]
    prepared_manifest = _read_json(root / "prepared_run_manifest.v1.json")
    prepared_only = _is_prepared_only_root(root)
    preflight_failed = _is_pre_campaign_preflight_failed_root(root)
    skip_current_run_reports = prepared_only or preflight_failed
    stem = _resolve_report_stem(
        explicit=report_stem,
        run_root=root,
        prepared_manifest=prepared_manifest,
    )
    arm = _resolve_observed_control_arm(
        explicit=observed_control_arm,
        prepared_manifest=prepared_manifest,
    )
    pair_key = _resolve_control_pair_key(
        explicit=control_pair_key,
        prepared_manifest=prepared_manifest,
    )

    report_dir = root / "postrun_acceptance"
    for family in (*DEFAULT_FAMILIES, "rebuild"):
        (report_dir / family).mkdir(parents=True, exist_ok=True)

    family_results: dict[str, dict[str, Any]] = {}
    if skip_current_run_reports:
        skip_reason = _current_run_skip_reason(
            prepared_only=prepared_only,
            preflight_failed=preflight_failed,
        )
        family_results["summaries"] = _skipped_family("summary", skip_reason)
        family_results["failures"] = _skipped_family("failures", skip_reason)
        family_results["research_efficiency"] = _skipped_family(
            "research_efficiency",
            skip_reason,
        )
        family_results["manifests"] = _skipped_family("manifests", skip_reason)
    else:
        family_results["summaries"] = _run_cli_report(
            "summary",
            [
                "report",
                "summary",
                "--campaign-dir",
                str(campaign_dir),
                "--output",
                str(report_dir / "summaries" / f"{stem}.summary.json"),
            ],
            outputs=[report_dir / "summaries" / f"{stem}.summary.json"],
        )
        family_results["failures"] = _run_cli_report(
            "failures",
            [
                "report",
                "failures",
                "--campaign-dir",
                str(campaign_dir),
                "--output",
                str(report_dir / "failures" / f"{stem}.failures.json"),
            ],
            outputs=[report_dir / "failures" / f"{stem}.failures.json"],
        )
        family_results["research_efficiency"] = _write_family(
            "research_efficiency",
            [
                report_dir
                / "research_efficiency"
                / f"{stem}.research_efficiency.v1.json"
            ],
            lambda: write_research_efficiency_report(
                campaign_dir,
                output_path=report_dir
                / "research_efficiency"
                / f"{stem}.research_efficiency.v1.json",
            ),
        )
        family_results["manifests"] = _write_family(
            "manifests",
            [
                report_dir
                / "manifests"
                / f"{stem}.proposal_trajectory_manifest.v1.json"
            ],
            lambda: write_proposal_trajectory_manifest(
                campaign_dir,
                observed_control_arm=arm,
                control_pair_key=pair_key,
                output_path=report_dir
                / "manifests"
                / f"{stem}.proposal_trajectory_manifest.v1.json",
            ),
        )
    family_results["analysis_brief"] = _write_family(
        "analysis_brief",
        [
            report_dir / "analysis_brief" / f"{stem}.postrun_analysis_brief.v1.json",
            report_dir / "analysis_brief" / f"{stem}.postrun_analysis_brief.md",
        ],
        lambda: _write_analysis_brief(root, report_dir, stem),
    )
    family_results["inventory"] = _write_family(
        "inventory",
        [
            report_dir / "inventory" / f"{stem}.postrun_artifact_inventory.v1.json",
            report_dir / "inventory" / f"{stem}.postrun_artifact_inventory.md",
        ],
        lambda: _write_inventory(root, report_dir, stem),
    )

    complete = all(
        result.get("status") == "ok" for result in family_results.values()
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "postrun_acceptance_rebuild",
        "generated_at": _utc_now_iso(),
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
        "run_root": str(root),
        "campaign_dir": str(campaign_dir),
        "report_dir": str(report_dir),
        "report_stem": stem,
        "observed_control_arm": arm,
        "control_pair_key": pair_key,
        "prepared_only": prepared_only,
        "pre_campaign_completion_preflight_failed": preflight_failed,
        "current_run_reports_skipped": skip_current_run_reports,
        "current_run_skip_reason": (
            _current_run_skip_reason(
                prepared_only=prepared_only,
                preflight_failed=preflight_failed,
            )
            if skip_current_run_reports
            else ""
        ),
        "complete": complete,
        "families": family_results,
    }
    manifest_path = report_dir / "rebuild" / "rebuild_manifest.v1.json"
    manifest_path.write_text(_stable_json(manifest), encoding="utf-8")
    if family_results.get("inventory", {}).get("status") == "ok":
        family_results["inventory"] = _write_family(
            "inventory",
            [
                report_dir
                / "inventory"
                / f"{stem}.postrun_artifact_inventory.v1.json",
                report_dir / "inventory" / f"{stem}.postrun_artifact_inventory.md",
            ],
            lambda: _write_inventory(root, report_dir, stem),
        )
        manifest["families"] = family_results
        manifest["complete"] = all(
            result.get("status") == "ok" for result in family_results.values()
        )
        manifest_path.write_text(_stable_json(manifest), encoding="utf-8")
        complete = bool(manifest["complete"])
    if strict and not complete:
        failed = ", ".join(
            name
            for name, result in sorted(family_results.items())
            if result.get("status") != "ok"
        )
        raise RuntimeError(f"postrun acceptance rebuild incomplete: {failed}")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_root", help="Run root, or campaign directory.")
    parser.add_argument("--report-stem", help="Filename stem for rebuilt reports.")
    parser.add_argument(
        "--observed-control-arm",
        choices=sorted(OBSERVED_CONTROL_ARMS),
        help="Observed measurement-control arm for proposal trajectory manifests.",
    )
    parser.add_argument(
        "--control-pair-key",
        help="Optional report-only control-pair key.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any report family fails to rebuild.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="text",
        help="Output format for the rebuild manifest summary.",
    )
    args = parser.parse_args(argv)

    try:
        manifest = rebuild_postrun_acceptance(
            args.run_root,
            report_stem=args.report_stem,
            observed_control_arm=args.observed_control_arm,
            control_pair_key=args.control_pair_key,
            strict=args.strict,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        print(_stable_json(manifest), end="")
        return 0 if manifest["complete"] or not args.strict else 1

    print(f"POSTRUN_ACCEPTANCE_REBUILD={manifest['report_dir']}")
    print(f"COMPLETE={int(bool(manifest['complete']))}")
    for family, result in sorted(manifest["families"].items()):
        print(f"{family}={result.get('status')}")
    return 0 if manifest["complete"] or not args.strict else 1


def _resolve_run_paths(path: Path) -> dict[str, Path]:
    if (path / "campaign").is_dir():
        return {"run_root": path, "campaign_dir": path / "campaign"}
    if _looks_like_campaign_dir(path):
        return {"run_root": path.parent, "campaign_dir": path}
    nested = path / "campaign"
    return {"run_root": path, "campaign_dir": nested}


def _looks_like_campaign_dir(path: Path) -> bool:
    return any(
        (path / name).exists()
        for name in ("campaign_summary.json", "status.json", "scion.db", "artifacts")
    )


def _is_prepared_only_root(run_root: Path) -> bool:
    status = _read_json(run_root / "run_status.json")
    if not isinstance(status, dict):
        return False
    return (
        status.get("prepared_only") is True
        or (
            status.get("schema") == "scion.launcher_prepare.v1"
            and status.get("status") == "prepared"
        )
    )


def _is_pre_campaign_preflight_failed_root(run_root: Path) -> bool:
    status = _read_json(run_root / "run_status.json")
    manifest = _read_json(run_root / "prepared_run_manifest.v1.json")
    if not isinstance(status, dict) or not isinstance(manifest, dict):
        return False
    return (
        status.get("pre_campaign_completion_preflight") == "failed"
        and manifest.get("schema_version") == "scion.launcher_prepared_run_manifest.v1"
    )


def _current_run_skip_reason(
    *,
    prepared_only: bool,
    preflight_failed: bool,
) -> str:
    if preflight_failed:
        return (
            "pre_campaign_completion_preflight_failed: copied campaign artifacts "
            "are resume input, not current-run postrun evidence"
        )
    if prepared_only:
        return (
            "prepared_only_not_launched: copied campaign artifacts are launch "
            "input, not current-run postrun evidence"
        )
    return ""


def _resolve_report_stem(
    *,
    explicit: str | None,
    run_root: Path,
    prepared_manifest: Any,
) -> str:
    if explicit:
        return _safe_stem(explicit)
    manifest = prepared_manifest if isinstance(prepared_manifest, dict) else {}
    problem = _problem_prefix(manifest.get("problem_family"))
    execution = manifest.get("execution")
    if isinstance(execution, dict):
        governance = str(execution.get("measurement_governance") or "on").replace(
            "-",
            "_",
        )
        ablation = str(
            execution.get("proposal_context_ablation") or "full"
        ).replace("-", "_")
        return _safe_stem(f"{problem}_{governance}_{ablation}")
    return _safe_stem(run_root.name)


def _resolve_observed_control_arm(
    *,
    explicit: str | None,
    prepared_manifest: Any,
) -> str:
    if explicit:
        return explicit
    manifest = prepared_manifest if isinstance(prepared_manifest, dict) else {}
    execution = manifest.get("execution")
    if isinstance(execution, dict):
        arm = str(execution.get("measurement_governance") or "").replace("-", "_")
        if arm in OBSERVED_CONTROL_ARMS:
            return arm
    return "on"


def _resolve_control_pair_key(
    *,
    explicit: str | None,
    prepared_manifest: Any,
) -> str | None:
    if explicit is not None:
        return explicit
    manifest = prepared_manifest if isinstance(prepared_manifest, dict) else {}
    metadata = manifest.get("report_metadata")
    if isinstance(metadata, dict):
        value = metadata.get("control_pair_key")
        if value:
            return str(value)
    return None


def _problem_prefix(value: Any) -> str:
    text = str(value or "").strip().lower()
    if "warehouse" in text:
        return "warehouse"
    if "cvrp" in text or "vrp" in text:
        return "cvrp"
    return "scion"


def _safe_stem(value: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    stem = stem.strip("._-")
    return stem or "postrun"


def _run_cli_report(
    label: str,
    args: list[str],
    *,
    outputs: list[Path],
) -> dict[str, Any]:
    env = os.environ.copy()
    old_path = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{SCION_PROJECT_DIR}{os.pathsep}{old_path}" if old_path else str(SCION_PROJECT_DIR)
    )
    result = subprocess.run(
        [sys.executable, "-m", "scion.cli.main", *args],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    return _family_result(
        label,
        status="ok" if result.returncode == 0 and all(path.exists() for path in outputs) else "failed",
        outputs=outputs,
        command=[sys.executable, "-m", "scion.cli.main", *args],
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def _write_family(
    label: str,
    outputs: list[Path],
    writer: Any,
) -> dict[str, Any]:
    try:
        writer()
    except Exception as exc:
        return _family_result(
            label,
            status="failed",
            outputs=outputs,
            error=f"{type(exc).__name__}: {exc}",
        )
    return _family_result(
        label,
        status="ok" if all(path.exists() for path in outputs) else "failed",
        outputs=outputs,
    )


def _skipped_family(label: str, reason: str) -> dict[str, Any]:
    return _family_result(
        label,
        status="skipped",
        outputs=[],
        error=reason,
    )


def _write_analysis_brief(run_root: Path, report_dir: Path, stem: str) -> None:
    brief = build_brief(run_root)
    json_path = report_dir / "analysis_brief" / f"{stem}.postrun_analysis_brief.v1.json"
    md_path = report_dir / "analysis_brief" / f"{stem}.postrun_analysis_brief.md"
    json_path.write_text(_stable_json(brief), encoding="utf-8")
    md_path.write_text(render_markdown(brief), encoding="utf-8")


def _write_inventory(run_root: Path, report_dir: Path, stem: str) -> None:
    inventory = build_inventory(run_root)
    json_path = (
        report_dir / "inventory" / f"{stem}.postrun_artifact_inventory.v1.json"
    )
    md_path = report_dir / "inventory" / f"{stem}.postrun_artifact_inventory.md"
    json_path.write_text(_stable_json(inventory), encoding="utf-8")
    md_path.write_text(render_inventory_markdown(inventory), encoding="utf-8")


def _family_result(
    label: str,
    *,
    status: str,
    outputs: list[Path],
    command: list[str] | None = None,
    returncode: int | None = None,
    stdout: str = "",
    stderr: str = "",
    error: str = "",
) -> dict[str, Any]:
    return {
        "status": status,
        "label": label,
        "outputs": [str(path) for path in outputs],
        "outputs_present": {str(path): path.exists() for path in outputs},
        "command": command or [],
        "returncode": returncode,
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
        "error": error,
    }


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _stable_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def _tail(text: str, limit: int = 2000) -> str:
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[-limit:]


if __name__ == "__main__":
    raise SystemExit(main())
