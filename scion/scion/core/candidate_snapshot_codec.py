"""Canonical candidate snapshot closure encoder and strict decoder."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from scion.core import candidate_snapshot as cs
from scion.core import candidate_snapshot_materialization as materialization


def identity_payload(snapshot: cs.CandidateSnapshot) -> dict[str, Any]:
    return {
        "schema_version": snapshot.schema_version,
        "campaign_id": snapshot.campaign_id,
        "origin": {"kind": snapshot.origin_kind.value, "id": snapshot.origin_id},
        "branch_id": snapshot.branch_id,
        "lineage_id": snapshot.lineage_id,
        "candidate_code_hash": snapshot.candidate_code_hash,
        "executable_snapshot_hash": snapshot.executable_snapshot_hash,
        "parent_execution_manifest_digest": snapshot.parent_execution_manifest_digest,
        "candidate_execution_manifest_digest": snapshot.candidate_execution_manifest_digest,
        "code_parent": cs._parent_identity_payload(snapshot.code_parent),
        "champion_anchor": {
            "id": snapshot.base_champion_id,
            "hash": snapshot.base_champion_hash,
        },
        "evidence_parent_hypothesis_id": snapshot.evidence_parent_hypothesis_id,
        "hypothesis_id": snapshot.hypothesis_id,
        "mechanism_owner_id": snapshot.mechanism_owner_id,
        "verified_touched_files": list(snapshot.verified_touched_files),
        "proposal_patch_digest": snapshot.proposal_patch_digest,
        "verification_identity_digest": snapshot.verification_identity_digest,
    }


def encode_closure(closure: cs.CandidateSnapshotClosure) -> bytes:
    materialization.validate_internal(closure)
    payload = _payload(closure)
    envelope = {
        "schema_version": cs.CLOSURE_SCHEMA,
        "payload": payload,
        "payload_sha256": _digest_text(_json(payload)),
    }
    return (_json(envelope) + "\n").encode()


def decode_closure(
    data: bytes,
    *,
    expected_sha256: str | None = None,
) -> cs.CandidateSnapshotClosure:
    if expected_sha256 is not None:
        cs._sha(expected_sha256, "expected artifact hash")
        if hashlib.sha256(data).hexdigest() != expected_sha256:
            raise cs.CandidateSnapshotTamperError("snapshot artifact hash mismatch")
    try:
        envelope = json.loads(data.decode())
        if (
            set(envelope) != {"schema_version", "payload", "payload_sha256"}
            or envelope["schema_version"] != cs.CLOSURE_SCHEMA
            or _digest_text(_json(envelope["payload"])) != envelope["payload_sha256"]
        ):
            raise ValueError("invalid envelope")
        closure = _from_payload(envelope["payload"])
        materialization.validate_internal(closure)
        return closure
    except (
        KeyError,
        TypeError,
        ValueError,
        UnicodeError,
        binascii.Error,
    ) as exc:
        raise cs.CandidateSnapshotTamperError(
            "candidate snapshot artifact is invalid"
        ) from exc


def load_closure(
    campaign_root: str | Path,
    ref: str,
    *,
    expected_sha256: str | None = None,
) -> cs.CandidateSnapshotClosure:
    data = materialization.read_snapshot_ref_bytes(campaign_root, ref)
    return decode_closure(data, expected_sha256=expected_sha256)


def _payload(closure: cs.CandidateSnapshotClosure) -> dict[str, Any]:
    snapshot = closure.snapshot
    raw_snapshot = {
        **identity_payload(snapshot),
        "candidate_id": snapshot.candidate_id,
        "code_parent": {
            **cs._parent_identity_payload(snapshot.code_parent),
            "ref": snapshot.code_parent.ref,
        },
        "candidate_snapshot_ref": snapshot.candidate_snapshot_ref,
        "proposal_patch_ref": snapshot.proposal_patch_ref,
        "verification_result_ref": snapshot.verification_result_ref,
    }
    return {
        "schema_version": closure.schema_version,
        "snapshot": raw_snapshot,
        "parent_execution_manifest": cs.execution_manifest_payload(
            closure.parent_execution_manifest
        ),
        "candidate_execution_manifest": cs.execution_manifest_payload(
            closure.candidate_execution_manifest
        ),
        "delta": [
            {
                "file_path": item.file_path,
                "action": item.action,
                "base_sha256": item.base_sha256,
                "result_sha256": item.result_sha256,
                "content_b64": (
                    None
                    if item.content is None
                    else base64.b64encode(item.content).decode()
                ),
            }
            for item in closure.delta
        ],
        "proposal_patch": {
            "representation": "full_file_replacement_by_delta_reference",
            "changes": [
                {
                    "file_path": item.file_path,
                    "action": item.action,
                    "code_sha256": item.code_sha256,
                    "test_hint": item.test_hint,
                    "content_source": item.content_source,
                }
                for item in closure.proposal_patch
            ],
            "repair_attribution": [
                json.loads(item) for item in closure.repair_attribution_json
            ],
        },
        "verification_result": json.loads(closure.verification_result_json),
    }


def _from_payload(payload: Mapping[str, Any]) -> cs.CandidateSnapshotClosure:
    cs._json_object_fields(
        payload,
        {
            "schema_version",
            "snapshot",
            "parent_execution_manifest",
            "candidate_execution_manifest",
            "delta",
            "proposal_patch",
            "verification_result",
        },
        "closure",
    )
    if payload["schema_version"] != cs.CLOSURE_SCHEMA:
        raise ValueError("closure schema mismatch")
    raw, raw_parent = payload["snapshot"], payload["snapshot"]["code_parent"]
    cs._json_object_fields(
        raw,
        {
            "schema_version",
            "candidate_id",
            "campaign_id",
            "origin",
            "branch_id",
            "lineage_id",
            "candidate_code_hash",
            "executable_snapshot_hash",
            "parent_execution_manifest_digest",
            "candidate_execution_manifest_digest",
            "code_parent",
            "champion_anchor",
            "evidence_parent_hypothesis_id",
            "hypothesis_id",
            "mechanism_owner_id",
            "verified_touched_files",
            "proposal_patch_digest",
            "verification_identity_digest",
            "candidate_snapshot_ref",
            "proposal_patch_ref",
            "verification_result_ref",
        },
        "snapshot",
    )
    cs._json_object_fields(
        raw_parent,
        {"kind", "candidate_id", "code_hash", "executable_snapshot_hash", "ref"},
        "code parent",
    )
    parent = cs.CandidateCodeParent(
        cs.CandidateCodeParentKind(raw_parent["kind"]),
        raw_parent["candidate_id"],
        raw_parent["code_hash"],
        raw_parent["executable_snapshot_hash"],
        raw_parent["ref"],
    )
    origin, champion = raw["origin"], raw["champion_anchor"]
    cs._json_object_fields(origin, {"kind", "id"}, "origin")
    cs._json_object_fields(champion, {"id", "hash"}, "champion anchor")
    snapshot = cs.CandidateSnapshot(
        raw["schema_version"],
        raw["candidate_id"],
        raw["campaign_id"],
        cs.CandidateOriginKind(origin["kind"]),
        origin["id"],
        raw["branch_id"],
        raw["lineage_id"],
        raw["candidate_code_hash"],
        raw["executable_snapshot_hash"],
        raw["parent_execution_manifest_digest"],
        raw["candidate_execution_manifest_digest"],
        parent,
        champion["id"],
        champion["hash"],
        raw["evidence_parent_hypothesis_id"],
        raw["hypothesis_id"],
        raw["mechanism_owner_id"],
        tuple(cs._json_array(raw["verified_touched_files"], "touched files")),
        raw["proposal_patch_digest"],
        raw["verification_identity_digest"],
        raw["candidate_snapshot_ref"],
        raw["proposal_patch_ref"],
        raw["verification_result_ref"],
    )
    raw_patch = payload["proposal_patch"]
    cs._json_object_fields(
        raw_patch, {"representation", "changes", "repair_attribution"}, "Patch"
    )
    if raw_patch["representation"] != "full_file_replacement_by_delta_reference":
        raise ValueError("Patch representation mismatch")
    changes = cs._json_array(raw_patch["changes"], "Patch changes")
    repairs = cs._json_array(raw_patch["repair_attribution"], "repair attribution")
    for item in changes:
        cs._json_object_fields(
            item,
            {"file_path", "action", "code_sha256", "test_hint", "content_source"},
            "Patch change",
        )
    patch = tuple(
        cs.NormalizedPatchChange(
            item["file_path"],
            item["action"],
            item["code_sha256"],
            item["test_hint"],
            item["content_source"],
        )
        for item in changes
    )
    delta_items = cs._json_array(payload["delta"], "delta")
    for item in delta_items:
        cs._json_object_fields(
            item,
            {"file_path", "action", "base_sha256", "result_sha256", "content_b64"},
            "delta entry",
        )
    delta = tuple(
        cs.CandidateDeltaEntry(
            item["file_path"],
            item["action"],
            item["base_sha256"],
            item["result_sha256"],
            (
                None
                if item["content_b64"] is None
                else base64.b64decode(item["content_b64"], validate=True)
            ),
        )
        for item in delta_items
    )
    if any(not isinstance(item, dict) for item in repairs):
        raise ValueError("repair attribution entries must be mappings")
    return cs.CandidateSnapshotClosure(
        payload["schema_version"],
        snapshot,
        cs._execution_manifest_from_json(payload["parent_execution_manifest"]),
        cs._execution_manifest_from_json(payload["candidate_execution_manifest"]),
        delta,
        patch,
        tuple(_json(cs._json_safe(item)) for item in repairs),
        _json(cs._json_safe(payload["verification_result"])),
    )


def _json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
