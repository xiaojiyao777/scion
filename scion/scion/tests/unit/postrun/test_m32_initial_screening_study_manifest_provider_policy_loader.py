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
import scion.postrun.research_effectiveness.study_manifest_provider_policy_io as io_module
import scion.postrun.research_effectiveness.study_manifest_provider_policy_loader as loader_module
import scion.postrun.research_effectiveness.study_root as study_root_module
import scion.postrun.research_effectiveness.study_root_loader as old_loader_module
from scion.postrun.research_effectiveness.models import ResearchEffectivenessInputError
from scion.postrun.research_effectiveness.study_manifest_controls_schema import (
    _canonical_json_bytes,
)
from scion.postrun.research_effectiveness.study_manifest_loader import (
    _validate_initial_screening_study_manifest_config_subset,
)
from scion.postrun.research_effectiveness.study_manifest_provider_policy_loader import (
    _validate_initial_screening_study_manifest_config_subset_and_requested_provider_policy as _validate_initial_screening_study_manifest_config_and_requested_provider_policy,
)
from scion.postrun.research_effectiveness.study_manifest_provider_policy_schema import (
    _JOIN_LIMITATIONS,
)
from scion.tests.unit.postrun.test_m32_initial_screening_study_manifest_loader import (
    _loader_manifest as _v1_loader_manifest,
)
from scion.tests.unit.postrun.test_m32_initial_screening_study_manifest_loader import (
    _rewrite_manifest,
)
from scion.tests.unit.postrun.test_m32_initial_screening_study_manifest_provider_policy_schema import (
    _provider_policy,
    _set_policy_family,
)

_ERROR = "STUDY_CONFIG_SUBSET_AND_REQUESTED_PROVIDER_POLICY_JOIN_INVALID"
_MANIFEST_VERSION = (
    "scion.initial_screening_study_manifest."
    "config_subset_and_requested_provider_policy.v2"
)
_SCOPE = "CONFIG_SUBSET_AND_REQUESTED_PROVIDER_POLICY_ONLY"
_PROVIDER_NAME = "initial_screening_provider_policy.json"


def _loader_manifest(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    manifest_path, raw = _v1_loader_manifest(tmp_path)
    provider_policy = _provider_policy()
    provider_bytes = _canonical_json_bytes(provider_policy, max_bytes=65_536)
    raw["schema_version"] = _MANIFEST_VERSION
    raw["scope"] = _SCOPE
    raw["declared_provider_policy"] = provider_policy
    for block in raw["blocks"]:
        for arm in block["arms"]:
            path = manifest_path.parent / arm["root_path"] / _PROVIDER_NAME
            path.write_bytes(provider_bytes)
            path.chmod(0o600)
    _rewrite_manifest(manifest_path, raw)
    return manifest_path, raw


def _roots(manifest_path: Path, raw: dict[str, Any]) -> list[Path]:
    return [
        manifest_path.parent / arm["root_path"]
        for block in raw["blocks"]
        for arm in block["arms"]
    ]


def _fixed_error(call: Any) -> None:
    with pytest.raises(ResearchEffectivenessInputError) as raised:
        call()
    error = raised.value
    assert error.code == _ERROR
    assert str(error) == _ERROR
    assert error.args == (_ERROR,)
    assert error.__cause__ is None
    assert error.__context__ is None


def test_validates_v2_decodes_exactly_ten_after_fresh_rewalk_and_never_scores(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, _raw = _loader_manifest(tmp_path)
    original_decode = loader_module._decode_study_root
    original_verify = loader_module._verify_provider_policy_study_bundle
    verified = False
    decoded = 0
    forbidden = 0

    def verify(*args: Any, **kwargs: Any) -> Any:
        nonlocal verified
        result = original_verify(*args, **kwargs)
        verified = True
        return result

    def decode(artifacts: Any) -> Any:
        nonlocal decoded
        assert verified
        decoded += 1
        return original_decode(artifacts)

    def bomb(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal forbidden
        forbidden += 1
        raise AssertionError

    monkeypatch.setattr(loader_module, "_verify_provider_policy_study_bundle", verify)
    monkeypatch.setattr(loader_module, "_decode_study_root", decode)
    for module, name in (
        (endpoints_module, "calculate_research_effectiveness"),
        (endpoints_module, "_evaluate_arm"),
        (comparison_module, "compare_five_block_research_effectiveness"),
        (study_root_module, "calculate_research_effectiveness"),
        (study_root_module, "compare_five_block_research_effectiveness"),
        (study_root_module, "_calculate_initial_screening_study_root_effectiveness"),
        (study_root_module, "_compare_five_block_initial_screening_study_roots"),
        (old_loader_module, "_compare_decoded_blocks"),
        (old_loader_module, "_compare_five_block_initial_screening_study_root_paths"),
    ):
        monkeypatch.setattr(module, name, bomb)

    result = (
        _validate_initial_screening_study_manifest_config_and_requested_provider_policy(
            manifest_path=str(manifest_path)
        )
    )
    assert decoded == 10
    assert forbidden == 0
    assert result == {
        "schema_version": (
            "scion.initial_screening_study_manifest_join."
            "config_subset_and_requested_provider_policy.v2"
        ),
        "status": "CONFIG_SUBSET_AND_REQUESTED_PROVIDER_POLICY_JOINED",
        "validated_scope": _SCOPE,
        "blocks_checked": 5,
        "arms_checked": 10,
        "limitations": list(_JOIN_LIMITATIONS),
    }
    assert len(result["limitations"]) == 25


def test_loads_all_histories_before_roots_and_all_seven_leaves_share_root_fd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, _raw = _loader_manifest(tmp_path)
    original_histories = loader_module._load_history_bases
    original_root = io_module._load_one_provider_policy_root
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
        token = fd_tokens[fd]
        reads.setdefault(token, []).append((fd, name))
        return original_required(fd, name, **kwargs)

    def read_optional(fd: int, name: str, **kwargs: Any) -> Any:
        token = fd_tokens[fd]
        reads.setdefault(token, []).append((fd, name))
        return original_optional(fd, name, **kwargs)

    monkeypatch.setattr(loader_module, "_load_history_bases", load_histories)
    monkeypatch.setattr(io_module, "_load_one_provider_policy_root", load_root)
    monkeypatch.setattr(io_module, "_open_relative_directory", open_root)
    monkeypatch.setattr(io_module, "_read_required_leaf", read_required)
    monkeypatch.setattr(io_module, "_read_optional_leaf", read_optional)
    _validate_initial_screening_study_manifest_config_and_requested_provider_policy(
        manifest_path=str(manifest_path)
    )

    assert len(reads) == 10
    expected_names = {
        "status.json",
        "campaign_summary.json",
        "research_history.jsonl",
        "initial_screening_study_controls.json",
        "code_research_limits.json",
        "resource_envelope.json",
        _PROVIDER_NAME,
    }
    for events in reads.values():
        assert len({fd for fd, _name in events}) == 1
        assert {name for _fd, name in events} == expected_names


@pytest.mark.parametrize(
    "mutation",
    ["missing", "mode", "noncanonical", "declared_drift", "leaf_drift"],
)
def test_rejects_provider_leaf_or_declaration_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    leaf = _roots(manifest_path, raw)[0] / _PROVIDER_NAME
    if mutation == "missing":
        leaf.unlink()
    elif mutation == "mode":
        leaf.chmod(0o644)
    elif mutation == "noncanonical":
        leaf.write_text(
            json.dumps(raw["declared_provider_policy"], indent=2),
            encoding="utf-8",
        )
    elif mutation == "declared_drift":
        raw["declared_provider_policy"]["request_policies"][0]["timeout_sec"] += 1.0
        _rewrite_manifest(manifest_path, raw)
    else:
        policy = copy.deepcopy(raw["declared_provider_policy"])
        policy["request_policies"][0]["timeout_sec"] += 1.0
        leaf.write_bytes(_canonical_json_bytes(policy, max_bytes=65_536))
    _fixed_error(
        lambda: (
            _validate_initial_screening_study_manifest_config_and_requested_provider_policy(
                manifest_path=str(manifest_path)
            )
        )
    )


@pytest.mark.parametrize("mutation", ["symlink", "fifo", "directory", "hardlink"])
def test_provider_leaf_requires_private_regular_nofollow_single_link(
    tmp_path: Path,
    mutation: str,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    root = _roots(manifest_path, raw)[0]
    leaf = root / _PROVIDER_NAME
    saved = root / "provider-policy-saved.json"
    if mutation == "symlink":
        leaf.rename(saved)
        leaf.symlink_to(saved.name)
    elif mutation == "fifo":
        leaf.unlink()
        os.mkfifo(leaf, 0o600)
    elif mutation == "directory":
        leaf.unlink()
        leaf.mkdir(mode=0o700)
    else:
        leaf.unlink()
        os.link(root / "status.json", leaf)
    _fixed_error(
        lambda: (
            _validate_initial_screening_study_manifest_config_and_requested_provider_policy(
                manifest_path=str(manifest_path)
            )
        )
    )


def test_provider_leaf_cap_accepts_exact_size_and_rejects_plus_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    size = (_roots(manifest_path, raw)[0] / _PROVIDER_NAME).stat().st_size
    monkeypatch.setattr(io_module, "_PROVIDER_POLICY_MAX_BYTES", size)
    _validate_initial_screening_study_manifest_config_and_requested_provider_policy(
        manifest_path=str(manifest_path)
    )
    monkeypatch.setattr(io_module, "_PROVIDER_POLICY_MAX_BYTES", size - 1)
    _fixed_error(
        lambda: (
            _validate_initial_screening_study_manifest_config_and_requested_provider_policy(
                manifest_path=str(manifest_path)
            )
        )
    )


@pytest.mark.parametrize("surface", ["client", "body", 0, 1, 2, 3, 4])
def test_each_root_policy_surface_must_equal_the_single_common_declaration(
    tmp_path: Path,
    surface: str | int,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    leaf = _roots(manifest_path, raw)[-1] / _PROVIDER_NAME
    policy = json.loads(leaf.read_text(encoding="utf-8"))
    if surface == "client":
        _set_policy_family(
            policy,
            model="minimax-text-01",
            configured_url="https://provider.example",
            effective_url="https://provider.example/v1",
            provider="openai_compatible",
            requested_reasoning="",
            effective_reasoning="",
            thinking_mode="disabled",
            system_blocks="merged_into_user_prompt",
            tool_choice="required_named_function",
        )
    elif surface == "body":
        _set_policy_family(
            policy,
            model="deepseek-v4-pro",
            configured_url="https://api.deepseek.com/v1",
            effective_url="https://api.deepseek.com",
            provider="openai_compatible",
            requested_reasoning="",
            effective_reasoning="",
            thinking_mode="disabled",
            system_blocks="merged_into_user_prompt",
            tool_choice="omitted",
        )
    else:
        policy["request_policies"][surface]["timeout_sec"] += 1.0
    leaf.write_bytes(_canonical_json_bytes(policy, max_bytes=65_536))
    _fixed_error(
        lambda: (
            _validate_initial_screening_study_manifest_config_and_requested_provider_policy(
                manifest_path=str(manifest_path)
            )
        )
    )


def test_invalid_first_provider_does_not_skip_loading_or_auditing_later_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    roots = _roots(manifest_path, raw)
    first = json.loads((roots[0] / _PROVIDER_NAME).read_text(encoding="utf-8"))
    first["request_policies"][0]["timeout_sec"] = 0.0
    (roots[0] / _PROVIDER_NAME).write_bytes(
        _canonical_json_bytes(first, max_bytes=65_536)
    )
    original_load = io_module._load_one_provider_policy_root
    original_normalize = loader_module._normalize_declared_provider_policy
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

    monkeypatch.setattr(io_module, "_load_one_provider_policy_root", load)
    monkeypatch.setattr(loader_module, "_normalize_declared_provider_policy", normalize)
    _fixed_error(
        lambda: (
            _validate_initial_screening_study_manifest_config_and_requested_provider_policy(
                manifest_path=str(manifest_path)
            )
        )
    )
    assert loaded == 10
    assert normalized == 10


def test_provider_leaf_cannot_alias_across_roots(tmp_path: Path) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    roots = _roots(manifest_path, raw)
    target = roots[0] / _PROVIDER_NAME
    target.unlink()
    os.link(roots[1] / _PROVIDER_NAME, target)
    _fixed_error(
        lambda: (
            _validate_initial_screening_study_manifest_config_and_requested_provider_policy(
                manifest_path=str(manifest_path)
            )
        )
    )


@pytest.mark.parametrize(
    "mutation",
    ["provider_after_join", "manifest_after_normalize", "manifest_second_pass"],
)
def test_fresh_rewalk_rejects_provider_or_manifest_toctou(
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
    if mutation == "provider_after_join":
        original = loader_module._verify_provider_policy_study_bundle

        def mutate_then_verify(*args: Any, **kwargs: Any) -> Any:
            leaf = _roots(manifest_path, raw)[-1] / _PROVIDER_NAME
            leaf.write_bytes(leaf.read_bytes() + b" ")
            return original(*args, **kwargs)

        monkeypatch.setattr(
            loader_module,
            "_verify_provider_policy_study_bundle",
            mutate_then_verify,
        )
    elif mutation == "manifest_after_normalize":
        original_normalize = loader_module._normalize_study_manifest_provider_policy

        def normalize_then_mutate(value: Any) -> Any:
            result = original_normalize(value)
            manifest_path.write_bytes(manifest_path.read_bytes() + b" ")
            return result

        monkeypatch.setattr(
            loader_module,
            "_normalize_study_manifest_provider_policy",
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
    _fixed_error(
        lambda: (
            _validate_initial_screening_study_manifest_config_and_requested_provider_policy(
                manifest_path=str(manifest_path)
            )
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
        _PROVIDER_NAME,
    ],
)
def test_integrated_fresh_rewalk_covers_each_of_the_seven_leaves(
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
    _fixed_error(
        lambda: (
            _validate_initial_screening_study_manifest_config_and_requested_provider_policy(
                manifest_path=str(manifest_path)
            )
        )
    )


def test_second_absolute_rewalk_rejects_detached_replacement_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, _raw = _loader_manifest(tmp_path)
    bundle = manifest_path.parent
    original = io_module._verify_provider_policy_root_snapshot
    verified = 0

    def detach(final_bundle: Any, snapshot: Any) -> None:
        nonlocal verified
        original(final_bundle, snapshot)
        verified += 1
        if verified == 10:
            detached = bundle.with_name("bundle-detached-old")
            bundle.rename(detached)
            shutil.copytree(detached, bundle)

    monkeypatch.setattr(io_module, "_verify_provider_policy_root_snapshot", detach)
    _fixed_error(
        lambda: (
            _validate_initial_screening_study_manifest_config_and_requested_provider_policy(
                manifest_path=str(manifest_path)
            )
        )
    )
    assert verified == 10


def test_provider_leaf_is_in_existing_ten_root_aggregate(
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
        _PROVIDER_NAME,
    )
    total = sum(
        (root / name).stat().st_size
        for root in _roots(manifest_path, raw)
        for name in leaf_names
    )
    monkeypatch.setattr(io_module, "_ROOT_TOTAL_MAX_BYTES", total)
    _validate_initial_screening_study_manifest_config_and_requested_provider_policy(
        manifest_path=str(manifest_path)
    )
    monkeypatch.setattr(io_module, "_ROOT_TOTAL_MAX_BYTES", total - 1)
    _fixed_error(
        lambda: (
            _validate_initial_screening_study_manifest_config_and_requested_provider_policy(
                manifest_path=str(manifest_path)
            )
        )
    )


def test_extra_unrelated_private_root_entry_does_not_widen_the_join(
    tmp_path: Path,
) -> None:
    manifest_path, raw = _loader_manifest(tmp_path)
    extra = _roots(manifest_path, raw)[0] / "unrelated-private-artifact.bin"
    extra.write_bytes(b"not part of the seven-leaf authority")
    result = (
        _validate_initial_screening_study_manifest_config_and_requested_provider_policy(
            manifest_path=str(manifest_path)
        )
    )
    assert result["status"] == "CONFIG_SUBSET_AND_REQUESTED_PROVIDER_POLICY_JOINED"


def test_validation_only_discards_all_ten_decoder_returns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, _raw = _loader_manifest(tmp_path)
    decoded = 0

    def incomplete(_artifacts: Any) -> None:
        nonlocal decoded
        decoded += 1

    monkeypatch.setattr(loader_module, "_decode_study_root", incomplete)
    result = (
        _validate_initial_screening_study_manifest_config_and_requested_provider_policy(
            manifest_path=str(manifest_path)
        )
    )
    assert decoded == 10
    assert result["status"] == "CONFIG_SUBSET_AND_REQUESTED_PROVIDER_POLICY_JOINED"


def test_validation_never_dispatches_provider_runner_trace_or_database(
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
    result = (
        _validate_initial_screening_study_manifest_config_and_requested_provider_policy(
            manifest_path=str(manifest_path)
        )
    )
    assert result["status"] == "CONFIG_SUBSET_AND_REQUESTED_PROVIDER_POLICY_JOINED"
    assert calls == 0


def test_v1_api_and_result_remain_unchanged(tmp_path: Path) -> None:
    manifest_path, _raw = _v1_loader_manifest(tmp_path)
    result = _validate_initial_screening_study_manifest_config_subset(
        manifest_path=str(manifest_path)
    )
    assert result["status"] == "CONFIG_SUBSET_JOINED"
    assert len(result["limitations"]) == 20
    _fixed_error(
        lambda: (
            _validate_initial_screening_study_manifest_config_and_requested_provider_policy(
                manifest_path=str(manifest_path)
            )
        )
    )


def test_v2_loader_is_private_body_free_and_has_no_public_or_scoring_surface(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    private_parent = tmp_path / "PRIVATE_PATH_SENTINEL"
    private_parent.mkdir()
    manifest_path, raw = _loader_manifest(private_parent)
    sentinel = "PRIVATE_PROVIDER_SENTINEL"
    raw["declared_provider_policy"]["client"]["requested_model"] = sentinel
    _rewrite_manifest(manifest_path, raw)
    assert not hasattr(
        public_api,
        "validate_initial_screening_study_manifest_config_subset_and_requested_provider_policy",
    )
    _fixed_error(
        lambda: (
            _validate_initial_screening_study_manifest_config_and_requested_provider_policy(
                manifest_path=str(manifest_path)
            )
        )
    )
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
