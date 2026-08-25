"""Public API for provider- and solver-free M32 effectiveness scoring."""

from .comparison import compare_five_block_research_effectiveness
from .endpoints import calculate_research_effectiveness
from .models import (
    BLOCK_UNSCORABLE,
    CANDIDATE_FEASIBILITY_EVIDENCE_UNAVAILABLE,
    HISTORY_REPLAY_BASIS_UNAVAILABLE,
    INITIAL_CELL_DATA_UNAVAILABLE,
    SCIENTIFIC_DELEGATION_INCOMPLETE,
    InitialCell,
    LoadedHistoryAvailable,
    LoadedHistoryUnavailable,
    MatchedResearchEffectivenessBlock,
    ResearchEffectivenessArmArtifacts,
    ResearchEffectivenessExpectation,
    ResearchEffectivenessInputError,
)

__all__ = [
    "BLOCK_UNSCORABLE",
    "CANDIDATE_FEASIBILITY_EVIDENCE_UNAVAILABLE",
    "HISTORY_REPLAY_BASIS_UNAVAILABLE",
    "INITIAL_CELL_DATA_UNAVAILABLE",
    "SCIENTIFIC_DELEGATION_INCOMPLETE",
    "InitialCell",
    "LoadedHistoryAvailable",
    "LoadedHistoryUnavailable",
    "MatchedResearchEffectivenessBlock",
    "ResearchEffectivenessArmArtifacts",
    "ResearchEffectivenessExpectation",
    "ResearchEffectivenessInputError",
    "calculate_research_effectiveness",
    "compare_five_block_research_effectiveness",
]
