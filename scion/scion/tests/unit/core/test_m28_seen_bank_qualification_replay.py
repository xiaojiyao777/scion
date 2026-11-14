"""Provider- and solver-free M28 context and nearest-history audit replay."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from copy import deepcopy
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from scion.cli.commands.init_run import _load_research_input
from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.core.code_research_limits import load_code_research_limits
from scion.core.research_history import (
    load_research_histories,
    provider_research_history,
)
from scion.problems.cvrp.prior_research_observation import (
    CvrpPriorResearchObservationProvider,
)
from scion.proposal.engine import build_prompt_turn_snapshot
from scion.proposal.hypothesis_research_corpus import (
    build_hypothesis_research_corpus,
)
from scion.proposal.hypothesis_research_session import (
    HypothesisResearchFinalized,
    HypothesisResearchSession,
)

_SCION_ROOT = Path(__file__).resolve().parents[4]
_INPUT_ROOT = _SCION_ROOT / "docs" / "experiments" / "v0.4" / "inputs"
_M27_INPUT = _INPUT_ROOT / "v04-cvrp-m27-m26-terminal-research-input.json"
_M28_INPUT = _INPUT_ROOT / "v04-cvrp-m28-m27-terminal-research-input.json"
_M28_HISTORY_COPY = _INPUT_ROOT / "v04-cvrp-m28-m27-research-history.jsonl"
_M28_HISTORY_PATHS = tuple(
    _INPUT_ROOT / filename
    for filename in (
        "v04-cvrp-m10-m9-research-history.jsonl",
        "v04-cvrp-m11-m10-research-history.jsonl",
        "v04-cvrp-m12-m11-research-history.jsonl",
        "v04-cvrp-m13-m12-research-history.jsonl",
        "v04-cvrp-m14-m13-research-history.jsonl",
        "v04-cvrp-m15-m14-research-history.jsonl",
        "v04-cvrp-m16-m15-research-history.jsonl",
        "v04-cvrp-m19-m16-research-history.jsonl",
        "v04-cvrp-m20-m19-research-history.jsonl",
        "v04-cvrp-m21-m20-research-history.jsonl",
        "v04-cvrp-m22-m21-research-history.jsonl",
        "v04-cvrp-m24-m22-research-history.jsonl",
        "v04-cvrp-m26-m25-research-history.jsonl",
        "v04-cvrp-m27-m26-research-history.jsonl",
        "v04-cvrp-m28-m27-research-history.jsonl",
    )
)
_LIMITS_PATH = _INPUT_ROOT / "v04-cvrp-m11-code-research-limits.json"
_M24_PROTOCOL = (
    _INPUT_ROOT / "v04-cvrp-m24-autonomous-direction-research-development-protocol.yaml"
)
_M24_SPLIT = (
    _INPUT_ROOT / "v04-cvrp-m24-autonomous-direction-research-development-split.yaml"
)
_M24_SEEDS = (
    _INPUT_ROOT / "v04-cvrp-m24-autonomous-direction-research-development-seeds.yaml"
)
_M28_PROTOCOL = _INPUT_ROOT / "v04-cvrp-m28-seen-bank-qualification-protocol.yaml"
_M28_SPLIT = _INPUT_ROOT / "v04-cvrp-m28-seen-bank-qualification-split.yaml"
_M28_SEEDS = _INPUT_ROOT / "v04-cvrp-m28-seen-bank-qualification-seeds.yaml"
_M29_POOL_STEMS = (
    "v04-cvrp-m19-fresh-development",
    "v04-cvrp-m20-frontier-development",
    "v04-cvrp-m22-provider-recovery-development",
)
_M21_SPLIT = _INPUT_ROOT / "v04-cvrp-m21-strict-expansion-development-split.yaml"
_FIXTURE_PATH = (
    _SCION_ROOT
    / "scion"
    / "tests"
    / "fixtures"
    / "m28_seen_bank_qualification_replay.json"
)

_CVRPLIB_CASE = re.compile(r"^(A|B|P|X)-n([1-9][0-9]*)-k([1-9][0-9]*)\.vrp$")


def _fixture() -> dict[str, Any]:
    value = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _normalized_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.casefold()).strip("_")


def _iter_keys(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _iter_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_keys(child)


def _iter_scalars(value: Any):
    if isinstance(value, dict):
        for child in value.values():
            yield from _iter_scalars(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_scalars(child)
    else:
        yield value


def _diagnostics(observation: dict[str, Any]) -> dict[str, Any]:
    return {
        item["name"]: item["value"]
        for item in observation["terminal"]["failure"]["diagnostics"]
    }


def _tracked_cvrp_seed_values(base_revision: str) -> set[int]:
    repository = _SCION_ROOT.parent
    raw_paths = subprocess.check_output(
        ["git", "ls-tree", "-r", "-z", "--name-only", base_revision],
        cwd=repository,
    )
    paths = [
        raw_path.decode("utf-8")
        for raw_path in raw_paths.split(b"\0")
        if raw_path and (b"cvrp" in raw_path.lower() or raw_path == b"scion/TASK.md")
    ]
    seed_values: set[int] = set()

    def collect(value: Any, *, below_seed_key: bool) -> None:
        if type(value) is int:
            if below_seed_key:
                seed_values.add(value)
            return
        if isinstance(value, dict):
            for key, child in value.items():
                collect(
                    child,
                    below_seed_key=(
                        below_seed_key
                        or (isinstance(key, str) and "seed" in key.casefold())
                    ),
                )
            return
        if isinstance(value, list):
            for child in value:
                collect(child, below_seed_key=below_seed_key)

    integer_pattern = re.compile(r"(?<![A-Za-z0-9])([0-9]{1,9})(?![A-Za-z0-9])")
    for path in paths:
        text = subprocess.check_output(
            ["git", "show", f"{base_revision}:{path}"],
            cwd=repository,
        ).decode("utf-8")
        suffix = PurePosixPath(path).suffix.casefold()
        parsed: Any = None
        if suffix == ".json":
            parsed = json.loads(text)
        elif suffix in {".yaml", ".yml"}:
            parsed = yaml.safe_load(text)
        if parsed is not None:
            collect(
                parsed,
                below_seed_key="seed" in PurePosixPath(path).name.casefold(),
            )
        for line in text.splitlines():
            if "seed" in line.casefold():
                seed_values.update(
                    int(match.group(1)) for match in integer_pattern.finditer(line)
                )
    return seed_values


def _canonical_m29_pool_case(raw: Any) -> tuple[str, str, int]:
    assert isinstance(raw, str)
    normalized = raw.strip().replace("\\", "/")
    path = PurePosixPath(normalized)
    canonical = path.as_posix()
    assert canonical == normalized
    assert not path.is_absolute()
    assert path.parts[0] == "cvrplib"
    assert all(part not in {"", ".", ".."} for part in path.parts)
    match = _CVRPLIB_CASE.fullmatch(path.name)
    assert match is not None
    return canonical, match.group(1), int(match.group(2))


def _time_band(dimension: int) -> int:
    if dimension <= 100:
        return 30
    if dimension <= 200:
        return 45
    if dimension <= 350:
        return 60
    if dimension <= 700:
        return 90
    if dimension <= 1001:
        return 120
    raise AssertionError(f"M29 pool dimension is outside the frozen bands: {dimension}")


def _provider_context(
    fixture: dict[str, Any],
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...], dict[str, Any]]:
    research_input = _load_research_input(_M28_INPUT)
    history = load_research_histories(
        _M28_HISTORY_PATHS,
        expected_problem_id="cvrp",
    )
    projector = CvrpPriorResearchObservationProvider()
    observations = [
        projector.project_prior_research_observation(observation=observation)
        for observation in research_input["observations"]
    ]
    source = fixture["source"]
    context = {
        "problem_summary": "Generic bounded optimization subject.",
        "branch_id": "m28-provider-free-nearest-history-audit",
        "research_surfaces": [{"name": "solver_design", "kind": "generic_algorithm"}],
        "available_actions": ["modify"],
        "existing_target_files": [source["path"]],
        "champion_operators_code": (
            f"### {source['path']}\n```python\n{source['content']}```\n"
        ),
        "champion_stats": {},
        "prior_research_observations": observations,
        "prior_research_history": provider_research_history(history),
        "research_question": {"current_question": research_input["current_question"]},
    }
    return research_input, history, context


def _basis(
    fixture: dict[str, Any],
    *,
    read_refs: list[str],
    nearest_prior_refs: list[str],
) -> dict[str, Any]:
    return {
        "read_refs": read_refs,
        "nearest_prior_refs": nearest_prior_refs,
        **deepcopy(fixture["research_basis"]),
    }


def _action_names(snapshot) -> set[str]:
    return {
        branch["properties"]["action"]["enum"][0]
        for branch in snapshot.provider_tool["input_schema"]["oneOf"]
    }


class _SequenceCreative:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.contexts: list[dict[str, Any]] = []
        self.snapshots = []

    def call_hypothesis_research_turn(self, snapshot):
        self.snapshots.append(snapshot)
        self.contexts.append(deepcopy(snapshot.structured_context))
        return deepcopy(self.responses.pop(0))


def test_m28_real_context_keeps_native_audit_and_filters_provider_history() -> None:
    fixture = _fixture()
    prior_input = _load_research_input(_M27_INPUT)
    research_input, history, context = _provider_context(fixture)
    expected = fixture["expected"]

    assert research_input["observations"][:6] == prior_input["observations"]
    assert len(research_input["observations"]) == expected["prior_observations"]
    assert len(_M28_HISTORY_PATHS) == expected["history_files"]
    assert len(history) == expected["native_history"]

    copied_bytes = _M28_HISTORY_COPY.read_bytes()
    assert len(copied_bytes) == expected["m27_history_bytes"]
    assert copied_bytes.count(b"\n") == expected["m27_history_lines"]
    canonical_m27 = load_research_histories(
        (_M28_HISTORY_COPY,),
        expected_problem_id="cvrp",
    )
    assert history[-2:] == canonical_m27
    assert [
        record["protocol"]["evidence"]["protocol_outcome"]["gate_outcome"]
        for record in canonical_m27
    ] == ["expand", "fail"]
    assert [record["decision"]["value"] for record in canonical_m27] == [
        "expand_screening",
        "abandon",
    ]

    _sources, indexed_history, compact = build_hypothesis_research_corpus(context)
    assert len(indexed_history) == expected["provider_history_entries"]
    assert [entry["ref"] for entry in indexed_history] == [
        f"history-{ordinal:04d}"
        for ordinal in range(1, expected["provider_history_entries"] + 1)
    ]
    assert [entry["ref"] for entry in indexed_history[:7]] == expected[
        "provider_observation_refs"
    ]
    assert [entry["kind"] for entry in indexed_history[:7]] == [
        "prior_research_observations"
    ] * 7
    assert [entry["kind"] for entry in indexed_history[7:]] == [
        "prior_research_history"
    ] * expected["provider_scientific_history"]
    assert [entry["ref"] for entry in indexed_history[-2:]] == expected[
        "m27_history_provider_refs"
    ]
    assert [entry["record"] for entry in indexed_history[-2:]] == (
        context["prior_research_history"][-2:]
    )
    assert compact["prior_research_observations"]["record_count"] == 7
    assert compact["prior_research_history"]["record_count"] == expected[
        "provider_scientific_history"
    ]
    eligible_fields = (
        "text",
        "hypothesis_text",
        "target_file",
        "change_locus",
        "action",
        "predicted_direction",
        "target_weakness",
        "expected_effect",
    )
    eligible = [
        entry
        for entry in indexed_history
        if isinstance(entry["index"].get("hypothesis"), dict)
        and any(
            isinstance(entry["index"]["hypothesis"].get(field), str)
            and bool(entry["index"]["hypothesis"][field].strip())
            for field in eligible_fields
        )
    ]
    assert len(eligible) == expected["eligible_headline_entries"]
    assert [entry["ref"] for entry in eligible] == [
        f"history-{ordinal:04d}"
        for ordinal in range(8, expected["provider_history_entries"] + 1)
    ]


def test_m28_terminal_observation_is_strict_aggregate_public_context() -> None:
    fixture = _fixture()
    research_input, _history, context = _provider_context(fixture)
    assert (
        research_input["observations"][:6]
        == _load_research_input(_M27_INPUT)["observations"]
    )
    terminal = research_input["observations"][6]
    projected = context["prior_research_observations"][6]

    assert terminal["observation_kind"] == "autonomous_candidate_evaluation_terminal"
    assert [stage["block"] for stage in terminal["completed_stages"]] == [
        "initial",
        "expanded",
    ]
    assert [stage["valid_pairs"] for stage in terminal["completed_stages"]] == [6, 10]
    assert [
        stage["case_outcomes"]["ci_low"] for stage in terminal["completed_stages"]
    ] == [
        0,
        -0.5,
    ]
    diagnostics = _diagnostics(terminal)
    assert diagnostics["provider_calls_used"] == 8
    assert diagnostics["hypothesis_research_calls"] == 4
    assert diagnostics["code_research_calls"] == 3
    assert diagnostics["code_final_decision_calls"] == 1
    assert diagnostics["code_candidates"] == 1
    assert diagnostics["solver_calls"] == 42
    assert diagnostics["nearest_history_audit_accepted_hypotheses"] == 1
    assert diagnostics["nearest_history_audit_triggered_hypotheses"] == 1
    assert diagnostics["nearest_history_audit_incomplete_hypotheses"] == 0
    assert diagnostics["exact_structured_h_replays"] == 0
    assert diagnostics["exact_ordered_patch_replays"] == 0
    assert diagnostics["initial_screen_valid_pairs"] == 6
    assert diagnostics["expanded_screen_valid_pairs"] == 10
    assert diagnostics["expanded_screen_planned_pairs"] == 12
    assert diagnostics["candidate_only_failures"] == 2
    assert diagnostics["validation_reached"] is False
    assert diagnostics["frozen_reached"] is False
    assert projected["observed_outputs"] == {
        "terminal_stage_metrics": True,
        "terminal_safe_features": True,
        "terminal_decision": True,
        "later_stage_metrics": False,
        "promotion": False,
        "retained_baseline_comparison": False,
    }
    claim = terminal["claim_context"]
    assert (
        claim["population_selection_outcome_blind_relative_to_exact_estimand"] is False
    )
    assert claim["incremental_effect_isolated"] is False
    assert claim["globally_case_unseen"] is False
    # Direct equality found no prior exact candidate; this is not a novelty claim.
    assert claim["exact_candidate_outcome_overlap_count"] == 0

    normalized_keys = {_normalized_key(key) for key in _iter_keys(terminal)}
    assert normalized_keys.isdisjoint(
        {
            "action",
            "change_locus",
            "editable_source",
            "falsifier_source",
            "mechanism",
            "patch",
            "provider_response",
            "provider_trace",
            "repair",
            "research_basis",
            "surface",
            "target_file",
        }
    )
    strings = [value for value in _iter_scalars(terminal) if isinstance(value, str)]
    assert all(".vrp" not in value.casefold() for value in strings)
    assert all("policies/" not in value.casefold() for value in strings)
    assert {5405, 4354, 2959, 6748}.isdisjoint(set(_iter_scalars(terminal)))
    question = research_input["current_question"]
    prior_targets = {
        record["hypothesis"].get("target_file")
        for record in context["prior_research_history"]
        if isinstance(record.get("hypothesis"), dict)
    }
    assert all(target not in question for target in prior_targets if target)


def test_m28_changes_only_expansion_seed_count_and_two_prefrozen_seeds() -> None:
    m24_protocol = ProtocolConfig.from_yaml(_M24_PROTOCOL)
    protocol = ProtocolConfig.from_yaml(_M28_PROTOCOL)
    m24_split = SplitManifest.from_yaml(_M24_SPLIT)
    split = SplitManifest.from_yaml(_M28_SPLIT)
    m24_seeds = SeedLedgerConfig.from_yaml(_M24_SEEDS)
    seeds = SeedLedgerConfig.from_yaml(_M28_SEEDS)

    prior_protocol = m24_protocol.model_dump(mode="json")
    current_protocol = protocol.model_dump(mode="json")
    assert current_protocol.pop("version") == "0.4-cvrp-m28-seen-bank-qualification"
    assert prior_protocol.pop("version") == (
        "0.4-cvrp-m24-autonomous-direction-research-development"
    )
    assert prior_protocol["screening"].pop("expand_n_seeds") == 2
    assert current_protocol["screening"].pop("expand_n_seeds") == 4
    assert current_protocol == prior_protocol

    prior_split = m24_split.model_dump(mode="json")
    current_split = split.model_dump(mode="json")
    assert current_split.pop("version") == "0.4-cvrp-m28-seen-bank-qualification"
    assert prior_split.pop("version") == (
        "0.4-cvrp-m24-autonomous-direction-research-development"
    )
    assert current_split == prior_split

    assert protocol.screening.n_seeds == 2
    assert protocol.screening.effective_expand_n_seeds == 4
    assert tuple(split.screening[:3]) == protocol.screening.priority_case_ids
    assert len(split.screening) == 6
    assert seeds.screening == [4358, 1868, 10684, 14577]
    assert seeds.screening[:2] == m24_seeds.screening
    assert seeds.validation == m24_seeds.validation
    assert seeds.frozen == m24_seeds.frozen
    assert seeds.canary == m24_seeds.canary
    assert protocol.version == split.version == seeds.version

    initial_cases = split.screening[:3]
    expanded_cases = split.screening[:6]
    time_limits = protocol.runtime.time_limits
    initial_subject_seconds = (
        2
        * 2
        * sum(
            time_limits.resolve(
                stage="screening",
                case_path=case,
                fallback_time_limit_sec=30,
            )
            for case in initial_cases
        )
    )
    expanded_subject_seconds = (
        2
        * 4
        * sum(
            time_limits.resolve(
                stage="screening",
                case_path=case,
                fallback_time_limit_sec=30,
            )
            for case in expanded_cases
        )
    )
    assert initial_subject_seconds == 480
    assert expanded_subject_seconds == 2280
    assert initial_subject_seconds + expanded_subject_seconds == 2760

    verification_solver_calls = 8
    canary_solver_calls = 4
    formal_solver_calls = 60
    total_solver_calls = (
        verification_solver_calls + canary_solver_calls + formal_solver_calls
    )
    assert total_solver_calls == 72
    solver_nominal_seconds = 3040
    communicate_guarded_seconds = solver_nominal_seconds + total_solver_calls * 15
    assert communicate_guarded_seconds == 4120
    assert 7080 + 450 + 480 + communicate_guarded_seconds == 12130
    conservative_elapsed_seconds = communicate_guarded_seconds + total_solver_calls * (
        5 + 1
    )
    assert conservative_elapsed_seconds == 4552
    all_known_elapsed_seconds = 7080 + 450 + 480 + conservative_elapsed_seconds
    assert all_known_elapsed_seconds == 12562
    assert 15000 - all_known_elapsed_seconds == 2438


def test_m28_new_seeds_replay_from_frozen_metadata_scan() -> None:
    selection = _fixture()["seed_selection"]
    seed_values = _tracked_cvrp_seed_values(selection["base_revision"])
    assert len(seed_values) == selection["tracked_seed_values"]
    assert (
        sum(
            selection["domain_min"] <= value <= selection["domain_max"]
            for value in seed_values
        )
        == selection["excluded_domain_values"]
    )

    salt = selection["salt"].encode("utf-8")
    ranked = sorted(
        (
            hashlib.sha256(salt + b"\0" + str(seed).encode("ascii")).digest(),
            seed,
        )
        for seed in range(selection["domain_min"], selection["domain_max"] + 1)
        if seed not in seed_values
    )
    expected = selection["selected"]
    assert [seed for _digest, seed in ranked[:2]] == [item["seed"] for item in expected]
    assert [digest.hex() for digest, _seed in ranked[:2]] == [
        item["digest"] for item in expected
    ]


def test_conditional_m29_selector_pool_is_feasible_without_ranking_identities() -> None:
    base_revision = _fixture()["seed_selection"]["base_revision"]
    base_tree = subprocess.check_output(
        [
            "git",
            "ls-tree",
            "-r",
            "-z",
            base_revision,
            "--",
            "scion/scion/problems/cvrp",
        ],
        cwd=_SCION_ROOT.parent,
    )
    source_records = [record for record in base_tree.split(b"\0") if record]
    assert len(source_records) == 99
    assert all(
        record.split(b"\t", 1)[0].split()[:2]
        in ([b"100644", b"blob"], [b"100755", b"blob"])
        for record in source_records
    )

    raw_cases: list[Any] = []
    reserve_seeds: list[Any] = []
    for stem in _M29_POOL_STEMS:
        split = yaml.safe_load((_INPUT_ROOT / f"{stem}-split.yaml").read_text())
        seeds = yaml.safe_load((_INPUT_ROOT / f"{stem}-seeds.yaml").read_text())
        for field in ("validation", "frozen"):
            raw_cases.extend(split[field])
            reserve_seeds.extend(seeds[field])

    parsed = [_canonical_m29_pool_case(raw) for raw in raw_cases]
    paths = [path for path, _family, _dimension in parsed]
    assert len(paths) == len(set(paths)) == 18
    assert all(type(seed) is int for seed in reserve_seeds)
    assert len(reserve_seeds) == len(set(reserve_seeds)) == 12

    family_counts = {
        family: sum(item_family == family for _path, item_family, _size in parsed)
        for family in ("A", "B", "P", "X")
    }
    band_counts = {
        band: sum(_time_band(size) == band for _path, _family, size in parsed)
        for band in (30, 45, 60, 90, 120)
    }
    assert family_counts == {"A": 3, "B": 1, "P": 3, "X": 11}
    assert band_counts == {30: 7, 45: 2, 60: 5, 90: 3, 120: 1}

    m21 = yaml.safe_load(_M21_SPLIT.read_text())
    m21_cases = {
        value
        for field in ("screening", "validation", "frozen", "canary")
        for value in m21[field]
    }
    m24 = yaml.safe_load(_M24_SPLIT.read_text())
    m24_controls = {*m24["validation"], *m24["frozen"]}
    assert set(paths).isdisjoint(m21_cases)
    assert set(paths).isdisjoint(m24_controls)

    def count(predicate) -> int:
        return sum(predicate(family, size) for _path, family, size in parsed)

    screen_counts = (
        count(lambda family, size: family == "A" and 20 <= size <= 100),
        count(lambda family, size: family == "B" and 20 <= size <= 100),
        count(lambda family, size: family == "P" and 20 <= size <= 100),
        count(lambda family, size: family == "X" and 101 <= size <= 200),
        count(lambda family, size: family == "X" and 201 <= size <= 350),
        count(lambda family, size: family == "X" and 351 <= size <= 700),
    )
    assert all(value >= 1 for value in screen_counts)

    # Prove retained feasibility after any one removal from each overlapping
    # screen stratum without calculating or recording a ranked case identity.
    assert (
        count(lambda family, size: family in {"A", "B", "P"} and 20 <= size <= 100) >= 4
    )
    assert count(lambda family, size: family == "X" and 201 <= size <= 350) >= 2
    assert count(lambda family, size: family == "X" and 351 <= size <= 700) >= 2


def test_conditional_m29_resource_rule_includes_strict_canary() -> None:
    protocol = ProtocolConfig.from_yaml(_M28_PROTOCOL)
    split = SplitManifest.from_yaml(_M28_SPLIT)
    time_limits = protocol.runtime.time_limits

    screen_subject_seconds = 2 * 4 * (30 + 30 + 30 + 45 + 60 + 90)
    validation_subject_seconds = (
        2
        * 2
        * sum(
            time_limits.resolve(
                stage="validation",
                case_path=case,
                fallback_time_limit_sec=30,
            )
            for case in split.validation
        )
    )
    frozen_subject_seconds = (
        2
        * 2
        * sum(
            time_limits.resolve(
                stage="frozen",
                case_path=case,
                fallback_time_limit_sec=30,
            )
            for case in split.frozen
        )
    )
    retained_subject_seconds = 2 * 2 * (30 + 60 + 90)
    canary_subject_seconds = 2 * 10
    assert (
        screen_subject_seconds,
        validation_subject_seconds,
        frozen_subject_seconds,
        retained_subject_seconds,
        canary_subject_seconds,
    ) == (2280, 720, 1080, 720, 20)

    solver_calls = 2 + 48 + 12 + 12 + 12
    nominal_seconds = (
        screen_subject_seconds
        + validation_subject_seconds
        + frozen_subject_seconds
        + retained_subject_seconds
        + canary_subject_seconds
    )
    communicate_guarded_seconds = nominal_seconds + solver_calls * 15
    conservative_elapsed_seconds = communicate_guarded_seconds + solver_calls * (5 + 1)
    assert solver_calls == 86
    assert nominal_seconds == 4820
    assert communicate_guarded_seconds == 6110
    assert conservative_elapsed_seconds == 6626
    assert 8000 - conservative_elapsed_seconds == 1374


def test_m28_actual_context_allows_finalize_without_host_routed_history() -> None:
    fixture = _fixture()
    _research_input, _history, context = _provider_context(fixture)
    first_basis = _basis(
        fixture,
        read_refs=["source-0001"],
        nearest_prior_refs=[],
    )
    creative = _SequenceCreative(
        [
            {"action": "read_source", "ref": "source-0001"},
            {
                "action": "finalize_hypothesis",
                "hypothesis": fixture["hypothesis"],
                "research_basis": first_basis,
            },
        ]
    )
    session = HypothesisResearchSession(
        creative,
        load_code_research_limits(_LIMITS_PATH),
    )

    result = session.run(build_prompt_turn_snapshot("hypothesis", context))

    assert isinstance(result, HypothesisResearchFinalized)
    assert result.research_basis.read_refs == ("source-0001",)
    assert result.research_basis.nearest_prior_refs == ()
    assert session.provider_calls_used == 2
    assert len(creative.contexts) == 2
    assert "finalize_hypothesis" not in _action_names(creative.snapshots[0])
    assert "finalize_hypothesis" in _action_names(creative.snapshots[1])
    assert "required_history_ref" not in json.dumps(creative.contexts, sort_keys=True)


def test_m28_actual_context_accepts_an_agent_selected_history_read() -> (
    None
):
    fixture = _fixture()
    _research_input, _history, context = _provider_context(fixture)
    _sources, indexed_history, _compact = build_hypothesis_research_corpus(context)
    required_ref = fixture["expected"]["generic_fake_h_required_ref"]
    assert required_ref in {entry["ref"] for entry in indexed_history}
    accepted_basis = _basis(
        fixture,
        read_refs=["source-0001", required_ref],
        nearest_prior_refs=[required_ref],
    )
    creative = _SequenceCreative(
        [
            {"action": "read_source", "ref": "source-0001"},
            {"action": "read_history", "ref": required_ref},
            {
                "action": "finalize_hypothesis",
                "hypothesis": fixture["hypothesis"],
                "research_basis": accepted_basis,
            },
        ]
    )
    session = HypothesisResearchSession(
        creative,
        load_code_research_limits(_LIMITS_PATH),
    )

    result = session.run(build_prompt_turn_snapshot("hypothesis", context))

    assert isinstance(result, HypothesisResearchFinalized)
    assert result.research_basis.nearest_prior_refs == (required_ref,)
    assert session.provider_calls_used == 3
    tool_results = creative.contexts[-1]["hypothesis_research"]["tool_results"]
    assert [result["action"] for result in tool_results] == [
        "read_source",
        "read_history",
    ]
    assert all(
        result.get("reason") != fixture["expected"]["feedback_reason"]
        for result in tool_results
    )
