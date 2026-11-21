"""Explicit public-research opt-in; no scientific budget defaults."""
from dataclasses import dataclass
from pathlib import Path

from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.observation.sandbox import RunLimits
from scion.observation.service import ObservationBudget
from scion.problem.public_input import decode_public_json


class PublicResearchStop(Exception):
    def __init__(self, reason_code, *, phase="setup"):
        outcome = {
            "PROPOSAL_LOCAL_LIMIT": ExecutionOutcome.RESEARCH_REJECTED,
            "GLOBAL_RESEARCH_LIMIT": ExecutionOutcome.RESOURCE_EXHAUSTED,
            "INITIAL_CONTEXT_LIMIT": ExecutionOutcome.RESOURCE_EXHAUSTED,
            "ISOLATION_UNAVAILABLE": ExecutionOutcome.BLOCKED_INFRA,
            "PUBLIC_CLOSURE_INVALID": ExecutionOutcome.BLOCKED_INFRA,
            "PERSISTENCE_ERROR": ExecutionOutcome.BLOCKED_INFRA,
            "USER_INTERRUPTED": ExecutionOutcome.INTERRUPTED,
            "EXTERNAL_STOP_REQUESTED": ExecutionOutcome.INTERRUPTED,
            "OUTER_HARDWALL_EXCEEDED": ExecutionOutcome.INTERRUPTED,
            "PROVIDER_CALL_CAP_EXHAUSTED": ExecutionOutcome.RESOURCE_EXHAUSTED,
        }.get(reason_code, ExecutionOutcome.NOT_EVALUATED)
        self.record = ExecutionOutcomeRecord(outcome, reason_code,
            provenance={"stage": "public_research", "phase": phase})
        super().__init__(reason_code)


TERMINAL_REASONS = frozenset({
    "PROPOSAL_LOCAL_LIMIT", "GLOBAL_RESEARCH_LIMIT", "INITIAL_CONTEXT_LIMIT",
    "ISOLATION_UNAVAILABLE", "PUBLIC_CLOSURE_INVALID", "PERSISTENCE_ERROR",
    "INTERNAL_ERROR", "USER_INTERRUPTED",
})


@dataclass(frozen=True)
class PublicResearchConfig:
    public_observation_enabled: bool = False
    research_materials_enabled: bool = False
    budget: ObservationBudget | None = None

    def __post_init__(self):
        if (type(self.public_observation_enabled) is not bool
                or type(self.research_materials_enabled) is not bool
                or ((self.public_observation_enabled or self.research_materials_enabled) and type(self.budget) is not ObservationBudget)
                or (not (self.public_observation_enabled or self.research_materials_enabled) and self.budget is not None)):
            raise PublicResearchStop("OBS_CONFIG_INVALID")


def normalize_public_research(value):
    if value is None:
        return PublicResearchConfig()
    if type(value) is PublicResearchConfig:
        return value
    try:
        if type(value) is not dict:
            raise ValueError()
        if set(value) not in (
            {"public_observation_enabled", "research_materials_enabled"},
            {"public_observation_enabled", "research_materials_enabled", "budget"},
        ):
            raise ValueError()
        kwargs = dict(value)
        if "budget" in kwargs:
            data = dict(kwargs["budget"])
            data["per_action"] = RunLimits(**data["per_action"])
            data["checker"] = RunLimits(**data["checker"])
            kwargs["budget"] = ObservationBudget(**data)
        return PublicResearchConfig(**kwargs)
    except (TypeError, ValueError, KeyError):
        raise PublicResearchStop("OBS_CONFIG_INVALID") from None


def load_public_research(path: Path):
    try:
        with path.open("rb") as stream:
            raw = stream.read(65537)
        return normalize_public_research(decode_public_json(raw, max_bytes=65536,
            max_depth=8, max_collection_items=128))
    except (OSError, ValueError):
        raise PublicResearchStop("OBS_CONFIG_INVALID") from None
