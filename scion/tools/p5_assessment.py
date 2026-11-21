"""Offline P5 export/review aid. Never imported by the research runtime.

Checks evidence locations and report coverage, not research quality or causality.
Problem-owned public examples and evaluator answers remain separate files.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path, PurePosixPath

DATA = Path(__file__).resolve().parents[1] / "experiments/v0.5/p5"
DIMENSIONS = ("investigation", "interpretation", "revision", "conclusion", "continuity")
RATINGS = {"supported", "contradicted", "insufficient", "not_applicable"}
STATUSES = {"not_run", "completed", "resource_stop", "provider_failure",
            "infra_failure", "interrupted", "boundary_failure"}
COSTS = ("physical_calls", "input_tokens", "output_tokens", "reasoning_tokens",
         "cache_tokens", "research_cpu_seconds", "research_wall_seconds",
         "test_wall_seconds", "formal_wall_seconds", "total_wall_seconds", "storage_bytes")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, names):
    require(type(value) is dict and set(value) == set(names), "unexpected fields")


def nonempty(value):
    require(type(value) is str and bool(value.strip()), "nonempty text required")


def load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def constant(_):
        raise ValueError("nonfinite JSON")

    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=pairs,
                      parse_constant=constant)


def plan():
    return load(DATA / "plan.json")["runs"]


def export_task(task_id):
    """Only public files are opened; no dynamic paths from user input."""
    for problem in ("cvrp", "warehouse"):
        if task_id == "open-" + problem:
            return load(DATA / problem / "public/open.json")
        for task in load(DATA / problem / "public/tasks.json"):
            if task["task_id"] == task_id:
                value = task["research_input"]
                # prior observations have problem-specific schemas. These are plain
                # synthetic task data, not historical measurements or formal evidence.
                return {"current_question": value["current_question"] +
                        "\n公开示例数据（非 solver 实测）：\n" +
                        json.dumps(value["observations"], ensure_ascii=False, indent=2),
                        "observations": []}
    raise ValueError("unknown diagnostic task")


def template():
    return {"schema_version": 1, "runs": [
        {"run_id": run["run_id"], "status": "not_run", "note": "Not started",
         "terminal_ref": None, "interventions": [],
         "costs": dict.fromkeys(COSTS),
         "missing_costs": {key: "Not started" for key in COSTS}, "reviews": []}
        for run in plan()]}


def check_citation(citation, root):
    fields(citation, ("path", "start", "end", "quote"))
    name, start, end, quote = (citation[key] for key in ("path", "start", "end", "quote"))
    nonempty(name)
    relative = PurePosixPath(name)
    require(not relative.is_absolute() and str(relative) == name and
            ".." not in relative.parts and "\\" not in name and "\x00" not in name,
            "invalid evidence path")
    path = Path(root)
    require(path.is_dir() and not path.is_symlink(), "invalid evidence root")
    for part in relative.parts:
        path /= part
        require(not path.is_symlink(), "symlink evidence")
    require(path.is_file(), "evidence unavailable")
    require(type(start) is int and type(end) is int and 0 <= start < end <= path.stat().st_size,
            "invalid evidence range")
    nonempty(quote)
    require(end - start == len(quote.encode("utf-8")), "quote size mismatch")
    with path.open("rb") as stream:
        stream.seek(start)
        require(stream.read(end - start) == quote.encode("utf-8"), "quote mismatch")


def review(sheet, evidence_root):
    """Return descriptive coverage/disagreement only; humans assess semantics."""
    fields(sheet, ("schema_version", "runs"))
    require(type(sheet["schema_version"]) is int and sheet["schema_version"] == 1,
            "unsupported review schema")
    require(type(sheet["runs"]) is list, "runs must be a list")
    declared = {run["run_id"]: run for run in plan()}
    seen, rows = set(), []
    for row in sheet["runs"]:
        fields(row, ("run_id", "status", "note", "terminal_ref", "interventions",
                     "costs", "missing_costs", "reviews"))
        rid = row["run_id"]
        nonempty(rid)
        require(rid in declared and rid not in seen, "unknown or duplicate run")
        seen.add(rid)
        nonempty(row["status"])
        require(row["status"] in STATUSES, "unknown status")
        nonempty(row["note"])
        require(type(row["interventions"]) is list, "interventions must be a list")
        for intervention in row["interventions"]:
            fields(intervention, ("kind", "note", "evidence"))
            require(intervention["kind"] in ("operational", "scientific"), "invalid intervention")
            nonempty(intervention["note"])
            check_citation(intervention["evidence"], evidence_root)
        fields(row["costs"], COSTS)
        require(type(row["missing_costs"]) is dict, "missing costs must be a mapping")
        missing = set()
        for key, value in row["costs"].items():
            if value is None:
                missing.add(key)
            else:
                require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
                        "invalid cost")
                if key.endswith("tokens") or key in ("physical_calls", "storage_bytes"):
                    require(type(value) is int, "integer count required")
        require(set(row["missing_costs"]) == missing, "missing costs need exact reasons")
        for reason in row["missing_costs"].values():
            nonempty(reason)
        require(type(row["reviews"]) is list and len(row["reviews"]) <= 2,
                "at most two independent reviews")
        if row["status"] == "not_run":
            require(row["terminal_ref"] is None and not row["reviews"] and
                    not row["interventions"] and missing == set(COSTS),
                    "not_run cannot contain execution evidence")
        else:
            check_citation(row["terminal_ref"], evidence_root)
        reviewers = set()
        for assessment in row["reviews"]:
            fields(assessment, ("reviewer", "blinding", "dimensions"))
            nonempty(assessment["reviewer"])
            require(assessment["reviewer"] not in reviewers, "duplicate reviewer")
            reviewers.add(assessment["reviewer"])
            nonempty(assessment["blinding"])
            fields(assessment["dimensions"], DIMENSIONS)
            for dim, finding in assessment["dimensions"].items():
                fields(finding, ("rating", "reason", "evidence"))
                nonempty(finding["rating"])
                require(finding["rating"] in RATINGS, "unknown rating")
                nonempty(finding["reason"])
                require(type(finding["evidence"]) is list, "evidence must be a list")
                if finding["rating"] == "not_applicable":
                    require(dim == "continuity" and not declared[rid]["continuity_required"],
                            "required dimension cannot be not_applicable")
                if finding["rating"] in ("supported", "contradicted"):
                    require(bool(finding["evidence"]), "judgment needs evidence")
                for citation in finding["evidence"]:
                    check_citation(citation, evidence_root)
        disagreements = []
        if len(row["reviews"]) == 2:
            left, right = (item["dimensions"] for item in row["reviews"])
            disagreements = [dim for dim in DIMENSIONS if left[dim]["rating"] != right[dim]["rating"]]
        rows.append({"run_id": rid, "status": row["status"], "costs": row["costs"],
                     "missing_costs": row["missing_costs"], "review_count": len(reviewers),
                     "disagreements": disagreements, "reviews": row["reviews"],
                     "interventions": row["interventions"], "note": row["note"],
                     "terminal_ref": row["terminal_ref"]})
    require(seen == set(declared), "all planned slots must be reported")
    rows.sort(key=lambda row: list(declared).index(row["run_id"]))
    return {"scope": "Offline coverage and citation checks only; no E2/E3/E4 decision",
            "runs": rows, "pending_double_review": [r["run_id"] for r in rows if r["review_count"] < 2]}


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("task")
    export.add_argument("output", type=Path)
    draft = commands.add_parser("template")
    draft.add_argument("output", type=Path)
    check = commands.add_parser("review")
    check.add_argument("sheet", type=Path)
    check.add_argument("--evidence-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "export":
            write_new(args.output, export_task(args.task))
        elif args.command == "template":
            write_new(args.output, template())
        else:
            print(json.dumps(review(load(args.sheet), args.evidence_root), ensure_ascii=False, indent=2))
    except (ValueError, OSError) as error:
        parser.exit(2, f"{error}\n")


if __name__ == "__main__":
    main()
