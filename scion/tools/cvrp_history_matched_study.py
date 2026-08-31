"""Run the five-block CVRP history OFF/ON matched development study.

The driver is deliberately a thin composition layer over the ordinary
``scion run`` command.  It does not create a study manifest, identify source
objects, or interpret campaign results.  Each arm writes only the artifacts
owned by a normal campaign: ``status.json``, ``campaign_summary.json``,
``research_history.jsonl`` when a step is recordable, and ``llm_traces/``.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Direct script execution puts ``tools/`` rather than the package root on
# sys.path.  Keep the checked-out Scion package authoritative for this local
# experiment runner without requiring installation or a build step.
SCION_ROOT = Path(__file__).resolve().parents[1]
if str(SCION_ROOT) not in sys.path:
    sys.path.insert(0, str(SCION_ROOT))

# isort: off
from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.core.code_research_limits import load_code_research_limits
from scion.core.research_history import load_research_histories
from scion.core.research_input import normalize_research_input
from scion.postrun.research_effectiveness import (
    calculate_research_trajectory,
    compare_history_trajectories,
)
from scion.problem.loader import load_problem_adapter, load_problem_spec_v1_from_yaml
from scion.protocol.experiment import validate_requested_screening_expansion
from tools.generate_cvrp_history_matched_cases import (
    CASE_SPECS,
    NAMESPACE as GENERATED_NAMESPACE,
    render_case,
    specs_for_block,
)
# isort: on


DEFAULT_CONFIG = (
    SCION_ROOT / "experiments" / "cvrp_history_matched_study" / "study.json"
)
ARMS = ("off", "on")
EXPECTED_BLOCKS = 5
EXPECTED_HISTORY_FILES = 16
EXPECTED_MODEL = "gpt-5.6-sol"
EXPECTED_BASE_URL = "http://127.0.0.1:8080"
CONTINUE_EXIT_CODES = frozenset({0, 21, 124})
SCREENING_EXCLUSION_AUDIT = {
    "local_cvrplib_cases": 10_344,
    "full_results_covered_cases": 10_330,
    "reference_validation_bad_cases": 14,
    "historically_contaminated_existing_cases": 10_344,
    "fresh_existing_cases": 0,
    "synthetic_namespace": GENERATED_NAMESPACE,
    "synthetic_fixed_input_cases": len(CASE_SPECS),
    "synthetic_generator_historical_inputs": 0,
    "synthetic_generator_outcome_inputs": 0,
    "synthetic_solution_sidecars": 0,
}


class StudyConfigError(ValueError):
    """The ordinary study inputs do not describe the matched experiment."""


@dataclass(frozen=True)
class StudyBlock:
    block_id: str
    order: tuple[str, str]
    split_path: Path
    seeds_path: Path
    split: SplitManifest
    seeds: SeedLedgerConfig


@dataclass(frozen=True)
class PreparedStudy:
    config_path: Path
    problem_path: Path
    problem_dir: Path
    data_root: Path
    protocol_path: Path
    protocol: ProtocolConfig
    research_input_path: Path
    code_research_limits_path: Path
    history_paths: tuple[Path, ...]
    history_records: tuple[dict[str, Any], ...]
    model: str
    base_url: str
    reasoning_effort: str
    rounds: int
    provider_call_cap: int
    outer_hardwall_sec: int
    time_limit_sec: int
    blocks: tuple[StudyBlock, ...]

    @property
    def total_arms(self) -> int:
        return len(self.blocks) * len(ARMS)

    @property
    def provider_call_cap_total(self) -> int:
        return self.total_arms * self.provider_call_cap

    @property
    def formal_stage_cap_total(self) -> int:
        return self.total_arms * self.rounds


def _without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            raise StudyConfigError(f"duplicate study config key: {key}")
        value[key] = child
    return value


def _load_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_without_duplicate_keys,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StudyConfigError(f"cannot load JSON {path}: {exc}") from exc


def _mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise StudyConfigError(f"{label} must be a JSON object")
    return value


def _exact_fields(
    value: Mapping[str, Any], *, allowed: set[str], required: set[str], label: str
) -> None:
    unknown = sorted(set(value) - allowed)
    missing = sorted(required - set(value))
    if unknown:
        raise StudyConfigError(f"unsupported {label} field: {unknown[0]}")
    if missing:
        raise StudyConfigError(f"missing {label} field: {missing[0]}")


def _positive_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise StudyConfigError(f"{label} must be a positive integer")
    return value


def _path(base: Path, value: Any, *, label: str, directory: bool = False) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise StudyConfigError(f"{label} must be a nonempty path string")
    unresolved = Path(value).expanduser()
    path = unresolved if unresolved.is_absolute() else base / unresolved
    path = path.resolve()
    valid = path.is_dir() if directory else path.is_file()
    if not valid:
        kind = "directory" if directory else "file"
        raise StudyConfigError(f"{label} is not a regular {kind}: {path}")
    return path


def _problem_id(adapter: Any) -> str:
    spec = getattr(adapter, "spec", None)
    value = str(getattr(spec, "id", None) or getattr(spec, "name", "") or "")
    if not value.strip():
        raise StudyConfigError("CVRP adapter.spec must expose a problem id")
    return value.strip()


def _validate_case_paths(
    split: SplitManifest,
    *,
    adapter: Any,
    problem_dir: Path,
    data_root: Path,
    label: str,
) -> None:
    for stage in ("screening", "validation", "frozen", "canary"):
        cases = tuple(getattr(split, stage))
        if not cases:
            raise StudyConfigError(f"{label}.{stage} must not be empty")
        for case in cases:
            root = (
                data_root
                if str(case).startswith(("cvrplib/", "scion_generated/"))
                else problem_dir
            )
            path = root / str(case)
            if not path.is_file():
                raise StudyConfigError(f"missing {label}.{stage} case: {path}")
            if stage == "screening":
                try:
                    adapter.load_instance(str(path))
                except (OSError, TypeError, ValueError) as exc:
                    raise StudyConfigError(
                        f"adapter cannot load {label}.{stage} case {path}: {exc}"
                    ) from exc


def _validate_seed_ledger(seeds: SeedLedgerConfig, *, label: str) -> None:
    seen: set[int] = set()
    for stage in ("screening", "validation", "frozen", "canary"):
        values = tuple(getattr(seeds, stage))
        if not values:
            raise StudyConfigError(f"{label}.{stage} must not be empty")
        for seed in values:
            if seed in seen:
                raise StudyConfigError(f"{label} reuses seed {seed} across stages")
            seen.add(seed)


def _resolved_screening_time_limits(
    *,
    protocol: ProtocolConfig,
    cases: Sequence[str],
    fallback_time_limit_sec: int,
) -> tuple[int, ...]:
    return tuple(
        protocol.runtime.time_limits.resolve(
            stage="screening",
            case_path=case,
            fallback_time_limit_sec=fallback_time_limit_sec,
        )
        for case in cases
    )


def load_study_config(path: str | Path = DEFAULT_CONFIG) -> PreparedStudy:
    """Load and provider-/solver-free validate the complete study setup."""

    config_path = Path(path).expanduser().resolve()
    raw = _mapping(_load_json(config_path), label="study config")
    required = {
        "schema",
        "problem",
        "data_root",
        "protocol",
        "research_input",
        "code_research_limits",
        "history",
        "model",
        "base_url",
        "reasoning_effort",
        "rounds",
        "provider_call_cap",
        "outer_hardwall_sec",
        "time_limit_sec",
        "blocks",
    }
    _exact_fields(raw, allowed=required, required=required, label="study config")
    if raw["schema"] != "scion.cvrp_history_matched_study.v1":
        raise StudyConfigError("unsupported study config schema")

    base = config_path.parent
    problem_path = _path(base, raw["problem"], label="problem")
    if problem_path.name != "problem-v1.yaml":
        raise StudyConfigError("problem must directly name problem-v1.yaml")
    problem_v1 = load_problem_spec_v1_from_yaml(problem_path)
    adapter = load_problem_adapter(problem_v1)
    problem_id = _problem_id(adapter)
    if problem_id != "cvrp":
        raise StudyConfigError(f"study requires cvrp adapter, got {problem_id!r}")

    data_root = _path(base, raw["data_root"], label="data_root", directory=True)
    protocol_path = _path(base, raw["protocol"], label="protocol")
    protocol = ProtocolConfig.from_yaml(protocol_path)
    if not protocol.screening.require_expanded_for_pass:
        raise StudyConfigError(
            "two-stage study requires screening.require_expanded_for_pass=true "
            "so held-out stages are unreachable"
        )
    research_input_path = _path(base, raw["research_input"], label="research_input")
    normalize_research_input(_load_json(research_input_path))
    code_limits_path = _path(
        base,
        raw["code_research_limits"],
        label="code_research_limits",
    )
    code_limits = load_code_research_limits(code_limits_path)
    if code_limits.max_hypothesis_candidates != 1:
        raise StudyConfigError("matched history study requires K=1")

    history_values = raw["history"]
    if not isinstance(history_values, list):
        raise StudyConfigError("history must be an ordered JSON array")
    if len(history_values) != EXPECTED_HISTORY_FILES:
        raise StudyConfigError(
            f"history must contain {EXPECTED_HISTORY_FILES} ordered files"
        )
    history_paths = tuple(
        _path(base, value, label=f"history[{index}]")
        for index, value in enumerate(history_values)
    )
    if len(set(history_paths)) != len(history_paths):
        raise StudyConfigError("history paths must be unique")
    history_records = load_research_histories(
        history_paths,
        expected_problem_id=problem_id,
    )
    if not history_records:
        raise StudyConfigError("history ON arm must expose a nonempty ordered history")

    model = str(raw["model"] or "").strip()
    base_url = str(raw["base_url"] or "").strip().rstrip("/")
    reasoning_effort = str(raw["reasoning_effort"] or "").strip()
    if model != EXPECTED_MODEL:
        raise StudyConfigError(f"model must be {EXPECTED_MODEL}")
    if base_url != EXPECTED_BASE_URL:
        raise StudyConfigError(f"base_url must be {EXPECTED_BASE_URL}")
    if not reasoning_effort:
        raise StudyConfigError("reasoning_effort must be nonempty")
    rounds = _positive_int(raw["rounds"], label="rounds")
    if rounds != 2:
        raise StudyConfigError(
            "matched development arms require exactly two screening-stage opportunities"
        )
    provider_call_cap = _positive_int(
        raw["provider_call_cap"], label="provider_call_cap"
    )
    outer_hardwall_sec = _positive_int(
        raw["outer_hardwall_sec"], label="outer_hardwall_sec"
    )
    time_limit_sec = _positive_int(raw["time_limit_sec"], label="time_limit_sec")

    block_values = raw["blocks"]
    if not isinstance(block_values, list) or len(block_values) != EXPECTED_BLOCKS:
        raise StudyConfigError(f"blocks must contain exactly {EXPECTED_BLOCKS} values")
    blocks: list[StudyBlock] = []
    all_screening: set[str] = set()
    first_arm_counts = {arm: 0 for arm in ARMS}
    for index, block_value in enumerate(block_values, 1):
        block_raw = _mapping(block_value, label=f"blocks[{index - 1}]")
        block_fields = {"id", "order", "split", "seeds"}
        _exact_fields(
            block_raw,
            allowed=block_fields,
            required=block_fields,
            label=f"blocks[{index - 1}]",
        )
        expected_id = f"block-{index:02d}"
        if block_raw["id"] != expected_id:
            raise StudyConfigError(f"block {index} id must be {expected_id}")
        order_raw = block_raw["order"]
        if not isinstance(order_raw, list) or sorted(order_raw) != list(ARMS):
            raise StudyConfigError(f"{expected_id}.order must contain off and on once")
        order = (str(order_raw[0]), str(order_raw[1]))
        first_arm_counts[order[0]] += 1
        split_path = _path(base, block_raw["split"], label=f"{expected_id}.split")
        seeds_path = _path(base, block_raw["seeds"], label=f"{expected_id}.seeds")
        split = SplitManifest.from_yaml(split_path)
        seeds = SeedLedgerConfig.from_yaml(seeds_path)
        expected_screening = tuple(
            spec.relative_path for spec in specs_for_block(index)
        )
        if tuple(split.screening) != expected_screening:
            raise StudyConfigError(
                f"{expected_id}.screening differs from the fixed synthetic generator"
            )
        for spec in specs_for_block(index):
            generated_path = data_root / spec.relative_path
            try:
                generated_text = generated_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise StudyConfigError(
                    f"cannot read generated screening case {generated_path}: {exc}"
                ) from exc
            if generated_text != render_case(spec):
                raise StudyConfigError(
                    "generated screening case differs from exact regeneration: "
                    f"{generated_path}"
                )
        if len(split.screening) != 6:
            raise StudyConfigError(f"{expected_id}.screening must contain six cases")
        if len(split.validation) != 1 or len(split.frozen) != 1:
            raise StudyConfigError(
                f"{expected_id} must reserve one undispatched validation and frozen case"
            )
        if len(split.canary) != 1:
            raise StudyConfigError(f"{expected_id}.canary must contain one case")
        overlap = all_screening.intersection(split.screening)
        if overlap:
            raise StudyConfigError(
                f"fresh screening populations overlap: {min(overlap)}"
            )
        all_screening.update(split.screening)
        _validate_case_paths(
            split,
            adapter=adapter,
            problem_dir=problem_path.parent,
            data_root=data_root,
            label=expected_id,
        )
        _validate_seed_ledger(seeds, label=expected_id)
        if len(seeds.screening) != 2:
            raise StudyConfigError(f"{expected_id}.screening must contain two seeds")
        validate_requested_screening_expansion(
            config=protocol,
            split_manifest=split,
            requested_rounds=rounds,
        )
        blocks.append(
            StudyBlock(
                block_id=expected_id,
                order=order,
                split_path=split_path,
                seeds_path=seeds_path,
                split=split,
                seeds=seeds,
            )
        )
    if first_arm_counts != {"off": 2, "on": 3}:
        raise StudyConfigError(
            "block order must counterbalance 3 ON-first / 2 OFF-first"
        )
    resolved_screening_limits = _resolved_screening_time_limits(
        protocol=protocol,
        cases=tuple(case for block in blocks for case in block.split.screening),
        fallback_time_limit_sec=time_limit_sec,
    )
    if set(resolved_screening_limits) != {time_limit_sec}:
        raise StudyConfigError(
            "every screening case must resolve to the uniform study time limit "
            f"of {time_limit_sec} seconds"
        )

    return PreparedStudy(
        config_path=config_path,
        problem_path=problem_path,
        problem_dir=problem_path.parent,
        data_root=data_root,
        protocol_path=protocol_path,
        protocol=protocol,
        research_input_path=research_input_path,
        code_research_limits_path=code_limits_path,
        history_paths=history_paths,
        history_records=tuple(history_records),
        model=model,
        base_url=base_url,
        reasoning_effort=reasoning_effort,
        rounds=rounds,
        provider_call_cap=provider_call_cap,
        outer_hardwall_sec=outer_hardwall_sec,
        time_limit_sec=time_limit_sec,
        blocks=tuple(blocks),
    )


def campaign_dir(output_root: str | Path, block: StudyBlock, arm: str) -> Path:
    if arm not in ARMS:
        raise StudyConfigError(f"unknown arm: {arm}")
    return Path(output_root).expanduser().resolve() / block.block_id / arm


def campaign_artifact_paths(
    output_root: str | Path, block: StudyBlock, arm: str
) -> dict[str, Path]:
    root = campaign_dir(output_root, block, arm)
    return {
        "status": root / "status.json",
        "summary": root / "campaign_summary.json",
        "history": root / "research_history.jsonl",
        "traces": root / "llm_traces",
    }


def build_campaign_command(
    study: PreparedStudy,
    block: StudyBlock,
    arm: str,
    output_root: str | Path,
    *,
    python: str | Path | None = None,
) -> list[str]:
    """Build one normal campaign command; only ON receives prior history."""

    if arm not in ARMS:
        raise StudyConfigError(f"unknown arm: {arm}")
    command = [
        str(python or sys.executable),
        "-B",
        "-m",
        "scion.cli.main",
        "run",
        "--problem",
        str(study.problem_path),
        "--research-input",
        str(study.research_input_path),
    ]
    if arm == "on":
        for path in study.history_paths:
            command.extend(("--research-history", str(path)))
    command.extend(
        (
            "--code-research-limits",
            str(study.code_research_limits_path),
            "--protocol",
            str(study.protocol_path),
            "--split",
            str(block.split_path),
            "--seeds",
            str(block.seeds_path),
            "--time-limit-sec",
            str(study.time_limit_sec),
            "--provider-call-cap",
            str(study.provider_call_cap),
            "--outer-hardwall-sec",
            str(study.outer_hardwall_sec),
            "--rounds",
            str(study.rounds),
            "--campaign-dir",
            str(campaign_dir(output_root, block, arm)),
        )
    )
    return command


def iter_campaigns(study: PreparedStudy) -> Sequence[tuple[StudyBlock, str]]:
    return tuple((block, arm) for block in study.blocks for arm in block.order)


def live_environment(study: PreparedStudy) -> dict[str, str]:
    """Return the same local-model and process environment for every arm."""

    environment = dict(os.environ)
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
            "PYTHONHASHSEED": "0",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "SCION_PROBLEM_DATA_ROOT": str(study.data_root),
            "SCION_MODEL": study.model,
            "SCION_REASONING_EFFORT": study.reasoning_effort,
            "SCION_BASE_URL": study.base_url,
            "SCION_LLM_TIMEOUT_SEC": "120",
            "SCION_LLM_HYPOTHESIS_RESEARCH_TURN_TIMEOUT_SEC": "120",
            "SCION_LLM_CODE_RESEARCH_TURN_TIMEOUT_SEC": "240",
            "SCION_LLM_CODE_RESEARCH_FINALIZE_TIMEOUT_SEC": "240",
        }
    )
    return environment


def preflight_summary(study: PreparedStudy, output_root: str | Path) -> dict[str, Any]:
    screening_limits = _resolved_screening_time_limits(
        protocol=study.protocol,
        cases=tuple(case for block in study.blocks for case in block.split.screening),
        fallback_time_limit_sec=study.time_limit_sec,
    )
    return {
        "status": "ready",
        "model": study.model,
        "blocks": len(study.blocks),
        "arms": study.total_arms,
        "history_files_on": len(study.history_paths),
        "history_records_on": len(study.history_records),
        "history_files_off": 0,
        "k": 1,
        "rounds_per_arm": study.rounds,
        "provider_call_cap_per_arm": study.provider_call_cap,
        "provider_call_cap_total": study.provider_call_cap_total,
        "formal_stage_cap_total": study.formal_stage_cap_total,
        "screening_cases": sum(len(block.split.screening) for block in study.blocks),
        "screening_cases_unique": len(
            {case for block in study.blocks for case in block.split.screening}
        ),
        "screening_cases_adapter_loaded": sum(
            len(block.split.screening) for block in study.blocks
        ),
        "screening_time_limit_sec_unique": sorted(set(screening_limits)),
        "screening_initial_positions": [0, 2, 5],
        "screening_initial_strata": ["small", "medium", "large"],
        "screening_generation_inputs": [
            "fixed_block",
            "fixed_position",
            "fixed_structure",
            "fixed_seed",
            "fixed_dimension",
            "fixed_demand_bounds",
            "fixed_capacity",
            "fixed_allowed_routes",
        ],
        "screening_generation_namespace": GENERATED_NAMESPACE,
        "screening_generation_structures": ["uniform", "clustered", "radial"],
        "screening_exact_regeneration_checked": len(CASE_SPECS),
        "screening_arm_input_bytes_identical": True,
        "screening_selection_reads_outcomes": False,
        "screening_exclusion_audit_at_freeze": dict(SCREENING_EXCLUSION_AUDIT),
        "heldout_stage_reachable": False,
        "outer_hardwall_sec_per_arm": study.outer_hardwall_sec,
        "output_root": str(Path(output_root).expanduser().resolve()),
    }


def execute_study(study: PreparedStudy, output_root: str | Path) -> int:
    """Run every normal arm, stopping only on infra faults or missing artifacts."""

    root = Path(output_root).expanduser().resolve()
    if root.exists() or root.is_symlink():
        raise StudyConfigError(f"execute requires a fresh output root: {root}")
    environment = live_environment(study)
    if not str(environment.get("SCION_API_KEY", "")).strip():
        raise StudyConfigError("execute requires SCION_API_KEY for the local proxy")

    for block, arm in iter_campaigns(study):
        command = build_campaign_command(study, block, arm, root)
        print(f"running {block.block_id}/{arm}", flush=True)
        completed = subprocess.run(
            command, cwd=SCION_ROOT, env=environment, check=False
        )
        if completed.returncode not in CONTINUE_EXIT_CODES:
            print(
                f"stopping study after {block.block_id}/{arm}: "
                f"exit={completed.returncode}",
                file=sys.stderr,
                flush=True,
            )
            return int(completed.returncode)
        artifacts = campaign_artifact_paths(root, block, arm)
        if not artifacts["status"].is_file() or not artifacts["summary"].is_file():
            print(
                f"stopping study after {block.block_id}/{arm}: "
                "ordinary terminal artifacts are missing",
                file=sys.stderr,
                flush=True,
            )
            return 1
        print(
            json.dumps(
                {name: str(path) for name, path in artifacts.items()},
                sort_keys=True,
            ),
            flush=True,
        )
    return 0


def _campaign_trajectory(campaign_path: Path) -> dict[str, Any]:
    status_path = campaign_path / "status.json"
    summary_path = campaign_path / "campaign_summary.json"
    if not status_path.is_file() or not summary_path.is_file():
        raise StudyConfigError(
            f"ordinary campaign artifacts are incomplete: {campaign_path}"
        )
    status = _mapping(_load_json(status_path), label=f"{campaign_path}/status")
    summary = _mapping(_load_json(summary_path), label=f"{campaign_path}/summary")
    history_path = campaign_path / "research_history.jsonl"
    history = (
        load_research_histories((history_path,), expected_problem_id="cvrp")
        if history_path.is_file()
        else ()
    )
    trace_dir = campaign_path / "llm_traces"
    traces = (
        tuple(
            _mapping(_load_json(path), label=f"trace {path}")
            for path in sorted(trace_dir.glob("*.json"))
            if path.is_file()
        )
        if trace_dir.is_dir()
        else ()
    )
    return calculate_research_trajectory(
        status=status,
        campaign_summary=summary,
        research_history=history,
        hypothesis_research_traces=traces,
    )


def _aggregate_comparisons(
    comparisons: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if not comparisons:
        return {"blocks": 0, "endpoints": {}}
    endpoint_names = tuple(comparisons[0]["endpoints"])
    if any(
        tuple(comparison["endpoints"]) != endpoint_names for comparison in comparisons
    ):
        raise StudyConfigError("trajectory comparisons expose different endpoints")
    endpoints: dict[str, Any] = {}
    for name in endpoint_names:
        rows = [comparison["endpoints"][name] for comparison in comparisons]
        differences = [row["difference_on_minus_off"] for row in rows]
        matched = [
            (row["history_on"], row["history_off"])
            for row in rows
            if row["history_on"] is not None and row["history_off"] is not None
        ]
        observed_pairs = len(matched)
        endpoints[name] = {
            "history_on_by_block": [row["history_on"] for row in rows],
            "history_off_by_block": [row["history_off"] for row in rows],
            "difference_on_minus_off_by_block": differences,
            "matched_history_on_mean": (
                sum(value[0] for value in matched) / observed_pairs
                if observed_pairs
                else None
            ),
            "matched_history_off_mean": (
                sum(value[1] for value in matched) / observed_pairs
                if observed_pairs
                else None
            ),
            "matched_mean_delta_on_minus_off": (
                sum(value[0] - value[1] for value in matched) / observed_pairs
                if observed_pairs
                else None
            ),
            "observed_pairs": observed_pairs,
        }
    return {"blocks": len(comparisons), "endpoints": endpoints}


def analyze_existing(study: PreparedStudy, output_root: str | Path) -> dict[str, Any]:
    """Load ten ordinary roots and compare separate trajectory endpoints."""

    root = Path(output_root).expanduser().resolve()
    block_reports: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    for block in study.blocks:
        off = _campaign_trajectory(campaign_dir(root, block, "off"))
        on = _campaign_trajectory(campaign_dir(root, block, "on"))
        comparison = compare_history_trajectories(history_on=on, history_off=off)
        comparisons.append(comparison)
        block_reports.append(
            {
                "block": block.block_id,
                "history_off": off,
                "history_on": on,
                "comparison": comparison,
            }
        )
    return {
        "schema_version": "scion.cvrp_history_matched_analysis.v1",
        "blocks": block_reports,
        "aggregate_descriptive_endpoints": _aggregate_comparisons(comparisons),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--print-commands", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--analyze-existing", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        study = load_study_config(args.config)
        if args.preflight:
            print(json.dumps(preflight_summary(study, args.output_root), indent=2))
            return 0
        if args.print_commands:
            environment = live_environment(study)
            print(
                " ".join(
                    f"{key}={json.dumps(environment[key])}"
                    for key in (
                        "SCION_PROBLEM_DATA_ROOT",
                        "SCION_MODEL",
                        "SCION_REASONING_EFFORT",
                        "SCION_BASE_URL",
                    )
                )
            )
            for block, arm in iter_campaigns(study):
                print(
                    json.dumps(
                        build_campaign_command(study, block, arm, args.output_root),
                        ensure_ascii=False,
                    )
                )
            return 0
        if args.analyze_existing:
            print(
                json.dumps(
                    analyze_existing(study, args.output_root),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        return execute_study(study, args.output_root)
    except (StudyConfigError, TypeError, ValueError) as exc:
        print(f"PREP_INVALID: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ARMS",
    "DEFAULT_CONFIG",
    "SCREENING_EXCLUSION_AUDIT",
    "PreparedStudy",
    "StudyBlock",
    "StudyConfigError",
    "analyze_existing",
    "build_campaign_command",
    "campaign_artifact_paths",
    "campaign_dir",
    "execute_study",
    "iter_campaigns",
    "live_environment",
    "load_study_config",
    "main",
    "preflight_summary",
]
