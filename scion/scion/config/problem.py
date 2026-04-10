from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Optional, Literal, Set, Tuple
import yaml
import os


class ParameterSearchConfig(BaseModel):
    enabled: bool = True
    trigger: Literal["on_promote"] = "on_promote"
    target: Literal["operator_weights"] = "operator_weights"
    strategy: Literal["random_local", "bayesian"] = "random_local"
    n_initial_random: int = 8
    n_iterations: int = 8
    n_eval_seeds: int = 2
    weight_bounds: Tuple[float, float] = (0.05, 5.0)
    eval_cases: List[str] = Field(default_factory=list)


class SolverConfig(BaseModel):
    time_limit_sec: int = 300
    max_iter: int = 1000

class SearchSpace(BaseModel):
    editable: List[str]
    frozen: List[str]
    import_whitelist: List[str]

class ProblemSpec(BaseModel):
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

class ProtocolConfig(BaseModel):
    screening_n: int = 6
    screening_win_rate_threshold: float = 0.66
    validation_n: int = 12
    validation_win_rate_threshold: float = 0.66
    frozen_n: int = 24
    min_practical_delta: float = 0.001
    
    @classmethod
    def from_yaml(cls, path: str) -> ProtocolConfig:
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return cls(**data)

class SplitManifest(BaseModel):
    screening: List[str]
    validation: List[str]
    frozen: List[str]

    @field_validator('screening', 'validation', 'frozen')
    @classmethod
    def check_disjoint(cls, v, info):
        # We'll check all splits in a cross-validator
        return v

    def validate_disjoint(self):
        s = set(self.screening)
        v = set(self.validation)
        f = set(self.frozen)
        
        # Frozen must be disjoint from both screening and validation
        # (holdout integrity). Screening/validation overlap is allowed
        # — validation uses different seeds to test stability.
        if not s.isdisjoint(f):
            raise ValueError(f"Screening and Frozen splits overlap: {s & f}")
        if not v.isdisjoint(f):
            raise ValueError(f"Validation and Frozen splits overlap: {v & f}")

    @classmethod
    def from_yaml(cls, path: str) -> SplitManifest:
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        manifest = cls(**data)
        manifest.validate_disjoint()
        return manifest

class SeedLedgerConfig(BaseModel):
    screening: List[int]
    validation: List[int]
    frozen: List[int]

    @classmethod
    def from_yaml(cls, path: str) -> SeedLedgerConfig:
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return cls(**data)
