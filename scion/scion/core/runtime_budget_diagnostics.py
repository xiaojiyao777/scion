"""Generic runtime budget saturation diagnostics."""
from __future__ import annotations

import statistics
from collections.abc import Sequence
from typing import Any, Mapping

RUNTIME_BUDGET_DIAGNOSTIC_SCHEMA = "scion.runtime_budget_diagnostic.v1"
TINY_RUNTIME_BUDGET_SATURATION = "TINY_RUNTIME_BUDGET_SATURATION"
SCREENING_RUNTIME_BUDGET_SATURATION = "SCREENING_RUNTIME_BUDGET_SATURATION"
CANDIDATE_RUNTIME_BUDGET_SATURATION = "CANDIDATE_RUNTIME_BUDGET_SATURATION"
CHAMPION_RUNTIME_BUDGET_SATURATION = "CHAMPION_RUNTIME_BUDGET_SATURATION"
BOTH_RUNTIME_BUDGET_SATURATION = "BOTH_RUNTIME_BUDGET_SATURATION"

_TINY_PAIR_LIMIT = 4
_TINY_SATURATION_RATIO = 0.75
_SCREENING_SATURATION_RATIO = 0.90


def runtime_budget_diagnostic(
    *,
    stage: Any,
    time_limit_sec: float | int | None,
    candidate_elapsed_ms: Sequence[Any] = (),
    champion_elapsed_ms: Sequence[Any] = (),
    total_pairs: int | None = None,
) -> dict[str, Any] | None:
    """Return a repairable diagnostic when tiny/screening runs saturate budget."""
    stage_value = str(getattr(stage, "value", stage) or "").strip().lower()
    if stage_value not in {"screening", "smoke", "proposal_smoke"}:
        return None
    limit_ms = _positive_float(time_limit_sec)
    if limit_ms is None:
        return None
    limit_ms *= 1000.0
    if limit_ms <= 0:
        return None

    candidate_samples = _elapsed_samples(candidate_elapsed_ms)
    champion_samples = _elapsed_samples(champion_elapsed_ms)
    if not candidate_samples and not champion_samples:
        return None

    observed_pairs = int(total_pairs or 0)
    if observed_pairs <= 0:
        observed_pairs = max(len(candidate_samples), len(champion_samples))
    candidate_summary = _sample_summary(candidate_samples, limit_ms)
    champion_summary = _sample_summary(champion_samples, limit_ms)
    saturation_ratio = max(
        candidate_summary.get("max_budget_ratio") or 0.0,
        champion_summary.get("max_budget_ratio") or 0.0,
    )
    median_ratio = max(
        candidate_summary.get("median_budget_ratio") or 0.0,
        champion_summary.get("median_budget_ratio") or 0.0,
    )

    tiny = observed_pairs <= _TINY_PAIR_LIMIT
    threshold = _TINY_SATURATION_RATIO if tiny else _SCREENING_SATURATION_RATIO
    if saturation_ratio < threshold and median_ratio < threshold:
        return None
    candidate_saturated = _summary_saturated(candidate_summary, threshold)
    champion_saturated = _summary_saturated(champion_summary, threshold)
    saturated_side = _saturated_side(
        candidate_saturated=candidate_saturated,
        champion_saturated=champion_saturated,
    )

    code = (
        TINY_RUNTIME_BUDGET_SATURATION
        if tiny
        else SCREENING_RUNTIME_BUDGET_SATURATION
    )
    scope = "Tiny runtime" if tiny else "Screening runtime"
    side_codes = _side_reason_codes(saturated_side)
    return {
        "schema": RUNTIME_BUDGET_DIAGNOSTIC_SCHEMA,
        "code": code,
        "stage": stage_value,
        "severity": "warn",
        "repairable": candidate_saturated,
        "total_pairs": observed_pairs,
        "time_limit_ms": round(limit_ms, 3),
        "threshold_ratio": threshold,
        "saturation_ratio": round(saturation_ratio, 4),
        "saturated_side": saturated_side,
        "candidate_saturated": candidate_saturated,
        "champion_saturated": champion_saturated,
        "reason_codes": list(side_codes),
        "candidate": candidate_summary,
        "champion": champion_summary,
        "guidance": _guidance_for_side(
            scope,
            candidate_saturated=candidate_saturated,
            champion_saturated=champion_saturated,
        ),
    }


def format_runtime_budget_diagnostic(summary: Mapping[str, Any] | None) -> str:
    """Return a compact prompt-facing runtime budget diagnostic suffix."""
    if not isinstance(summary, Mapping) or not summary:
        return ""
    code = str(summary.get("code") or "").strip()
    if not code:
        return ""
    candidate = summary.get("candidate")
    champion = summary.get("champion")
    candidate_ratio = (
        candidate.get("max_budget_ratio")
        if isinstance(candidate, Mapping)
        else None
    )
    champion_ratio = (
        champion.get("max_budget_ratio")
        if isinstance(champion, Mapping)
        else None
    )
    parts = [f"runtime_budget_diagnostic={code}"]
    if candidate_ratio is not None:
        parts.append(f"candidate_budget_ratio={candidate_ratio}")
    if champion_ratio is not None:
        parts.append(f"champion_budget_ratio={champion_ratio}")
    side = str(summary.get("saturated_side") or "").strip()
    if side:
        parts.append(f"saturated_side={side}")
    if summary.get("total_pairs") is not None:
        parts.append(f"total_pairs={summary.get('total_pairs')}")
    return " " + " ".join(parts)


def protocol_runtime_budget_diagnostic(
    protocol_result: Any,
) -> dict[str, Any] | None:
    surface_summary = getattr(
        protocol_result,
        "candidate_surface_runtime_summary",
        None,
    )
    if not isinstance(surface_summary, Mapping):
        return None
    diagnostic = surface_summary.get("runtime_budget_diagnostic")
    return dict(diagnostic) if isinstance(diagnostic, Mapping) else None


def runtime_budget_diagnostic_code(protocol_result: Any) -> str:
    diagnostic = protocol_runtime_budget_diagnostic(protocol_result)
    if not diagnostic:
        return ""
    if str(diagnostic.get("saturated_side") or "").strip().lower() == "champion":
        return ""
    code = str(diagnostic.get("code") or "").strip()
    if code in {TINY_RUNTIME_BUDGET_SATURATION, SCREENING_RUNTIME_BUDGET_SATURATION}:
        return code
    return ""


def runtime_budget_diagnostic_detected(protocol_result: Any) -> bool:
    return bool(runtime_budget_diagnostic_code(protocol_result))


def runtime_budget_candidate_saturation_detected(protocol_result: Any) -> bool:
    diagnostic = protocol_runtime_budget_diagnostic(protocol_result)
    if not diagnostic:
        return False
    side = str(diagnostic.get("saturated_side") or "").strip().lower()
    if side in {"candidate", "both"}:
        return True
    if side == "champion":
        return False
    return bool(runtime_budget_diagnostic_code(protocol_result))


def runtime_budget_candidate_diagnostic_code(protocol_result: Any) -> str:
    if not runtime_budget_candidate_saturation_detected(protocol_result):
        return ""
    return runtime_budget_diagnostic_code(protocol_result)


def runtime_budget_diagnostic_reason_codes(protocol_result: Any) -> tuple[str, ...]:
    diagnostic = protocol_runtime_budget_diagnostic(protocol_result)
    return runtime_budget_summary_reason_codes(diagnostic)


def runtime_budget_summary_reason_codes(
    diagnostic: Mapping[str, Any] | None,
) -> tuple[str, ...]:
    if not diagnostic:
        return ()
    base_code = _diagnostic_base_code(diagnostic)
    side = str(diagnostic.get("saturated_side") or "").strip().lower()
    if side in {"candidate", "both"}:
        codes = (
            (base_code, *_side_reason_codes(side))
            if base_code
            else _side_reason_codes(side)
        )
        return tuple(dict.fromkeys(codes))
    if side == "champion":
        return (CHAMPION_RUNTIME_BUDGET_SATURATION,)
    return (base_code,) if base_code else ()


def _diagnostic_base_code(diagnostic: Mapping[str, Any]) -> str:
    code = str(diagnostic.get("code") or "").strip()
    if code in {TINY_RUNTIME_BUDGET_SATURATION, SCREENING_RUNTIME_BUDGET_SATURATION}:
        return code
    return ""


def _elapsed_samples(values: Sequence[Any]) -> list[float]:
    samples: list[float] = []
    for value in values:
        number = _positive_float(value)
        if number is not None:
            samples.append(number)
    return samples


def _positive_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    return number


def _summary_saturated(summary: Mapping[str, Any], threshold: float) -> bool:
    return (
        (summary.get("max_budget_ratio") or 0.0) >= threshold
        or (summary.get("median_budget_ratio") or 0.0) >= threshold
    )


def _saturated_side(
    *,
    candidate_saturated: bool,
    champion_saturated: bool,
) -> str:
    if candidate_saturated and champion_saturated:
        return "both"
    if candidate_saturated:
        return "candidate"
    if champion_saturated:
        return "champion"
    return "unknown"


def _side_reason_codes(side: str) -> tuple[str, ...]:
    if side == "candidate":
        return (CANDIDATE_RUNTIME_BUDGET_SATURATION,)
    if side == "champion":
        return (CHAMPION_RUNTIME_BUDGET_SATURATION,)
    if side == "both":
        return (BOTH_RUNTIME_BUDGET_SATURATION,)
    return ()


def _guidance_for_side(
    scope: str,
    *,
    candidate_saturated: bool,
    champion_saturated: bool,
) -> str:
    if candidate_saturated:
        if champion_saturated:
            return (
                f"{scope} is close to the per-run time limit on both sides. "
                "Reduce candidate per-case work before formal screening when "
                "the candidate change adds work; otherwise treat this as "
                "low-confidence runtime evidence that needs a fresh bounded run."
            )
        return (
            f"{scope} is close to the per-run time limit on the candidate side. "
            "Reduce the candidate's per-case work before formal screening by "
            "adding time polling, smaller bounded candidate sets, earlier exits, "
            "or a cheaper schedule."
        )
    if champion_saturated:
        return (
            f"{scope} is close to the per-run time limit on the champion side. "
            "Keep this as runtime evidence-confidence diagnostic; do not direct "
            "candidate repair from this signal alone."
        )
    return (
        f"{scope} is close to the per-run time limit, but the saturated side "
        "could not be identified."
    )


def _sample_summary(samples: Sequence[float], limit_ms: float) -> dict[str, Any]:
    if not samples:
        return {"count": 0}
    median_ms = statistics.median(samples)
    max_ms = max(samples)
    return {
        "count": len(samples),
        "median_elapsed_ms": round(median_ms, 3),
        "max_elapsed_ms": round(max_ms, 3),
        "median_budget_ratio": round(median_ms / limit_ms, 4),
        "max_budget_ratio": round(max_ms / limit_ms, 4),
    }


__all__ = [
    "BOTH_RUNTIME_BUDGET_SATURATION",
    "CANDIDATE_RUNTIME_BUDGET_SATURATION",
    "CHAMPION_RUNTIME_BUDGET_SATURATION",
    "RUNTIME_BUDGET_DIAGNOSTIC_SCHEMA",
    "SCREENING_RUNTIME_BUDGET_SATURATION",
    "TINY_RUNTIME_BUDGET_SATURATION",
    "format_runtime_budget_diagnostic",
    "runtime_budget_candidate_diagnostic_code",
    "runtime_budget_candidate_saturation_detected",
    "protocol_runtime_budget_diagnostic",
    "runtime_budget_diagnostic",
    "runtime_budget_diagnostic_code",
    "runtime_budget_diagnostic_detected",
    "runtime_budget_diagnostic_reason_codes",
    "runtime_budget_summary_reason_codes",
]
