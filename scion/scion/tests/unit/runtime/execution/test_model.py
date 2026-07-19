from __future__ import annotations

import dataclasses

import pytest

from scion.runtime.execution import model


NONCE = "0123456789abcdef" * 4


def _spec() -> model.GenericProcessSpec:
    return model.GenericProcessSpec.create(
        opaque_job_key="opaque:job/0",
        executable=b"/usr/bin/probe",
        argv=(b"/usr/bin/probe", b"NUL-free-\xff"),
        environment=(b"A=1", b"B=\xff"),
        cwd=b"/tmp",
    )


def _process() -> model.ProcessIdentity:
    return model.ProcessIdentity(
        pid=1201,
        proc_starttime_ticks=700,
        pidfd_device=5,
        pidfd_inode=91,
        creator_pid=1199,
        creator_starttime_ticks=600,
    )


def _wait_exit(code: int = 0) -> model.WaitFact:
    return model.WaitFact.from_native(
        (1201, 1000, 1, code, code << 8, code, 0, 0)
    )


def _events(populated: int, *, extra: bool = False) -> model.CgroupEventsFact:
    suffix = b"future_key 17\n" if extra else b""
    return model.CgroupEventsFact.decode(
        f"populated {populated}\nfrozen 0\n".encode("ascii") + suffix
    )


def _cgroup() -> model.CgroupIdentity:
    key = model.JobCgroupKey.create(ordinal=4, invocation_nonce=NONCE)
    return model.CgroupIdentity(
        service_name="scion-w3@fixture.service",
        supervisor_name="supervisor",
        job_name=key.rendered_name,
        service_device=1,
        service_inode=11,
        supervisor_device=1,
        supervisor_inode=12,
        job_device=1,
        job_inode=13,
        service_relative_lineage=("scion-w3@fixture.service", key.rendered_name),
    )


def _observation() -> model.ClosedSpawnObservation:
    return model.ClosedSpawnObservation.create(
        spec=_spec(),
        start_wall_ns=100,
        end_wall_ns=200,
        start_monotonic_ns=300,
        end_monotonic_ns=400,
        process_identity=_process(),
        wait_fact=_wait_exit(),
        stdout=model.CapturedStream.from_bytes(b"out\x00\xff"),
        stderr=model.CapturedStream.from_bytes(b"err\xfe"),
        cgroup_identity=_cgroup(),
        initial_cgroup_events=_events(0),
        final_cgroup_events=_events(0, extra=True),
    )


def _contained_mapping(
    *,
    phase: model.ContainedSpawnPhase,
    reason: model.ContainedSpawnReason,
    wait_fact: model.WaitFact,
    exec_error: bytes = b"",
    exec_error_stage: int | None = None,
    exec_error_errno: int | None = None,
) -> dict[str, object]:
    spec = _spec()
    return {
        "phase": phase.value,
        "reason": reason.value,
        "opaque_job_key": spec.opaque_job_key,
        "process_spec_sha256": spec.spec_sha256,
        "process_identity": _process().to_mapping(),
        "wait_fact": wait_fact.to_mapping(),
        "cgroup_identity": _cgroup().to_mapping(),
        "initial_cgroup_events": _events(0).to_mapping(),
        "final_cgroup_events": _events(0).to_mapping(),
        "stdout_availability": model.StreamAvailability.COMPLETE.value,
        "stdout": model.CapturedStream.from_bytes(b"").to_mapping(),
        "stderr_availability": model.StreamAvailability.COMPLETE.value,
        "stderr": model.CapturedStream.from_bytes(b"").to_mapping(),
        "exec_error_availability": model.StreamAvailability.COMPLETE.value,
        "exec_error": model.CapturedStream.from_bytes(exec_error).to_mapping(),
        "exec_error_stage": exec_error_stage,
        "exec_error_errno": exec_error_errno,
    }


def _all_public_facts() -> tuple[object, ...]:
    spec = _spec()
    key = model.JobCgroupKey.create(ordinal=4, invocation_nonce=NONCE)
    process = _process()
    wait = _wait_exit()
    stream = model.CapturedStream.from_bytes(b"fact\x00\xff")
    filesystem = model.FilesystemIdentity(device=1, inode=99)
    service = model.ServiceCgroupLineage(
        service_name="scion-w3@fixture.service",
        supervisor_name="supervisor",
        service_device=1,
        service_inode=10,
        supervisor_device=1,
        supervisor_inode=11,
        service_relative_lineage=("scion-w3@fixture.service", "supervisor"),
    )
    cgroup = _cgroup()
    events = _events(0, extra=True)
    observation = _observation()
    backend_failure = model.BackendOpenFailure(
        phase=model.BackendOpenPhase.BACKEND_ALLOCATION,
        reason=model.BackendOpenReason.BACKEND_ALLOCATION_FAILED,
        service_lineage=service,
        capture_directory_acquired=True,
        capture_directory_identity=filesystem,
        errno=None,
    )
    pre_handle_failure = model.PreHandleFailure(
        phase=model.PreHandlePhase.SPEC_VALIDATION,
        reason=model.PreHandleReason.SPEC_INVALID,
        native_called=False,
        native_handle_acquired=False,
        child_creation=model.ChildCreation.NOT_CALLED,
        job_cgroup_created=False,
        job_cgroup_identity=None,
        initial_cgroup_events=None,
        final_cgroup_events=None,
        stdout_availability=model.StreamAvailability.NOT_STARTED,
        stdout=None,
        stderr_availability=model.StreamAvailability.NOT_STARTED,
        stderr=None,
        exec_error_availability=model.StreamAvailability.NOT_STARTED,
        exec_error=None,
    )
    contained_failure = model.ContainedSpawnFailure(
        phase=model.ContainedSpawnPhase.LEADER_REAPED_DRAINING,
        reason=model.ContainedSpawnReason.CAPTURE_FAILED,
        opaque_job_key=spec.opaque_job_key,
        process_spec_sha256=spec.spec_sha256,
        process_identity=process,
        wait_fact=wait,
        cgroup_identity=cgroup,
        initial_cgroup_events=_events(0),
        final_cgroup_events=_events(0),
        stdout_availability=model.StreamAvailability.UNAVAILABLE,
        stdout=None,
        stderr_availability=model.StreamAvailability.COMPLETE,
        stderr=model.CapturedStream.from_bytes(b""),
        exec_error_availability=model.StreamAvailability.COMPLETE,
        exec_error=model.CapturedStream.from_bytes(b""),
        exec_error_stage=None,
        exec_error_errno=None,
    )
    return (
        spec,
        key,
        process,
        wait,
        stream,
        filesystem,
        service,
        cgroup,
        events,
        observation,
        backend_failure,
        pre_handle_failure,
        contained_failure,
    )


@pytest.mark.parametrize(
    "fact",
    _all_public_facts(),
    ids=lambda fact: type(fact).__name__,
)
def test_every_public_immutable_fact_has_an_exact_round_trip(fact: object) -> None:
    fact_type = type(fact)
    assert fact_type.from_mapping(fact.to_mapping()) == fact  # type: ignore[attr-defined]
    assert not hasattr(fact, "__dict__")


def test_generic_process_spec_binds_exact_binary_inputs_and_round_trips() -> None:
    spec = _spec()
    assert spec.executable_sha256
    assert spec.argv_sha256 != spec.environment_sha256
    assert model.GenericProcessSpec.from_mapping(spec.to_mapping()) == spec
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.cwd = b"/changed"  # type: ignore[misc]
    with pytest.raises(TypeError):

        class InvalidSubclass(model.GenericProcessSpec):
            pass


@pytest.mark.parametrize(
    "change",
    [
        {"opaque_job_key": "has space"},
        {"argv": (b"different",)},
        {"environment": (b"B=2", b"A=1")},
        {"environment": (b"A=1", b"A=1")},
        {"environment": (b"A=1", b"A=2")},
        {"cwd": b"relative"},
    ],
)
def test_generic_process_spec_rejects_noncanonical_inputs(change: dict[str, object]) -> None:
    values: dict[str, object] = {
        "opaque_job_key": "job",
        "executable": b"/bin/probe",
        "argv": (b"/bin/probe",),
        "environment": (b"A=1",),
        "cwd": b"/tmp",
    }
    values.update(change)
    with pytest.raises((TypeError, model.ModelValidationError)):
        model.GenericProcessSpec.create(**values)  # type: ignore[arg-type]


def test_strict_mapping_codec_rejects_bool_integer_unknown_and_missing() -> None:
    key = model.JobCgroupKey.create(ordinal=3, invocation_nonce=NONCE)
    encoded = key.to_mapping()
    with pytest.raises(TypeError):
        model.JobCgroupKey.from_mapping({**encoded, "ordinal": True})
    with pytest.raises(model.ModelValidationError):
        model.JobCgroupKey.from_mapping({**encoded, "unknown": 1})
    encoded.pop("key_sha256")
    with pytest.raises(model.ModelValidationError):
        model.JobCgroupKey.from_mapping(encoded)
    pairs = tuple(key.to_mapping().items())
    assert model.JobCgroupKey.from_pairs(pairs) == key
    with pytest.raises(model.ModelValidationError):
        model.JobCgroupKey.from_pairs(pairs + (("ordinal", 3),))


def test_job_cgroup_key_enforces_grammar_bound_and_full_nonce_digest() -> None:
    maximum = model.JobCgroupKey.create(ordinal=(1 << 64) - 1, invocation_nonce=NONCE)
    assert maximum.rendered_name == "job-18446744073709551615-0123456789abcdef"
    assert len(maximum.rendered_name.encode("ascii")) == 41
    assert model.JobCgroupKey.from_rendered(
        rendered_name=maximum.rendered_name, invocation_nonce=NONCE
    ) == maximum
    with pytest.raises(model.ModelValidationError):
        model.JobCgroupKey.create(ordinal=1 << 64, invocation_nonce=NONCE)
    with pytest.raises(model.ModelValidationError):
        model.JobCgroupKey.from_rendered(
            rendered_name="job-01-0123456789abcdef", invocation_nonce=NONCE
        )
    with pytest.raises(model.ModelValidationError):
        model.JobCgroupKey.from_rendered(
            rendered_name="job-1-ffffffffffffffff", invocation_nonce=NONCE
        )


def test_wait_fact_accepts_only_coherent_native_terminal_tuples() -> None:
    assert _wait_exit(19).return_code == 19
    killed = model.WaitFact.from_native((1201, 1000, 2, 9, 9, -9, 9, 0))
    dumped = model.WaitFact.from_native((1201, 1000, 3, 11, 139, -11, 11, 1))
    assert killed.signal == 9 and not killed.core_dumped
    assert dumped.signal == 11 and dumped.core_dumped
    assert model.WaitFact.from_mapping(dumped.to_mapping()) == dumped
    with pytest.raises(TypeError):
        model.WaitFact.from_native((True, 1000, 1, 0, 0, 0, 0, 0))
    with pytest.raises(model.ModelValidationError):
        model.WaitFact.from_native((1201, 1000, 3, 11, 11, -11, 11, 0))


def test_captured_stream_is_exact_binary_and_digest_bound() -> None:
    captured = model.CapturedStream.from_bytes(b"\x00\xffinvalid-utf8")
    assert captured.byte_length == len(captured.data)
    assert model.CapturedStream.from_mapping(captured.to_mapping()) == captured
    with pytest.raises(model.ModelValidationError):
        model.CapturedStream(captured.data, captured.byte_length + 1, captured.sha256)


def test_cgroup_events_retains_unknown_fields_and_rejects_malformed_required_data() -> None:
    fact = _events(0, extra=True)
    assert fact.raw.endswith(b"future_key 17\n")
    assert fact.value("future_key") == 17
    assert model.CgroupEventsFact.from_mapping(fact.to_mapping()) == fact
    for raw in (
        b"populated 0\n",
        b"populated 0\npopulated 0\nfrozen 0\n",
        b"populated 00\nfrozen 0\n",
        b"populated 0 frozen 0\n",
        b"populated 0\nfrozen 0",
        b"populated 0\nfrozen 0\n\xff 1\n",
    ):
        with pytest.raises(model.ModelValidationError):
            model.CgroupEventsFact.decode(raw)


def test_cgroup_identity_is_copied_lineage_without_path_or_fd() -> None:
    identity = _cgroup()
    assert model.CgroupIdentity.from_mapping(identity.to_mapping()) == identity
    assert all("fd" not in field.name and "path" not in field.name for field in dataclasses.fields(identity))
    with pytest.raises(model.ModelValidationError):
        model.CgroupIdentity(
            **{**identity.to_mapping(), "job_name": "../replacement"}  # type: ignore[arg-type]
        )
    with pytest.raises(model.ModelValidationError):
        model.CgroupIdentity(
            **{
                **identity.to_mapping(),
                "service_relative_lineage": (
                    identity.service_name,
                    "unexpected",
                    identity.job_name,
                ),
            }  # type: ignore[arg-type]
        )
    with pytest.raises(model.ModelValidationError):
        model.CgroupIdentity(
            **{
                **identity.to_mapping(),
                "job_name": "job-18446744073709551616-0123456789abcdef",
            }  # type: ignore[arg-type]
        )


def test_closed_observation_is_positive_only_after_complete_empty_settlement() -> None:
    observation = _observation()
    assert observation.leader_outcome is model.LeaderOutcome.ZERO
    assert len(observation.observation_sha256) == 64
    assert model.ClosedSpawnObservation.from_mapping(observation.to_mapping()) == observation
    forbidden = ("fd", "path", "callback", "cleanup", "handle", "warehouse", "protocol")
    assert all(
        not any(token in field.name.lower() for token in forbidden)
        for field in dataclasses.fields(observation)
    )
    with pytest.raises(model.ModelValidationError):
        model.ClosedSpawnObservation(
            **{
                **observation.to_mapping(),
                "final_cgroup_events": _events(1),
                "process_identity": observation.process_identity,
                "wait_fact": observation.wait_fact,
                "stdout": observation.stdout,
                "stderr": observation.stderr,
                "cgroup_identity": observation.cgroup_identity,
                "initial_cgroup_events": observation.initial_cgroup_events,
                "leader_outcome": observation.leader_outcome,
            }  # type: ignore[arg-type]
        )


def _service_lineage() -> model.ServiceCgroupLineage:
    return model.ServiceCgroupLineage(
        service_name="scion-w3@fixture.service",
        supervisor_name="supervisor",
        service_device=1,
        service_inode=10,
        supervisor_device=1,
        supervisor_inode=11,
        service_relative_lineage=("scion-w3@fixture.service", "supervisor"),
    )


def test_backend_open_failure_requires_capture_identity_and_reason_specific_errno() -> None:
    failure = model.BackendOpenFailure(
        phase=model.BackendOpenPhase.CAPTURE_DIRECTORY_ACQUIRE,
        reason=model.BackendOpenReason.CAPTURE_DIRECTORY_OPEN_FAILED,
        service_lineage=_service_lineage(),
        capture_directory_acquired=False,
        capture_directory_identity=None,
        errno=13,
    )
    assert model.BackendOpenFailure.from_mapping(failure.to_mapping()) == failure
    with pytest.raises(model.ModelValidationError):
        model.BackendOpenFailure(
            phase=model.BackendOpenPhase.BACKEND_ALLOCATION,
            reason=model.BackendOpenReason.BACKEND_ALLOCATION_FAILED,
            service_lineage=_service_lineage(),
            capture_directory_acquired=True,
            capture_directory_identity=None,
            errno=None,
        )
    with pytest.raises(model.ModelValidationError):
        model.BackendOpenFailure(
            phase=model.BackendOpenPhase.SERVICE_CONSUME,
            reason=model.BackendOpenReason.CAPTURE_DIRECTORY_OPEN_FAILED,
            service_lineage=_service_lineage(),
            capture_directory_acquired=False,
            capture_directory_identity=None,
            errno=13,
        )


def test_pre_handle_failure_has_no_process_or_started_stream_fact() -> None:
    failure = model.PreHandleFailure(
        phase=model.PreHandlePhase.SPEC_VALIDATION,
        reason=model.PreHandleReason.SPEC_INVALID,
        native_called=False,
        native_handle_acquired=False,
        child_creation=model.ChildCreation.NOT_CALLED,
        job_cgroup_created=False,
        job_cgroup_identity=None,
        initial_cgroup_events=None,
        final_cgroup_events=None,
        stdout_availability=model.StreamAvailability.NOT_STARTED,
        stdout=None,
        stderr_availability=model.StreamAvailability.NOT_STARTED,
        stderr=None,
        exec_error_availability=model.StreamAvailability.NOT_STARTED,
        exec_error=None,
    )
    assert model.PreHandleFailure.from_mapping(failure.to_mapping()) == failure
    assert all("process" not in field.name and "wait" not in field.name for field in dataclasses.fields(failure))
    with pytest.raises(model.ModelValidationError):
        model.PreHandleFailure(
            **{
                **failure.to_mapping(),
                "stdout_availability": model.StreamAvailability.COMPLETE,
                "stdout": model.CapturedStream.from_bytes(b""),
                "phase": failure.phase,
                "reason": failure.reason,
                "child_creation": failure.child_creation,
                "stderr_availability": failure.stderr_availability,
                "exec_error_availability": failure.exec_error_availability,
            }  # type: ignore[arg-type]
        )


def test_pre_handle_interruption_can_record_native_no_handle_window() -> None:
    failure = model.PreHandleFailure(
        phase=model.PreHandlePhase.NATIVE_NO_HANDLE,
        reason=model.PreHandleReason.ISSUER_INTERRUPTED_PRE_HANDLE,
        native_called=True,
        native_handle_acquired=False,
        child_creation=model.ChildCreation.NATIVE_INTERNAL_SETTLED,
        job_cgroup_created=True,
        job_cgroup_identity=_cgroup(),
        initial_cgroup_events=_events(0),
        final_cgroup_events=_events(0),
        stdout_availability=model.StreamAvailability.NOT_STARTED,
        stdout=None,
        stderr_availability=model.StreamAvailability.NOT_STARTED,
        stderr=None,
        exec_error_availability=model.StreamAvailability.NOT_STARTED,
        exec_error=None,
    )
    assert model.PreHandleFailure.from_mapping(failure.to_mapping()) == failure
    with pytest.raises(model.ModelValidationError):
        model.PreHandleFailure(
            **{
                **failure.to_mapping(),
                "phase": model.PreHandlePhase.SPEC_VALIDATION,
                "reason": model.PreHandleReason.JOB_CREATE_FAILED,
                "child_creation": failure.child_creation,
                "stdout_availability": failure.stdout_availability,
                "stderr_availability": failure.stderr_availability,
                "exec_error_availability": failure.exec_error_availability,
                "job_cgroup_identity": failure.job_cgroup_identity,
                "initial_cgroup_events": failure.initial_cgroup_events,
                "final_cgroup_events": failure.final_cgroup_events,
            }  # type: ignore[arg-type]
        )


def test_contained_failure_requires_reap_empty_and_complete_exec_record() -> None:
    exec_record = b"SCXE" + bytes((1, 13, 0, 0)) + (2).to_bytes(4, "little")
    exec_error = model.CapturedStream.from_bytes(exec_record)
    failure = model.ContainedSpawnFailure(
        phase=model.ContainedSpawnPhase.LEADER_REAPED_DRAINING,
        reason=model.ContainedSpawnReason.EXEC_FAILED,
        opaque_job_key="job",
        process_spec_sha256=_spec().spec_sha256,
        process_identity=_process(),
        wait_fact=_wait_exit(127),
        cgroup_identity=_cgroup(),
        initial_cgroup_events=_events(0),
        final_cgroup_events=_events(0),
        stdout_availability=model.StreamAvailability.COMPLETE,
        stdout=model.CapturedStream.from_bytes(b""),
        stderr_availability=model.StreamAvailability.COMPLETE,
        stderr=model.CapturedStream.from_bytes(b""),
        exec_error_availability=model.StreamAvailability.COMPLETE,
        exec_error=exec_error,
        exec_error_stage=13,
        exec_error_errno=2,
    )
    assert model.ContainedSpawnFailure.from_mapping(failure.to_mapping()) == failure
    with pytest.raises(model.ModelValidationError):
        model.ContainedSpawnFailure(
            **{
                **failure.to_mapping(),
                "phase": model.ContainedSpawnPhase.BLOCKED,
                "reason": failure.reason,
                "process_identity": failure.process_identity,
                "wait_fact": failure.wait_fact,
                "cgroup_identity": failure.cgroup_identity,
                "initial_cgroup_events": failure.initial_cgroup_events,
                "final_cgroup_events": failure.final_cgroup_events,
                "stdout_availability": failure.stdout_availability,
                "stderr_availability": failure.stderr_availability,
                "exec_error_availability": failure.exec_error_availability,
                "stdout": failure.stdout,
                "stderr": failure.stderr,
                "exec_error": failure.exec_error,
            }  # type: ignore[arg-type]
        )
    release_record = b"SCXE" + bytes((1, 9, 0, 0)) + (32).to_bytes(4, "little")
    release_uncertain = model.ContainedSpawnFailure(
        **{
            **failure.to_mapping(),
            "phase": model.ContainedSpawnPhase.RELEASED_DRAINING,
            "reason": model.ContainedSpawnReason.RELEASE_UNCERTAIN,
            "process_identity": failure.process_identity,
            "wait_fact": failure.wait_fact,
            "cgroup_identity": failure.cgroup_identity,
            "initial_cgroup_events": failure.initial_cgroup_events,
            "final_cgroup_events": failure.final_cgroup_events,
            "stdout_availability": failure.stdout_availability,
            "stderr_availability": failure.stderr_availability,
            "exec_error_availability": failure.exec_error_availability,
            "stdout": failure.stdout,
            "stderr": failure.stderr,
            "exec_error": model.CapturedStream.from_bytes(release_record),
            "exec_error_stage": 9,
            "exec_error_errno": 32,
        }  # type: ignore[arg-type]
    )
    assert release_uncertain.exec_error_stage == 9
    with pytest.raises(model.ModelValidationError):
        model.ContainedSpawnFailure(
            **{
                **failure.to_mapping(),
                "phase": failure.phase,
                "reason": failure.reason,
                "process_identity": failure.process_identity,
                "wait_fact": failure.wait_fact,
                "cgroup_identity": failure.cgroup_identity,
                "initial_cgroup_events": failure.initial_cgroup_events,
                "final_cgroup_events": failure.final_cgroup_events,
                "stdout_availability": failure.stdout_availability,
                "stderr_availability": failure.stderr_availability,
                "exec_error_availability": failure.exec_error_availability,
                "stdout": failure.stdout,
                "stderr": failure.stderr,
                "exec_error": model.CapturedStream.from_bytes(b""),
                "exec_error_stage": None,
                "exec_error_errno": None,
            }  # type: ignore[arg-type]
        )
    with pytest.raises(model.ModelValidationError):
        model.ContainedSpawnFailure(
            **{
                **failure.to_mapping(),
                "phase": failure.phase,
                "reason": failure.reason,
                "process_identity": failure.process_identity,
                "wait_fact": _wait_exit(126),
                "cgroup_identity": failure.cgroup_identity,
                "initial_cgroup_events": failure.initial_cgroup_events,
                "final_cgroup_events": failure.final_cgroup_events,
                "stdout_availability": failure.stdout_availability,
                "stderr_availability": failure.stderr_availability,
                "exec_error_availability": failure.exec_error_availability,
                "stdout": failure.stdout,
                "stderr": failure.stderr,
                "exec_error": failure.exec_error,
            }  # type: ignore[arg-type]
        )
    with pytest.raises(model.ModelValidationError):
        model.ContainedSpawnFailure(
            **{
                **failure.to_mapping(),
                "phase": failure.phase,
                "reason": failure.reason,
                "process_identity": failure.process_identity,
                "wait_fact": failure.wait_fact,
                "cgroup_identity": failure.cgroup_identity,
                "initial_cgroup_events": failure.initial_cgroup_events,
                "final_cgroup_events": failure.final_cgroup_events,
                "stdout_availability": model.StreamAvailability.NOT_STARTED,
                "stderr_availability": failure.stderr_availability,
                "exec_error_availability": failure.exec_error_availability,
                "stderr": failure.stderr,
                "exec_error": failure.exec_error,
            }  # type: ignore[arg-type]
        )
    for malformed in (
        b"BAD!" + exec_record[4:],
        exec_record[:4] + bytes((2,)) + exec_record[5:],
        exec_record[:5] + bytes((0,)) + exec_record[6:],
        exec_record[:6] + b"\x01\x00" + exec_record[8:],
        exec_record[:8] + b"\x00\x00\x00\x00",
    ):
        with pytest.raises(model.ModelValidationError):
            model.ContainedSpawnFailure(
                **{
                    **failure.to_mapping(),
                    "phase": failure.phase,
                    "reason": failure.reason,
                    "process_identity": failure.process_identity,
                    "wait_fact": failure.wait_fact,
                    "cgroup_identity": failure.cgroup_identity,
                    "initial_cgroup_events": failure.initial_cgroup_events,
                    "final_cgroup_events": failure.final_cgroup_events,
                    "stdout_availability": failure.stdout_availability,
                    "stderr_availability": failure.stderr_availability,
                    "exec_error_availability": failure.exec_error_availability,
                    "stdout": failure.stdout,
                    "stderr": failure.stderr,
                    "exec_error": model.CapturedStream.from_bytes(malformed),
                }  # type: ignore[arg-type]
            )


def test_unavailable_streams_are_exact_for_capture_or_issuer_failure() -> None:
    base = {
        "phase": model.ContainedSpawnPhase.LEADER_REAPED_DRAINING,
        "reason": model.ContainedSpawnReason.CAPTURE_FAILED,
        "opaque_job_key": "job",
        "process_spec_sha256": _spec().spec_sha256,
        "process_identity": _process(),
        "wait_fact": _wait_exit(),
        "cgroup_identity": _cgroup(),
        "initial_cgroup_events": _events(0),
        "final_cgroup_events": _events(0),
        "stdout_availability": model.StreamAvailability.UNAVAILABLE,
        "stdout": None,
        "stderr_availability": model.StreamAvailability.COMPLETE,
        "stderr": model.CapturedStream.from_bytes(b"err"),
        "exec_error_availability": model.StreamAvailability.COMPLETE,
        "exec_error": model.CapturedStream.from_bytes(b""),
        "exec_error_stage": None,
        "exec_error_errno": None,
    }
    failure = model.ContainedSpawnFailure(**base)
    assert failure.stdout is None
    interrupted = model.ContainedSpawnFailure(
        **{
            **base,
            "reason": model.ContainedSpawnReason.ISSUER_INTERRUPTED,
        }
    )
    assert interrupted.stdout_availability is model.StreamAvailability.UNAVAILABLE
    with pytest.raises(model.ModelValidationError):
        model.ContainedSpawnFailure(
            **{
                **base,
                "reason": model.ContainedSpawnReason.ISSUER_INTERRUPTED,
                "exec_error_availability": model.StreamAvailability.UNAVAILABLE,
                "exec_error": None,
            }
        )
    release_first = model.ContainedSpawnFailure(
        **{
            **base,
            "phase": model.ContainedSpawnPhase.RELEASED_DRAINING,
            "reason": model.ContainedSpawnReason.RELEASE_UNCERTAIN,
        }
    )
    assert release_first.stdout_availability is model.StreamAvailability.UNAVAILABLE
    active_first = model.ContainedSpawnFailure(
        **{
            **base,
            "phase": model.ContainedSpawnPhase.BLOCKED,
            "reason": model.ContainedSpawnReason.ACTIVE_NOT_DURABLE,
        }
    )
    assert active_first.stdout is None
    with pytest.raises(model.ModelValidationError):
        model.ContainedSpawnFailure(
            **{
                **base,
                "stdout_availability": model.StreamAvailability.COMPLETE,
                "stdout": model.CapturedStream.from_bytes(b""),
            }
        )


def test_contained_reason_phase_checks_only_contract_deducible_first_states() -> None:
    captured_failure = next(
        fact
        for fact in _all_public_facts()
        if type(fact) is model.ContainedSpawnFailure
    )
    encoded = captured_failure.to_mapping()
    complete_empty = model.CapturedStream.from_bytes(b"").to_mapping()
    encoded = {
        **encoded,
        "stdout_availability": model.StreamAvailability.COMPLETE.value,
        "stdout": complete_empty,
    }
    active = {
        **encoded,
        "phase": model.ContainedSpawnPhase.BLOCKED.value,
        "reason": model.ContainedSpawnReason.ACTIVE_NOT_DURABLE.value,
    }
    assert model.ContainedSpawnFailure.from_mapping(active).phase is model.ContainedSpawnPhase.BLOCKED
    with pytest.raises(model.ModelValidationError):
        model.ContainedSpawnFailure.from_mapping(
            {**active, "phase": model.ContainedSpawnPhase.RELEASED_DRAINING.value}
        )
    descendant = {
        **encoded,
        "phase": model.ContainedSpawnPhase.LEADER_TERMINAL.value,
        "reason": model.ContainedSpawnReason.DESCENDANT_SURVIVED.value,
    }
    assert (
        model.ContainedSpawnFailure.from_mapping(descendant).phase
        is model.ContainedSpawnPhase.LEADER_TERMINAL
    )
    with pytest.raises(model.ModelValidationError):
        model.ContainedSpawnFailure.from_mapping(
            {**descendant, "phase": model.ContainedSpawnPhase.BLOCKED.value}
        )


def test_release_uncertain_has_one_exact_first_failure_phase() -> None:
    release_record = b"SCXE" + bytes((1, 9, 0, 0)) + (32).to_bytes(4, "little")
    base = _contained_mapping(
        phase=model.ContainedSpawnPhase.RELEASED_DRAINING,
        reason=model.ContainedSpawnReason.RELEASE_UNCERTAIN,
        wait_fact=_wait_exit(127),
        exec_error=release_record,
        exec_error_stage=9,
        exec_error_errno=32,
    )
    for phase in model.ContainedSpawnPhase:
        candidate = {**base, "phase": phase.value}
        if phase is model.ContainedSpawnPhase.RELEASED_DRAINING:
            decoded = model.ContainedSpawnFailure.from_mapping(candidate)
            assert decoded.exec_error_stage == 9
        else:
            with pytest.raises(model.ModelValidationError):
                model.ContainedSpawnFailure.from_mapping(candidate)


def test_exec_error_record_is_legal_only_in_exact_post_release_phases() -> None:
    record = b"SCXE" + bytes((1, 13, 0, 0)) + (2).to_bytes(4, "little")
    allowed = {
        model.ContainedSpawnPhase.RELEASED_DRAINING,
        model.ContainedSpawnPhase.LEADER_TERMINAL,
        model.ContainedSpawnPhase.LEADER_REAPED_DRAINING,
        model.ContainedSpawnPhase.SETTLING_DESCENDANTS,
    }
    for phase in model.ContainedSpawnPhase:
        candidate = _contained_mapping(
            phase=phase,
            reason=model.ContainedSpawnReason.ISSUER_INTERRUPTED,
            wait_fact=_wait_exit(127),
            exec_error=record,
            exec_error_stage=13,
            exec_error_errno=2,
        )
        if phase in allowed:
            assert model.ContainedSpawnFailure.from_mapping(candidate).phase is phase
        else:
            with pytest.raises(model.ModelValidationError):
                model.ContainedSpawnFailure.from_mapping(candidate)


def test_active_not_durable_requires_clean_exec_error_eof_for_every_phase() -> None:
    record = b"SCXE" + bytes((1, 13, 0, 0)) + (2).to_bytes(4, "little")
    clean = _contained_mapping(
        phase=model.ContainedSpawnPhase.BLOCKED,
        reason=model.ContainedSpawnReason.ACTIVE_NOT_DURABLE,
        wait_fact=_wait_exit(),
    )
    assert (
        model.ContainedSpawnFailure.from_mapping(clean).phase
        is model.ContainedSpawnPhase.BLOCKED
    )
    for phase in model.ContainedSpawnPhase:
        with pytest.raises(model.ModelValidationError):
            model.ContainedSpawnFailure.from_mapping(
                _contained_mapping(
                    phase=phase,
                    reason=model.ContainedSpawnReason.ACTIVE_NOT_DURABLE,
                    wait_fact=_wait_exit(127),
                    exec_error=record,
                    exec_error_stage=13,
                    exec_error_errno=2,
                )
            )


def test_cleanup_permit_identity_is_private_immutable_and_exactly_bound() -> None:
    key = model.JobCgroupKey.create(ordinal=4, invocation_nonce=NONCE)
    identity = model._CleanupPermitIdentity(  # noqa: SLF001
        backend_generation=9,
        job_key=key,
        observation_sha256=_observation().observation_sha256,
    )
    assert model._CleanupPermitIdentity.from_mapping(identity.to_mapping()) == identity  # noqa: SLF001
    assert not hasattr(identity, "__dict__")
    with pytest.raises(dataclasses.FrozenInstanceError):
        identity.backend_generation = 10  # type: ignore[misc]
    assert "_CleanupPermitIdentity" not in model.__all__
    assert not hasattr(model, "_SettledJobCleanupPermit")
    assert not hasattr(model, "_issue_cleanup_permit_for_tests")
