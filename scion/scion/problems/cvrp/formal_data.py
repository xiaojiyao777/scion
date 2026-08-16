"""CVRP split-data prerequisite checks."""

from __future__ import annotations

from pathlib import Path

from scion.cli.commands.data_roots import (
    missing_problem_data_cases,
    resolve_problem_data_case,
)
from scion.config.split_manifest import SplitManifest


STAGES = ("screening", "validation", "frozen", "canary")


def check_formal_data(
    *,
    problem_path: Path,
    split_path: Path,
    data_root: Path,
) -> dict[str, object]:
    """Check that every declared case and required solution file is usable."""

    problem_path = problem_path.expanduser().resolve(strict=False)
    split_path = split_path.expanduser().resolve(strict=False)
    data_root = data_root.expanduser().resolve(strict=False)
    manifest = SplitManifest.from_yaml(split_path)
    missing = missing_problem_data_cases(
        problem_yaml=problem_path,
        split_manifest=manifest,
        data_roots=(data_root,),
    )
    counts = {stage: len(getattr(manifest, stage) or ()) for stage in STAGES}
    checked_files: list[str] = []
    missing_companions: list[str] = []
    unsafe_files: list[str] = []
    for stage in STAGES:
        for case in getattr(manifest, stage) or ():
            resolved = resolve_problem_data_case(
                case,
                problem_dir=problem_path.parent,
                data_roots=(data_root,),
            )
            if resolved is None:
                continue
            _check_file(
                resolved,
                relative_path=str(case),
                checked_files=checked_files,
                unsafe_files=unsafe_files,
            )
            if str(case).startswith("cvrplib/") and resolved.suffix == ".vrp":
                companion = resolved.with_suffix(".sol")
                companion_relative = str(Path(case).with_suffix(".sol"))
                if not companion.is_file() or companion.is_symlink():
                    missing_companions.append(companion_relative)
                    continue
                _check_file(
                    companion,
                    relative_path=companion_relative,
                    checked_files=checked_files,
                    unsafe_files=unsafe_files,
                )
    return {
        "ok": not missing and not missing_companions and not unsafe_files,
        "problem": str(problem_path),
        "split": str(split_path),
        "data_root": str(data_root),
        "case_counts": counts,
        "declared_case_count": sum(counts.values()),
        "missing_case_count": len(missing),
        "missing_cases": missing,
        "missing_companion_count": len(missing_companions),
        "missing_companions": missing_companions,
        "unsafe_file_count": len(unsafe_files),
        "unsafe_files": unsafe_files,
        "checked_file_count": len(checked_files),
        "checked_files": checked_files,
    }


def _check_file(
    path: Path,
    *,
    relative_path: str,
    checked_files: list[str],
    unsafe_files: list[str],
) -> None:
    if not path.is_file() or path.is_symlink():
        unsafe_files.append(relative_path)
        return
    with path.open("rb") as handle:
        handle.read(1)
    checked_files.append(relative_path)


__all__ = ("STAGES", "check_formal_data")
