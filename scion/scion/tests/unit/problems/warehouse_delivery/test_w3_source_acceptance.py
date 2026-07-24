from __future__ import annotations

import json

import pytest

from scion.problems.warehouse_delivery.w3_source_acceptance import (
    FixedSourceReviewClosure,
    RootFixedSourceAcceptanceReceipt,
    W3_SOURCE_ACCEPTANCE_LOGICAL_PATH,
    WarehouseW3SourceAcceptanceError,
)
from scion.tests.unit.problems.warehouse_delivery.test_w3_installation import (
    _canonical,
    _prepared_inputs,
)


def _accepted(tmp_path, monkeypatch):
    _intent, source, objects, *_rest = _prepared_inputs(tmp_path, monkeypatch)
    sealed = next(
        item
        for item in objects
        if item.adapter.logical_path == W3_SOURCE_ACCEPTANCE_LOGICAL_PATH
    )
    return source, RootFixedSourceAcceptanceReceipt.from_bytes(sealed.raw)


def test_fixed_source_acceptance_round_trip_closes_two_independent_reviews(
    tmp_path,
    monkeypatch,
) -> None:
    source, accepted = _accepted(tmp_path, monkeypatch)

    assert RootFixedSourceAcceptanceReceipt.from_bytes(accepted.raw) == accepted
    assert accepted.source_receipt == source.receipt
    assert tuple(item.review_scope for item in accepted.reviews) == (
        "launch_readiness",
        "root_installation",
    )
    assert (
        len({(item.reviewer_identity, item.task_identity) for item in accepted.reviews})
        == 2
    )


def test_fixed_source_review_refuses_nonzero_p0_or_p1(
    tmp_path,
    monkeypatch,
) -> None:
    _source, accepted = _accepted(tmp_path, monkeypatch)
    value = json.loads(accepted.reviews[0].raw)
    value["p1_open"] = 1

    with pytest.raises(
        WarehouseW3SourceAcceptanceError,
        match="zero-P0/zero-P1",
    ):
        FixedSourceReviewClosure.from_bytes(_canonical(value))


def test_fixed_source_acceptance_refuses_one_reviewer_for_both_scopes(
    tmp_path,
    monkeypatch,
) -> None:
    source, accepted = _accepted(tmp_path, monkeypatch)
    first, second = accepted.reviews
    duplicate_identity = FixedSourceReviewClosure.create(
        review_scope=first.review_scope,
        reviewer_identity=second.reviewer_identity,
        task_identity=second.task_identity,
        source_commit=first.source_commit,
        source_tree=first.source_tree,
        source_inventory_sha256=first.source_inventory_sha256,
        report_sha256=first.report_sha256,
        p0_open=0,
        p1_open=0,
        completed_at_utc=first.completed_at_utc,
    )

    with pytest.raises(
        WarehouseW3SourceAcceptanceError,
        match="dependency binding differs",
    ):
        RootFixedSourceAcceptanceReceipt.create(
            source=source,
            root_git_verification=accepted.root_git_verification,
            reviews=(duplicate_identity, second),
            accepted_at_utc=accepted.accepted_at_utc,
        )
