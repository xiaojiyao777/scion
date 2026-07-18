from __future__ import annotations

import copy
import gc
import json
import os
import pickle
import threading
from pathlib import Path

import pytest

import scion.fresh_activation.source_snapshot as subject


def _acquire(
    root: Path | str,
    target: str = "state/campaign.sqlite",
) -> subject.StagingCapability:
    return subject.acquire_staging_capability(
        campaign_root=str(root),
        target_relative_path=target,
        cutover_id="cutover-1",
        policy_generation="fresh-policy-v1",
        schema_generation="owner-schema-v1",
        writer_generation="writer-v1",
    )


def _consume_and_abort(
    capability: subject.StagingCapability,
) -> subject._ConsumedStagingAuthority:
    authority = subject._consume_staging_capability(capability)
    subject._abort_staging_authority(authority)
    return authority


def test_stable_absence_pins_root_ancestors_parent_and_exact_names(
    tmp_path: Path,
) -> None:
    root = tmp_path / "campaign"
    parent = root / "nested" / "state"
    parent.mkdir(parents=True)

    capability = _acquire(root, "nested/state/campaign.sqlite")
    state = subject._lookup_staging_capability(capability)

    assert state.authority.target_basename == "campaign.sqlite"
    assert state.authority.parent_parts == ("nested", "state")
    assert len(state.authority.descriptors) == 3
    assert (
        state.authority.parent_identity.device,
        state.authority.parent_identity.inode,
    ) == (parent.stat().st_dev, parent.stat().st_ino)
    assert state.authority.parent_identity.mount_id > 0
    assert state.authority.absence_observation is not None
    assert not (parent / "campaign.sqlite").exists()
    assert all(
        not (parent / f"campaign.sqlite{suffix}").exists()
        for suffix in subject._SIDECAR_SUFFIXES
    )
    assert not (parent / state.authority.staging_basename).exists()

    _consume_and_abort(capability)


@pytest.mark.parametrize("payload", [b"", b"legacy-owner-state", b"SQLite format 3\x00"])
def test_every_present_target_is_a_hold_and_is_never_opened(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
) -> None:
    root = tmp_path / "campaign"
    parent = root / "state"
    parent.mkdir(parents=True)
    target = parent / "campaign.sqlite"
    target.write_bytes(payload)
    opened: list[object] = []
    real_open = subject.os.open

    def recording_open(path: object, *args: object, **kwargs: object) -> int:
        opened.append(path)
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(subject.os, "open", recording_open)
    monkeypatch.setattr(subject, "_require_linux_primitives", lambda: None)
    with pytest.raises(subject.FreshActivationHoldError) as caught:
        _acquire(root)

    assert caught.value.reason_code == "existing_target_hold"
    assert "campaign.sqlite" not in opened
    assert target.read_bytes() == payload


@pytest.mark.parametrize("suffix", subject._SIDECAR_SUFFIXES)
def test_any_present_sqlite_sidecar_is_a_hold(tmp_path: Path, suffix: str) -> None:
    root = tmp_path / "campaign"
    parent = root / "state"
    parent.mkdir(parents=True)
    (parent / f"campaign.sqlite{suffix}").write_bytes(b"preserve")

    with pytest.raises(subject.FreshActivationHoldError) as caught:
        _acquire(root)

    assert caught.value.reason_code == "existing_sidecar_hold"
    assert (parent / f"campaign.sqlite{suffix}").read_bytes() == b"preserve"


def test_target_symlink_is_a_hold_and_is_not_followed(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    parent = root / "state"
    parent.mkdir(parents=True)
    outside = tmp_path / "outside.sqlite"
    outside.write_bytes(b"outside")
    (parent / "campaign.sqlite").symlink_to(outside)

    with pytest.raises(subject.FreshActivationHoldError) as caught:
        _acquire(root)

    assert caught.value.reason_code == "existing_target_hold"
    assert outside.read_bytes() == b"outside"


@pytest.mark.parametrize("at_root", [False, True])
def test_root_or_ancestor_symlink_is_rejected(
    tmp_path: Path,
    at_root: bool,
) -> None:
    real_root = tmp_path / "real"
    (real_root / "state").mkdir(parents=True)
    if at_root:
        root = tmp_path / "campaign"
        root.symlink_to(real_root, target_is_directory=True)
        target = "state/campaign.sqlite"
    else:
        root = tmp_path / "campaign"
        root.mkdir()
        (root / "state").symlink_to(real_root / "state", target_is_directory=True)
        target = "state/campaign.sqlite"

    with pytest.raises(subject.FreshActivationHoldError) as caught:
        _acquire(root, target)

    assert caught.value.reason_code == "ancestor_unavailable_or_unsafe"


def test_non_directory_ancestor_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    root.mkdir()
    (root / "state").write_bytes(b"not-a-directory")

    with pytest.raises(subject.FreshActivationHoldError) as caught:
        _acquire(root)

    assert caught.value.reason_code == "ancestor_unavailable_or_unsafe"


def test_initializer_lock_is_exclusive_for_the_pinned_directory(
    tmp_path: Path,
) -> None:
    root = tmp_path / "campaign"
    (root / "state").mkdir(parents=True)
    first = _acquire(root)

    with pytest.raises(subject.FreshActivationHoldError) as caught:
        _acquire(root, "state/another.sqlite")

    assert caught.value.reason_code == "initializer_lock_unavailable"
    _consume_and_abort(first)

    replacement = _acquire(root, "state/another.sqlite")
    _consume_and_abort(replacement)


def test_staging_name_collision_is_a_terminal_hold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "campaign"
    parent = root / "state"
    parent.mkdir(parents=True)
    collision = ".fixed.scion-staging"
    (parent / collision).write_bytes(b"preserve")
    monkeypatch.setattr(subject, "_new_staging_basename", lambda _cutover: collision)

    with pytest.raises(subject.FreshActivationHoldError) as caught:
        _acquire(root)

    assert caught.value.reason_code == "staging_collision_hold"
    assert (parent / collision).read_bytes() == b"preserve"


def test_target_created_between_absence_observations_yields_no_capability(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "campaign"
    parent = root / "state"
    parent.mkdir(parents=True)
    target = parent / "campaign.sqlite"
    real_check = subject._assert_target_bundle_absent
    calls = 0

    def racing_check(authority: subject._PinnedAuthority) -> None:
        nonlocal calls
        real_check(authority)
        calls += 1
        if calls == 1:
            target.write_bytes(b"competitor")

    monkeypatch.setattr(subject, "_assert_target_bundle_absent", racing_check)
    with pytest.raises(subject.FreshActivationHoldError) as caught:
        _acquire(root)

    assert caught.value.reason_code == "existing_target_hold"
    assert target.read_bytes() == b"competitor"

    # The failed acquisition released the directory lock; it did not retry.
    target.unlink()
    monkeypatch.setattr(subject, "_assert_target_bundle_absent", real_check)
    capability = _acquire(root)
    _consume_and_abort(capability)


def test_parent_replacement_spends_staging_capability_and_fails_closed(
    tmp_path: Path,
) -> None:
    root = tmp_path / "campaign"
    parent = root / "state"
    parent.mkdir(parents=True)
    capability = _acquire(root)
    parent.rename(root / "old-state")
    parent.mkdir()

    with pytest.raises(subject.FreshActivationHoldError) as caught:
        subject._consume_staging_capability(capability)
    assert caught.value.reason_code == "directory_identity_drift"
    with pytest.raises(subject.FreshActivationLifecycleError, match="already spent"):
        subject._consume_staging_capability(capability)


def test_capabilities_are_sealed_uncopyable_unpickleable_and_one_shot(
    tmp_path: Path,
) -> None:
    root = tmp_path / "campaign"
    (root / "state").mkdir(parents=True)
    capability = _acquire(root)

    with pytest.raises(subject.InvalidFreshActivationCapabilityError):
        subject.StagingCapability()
    with pytest.raises(TypeError, match="sealed"):
        type("Forged", (subject.StagingCapability,), {})
    with pytest.raises(subject.InvalidFreshActivationCapabilityError):
        copy.copy(capability)
    with pytest.raises(subject.InvalidFreshActivationCapabilityError):
        copy.deepcopy(capability)
    with pytest.raises(subject.InvalidFreshActivationCapabilityError):
        pickle.dumps(capability)
    with pytest.raises(TypeError):
        json.dumps(capability)

    authority = subject._consume_staging_capability(capability)
    with pytest.raises(subject.FreshActivationLifecycleError, match="already spent"):
        subject._consume_staging_capability(capability)
    subject._abort_staging_authority(authority)

    forged = object.__new__(subject.StagingCapability)
    with pytest.raises(subject.InvalidFreshActivationCapabilityError):
        subject._consume_staging_capability(forged)


def test_capability_finalizer_releases_directory_lock(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    (root / "state").mkdir(parents=True)
    capability = _acquire(root)
    del capability
    gc.collect()

    replacement = _acquire(root)
    _consume_and_abort(replacement)


def test_two_threads_can_consume_staging_capability_only_once(
    tmp_path: Path,
) -> None:
    root = tmp_path / "campaign"
    (root / "state").mkdir(parents=True)
    capability = _acquire(root)
    barrier = threading.Barrier(3)
    outcomes: list[str] = []
    authorities: list[subject._ConsumedStagingAuthority] = []

    def consume() -> None:
        barrier.wait()
        try:
            authority = subject._consume_staging_capability(capability)
        except subject.FreshActivationLifecycleError:
            outcomes.append("spent")
        else:
            authorities.append(authority)
            outcomes.append("consumed")

    threads = [threading.Thread(target=consume) for _ in range(2)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()

    assert sorted(outcomes) == ["consumed", "spent"]
    assert len(authorities) == 1
    subject._abort_staging_authority(authorities[0])


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires real Linux fork")
def test_fork_child_cannot_consume_or_abort_and_cannot_unlock_parent(
    tmp_path: Path,
) -> None:
    root = tmp_path / "campaign"
    (root / "cap-state").mkdir(parents=True)
    (root / "authority-state").mkdir()
    capability = _acquire(root, "cap-state/campaign.sqlite")
    consumed = subject._consume_staging_capability(
        _acquire(root, "authority-state/campaign.sqlite")
    )
    capability_fds = tuple(
        subject._lookup_staging_capability(capability).authority.descriptors
    )
    authority_fds = tuple(
        subject._lookup_staging_authority(consumed).authority.descriptors
    )

    child_pid = os.fork()
    if child_pid == 0:
        exit_code = 0
        try:
            subject._consume_staging_capability(capability)
        except subject.FreshActivationLifecycleError:
            pass
        else:
            exit_code = 11
        try:
            subject._abort_staging_authority(consumed)
        except subject.FreshActivationLifecycleError:
            pass
        else:
            exit_code = 12
        del capability
        del consumed
        gc.collect()
        for descriptor in (*capability_fds, *authority_fds):
            try:
                os.fstat(descriptor)
            except OSError:
                continue
            exit_code = 13
        os._exit(exit_code)

    _, status = os.waitpid(child_pid, 0)
    assert os.waitstatus_to_exitcode(status) == 0

    for target in (
        "cap-state/another.sqlite",
        "authority-state/another.sqlite",
    ):
        with pytest.raises(subject.FreshActivationHoldError) as caught:
            _acquire(root, target)
        assert caught.value.reason_code == "initializer_lock_unavailable"

    _consume_and_abort(capability)
    subject._abort_staging_authority(consumed)
    for target in (
        "cap-state/another.sqlite",
        "authority-state/another.sqlite",
    ):
        replacement = _acquire(root, target)
        _consume_and_abort(replacement)


def test_mount_identity_drift_spends_capability_and_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "campaign"
    (root / "state").mkdir(parents=True)
    capability = _acquire(root)
    real_mount_id = subject._mount_id
    monkeypatch.setattr(
        subject,
        "_mount_id",
        lambda descriptor: real_mount_id(descriptor) + 1,
    )

    with pytest.raises(subject.FreshActivationHoldError) as caught:
        subject._consume_staging_capability(capability)
    assert caught.value.reason_code == "directory_identity_drift"
    with pytest.raises(subject.FreshActivationLifecycleError, match="already spent"):
        subject._consume_staging_capability(capability)


def test_missing_mount_identity_has_no_fallback_and_releases_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "campaign"
    (root / "state").mkdir(parents=True)
    real_mount_id = subject._mount_id

    def unavailable(_descriptor: int) -> int:
        raise subject.FreshActivationHoldError(
            "mount_identity_unavailable",
            "missing",
        )

    monkeypatch.setattr(subject, "_mount_id", unavailable)
    with pytest.raises(subject.FreshActivationHoldError) as caught:
        _acquire(root)
    assert caught.value.reason_code == "mount_identity_unavailable"

    monkeypatch.setattr(subject, "_mount_id", real_mount_id)
    capability = _acquire(root)
    _consume_and_abort(capability)


def test_publication_permit_is_only_an_unissuable_sealed_placeholder() -> None:
    for payload in (None, b"bytes", "a" * 64, 12345):
        with pytest.raises(subject.InvalidFreshActivationCapabilityError):
            subject.PublicationPermit(payload)
    with pytest.raises(TypeError, match="sealed"):
        type("ForgedPermit", (subject.PublicationPermit,), {})
    inert_forgery = object.__new__(subject.PublicationPermit)
    for operation in (copy.copy, copy.deepcopy, pickle.dumps):
        with pytest.raises(subject.InvalidFreshActivationCapabilityError):
            operation(inert_forgery)
    with pytest.raises(TypeError):
        json.dumps(inert_forgery)
    assert not hasattr(subject, "_issue_publication_permit")
    assert not hasattr(subject, "_issue_test_publication_permit")
    assert not hasattr(subject, "_consume_publication_permit")
    assert not hasattr(subject, "_PUBLICATION_PERMIT_STATES")


def test_missing_linux_primitive_has_no_fallback_or_filesystem_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "campaign"
    (root / "state").mkdir(parents=True)
    opened = False

    def unsupported() -> None:
        raise subject.FreshActivationHoldError(
            "required_linux_primitive_unavailable",
            "unsupported",
        )

    def forbidden_open(*_args: object, **_kwargs: object) -> int:
        nonlocal opened
        opened = True
        raise AssertionError("fallback path attempted filesystem access")

    monkeypatch.setattr(subject, "_require_linux_primitives", unsupported)
    monkeypatch.setattr(subject.os, "open", forbidden_open)
    with pytest.raises(subject.FreshActivationHoldError) as caught:
        _acquire(root)

    assert caught.value.reason_code == "required_linux_primitive_unavailable"
    assert not opened


@pytest.mark.parametrize(
    "root_value,target",
    [
        ("relative", "state/campaign.sqlite"),
        ("{root}/./campaign", "state/campaign.sqlite"),
        ("{root}/campaign", "../campaign.sqlite"),
        ("{root}/campaign", "/campaign.sqlite"),
        ("{root}/campaign", "state//campaign.sqlite"),
    ],
)
def test_non_normalized_or_escaping_requests_are_rejected_before_authority(
    tmp_path: Path,
    root_value: str,
    target: str,
) -> None:
    rendered = root_value.format(root=tmp_path)
    with pytest.raises(subject.FreshActivationRequestError):
        _acquire(rendered, target)
