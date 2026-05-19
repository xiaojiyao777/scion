"""Data models for solver-design runtime smoke."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class _RuntimeSmokeCase:
    label: str
    rel_path: str
    seed: int
    path: Path
    data_root: str | None = None
    data_root_source: str = "unknown"
    data_root_status: str = "unresolved"
    case_source: str = "runtime_smoke_manifest"
