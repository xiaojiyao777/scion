"""Pure structured-context projection into provider-visible prompt bytes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from scion.proposal.context_snapshot import ProposalContextSnapshot


@dataclass(frozen=True)
class PromptProjection:
    """One immutable, order-preserving prompt projection."""

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
    ) -> "PromptProjection":
        return cls(
            structured_context_json=_json(structured_context),
            system_blocks_json=_json(list(system_blocks)),
            user_prompt=str(user_prompt),
        )

    @property
    def structured_context(self) -> dict[str, Any]:
        value = json.loads(self.structured_context_json)
        if not isinstance(value, dict):
            raise TypeError("structured prompt context is not a mapping")
        return value

    @property
    def system_blocks(self) -> tuple[dict[str, Any], ...]:
        value = json.loads(self.system_blocks_json)
        if not isinstance(value, list) or not all(
            isinstance(block, dict) for block in value
        ):
            raise TypeError("prompt system blocks are invalid")
        return tuple(value)


def project_prompt(
    render_kind: str,
    snapshot: ProposalContextSnapshot,
) -> PromptProjection:
    """Render one hypothesis or code prompt from a value snapshot."""

    kind = str(render_kind)
    if kind not in {"hypothesis", "code"}:
        raise ValueError(f"unsupported prompt kind: {kind}")
    if snapshot.phase != kind:
        raise ValueError(f"{kind} prompt requires a {kind} context snapshot")

    structured = snapshot.inputs.provider_context(include_renderer_inputs=True)
    if kind == "hypothesis":
        from scion.proposal.engine.hypothesis_prompts import (
            _split_direct_v3_hypothesis_context,
        )

        system_blocks, user_prompt = _split_direct_v3_hypothesis_context(structured)
    else:
        from scion.proposal.engine.code_prompts import _split_code_context

        system_blocks, user_prompt = _split_code_context(structured)
    return PromptProjection.create(
        structured_context=structured,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )


def _json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=False,
        separators=(",", ":"),
        allow_nan=False,
    )


__all__ = ["PromptProjection", "project_prompt"]
