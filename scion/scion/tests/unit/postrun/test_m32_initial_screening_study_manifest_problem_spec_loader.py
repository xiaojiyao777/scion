from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

import scion.postrun.research_effectiveness.study_manifest_problem_spec_io as io_module
import scion.postrun.research_effectiveness.study_manifest_problem_spec_loader as loader_module
from scion.postrun.research_effectiveness.models import ResearchEffectivenessInputError
from scion.postrun.research_effectiveness.study_manifest_controls_schema import (
    _canonical_json_bytes,
)
from scion.postrun.research_effectiveness.study_manifest_loader import (
    _validate_initial_screening_study_manifest_config_subset,
)
from scion.postrun.research_effectiveness.study_manifest_problem_spec_loader import (
    _validate_initial_screening_study_manifest_config_subset_and_requested_provider_policy_and_problem_spec_declaration as _validate_v3,
)
from scion.postrun.research_effectiveness.study_manifest_provider_policy_loader import (
    _validate_initial_screening_study_manifest_config_subset_and_requested_provider_policy as _validate_v2,
)
from scion.tests.unit.postrun.test_m32_initial_screening_study_manifest_loader import (
    _rewrite_manifest,
)
from scion.tests.unit.postrun.test_m32_initial_screening_study_manifest_problem_spec_schema import (
    _problem_leaf,
)
from scion.tests.unit.postrun.test_m32_initial_screening_study_manifest_provider_policy_loader import (
    _loader_manifest as _v2_loader_manifest,
)

_ERROR = (
    "STUDY_CONFIG_SUBSET_AND_REQUESTED_PROVIDER_POLICY_AND_"
    "PROBLEM_SPEC_DECLARATION_JOIN_INVALID"
)
_MANIFEST_VERSION = (
    "scion.initial_screening_study_manifest."
    "config_subset_and_requested_provider_policy_and_problem_spec_declaration.v3"
)
_SCOPE = "CONFIG_SUBSET_AND_REQUESTED_PROVIDER_POLICY_AND_PROBLEM_SPEC_DECLARATION_ONLY"
_PROBLEM_NAME = "initial_screening_problem_spec.json"
_CONTROLS_NAME = "initial_screening_study_controls.json"


def _loader_manifest(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    manifest_path, raw = _v2_loader_manifest(tmp_path)
    problem = _problem_leaf()
    spec = problem["problem_spec_v1"]
    spec["id"] = "demo"
    spec["adapter"]["import_path"] = "scion.problems.demo.adapter:DemoAdapter"
    problem_bytes = _canonical_json_bytes(problem, max_bytes=1 << 20)
    raw["schema_version"] = _MANIFEST_VERSION
    raw["scope"] = _SCOPE
    raw["declared_problem_spec"] = problem
    for block in raw["blocks"]:
        for arm in block["arms"]:
            controls = arm["declared_controls"]
            initial = controls["protocol"]["initial_screening"]
            effect = initial["effect_policy"]
            effect["pairing_validity"] = "trajectory_divergent"
            effect["runtime_model"] = "budget_exhausting"
            initial["screening_gate"]["resolved_median_delta_min"] = 2.0
            root = manifest_path.parent / arm["root_path"]
            controls_path = root / _CONTROLS_NAME
            controls_path.write_bytes(
                _canonical_json_bytes(controls, max_bytes=1 << 20)
            )
            controls_path.chmod(0o600)
            problem_path = root / _PROBLEM_NAME
            problem_path.write_bytes(problem_bytes)
            problem_path.chmod(0o600)
    _rewrite_manifest(manifest_path, raw)
    return manifest_path, raw


def _roots(manifest_path: Path, raw: dict[str, Any]) -> list[Path]:
    return [
        manifest_path.parent / arm["root_path"]
        for block in raw["blocks"]
        for arm in block["arms"]
    ]


def _fixed_error(call: Any, *, expected: str = _ERROR) -> None:
    with pytest.raises(ResearchEffectivenessInputError) as raised:
        call()
    error = raised.value
    assert str(error) == expected
    assert error.args == (expected,)
    assert error.__cause__ is None
    assert error.__context__ is None


def test_validates_v3_only_after_full_rewalk_and_exactly_ten_decodes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, _raw = _loader_manifest(tmp_path)
    original_decode = loader_module._decode_study_root
    original_verify = loader_module._verify_problem_spec_study_bundle
    events: list[str] = []

    def verify(*args: Any, **kwargs: Any) -> Any:
        events.append("verify")
        return original_verify(*args, **kwargs)

    def decode(artifacts: Any) -> Any:
        events.append("decode")
        return original_decode(artifacts)

    monkeypatch.setattr(loader_module, "_verify_problem_spec_study_bundle", verify)
    monkeypatch.setattr(loader_module, "_decode_study_root", decode)

    result = _validate_v3(manifest_path=str(manifest_path))

    assert result["status"] == (
        "CONFIG_SUBSET_AND_REQUESTED_PROVIDER_POLICY_AND_"
        "PROBLEM_SPEC_DECLARATION_JOINED"
    )
    assert len(result["limitations"]) == 24
    assert events == ["verify", *("decode" for _ in range(10))]


def test_loads_histories_before_roots_and_all_eight_leaves_share_one_root_fd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, _raw = _loader_manifest(tmp_path)
    original_histories = loader_module._load_history_bases
    original_root = io_module._load_one_problem_spec_root
    original_open = io_module._open_relative_directory
    original_required = io_module._read_required_leaf
    original_optional = io_module._read_optional_leaf
    histories_loaded = False
    fd_tokens: dict[int, str] = {}
    reads: dict[str, list[tuple[int, str]]] = {}

    def load_histories(*args: Any, **kwargs: Any) -> Any:
        nonlocal histories_loaded
        result = original_histories(*args, **kwargs)
        histories_loaded = True
        return result

    def load_root(*args: Any, **kwargs: Any) -> Any:
        assert histories_loaded
        return original_root(*args, **kwargs)

    def open_root(bundle: Any, token: str) -> Any:
        result = original_open(bundle, token)
        fd_tokens[result[0]] = token
        return result

    def read_required(fd: int, name: str, **kwargs: Any) -> Any:
        reads.setdefault(fd_tokens[fd], []).append((fd, name))
        return original_required(fd, name, **kwargs)

    def read_optional(fd: int, name: str, **kwargs: Any) -> Any:
        reads.setdefault(fd_tokens[fd], []).append((fd, name))
        return original_optional(fd, name, **kwargs)

    monkeypatch.setattr(loader_module, "_load_history_bases", load_histories)
    monkeypatch.setattr(io_module, "_load_one_problem_spec_root", load_root)
    monkeypatch.setattr(io_module, "_open_relative_directory", open_root)
    monkeypatch.setattr(io_module, "_read_required_leaf", read_required)
    monkeypatch.setattr(io_module, "_read_optional_leaf", read_optional)

    _validate_v3(manifest_path=str(manifest_path))

    expected = [
        "status.json",
        "campaign_summary.json",
        "research_history.jsonl",
        _CONTROLS_NAME,
        "code_research_limits.json",
        "resource_envelope.json",
        "initial_screening_provider_policy.json",
        _PROBLEM_NAME,
    ]
    assert len(reads) == 10
    for events in reads.values():
        assert len({fd for fd, _name in events}) == 1
        assert [name for _fd, name in events] == expected


@pytest.mark.parametrize(
    "surface", ["declaration", "first_root", "last_root", "noncanonical_root"]
)
def test_problem_leaf_and_manifest_declaration_are_exact_common(
    tmp_path: Path,
    surface: str,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    if surface == "declaration":
        raw["declared_problem_spec"]["problem_spec_v1"]["description"] = "drift"
        _rewrite_manifest(manifest_path, raw)
    else:
        root = _roots(manifest_path, raw)[0 if surface == "first_root" else -1]
        leaf = json.loads((root / _PROBLEM_NAME).read_bytes())
        if surface == "noncanonical_root":
            (root / _PROBLEM_NAME).write_text(json.dumps(leaf, indent=2))
        else:
            leaf["problem_spec_v1"]["description"] = "drift"
            (root / _PROBLEM_NAME).write_bytes(
                _canonical_json_bytes(leaf, max_bytes=1 << 20)
            )
    _fixed_error(lambda: _validate_v3(manifest_path=str(manifest_path)))


@pytest.mark.parametrize(
    "mutation",
    [
        "metrics",
        "objective_policy",
        "effect_metric",
        "protected",
        "pairing",
        "runtime",
        "median",
    ],
)
def test_problem_declaration_joins_controls_under_governance(
    tmp_path: Path,
    mutation: str,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    for block in raw["blocks"]:
        for arm in block["arms"]:
            initial = arm["declared_controls"]["protocol"]["initial_screening"]
            effect = initial["effect_policy"]
            if mutation == "metrics":
                effect["metric_specs"][0]["tie_tolerance"] = -0.0
            elif mutation == "objective_policy":
                effect["objective_policy"]["mode"] = "single"
            elif mutation == "effect_metric":
                effect["effect_metric"] = "fleet_violation"
            elif mutation == "protected":
                effect["protected_objectives"] = []
            elif mutation == "pairing":
                effect["pairing_validity"] = "trajectory_stable"
            elif mutation == "runtime":
                effect["runtime_model"] = "comparative"
            else:
                initial["screening_gate"]["resolved_median_delta_min"] = 1.5
            root = manifest_path.parent / arm["root_path"]
            (root / _CONTROLS_NAME).write_bytes(
                _canonical_json_bytes(arm["declared_controls"], max_bytes=1 << 20)
            )
    _rewrite_manifest(manifest_path, raw)
    _fixed_error(lambda: _validate_v3(manifest_path=str(manifest_path)))


def test_invalid_first_problem_still_loads_and_audits_all_ten_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    roots = _roots(manifest_path, raw)
    first = json.loads((roots[0] / _PROBLEM_NAME).read_bytes())
    first["problem_spec_v1"]["objectives"] = []
    (roots[0] / _PROBLEM_NAME).write_bytes(
        _canonical_json_bytes(first, max_bytes=1 << 20)
    )
    original_load = io_module._load_one_problem_spec_root
    original_normalize = loader_module._normalize_declared_problem_spec
    loaded = 0
    normalized = 0

    def load(*args: Any, **kwargs: Any) -> Any:
        nonlocal loaded
        loaded += 1
        return original_load(*args, **kwargs)

    def normalize(*args: Any, **kwargs: Any) -> Any:
        nonlocal normalized
        normalized += 1
        return original_normalize(*args, **kwargs)

    monkeypatch.setattr(io_module, "_load_one_problem_spec_root", load)
    monkeypatch.setattr(loader_module, "_normalize_declared_problem_spec", normalize)

    _fixed_error(lambda: _validate_v3(manifest_path=str(manifest_path)))
    assert loaded == 10
    assert normalized == 10


def test_invalid_first_provider_still_audits_all_ten_problem_leaves(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    provider_name = "initial_screening_provider_policy.json"
    first = _roots(manifest_path, raw)[0] / provider_name
    provider = json.loads(first.read_bytes())
    provider["request_policies"][0]["timeout_sec"] = 0.0
    first.write_bytes(_canonical_json_bytes(provider, max_bytes=65_536))
    original = loader_module._normalize_declared_problem_spec
    normalized = 0

    def normalize(*args: Any, **kwargs: Any) -> Any:
        nonlocal normalized
        normalized += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(loader_module, "_normalize_declared_problem_spec", normalize)

    _fixed_error(lambda: _validate_v3(manifest_path=str(manifest_path)))
    assert normalized == 10


def test_record_only_keeps_metric_and_objective_join_but_not_measurement_join(
    tmp_path: Path,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    problem = raw["declared_problem_spec"]
    problem["problem_spec_v1"]["measurement"]["effect_scale"]["metric"] = (
        "fleet_violation"
    )
    problem_bytes = _canonical_json_bytes(problem, max_bytes=1 << 20)
    for block in raw["blocks"]:
        for arm in block["arms"]:
            initial = arm["declared_controls"]["protocol"]["initial_screening"]
            effect = initial["effect_policy"]
            effect["measurement_governance"] = "record_only"
            effect["effect_metric"] = "total_distance"
            effect["protected_objectives"] = []
            effect["pairing_validity"] = "trajectory_stable"
            effect["runtime_model"] = "comparative"
            initial["screening_gate"]["resolved_median_delta_min"] = 0.0
            root = manifest_path.parent / arm["root_path"]
            (root / _CONTROLS_NAME).write_bytes(
                _canonical_json_bytes(arm["declared_controls"], max_bytes=1 << 20)
            )
            (root / _PROBLEM_NAME).write_bytes(problem_bytes)
    _rewrite_manifest(manifest_path, raw)

    result = _validate_v3(manifest_path=str(manifest_path))

    assert result["arms_checked"] == 10


@pytest.mark.parametrize("mutation", ["metric_specs", "objective_policy"])
def test_record_only_still_requires_problem_owned_objective_joins(
    tmp_path: Path,
    mutation: str,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    for block in raw["blocks"]:
        for arm in block["arms"]:
            effect = arm["declared_controls"]["protocol"]["initial_screening"][
                "effect_policy"
            ]
            effect["measurement_governance"] = "record_only"
            if mutation == "metric_specs":
                effect["metric_specs"][0]["tie_tolerance"] = -0.0
            else:
                effect["objective_policy"]["mode"] = "single"
            root = manifest_path.parent / arm["root_path"]
            (root / _CONTROLS_NAME).write_bytes(
                _canonical_json_bytes(arm["declared_controls"], max_bytes=1 << 20)
            )
    _rewrite_manifest(manifest_path, raw)

    _fixed_error(lambda: _validate_v3(manifest_path=str(manifest_path)))


def test_resolved_problem_delta_join_distinguishes_signed_zero(
    tmp_path: Path,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    problem = raw["declared_problem_spec"]
    problem["problem_spec_v1"]["measurement"]["effect_scale"][
        "practical_delta_screen"
    ] = 0.0
    problem_bytes = _canonical_json_bytes(problem, max_bytes=1 << 20)
    for block in raw["blocks"]:
        for arm in block["arms"]:
            initial = arm["declared_controls"]["protocol"]["initial_screening"]
            initial["screening_gate"]["resolved_median_delta_min"] = -0.0
            root = manifest_path.parent / arm["root_path"]
            (root / _CONTROLS_NAME).write_bytes(
                _canonical_json_bytes(arm["declared_controls"], max_bytes=1 << 20)
            )
            (root / _PROBLEM_NAME).write_bytes(problem_bytes)
    _rewrite_manifest(manifest_path, raw)

    _fixed_error(lambda: _validate_v3(manifest_path=str(manifest_path)))


def test_parameter_search_enabled_is_not_mapped_to_hypothesis_k(
    tmp_path: Path,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    problem = raw["declared_problem_spec"]
    problem["problem_spec_v1"]["parameter_search"]["enabled"] = True
    problem_bytes = _canonical_json_bytes(problem, max_bytes=1 << 20)
    for root in _roots(manifest_path, raw):
        (root / _PROBLEM_NAME).write_bytes(problem_bytes)
    _rewrite_manifest(manifest_path, raw)

    result = _validate_v3(manifest_path=str(manifest_path))

    assert result["arms_checked"] == 10


def test_governance_join_uses_actual_problem_measurement_consumer_projection(
    tmp_path: Path,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import copy
import json
from scion.config.protocol_config import ProtocolConfig
from scion.core.initial_screening_problem_spec import _freeze_problem_spec_inputs
from scion.problem.bridge import bridge_problem_spec_v1
from scion.problem.loader import load_problem_adapter
from scion.tests.unit.core.test_initial_screening_problem_spec import _cvrp_inputs

spec, _bridge, _adapter = _cvrp_inputs()
spec.measurement.effect_scale.metric = " total_distance "
spec.objectives[0].name = " fleet_violation "
whitespace_objective = copy.deepcopy(spec.objectives[0])
whitespace_objective.name = "   "
whitespace_objective.priority = 3
spec.objectives.append(whitespace_objective)
spec.measurement.protected_objectives = (" fleet_violation ", "   ")
bridge = bridge_problem_spec_v1(spec)
adapter = load_problem_adapter(spec)
inputs = _freeze_problem_spec_inputs(
    bridge.problem_spec, adapter, bridge.operator_execute_signature
)
consumer = ProtocolConfig().with_problem_measurement(spec)
print(json.dumps({
    "leaf": json.loads(inputs.payload_bytes),
    "effect_metric": consumer.effect_metric,
    "protected_objectives": list(consumer.protected_objectives),
    "pairing_validity": consumer.pairing_validity,
    "runtime_model": consumer.runtime.runtime_model,
    "metric_specs": [item.model_dump(mode="json") for item in spec.objectives],
    "objective_policy": spec.objective_policy.model_dump(mode="json"),
}))
""",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    projection = json.loads(child.stdout)
    problem = projection["leaf"]
    problem["problem_spec_v1"]["id"] = "demo"
    problem["problem_spec_v1"]["adapter"]["import_path"] = (
        "scion.problems.demo.adapter:DemoAdapter"
    )
    assert projection["effect_metric"] == "total_distance"
    assert projection["protected_objectives"] == ["fleet_violation"]

    raw["declared_problem_spec"] = problem
    problem_bytes = _canonical_json_bytes(problem, max_bytes=1 << 20)
    for block in raw["blocks"]:
        for arm in block["arms"]:
            initial = arm["declared_controls"]["protocol"]["initial_screening"]
            effect = initial["effect_policy"]
            effect["effect_metric"] = projection["effect_metric"]
            effect["protected_objectives"] = projection["protected_objectives"]
            effect["pairing_validity"] = projection["pairing_validity"]
            effect["runtime_model"] = projection["runtime_model"]
            effect["metric_specs"] = projection["metric_specs"]
            effect["objective_policy"] = projection["objective_policy"]
            root = manifest_path.parent / arm["root_path"]
            (root / _CONTROLS_NAME).write_bytes(
                _canonical_json_bytes(arm["declared_controls"], max_bytes=1 << 20)
            )
            (root / _PROBLEM_NAME).write_bytes(problem_bytes)
    _rewrite_manifest(manifest_path, raw)

    result = _validate_v3(manifest_path=str(manifest_path))

    assert result["arms_checked"] == 10


def test_v1_and_v2_entrypoints_remain_unchanged(tmp_path: Path) -> None:
    v2_path, _raw = _v2_loader_manifest(tmp_path)
    assert _validate_v2(manifest_path=str(v2_path))["status"] == (
        "CONFIG_SUBSET_AND_REQUESTED_PROVIDER_POLICY_JOINED"
    )
    _fixed_error(lambda: _validate_v3(manifest_path=str(v2_path)))

    other = tmp_path / "v1"
    other.mkdir()
    from scion.tests.unit.postrun.test_m32_initial_screening_study_manifest_loader import (
        _loader_manifest as v1_loader_manifest,
    )

    v1_path, _raw = v1_loader_manifest(other)
    assert (
        _validate_initial_screening_study_manifest_config_subset(
            manifest_path=str(v1_path)
        )["status"]
        == "CONFIG_SUBSET_JOINED"
    )
    _fixed_error(lambda: _validate_v3(manifest_path=str(v1_path)))

    v3_dir = tmp_path / "v3"
    v3_dir.mkdir()
    v3_path, _raw = _loader_manifest(v3_dir)
    _fixed_error(
        lambda: _validate_initial_screening_study_manifest_config_subset(
            manifest_path=str(v3_path)
        ),
        expected="STUDY_CONFIG_SUBSET_JOIN_INVALID",
    )
    _fixed_error(
        lambda: _validate_v2(manifest_path=str(v3_path)),
        expected=("STUDY_CONFIG_SUBSET_AND_REQUESTED_PROVIDER_POLICY_JOIN_INVALID"),
    )


def test_validation_discards_all_ten_decoder_returns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, _raw = _loader_manifest(tmp_path)
    decoded = 0

    def incomplete(_artifacts: Any) -> None:
        nonlocal decoded
        decoded += 1

    monkeypatch.setattr(loader_module, "_decode_study_root", incomplete)

    result = _validate_v3(manifest_path=str(manifest_path))

    assert result["arms_checked"] == 10
    assert decoded == 10


@pytest.mark.parametrize(
    "mutation", ["mode", "symlink", "fifo", "directory", "hardlink"]
)
def test_problem_leaf_requires_private_regular_nofollow_single_link(
    tmp_path: Path,
    mutation: str,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    root = _roots(manifest_path, raw)[0]
    leaf = root / _PROBLEM_NAME
    saved = root / "problem-saved.json"
    if mutation == "mode":
        leaf.chmod(0o644)
    elif mutation == "symlink":
        leaf.rename(saved)
        leaf.symlink_to(saved.name)
    elif mutation == "fifo":
        leaf.unlink()
        os.mkfifo(leaf, 0o600)
    elif mutation == "directory":
        leaf.unlink()
        leaf.mkdir(mode=0o700)
    else:
        leaf.rename(saved)
        os.link(saved, leaf)
    _fixed_error(lambda: _validate_v3(manifest_path=str(manifest_path)))


def test_problem_leaf_cap_accepts_exact_size_and_rejects_plus_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    size = (_roots(manifest_path, raw)[0] / _PROBLEM_NAME).stat().st_size
    monkeypatch.setattr(io_module, "_PROBLEM_SPEC_MAX_BYTES", size)
    assert _validate_v3(manifest_path=str(manifest_path))["arms_checked"] == 10
    monkeypatch.setattr(io_module, "_PROBLEM_SPEC_MAX_BYTES", size - 1)
    _fixed_error(lambda: _validate_v3(manifest_path=str(manifest_path)))


def test_problem_leaf_cannot_alias_another_root(tmp_path: Path) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    roots = _roots(manifest_path, raw)
    target = roots[0] / _PROBLEM_NAME
    target.unlink()
    os.link(roots[1] / _PROBLEM_NAME, target)
    _fixed_error(lambda: _validate_v3(manifest_path=str(manifest_path)))


@pytest.mark.parametrize(
    "mutation",
    ["problem_after_join", "manifest_after_normalize", "manifest_second_pass"],
)
def test_fresh_rewalk_rejects_problem_or_manifest_toctou_before_decode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    decodes = 0

    def decode(_artifacts: Any) -> None:
        nonlocal decodes
        decodes += 1

    monkeypatch.setattr(loader_module, "_decode_study_root", decode)
    if mutation == "problem_after_join":
        original = loader_module._verify_problem_spec_study_bundle

        def mutate_then_verify(*args: Any, **kwargs: Any) -> Any:
            leaf = _roots(manifest_path, raw)[-1] / _PROBLEM_NAME
            leaf.write_bytes(leaf.read_bytes() + b" ")
            return original(*args, **kwargs)

        monkeypatch.setattr(
            loader_module,
            "_verify_problem_spec_study_bundle",
            mutate_then_verify,
        )
    elif mutation == "manifest_after_normalize":
        original_normalize = loader_module._normalize_study_manifest_problem_spec

        def normalize_then_mutate(value: Any) -> Any:
            result = original_normalize(value)
            manifest_path.write_bytes(manifest_path.read_bytes() + b" ")
            return result

        monkeypatch.setattr(
            loader_module,
            "_normalize_study_manifest_problem_spec",
            normalize_then_mutate,
        )
    else:
        original_manifest_rewalk = io_module._verify_final_manifest_rewalk

        def mutate_manifest(bundle: Any) -> Any:
            manifest_path.write_bytes(manifest_path.read_bytes() + b" ")
            return original_manifest_rewalk(bundle)

        monkeypatch.setattr(
            io_module,
            "_verify_final_manifest_rewalk",
            mutate_manifest,
        )

    _fixed_error(lambda: _validate_v3(manifest_path=str(manifest_path)))
    assert decodes == 0


@pytest.mark.parametrize(
    "leaf_name",
    [
        "status.json",
        "campaign_summary.json",
        "research_history.jsonl",
        _CONTROLS_NAME,
        "code_research_limits.json",
        "resource_envelope.json",
        "initial_screening_provider_policy.json",
        _PROBLEM_NAME,
    ],
)
def test_integrated_fresh_rewalk_covers_all_eight_root_leaves(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    leaf_name: str,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    root = _roots(manifest_path, raw)[0]
    original = loader_module._build_validation_blocks

    def mutate(*args: Any, **kwargs: Any) -> Any:
        blocks = original(*args, **kwargs)
        path = root / leaf_name
        path.write_bytes(path.read_bytes() + b" ")
        return blocks

    monkeypatch.setattr(loader_module, "_build_validation_blocks", mutate)
    _fixed_error(lambda: _validate_v3(manifest_path=str(manifest_path)))


def test_second_absolute_rewalk_rejects_detached_replacement_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, _raw = _loader_manifest(tmp_path)
    bundle = manifest_path.parent
    original = io_module._verify_problem_spec_root_snapshot
    verified = 0

    def detach(final_bundle: Any, snapshot: Any) -> None:
        nonlocal verified
        original(final_bundle, snapshot)
        verified += 1
        if verified == 10:
            detached = bundle.with_name("bundle-detached-old")
            bundle.rename(detached)
            shutil.copytree(detached, bundle)

    monkeypatch.setattr(io_module, "_verify_problem_spec_root_snapshot", detach)
    _fixed_error(lambda: _validate_v3(manifest_path=str(manifest_path)))
    assert verified == 10


def test_problem_leaf_is_in_existing_ten_root_aggregate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    names = (
        "status.json",
        "campaign_summary.json",
        "research_history.jsonl",
        _CONTROLS_NAME,
        "code_research_limits.json",
        "resource_envelope.json",
        "initial_screening_provider_policy.json",
        _PROBLEM_NAME,
    )
    total = sum(
        (root / name).stat().st_size
        for root in _roots(manifest_path, raw)
        for name in names
        if (root / name).exists()
    )
    monkeypatch.setattr(io_module, "_ROOT_TOTAL_MAX_BYTES", total)
    assert _validate_v3(manifest_path=str(manifest_path))["arms_checked"] == 10
    monkeypatch.setattr(io_module, "_ROOT_TOTAL_MAX_BYTES", total - 1)
    _fixed_error(lambda: _validate_v3(manifest_path=str(manifest_path)))


def test_extra_unrelated_private_root_entry_does_not_widen_the_join(
    tmp_path: Path,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    extra = _roots(manifest_path, raw)[0] / "unrelated-private-artifact.bin"
    extra.write_bytes(b"not part of the eight-leaf authority")

    result = _validate_v3(manifest_path=str(manifest_path))

    assert result["arms_checked"] == 10


def test_validation_only_never_calls_provider_solver_trace_or_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sqlite3

    from scion.core.branch_step_runner import BranchStepRunner
    from scion.proposal.engine.provider_call import ProviderCaller
    from scion.proposal.engine.trace import _TraceWriter
    from scion.proposal.llm.client import LLMClient

    manifest_path, _raw = _loader_manifest(tmp_path)
    calls = 0

    def bomb(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        raise AssertionError

    monkeypatch.setattr(ProviderCaller, "call", bomb)
    monkeypatch.setattr(LLMClient, "call_with_tool", bomb)
    monkeypatch.setattr(BranchStepRunner, "run_one_step", bomb)
    monkeypatch.setattr(_TraceWriter, "write_terminal", bomb)
    monkeypatch.setattr(sqlite3, "connect", bomb)

    result = _validate_v3(manifest_path=str(manifest_path))

    assert result["arms_checked"] == 10
    assert calls == 0


def test_v3_loader_is_private_body_free_and_has_no_scoring_surface(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    private_parent = tmp_path / "PRIVATE_PATH_SENTINEL"
    private_parent.mkdir()
    manifest_path, raw = _loader_manifest(private_parent)
    sentinel = "PRIVATE_PROBLEM_SENTINEL"
    raw["declared_problem_spec"]["problem_spec_v1"]["description"] = sentinel
    _rewrite_manifest(manifest_path, raw)

    _fixed_error(lambda: _validate_v3(manifest_path=str(manifest_path)))

    captured = capsys.readouterr()
    assert sentinel not in captured.out
    assert sentinel not in captured.err
    assert sentinel not in caplog.text
    source = Path(loader_module.__file__).read_text(encoding="utf-8")
    forbidden = (
        "compare_five_block_research_effectiveness",
        "_compare_decoded_blocks",
        "calculate_research_effectiveness",
        "_evaluate_arm",
        "write_text",
        "write_bytes",
        "requests.",
    )
    assert not any(token in source for token in forbidden)
    assert loader_module.__all__ == ()
