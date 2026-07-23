from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from scion.runtime.execution.environment_integrity import (
    EnvironmentContentReceipt,
    EnvironmentIntegrityError,
    ExternalRuntimeEntry,
    verify_environment_content,
)


@pytest.fixture
def immutable_environment(
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> tuple[Path, Path, Path, Path]:
    candidate = tmp_path / "candidate"
    selection = tmp_path / ".scion-w3-selections" / ("a" * 64)
    environment = candidate / "environment"
    package = environment / "lib" / "python3.12" / "site-packages" / "example"
    binary = environment / "bin" / "python"
    module = package / "__init__.py"
    external = tmp_path / "external-python"

    package.mkdir(parents=True)
    binary.parent.mkdir()
    selection.mkdir(parents=True)
    binary.write_bytes(b"ELF runtime entrypoint\n")
    module.write_bytes(b"VALUE = 1\n")
    external.write_bytes(b"external runtime bytes\n")
    binary.chmod(0o555)
    module.chmod(0o444)
    external.chmod(0o444)
    for directory in sorted(
        (item for item in environment.rglob("*") if item.is_dir()),
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        directory.chmod(0o555)
    environment.chmod(0o555)

    def restore_writable() -> None:
        for directory in sorted(
            (item for item in tmp_path.rglob("*") if item.is_dir()),
            key=lambda item: len(item.parts),
        ):
            directory.chmod(0o755)
        for item in tmp_path.rglob("*"):
            if item.is_file():
                item.chmod(0o644)

    request.addfinalizer(restore_writable)
    return environment, external, candidate, selection


def _receipt(
    facts: tuple[Path, Path, Path, Path],
) -> EnvironmentContentReceipt:
    environment, external, candidate, selection = facts
    return EnvironmentContentReceipt.create(
        environment,
        external_runtime_paths=(external,),
        candidate_root=candidate,
        selection_root=selection,
    )


def test_canonical_receipt_round_trip_and_read_only_verification(
    immutable_environment: tuple[Path, Path, Path, Path],
) -> None:
    environment, external, candidate, selection = immutable_environment

    receipt = _receipt(immutable_environment)
    decoded = json.loads(receipt.raw)

    assert receipt == EnvironmentContentReceipt.from_bytes(receipt.raw)
    assert receipt.raw.endswith(b"\n")
    assert receipt.raw_sha256
    assert decoded["schema"] == "scion.environment-content.v1"
    assert [item["path"] for item in decoded["environment_inventory"]] == [
        ".",
        "bin",
        "bin/python",
        "lib",
        "lib/python3.12",
        "lib/python3.12/site-packages",
        "lib/python3.12/site-packages/example",
        "lib/python3.12/site-packages/example/__init__.py",
    ]
    assert decoded["environment_inventory"][0] == {
        "kind": "directory",
        "mode": 0o555,
        "path": ".",
        "sha256": None,
        "size_bytes": 0,
    }
    assert decoded["environment_inventory"][2]["mode"] == 0o555
    assert decoded["environment_inventory"][-1]["mode"] == 0o444
    assert decoded["external_runtime"] == [
        {
            "device": os.lstat(external).st_dev,
            "inode": os.lstat(external).st_ino,
            "path": str(external),
            "sha256": ExternalRuntimeEntry.acquire(external).sha256,
            "size_bytes": len(b"external runtime bytes\n"),
        }
    ]

    before = receipt.raw
    verify_environment_content(
        environment,
        receipt,
        external_runtime_paths=(external,),
        candidate_root=candidate,
        selection_root=selection,
    )
    assert receipt.raw == before


@pytest.mark.parametrize("case", ["symlink", "hardlink", "fifo", "bad-mode"])
def test_environment_rejects_nonclosed_tree_entries(
    immutable_environment: tuple[Path, Path, Path, Path],
    case: str,
) -> None:
    environment, _external, _candidate, _selection = immutable_environment
    module = (
        environment / "lib" / "python3.12" / "site-packages" / "example" / "__init__.py"
    )
    parent = module.parent
    parent.chmod(0o755)
    if case == "symlink":
        os.symlink("__init__.py", parent / "link.py")
    elif case == "hardlink":
        os.link(module, parent / "hardlink.py")
    elif case == "fifo":
        os.mkfifo(parent / "pipe")
    else:
        module.chmod(0o644)
    parent.chmod(0o555)

    with pytest.raises(
        EnvironmentIntegrityError,
        match="symlink|multiply linked|special file|mode differs",
    ):
        _receipt(immutable_environment)


def test_candidate_and_selection_path_byte_leaks_are_rejected(
    immutable_environment: tuple[Path, Path, Path, Path],
) -> None:
    environment, _external, candidate, selection = immutable_environment
    module = (
        environment / "lib" / "python3.12" / "site-packages" / "example" / "__init__.py"
    )
    module.chmod(0o644)
    module.write_bytes(
        b"candidate="
        + str(candidate).encode()
        + b"\nselection="
        + str(selection).encode()
    )
    module.chmod(0o444)

    with pytest.raises(EnvironmentIntegrityError, match="forbidden path"):
        _receipt(immutable_environment)


def test_candidate_path_leak_crossing_read_boundary_is_rejected(
    immutable_environment: tuple[Path, Path, Path, Path],
) -> None:
    environment, _external, candidate, _selection = immutable_environment
    module = (
        environment / "lib" / "python3.12" / "site-packages" / "example" / "__init__.py"
    )
    needle = str(candidate).encode()
    split = len(needle) // 2
    module.chmod(0o644)
    module.write_bytes(b"x" * (1024 * 1024 - split) + needle)
    module.chmod(0o444)

    with pytest.raises(EnvironmentIntegrityError, match="forbidden path"):
        _receipt(immutable_environment)


def test_external_runtime_requires_absolute_regular_paths_and_allows_hardlinks(
    immutable_environment: tuple[Path, Path, Path, Path],
) -> None:
    environment, external, candidate, selection = immutable_environment
    alias = external.parent / "external-alias"
    os.link(external, alias)

    first = ExternalRuntimeEntry.acquire(external)
    second = ExternalRuntimeEntry.acquire(alias)
    assert (first.device, first.inode) == (second.device, second.inode)
    receipt = EnvironmentContentReceipt.create(
        environment,
        external_runtime_paths=(external, alias),
        candidate_root=candidate,
        selection_root=selection,
    )
    assert len(receipt.external_runtime) == 2
    with pytest.raises(EnvironmentIntegrityError, match="path is duplicated"):
        EnvironmentContentReceipt.create(
            environment,
            external_runtime_paths=(external, external),
            candidate_root=candidate,
            selection_root=selection,
        )
    symlink = external.parent / "external-symlink"
    symlink.symlink_to(external)
    with pytest.raises(EnvironmentIntegrityError, match="symlink"):
        ExternalRuntimeEntry.acquire(symlink)
    with pytest.raises(EnvironmentIntegrityError, match="canonical absolute"):
        ExternalRuntimeEntry.acquire(Path("relative-python"))
    with pytest.raises(EnvironmentIntegrityError, match="canonical absolute"):
        ExternalRuntimeEntry.acquire(Path("//tmp/runtime"))


def test_verify_detects_environment_and_external_runtime_drift(
    immutable_environment: tuple[Path, Path, Path, Path],
) -> None:
    environment, external, candidate, selection = immutable_environment
    receipt = _receipt(immutable_environment)
    module = (
        environment / "lib" / "python3.12" / "site-packages" / "example" / "__init__.py"
    )
    module.chmod(0o644)
    module.write_bytes(b"VALUE = 2\n")
    module.chmod(0o444)

    with pytest.raises(EnvironmentIntegrityError, match="inventory differs"):
        verify_environment_content(
            environment,
            receipt,
            external_runtime_paths=(external,),
            candidate_root=candidate,
            selection_root=selection,
        )

    module.chmod(0o644)
    module.write_bytes(b"VALUE = 1\n")
    module.chmod(0o444)
    external.chmod(0o644)
    external.write_bytes(b"changed external runtime\n")
    external.chmod(0o444)
    with pytest.raises(EnvironmentIntegrityError, match="external runtime"):
        verify_environment_content(
            environment,
            receipt,
            external_runtime_paths=(external,),
            candidate_root=candidate,
            selection_root=selection,
        )


def test_receipt_parser_rejects_noncanonical_unknown_and_duplicate_fields(
    immutable_environment: tuple[Path, Path, Path, Path],
) -> None:
    receipt = _receipt(immutable_environment)
    decoded = json.loads(receipt.raw)
    noncanonical = json.dumps(decoded, indent=2, sort_keys=True).encode() + b"\n"
    unknown = dict(decoded)
    unknown["unexpected"] = False
    unknown_raw = (
        json.dumps(
            unknown,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()
    duplicate = receipt.raw.replace(
        b'{"environment_inventory":',
        b'{"schema":"duplicate","environment_inventory":',
        1,
    )

    with pytest.raises(EnvironmentIntegrityError, match="canonical"):
        EnvironmentContentReceipt.from_bytes(noncanonical)
    with pytest.raises(EnvironmentIntegrityError, match="fields differ"):
        EnvironmentContentReceipt.from_bytes(unknown_raw)
    with pytest.raises(EnvironmentIntegrityError, match="duplicate JSON key"):
        EnvironmentContentReceipt.from_bytes(duplicate)

    environment, external, candidate, selection = immutable_environment
    with pytest.raises(EnvironmentIntegrityError, match="receipt object differs"):
        verify_environment_content(
            environment,
            replace(receipt, raw_sha256="0" * 64),
            external_runtime_paths=(external,),
            candidate_root=candidate,
            selection_root=selection,
        )


def test_receipt_parser_requires_tree_parent_closure(
    immutable_environment: tuple[Path, Path, Path, Path],
) -> None:
    receipt = _receipt(immutable_environment)
    decoded = json.loads(receipt.raw)

    without_parent = dict(decoded)
    without_parent["environment_inventory"] = [
        item
        for item in decoded["environment_inventory"]
        if item["path"] != "lib/python3.12/site-packages/example"
    ]
    without_parent_raw = (
        json.dumps(
            without_parent,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()
    with pytest.raises(EnvironmentIntegrityError, match="parent closure"):
        EnvironmentContentReceipt.from_bytes(without_parent_raw)
