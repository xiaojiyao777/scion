"""HypothesisStore — thin re-export from scion.lineage.branch_store.

The authoritative implementation lives in scion.lineage.branch_store.HypothesisStore.
This module exists for backwards compatibility with callers that import from
scion.memory.hypothesis_store.
"""
from scion.lineage.branch_store import HypothesisStore  # noqa: F401

__all__ = ["HypothesisStore"]
