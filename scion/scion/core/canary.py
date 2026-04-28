"""Canary set versioning (W12).

Tracks canary set versions so accumulated failure cases enter the next
campaign's canary pool, not the current one. This prevents retroactive
semantic changes mid-campaign.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class CanarySetVersion:
    version: str
    cases: List[str]
    accumulated_candidates: List[str] = field(default_factory=list)

    def add_candidate(self, case_path: str, reason: str) -> None:
        entry = f"{case_path} ({reason})"
        if entry not in self.accumulated_candidates:
            self.accumulated_candidates.append(entry)

    def export_next_version(self, new_version: str) -> "CanarySetVersion":
        """Create the next version's canary set, merging accumulated candidates."""
        new_cases = list(self.cases)
        for entry in self.accumulated_candidates:
            path = entry.split(" (")[0]
            if path not in new_cases:
                new_cases.append(path)
        return CanarySetVersion(version=new_version, cases=new_cases)
