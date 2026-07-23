from __future__ import annotations

import base64
import copy
import dataclasses
import hashlib
import json
import os
import pickle
from pathlib import Path

import pytest

from scion.runtime.execution import (
    CapturedStream,
    CgroupEventsFact,
    CgroupIdentity,
    ClosedSpawnObservation,
    GenericProcessSpec,
    InvocationLineage,
    InvocationTerminalError,
    InvocationWriter,
    JobCgroupKey,
    ProcessIdentity,
    StopPostEnvironment,
    StopPostTopology,
    TerminalPolicy,
    UnitHandoffProperties,
    WaitFact,
    accept_invocation,
    inspect_terminal,
    observe_unit_final,
    publish_opaque_artifact_bundle,
    seal_unit_drained,
)
from scion.runtime.execution import invocation_terminal as terminal

NONCE = "0123456789abcdef" * 4
AUTHORITY_SHA256 = "a" * 64
MANIFEST_SHA256 = "b" * 64
PROBLEM_ACCEPTANCE_SHA256 = "d" * 64


def _root(tmp_path: Path, name: str = "invocation") -> Path:
    root = tmp_path / name
    root.mkdir()
    for child in ("control", "evidence", "raw", "artifacts"):
        (root / child).mkdir()
    return root


def _policy(
    *,
    expected_rows: int = 2,
    artifact_names: tuple[str, ...] = ("analysis.bin", "summary.json"),
    nonce_claim_sha256: str | None = None,
) -> TerminalPolicy:
    return TerminalPolicy(
        authority_sha256=AUTHORITY_SHA256,
        manifest_sha256=MANIFEST_SHA256,
        invocation_nonce=NONCE,
        expected_rows=expected_rows,
        artifact_names=artifact_names,
        nonce_claim_sha256=nonce_claim_sha256,
    )


def _observation(ordinal: int) -> ClosedSpawnObservation:
    pid = 1201 + ordinal
    spec = GenericProcessSpec.create(
        opaque_job_key=f"opaque:job/{ordinal}",
        executable=b"/usr/bin/probe",
        argv=(b"/usr/bin/probe", f"job-{ordinal}".encode(), b"\xff"),
        environment=(b"A=1", b"B=\xff"),
        cwd=b"/tmp",
    )
    process = ProcessIdentity(
        pid=pid,
        proc_starttime_ticks=700 + ordinal,
        pidfd_device=5,
        pidfd_inode=91 + ordinal,
        creator_pid=1199,
        creator_starttime_ticks=600,
    )
    wait = WaitFact.from_native((pid, 1000, 1, 0, 0, 0, 0, 0))
    key = JobCgroupKey.create(ordinal=ordinal, invocation_nonce=NONCE)
    cgroup = CgroupIdentity(
        service_name="scion-w3@fixture.service",
        supervisor_name="supervisor",
        job_name=key.rendered_name,
        service_device=1,
        service_inode=11,
        supervisor_device=1,
        supervisor_inode=12,
        job_device=1,
        job_inode=20 + ordinal,
        service_relative_lineage=(
            "scion-w3@fixture.service",
            key.rendered_name,
        ),
    )
    empty = CgroupEventsFact.decode(b"populated 0\nfrozen 0\n")
    final = CgroupEventsFact.decode(b"populated 0\nfrozen 0\nfuture_key 17\n")
    return ClosedSpawnObservation.create(
        spec=spec,
        start_wall_ns=100 + ordinal,
        end_wall_ns=200 + ordinal,
        start_monotonic_ns=300 + ordinal,
        end_monotonic_ns=400 + ordinal,
        process_identity=process,
        wait_fact=wait,
        stdout=CapturedStream.from_bytes(b"out-" + bytes([ordinal]) + b"\x00\xff"),
        stderr=CapturedStream.from_bytes(b"err-" + bytes([ordinal]) + b"\xfe"),
        cgroup_identity=cgroup,
        initial_cgroup_events=empty,
        final_cgroup_events=final,
    )


def _lineage() -> InvocationLineage:
    return InvocationLineage(
        boot_id="00000000-0000-0000-0000-000000000001",
        unit="scion-w3@fixture.service",
        invocation_id="1" * 32,
        control_group="/system.slice/scion-w3@fixture.service",
        service_device=1,
        service_inode=10,
        supervisor_device=1,
        supervisor_inode=11,
        main_pid=1200,
        main_starttime=700,
    )


def _stop_post() -> StopPostEnvironment:
    return StopPostEnvironment(
        invocation_id="1" * 32,
        service_result="success",
        exit_code="exited",
        exit_status="0",
    )


def _topology() -> StopPostTopology:
    return StopPostTopology(
        service_control_group="/system.slice/scion-w3@fixture.service",
        control_group="/system.slice/scion-w3@fixture.service/.control",
        sealer_pid=1300,
        sealer_starttime=800,
        control_pids=(1300,),
        supervisor_pids=(),
        job_cgroups=(),
        job_pids=(),
    )


def _handoff() -> UnitHandoffProperties:
    return UnitHandoffProperties(
        unit="scion-w3@fixture.service",
        invocation_id="1" * 32,
        load_state="loaded",
        active_state="inactive",
        sub_state="dead",
        result="success",
        exec_main_code=1,
        exec_main_status=0,
        exec_stop_post_code=1,
        exec_stop_post_status=0,
    )


def _advance_complete(root: Path, policy: TerminalPolicy):
    writer = InvocationWriter.open_fresh(root, policy)
    for ordinal in range(policy.expected_rows):
        observation = _observation(ordinal)
        writer.record_observation(ordinal, observation)
        writer.commit_opaque_row(
            ordinal,
            observation.observation_sha256,
            b"\x00opaque-row-" + str(ordinal).encode() + b"\xff",
        )
    writer.finish_raw()
    seal_unit_drained(root, policy, _lineage(), _stop_post(), _topology())
    observe_unit_final(root, policy, _handoff())
    return accept_invocation(root, policy, PROBLEM_ACCEPTANCE_SHA256)


def _tree_identity(root: Path) -> tuple[tuple[object, ...], ...]:
    identities = []
    for path in sorted(root.rglob("*"), key=lambda item: str(item.relative_to(root))):
        relative = str(path.relative_to(root))
        metadata = path.lstat()
        if path.is_file():
            data = path.read_bytes()
            identities.append(
                (
                    relative,
                    "file",
                    metadata.st_mode,
                    len(data),
                    hashlib.sha256(data).hexdigest(),
                )
            )
        elif path.is_dir():
            identities.append((relative, "directory", metadata.st_mode))
        else:
            identities.append((relative, "other", metadata.st_mode))
    return tuple(identities)


def test_complete_positive_chain_and_read_only_inspection(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    policy = _policy()
    assert inspect_terminal(root, policy).state == "PREPARED"

    writer = InvocationWriter.open_fresh(root, policy)
    assert inspect_terminal(root, policy).state == "ACTIVE_IDLE(0)"
    with pytest.raises(TypeError, match="not copyable"):
        copy.copy(writer)
    with pytest.raises(TypeError, match="not copyable"):
        copy.deepcopy(writer)
    with pytest.raises(TypeError, match="not serializable"):
        pickle.dumps(writer)

    first = _observation(0)
    evidence = writer.record_observation(0, first)
    assert evidence.observation_sha256 == first.observation_sha256
    assert inspect_terminal(root, policy).state == "EVIDENCE_ONLY(0)"
    evidence_bytes = (root / "evidence" / "000000.json").read_bytes()
    assert base64.b64encode(b"out-\x00\x00\xff") in evidence_bytes

    first_row = writer.commit_opaque_row(
        0, first.observation_sha256, b"\x00not-json\xff"
    )
    assert first_row.row_sha256 == hashlib.sha256(b"\x00not-json\xff").hexdigest()
    assert inspect_terminal(root, policy).state == "ACTIVE_IDLE(1)"

    second = _observation(1)
    writer.record_observation(1, second)
    writer.commit_opaque_row(1, second.observation_sha256, b"second\x00row")
    raw = writer.finish_raw()
    assert raw.row_count == 2
    assert inspect_terminal(root, policy).state == "RAW_COMPLETE"

    drained = seal_unit_drained(root, policy, _lineage(), _stop_post(), _topology())
    assert drained.invocation_id == "1" * 32
    assert inspect_terminal(root, policy).state == "UNIT_DRAINED"

    final = observe_unit_final(root, policy, _handoff())
    assert final.unit_drained_sha256 == drained.unit_drained_sha256
    assert inspect_terminal(root, policy).state == "UNIT_FINAL"

    complete = accept_invocation(root, policy, PROBLEM_ACCEPTANCE_SHA256)
    assert complete.opaque_problem_acceptance_digest == PROBLEM_ACCEPTANCE_SHA256
    assert inspect_terminal(root, policy).state == "COMPLETE_UNCLOSED"

    closed = publish_opaque_artifact_bundle(
        root,
        policy,
        complete,
        (
            ("analysis.bin", b"\x00analysis\xff"),
            ("summary.json", b'{"problem_owned":true}\n'),
        ),
    )
    assert closed.complete_sha256 == complete.complete_sha256
    assert (root / "artifacts" / "final" / "analysis.bin").read_bytes() == (
        b"\x00analysis\xff"
    )
    before = _tree_identity(root)
    inspection = inspect_terminal(root, policy)
    after = _tree_identity(root)
    assert inspection.state == "CLOSED"
    assert inspection.evidence_count == 2
    assert inspection.row_count == 2
    assert inspection.filesystem_mutated is False
    assert after == before


def test_claim_bound_terminal_retains_exact_claim_through_closed(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    claim = b'{"external_first":true,"schema":"claim-fixture.v1"}\n'
    policy = _policy(
        expected_rows=1,
        nonce_claim_sha256=hashlib.sha256(claim).hexdigest(),
    )
    assert inspect_terminal(root, policy).state == "PREPARED_UNCLAIMED"
    with pytest.raises(InvocationTerminalError, match="requires open_claimed"):
        InvocationWriter.open_fresh(root, policy)

    claim_path = root / "control" / "invocation_claimed.v1.json"
    claim_path.write_bytes(claim)
    assert inspect_terminal(root, policy).state == "CLAIMED_PRESTART"
    writer = InvocationWriter.open_claimed(root, policy)
    assert inspect_terminal(root, policy).state == "STARTED_AWAITING_LINEAGE"
    writer.bind_invocation_lineage(_lineage())
    observation = _observation(0)
    writer.record_observation(0, observation)
    writer.commit_opaque_row(
        0,
        observation.observation_sha256,
        b"claimed-row",
    )
    writer.finish_raw()
    wrong_lineage = dataclasses.replace(
        _lineage(),
        invocation_id="f" * 32,
    )
    with pytest.raises(
        InvocationTerminalError,
        match="durable invocation lineage",
    ):
        seal_unit_drained(
            root,
            policy,
            wrong_lineage,
            dataclasses.replace(
                _stop_post(),
                invocation_id="f" * 32,
            ),
            _topology(),
        )
    drained = seal_unit_drained(
        root,
        policy,
        _lineage(),
        _stop_post(),
        _topology(),
    )
    final = observe_unit_final(root, policy, _handoff())
    assert final.unit_drained_sha256 == drained.unit_drained_sha256
    complete = accept_invocation(
        root,
        policy,
        PROBLEM_ACCEPTANCE_SHA256,
    )
    publish_opaque_artifact_bundle(
        root,
        policy,
        complete,
        (
            ("analysis.bin", b"analysis"),
            ("summary.json", b"summary"),
        ),
    )
    assert inspect_terminal(root, policy).state == "CLOSED"
    assert claim_path.read_bytes() == claim
    assert "invocation_claimed.v1.json" in {
        path.name for path in (root / "control").iterdir()
    }


def test_claimed_open_rejects_missing_or_drifted_claim(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    claim = b"claim\n"
    policy = _policy(nonce_claim_sha256=hashlib.sha256(claim).hexdigest())
    with pytest.raises(InvocationTerminalError, match="directories are not empty"):
        InvocationWriter.open_claimed(root, policy)
    (root / "control" / "invocation_claimed.v1.json").write_bytes(b"wrong\n")
    assert inspect_terminal(root, policy).state == "UNKNOWN_INTEGRITY_HOLD"
    with pytest.raises(InvocationTerminalError, match="digest differs"):
        InvocationWriter.open_claimed(root, policy)


def test_prepare_terminal_root_is_exact_and_no_replace(
    tmp_path: Path,
) -> None:
    root = tmp_path / "prepared"
    terminal.prepare_terminal_root(root)
    assert tuple(sorted(path.name for path in root.iterdir())) == (
        "artifacts",
        "control",
        "evidence",
        "raw",
    )
    assert inspect_terminal(root, _policy()).state == "PREPARED"
    with pytest.raises(InvocationTerminalError, match="without repair"):
        terminal.prepare_terminal_root(root)


def test_writer_rejects_gap_digest_type_and_resume(tmp_path: Path) -> None:
    root = _root(tmp_path)
    policy = _policy()
    writer = InvocationWriter.open_fresh(root, policy)
    with pytest.raises(InvocationTerminalError, match="no pending"):
        writer.commit_opaque_row(0, "f" * 64, b"row")
    with pytest.raises(InvocationTerminalError, match="exact next"):
        writer.record_observation(1, _observation(1))

    observation = _observation(0)
    writer.record_observation(0, observation)
    with pytest.raises(InvocationTerminalError, match="exact next"):
        writer.record_observation(0, observation)
    with pytest.raises(InvocationTerminalError, match="digest differs"):
        writer.commit_opaque_row(0, "f" * 64, b"row")
    with pytest.raises(TypeError, match="row_bytes"):
        writer.commit_opaque_row(0, observation.observation_sha256, "row")
    writer.commit_opaque_row(0, observation.observation_sha256, b"row")
    with pytest.raises(InvocationTerminalError, match="exact next"):
        writer.record_observation(2, _observation(2))
    with pytest.raises(InvocationTerminalError, match="exact complete"):
        writer.finish_raw()
    with pytest.raises(InvocationTerminalError, match="canonical"):
        writer.mark_incomplete("not-canonical")

    incomplete = writer.mark_incomplete("WORKER_FAILED")
    assert incomplete.evidence_count == 1
    assert incomplete.row_count == 1
    assert inspect_terminal(root, policy).state == "INCOMPLETE"
    with pytest.raises(InvocationTerminalError, match="closed"):
        writer.record_observation(1, _observation(1))
    with pytest.raises(InvocationTerminalError, match="not empty"):
        InvocationWriter.open_fresh(root, policy)
    with pytest.raises(InvocationTerminalError):
        seal_unit_drained(root, policy, _lineage(), _stop_post(), _topology())


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"expected_rows": 0}, InvocationTerminalError),
        ({"expected_rows": 1_000_001}, InvocationTerminalError),
        ({"artifact_names": ("a", "a")}, InvocationTerminalError),
        ({"artifact_names": ("../a",)}, InvocationTerminalError),
        ({"artifact_names": ["a"]}, TypeError),
    ],
)
def test_policy_rejects_noncanonical_bounds(
    overrides: dict[str, object], error: type[Exception]
) -> None:
    values: dict[str, object] = {
        "authority_sha256": AUTHORITY_SHA256,
        "manifest_sha256": MANIFEST_SHA256,
        "invocation_nonce": NONCE,
        "expected_rows": 1,
        "artifact_names": ("a",),
    }
    values.update(overrides)
    with pytest.raises(error):
        TerminalPolicy(**values)


def test_existing_targets_are_never_overwritten(tmp_path: Path) -> None:
    root = _root(tmp_path)
    policy = _policy(expected_rows=1, artifact_names=("result.bin",))
    writer = InvocationWriter.open_fresh(root, policy)
    observation = _observation(0)
    writer.record_observation(0, observation)
    existing = b"preexisting-row"
    (root / "raw" / "000000.opaque").write_bytes(existing)
    with pytest.raises(FileExistsError):
        writer.commit_opaque_row(0, observation.observation_sha256, b"new-row")
    assert (root / "raw" / "000000.opaque").read_bytes() == existing
    writer.mark_incomplete("PUBLICATION_COLLISION")
    assert inspect_terminal(root, policy).state == "UNKNOWN_INTEGRITY_HOLD"

    other = _root(tmp_path, "other")
    existing_started = b"do-not-overwrite"
    target = other / "control" / "invocation_started.v1.json"
    target.write_bytes(existing_started)
    with pytest.raises(InvocationTerminalError, match="not empty"):
        InvocationWriter.open_fresh(other, policy)
    assert target.read_bytes() == existing_started


def test_link_failure_leaves_no_visible_fact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    policy = _policy(expected_rows=1, artifact_names=("result.bin",))

    def fail_link(*_args: object) -> None:
        raise OSError("injected link failure")

    monkeypatch.setattr(terminal, "_link_tmpfile", fail_link)
    with pytest.raises(OSError, match="injected link failure"):
        InvocationWriter.open_fresh(root, policy)
    assert list((root / "control").iterdir()) == []
    assert inspect_terminal(root, policy).state == "PREPARED"


def test_artifact_contract_and_collisions_fail_closed(tmp_path: Path) -> None:
    root = _root(tmp_path)
    policy = _policy(expected_rows=1)
    complete = _advance_complete(root, policy)
    with pytest.raises(InvocationTerminalError, match="names/order"):
        publish_opaque_artifact_bundle(
            root,
            policy,
            complete,
            (
                ("summary.json", b"summary"),
                ("analysis.bin", b"analysis"),
            ),
        )
    with pytest.raises(TypeError, match="artifact analysis.bin"):
        publish_opaque_artifact_bundle(
            root,
            policy,
            complete,
            (
                ("analysis.bin", "not-bytes"),
                ("summary.json", b"summary"),
            ),
        )
    forged = dataclasses.replace(complete, complete_sha256="f" * 64)
    with pytest.raises(InvocationTerminalError, match="durable COMPLETE"):
        publish_opaque_artifact_bundle(
            root,
            policy,
            forged,
            (
                ("analysis.bin", b"analysis"),
                ("summary.json", b"summary"),
            ),
        )

    final = root / "artifacts" / "final"
    final.mkdir()
    sentinel = final / "sentinel"
    sentinel.write_bytes(b"keep")
    with pytest.raises(InvocationTerminalError, match="not empty"):
        publish_opaque_artifact_bundle(
            root,
            policy,
            complete,
            (
                ("analysis.bin", b"analysis"),
                ("summary.json", b"summary"),
            ),
        )
    assert sentinel.read_bytes() == b"keep"
    assert inspect_terminal(root, policy).state == "UNKNOWN_INTEGRITY_HOLD"

    marker_root = _root(tmp_path, "marker")
    marker_complete = _advance_complete(marker_root, policy)
    marker = marker_root / "control" / "closed.v1.json"
    marker.write_bytes(b"preexisting-marker")
    with pytest.raises(InvocationTerminalError, match="inventory differs"):
        publish_opaque_artifact_bundle(
            marker_root,
            policy,
            marker_complete,
            (
                ("analysis.bin", b"analysis"),
                ("summary.json", b"summary"),
            ),
        )
    assert marker.read_bytes() == b"preexisting-marker"
    assert list((marker_root / "artifacts").iterdir()) == []


def test_artifact_rename_failure_exposes_only_integrity_hold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    policy = _policy(expected_rows=1, artifact_names=("result.bin",))
    complete = _advance_complete(root, policy)

    def fail_rename(*_args: object) -> None:
        raise OSError("injected rename failure")

    monkeypatch.setattr(terminal, "_rename_noreplace", fail_rename)
    with pytest.raises(OSError, match="injected rename failure"):
        publish_opaque_artifact_bundle(
            root, policy, complete, (("result.bin", b"result"),)
        )
    assert not (root / "artifacts" / "final").exists()
    assert not (root / "control" / "closed.v1.json").exists()
    assert [item.name for item in (root / "artifacts").iterdir()] == [
        f".bundle-{NONCE[:16]}"
    ]
    assert inspect_terminal(root, policy).state == "UNKNOWN_INTEGRITY_HOLD"


def test_tampering_and_noncanonical_incomplete_are_integrity_holds(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    policy = _policy(expected_rows=1, artifact_names=("result.bin",))
    complete = _advance_complete(root, policy)
    publish_opaque_artifact_bundle(root, policy, complete, (("result.bin", b"result"),))
    (root / "artifacts" / "final" / "result.bin").write_bytes(b"altered")
    assert inspect_terminal(root, policy).state == "UNKNOWN_INTEGRITY_HOLD"

    other = _root(tmp_path, "other")
    writer = InvocationWriter.open_fresh(other, policy)
    writer.mark_incomplete("WORKER_FAILED")
    incomplete_path = other / "control" / "incomplete.v1.json"
    value = json.loads(incomplete_path.read_bytes())
    value["extra"] = True
    incomplete_path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    assert inspect_terminal(other, policy).state == "UNKNOWN_INTEGRITY_HOLD"


def test_copied_systemd_fact_is_revalidated_from_durable_bytes(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    policy = _policy(expected_rows=1, artifact_names=("result.bin",))
    writer = InvocationWriter.open_fresh(root, policy)
    observation = _observation(0)
    writer.record_observation(0, observation)
    writer.commit_opaque_row(0, observation.observation_sha256, b"row")
    writer.finish_raw()
    seal_unit_drained(root, policy, _lineage(), _stop_post(), _topology())
    path = root / "control" / "unit_drained.v1.json"
    value = json.loads(path.read_bytes())
    value["topology"]["job_cgroups"] = [f"job-0-{NONCE[:16]}"]
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    assert inspect_terminal(root, policy).state == "UNKNOWN_INTEGRITY_HOLD"


def test_boolean_ordinal_and_extra_root_entry_are_rejected(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    policy = _policy(expected_rows=1, artifact_names=("result.bin",))
    extra = root / "unexpected"
    extra.write_bytes(b"extra")
    with pytest.raises(InvocationTerminalError, match="root inventory"):
        InvocationWriter.open_fresh(root, policy)
    extra.unlink()

    writer = InvocationWriter.open_fresh(root, policy)
    observation = _observation(0)
    writer.record_observation(0, observation)
    writer.commit_opaque_row(0, observation.observation_sha256, b"row")
    writer.finish_raw()
    raw_path = root / "control" / "raw_complete.v1.json"
    value = json.loads(raw_path.read_bytes())
    value["row_identities"][0]["job_ordinal"] = False
    raw_path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    assert inspect_terminal(root, policy).state == "UNKNOWN_INTEGRITY_HOLD"


def test_symlink_terminal_directory_is_rejected(tmp_path: Path) -> None:
    root = _root(tmp_path)
    external = tmp_path / "external"
    external.mkdir()
    (root / "control").rmdir()
    os.symlink(external, root / "control")
    with pytest.raises(InvocationTerminalError, match="cannot open terminal"):
        InvocationWriter.open_fresh(root, _policy())

    actual = _root(tmp_path, "actual")
    link = tmp_path / "linked-root"
    os.symlink(actual, link)
    with pytest.raises(InvocationTerminalError, match="symlink path component"):
        inspect_terminal(link, _policy())


def test_module_has_no_problem_owned_import() -> None:
    source_path = Path(terminal.__file__)
    source = source_path.read_text(encoding="utf-8")
    lowered = source.lower()
    assert "warehouse" not in lowered
    assert "cvrp" not in lowered
    assert "alns" not in lowered
    assert "vns" not in lowered
