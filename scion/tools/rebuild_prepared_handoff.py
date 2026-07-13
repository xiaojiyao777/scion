#!/usr/bin/env python3
"""Rebuild report-only prepared handoff artifacts for a Scion launch root."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

TOOLS_DIR = Path(__file__).resolve().parent
SCION_PROJECT_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = Path(__file__).resolve().parents[2]
if str(SCION_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(SCION_PROJECT_DIR))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from check_launch_readiness import (  # noqa: E402
    build_readiness,
    render_markdown as render_readiness_markdown,
)
from postrun_analysis_brief import (  # noqa: E402
    build_brief,
    render_markdown as render_brief_markdown,
)
from postrun_artifact_inventory import (  # noqa: E402
    render_markdown as render_inventory_markdown,
)
from scion.postrun.handoff.prompt_context_readiness import (  # noqa: E402
    build_prepared_prompt_context_readiness,
    render_prompt_context_readiness_markdown,
)
from scion.postrun.inventory.prepared_contract import (  # noqa: E402
    prepared_execution_runtime_mode,
)
from scion.problems.postrun_inventory import (
    build_problem_inventory as build_inventory,
)  # noqa: E402

SCHEMA_VERSION = "scion.prepared_handoff_rebuild.v1"
DEFAULT_FAMILIES = (
    "analysis_brief",
    "inventory",
    "prompt_context_readiness",
    "launch_readiness",
)


def rebuild_prepared_handoff(
    run_root: Path | str,
    *,
    report_stem: str | None = None,
    strict: bool = False,
) -> dict[str, Any]:
    """Rebuild prepared handoff artifacts without starting a campaign."""

    root = Path(run_root).expanduser().resolve()
    manifest = _read_json(root / "prepared_run_manifest.v1.json")
    manifest_dict = manifest if isinstance(manifest, dict) else {}
    execution = manifest_dict.get("execution")
    execution_dict = execution if isinstance(execution, dict) else {}
    try:
        proposal_runtime_mode = prepared_execution_runtime_mode(execution_dict)
        proposal_runtime_status = "resolved"
        proposal_runtime_error = None
    except ValueError as exc:
        proposal_runtime_mode = None
        proposal_runtime_status = "invalid"
        proposal_runtime_error = str(exc)
    stem = report_stem or _resolve_report_stem(root, manifest)

    handoff_dir = root / "prepared_handoff"
    brief_dir = handoff_dir / "analysis_brief"
    inventory_dir = handoff_dir / "inventory"
    prompt_context_dir = handoff_dir / "prompt_context_readiness"
    readiness_dir = handoff_dir / "launch_readiness"
    rebuild_dir = handoff_dir / "rebuild"
    for path in (
        brief_dir,
        inventory_dir,
        prompt_context_dir,
        readiness_dir,
        rebuild_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
    _clear_generated_family_outputs(handoff_dir, DEFAULT_FAMILIES)

    family_results: dict[str, dict[str, Any]] = {}
    family_results["analysis_brief"] = _write_family(
        [
            brief_dir / f"{stem}.prepared_analysis_brief.v1.json",
            brief_dir / f"{stem}.prepared_analysis_brief.md",
        ],
        lambda: _write_analysis_brief(root, brief_dir, stem),
    )
    family_results["inventory"] = _write_family(
        [
            inventory_dir / f"{stem}.prepared_artifact_inventory.v1.json",
            inventory_dir / f"{stem}.prepared_artifact_inventory.md",
        ],
        lambda: _write_inventory(root, inventory_dir, stem),
    )
    family_results["prompt_context_readiness"] = _write_family(
        [
            prompt_context_dir / f"{stem}.prepared_prompt_context_readiness.v1.json",
            prompt_context_dir / f"{stem}.prepared_prompt_context_readiness.md",
        ],
        lambda: _write_prompt_context_readiness(root, prompt_context_dir, stem),
    )
    family_results["launch_readiness"] = _write_family(
        [
            readiness_dir / f"{stem}.prepared_launch_readiness.v1.json",
            readiness_dir / f"{stem}.prepared_launch_readiness.md",
        ],
        lambda: _write_launch_readiness(root, readiness_dir, stem),
    )

    complete = (
        proposal_runtime_status == "resolved"
        and all(result.get("status") == "ok" for result in family_results.values())
    )
    rebuild_manifest = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "prepared_handoff_rebuild",
        "generated_at": _utc_now_iso(),
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
        "run_root": str(root),
        "prepared_handoff_dir": str(handoff_dir),
        "report_stem": stem,
        "problem_family": (
            manifest.get("problem_family") if isinstance(manifest, dict) else None
        ),
        "proposal_runtime": {
            "status": proposal_runtime_status,
            "resolved_mode": proposal_runtime_mode,
            "error": proposal_runtime_error,
            "fail_closed": proposal_runtime_status != "resolved",
        },
        "prepared_manifest_commit": _manifest_commit(manifest),
        "checkout_commit": _git_output(("rev-parse", "--short", "HEAD")),
        "families": family_results,
        "complete": complete,
    }
    manifest_path = rebuild_dir / "prepared_handoff_rebuild.v1.json"
    manifest_path.write_text(_stable_json(rebuild_manifest), encoding="utf-8")
    if family_results.get("launch_readiness", {}).get("status") == "ok":
        family_results["launch_readiness"] = _write_family(
            [
                readiness_dir / f"{stem}.prepared_launch_readiness.v1.json",
                readiness_dir / f"{stem}.prepared_launch_readiness.md",
            ],
            lambda: _write_launch_readiness(root, readiness_dir, stem),
        )
        rebuild_manifest["families"] = family_results
        rebuild_manifest["complete"] = (
            proposal_runtime_status == "resolved"
            and all(
                result.get("status") == "ok"
                for result in family_results.values()
            )
        )
        manifest_path.write_text(_stable_json(rebuild_manifest), encoding="utf-8")
        complete = bool(rebuild_manifest["complete"])
    if strict and not complete:
        failed = ", ".join(
            name
            for name, result in sorted(family_results.items())
            if result.get("status") != "ok"
        )
        raise RuntimeError(f"prepared handoff rebuild incomplete: {failed}")
    return rebuild_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_root", help="Prepared launch root.")
    parser.add_argument(
        "--report-stem", help="Filename stem for rebuilt handoff files."
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any handoff family fails to rebuild.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="text",
        help="Output format for the rebuild summary.",
    )
    args = parser.parse_args(argv)

    try:
        manifest = rebuild_prepared_handoff(
            args.run_root,
            report_stem=args.report_stem,
            strict=args.strict,
        )
    except Exception as exc:  # noqa: BLE001
        if args.format == "json":
            print(
                json.dumps(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "complete": False,
                        "error": str(exc),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print(f"prepared handoff rebuild failed: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        print(json.dumps(manifest, indent=2, sort_keys=True))
    else:
        print(f"prepared_handoff_rebuild_complete={manifest['complete']}")
        print(f"prepared_handoff_dir={manifest['prepared_handoff_dir']}")
        print(f"report_stem={manifest['report_stem']}")
        for name, result in sorted(manifest["families"].items()):
            print(f"{name}={result.get('status')}")
    return 0 if manifest["complete"] else 1


def _write_analysis_brief(root: Path, brief_dir: Path, stem: str) -> None:
    brief = build_brief(root)
    (brief_dir / f"{stem}.prepared_analysis_brief.v1.json").write_text(
        _stable_json(brief),
        encoding="utf-8",
    )
    (brief_dir / f"{stem}.prepared_analysis_brief.md").write_text(
        render_brief_markdown(brief),
        encoding="utf-8",
    )


def _write_inventory(root: Path, inventory_dir: Path, stem: str) -> None:
    inventory = build_inventory(root)
    (inventory_dir / f"{stem}.prepared_artifact_inventory.v1.json").write_text(
        _stable_json(inventory),
        encoding="utf-8",
    )
    (inventory_dir / f"{stem}.prepared_artifact_inventory.md").write_text(
        render_inventory_markdown(inventory),
        encoding="utf-8",
    )


def _write_prompt_context_readiness(
    root: Path,
    prompt_context_dir: Path,
    stem: str,
) -> None:
    report = build_prepared_prompt_context_readiness(root)
    (
        prompt_context_dir / f"{stem}.prepared_prompt_context_readiness.v1.json"
    ).write_text(
        _stable_json(report),
        encoding="utf-8",
    )
    (prompt_context_dir / f"{stem}.prepared_prompt_context_readiness.md").write_text(
        render_prompt_context_readiness_markdown(report),
        encoding="utf-8",
    )


def _write_launch_readiness(root: Path, readiness_dir: Path, stem: str) -> None:
    readiness = build_readiness(root)
    (readiness_dir / f"{stem}.prepared_launch_readiness.v1.json").write_text(
        _stable_json(readiness),
        encoding="utf-8",
    )
    (readiness_dir / f"{stem}.prepared_launch_readiness.md").write_text(
        render_readiness_markdown(readiness),
        encoding="utf-8",
    )


def _write_family(
    outputs: list[Path],
    writer: Callable[[], None],
) -> dict[str, Any]:
    try:
        writer()
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "failed",
            "error": str(exc),
            "outputs": [str(path) for path in outputs],
            "outputs_present": {str(path): path.exists() for path in outputs},
        }
    return {
        "status": "ok" if all(path.exists() for path in outputs) else "failed",
        "outputs": [str(path) for path in outputs],
        "outputs_present": {str(path): path.exists() for path in outputs},
    }


def _clear_generated_family_outputs(
    handoff_dir: Path,
    families: tuple[str, ...],
) -> None:
    """Remove stale generated handoff files before rebuilding a fresh bundle."""

    for family in families:
        family_dir = handoff_dir / family
        if not family_dir.exists():
            continue
        for path in family_dir.iterdir():
            if path.is_file() and path.suffix in {".json", ".md"}:
                path.unlink()


def _resolve_report_stem(root: Path, manifest: Any) -> str:
    if isinstance(manifest, dict):
        family = str(manifest.get("problem_family") or "").strip()
        prefix = {
            "cvrp": "cvrp",
            "warehouse_delivery": "warehouse",
        }.get(family, _safe_slug(family) or _safe_slug(root.name))
        return f"{prefix}_direct_v3"
    return _safe_slug(root.name) or "prepared_handoff"


def _safe_slug(value: str) -> str:
    cleaned = []
    for char in value.strip().lower():
        if char.isalnum() or char == "_":
            cleaned.append(char)
        elif char in {"-", ".", " "}:
            cleaned.append("_")
    slug = "".join(cleaned).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _manifest_commit(manifest: Any) -> str | None:
    if not isinstance(manifest, dict):
        return None
    git = manifest.get("git")
    if not isinstance(git, dict):
        return None
    commit = git.get("commit")
    return str(commit) if commit else None


def _git_output(args: tuple[str, ...]) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(REPO_DIR), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _stable_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
