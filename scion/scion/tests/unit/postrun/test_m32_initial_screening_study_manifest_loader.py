from __future__ import annotations

import copy
import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest

import scion.postrun.research_effectiveness as public_api
import scion.postrun.research_effectiveness.comparison as comparison_module
import scion.postrun.research_effectiveness.endpoints as endpoints_module
import scion.postrun.research_effectiveness.study_manifest_io as io_module
import scion.postrun.research_effectiveness.study_manifest_loader as loader_module
import scion.postrun.research_effectiveness.study_root as study_root_module
import scion.postrun.research_effectiveness.study_root_loader as old_loader_module
from scion.core.research_history import _render
from scion.postrun.research_effectiveness.models import (
    LoadedHistoryAvailable,
    LoadedHistoryUnavailable,
    ResearchEffectivenessInputError,
)
from scion.postrun.research_effectiveness.study_manifest_loader import (
    _validate_initial_screening_study_manifest_config_subset,
)
from scion.postrun.research_effectiveness.study_manifest_schema import (
    _JOIN_LIMITATIONS,
    _canonical_json_bytes,
)
from scion.tests.unit.postrun.test_m32_initial_screening_study_manifest_schema import (
    _controls,
    _manifest,
)
from scion.tests.unit.postrun.test_m32_initial_screening_study_root import (
    _block,
    _formal_record,
)

_ERROR = "STUDY_CONFIG_SUBSET_JOIN_INVALID"


def _loader_manifest(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    raw = _manifest()
    raw["problem_id"] = "demo"
    for ordinal, block in enumerate(raw["blocks"], start=1):
        decoded = _block(ordinal)
        for arm in block["arms"]:
            k = 1 if arm["treatment"] == "K1" else 2
            controls = _loader_controls(ordinal, k)
            arm["campaign_id"] = f"block-{ordinal}-k{k}"
            arm["root_path"] = f"outcomes/block-{ordinal}/k{k}"
            arm["declared_controls"] = controls
            artifacts = decoded.k1 if k == 1 else decoded.k2
            _write_root(bundle / arm["root_path"], artifacts, controls)
    path = bundle / "study_manifest.json"
    path.write_bytes(_canonical_json_bytes(raw, max_bytes=16 << 20))
    return path, raw


def _loader_controls(ordinal: int, k: int) -> dict[str, Any]:
    controls = _controls(ordinal, k)
    campaign = controls["campaign"]
    campaign["requested_rounds"] = 1
    campaign["qualification_limits"] = {
        "max_proposal_attempts": 1,
        "max_verified_candidate_chains": 1,
        "max_formal_screening_stages": 1,
    }
    campaign["scheduler"]["max_active_branches"] = 8
    first = f"cases/block-{ordinal}-alpha.vrp"
    second = f"cases/block-{ordinal}-beta.vrp"
    initial = controls["protocol"]["initial_screening"]
    initial["measurement_readiness"]["mde_at_power_80"] = 0.0
    initial["cases_by_action"] = {
        "modify_or_remove": [first, second],
        "create_new": [first, second],
    }
    initial["seeds"] = [ordinal]
    initial["selection"]["n_cases_modify"] = 2
    initial["selection"]["n_cases_create"] = 2
    initial["selection"]["n_seeds"] = 1
    initial["selection"]["priority_case_ids"] = [first, second]
    initial["resolved_time_limits"] = [
        {"case_ref": first, "time_limit_sec": 30},
        {"case_ref": second, "time_limit_sec": 30},
    ]
    return controls


def _write_root(root: Path, artifacts: Any, controls: dict[str, Any]) -> None:
    root.mkdir(parents=True)
    root.chmod(0o700)
    status = copy.deepcopy(artifacts.status)
    summary = copy.deepcopy(artifacts.summary)
    initial = controls["protocol"]["initial_screening"]
    readiness = copy.deepcopy(initial["measurement_readiness"])
    status["measurement_readiness"] = readiness
    summary["measurement_readiness"] = copy.deepcopy(readiness)
    case_refs = initial["cases_by_action"]["modify_or_remove"]
    seeds = initial["seeds"]
    for step in summary["steps"]:
        protocol = step.get("protocol_result")
        if protocol is not None:
            protocol["case_ids"] = list(case_refs)
            protocol["seed_set"] = list(seeds)
    (root / "status.json").write_text(
        json.dumps(status, allow_nan=False, sort_keys=True),
        encoding="utf-8",
    )
    (root / "campaign_summary.json").write_text(
        json.dumps(summary, allow_nan=False, sort_keys=True),
        encoding="utf-8",
    )
    (root / "research_history.jsonl").write_bytes(
        b"".join(_render(record) for record in artifacts.current_history)
    )
    controls_path = root / "initial_screening_study_controls.json"
    controls_path.write_bytes(_canonical_json_bytes(controls, max_bytes=1 << 20))
    controls_path.chmod(0o600)
    (root / "code_research_limits.json").write_text(
        json.dumps(controls["code_research_limits"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (root / "resource_envelope.json").write_text(
        json.dumps(controls["resource_envelope"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _rewrite_manifest(path: Path, raw: dict[str, Any]) -> None:
    path.write_bytes(_canonical_json_bytes(raw, max_bytes=16 << 20))


def _fixed_error(call: Any) -> None:
    with pytest.raises(ResearchEffectivenessInputError) as raised:
        call()
    error = raised.value
    assert error.code == _ERROR
    assert str(error) == _ERROR
    assert error.args == (_ERROR,)
    assert error.__cause__ is None
    assert error.__context__ is None


def test_validates_config_subset_decodes_exactly_ten_and_never_scores(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, _raw = _loader_manifest(tmp_path)
    original = loader_module._decode_study_root
    decoded = 0

    def counted(artifacts: Any) -> Any:
        nonlocal decoded
        decoded += 1
        return original(artifacts)

    monkeypatch.setattr(loader_module, "_decode_study_root", counted)
    result = _validate_initial_screening_study_manifest_config_subset(
        manifest_path=str(manifest_path)
    )

    assert decoded == 10
    assert result["status"] == "CONFIG_SUBSET_JOINED"
    assert result["blocks_checked"] == 5
    assert result["arms_checked"] == 10
    assert result["limitations"] == list(_JOIN_LIMITATIONS)
    assert len(result["limitations"]) == 20
    rendered = json.dumps(result, sort_keys=True).casefold()
    assert str(tmp_path).casefold() not in rendered
    assert "endpoint" not in set(result)
    assert "matched" not in set(result)


def test_does_not_reach_any_scoring_or_five_block_function(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, _raw = _loader_manifest(tmp_path)
    calls = 0

    def bomb(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        raise AssertionError("forbidden downstream call")

    for module, name in (
        (endpoints_module, "calculate_research_effectiveness"),
        (endpoints_module, "_evaluate_arm"),
        (comparison_module, "compare_five_block_research_effectiveness"),
        (study_root_module, "calculate_research_effectiveness"),
        (study_root_module, "compare_five_block_research_effectiveness"),
        (
            study_root_module,
            "_calculate_initial_screening_study_root_effectiveness",
        ),
        (
            study_root_module,
            "_compare_five_block_initial_screening_study_roots",
        ),
        (old_loader_module, "_compare_decoded_blocks"),
        (
            old_loader_module,
            "_compare_five_block_initial_screening_study_root_paths",
        ),
    ):
        monkeypatch.setattr(module, name, bomb)
    monkeypatch.setattr(comparison_module, "_evaluate_arm", bomb, raising=False)

    result = _validate_initial_screening_study_manifest_config_subset(
        manifest_path=str(manifest_path)
    )
    assert result["status"] == "CONFIG_SUBSET_JOINED"
    assert calls == 0


def test_each_block_shares_one_typed_history_object_between_arms(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, _raw = _loader_manifest(tmp_path)
    original = loader_module._decode_validation_blocks
    observed: list[Any] = []

    def inspect(blocks: Any) -> None:
        for block in blocks:
            assert block.arms[0].loaded_history is block.arms[1].loaded_history
            observed.append(block.arms[0].loaded_history)
        original(blocks)

    monkeypatch.setattr(loader_module, "_decode_validation_blocks", inspect)
    _validate_initial_screening_study_manifest_config_subset(
        manifest_path=str(manifest_path)
    )

    assert len(observed) == 5
    assert [type(item) for item in observed] == [
        LoadedHistoryAvailable,
        LoadedHistoryUnavailable,
        LoadedHistoryAvailable,
        LoadedHistoryUnavailable,
        LoadedHistoryAvailable,
    ]
    assert all(
        not item.records for item in observed if type(item) is LoadedHistoryAvailable
    )


def test_manifest_loader_is_private_redacted_and_has_no_public_surface(
    tmp_path: Path,
) -> None:
    manifest_path, _raw = _loader_manifest(tmp_path)

    assert not hasattr(
        public_api,
        "validate_initial_screening_study_manifest_config_subset",
    )
    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=manifest_path  # type: ignore[arg-type]
        )
    )


def test_success_and_failure_do_not_expose_manifest_owned_sentinels(
    tmp_path: Path,
) -> None:
    marker = "PRIVATE_CAMPAIGN_SENTINEL"
    private_parent = tmp_path / "PRIVATE_PATH_SENTINEL"
    private_parent.mkdir()
    manifest_path, raw = _loader_manifest(private_parent)
    arm = raw["blocks"][0]["arms"][0]
    root = manifest_path.parent / arm["root_path"]
    arm["campaign_id"] = marker
    for name in ("status.json", "campaign_summary.json"):
        path = root / name
        value = json.loads(path.read_text(encoding="utf-8"))
        value["campaign_id"] = marker
        path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    _rewrite_manifest(manifest_path, raw)

    result = _validate_initial_screening_study_manifest_config_subset(
        manifest_path=str(manifest_path)
    )
    assert marker not in json.dumps(result, sort_keys=True)
    (root / "status.json").write_text(marker, encoding="utf-8")
    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=str(manifest_path)
        )
    )


@pytest.mark.parametrize(
    "invalid",
    [
        "relative/manifest.json",
        "/",
        "//tmp/manifest.json",
        "/tmp/../tmp/manifest.json",
        "/tmp/manifest.json/",
        "/tmp/manifest.json\x00suffix",
        "/tmp/back\\slash.json",
    ],
)
def test_rejects_noncanonical_manifest_path(
    invalid: str,
) -> None:
    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=invalid
        )
    )


def test_rejects_noncanonical_manifest_bytes_before_root_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    manifest_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    root_reads = 0

    def unexpected(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal root_reads
        root_reads += 1
        raise AssertionError

    monkeypatch.setattr(loader_module, "_load_root_snapshots", unexpected)
    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=str(manifest_path)
        )
    )
    assert root_reads == 0


def test_loads_and_normalizes_all_history_bases_before_any_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    history = manifest_path.parent / "history" / "block-1.jsonl"
    history.parent.mkdir()
    history.write_bytes(_render(_formal_record()))
    raw["blocks"][0]["loaded_history"] = {
        "availability": "available",
        "files": ["history/block-1.jsonl"],
    }
    _rewrite_manifest(manifest_path, raw)
    history.write_bytes(
        json.dumps(_formal_record(), allow_nan=False, sort_keys=True).encode() + b"\n"
    )
    root_reads = 0

    def unexpected(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal root_reads
        root_reads += 1
        raise AssertionError

    monkeypatch.setattr(loader_module, "_load_root_snapshots", unexpected)
    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=str(manifest_path)
        )
    )
    assert root_reads == 0


def test_cross_block_history_file_is_read_once_and_reused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    history = manifest_path.parent / "history" / "common.jsonl"
    history.parent.mkdir()
    history.write_bytes(_render(_formal_record()))
    declaration = {
        "availability": "available",
        "files": ["history/common.jsonl"],
    }
    raw["blocks"][0]["loaded_history"] = copy.deepcopy(declaration)
    raw["blocks"][2]["loaded_history"] = copy.deepcopy(declaration)
    _rewrite_manifest(manifest_path, raw)
    original = io_module._read_relative_file
    reads = 0

    def counted(*args: Any, **kwargs: Any) -> Any:
        nonlocal reads
        reads += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(io_module, "_read_relative_file", counted)
    _validate_initial_screening_study_manifest_config_subset(
        manifest_path=str(manifest_path)
    )
    assert reads == 1


def test_available_basis_accepts_two_distinct_canonical_files(
    tmp_path: Path,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    directory = manifest_path.parent / "history"
    directory.mkdir()
    (directory / "first.jsonl").write_bytes(_render(_formal_record()))
    (directory / "second.jsonl").write_bytes(_render(_formal_record()))
    raw["blocks"][0]["loaded_history"] = {
        "availability": "available",
        "files": ["history/first.jsonl", "history/second.jsonl"],
    }
    _rewrite_manifest(manifest_path, raw)

    result = _validate_initial_screening_study_manifest_config_subset(
        manifest_path=str(manifest_path)
    )
    assert result["status"] == "CONFIG_SUBSET_JOINED"


def test_history_block_record_cap_is_enforced_before_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    history = manifest_path.parent / "history" / "too-many.jsonl"
    history.parent.mkdir()
    line = _render(_formal_record())
    history.write_bytes(line * 257)
    raw["blocks"][0]["loaded_history"] = {
        "availability": "available",
        "files": ["history/too-many.jsonl"],
    }
    _rewrite_manifest(manifest_path, raw)
    roots = 0

    def unexpected(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal roots
        roots += 1
        raise AssertionError

    monkeypatch.setattr(loader_module, "_load_root_snapshots", unexpected)
    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=str(manifest_path)
        )
    )
    assert roots == 0


def test_manifest_byte_cap_accepts_boundary_and_rejects_plus_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, _raw = _loader_manifest(tmp_path)
    size = manifest_path.stat().st_size
    monkeypatch.setattr(io_module, "_MANIFEST_MAX_BYTES", size)
    _validate_initial_screening_study_manifest_config_subset(
        manifest_path=str(manifest_path)
    )
    monkeypatch.setattr(io_module, "_MANIFEST_MAX_BYTES", size - 1)
    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=str(manifest_path)
        )
    )


def test_history_file_and_line_caps_cover_boundary_and_plus_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    history = manifest_path.parent / "history" / "bounded.jsonl"
    history.parent.mkdir()
    long_line = _render(_formal_record(hypothesis_text="x" * 4096))
    history.write_bytes(long_line + _render(_formal_record()))
    raw["blocks"][0]["loaded_history"] = {
        "availability": "available",
        "files": ["history/bounded.jsonl"],
    }
    _rewrite_manifest(manifest_path, raw)
    file_size = history.stat().st_size
    monkeypatch.setattr(io_module, "MAX_RESEARCH_HISTORY_FILE_BYTES", file_size)
    monkeypatch.setattr(io_module, "MAX_RESEARCH_HISTORY_LINE_BYTES", len(long_line))
    _validate_initial_screening_study_manifest_config_subset(
        manifest_path=str(manifest_path)
    )
    monkeypatch.setattr(io_module, "MAX_RESEARCH_HISTORY_FILE_BYTES", file_size - 1)
    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=str(manifest_path)
        )
    )
    monkeypatch.setattr(io_module, "MAX_RESEARCH_HISTORY_FILE_BYTES", file_size)
    monkeypatch.setattr(
        io_module, "MAX_RESEARCH_HISTORY_LINE_BYTES", len(long_line) - 1
    )
    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=str(manifest_path)
        )
    )


def test_history_unique_total_cap_accepts_boundary_and_rejects_plus_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    directory = manifest_path.parent / "history"
    directory.mkdir()
    files = [directory / "first.jsonl", directory / "second.jsonl"]
    for path in files:
        path.write_bytes(_render(_formal_record()))
    raw["blocks"][0]["loaded_history"] = {
        "availability": "available",
        "files": ["history/first.jsonl", "history/second.jsonl"],
    }
    _rewrite_manifest(manifest_path, raw)
    total = sum(path.stat().st_size for path in files)
    monkeypatch.setattr(io_module, "MAX_RESEARCH_HISTORY_TOTAL_BYTES", total)
    _validate_initial_screening_study_manifest_config_subset(
        manifest_path=str(manifest_path)
    )
    monkeypatch.setattr(io_module, "MAX_RESEARCH_HISTORY_TOTAL_BYTES", total - 1)
    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=str(manifest_path)
        )
    )


def test_root_and_current_history_aggregate_caps_cover_boundaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    leaf_names = (
        "status.json",
        "campaign_summary.json",
        "research_history.jsonl",
        "initial_screening_study_controls.json",
        "code_research_limits.json",
        "resource_envelope.json",
    )
    roots = [
        manifest_path.parent / arm["root_path"]
        for block in raw["blocks"]
        for arm in block["arms"]
    ]
    total = sum((root / name).stat().st_size for root in roots for name in leaf_names)
    history_total = sum(
        (root / "research_history.jsonl").stat().st_size for root in roots
    )
    monkeypatch.setattr(io_module, "_ROOT_TOTAL_MAX_BYTES", total)
    monkeypatch.setattr(io_module, "_CURRENT_HISTORY_TOTAL_MAX_BYTES", history_total)
    _validate_initial_screening_study_manifest_config_subset(
        manifest_path=str(manifest_path)
    )
    monkeypatch.setattr(io_module, "_ROOT_TOTAL_MAX_BYTES", total - 1)
    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=str(manifest_path)
        )
    )
    monkeypatch.setattr(io_module, "_ROOT_TOTAL_MAX_BYTES", total)
    monkeypatch.setattr(
        io_module,
        "_CURRENT_HISTORY_TOTAL_MAX_BYTES",
        history_total - 1,
    )
    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=str(manifest_path)
        )
    )


def test_json_depth_accepts_24_and_rejects_25() -> None:
    value: Any = 0
    for _ in range(24):
        value = [value]
    assert io_module._parse_json(json.dumps(value).encode()) is not None
    with pytest.raises(ValueError):
        io_module._parse_json(json.dumps([value]).encode())


def test_history_file_count_accepts_16_and_rejects_17(tmp_path: Path) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    directory = manifest_path.parent / "history"
    directory.mkdir()
    tokens: list[str] = []
    for ordinal in range(17):
        token = f"history/file-{ordinal}.jsonl"
        (manifest_path.parent / token).write_bytes(_render(_formal_record()))
        tokens.append(token)
    raw["blocks"][0]["loaded_history"] = {
        "availability": "available",
        "files": tokens[:16],
    }
    _rewrite_manifest(manifest_path, raw)
    _validate_initial_screening_study_manifest_config_subset(
        manifest_path=str(manifest_path)
    )
    raw["blocks"][0]["loaded_history"]["files"] = tokens
    _rewrite_manifest(manifest_path, raw)
    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=str(manifest_path)
        )
    )


def test_distinct_history_tokens_cannot_alias_one_inode(
    tmp_path: Path,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    directory = manifest_path.parent / "history"
    directory.mkdir()
    first = directory / "first.jsonl"
    second = directory / "second.jsonl"
    first.write_bytes(_render(_formal_record()))
    os.link(first, second)
    raw["blocks"][0]["loaded_history"] = {
        "availability": "available",
        "files": ["history/first.jsonl", "history/second.jsonl"],
    }
    _rewrite_manifest(manifest_path, raw)
    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=str(manifest_path)
        )
    )


def test_rejects_root_controls_mode_and_campaign_drift(
    tmp_path: Path,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    root = manifest_path.parent / raw["blocks"][0]["arms"][0]["root_path"]
    controls = root / "initial_screening_study_controls.json"
    controls.chmod(0o644)
    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=str(manifest_path)
        )
    )
    controls.chmod(0o600)
    status_path = root / "status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["campaign_id"] = "drift"
    status_path.write_text(json.dumps(status, sort_keys=True), encoding="utf-8")
    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=str(manifest_path)
        )
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "scheduler",
        "readiness_type",
        "readiness_signed_zero",
        "pair_champion_version",
    ],
)
def test_rejects_visible_root_control_and_pair_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    decodes = 0

    def unexpected_decode(_artifacts: Any) -> None:
        nonlocal decodes
        decodes += 1

    monkeypatch.setattr(loader_module, "_decode_study_root", unexpected_decode)
    first = manifest_path.parent / raw["blocks"][0]["arms"][0]["root_path"]
    path = first / "status.json"
    status = json.loads(path.read_text(encoding="utf-8"))
    if mutation == "scheduler":
        status["active_slots"]["max"] += 1
    elif mutation == "readiness_type":
        status["measurement_readiness"]["n_pairs"] = 0.0
    elif mutation == "readiness_signed_zero":
        status["measurement_readiness"]["mde_at_power_80"] = -0.0
    else:
        status["champion_version"] += 1
    path.write_text(json.dumps(status, sort_keys=True), encoding="utf-8")
    if mutation == "readiness_signed_zero":
        summary_path = first / "campaign_summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["measurement_readiness"]["mde_at_power_80"] = -0.0
        summary_path.write_text(json.dumps(summary, sort_keys=True), encoding="utf-8")

    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=str(manifest_path)
        )
    )
    assert decodes == 0


@pytest.mark.parametrize(
    "leaf_name",
    [
        "status.json",
        "campaign_summary.json",
        "research_history.jsonl",
        "initial_screening_study_controls.json",
        "code_research_limits.json",
        "resource_envelope.json",
    ],
)
def test_each_root_leaf_rejects_cross_root_inode_alias(
    tmp_path: Path,
    leaf_name: str,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    first = manifest_path.parent / raw["blocks"][0]["arms"][0]["root_path"]
    second = manifest_path.parent / raw["blocks"][0]["arms"][1]["root_path"]
    target = first / leaf_name
    target.unlink()
    os.link(second / leaf_name, target)

    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=str(manifest_path)
        )
    )


@pytest.mark.parametrize(
    ("leaf_name", "mutation"),
    [
        ("code_research_limits.json", "minify"),
        ("resource_envelope.json", "minify"),
        ("code_research_limits.json", "loose_type"),
        ("resource_envelope.json", "independent_drift"),
    ],
)
def test_independent_control_files_require_exact_typed_producer_bytes(
    tmp_path: Path,
    leaf_name: str,
    mutation: str,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    root = manifest_path.parent / raw["blocks"][0]["arms"][0]["root_path"]
    path = root / leaf_name
    value = json.loads(path.read_text(encoding="utf-8"))
    if mutation == "minify":
        path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    elif mutation == "loose_type":
        value["max_turns"] = float(value["max_turns"])
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    else:
        value["provider_call_cap"] += 1
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=str(manifest_path)
        )
    )


def test_loads_all_ten_roots_before_a_last_root_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    last = manifest_path.parent / raw["blocks"][-1]["arms"][-1]["root_path"]
    (last / "initial_screening_study_controls.json").chmod(0o644)
    original = io_module._load_one_root
    loads = 0

    def counted(*args: Any, **kwargs: Any) -> Any:
        nonlocal loads
        loads += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(io_module, "_load_one_root", counted)
    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=str(manifest_path)
        )
    )
    assert loads == 10


def test_reverify_precedes_all_decodes_and_tenth_decode_failure_is_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, _raw = _loader_manifest(tmp_path)
    events: list[str] = []
    original_verify = loader_module._verify_study_bundle

    def verified(bundle: Any, histories: Any, roots: Any) -> None:
        original_verify(bundle, histories, roots)
        events.append("verified")

    def decode(_artifacts: Any) -> Any:
        events.append("decode")
        if events.count("decode") == 10:
            raise ValueError("PRIVATE_TENTH_ARM_SENTINEL")
        return object()

    monkeypatch.setattr(loader_module, "_verify_study_bundle", verified)
    monkeypatch.setattr(loader_module, "_decode_study_root", decode)
    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=str(manifest_path)
        )
    )
    assert events == ["verified", *("decode" for _ in range(10))]


def test_rejects_symlinked_leaf_and_root_nesting_with_history(
    tmp_path: Path,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    root_token = raw["blocks"][0]["arms"][0]["root_path"]
    root = manifest_path.parent / root_token
    status = root / "status.json"
    original = root / "status-original.json"
    status.rename(original)
    status.symlink_to(original.name)
    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=str(manifest_path)
        )
    )
    status.unlink()
    original.rename(status)
    raw["blocks"][0]["loaded_history"] = {
        "availability": "available",
        "files": [f"{root_token}/research_history.jsonl"],
    }
    _rewrite_manifest(manifest_path, raw)
    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=str(manifest_path)
        )
    )


def test_rejects_symlinked_intermediate_root_component(tmp_path: Path) -> None:
    manifest_path, _raw = _loader_manifest(tmp_path)
    outcomes = manifest_path.parent / "outcomes"
    actual = manifest_path.parent / "outcomes-actual"
    outcomes.rename(actual)
    outcomes.symlink_to(actual.name, target_is_directory=True)

    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=str(manifest_path)
        )
    )


@pytest.mark.parametrize(
    "leaf_name",
    [
        "status.json",
        "campaign_summary.json",
        "research_history.jsonl",
        "initial_screening_study_controls.json",
        "code_research_limits.json",
        "resource_envelope.json",
    ],
)
def test_final_revalidation_catches_each_leaf_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    leaf_name: str,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    root = manifest_path.parent / raw["blocks"][0]["arms"][0]["root_path"]
    original = loader_module._build_validation_blocks

    def mutate(*args: Any, **kwargs: Any) -> Any:
        blocks = original(*args, **kwargs)
        path = root / leaf_name
        path.write_bytes(path.read_bytes() + b" ")
        return blocks

    monkeypatch.setattr(loader_module, "_build_validation_blocks", mutate)
    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=str(manifest_path)
        )
    )


@pytest.mark.parametrize("surface", ["manifest", "basis", "root"])
def test_final_revalidation_catches_bundle_path_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    surface: str,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    basis = manifest_path.parent / "history" / "basis.jsonl"
    basis.parent.mkdir()
    basis.write_bytes(_render(_formal_record()))
    raw["blocks"][0]["loaded_history"] = {
        "availability": "available",
        "files": ["history/basis.jsonl"],
    }
    _rewrite_manifest(manifest_path, raw)
    root = manifest_path.parent / raw["blocks"][0]["arms"][0]["root_path"]
    original = loader_module._build_validation_blocks

    def mutate(*args: Any, **kwargs: Any) -> Any:
        blocks = original(*args, **kwargs)
        if surface == "manifest":
            manifest_path.write_bytes(manifest_path.read_bytes() + b" ")
        elif surface == "basis":
            basis.write_bytes(basis.read_bytes() + b" ")
        else:
            saved = root.with_name(f"{root.name}-saved")
            root.rename(saved)
            shutil.copytree(saved, root)
        return blocks

    monkeypatch.setattr(loader_module, "_build_validation_blocks", mutate)
    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=str(manifest_path)
        )
    )


def test_second_absolute_rewalk_rejects_detached_old_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, _raw = _loader_manifest(tmp_path)
    bundle = manifest_path.parent
    original = io_module._verify_root_snapshot
    verified = 0

    def detach(final_bundle: Any, snapshot: Any) -> None:
        nonlocal verified
        original(final_bundle, snapshot)
        verified += 1
        if verified == 10:
            old_bundle = bundle.with_name("bundle-detached-old")
            bundle.rename(old_bundle)
            shutil.copytree(old_bundle, bundle)

    monkeypatch.setattr(io_module, "_verify_root_snapshot", detach)
    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=str(manifest_path)
        )
    )
    assert verified == 10


def test_final_revalidation_rejects_absent_history_becoming_present(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    root = manifest_path.parent / raw["blocks"][0]["arms"][0]["root_path"]
    history = root / "research_history.jsonl"
    history.unlink()
    summary_path = root / "campaign_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["steps"] = []
    summary_path.write_text(json.dumps(summary, sort_keys=True), encoding="utf-8")
    original = loader_module._build_validation_blocks

    def mutate(*args: Any, **kwargs: Any) -> Any:
        blocks = original(*args, **kwargs)
        history.write_bytes(_render(_formal_record()))
        return blocks

    monkeypatch.setattr(loader_module, "_build_validation_blocks", mutate)
    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=str(manifest_path)
        )
    )


def test_final_revalidation_uses_a_fresh_absolute_parent_anchor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, _raw = _loader_manifest(tmp_path)
    original_verify = loader_module._verify_study_bundle
    original_root = io_module._verify_root_snapshot
    initial_fds: list[int] = []
    final_fds: list[int] = []

    def counted(bundle: Any, histories: Any, roots: Any) -> None:
        initial_fds.append(bundle.parent_fd)
        original_verify(bundle, histories, roots)

    def count_root(bundle: Any, snapshot: Any) -> None:
        final_fds.append(bundle.parent_fd)
        original_root(bundle, snapshot)

    monkeypatch.setattr(loader_module, "_verify_study_bundle", counted)
    monkeypatch.setattr(io_module, "_verify_root_snapshot", count_root)

    _validate_initial_screening_study_manifest_config_subset(
        manifest_path=str(manifest_path)
    )
    assert len(initial_fds) == 1
    assert len(final_fds) == 10
    assert len(set(final_fds)) == 1
    assert final_fds[0] != initial_fds[0]


def test_production_modules_exclude_scoring_and_matched_result_symbols() -> None:
    directory = Path(loader_module.__file__).parent
    source = "\n".join(
        (directory / name).read_text(encoding="utf-8")
        for name in (
            "study_manifest_controls_schema.py",
            "study_manifest_schema.py",
            "study_manifest_io_primitives.py",
            "study_manifest_io.py",
            "study_manifest_loader.py",
        )
    )
    forbidden = (
        "calculate_research_effectiveness",
        "_evaluate_arm",
        "_calculate_initial_screening_study_root_effectiveness",
        "compare_five_block_research_effectiveness",
        "_compare_five_block_initial_screening_study_roots",
        "_compare_decoded_blocks",
        "MatchedResearchEffectivenessBlock",
        "_ArmEvaluation",
    )
    assert not any(token in source for token in forbidden)
