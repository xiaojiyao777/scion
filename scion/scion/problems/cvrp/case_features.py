"""CVRPLIB filename features owned by the CVRP problem package."""

from __future__ import annotations

import re
from pathlib import Path

_CVRPLIB_DIMENSION_RE = re.compile(
    r"(?:^|-)n(?P<dimension>\d+)(?:-|$)",
    re.IGNORECASE,
)


def extract_case_features(case_path: str) -> dict[str, int | str]:
    """Project proposal-visible size facts encoded by CVRPLIB filenames."""

    stem = Path(case_path).stem
    match = _CVRPLIB_DIMENSION_RE.search(stem)
    if match is None:
        return {}
    dimension = int(match.group("dimension"))
    if dimension <= 100:
        size_bucket = "n_le_100"
    elif dimension <= 149:
        size_bucket = "n_101_149"
    elif dimension <= 250:
        size_bucket = "n_150_250"
    else:
        size_bucket = "n_ge_251"
    return {
        "dimension": dimension,
        "size_bucket": size_bucket,
    }


__all__ = ["extract_case_features"]
