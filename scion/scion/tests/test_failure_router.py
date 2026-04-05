"""Tests for scion/failure/router.py — FailureRouter."""
from __future__ import annotations
import uuid
import pytest
from datetime import datetime

from scion.core.models import Branch, BranchState, FailureEvent
from scion.failure.router import FailureRouter, RetryConfig


def _branch(retry_count: int = 0) -> Branch:
    return Branch(
        branch_id=str(uuid.uuid4()),
        state=BranchState.EXPLORE,
        base_champion_id=0,
        base_champion_hash="hash0",
        retry_count=retry_count,
    )


def _failure(category: str) -> FailureEvent:
    return FailureEvent(category=category, detail="test detail")


router = FailureRouter(RetryConfig(max_llm_retries=3, max_infra_retries=5))


# ─────────────────────────────────────────────────────────────────────────────
# Proposal / Contract → retry_llm
# ─────────────────────────────────────────────────────────────────────────────

def test_proposal_failure_retry_llm():
    action = router.route(_failure("proposal"), _branch(retry_count=0))
    assert action.action == "retry_llm"
    assert action.consumes_budget is False
    assert action.writes_hypothesis_memory is False


def test_contract_failure_retry_llm():
    action = router.route(_failure("contract"), _branch(retry_count=1))
    assert action.action == "retry_llm"


def test_proposal_exhausted_retries_discard():
    action = router.route(_failure("proposal"), _branch(retry_count=10))
    assert action.action == "discard"
    assert action.max_retries_remaining == 0


# ─────────────────────────────────────────────────────────────────────────────
# Verification-Light → retry_llm
# ─────────────────────────────────────────────────────────────────────────────

def test_verification_light_retry_llm():
    action = router.route(_failure("verification_light"), _branch(retry_count=0))
    assert action.action == "retry_llm"
    assert action.consumes_budget is False


def test_verification_light_exhausted_discard():
    action = router.route(_failure("verification_light"), _branch(retry_count=10))
    assert action.action == "discard"
    assert action.consumes_budget is True
    assert action.writes_hypothesis_memory is True


# ─────────────────────────────────────────────────────────────────────────────
# Verification-Heavy → discard
# ─────────────────────────────────────────────────────────────────────────────

def test_verification_heavy_discard():
    action = router.route(_failure("verification_heavy"), _branch())
    assert action.action == "discard"
    assert action.consumes_budget is True
    assert action.writes_hypothesis_memory is True
    assert action.max_retries_remaining == 0


# ─────────────────────────────────────────────────────────────────────────────
# Infra → retry_infra
# ─────────────────────────────────────────────────────────────────────────────

def test_infra_retry():
    action = router.route(_failure("infra"), _branch(retry_count=0))
    assert action.action == "retry_infra"
    assert action.consumes_budget is False
    assert action.writes_hypothesis_memory is False


# ─────────────────────────────────────────────────────────────────────────────
# Evaluation → discard
# ─────────────────────────────────────────────────────────────────────────────

def test_evaluation_discard():
    action = router.route(_failure("evaluation"), _branch())
    assert action.action == "discard"
    assert action.consumes_budget is True
    assert action.writes_hypothesis_memory is True
