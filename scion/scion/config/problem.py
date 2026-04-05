from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Optional, Literal, Set
import yaml
import os

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
    operators_dir: str = "operators"
    data_dir: str = "data"
    oracle_path: str = "oracle.py"
    solver_path: str = "solver.py"
    operator_categories: List[str]
    search_space: SearchSpace
    solver: SolverConfig = Field(default_factory=SolverConfig)

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
        
        if not s.isdisjoint(v):
            raise ValueError(f"Screening and Validation splits overlap: {s & v}")
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
