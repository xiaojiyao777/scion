from __future__ import annotations

import json
import os
import signal
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

import scion.postrun.research_effectiveness as public_api
import scion.postrun.research_effectiveness.safe_artifact_loader as safe_loader_module
import scion.postrun.research_effectiveness.study_root as study_root_module
import scion.postrun.research_effectiveness.study_root_loader as loader_module
from scion.cli.commands.init_run import (
    _campaign_signal_handlers,
    _CampaignOuterHardwall,
    _CampaignSignalStop,
)
from scion.core.models import ExperimentStage
from scion.core.research_history import (
    MAX_RESEARCH_HISTORY_FILE_BYTES,
    MAX_RESEARCH_HISTORY_LINE_BYTES,
)
from scion.postrun.research_effectiveness import LoadedHistoryAvailable
from scion.postrun.research_effectiveness.models import (
    ResearchEffectivenessInputError,
)
from scion.postrun.research_effectiveness.safe_artifact_loader import (
    _ALL_ARTIFACTS_MAX_BYTES,
    _load_root_snapshot,
)
from scion.postrun.research_effectiveness.study_root import (
    _compare_five_block_initial_screening_study_roots,
    _InitialScreeningStudyExpectation,
    _InitialScreeningStudyRootArtifacts,
)
from scion.postrun.research_effectiveness.study_root_loader import (
    _compare_five_block_initial_screening_study_root_paths,
    _InitialScreeningStudyRootPath,
    _MatchedInitialScreeningStudyRootPathBlock,
)
from scion.tests.campaign_test_support import (
    MockExperimentProtocol,
    _campaign,
    _make_protocol_result,
)
from scion.tests.unit.core.test_m32_initial_screening_only_boundary import (
    _envelope,
    _initial_only_config,
    _install_synthetic_bounded_proposals,
    _limits,
)
from scion.tests.unit.postrun.test_m32_initial_screening_study_root import (
    _block,
    _event_write_failure_root,
    _formal_record,
    _study_root,
)
from scion.tests.unit.postrun.test_m32_research_effectiveness import _expectation

_LOAD_ERROR = "STUDY_ROOT_LOAD_INVALID"
_PRODUCER_CASE_REFS = ("private/a/alpha.vrp", "private/b/beta.vrp")
_PRODUCER_SEEDS = (11, 29)


def _write_root(
    root: Path,
    artifacts: _InitialScreeningStudyRootArtifacts,
    *,
    write_history: bool = True,
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "status.json").write_text(
        json.dumps(artifacts.status, allow_nan=False, sort_keys=True),
        encoding="utf-8",
    )
    (root / "campaign_summary.json").write_text(
        json.dumps(artifacts.summary, allow_nan=False, sort_keys=True),
        encoding="utf-8",
    )
    if write_history:
        (root / "research_history.jsonl").write_text(
            "".join(
                f"{json.dumps(record, allow_nan=False)}\n"
                for record in artifacts.current_history
            ),
            encoding="utf-8",
        )


def _path_blocks(
    tmp_path: Path,
) -> tuple[_MatchedInitialScreeningStudyRootPathBlock, ...]:
    result: list[_MatchedInitialScreeningStudyRootPathBlock] = []
    for ordinal in range(1, 6):
        block = _block(ordinal)
        k1_path = tmp_path / f"block-{ordinal}-k1"
        k2_path = tmp_path / f"block-{ordinal}-k2"
        _write_root(k1_path, block.k1)
        _write_root(k2_path, block.k2)
        result.append(
            _MatchedInitialScreeningStudyRootPathBlock(
                k1=_InitialScreeningStudyRootPath(
                    root=k1_path,
                    expectation=block.k1.expectation,
                ),
                k2=_InitialScreeningStudyRootPath(
                    root=k2_path,
                    expectation=block.k2.expectation,
                ),
                loaded_history=block.loaded_history,
            )
        )
    return tuple(result)


def _replace_path(
    blocks: tuple[_MatchedInitialScreeningStudyRootPathBlock, ...],
    *,
    block_index: int = 0,
    arm: str = "k1",
    root: str | os.PathLike[str],
) -> tuple[_MatchedInitialScreeningStudyRootPathBlock, ...]:
    mutable = list(blocks)
    block = mutable[block_index]
    current = getattr(block, arm)
    replacement = replace(current, root=root)
    mutable[block_index] = replace(block, **{arm: replacement})
    return tuple(mutable)


def _assert_fixed_load_error(call: Any) -> None:
    with pytest.raises(ResearchEffectivenessInputError) as raised:
        call()
    error = raised.value
    assert error.code == _LOAD_ERROR
    assert str(error) == _LOAD_ERROR
    assert error.args == (_LOAD_ERROR,)
    assert repr(error) == f"ResearchEffectivenessInputError({_LOAD_ERROR!r})"
    assert error.__cause__ is None
    assert error.__context__ is None


def test_private_loader_matches_decoded_ten_arm_audit_and_decodes_all_before_d3(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocks = _path_blocks(tmp_path)
    expected = _compare_five_block_initial_screening_study_roots(
        blocks=tuple(_block(ordinal) for ordinal in range(1, 6))
    )
    original = study_root_module._decode_study_root
    decoded = 0

    def counted(artifacts: _InitialScreeningStudyRootArtifacts) -> Any:
        nonlocal decoded
        decoded += 1
        return original(artifacts)

    monkeypatch.setattr(study_root_module, "_decode_study_root", counted)

    result = _compare_five_block_initial_screening_study_root_paths(blocks=blocks)

    assert decoded == 10
    assert result == expected
    assert "root" not in json.dumps(result, sort_keys=True).casefold()


def test_loader_path_carriers_are_private_redacted_and_not_exported(
    tmp_path: Path,
) -> None:
    blocks = _path_blocks(tmp_path)
    path = blocks[0].k1

    assert str(path.root) not in repr(path)
    assert str(path.root) not in repr(blocks[0])
    assert not hasattr(
        public_api,
        "compare_five_block_initial_screening_study_root_paths",
    )
    assert not hasattr(public_api, "InitialScreeningStudyRootPath")


@pytest.mark.parametrize(
    "invalid_root",
    [
        "relative/root",
        "/",
        "//tmp/root",
        "/tmp/root/.",
        "/tmp/root/../root",
        "/tmp/root/",
        "/tmp/root\x00suffix",
    ],
)
def test_loader_rejects_noncanonical_root_spellings(
    tmp_path: Path,
    invalid_root: str,
) -> None:
    blocks = _path_blocks(tmp_path)

    _assert_fixed_load_error(
        lambda: _compare_five_block_initial_screening_study_root_paths(
            blocks=_replace_path(blocks, root=invalid_root)
        )
    )


def test_loader_rejects_a_symlinked_root_component(tmp_path: Path) -> None:
    blocks = _path_blocks(tmp_path / "real")
    alias = tmp_path / "alias"
    alias.symlink_to(tmp_path / "real", target_is_directory=True)
    target = Path(blocks[0].k1.root)
    aliased = alias / target.relative_to(tmp_path / "real")

    _assert_fixed_load_error(
        lambda: _compare_five_block_initial_screening_study_root_paths(
            blocks=_replace_path(blocks, root=aliased)
        )
    )


def test_loader_rejects_duplicate_root_identity(tmp_path: Path) -> None:
    blocks = _path_blocks(tmp_path)

    _assert_fixed_load_error(
        lambda: _compare_five_block_initial_screening_study_root_paths(
            blocks=_replace_path(blocks, arm="k2", root=blocks[0].k1.root)
        )
    )


def test_loader_rejects_duplicate_canonical_tokens_before_any_root_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocks = _path_blocks(tmp_path)
    blocks = _replace_path(blocks, arm="k2", root=blocks[0].k1.root)
    reads = 0

    def unexpected_load(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal reads
        reads += 1
        raise AssertionError("duplicate token reached artifact loading")

    monkeypatch.setattr(
        loader_module,
        "_load_root_snapshot_from_canonical",
        unexpected_load,
    )

    _assert_fixed_load_error(
        lambda: _compare_five_block_initial_screening_study_root_paths(blocks=blocks)
    )
    assert reads == 0


def test_loader_rejects_a_leaf_symlink_and_hardlinked_leaf_alias(
    tmp_path: Path,
) -> None:
    symlink_blocks = _path_blocks(tmp_path / "symlink")
    symlink_root = Path(symlink_blocks[0].k1.root)
    status = symlink_root / "status.json"
    target = symlink_root / "status-target.json"
    status.rename(target)
    status.symlink_to(target.name)

    _assert_fixed_load_error(
        lambda: _compare_five_block_initial_screening_study_root_paths(
            blocks=symlink_blocks
        )
    )


def test_loader_rejects_a_leaf_hardlinked_only_to_an_external_path(
    tmp_path: Path,
) -> None:
    blocks = _path_blocks(tmp_path / "roots")
    status = Path(blocks[0].k1.root) / "status.json"
    external = tmp_path / "external-status.json"
    os.link(status, external)

    _assert_fixed_load_error(
        lambda: _compare_five_block_initial_screening_study_root_paths(blocks=blocks)
    )

    hardlink_blocks = _path_blocks(tmp_path / "hardlink")
    first = Path(hardlink_blocks[0].k1.root) / "status.json"
    second = Path(hardlink_blocks[0].k2.root) / "status.json"
    second.unlink()
    os.link(first, second)

    _assert_fixed_load_error(
        lambda: _compare_five_block_initial_screening_study_root_paths(
            blocks=hardlink_blocks
        )
    )


@pytest.mark.parametrize("leaf_kind", ["directory", "fifo"])
def test_loader_rejects_nonregular_required_leaves(
    tmp_path: Path,
    leaf_kind: str,
) -> None:
    blocks = _path_blocks(tmp_path)
    status = Path(blocks[0].k1.root) / "status.json"
    status.unlink()
    if leaf_kind == "directory":
        status.mkdir()
    else:
        os.mkfifo(status)

    _assert_fixed_load_error(
        lambda: _compare_five_block_initial_screening_study_root_paths(blocks=blocks)
    )


@pytest.mark.parametrize(
    ("name", "payload"),
    [
        ("status.json", b'{"outer":{"duplicate":1,"duplicate":2}}'),
        ("status.json", b'{"value":NaN}'),
        ("status.json", b'{"value":Infinity}'),
        ("status.json", b'{"value":1e999}'),
        ("status.json", b"\xef\xbb\xbf{}"),
        ("status.json", b"{}{}"),
        ("status.json", b"{} trailing-private-body"),
        ("status.json", b"[]"),
        ("status.json", b'{"invalid":\xff}'),
        ("campaign_summary.json", b'{"steps":[],"steps":[]}'),
    ],
)
def test_loader_rejects_noncanonical_json_without_leaking_body(
    tmp_path: Path,
    name: str,
    payload: bytes,
) -> None:
    blocks = _path_blocks(tmp_path)
    (Path(blocks[0].k1.root) / name).write_bytes(payload)

    _assert_fixed_load_error(
        lambda: _compare_five_block_initial_screening_study_root_paths(blocks=blocks)
    )


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"{}",
        b"\n",
        b"{}\n\n",
        b"{}\r\n",
        b"[]\n",
        b'{"nested":{"same":1,"same":2}}\n',
        b'{"value":NaN}\n',
        b'{"invalid":\xff}\n',
    ],
)
def test_loader_rejects_noncanonical_present_history(
    tmp_path: Path,
    payload: bytes,
) -> None:
    blocks = _path_blocks(tmp_path)
    (Path(blocks[0].k1.root) / "research_history.jsonl").write_bytes(payload)

    _assert_fixed_load_error(
        lambda: _compare_five_block_initial_screening_study_root_paths(blocks=blocks)
    )


def test_missing_history_requires_an_empty_summary_prefix(tmp_path: Path) -> None:
    blocks = _path_blocks(tmp_path)
    (Path(blocks[0].k1.root) / "research_history.jsonl").unlink()

    _assert_fixed_load_error(
        lambda: _compare_five_block_initial_screening_study_root_paths(blocks=blocks)
    )


@pytest.mark.parametrize(
    ("name", "size"),
    [
        ("status.json", 8 * 1024 * 1024 + 1),
        ("campaign_summary.json", 32 * 1024 * 1024 + 1),
        ("research_history.jsonl", MAX_RESEARCH_HISTORY_FILE_BYTES + 1),
    ],
)
def test_loader_rejects_oversized_leaves_before_reading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    size: int,
) -> None:
    blocks = _path_blocks(tmp_path)
    target = Path(blocks[0].k1.root) / name
    with target.open("wb") as output:
        output.truncate(size)
    original_read = safe_loader_module.os.read
    reads_from_target = 0
    target_identity = (target.stat().st_dev, target.stat().st_ino)

    def counted_read(fd: int, count: int) -> bytes:
        nonlocal reads_from_target
        value = os.fstat(fd)
        if (value.st_dev, value.st_ino) == target_identity:
            reads_from_target += 1
        return original_read(fd, count)

    monkeypatch.setattr(safe_loader_module.os, "read", counted_read)

    _assert_fixed_load_error(
        lambda: _compare_five_block_initial_screening_study_root_paths(blocks=blocks)
    )
    assert reads_from_target == 0


def test_loader_enforces_physical_history_line_and_arm_record_caps(
    tmp_path: Path,
) -> None:
    line_blocks = _path_blocks(tmp_path / "line")
    line_history = Path(line_blocks[0].k1.root) / "research_history.jsonl"
    line_history.write_bytes(
        b'{"value":"' + b"x" * MAX_RESEARCH_HISTORY_LINE_BYTES + b'"}\n'
    )
    _assert_fixed_load_error(
        lambda: _compare_five_block_initial_screening_study_root_paths(
            blocks=line_blocks
        )
    )

    count_blocks = _path_blocks(tmp_path / "count")
    history = Path(count_blocks[0].k1.root) / "research_history.jsonl"
    one_line = history.read_bytes()
    history.write_bytes(one_line + one_line)
    _assert_fixed_load_error(
        lambda: _compare_five_block_initial_screening_study_root_paths(
            blocks=count_blocks
        )
    )


def test_loader_applies_running_total_cap_and_does_not_read_later_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocks = _path_blocks(tmp_path)
    first = Path(blocks[0].k1.root)
    second = Path(blocks[0].k2.root)
    first_total = sum(path.stat().st_size for path in first.iterdir())
    second_status = (second / "status.json").stat().st_size
    monkeypatch.setattr(
        loader_module,
        "_ALL_ARTIFACTS_MAX_BYTES",
        first_total + second_status - 1,
    )
    original = loader_module._load_root_snapshot_from_canonical
    calls = 0

    def counted(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        loader_module,
        "_load_root_snapshot_from_canonical",
        counted,
    )

    _assert_fixed_load_error(
        lambda: _compare_five_block_initial_screening_study_root_paths(blocks=blocks)
    )
    assert calls == 2


def test_loader_applies_running_history_aggregate_cap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocks = _path_blocks(tmp_path)
    first = Path(blocks[0].k1.root) / "research_history.jsonl"
    second = Path(blocks[0].k2.root) / "research_history.jsonl"
    monkeypatch.setattr(
        loader_module,
        "MAX_RESEARCH_HISTORY_TOTAL_BYTES",
        first.stat().st_size + second.stat().st_size - 1,
    )
    original = loader_module._load_root_snapshot_from_canonical
    calls = 0

    def counted(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        loader_module,
        "_load_root_snapshot_from_canonical",
        counted,
    )

    _assert_fixed_load_error(
        lambda: _compare_five_block_initial_screening_study_root_paths(blocks=blocks)
    )
    assert calls == 2


def test_loader_canonicalizes_each_pathlike_once_before_reading(
    tmp_path: Path,
) -> None:
    blocks = _path_blocks(tmp_path)
    original = Path(blocks[0].k1.root)

    class MutablePath:
        def __init__(self) -> None:
            self.calls = 0

        def __fspath__(self) -> str:
            self.calls += 1
            return str(original if self.calls == 1 else blocks[0].k2.root)

    mutable = MutablePath()
    changed = _replace_path(blocks, root=mutable)

    result = _compare_five_block_initial_screening_study_root_paths(blocks=changed)

    assert mutable.calls == 1
    assert result["status"] == "endpoint_conditions_satisfied"


def test_loader_detects_atomic_leaf_replacement_after_final_leaf_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocks = _path_blocks(tmp_path)
    target_root = Path(blocks[0].k1.root)
    target_identity = (target_root.stat().st_dev, target_root.stat().st_ino)
    target = target_root / "status.json"
    original = safe_loader_module._verify_leaf
    status_checks = 0

    def replace_after_status_check(
        root_fd: int,
        name: str,
        expected: Any,
    ) -> None:
        nonlocal status_checks
        original(root_fd, name, expected)
        root_stat = os.fstat(root_fd)
        if (
            root_stat.st_dev,
            root_stat.st_ino,
        ) == target_identity and name == "status.json":
            status_checks += 1
            if status_checks == 2:
                replacement = target_root / "replacement.json"
                replacement.write_bytes(target.read_bytes())
                os.replace(replacement, target)

    monkeypatch.setattr(safe_loader_module, "_verify_leaf", replace_after_status_check)

    _assert_fixed_load_error(
        lambda: _compare_five_block_initial_screening_study_root_paths(blocks=blocks)
    )
    assert status_checks == 2


def test_loader_uses_only_fixed_literal_names_without_fallback(
    tmp_path: Path,
) -> None:
    blocks = _path_blocks(tmp_path)
    root = Path(blocks[0].k1.root)
    status = root / "status.json"
    backup = root / "status.json.backup"
    status.rename(backup)
    (root / "scion.db").write_bytes(b"PRIVATE DATABASE SENTINEL")
    (root / "raw_metrics.json").write_text('{"status":"forged"}', encoding="utf-8")

    _assert_fixed_load_error(
        lambda: _compare_five_block_initial_screening_study_root_paths(blocks=blocks)
    )
    assert backup.exists()


def test_a_structurally_incomplete_first_arm_still_decodes_all_ten(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocks = _path_blocks(tmp_path)
    incomplete = _event_write_failure_root(failure_detail="")
    matching_k2 = _study_root(
        records=(
            _formal_record(hypothesis_text="matching K2 first"),
            _formal_record(hypothesis_text="matching K2 second"),
        ),
        k=2,
        a_cap=2,
        campaign_id="incomplete-block-k2",
    )
    first_root = Path(blocks[0].k1.root)
    second_root = Path(blocks[0].k2.root)
    _write_root(first_root, incomplete)
    _write_root(second_root, matching_k2)
    blocks = tuple(
        replace(
            block,
            k1=(
                replace(block.k1, expectation=incomplete.expectation)
                if ordinal == 0
                else block.k1
            ),
            k2=(
                replace(block.k2, expectation=matching_k2.expectation)
                if ordinal == 0
                else block.k2
            ),
        )
        for ordinal, block in enumerate(blocks)
    )
    original = study_root_module._decode_study_root
    decoded = 0

    def counted(artifacts: _InitialScreeningStudyRootArtifacts) -> Any:
        nonlocal decoded
        decoded += 1
        return original(artifacts)

    monkeypatch.setattr(study_root_module, "_decode_study_root", counted)

    result = _compare_five_block_initial_screening_study_root_paths(blocks=blocks)

    assert decoded == 10
    assert result["status"] == "inconclusive"


def test_loader_output_is_detached_from_disk_and_path_inputs(tmp_path: Path) -> None:
    blocks = _path_blocks(tmp_path)
    before = deepcopy(blocks)

    result = _compare_five_block_initial_screening_study_root_paths(blocks=blocks)
    result_before = deepcopy(result)
    result["status"] = "MUTATED"

    assert blocks == before
    status = Path(blocks[0].k1.root) / "status.json"
    disk_before = status.read_bytes()
    status.write_text("{}", encoding="utf-8")
    assert result_before["status"] != "MUTATED"
    assert disk_before != status.read_bytes()


def test_loader_never_lists_or_opens_adjacent_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocks = _path_blocks(tmp_path)
    for block in blocks:
        for path in (block.k1, block.k2):
            root = Path(path.root)
            (root / "scion.db").write_bytes(b"PRIVATE DATABASE SENTINEL")
            (root / "status.json.backup").write_bytes(b"FORGED FALLBACK")
            (root / "raw_metrics.json").write_bytes(b"RAW METRICS SENTINEL")
    opened_leaves: list[str] = []
    read_leaves: list[str] = []
    leaf_fds: dict[int, str] = {}
    original_open = safe_loader_module.os.open
    original_read = safe_loader_module.os.read
    original_close = safe_loader_module.os.close

    def tracked_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        fd = original_open(path, flags, *args, **kwargs)
        if not flags & os.O_DIRECTORY:
            name = os.fspath(path)
            opened_leaves.append(name)
            leaf_fds[fd] = name
        return fd

    def tracked_read(fd: int, count: int) -> bytes:
        read_leaves.append(leaf_fds[fd])
        return original_read(fd, count)

    def tracked_close(fd: int) -> None:
        leaf_fds.pop(fd, None)
        original_close(fd)

    def forbidden_scan(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("safe loader attempted directory discovery")

    monkeypatch.setattr(safe_loader_module.os, "open", tracked_open)
    monkeypatch.setattr(safe_loader_module.os, "read", tracked_read)
    monkeypatch.setattr(safe_loader_module.os, "close", tracked_close)
    monkeypatch.setattr(safe_loader_module.os, "listdir", forbidden_scan)
    monkeypatch.setattr(safe_loader_module.os, "scandir", forbidden_scan)
    monkeypatch.setattr(safe_loader_module.os, "walk", forbidden_scan)

    result = _compare_five_block_initial_screening_study_root_paths(blocks=blocks)

    literal_names = {
        "status.json",
        "campaign_summary.json",
        "research_history.jsonl",
    }
    assert set(opened_leaves) == literal_names
    assert set(read_leaves) == literal_names
    assert result["status"] == "endpoint_conditions_satisfied"


def test_loader_caps_cannot_be_loosened_by_a_private_core_caller(
    tmp_path: Path,
) -> None:
    blocks = _path_blocks(tmp_path)

    _assert_fixed_load_error(
        lambda: _load_root_snapshot(
            blocks[0].k1.root,
            history_record_cap=1,
            total_byte_limit=_ALL_ARTIFACTS_MAX_BYTES + 1,
        )
    )


def test_semantic_artifact_errors_are_rethrown_without_body_context(
    tmp_path: Path,
) -> None:
    blocks = _path_blocks(tmp_path)
    status = Path(blocks[0].k1.root) / "status.json"
    status.write_text("{}", encoding="utf-8")

    with pytest.raises(ResearchEffectivenessInputError) as raised:
        _compare_five_block_initial_screening_study_root_paths(blocks=blocks)

    error = raised.value
    assert error.code != _LOAD_ERROR
    assert error.args == (error.code,)
    assert error.__cause__ is None
    assert error.__context__ is None
    assert str(status) not in repr(error)


def test_loader_result_recursively_excludes_path_and_artifact_bodies(
    tmp_path: Path,
) -> None:
    blocks = _path_blocks(tmp_path)
    forbidden: set[str] = set()
    for block in blocks:
        for path in (block.k1, block.k2):
            root = Path(path.root)
            forbidden.add(str(root))
            status = json.loads((root / "status.json").read_text(encoding="utf-8"))
            forbidden.add(str(status["campaign_id"]))
            for line in (
                (root / "research_history.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ):
                record = json.loads(line)
                hypothesis = record.get("hypothesis")
                if isinstance(hypothesis, dict):
                    forbidden.add(str(hypothesis.get("text", "")))
                    forbidden.add(str(hypothesis.get("target_file", "")))
                patch = record.get("patch")
                if isinstance(patch, dict):
                    for change in patch.get("changes", []):
                        forbidden.add(str(change.get("file_path", "")))
                        forbidden.add(str(change.get("source", "")))

    result = _compare_five_block_initial_screening_study_root_paths(blocks=blocks)
    rendered = json.dumps(result, sort_keys=True)

    assert all(not value or value not in rendered for value in forbidden)


def _zero_dispatch_path(
    parent: Path,
    *,
    k: int,
    campaign_id: str,
) -> _InitialScreeningStudyRootPath:
    parent.mkdir(parents=True)
    protocol = MockExperimentProtocol(
        results=[_make_protocol_result(ExperimentStage.SCREENING, "pass")]
    )
    manager = _campaign(
        parent,
        experiment_protocol=protocol,
        qualification_only=_initial_only_config(attempt_cap=2),
        resource_envelope=_envelope(),
        code_research_limits=_limits(candidates=k),
    )
    manager._campaign_id = campaign_id
    _install_synthetic_bounded_proposals(manager, candidates=k)
    hardwall = _CampaignOuterHardwall(None)
    hardwall.expired.set()
    with _campaign_signal_handlers(manager, hardwall=hardwall):
        handler = signal.getsignal(signal.SIGTERM)
        assert callable(handler)

        def interrupt_preflight() -> None:
            handler(signal.SIGTERM, None)

        manager._run_research_environment_preflight = interrupt_preflight
        with pytest.raises(_CampaignSignalStop) as raised:
            manager.run(requested_rounds=2)
    manager.finalize_requested_stop(
        raised.value.reason,
        interrupted_override=raised.value.interrupted_override,
    )
    root = parent / "campaign"
    assert (root / "status.json").is_file()
    assert (root / "campaign_summary.json").is_file()
    assert not (root / "research_history.jsonl").exists()
    effectiveness = replace(
        _expectation(a_cap=2, p_cap=200, k=k),
        problem_id="test_vrp",
        expected_initial_case_count=2,
        expected_initial_pair_count=4,
    )
    return _InitialScreeningStudyRootPath(
        root=root,
        expectation=_InitialScreeningStudyExpectation(
            effectiveness=effectiveness,
            case_refs=_PRODUCER_CASE_REFS,
            seeds=_PRODUCER_SEEDS,
            equivalence_band=0.0,
        ),
    )


def test_real_writer_zero_dispatch_roots_load_without_history_and_remain_incomplete(
    tmp_path: Path,
) -> None:
    blocks = tuple(
        _MatchedInitialScreeningStudyRootPathBlock(
            k1=_zero_dispatch_path(
                tmp_path / f"block-{ordinal}-k1",
                k=1,
                campaign_id=f"real-zero-block-{ordinal}-k1",
            ),
            k2=_zero_dispatch_path(
                tmp_path / f"block-{ordinal}-k2",
                k=2,
                campaign_id=f"real-zero-block-{ordinal}-k2",
            ),
            loaded_history=LoadedHistoryAvailable(records=()),
        )
        for ordinal in range(1, 6)
    )

    result = _compare_five_block_initial_screening_study_root_paths(blocks=blocks)

    assert result["status"] == "inconclusive"
    assert len(result["block_signs"]) == 5
    assert all(sign["status"] == "INCONCLUSIVE" for sign in result["block_signs"])

    first_history = Path(blocks[0].k1.root) / "research_history.jsonl"
    first_history.write_bytes(b"")
    _assert_fixed_load_error(
        lambda: _compare_five_block_initial_screening_study_root_paths(blocks=blocks)
    )
