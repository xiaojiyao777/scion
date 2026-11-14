"""Direct V3 hypothesis-to-code proposal engine."""

from __future__ import annotations

from .code_prompts import _split_code_context
from .exceptions import ProposalValidationError
from .facade import (
    CreativeLayer,
    PromptTurnSnapshot,
    build_prompt_turn_snapshot,
)
from .hypothesis_prompts import (
    _split_direct_v3_hypothesis_context,
    _split_hypothesis_context,
)
from .parsing import _parse_hypothesis, _parse_patch

__all__ = [
    "CreativeLayer",
    "PromptTurnSnapshot",
    "ProposalValidationError",
    "_parse_hypothesis",
    "_parse_patch",
    "_split_code_context",
    "_split_direct_v3_hypothesis_context",
    "_split_hypothesis_context",
    "build_prompt_turn_snapshot",
]
