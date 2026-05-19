"""CVRP contract-check result payloads."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SolverDesignIntegrationResult:
    passed: bool
    detail: str
