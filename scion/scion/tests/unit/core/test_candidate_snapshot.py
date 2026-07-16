from __future__ import annotations

import dataclasses
import copy
import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest

from scion.core.candidate_snapshot import (
    EXECUTION_MANIFEST_SCHEMA,
    CandidateAncestorArtifact,
    CandidateCodeParent,
    CandidateCodeParentKind,
    CandidateOriginKind,
    CandidateSnapshotError,
    CandidateSnapshotRequest,
    CandidateSnapshotTamperError,
    ExecutionFile,
    ExecutionManifest,
    _build_candidate_snapshot_closure,
    candidate_snapshot_closure_bytes,
    candidate_snapshot_identity_payload,
    decode_candidate_snapshot_closure,
    execution_manifest_digest,
    materialize_candidate_snapshot_closure,
    validate_candidate_snapshot_closure,
)
from scion.core.models import (
    CheckResult,
    PatchFileChange,
    PatchProposal,
    VerificationResult,
)
from scion.runtime.workspace import WorkspaceMaterializer


@dataclass
class Harness:
    campaign: Path
    parent: Path
    candidate: Path
    materializer: WorkspaceMaterializer
    parent_manifest: dict[str, object]
    candidate_manifest: dict[str, object]
    code_parent: CandidateCodeParent
    patch: PatchProposal
    verification: VerificationResult

    def build(self, **overrides):
        request_values = {
            "parent_workspace": self.parent,
            "candidate_workspace": self.candidate,
            "campaign_id": "campaign-1",
            "origin_kind": CandidateOriginKind.DIRECT_CODE_ATTEMPT,
            "origin_id": "attempt-1",
            "branch_id": "branch-1",
            "lineage_id": "lineage-1",
            "code_parent": self.code_parent,
            "base_champion_id": "1",
            "base_champion_hash": self.code_parent.executable_snapshot_hash,
            "evidence_parent_hypothesis_id": None,
            "hypothesis_id": "hypothesis-1",
            "mechanism_owner_id": "unclassified",
            "patch": self.patch,
            "verification_result": self.verification,
        }
        for key in tuple(request_values):
            if key in overrides:
                request_values[key] = overrides.pop(key)
        request_values["parent_workspace"] = str(request_values["parent_workspace"])
        request_values["candidate_workspace"] = str(
            request_values["candidate_workspace"]
        )
        campaign_root = overrides.pop("campaign_root", self.campaign)
        parent_manifest = overrides.pop(
            "parent_editable_identity_manifest", self.parent_manifest
        )
        candidate_manifest = overrides.pop(
            "candidate_editable_identity_manifest", self.candidate_manifest
        )
        ancestor_resolver = overrides.pop("ancestor_resolver", None)
        if overrides:
            raise AssertionError(f"unknown snapshot test override: {sorted(overrides)}")
        return _build_candidate_snapshot_closure(
            request=CandidateSnapshotRequest(**request_values),
            campaign_root=campaign_root,
            parent_editable_identity_manifest=parent_manifest,
            candidate_editable_identity_manifest=candidate_manifest,
            ancestor_resolver=ancestor_resolver,
        )


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _harness(tmp_path: Path) -> Harness:
    campaign = tmp_path / "campaign"
    parent = campaign / "champions" / "v1"
    candidate = campaign / "candidate_workspaces" / "branch-1" / "attempt-1"
    _write(parent / "operators" / "op.py", "VALUE = 1\n")
    _write(parent / "operators" / "old.py", "OLD = True\n")
    _write(parent / "registry.yaml", "operators:\n- op\n")
    _write(parent / "README.md", "not part of execution identity\n")
    shutil.copytree(parent, candidate)
    _write(candidate / "operators" / "op.py", "VALUE = 2\n")
    _write(candidate / "operators" / "new.py", "NEW = True\n")
    (candidate / "operators" / "old.py").unlink()
    _write(candidate / "registry.yaml", "operators:\n- op\n- new\n")
    materializer = WorkspaceMaterializer(
        str(campaign), editable_patterns=("operators/**",)
    )
    parent_manifest = materializer.editable_identity_manifest(str(parent))
    candidate_manifest = materializer.editable_identity_manifest(str(candidate))
    code_parent = CandidateCodeParent(
        kind=CandidateCodeParentKind.CHAMPION,
        candidate_id=None,
        code_hash=str(parent_manifest["code_hash"]),
        executable_snapshot_hash=materializer.compute_snapshot_hash(str(parent)),
        ref="champions/v1",
    )
    patch = PatchProposal(
        file_path="operators/op.py",
        action="modify",
        code_content="VALUE = 2\n",
        test_hint="unit",
        additional_changes=(
            PatchFileChange(
                file_path="operators/new.py",
                action="create",
                code_content="NEW = True\n",
            ),
            PatchFileChange(
                file_path="operators/old.py",
                action="delete",
                code_content="",
            ),
        ),
        repair_attribution=({"kind": "direct", "attempt": 1},),
    )
    verification = VerificationResult(
        passed=True,
        checks=(
            CheckResult(
                name="compile",
                passed=True,
                severity="light",
                detail="ok",
                elapsed_ms=7,
                metadata={"files": 3},
            ),
        ),
    )
    return Harness(
        campaign,
        parent,
        candidate,
        materializer,
        parent_manifest,
        candidate_manifest,
        code_parent,
        patch,
        verification,
    )


def _forge_patch_identity(closure, index: int, **changes):
    patch = list(closure.proposal_patch)
    patch[index] = dataclasses.replace(patch[index], **changes)
    patch_identity = [
        {
            "file_path": item.file_path,
            "action": item.action,
            "code_sha256": item.code_sha256,
        }
        for item in patch
    ]
    canonical_patch = json.dumps(
        patch_identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    snapshot = dataclasses.replace(
        closure.snapshot,
        proposal_patch_digest=hashlib.sha256(canonical_patch.encode()).hexdigest(),
    )
    canonical_identity = json.dumps(
        candidate_snapshot_identity_payload(snapshot),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    candidate_id = hashlib.sha256(canonical_identity.encode()).hexdigest()
    ref = f"candidate_snapshots/{candidate_id}.json"
    snapshot = dataclasses.replace(
        snapshot,
        candidate_id=candidate_id,
        candidate_snapshot_ref=ref,
        proposal_patch_ref=f"{ref}#/proposal_patch",
        verification_result_ref=f"{ref}#/verification_result",
    )
    return dataclasses.replace(
        closure,
        snapshot=snapshot,
        proposal_patch=tuple(patch),
    )


def test_builds_frozen_stable_identity_from_actual_execution_diff(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    closure = harness.build()

    assert len(closure.snapshot.candidate_id) == 64
    assert closure.snapshot.candidate_code_hash != closure.snapshot.candidate_id
    assert closure.snapshot.verified_touched_files == (
        "operators/new.py",
        "operators/old.py",
        "operators/op.py",
        "registry.yaml",
    )
    assert [item.action for item in closure.delta] == [
        "create",
        "delete",
        "modify",
        "modify",
    ]
    tombstone = closure.delta[1]
    assert tombstone.content is None and tombstone.result_sha256 is None
    assert closure.delta[0].content == b"NEW = True\n"
    assert closure.proposal_patch[0].content_source == "delta:operators/op.py"
    assert closure.repair_attribution == ({"attempt": 1, "kind": "direct"},)
    with pytest.raises(dataclasses.FrozenInstanceError):
        closure.snapshot.candidate_id = "0" * 64  # type: ignore[misc]

    again = harness.build()
    lineage_drift = harness.build(lineage_id="lineage-2")
    assert again.snapshot.candidate_id == closure.snapshot.candidate_id
    assert lineage_drift.snapshot.candidate_id != closure.snapshot.candidate_id

    alternate_parent = harness.campaign / "champions" / "same-content"
    shutil.copytree(harness.parent, alternate_parent)
    alternate_manifest = harness.materializer.editable_identity_manifest(
        str(alternate_parent)
    )
    alternate_owner = dataclasses.replace(
        harness.code_parent,
        ref="champions/same-content",
    )
    alternate_ref = harness.build(
        parent_workspace=alternate_parent,
        parent_editable_identity_manifest=alternate_manifest,
        code_parent=alternate_owner,
    )
    assert alternate_ref.snapshot.candidate_id == closure.snapshot.candidate_id


def test_verification_runtime_noise_is_not_candidate_identity(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    baseline = harness.build()
    check = harness.verification.checks[0]
    noisy_check = dataclasses.replace(
        check,
        elapsed_ms=987654,
        detail="compiled from a different temporary workspace",
        metadata={"workspace": "/tmp/other-host/random-run", "files": 3},
    )
    noisy = harness.build(
        verification_result=dataclasses.replace(
            harness.verification,
            checks=(noisy_check,),
        )
    )

    baseline_bytes = candidate_snapshot_closure_bytes(baseline)
    noisy_bytes = candidate_snapshot_closure_bytes(noisy)
    assert noisy.snapshot.candidate_id == baseline.snapshot.candidate_id
    assert noisy.snapshot.verification_identity_digest == (
        baseline.snapshot.verification_identity_digest
    )
    assert noisy_bytes != baseline_bytes
    assert (
        hashlib.sha256(noisy_bytes).hexdigest()
        != hashlib.sha256(baseline_bytes).hexdigest()
    )

    for stable_change in ({"name": "different-check"}, {"severity": "heavy"}):
        changed = harness.build(
            verification_result=dataclasses.replace(
                harness.verification,
                checks=(dataclasses.replace(check, **stable_change),),
            )
        )
        assert changed.snapshot.candidate_id != baseline.snapshot.candidate_id


def test_a_b_c_legacy_tree_hash_collision_is_framed_by_manifest_digest(
    tmp_path: Path,
) -> None:
    campaign = tmp_path / "campaign"
    first = campaign / "states" / "first"
    second = campaign / "states" / "second"
    for path, contents in (
        (first / "a", b""),
        (first / "b", b""),
        (first / "c", b"bcZ"),
        (second / "a", b"bc"),
        (second / "b", b""),
        (second / "c", b"Z"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
    materializer = WorkspaceMaterializer(
        str(campaign), editable_patterns=("a", "b", "c")
    )
    first_raw = materializer.editable_identity_manifest(str(first))
    second_raw = materializer.editable_identity_manifest(str(second))
    assert first_raw["code_hash"] == second_raw["code_hash"]

    def framed(raw: dict[str, object]) -> ExecutionManifest:
        files = tuple(
            ExecutionFile(item["file_path"], item["sha256"], "code_identity")
            for item in raw["files"]  # type: ignore[index,union-attr]
        )
        return ExecutionManifest(
            EXECUTION_MANIFEST_SCHEMA,
            files,
            str(raw["code_hash"]),
            str(raw["code_hash"]),
        )

    first_manifest, second_manifest = framed(first_raw), framed(second_raw)
    assert execution_manifest_digest(first_manifest) != execution_manifest_digest(
        second_manifest
    )
    baseline = _harness(tmp_path / "baseline").build().snapshot
    first_snapshot = dataclasses.replace(
        baseline,
        candidate_code_hash=first_manifest.code_hash,
        executable_snapshot_hash=first_manifest.executable_snapshot_hash,
        candidate_execution_manifest_digest=execution_manifest_digest(first_manifest),
    )
    second_snapshot = dataclasses.replace(
        baseline,
        candidate_code_hash=second_manifest.code_hash,
        executable_snapshot_hash=second_manifest.executable_snapshot_hash,
        candidate_execution_manifest_digest=execution_manifest_digest(second_manifest),
    )
    first_identity = json.dumps(
        candidate_snapshot_identity_payload(first_snapshot),
        sort_keys=True,
        separators=(",", ":"),
    )
    second_identity = json.dumps(
        candidate_snapshot_identity_payload(second_snapshot),
        sort_keys=True,
        separators=(",", ":"),
    )
    assert (
        hashlib.sha256(first_identity.encode()).hexdigest()
        != hashlib.sha256(second_identity.encode()).hexdigest()
    )


def test_unclaimed_code_delta_fails_closed_but_activation_delta_is_allowed(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    accepted = harness.build()
    registry_delta = next(
        item for item in accepted.delta if item.file_path == "registry.yaml"
    )
    assert registry_delta.action == "modify"

    _write(harness.candidate / "operators" / "unclaimed.py", "UNCLAIMED = True\n")
    manifest = harness.materializer.editable_identity_manifest(str(harness.candidate))
    with pytest.raises(CandidateSnapshotTamperError, match="unclaimed code identity"):
        harness.build(candidate_editable_identity_manifest=manifest)


@pytest.mark.parametrize(
    "verification",
    (
        VerificationResult(
            passed=True,
            checks=(CheckResult("compile", False, "light", "bad", 1),),
        ),
        VerificationResult(passed=True, checks=(), failure_severity="heavy"),
        VerificationResult(passed=True, checks=(), first_failure="compile"),
        VerificationResult(
            passed=True,
            checks=(
                CheckResult("compile", True, "light", "ok", 1),
                CheckResult("compile", True, "heavy", "ok", 2),
            ),
        ),
        VerificationResult(
            passed=True,
            checks=(CheckResult("compile", True, "light", "ok", -1),),
        ),
        VerificationResult(
            passed=True,
            checks=(CheckResult("compile", True, "light", "ok", True),),
        ),
        VerificationResult(
            passed=True,
            checks=(CheckResult("/tmp/random/check", True, "light", "ok", 1),),
        ),
    ),
)
def test_passed_verification_requires_consistent_stable_checks(
    tmp_path: Path,
    verification: VerificationResult,
) -> None:
    with pytest.raises(ValueError, match="Verification"):
        _harness(tmp_path).build(verification_result=verification)


def test_strict_decode_rejects_wrong_json_types_and_runtime_invariants(
    tmp_path: Path,
) -> None:
    encoded = candidate_snapshot_closure_bytes(_harness(tmp_path).build())

    def resigned(mutator) -> bytes:
        envelope = copy.deepcopy(json.loads(encoded))
        mutator(envelope["payload"])
        canonical = json.dumps(
            envelope["payload"],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        envelope["payload_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
        return json.dumps(
            envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()

    mutations = (
        lambda payload: payload["snapshot"].__setitem__("campaign_id", 7),
        lambda payload: payload["snapshot"].__setitem__(
            "evidence_parent_hypothesis_id", 8
        ),
        lambda payload: payload["proposal_patch"].__setitem__(
            "repair_attribution", ["not-a-map"]
        ),
        lambda payload: payload.__setitem__("delta", {}),
        lambda payload: payload["verification_result"]["checks"][0].__setitem__(
            "elapsed_ms", -1
        ),
    )
    for mutate in mutations:
        with pytest.raises(CandidateSnapshotTamperError):
            decode_candidate_snapshot_closure(resigned(mutate))


def test_codec_keeps_changed_content_only_in_delta_and_detects_tamper(
    tmp_path: Path,
) -> None:
    closure = _harness(tmp_path).build()
    encoded = candidate_snapshot_closure_bytes(closure)
    payload = json.loads(encoded)
    patch = payload["payload"]["proposal_patch"]
    assert "code_content" not in json.dumps(patch)
    assert all(
        set(change)
        == {"action", "code_sha256", "content_source", "file_path", "test_hint"}
        for change in patch["changes"]
    )
    new_b64 = payload["payload"]["delta"][0]["content_b64"]
    assert json.dumps(payload).count(new_b64) == 1
    assert decode_candidate_snapshot_closure(encoded) == closure
    pinned = hashlib.sha256(encoded).hexdigest()
    assert decode_candidate_snapshot_closure(encoded, expected_sha256=pinned) == closure

    payload["payload"]["delta"][0]["content_b64"] = "dGFtcGVyZWQ="
    tampered = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(CandidateSnapshotTamperError):
        decode_candidate_snapshot_closure(tampered)
    with pytest.raises(CandidateSnapshotTamperError):
        decode_candidate_snapshot_closure(encoded, expected_sha256="0" * 64)


@pytest.mark.parametrize(
    ("index", "changes", "message"),
    (
        (0, {"code_sha256": hashlib.sha256(b"forged").hexdigest()}, "delta content"),
        (0, {"action": "create"}, "delta content"),
        (1, {"content_source": "parent:operators/new.py"}, "parent content"),
        (2, {"code_sha256": hashlib.sha256(b"deleted bytes").hexdigest()}, "tombstone"),
    ),
)
def test_patch_semantics_remain_bound_after_identity_is_resigned(
    tmp_path: Path,
    index: int,
    changes: dict[str, str],
    message: str,
) -> None:
    harness = _harness(tmp_path)
    forged = _forge_patch_identity(harness.build(), index, **changes)

    with pytest.raises(CandidateSnapshotTamperError, match=message):
        candidate_snapshot_closure_bytes(forged)
    with pytest.raises(CandidateSnapshotTamperError, match=message):
        materialize_candidate_snapshot_closure(
            forged,
            campaign_root=harness.campaign,
            destination=tmp_path / "forged-materialization",
        )


def test_strict_decode_rejects_resigned_duplicate_patch_paths(tmp_path: Path) -> None:
    closure = _harness(tmp_path).build()
    envelope = json.loads(candidate_snapshot_closure_bytes(closure))
    changes = envelope["payload"]["proposal_patch"]["changes"]
    changes.append(copy.deepcopy(changes[0]))
    patch_identity = [
        {
            "file_path": item["file_path"],
            "action": item["action"],
            "code_sha256": item["code_sha256"],
        }
        for item in changes
    ]
    patch_digest = hashlib.sha256(
        json.dumps(patch_identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    snapshot = dataclasses.replace(closure.snapshot, proposal_patch_digest=patch_digest)
    candidate_id = hashlib.sha256(
        json.dumps(
            candidate_snapshot_identity_payload(snapshot),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    ref = f"candidate_snapshots/{candidate_id}.json"
    raw_snapshot = envelope["payload"]["snapshot"]
    raw_snapshot.update(
        {
            "proposal_patch_digest": patch_digest,
            "candidate_id": candidate_id,
            "candidate_snapshot_ref": ref,
            "proposal_patch_ref": f"{ref}#/proposal_patch",
            "verification_result_ref": f"{ref}#/verification_result",
        }
    )
    payload_json = json.dumps(
        envelope["payload"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    envelope["payload_sha256"] = hashlib.sha256(payload_json.encode()).hexdigest()
    resigned = json.dumps(
        envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()

    with pytest.raises(CandidateSnapshotTamperError):
        decode_candidate_snapshot_closure(resigned)


@pytest.mark.parametrize(
    "field",
    (
        "campaign_id",
        "origin_id",
        "branch_id",
        "lineage_id",
        "base_champion_id",
        "hypothesis_id",
        "mechanism_owner_id",
        "evidence_parent_hypothesis_id",
    ),
)
def test_snapshot_request_rejects_whitespace_identity(
    tmp_path: Path,
    field: str,
) -> None:
    with pytest.raises(ValueError, match="canonical|string or null"):
        _harness(tmp_path).build(**{field: " padded "})


def test_snapshot_request_requires_exact_typed_code_parent(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="code parent must be typed"):
        _harness(tmp_path).build(code_parent=object())


def test_materializes_only_exact_execution_identity_not_full_repository(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    closure = harness.build()
    destination = tmp_path / "materialized"
    materialize_candidate_snapshot_closure(
        closure, campaign_root=harness.campaign, destination=destination
    )

    for relative in closure.snapshot.verified_touched_files:
        expected = harness.candidate / relative
        actual = destination / relative
        if expected.exists():
            assert actual.read_bytes() == expected.read_bytes()
        else:
            assert not actual.exists()
    assert not (destination / "README.md").exists()
    assert harness.materializer.compute_code_hash(str(destination)) == (
        closure.snapshot.candidate_code_hash
    )
    assert harness.materializer.compute_snapshot_hash(str(destination)) == (
        closure.snapshot.executable_snapshot_hash
    )
    validate_candidate_snapshot_closure(closure, campaign_root=harness.campaign)


def test_rejects_parent_drift_candidate_hash_drift_and_reserved_origin(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    closure = harness.build()
    with pytest.raises(CandidateSnapshotTamperError, match="anchor"):
        harness.build(base_champion_hash="0" * 64)
    _write(harness.parent / "operators" / "op.py", "DRIFT = True\n")
    with pytest.raises(CandidateSnapshotTamperError, match="parent|hash|drift"):
        validate_candidate_snapshot_closure(closure, campaign_root=harness.campaign)

    harness = _harness(tmp_path / "second")
    _write(harness.candidate / "operators" / "op.py", "LATE = True\n")
    with pytest.raises(CandidateSnapshotTamperError, match="hash"):
        harness.build()
    with pytest.raises(ValueError, match="reserved"):
        harness.build(origin_kind=CandidateOriginKind.FIXED_REPLAY)
    failed = dataclasses.replace(harness.verification, passed=False)
    with pytest.raises(ValueError, match="passed Verification"):
        harness.build(verification_result=failed)


def test_exact_reuse_does_not_create_a_new_snapshot(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    shutil.rmtree(harness.candidate)
    shutil.copytree(harness.parent, harness.candidate)
    same_manifest = harness.materializer.editable_identity_manifest(
        str(harness.candidate)
    )
    with pytest.raises(ValueError, match="existing candidate ID"):
        harness.build(
            candidate_editable_identity_manifest=same_manifest,
            patch=PatchProposal("operators/op.py", "modify", "VALUE = 1\n"),
        )


def test_rejects_path_escape_symlink_and_missing_parent_ref(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    with pytest.raises(ValueError, match="relative"):
        CandidateCodeParent(
            CandidateCodeParentKind.CHAMPION,
            None,
            harness.code_parent.code_hash,
            harness.code_parent.executable_snapshot_hash,
            "../champion",
        )
    outside = tmp_path / "outside"
    shutil.copytree(harness.candidate, outside)
    with pytest.raises(CandidateSnapshotError, match="escapes"):
        harness.build(candidate_workspace=outside)

    missing = dataclasses.replace(harness.code_parent, ref="champions/missing")
    with pytest.raises(CandidateSnapshotTamperError, match="missing"):
        harness.build(code_parent=missing)

    linked = harness.candidate / "operators" / "linked.py"
    linked.symlink_to(harness.candidate / "operators" / "op.py")
    linked_manifest = harness.materializer.editable_identity_manifest(
        str(harness.candidate)
    )
    with pytest.raises(CandidateSnapshotTamperError, match="symlink"):
        harness.build(candidate_editable_identity_manifest=linked_manifest)


def test_candidate_parent_chain_is_loaded_validated_and_materialized(
    tmp_path: Path,
) -> None:
    first = _harness(tmp_path)
    first_closure = first.build()
    artifact_bytes = candidate_snapshot_closure_bytes(first_closure)
    artifact = first.campaign / first_closure.snapshot.candidate_snapshot_ref
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(artifact_bytes)
    pinned = CandidateAncestorArtifact(
        candidate_id=first_closure.snapshot.candidate_id,
        ref=first_closure.snapshot.candidate_snapshot_ref,
        artifact_sha256=hashlib.sha256(artifact_bytes).hexdigest(),
        artifact_bytes=artifact_bytes,
    )

    def resolver(candidate_id: str, ref: str) -> CandidateAncestorArtifact:
        assert (candidate_id, ref) == (pinned.candidate_id, pinned.ref)
        return pinned

    parent_workspace = first.campaign / "workspaces" / "candidate-parent"
    materialize_candidate_snapshot_closure(
        first_closure,
        campaign_root=first.campaign,
        destination=parent_workspace,
    )
    child_workspace = first.campaign / "candidate_workspaces" / "branch-1" / "attempt-2"
    shutil.copytree(parent_workspace, child_workspace)
    _write(child_workspace / "operators" / "op.py", "VALUE = 3\n")
    parent_manifest = first.materializer.editable_identity_manifest(
        str(parent_workspace)
    )
    child_manifest = first.materializer.editable_identity_manifest(str(child_workspace))
    candidate_parent = CandidateCodeParent(
        CandidateCodeParentKind.CANDIDATE,
        first_closure.snapshot.candidate_id,
        str(parent_manifest["code_hash"]),
        first.materializer.compute_snapshot_hash(str(parent_workspace)),
        first_closure.snapshot.candidate_snapshot_ref,
    )
    child_arguments = {
        "parent_workspace": parent_workspace,
        "candidate_workspace": child_workspace,
        "parent_editable_identity_manifest": parent_manifest,
        "candidate_editable_identity_manifest": child_manifest,
        "code_parent": candidate_parent,
        "origin_id": "attempt-2",
        "hypothesis_id": "hypothesis-2",
        "patch": PatchProposal("operators/op.py", "modify", "VALUE = 3\n"),
    }
    with pytest.raises(CandidateSnapshotTamperError, match="pinned resolver"):
        first.build(**child_arguments)
    with pytest.raises(CandidateSnapshotTamperError, match="champion anchor"):
        first.build(
            **child_arguments,
            ancestor_resolver=resolver,
            base_champion_id="drifted-champion",
        )
    child = first.build(
        **child_arguments,
        ancestor_resolver=resolver,
    )
    destination = tmp_path / "child-materialized"
    materialize_candidate_snapshot_closure(
        child,
        campaign_root=first.campaign,
        destination=destination,
        ancestor_resolver=resolver,
    )
    assert (destination / "operators" / "op.py").read_text() == "VALUE = 3\n"
    assert first.materializer.compute_snapshot_hash(str(destination)) == (
        child.snapshot.executable_snapshot_hash
    )

    tampered_envelope = json.loads(artifact_bytes)
    tampered_envelope["payload"]["verification_result"]["checks"][0][
        "detail"
    ] = "tampered diagnostic"
    canonical = json.dumps(
        tampered_envelope["payload"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    tampered_envelope["payload_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    tampered_bytes = json.dumps(
        tampered_envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    tampered_pin = dataclasses.replace(pinned, artifact_bytes=tampered_bytes)
    with pytest.raises(CandidateSnapshotTamperError, match="artifact hash"):
        first.build(
            **child_arguments,
            ancestor_resolver=lambda _candidate_id, _ref: tampered_pin,
        )
