"""Formal CVRP split-data identity owned by the CVRP problem package."""

from __future__ import annotations

import hashlib
from pathlib import Path

from scion.cli.commands.data_roots import (
    missing_problem_data_cases,
    resolve_problem_data_case,
)
from scion.config.split_manifest import SplitManifest


SCHEMA = "scion.cvrp_formal_data_identity.v1"
STAGES = ("screening", "validation", "frozen", "canary")


def build_formal_data_identity(
    *,
    problem_path: Path,
    split_path: Path,
    data_root: Path,
) -> dict[str, object]:
    """Build a deterministic identity for every formal case and CVRPLIB solution."""

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
    identities: list[dict[str, object]] = []
    missing_companions: list[str] = []
    unsafe_files: list[str] = []
    identity_lines: list[str] = []
    for stage in STAGES:
        for case in getattr(manifest, stage) or ():
            resolved = resolve_problem_data_case(
                case,
                problem_dir=problem_path.parent,
                data_roots=(data_root,),
            )
            if resolved is None:
                continue
            _append_identity(
                identities,
                identity_lines,
                stage=stage,
                kind="vrp",
                relative_path=case,
                path=resolved,
                unsafe_files=unsafe_files,
            )
            if str(case).startswith("cvrplib/") and resolved.suffix == ".vrp":
                companion = resolved.with_suffix(".sol")
                companion_relative = str(Path(case).with_suffix(".sol"))
                if not companion.is_file() or companion.is_symlink():
                    missing_companions.append(companion_relative)
                    continue
                _append_identity(
                    identities,
                    identity_lines,
                    stage=stage,
                    kind="sol",
                    relative_path=companion_relative,
                    path=companion,
                    unsafe_files=unsafe_files,
                )
    identity_sha256 = hashlib.sha256("".join(identity_lines).encode()).hexdigest()
    return {
        "schema": SCHEMA,
        "ok": not missing and not missing_companions and not unsafe_files,
        "problem": str(problem_path),
        "split": str(split_path),
        "split_sha256": hashlib.sha256(split_path.read_bytes()).hexdigest(),
        "data_root": str(data_root),
        "case_counts": counts,
        "declared_case_count": sum(counts.values()),
        "missing_case_count": len(missing),
        "missing_cases": missing,
        "missing_companion_count": len(missing_companions),
        "missing_companions": missing_companions,
        "unsafe_file_count": len(unsafe_files),
        "unsafe_files": unsafe_files,
        "identity_file_count": len(identities),
        "identity_sha256": identity_sha256,
        "files": identities,
    }


def _append_identity(
    identities: list[dict[str, object]],
    identity_lines: list[str],
    *,
    stage: str,
    kind: str,
    relative_path: str,
    path: Path,
    unsafe_files: list[str],
) -> None:
    if not path.is_file() or path.is_symlink():
        unsafe_files.append(relative_path)
        return
    content = path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    size = len(content)
    identities.append(
        {
            "stage": stage,
            "kind": kind,
            "relative_path": relative_path,
            "resolved_path": str(path.resolve(strict=True)),
            "bytes": size,
            "sha256": digest,
        }
    )
    identity_lines.append(
        f"{stage}\t{kind}\t{digest}\t{size}\t{relative_path}\n"
    )


__all__ = ("SCHEMA", "STAGES", "build_formal_data_identity")
