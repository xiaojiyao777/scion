from __future__ import annotations

import json
import os
from pathlib import Path
import stat

import pytest

import scion.problems.warehouse_delivery.w3_candidate_ingress as ingress_module
from scion.problems.warehouse_delivery.w3_candidate_gate import (
    CandidateGateClosureBundle,
)
from scion.problems.warehouse_delivery.w3_candidate_ingress import (
    CandidateGateIngressFact,
    CandidateGateIngressState,
    WarehouseW3CandidateIngressAlreadyPublished,
    WarehouseW3CandidateIngressError,
    WarehouseW3CandidateIngressHold,
    classify_candidate_gate_ingress,
    derive_candidate_gate_ingress_paths,
    pin_candidate_gate_ingress,
    publish_candidate_gate_ingress,
    reopen_candidate_gate_ingress,
)
from scion.problems.warehouse_delivery.w3_composition import (
    EXPECTED_MANIFEST_SHA256,
)
from scion.problems.warehouse_delivery.w3_installation import CandidateRootIdentity
from scion.tests.unit.problems.warehouse_delivery.test_w3_candidate_gate import (
    _candidate,
    _double_wheel,
    _environment_content,
    _semantic,
    _sha,
)
from scion.tests.unit.problems.warehouse_delivery.w3_candidate_gate_support import (
    make_candidate_gate_closure,
)


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def _candidate_root(tmp_path: Path, key: str) -> Path:
    root = tmp_path / f"v04-w3-launch-{key}-claw"
    root.mkdir()
    root.chmod(0o555)
    return root


def _closure(root: Path, key: str) -> CandidateGateClosureBundle:
    accepted = root.parent / "accepted-w3-root"
    accepted.mkdir(exist_ok=True)
    accepted.chmod(0o555)
    wheel = _double_wheel()
    environment = _environment_content(wheel)
    semantic = _semantic(environment, wheel)
    candidate = _candidate(
        selection_key=key,
        environment_receipt_sha256=environment.raw_sha256,
        candidate_root_identity=CandidateRootIdentity.capture(root),
    )
    return make_candidate_gate_closure(
        candidate=candidate,
        candidate_root=root,
        accepted_root=accepted,
        nonce=_sha("ingress nonce"),
        manifest_sha256=EXPECTED_MANIFEST_SHA256,
        wheel=wheel,
        semantic=semantic,
        environment=environment,
    )


def test_fixed_ingress_round_trip_does_not_change_candidate_inventory(
    tmp_path: Path,
) -> None:
    key = "a" * 64
    root = _candidate_root(tmp_path, key)
    closure = _closure(root, key)
    gate = closure.gate
    before = tuple(root.iterdir())

    published = publish_candidate_gate_ingress(closure)

    paths = derive_candidate_gate_ingress_paths(root, key)
    assert published == paths.gate_path
    assert published.read_bytes() == gate.raw
    assert stat.S_IMODE(published.stat().st_mode) == 0o444
    assert stat.S_IMODE(paths.ingress_directory.stat().st_mode) == 0o555
    assert tuple(root.iterdir()) == before
    assert classify_candidate_gate_ingress(root) is CandidateGateIngressState.CLOSED
    assert reopen_candidate_gate_ingress(root) == closure


def test_ingress_is_no_replace_and_never_overwrites(tmp_path: Path) -> None:
    key = "a" * 64
    root = _candidate_root(tmp_path, key)
    closure = _closure(root, key)
    gate = closure.gate
    path = publish_candidate_gate_ingress(closure)

    with pytest.raises(
        WarehouseW3CandidateIngressAlreadyPublished,
        match="already accepted",
    ):
        publish_candidate_gate_ingress(closure)

    assert path.read_bytes() == gate.raw
    assert reopen_candidate_gate_ingress(root) == closure


def test_short_write_leaves_permanent_hold_without_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = "a" * 64
    root = _candidate_root(tmp_path, key)
    closure = _closure(root, key)
    real_write = ingress_module.os.write
    calls = 0

    def fail_after_prefix(descriptor: int, raw: bytes) -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            return real_write(descriptor, raw[:1])
        return 0

    monkeypatch.setattr(ingress_module.os, "write", fail_after_prefix)
    with pytest.raises(WarehouseW3CandidateIngressHold, match="partial hold"):
        publish_candidate_gate_ingress(closure)

    paths = derive_candidate_gate_ingress_paths(root, key)
    intent_path = paths.ingress_directory / "intent.v1.json"
    assert intent_path.read_bytes() == b"{"
    assert not paths.gate_path.exists()
    assert stat.S_IMODE(paths.ingress_directory.stat().st_mode) == 0o700
    assert (
        classify_candidate_gate_ingress(root) is CandidateGateIngressState.PARTIAL_HOLD
    )
    with pytest.raises(WarehouseW3CandidateIngressError):
        reopen_candidate_gate_ingress(root)


def test_reopen_rejects_candidate_identity_or_gate_inventory_drift(
    tmp_path: Path,
) -> None:
    key = "a" * 64
    root = _candidate_root(tmp_path, key)
    closure = _closure(root, key)
    publish_candidate_gate_ingress(closure)
    paths = derive_candidate_gate_ingress_paths(root, key)

    root.chmod(0o755)
    with pytest.raises(WarehouseW3CandidateIngressError, match="ownership differs"):
        reopen_candidate_gate_ingress(root)
    root.chmod(0o555)

    paths.ingress_directory.chmod(0o755)
    extra = paths.ingress_directory / "extra"
    extra.write_bytes(b"unexpected\n")
    extra.chmod(0o444)
    paths.ingress_directory.chmod(0o555)
    with pytest.raises(WarehouseW3CandidateIngressError, match="inventory differs"):
        reopen_candidate_gate_ingress(root)


def test_retained_ingress_context_revalidates_all_named_facts(
    tmp_path: Path,
) -> None:
    key = "a" * 64
    root = _candidate_root(tmp_path, key)
    closure = _closure(root, key)
    gate = closure.gate
    publish_candidate_gate_ingress(closure)
    paths = derive_candidate_gate_ingress_paths(root, key)

    pinned = pin_candidate_gate_ingress(root)
    try:
        assert pinned.candidate.path == str(root)
        assert pinned.gate == gate
        assert pinned.closure == closure
        assert CandidateGateIngressFact.from_bytes(pinned.fact.raw) == pinned.fact
        assert pinned.fact.experiment_parent_identity.uid == root.stat().st_uid
        assert pinned.fact.ingress_parent_identity.mode & 0o777 == 0o755
        drifted_fact = json.loads(pinned.fact.raw)
        drifted_fact["gate_receipt_sha256"] = "0" * 64
        with pytest.raises(
            WarehouseW3CandidateIngressError,
            match="gate hashes differ",
        ):
            CandidateGateIngressFact.from_bytes(_canonical(drifted_fact))
        moved = paths.ingress_parent / f"{key}-moved"
        paths.ingress_directory.rename(moved)
        paths.ingress_directory.mkdir(mode=0o555)
        with pytest.raises(
            WarehouseW3CandidateIngressError,
            match="retained identity drifted",
        ):
            pinned.revalidate()
    finally:
        pinned.close()


def test_intent_or_gate_file_identity_drift_is_partial_hold(
    tmp_path: Path,
) -> None:
    key = "a" * 64
    root = _candidate_root(tmp_path, key)
    closure = _closure(root, key)
    publish_candidate_gate_ingress(closure)
    paths = derive_candidate_gate_ingress_paths(root, key)
    gate_path = paths.gate_path
    hardlink = tmp_path / "gate-hardlink"
    os.link(gate_path, hardlink)

    assert (
        classify_candidate_gate_ingress(root) is CandidateGateIngressState.PARTIAL_HOLD
    )
    with pytest.raises(WarehouseW3CandidateIngressError, match="identity differs"):
        reopen_candidate_gate_ingress(root)


def test_ingress_rejects_root_publisher_and_injected_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = "a" * 64
    root = _candidate_root(tmp_path, key)
    closure = _closure(root, key)
    monkeypatch.setattr(ingress_module.os, "geteuid", lambda: 0)

    with pytest.raises(PermissionError, match="refuses effective UID 0"):
        publish_candidate_gate_ingress(closure)

    with pytest.raises(
        WarehouseW3CandidateIngressError,
        match="canonical absolute path",
    ):
        derive_candidate_gate_ingress_paths(Path("relative"), key)
    wrong = tmp_path / f"arbitrary-{key}"
    with pytest.raises(
        WarehouseW3CandidateIngressError,
        match="basename",
    ):
        derive_candidate_gate_ingress_paths(wrong, key)
