from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

from scion.core.models import FailureEvent, Branch


@dataclass
class RetryConfig:
    max_llm_retries: int = 3
    max_infra_retries: int = 5


@dataclass(frozen=True)
class FailureAction:
    action: Literal["retry_llm", "retry_infra", "discard", "abandon"]
    consumes_budget: bool
    writes_hypothesis_memory: bool
    max_retries_remaining: int


class FailureRouter:
    """
    Routes failure events to appropriate actions based on failure category.

    Four-tier classification:
      proposal/contract    → retry_llm (no budget cost)
      verification_light   → retry_llm (no budget cost); discard if exhausted
      verification_heavy   → discard (consumes budget, records hypothesis memory)
      infra                → retry_infra (no budget cost)
      evaluation           → discard (consumes budget, records hypothesis memory)
    """

    def __init__(self, retry_config: RetryConfig | None = None) -> None:
        self.retry_config = retry_config or RetryConfig()

    def route(self, failure: FailureEvent, branch: Branch) -> FailureAction:
        cat = failure.category

        if cat in ("proposal", "contract"):
            remaining = max(
                0, self.retry_config.max_llm_retries - branch.retry_count
            )
            if remaining > 0:
                return FailureAction(
                    action="retry_llm",
                    consumes_budget=False,
                    writes_hypothesis_memory=False,
                    max_retries_remaining=remaining,
                )
            return FailureAction(
                action="discard",
                consumes_budget=False,
                writes_hypothesis_memory=False,
                max_retries_remaining=0,
            )

        elif cat == "verification_light":
            remaining = max(
                0, self.retry_config.max_llm_retries - branch.retry_count
            )
            if remaining > 0:
                return FailureAction(
                    action="retry_llm",
                    consumes_budget=False,
                    writes_hypothesis_memory=False,
                    max_retries_remaining=remaining,
                )
            return FailureAction(
                action="discard",
                consumes_budget=True,
                writes_hypothesis_memory=True,
                max_retries_remaining=0,
            )

        elif cat == "verification_heavy":
            return FailureAction(
                action="discard",
                consumes_budget=True,
                writes_hypothesis_memory=True,
                max_retries_remaining=0,
            )

        elif cat == "infra":
            remaining = max(
                0, self.retry_config.max_infra_retries - branch.retry_count
            )
            return FailureAction(
                action="retry_infra",
                consumes_budget=False,
                writes_hypothesis_memory=False,
                max_retries_remaining=remaining,
            )

        elif cat == "evaluation":
            return FailureAction(
                action="discard",
                consumes_budget=True,
                writes_hypothesis_memory=True,
                max_retries_remaining=0,
            )

        # Unknown category — treat as heavy failure
        return FailureAction(
            action="discard",
            consumes_budget=True,
            writes_hypothesis_memory=True,
            max_retries_remaining=0,
        )
