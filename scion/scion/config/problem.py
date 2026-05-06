from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Any, List, Dict, Optional, Literal, Set, Tuple
import yaml
import os

# Re-export authoritative schema — these are the ONLY authoritative implementations.
# Old code that imported simplified versions from this module will get the real ones.
from scion.config.protocol_config import ProtocolConfig
from scion.config.protocol_config import RuntimeGovernanceConfig
from scion.config.split_manifest import SplitManifest
from scion.config.seed_ledger import SeedLedger

# Backward-compatible alias: old code used SeedLedgerConfig, now it maps to SeedLedger
SeedLedgerConfig = SeedLedger

__all__ = [
    "ProtocolConfig",
    "RuntimeGovernanceConfig",
    "SplitManifest",
    "SeedLedger",
    "SeedLedgerConfig",
    "ProblemSpec",
    "SearchSpace",
    "SolverConfig",
    "ParameterSearchConfig",
]


class _StrictBase(BaseModel):
    """Pydantic base with strict schema — unknown YAML fields raise instead of being silently dropped.

    v0.3 §11.2 tech debt: ProblemSpec strict mode.
    """
    model_config = ConfigDict(extra="forbid")


class ParameterSearchConfig(_StrictBase):
    enabled: bool = True
    trigger: Literal["on_promote"] = "on_promote"
    target: Literal["operator_weights"] = "operator_weights"
    strategy: Literal["random_local", "bayesian"] = "random_local"
    execution: Literal["async", "sync"] = "async"
    final_wait_timeout_sec: Optional[float] = 600.0
    n_initial_random: int = 8
    n_iterations: int = 16
    n_eval_seeds: int = 2
    weight_bounds: Tuple[float, float] = (0.05, 5.0)
    eval_cases: List[str] = Field(default_factory=list)


class SolverConfig(_StrictBase):
    time_limit_sec: int = 300
    max_iter: int = 1000

class SearchSpace(_StrictBase):
    editable: List[str]
    frozen: List[str]
    import_whitelist: List[str]

class ProblemSpec(_StrictBase):
    name: str
    root_dir: str
    description: str = ""
    operators_dir: str = "operators"
    data_dir: str = "data"
    oracle_path: str = "oracle.py"
    solver_path: str = "solver.py"
    canary_case_path: str = ""  # absolute path to a small instance for verification canary runs
    unit_test_path: str = ""   # path (relative to root_dir or absolute) to unit test file
    regression_test_path: str = ""  # path (relative to root_dir or absolute) to regression test file
    operator_categories: List[str]
    research_surfaces: List[Any] = Field(default_factory=list)
    runtime_failure_guidance: List[Any] = Field(default_factory=list)
    search_space: SearchSpace
    solver: SolverConfig = Field(default_factory=SolverConfig)
    parameter_search: ParameterSearchConfig = Field(default_factory=ParameterSearchConfig)

    @property
    def operator_pool_categories(self) -> List[str]:
        return self.operator_categories

    @property
    def search_space_editable(self) -> List[str]:
        return self.search_space.editable

    @property
    def search_space_frozen(self) -> List[str]:
        return self.search_space.frozen

    @property
    def import_whitelist(self) -> List[str]:
        return self.search_space.import_whitelist

    @classmethod
    def from_yaml(cls, path: str) -> ProblemSpec:
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        # Ensure root_dir is set correctly if not in YAML
        if 'root_dir' not in data:
            data['root_dir'] = os.path.dirname(os.path.abspath(path))
        return cls(**data)
