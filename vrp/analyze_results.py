from __future__ import annotations

import argparse
import csv
import glob
import math
import re
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Iterable


def _expand_inputs(inputs: list[str]) -> list[Path]:
    paths: list[Path] = []
    for item in inputs:
        matches = [Path(p) for p in glob.glob(item)]
        if not matches:
            matches = [Path(item)]
        for path in matches:
            if path.is_dir():
                paths.extend(sorted(path.glob("*.csv")))
            elif path.exists():
                paths.append(path)
    return sorted(dict.fromkeys(paths))


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "nan", "null"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _int_or_none(value: object) -> int | None:
    number = _float_or_none(value)
    if number is None:
        return None
    return int(number)


def _infer_seed(source: str) -> int | None:
    match = re.search(r"(?:^|[_-])seed[_-]?(\d+)(?:$|[_\-.])", source)
    return int(match.group(1)) if match else None


def _infer_time_limit(source: str) -> float | None:
    match = re.search(r"(?:^|[_-])(?:t|time)[_-]?(\d+(?:\.\d+)?)(?:s)?(?:$|[_\-.])", source)
    return float(match.group(1)) if match else None


def _infer_subset(instance: str, path: str | None) -> str:
    if path:
        parent = Path(path).parent.name
        if parent and parent != ".":
            return parent
    if instance.startswith(("A-", "B-", "E-", "F-", "M-", "P-", "X-", "XL-")):
        return instance.split("-", 1)[0]
    if instance.startswith("CMT"):
        return "CMT"
    if instance.startswith("tai"):
        return "tai"
    if instance.startswith("XML"):
        return "XML"
    if instance.startswith(("Antwerp", "Brussels", "Flanders", "Ghent", "Leuven")):
        return "AGS"
    if instance.startswith(("Loggi", "ORTEC")):
        return "DIMACS"
    return "unknown"


def _mean(values: Iterable[float]) -> float | None:
    values = list(values)
    return statistics.fmean(values) if values else None


def _median(values: Iterable[float]) -> float | None:
    values = list(values)
    return statistics.median(values) if values else None


def _std(values: Iterable[float]) -> float:
    values = list(values)
    return statistics.stdev(values) if len(values) > 1 else 0.0


def _pct(count: int, total: int) -> float | None:
    return None if total == 0 else count / total * 100.0


def _load_validation(path: str | None) -> dict[str, str]:
    if not path:
        return {}
    result: dict[str, str] = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            instance = row.get("instance", "")
            status = row.get("status", "")
            if instance:
                result[instance] = status
    return result


def read_result_rows(paths: list[Path], validation_status: dict[str, str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in paths:
        source = path.name
        inferred_seed = _infer_seed(source)
        inferred_time = _infer_time_limit(source)
        with open(path, newline="") as f:
            for raw in csv.DictReader(f):
                instance = raw.get("instance", "").strip()
                if not instance:
                    continue
                bks = _float_or_none(raw.get("bks"))
                cost = _float_or_none(raw.get("cost"))
                gap = _float_or_none(raw.get("gap_pct"))
                if gap is None and bks and cost is not None:
                    gap = (cost - bks) / bks * 100.0
                row_path = raw.get("path") or raw.get("instance_path")
                seed = _int_or_none(raw.get("seed"))
                time_limit = _float_or_none(raw.get("time_limit"))
                rows.append(
                    {
                        "instance": instance,
                        "subset": raw.get("subset") or _infer_subset(instance, row_path),
                        "dimension": _int_or_none(raw.get("dimension")),
                        "bks": bks,
                        "cost": cost,
                        "gap_pct": gap,
                        "routes": _int_or_none(raw.get("routes")),
                        "bks_routes": _int_or_none(raw.get("bks_routes")),
                        "route_gap": _int_or_none(raw.get("route_gap")),
                        "iterations": _int_or_none(raw.get("iterations")),
                        "time": _float_or_none(raw.get("time")),
                        "time_limit": time_limit if time_limit is not None else inferred_time,
                        "seed": seed if seed is not None else inferred_seed,
                        "feasible": raw.get("feasible", ""),
                        "benchmark_feasible": raw.get("benchmark_feasible", ""),
                        "source": source,
                        "reference_status": validation_status.get(instance, ""),
                    }
                )
    return rows


def aggregate_per_instance(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["instance"])].append(row)

    result: list[dict[str, object]] = []
    for instance, group in sorted(grouped.items()):
        gaps = [g for g in (_float_or_none(row["gap_pct"]) for row in group) if g is not None]
        costs = [c for c in (_float_or_none(row["cost"]) for row in group) if c is not None]
        times = [t for t in (_float_or_none(row["time"]) for row in group) if t is not None]
        iters = [i for i in (_int_or_none(row["iterations"]) for row in group) if i is not None]
        best_row = min(
            group,
            key=lambda row: math.inf if _float_or_none(row["gap_pct"]) is None else float(row["gap_pct"]),
        )
        result.append(
            {
                "instance": instance,
                "subset": group[0]["subset"],
                "dimension": group[0]["dimension"],
                "runs": len(group),
                "bks": group[0]["bks"],
                "bks_routes": group[0]["bks_routes"],
                "route_gap": best_row["route_gap"],
                "best_cost": best_row["cost"],
                "best_gap_pct": best_row["gap_pct"],
                "mean_gap_pct": _mean(gaps),
                "median_gap_pct": _median(gaps),
                "std_gap_pct": _std(gaps),
                "mean_cost": _mean(costs),
                "std_cost": _std(costs),
                "mean_time": _mean(times),
                "mean_iterations": _mean(iters),
                "best_source": best_row["source"],
                "reference_status": group[0]["reference_status"],
            }
        )
    return result


def aggregate_by_subset(per_instance: list[dict[str, object]], rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    runs_by_subset: dict[str, int] = defaultdict(int)
    for row in rows:
        runs_by_subset[str(row["subset"])] += 1
    for row in per_instance:
        grouped[str(row["subset"])].append(row)

    summaries: list[dict[str, object]] = []
    for subset, group in sorted(grouped.items()):
        best_gaps = [g for g in (_float_or_none(row["best_gap_pct"]) for row in group) if g is not None]
        mean_gaps = [g for g in (_float_or_none(row["mean_gap_pct"]) for row in group) if g is not None]
        times = [t for t in (_float_or_none(row["mean_time"]) for row in group) if t is not None]
        total = len(best_gaps)
        summaries.append(
            {
                "subset": subset,
                "instances": len(group),
                "runs": runs_by_subset[subset],
                "mean_best_gap_pct": _mean(best_gaps),
                "median_best_gap_pct": _median(best_gaps),
                "max_best_gap_pct": max(best_gaps) if best_gaps else None,
                "mean_mean_gap_pct": _mean(mean_gaps),
                "solved_to_bks": sum(1 for gap in best_gaps if gap <= 1e-9),
                "under_1pct": sum(1 for gap in best_gaps if gap <= 1.0),
                "under_3pct": sum(1 for gap in best_gaps if gap <= 3.0),
                "under_5pct": sum(1 for gap in best_gaps if gap <= 5.0),
                "under_1pct_rate": _pct(sum(1 for gap in best_gaps if gap <= 1.0), total),
                "under_3pct_rate": _pct(sum(1 for gap in best_gaps if gap <= 3.0), total),
                "under_5pct_rate": _pct(sum(1 for gap in best_gaps if gap <= 5.0), total),
                "mean_time": _mean(times),
            }
        )

    all_best = [g for row in per_instance if (g := _float_or_none(row["best_gap_pct"])) is not None]
    all_mean = [g for row in per_instance if (g := _float_or_none(row["mean_gap_pct"])) is not None]
    all_times = [t for row in per_instance if (t := _float_or_none(row["mean_time"])) is not None]
    if per_instance:
        total = len(all_best)
        summaries.insert(
            0,
            {
                "subset": "ALL",
                "instances": len(per_instance),
                "runs": len(rows),
                "mean_best_gap_pct": _mean(all_best),
                "median_best_gap_pct": _median(all_best),
                "max_best_gap_pct": max(all_best) if all_best else None,
                "mean_mean_gap_pct": _mean(all_mean),
                "solved_to_bks": sum(1 for gap in all_best if gap <= 1e-9),
                "under_1pct": sum(1 for gap in all_best if gap <= 1.0),
                "under_3pct": sum(1 for gap in all_best if gap <= 3.0),
                "under_5pct": sum(1 for gap in all_best if gap <= 5.0),
                "under_1pct_rate": _pct(sum(1 for gap in all_best if gap <= 1.0), total),
                "under_3pct_rate": _pct(sum(1 for gap in all_best if gap <= 3.0), total),
                "under_5pct_rate": _pct(sum(1 for gap in all_best if gap <= 5.0), total),
                "mean_time": _mean(all_times),
            },
        )
    return summaries

def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        with open(path, "w", newline="") as f:
            f.write("")
        return
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def print_summary(summary_rows: list[dict[str, object]]) -> None:
    print("subset, instances, runs, mean_best_gap, median_best_gap, max_best_gap, <=1%, <=3%, <=5%")
    for row in summary_rows:
        print(
            f"{row['subset']}, {row['instances']}, {row['runs']}, "
            f"{_float_or_none(row['mean_best_gap_pct']) or 0.0:.3f}, "
            f"{_float_or_none(row['median_best_gap_pct']) or 0.0:.3f}, "
            f"{_float_or_none(row['max_best_gap_pct']) or 0.0:.3f}, "
            f"{_float_or_none(row['under_1pct_rate']) or 0.0:.1f}, "
            f"{_float_or_none(row['under_3pct_rate']) or 0.0:.1f}, "
            f"{_float_or_none(row['under_5pct_rate']) or 0.0:.1f}"
        )


def run_analysis(
    inputs: list[str],
    output_dir: str,
    validation_report: str | None,
    exclude_invalid_reference: bool,
    exclude_benchmark_infeasible: bool,
    top_n: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    paths = _expand_inputs(inputs)
    if not paths:
        raise FileNotFoundError("No input CSV files found")

    validation_status = _load_validation(validation_report)
    rows = read_result_rows(paths, validation_status)
    if exclude_invalid_reference:
        rows = [
            row
            for row in rows
            if str(row.get("reference_status") or "ok") in {"", "ok", "missing_sol"}
        ]
    if exclude_benchmark_infeasible:
        rows = [
            row
            for row in rows
            if str(row.get("benchmark_feasible") or "True").lower() in {"", "true"}
        ]

    per_instance = aggregate_per_instance(rows)
    summary = aggregate_by_subset(per_instance, rows)
    gap_rows = [row for row in per_instance if _float_or_none(row["best_gap_pct"]) is not None]
    top_gaps = sorted(
        gap_rows,
        key=lambda row: float(row["best_gap_pct"]),
        reverse=True,
    )[:top_n]

    out = Path(output_dir)
    _write_csv(out / "summary_by_subset.csv", summary)
    _write_csv(out / "per_instance.csv", per_instance)
    _write_csv(out / "top_gaps.csv", top_gaps)

    print(f"inputs={len(paths)} rows={len(rows)} instances={len(per_instance)} output_dir={out}")
    print_summary(summary)
    return summary, per_instance, top_gaps


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze benchmark CSV results")
    parser.add_argument("inputs", nargs="+", help="CSV files, directories, or glob patterns")
    parser.add_argument("--output-dir", default="results/analysis")
    parser.add_argument("--validation-report", default=None)
    parser.add_argument("--exclude-invalid-reference", action="store_true")
    parser.add_argument("--exclude-benchmark-infeasible", action="store_true")
    parser.add_argument("--top-n", type=int, default=20)
    args = parser.parse_args()

    run_analysis(
        inputs=args.inputs,
        output_dir=args.output_dir,
        validation_report=args.validation_report,
        exclude_invalid_reference=args.exclude_invalid_reference,
        exclude_benchmark_infeasible=args.exclude_benchmark_infeasible,
        top_n=args.top_n,
    )


if __name__ == "__main__":
    main()
