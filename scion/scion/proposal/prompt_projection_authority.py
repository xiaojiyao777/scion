"""Single authority for structured prompt projection and provider rendering."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from scion.proposal.context_snapshot import ProposalContextSnapshot
from scion.proposal.prompt_manifest import stable_digest


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
    "ProposalPromptProjectionAuthority",
]
