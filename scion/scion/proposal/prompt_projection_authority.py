"""Single authority for structured prompt projection and provider rendering."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from scion.proposal import hypothesis_generation_authority as _generation
from scion.proposal.context_owner_maps import HYPOTHESIS_CONTEXT_OWNER_MAP
from scion.proposal.context_snapshot import (
    ProposalContextSnapshot,
    SafeProposalInputs,
)
from scion.proposal.prompt_manifest import stable_digest
from scion.proposal.prompt_manifest_accounting import _provider_prompt_hash
from scion.proposal.schemas import bind_hypothesis_tool_to_context

BoundHypothesisPrompt = _generation.BoundHypothesisPrompt
HypothesisPromptSource = _generation.HypothesisPromptSource

_OWNER_CONTEXT_SCHEMA = "hypothesis-owner-context-projection.v1"
_PROVIDER_SNAPSHOT_SCHEMA = "hypothesis-provider-snapshot.v1"
_OWNER_CONTEXT_KEYS = frozenset(
    {
        "schema_version",
        "campaign_id",
        "runtime_mode",
        "root_generation",
        "branch",
        "h_bundle",
        "prior_head",
        "anchors",
    }
)
_BRANCH_KEYS = frozenset(
    {
        "branch_id",
        "owner_revision",
        "storage_sha256",
        "state",
        "branch_code_status",
        "current_code_hash",
        "last_clean_code_hash",
        "base_champion_id",
        "base_champion_hash",
        "base_champion_weight_revision",
    }
)
_H_BUNDLE_KEYS = frozenset({"digest", "count", "items"})
_H_ITEM_KEYS = frozenset(
    {"hypothesis_id", "owner_revision", "storage_sha256"}
)
_ANCHOR_KEYS = frozenset(
    {
        "problem_id",
        "problem_spec_hash",
        "split_manifest_hash",
        "seed_ledger_hash",
        "champion_version",
        "champion_weight_revision",
        "champion_code_snapshot_hash",
        "branch_base_champion_id",
        "branch_base_champion_hash",
    }
)
_EVIDENCE_GOVERNANCE_KEYS = frozenset(
    {
        "schema_version",
        "configured_keys",
        "configured_problem_evidence_sha256",
        "provider_context_sha256",
    }
)
_BOUND_OWNER_SOURCE_KEYS = frozenset(
    {
        "branch_id",
        "branch_current_code",
        "champion_operators_code",
        "champion_stats",
        "champion_version",
        "targetable_files",
    }
)
_NESTED_OWNER_SOURCE_KEYS = frozenset(
    {
        "base_champion_hash",
        "base_champion_id",
        "base_champion_weight_revision",
        "branch_current_code",
        "branch_id",
        "branch_owner",
        "champion_code_snapshot_hash",
        "champion_operators_code",
        "champion_version",
        "champion_weight_revision",
        "code_hash",
        "current_code_hash",
        "h_bundle",
        "last_clean_code_hash",
        "owner_context",
        "prior_head",
        "selected_manifest_digest",
        "snapshot_hash",
        "source_kind",
        "targetable_files",
    }
)


class HypothesisPromptRejectedError(RuntimeError):
    """Exact source, owner context, evidence, or rendering was rejected."""


class HypothesisPromptUnknownError(RuntimeError):
    """Unexpected prompt work failed after the prompt source was claimed."""


@dataclass(frozen=True)
class AuthoritativePromptProjection:
    """Immutable canonical projection result with order-preserving JSON owners."""

    structured_context_json: str
    system_blocks_json: str
    user_prompt: str

    @classmethod
    def create(
        cls,
        *,
        structured_context: dict[str, Any],
        system_blocks: list[dict[str, Any]] | tuple[dict[str, Any], ...],
        user_prompt: str,
    ) -> "AuthoritativePromptProjection":
        return cls(
            structured_context_json=_canonical_json(structured_context),
            system_blocks_json=_canonical_json(list(system_blocks)),
            user_prompt=str(user_prompt),
        )

    @property
    def structured_context(self) -> dict[str, Any]:
        value = json.loads(self.structured_context_json)
        if not isinstance(value, dict):
            raise TypeError("canonical structured prompt context is not a mapping")
        return value

    @property
    def system_blocks(self) -> tuple[dict[str, Any], ...]:
        value = json.loads(self.system_blocks_json)
        if not isinstance(value, list) or not all(
            isinstance(block, dict) for block in value
        ):
            raise TypeError("canonical prompt system blocks are invalid")
        return tuple(value)

    @property
    def context_digest(self) -> str:
        return stable_digest(self.structured_context, length=64)


class ProposalPromptProjectionAuthority:
    """Own the single direct-V3 provider projection."""

    __slots__ = ("__hypothesis_generation_authority",)

    def __init_subclass__(cls, **_kwargs: object) -> None:
        raise TypeError("ProposalPromptProjectionAuthority is sealed")

    def __init__(self) -> None:
        self.__hypothesis_generation_authority: (
            _generation._AuthorityHandle | None
        ) = None

    def _install_hypothesis_generation_authority(
        self,
        authority: _generation._AuthorityHandle,
    ) -> None:
        """Install this exact prompt owner's checkpoint-A handle once."""

        if self.__hypothesis_generation_authority is not None:
            raise _generation.HypothesisGenerationLifecycleError(
                "ProposalPromptProjectionAuthority generation authority is "
                "already installed"
            )
        _generation._require_authority(
            authority,
            role=_generation._AuthorityRole.PROMPT_OWNER,
            owner=self,
        )
        self.__hypothesis_generation_authority = authority

    def _require_hypothesis_generation_authority(
        self,
    ) -> _generation._AuthorityHandle:
        authority = self.__hypothesis_generation_authority
        if authority is None:
            raise _generation.InvalidHypothesisGenerationCapabilityError(
                "ProposalPromptProjectionAuthority generation authority is "
                "not installed"
            )
        _generation._require_authority(
            authority,
            role=_generation._AuthorityRole.PROMPT_OWNER,
            owner=self,
        )
        return authority

    def bind_hypothesis_prompt(
        self,
        prompt_source: HypothesisPromptSource,
    ) -> BoundHypothesisPrompt:
        """Claim and bind one prompt from exact owner/source/evidence facts."""

        authority = self._require_hypothesis_generation_authority()
        prompt, code, evidence = _generation._claim_prompt_source(
            authority,
            prompt_source,
        )
        try:
            snapshot, provider_context = _checkpoint_a_context_snapshot(
                prompt=prompt,
                code=code,
                evidence=evidence,
            )
            try:
                projection = self.project("hypothesis", snapshot)
                provider_tool, allowed_change_loci = (
                    bind_hypothesis_tool_to_context(provider_context)
                )
            except (TypeError, ValueError) as exc:
                raise HypothesisPromptRejectedError(
                    "authoritative hypothesis prompt cannot be rendered"
                ) from exc

            provider_context_json = _canonical_json_bytes(provider_context)
            context_digest = hashlib.sha256(provider_context_json).hexdigest()
            if stable_digest(provider_context, length=64) != context_digest:
                raise HypothesisPromptRejectedError(
                    "provider context digest codec is inconsistent"
                )
            system_blocks = tuple(
                dict(block) for block in projection.system_blocks
            )
            user_prompt = projection.user_prompt
            provider_tool = dict(provider_tool)
            allowed_change_loci = tuple(allowed_change_loci)
            provider_snapshot_bytes = _canonical_json_bytes(
                {
                    "allowed_change_loci": list(allowed_change_loci),
                    "authoritative_context_ref": snapshot.snapshot_id,
                    "context_digest": context_digest,
                    "provider_tool": provider_tool,
                    "render_kind": "hypothesis",
                    "schema_version": _PROVIDER_SNAPSHOT_SCHEMA,
                    "system_blocks": [dict(block) for block in system_blocks],
                    "user_prompt": user_prompt,
                }
            )
            return _generation._issue_bound_prompt(
                authority,
                prompt_source,
                context_snapshot=snapshot,
                provider_context_json=provider_context_json,
                provider_snapshot_bytes=provider_snapshot_bytes,
                context_digest=context_digest,
                prompt_hash=_provider_prompt_hash(
                    system_blocks,
                    user_prompt,
                ),
                provider_tool_digest=stable_digest(
                    provider_tool,
                    length=64,
                ),
                governance_digest=snapshot.governance_envelope.digest,
            )
        except HypothesisPromptRejectedError:
            _generation._finish_prompt_failure(
                authority,
                prompt_source,
                rejected=True,
            )
            raise
        except BaseException as exc:
            _generation._finish_prompt_failure(
                authority,
                prompt_source,
                rejected=False,
            )
            if not isinstance(exc, Exception):
                raise
            raise HypothesisPromptUnknownError(
                "hypothesis prompt binding failed unexpectedly after claim"
            ) from exc

    @staticmethod
    def project(
        render_kind: str,
        snapshot: ProposalContextSnapshot,
    ) -> AuthoritativePromptProjection:
        kind = str(render_kind)
        phase = "hypothesis" if kind.startswith("hypothesis") else kind
        if phase not in {"hypothesis", "code"}:
            raise ValueError(f"unsupported authoritative prompt kind: {kind}")
        if snapshot.phase != phase:
            raise ValueError(
                f"{kind} prompt requires a {phase} authoritative snapshot"
            )

        structured = snapshot.inputs.provider_context(include_renderer_inputs=True)
        if kind == "hypothesis":
            from scion.proposal.engine.hypothesis_prompts import (
                _split_direct_v3_hypothesis_context,
            )

            system_blocks, user_prompt = _split_direct_v3_hypothesis_context(
                structured
            )
        else:
            from scion.proposal.engine.code_prompts import _split_code_context

            system_blocks, user_prompt = _split_code_context(structured)
        return AuthoritativePromptProjection.create(
            structured_context=structured,
            system_blocks=system_blocks,
            user_prompt=user_prompt,
        )


def _checkpoint_a_context_snapshot(
    *,
    prompt: _generation._PromptSourceProjection,
    code: _generation._CodeSourceProjection,
    evidence: _generation._ProblemEvidenceProjection,
) -> tuple[ProposalContextSnapshot, dict[str, Any]]:
    _validate_projection_binding(prompt=prompt, code=code, evidence=evidence)
    owner_context = _decode_canonical_object(
        code.owner_context_json,
        label="hypothesis owner context",
    )
    branch, h_items, anchors = _validate_owner_context(
        owner_context,
        expected_h_bundle_digest=code.h_bundle_digest,
    )
    evidence_context = _decode_canonical_object(
        evidence.provider_context_json,
        label="hypothesis problem evidence",
    )
    evidence_governance = _decode_canonical_object(
        evidence.governance_json,
        label="hypothesis problem-evidence governance",
    )
    _validate_evidence_governance(
        evidence_context=evidence_context,
        evidence_context_json=evidence.provider_context_json,
        evidence_governance=evidence_governance,
        evidence_digest=evidence.evidence_digest,
        governance_json=evidence.governance_json,
    )
    _validate_tainted_context_keys(evidence_context)
    history = evidence_context.get("experiment_history", [])
    if type(history) is not list or any(type(item) is not dict for item in history):
        raise HypothesisPromptRejectedError(
            "hypothesis experiment_history must be a list of mappings"
        )
    _validate_history_references(
        history,
        branch_id=branch["branch_id"],
        hypothesis_ids=frozenset(item["hypothesis_id"] for item in h_items),
    )
    source_context, source_governance = _authoritative_source_context(
        code=code,
        branch=branch,
        anchors=anchors,
    )

    provider_context = dict(evidence_context)
    provider_context.setdefault("experiment_history", [])
    provider_context.update(
        {
            "branch_id": branch["branch_id"],
            "champion_stats": {
                "code_snapshot_hash": anchors["champion_code_snapshot_hash"],
                "selected_code_hash": code.code_hash,
                "selected_manifest_digest": code.selected_manifest_digest,
                "selected_snapshot_hash": code.snapshot_hash,
                "source_kind": code.source_kind,
                "version": anchors["champion_version"],
                "weight_revision": anchors["champion_weight_revision"],
            },
            "champion_version": anchors["champion_version"],
            "targetable_files": [
                entry["file_path"] for entry in source_context["files"]
            ],
        }
    )
    if code.source_kind == "base_champion":
        provider_context["champion_operators_code"] = source_context
    else:
        provider_context["branch_current_code"] = source_context

    governance = {
        "checkpoint_a_generation": {
            "owner_context": owner_context,
            "owner_context_sha256": hashlib.sha256(
                code.owner_context_json
            ).hexdigest(),
            "problem_evidence_digest": evidence.evidence_digest,
            "problem_evidence_governance": evidence_governance,
            "schema_version": "hypothesis-prompt-governance.v1",
            "source_manifest": source_governance,
        }
    }
    snapshot = _snapshot_from_owned_context(
        provider_context=provider_context,
        governance=governance,
    )
    reconstructed = snapshot.inputs.provider_context(
        include_renderer_inputs=True
    )
    if reconstructed != provider_context:
        raise HypothesisPromptRejectedError(
            "authoritative proposal snapshot changed provider context"
        )
    return snapshot, reconstructed


def _validate_projection_binding(
    *,
    prompt: _generation._PromptSourceProjection,
    code: _generation._CodeSourceProjection,
    evidence: _generation._ProblemEvidenceProjection,
) -> None:
    if (
        prompt.view_identity is not code.view_identity
        or prompt.view_identity is not evidence.view_identity
        or prompt.code_source is not evidence.code_source
        or prompt.branch_owner is not code.branch_owner
        or prompt.reservation_id != code.reservation_id
        or prompt.h_bundle_digest != code.h_bundle_digest
        or prompt.source_kind != code.source_kind
        or prompt.selected_manifest_digest != code.selected_manifest_digest
        or prompt.owner_context_json != code.owner_context_json
    ):
        raise HypothesisPromptRejectedError(
            "prompt source projections do not share one exact owner/source view"
        )


def _validate_owner_context(
    owner_context: dict[str, Any],
    *,
    expected_h_bundle_digest: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    _require_exact_keys(
        owner_context,
        _OWNER_CONTEXT_KEYS,
        label="hypothesis owner context",
    )
    if owner_context["schema_version"] != _OWNER_CONTEXT_SCHEMA:
        raise HypothesisPromptRejectedError(
            "hypothesis owner context schema is unsupported"
        )
    _required_text(owner_context["campaign_id"], label="campaign ID")
    if owner_context["runtime_mode"] != "direct_v3":
        raise HypothesisPromptRejectedError(
            "hypothesis owner context requires direct_v3 runtime"
        )
    _nonnegative_int(owner_context["root_generation"], label="root generation")

    branch = owner_context["branch"]
    _require_exact_keys(branch, _BRANCH_KEYS, label="owner Branch")
    _required_text(branch["branch_id"], label="Branch ID")
    _nonnegative_int(branch["owner_revision"], label="Branch owner revision")
    _digest(branch["storage_sha256"], label="Branch storage digest")
    _required_text(branch["state"], label="Branch state")
    _required_text(branch["branch_code_status"], label="Branch code status")
    _optional_digest(branch["current_code_hash"], label="current code hash")
    _optional_digest(branch["last_clean_code_hash"], label="last-clean code hash")
    _nonnegative_int(branch["base_champion_id"], label="base champion ID")
    _digest(branch["base_champion_hash"], label="base champion hash")
    _nonnegative_int(
        branch["base_champion_weight_revision"],
        label="base champion weight revision",
    )

    bundle = owner_context["h_bundle"]
    _require_exact_keys(bundle, _H_BUNDLE_KEYS, label="owner H bundle")
    bundle_digest = _digest(bundle["digest"], label="H-bundle digest")
    if bundle_digest != expected_h_bundle_digest:
        raise HypothesisPromptRejectedError(
            "owner H-bundle digest differs from the exact generation view"
        )
    count = _nonnegative_int(bundle["count"], label="H-bundle count")
    items = bundle["items"]
    if type(items) is not list or len(items) != count:
        raise HypothesisPromptRejectedError(
            "owner H-bundle count differs from its items"
        )
    previous = ""
    for item in items:
        _validate_h_item(item)
        hypothesis_id = item["hypothesis_id"]
        if previous and hypothesis_id <= previous:
            raise HypothesisPromptRejectedError(
                "owner H-bundle items must be unique and sorted"
            )
        previous = hypothesis_id

    prior_head = owner_context["prior_head"]
    if prior_head is not None:
        _validate_h_item(prior_head)
        if prior_head not in items:
            raise HypothesisPromptRejectedError(
                "owner prior head does not belong to the captured H bundle"
            )

    anchors = owner_context["anchors"]
    _require_exact_keys(anchors, _ANCHOR_KEYS, label="owner anchors")
    _required_text(anchors["problem_id"], label="problem ID")
    for name in (
        "problem_spec_hash",
        "split_manifest_hash",
        "seed_ledger_hash",
        "champion_code_snapshot_hash",
        "branch_base_champion_hash",
    ):
        _digest(anchors[name], label=name.replace("_", " "))
    for name in (
        "champion_version",
        "champion_weight_revision",
        "branch_base_champion_id",
    ):
        _nonnegative_int(anchors[name], label=name.replace("_", " "))
    if (
        anchors["champion_version"] != branch["base_champion_id"]
        or anchors["branch_base_champion_id"] != branch["base_champion_id"]
        or anchors["champion_weight_revision"]
        != branch["base_champion_weight_revision"]
        or anchors["champion_code_snapshot_hash"]
        != branch["base_champion_hash"]
        or anchors["branch_base_champion_hash"]
        != branch["base_champion_hash"]
    ):
        raise HypothesisPromptRejectedError(
            "owner champion anchors differ from the captured Branch"
        )
    return branch, items, anchors


def _validate_h_item(value: object) -> None:
    _require_exact_keys(value, _H_ITEM_KEYS, label="owner H item")
    assert type(value) is dict
    _required_text(value["hypothesis_id"], label="hypothesis ID")
    _nonnegative_int(value["owner_revision"], label="H owner revision")
    _digest(value["storage_sha256"], label="H storage digest")


def _validate_evidence_governance(
    *,
    evidence_context: dict[str, Any],
    evidence_context_json: bytes,
    evidence_governance: dict[str, Any],
    evidence_digest: str,
    governance_json: bytes,
) -> None:
    _require_exact_keys(
        evidence_governance,
        _EVIDENCE_GOVERNANCE_KEYS,
        label="problem-evidence governance",
    )
    if (
        evidence_governance["schema_version"]
        != "hypothesis-problem-evidence-governance.v1"
    ):
        raise HypothesisPromptRejectedError(
            "problem-evidence governance schema is unsupported"
        )
    configured_keys = evidence_governance["configured_keys"]
    if (
        type(configured_keys) is not list
        or configured_keys != sorted(evidence_context)
        or any(type(key) is not str for key in configured_keys)
    ):
        raise HypothesisPromptRejectedError(
            "problem-evidence governance keys differ from its context"
        )
    context_sha256 = hashlib.sha256(evidence_context_json).hexdigest()
    if (
        evidence_governance["configured_problem_evidence_sha256"]
        != context_sha256
        or evidence_governance["provider_context_sha256"] != context_sha256
    ):
        raise HypothesisPromptRejectedError(
            "problem-evidence governance digest differs from its context"
        )
    expected_evidence_digest = hashlib.sha256(
        b"hypothesis-problem-evidence.v1\0"
        + evidence_context_json
        + b"\0"
        + governance_json
    ).hexdigest()
    if evidence_digest != expected_evidence_digest:
        raise HypothesisPromptRejectedError(
            "problem-evidence leaf digest differs from its exact bytes"
        )


def _validate_tainted_context_keys(evidence_context: dict[str, Any]) -> None:
    for key in evidence_context:
        owner = HYPOTHESIS_CONTEXT_OWNER_MAP.get(key)
        if (
            key in _BOUND_OWNER_SOURCE_KEYS
            or owner is None
            or owner in {"audit", "governance", "static.source_index"}
        ):
            raise HypothesisPromptRejectedError(
                "problem evidence cannot supply owner/source field: " + key
            )
    _reject_nested_owner_source_fields(
        evidence_context,
        path="$.problem_evidence",
        root=True,
    )


def _reject_nested_owner_source_fields(
    value: object,
    *,
    path: str,
    root: bool = False,
) -> None:
    if type(value) is list:
        for index, child in enumerate(value):
            _reject_nested_owner_source_fields(
                child,
                path=f"{path}[{index}]",
            )
        return
    if type(value) is not dict:
        return
    for key, child in value.items():
        if not root and key in _NESTED_OWNER_SOURCE_KEYS:
            raise HypothesisPromptRejectedError(
                "problem evidence contains nested owner/source key at "
                f"{path}.{key}"
            )
        _reject_nested_owner_source_fields(
            child,
            path=f"{path}.{key}",
        )


def _validate_history_references(
    value: object,
    *,
    branch_id: str,
    hypothesis_ids: frozenset[str],
) -> None:
    if type(value) is list:
        for child in value:
            _validate_history_references(
                child,
                branch_id=branch_id,
                hypothesis_ids=hypothesis_ids,
            )
        return
    if type(value) is not dict:
        return
    for key, child in value.items():
        if key.endswith("hypothesis_id") and child is not None:
            if type(child) is not str or child not in hypothesis_ids:
                raise HypothesisPromptRejectedError(
                    "experiment_history references an uncaptured hypothesis"
                )
        if key in {"branch_id", "source_branch_id"} and child != branch_id:
            raise HypothesisPromptRejectedError(
                "experiment_history references another captured Branch"
            )
        _validate_history_references(
            child,
            branch_id=branch_id,
            hypothesis_ids=hypothesis_ids,
        )


def _authoritative_source_context(
    *,
    code: _generation._CodeSourceProjection,
    branch: dict[str, Any],
    anchors: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if code.source_kind == "base_champion":
        if code.snapshot_hash != branch["base_champion_hash"]:
            raise HypothesisPromptRejectedError(
                "base champion bytes differ from the owner anchor"
            )
    elif code.source_kind == "verified_branch_workspace":
        if (
            branch["state"] in {"stale", "stale_weight_update"}
            or branch["branch_code_status"] != "clean"
            or branch["current_code_hash"] is None
            or branch["current_code_hash"] != branch["last_clean_code_hash"]
            or code.code_hash != branch["current_code_hash"]
        ):
            raise HypothesisPromptRejectedError(
                "verified workspace bytes differ from the clean Branch anchor"
            )
    else:
        raise HypothesisPromptRejectedError(
            "hypothesis prompt has unsupported authoritative source kind"
        )

    files: list[dict[str, Any]] = []
    manifest_entries: list[dict[str, Any]] = []
    for path, content, digest, code_identity, snapshot_identity in code.entries:
        manifest_entries.append(
            {
                "code_identity": code_identity,
                "file_path": path,
                "sha256": digest,
                "snapshot_identity": snapshot_identity,
            }
        )
        if not code_identity:
            continue
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HypothesisPromptRejectedError(
                "authoritative code bytes are not UTF-8"
            ) from exc
        if text.encode("utf-8") != content:
            raise HypothesisPromptRejectedError(
                "authoritative code bytes do not round-trip through UTF-8"
            )
        files.append(
            {
                "content": text,
                "file_path": path,
                "sha256": digest,
            }
        )
    if not files:
        raise HypothesisPromptRejectedError(
            "authoritative source contains no provider-visible code bytes"
        )
    return (
        {
            "code_hash": code.code_hash,
            "files": files,
            "selected_manifest_digest": code.selected_manifest_digest,
            "snapshot_hash": code.snapshot_hash,
            "source_kind": code.source_kind,
        },
        {
            "code_hash": code.code_hash,
            "entries": manifest_entries,
            "selected_manifest_digest": code.selected_manifest_digest,
            "snapshot_hash": code.snapshot_hash,
            "source_kind": code.source_kind,
            "champion_code_snapshot_hash": anchors[
                "champion_code_snapshot_hash"
            ],
        },
    )


def _snapshot_from_owned_context(
    *,
    provider_context: dict[str, Any],
    governance: dict[str, Any],
) -> ProposalContextSnapshot:
    static: dict[str, dict[str, Any]] = {}
    evidence: dict[str, dict[str, Any]] = {}
    renderer: dict[str, Any] = {}
    field_order = tuple(sorted(provider_context))
    for key in field_order:
        owner = HYPOTHESIS_CONTEXT_OWNER_MAP.get(key)
        if owner is None or owner in {"audit", "governance"}:
            raise HypothesisPromptRejectedError(
                "provider context key has no exact hypothesis owner: " + key
            )
        if owner == "renderer_inputs":
            renderer[key] = provider_context[key]
            continue
        family, section = owner.split(".", 1)
        target = static if family == "static" else evidence
        target.setdefault(section, {})[key] = provider_context[key]
    try:
        inputs = SafeProposalInputs.create(
            phase="hypothesis",
            static_sections=static,
            evidence_sections=evidence,
            renderer_inputs=renderer,
            governance=governance,
            field_order=field_order,
        )
    except (TypeError, ValueError) as exc:
        raise HypothesisPromptRejectedError(
            "provider context cannot form a safe authoritative snapshot"
        ) from exc
    return ProposalContextSnapshot.from_safe_inputs(inputs)


def _decode_canonical_object(value: bytes, *, label: str) -> dict[str, Any]:
    if type(value) is not bytes or not value:
        raise HypothesisPromptRejectedError(f"{label} requires exact bytes")
    try:
        decoded = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HypothesisPromptRejectedError(f"{label} is malformed") from exc
    if type(decoded) is not dict or _canonical_json_bytes(decoded) != value:
        raise HypothesisPromptRejectedError(
            f"{label} is not one canonical JSON object"
        )
    return decoded


def _require_exact_keys(
    value: object,
    expected: frozenset[str],
    *,
    label: str,
) -> None:
    if type(value) is not dict or set(value) != expected:
        raise HypothesisPromptRejectedError(f"{label} has invalid exact schema")


def _required_text(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise HypothesisPromptRejectedError(f"{label} must be exact text")
    return value


def _digest(value: object, *, label: str) -> str:
    text = _required_text(value, label=label)
    if len(text) != 64 or text != text.lower():
        raise HypothesisPromptRejectedError(f"{label} must be lowercase SHA-256")
    try:
        int(text, 16)
    except ValueError as exc:
        raise HypothesisPromptRejectedError(
            f"{label} must be lowercase SHA-256"
        ) from exc
    return text


def _optional_digest(value: object, *, label: str) -> str | None:
    return None if value is None else _digest(value, label=label)


def _nonnegative_int(value: object, *, label: str) -> int:
    if type(value) is not int or not 0 <= value <= 2**63 - 1:
        raise HypothesisPromptRejectedError(
            f"{label} must be a nonnegative SQLite integer"
        )
    return value


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise HypothesisPromptRejectedError(
            "checkpoint-A prompt value cannot be canonically encoded"
        ) from exc
    return encoded.encode("utf-8")


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=False,
        separators=(",", ":"),
        allow_nan=False,
    )


__all__ = [
    "AuthoritativePromptProjection",
    "BoundHypothesisPrompt",
    "HypothesisPromptRejectedError",
    "HypothesisPromptSource",
    "HypothesisPromptUnknownError",
    "ProposalPromptProjectionAuthority",
]
