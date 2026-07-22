"""Warehouse W3 case-cluster analysis, closure, and immutable replay."""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from random import Random
from typing import Any, Mapping, Sequence

from scion.problems.warehouse_delivery.w3_fixed_arm import (
    ARM_ORDER,
    canonical_sha256,
    render_json,
    sha256_bytes,
)
from scion.problems.warehouse_delivery.w3_validation import validate_replay_rows

RESULTS_SCHEMA = "scion.warehouse_w3_fixed_arm_results.v1"
REPORT_SCHEMA = "scion.warehouse_w3_fixed_arm_report.v1"
RECEIPT_SCHEMA = "scion.warehouse_w3_fixed_arm_receipt.v1"
CONTRASTS = (
    ("destroy_only", "champion"),
    ("merge_only", "champion"),
    ("cumulative", "champion"),
    ("destroy_only", "cumulative"),
    ("merge_only", "cumulative"),
)
LOCK_POLICIES = {
    "champion": "baseline_merge_may_move_intact_locked_group",
    "destroy_only": "r3_destroy_fixed_original_and_champion_merge_group_movable",
    "merge_only": "r3_merge_source_unlocked_and_fixed_original_consistency",
    "cumulative": "r3_destroy_and_r3_merge_conservative_fixed_original",
}


def _quality_outcome(candidate: Mapping[str, Any], reference: Mapping[str, Any]) -> str:
    candidate_value = (
        candidate["objective"]["subcategory_splits"],
        candidate["objective"]["total_cost"],
    )
    reference_value = (
        reference["objective"]["subcategory_splits"],
        reference["objective"]["total_cost"],
    )
    if candidate_value < reference_value:
        return "win"
    if candidate_value > reference_value:
        return "loss"
    return "tie"


def _median(values: Sequence[float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def _bootstrap(values: Sequence[float], contract: Mapping[str, Any]) -> dict[str, Any]:
    if not values:
        return {"median": 0.0, "ci_low": 0.0, "ci_high": 0.0}
    rng = Random(int(contract["seed"]))
    draws = int(contract["draws"])
    alpha = float(contract["alpha"])
    count = len(values)
    medians = sorted(
        _median([values[rng.randrange(count)] for _ in range(count)])
        for _ in range(draws)
    )
    low_index = max(0, int(alpha / 2 * draws))
    high_index = min(draws - 1, int((1 - alpha / 2) * draws) - 1)
    return {
        "median": _median(values),
        "ci_low": medians[low_index],
        "ci_high": medians[high_index],
    }


def case_majority(outcomes: Sequence[str]) -> str:
    wins = outcomes.count("win")
    losses = outcomes.count("loss")
    if wins > len(outcomes) / 2:
        return "win"
    if losses > len(outcomes) / 2:
        return "loss"
    return "tie"


def _contrast(
    rows: Sequence[Mapping[str, Any]],
    *,
    candidate_arm: str,
    reference_arm: str,
    case_ids: Sequence[str],
    bootstrap: Mapping[str, Any],
) -> dict[str, Any]:
    requested = set(case_ids)
    case_order = {case_id: index for index, case_id in enumerate(case_ids)}
    by_cell_arm = {(row["cell_ordinal"], row["arm"]): row for row in rows}
    candidate_rows = [
        row
        for row in rows
        if row["arm"] == candidate_arm
        and row["case_identity"]["stable_case_id"] in requested
    ]
    seed_rows: list[dict[str, Any]] = []
    for candidate in candidate_rows:
        reference = by_cell_arm[(candidate["cell_ordinal"], reference_arm)]
        eligible_key = (
            "r3_merge_eligible_directed_pairs"
            if candidate_arm in {"merge_only", "cumulative"}
            else "champion_merge_eligible_directed_pairs"
        )
        seed_rows.append(
            {
                "cell_ordinal": candidate["cell_ordinal"],
                "stable_case_id": candidate["case_identity"]["stable_case_id"],
                "seed": candidate["seed"],
                "outcome": _quality_outcome(candidate, reference),
                "split_delta_reference_minus_candidate": (
                    reference["objective"]["subcategory_splits"]
                    - candidate["objective"]["subcategory_splits"]
                ),
                "cost_delta_reference_minus_candidate": (
                    reference["objective"]["total_cost"]
                    - candidate["objective"]["total_cost"]
                ),
                "runtime_delta_ns_candidate_minus_reference": (
                    candidate["objective"]["runner_wall_time_ns"]
                    - reference["objective"]["runner_wall_time_ns"]
                ),
                "candidate_position": candidate["arm_position"],
                "reference_position": reference["arm_position"],
                "candidate_oracle_feasible": candidate["oracle"]["feasible"],
                "reference_oracle_feasible": reference["oracle"]["feasible"],
                "candidate_final_intact_locked_groups": candidate["locked_groups"][
                    "final_intact_locked_group_count"
                ],
                "reference_final_intact_locked_groups": reference["locked_groups"][
                    "final_intact_locked_group_count"
                ],
                "candidate_whole_groups_moved": candidate["locked_groups"][
                    "whole_groups_moved_count"
                ],
                "reference_whole_groups_moved": reference["locked_groups"][
                    "whole_groups_moved_count"
                ],
                "candidate_split_group_violations": candidate["locked_groups"][
                    "split_group_count"
                ],
                "reference_split_group_violations": reference["locked_groups"][
                    "split_group_count"
                ],
                "candidate_operator_diagnostics_status": candidate[
                    "operator_runtime_diagnostics"
                ]["status"],
                "reference_operator_diagnostics_status": reference[
                    "operator_runtime_diagnostics"
                ]["status"],
                "lock_bearing": (
                    candidate["locked_groups"]["final_intact_locked_group_count"] > 0
                ),
                "formal_compatible_directed_pairs": candidate["merge_pair_counts"][
                    "formal_compatible_directed_pairs"
                ],
                "candidate_arm_eligible_directed_pairs": candidate["merge_pair_counts"][
                    eligible_key
                ],
            }
        )
    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in seed_rows:
        by_case[row["stable_case_id"]].append(row)
    case_rows: list[dict[str, Any]] = []
    for case_id in sorted(by_case, key=case_order.__getitem__):
        values = by_case[case_id]
        case_rows.append(
            {
                "stable_case_id": case_id,
                "seed_count": len(values),
                "outcome": case_majority([row["outcome"] for row in values]),
                "split_delta_reference_minus_candidate": _median(
                    [row["split_delta_reference_minus_candidate"] for row in values]
                ),
                "cost_delta_reference_minus_candidate": _median(
                    [row["cost_delta_reference_minus_candidate"] for row in values]
                ),
                "runtime_delta_ns_candidate_minus_reference": _median(
                    [
                        row["runtime_delta_ns_candidate_minus_reference"]
                        for row in values
                    ]
                ),
                "lock_bearing": values[0]["lock_bearing"],
                "formal_compatible_directed_pairs": values[0][
                    "formal_compatible_directed_pairs"
                ],
                "candidate_arm_eligible_directed_pairs": values[0][
                    "candidate_arm_eligible_directed_pairs"
                ],
                "candidate_whole_groups_moved_median": _median(
                    [row["candidate_whole_groups_moved"] for row in values]
                ),
                "reference_whole_groups_moved_median": _median(
                    [row["reference_whole_groups_moved"] for row in values]
                ),
            }
        )
    counts = Counter(row["outcome"] for row in case_rows)
    pair_counts = Counter(row["outcome"] for row in seed_rows)
    return {
        "candidate_arm": candidate_arm,
        "reference_arm": reference_arm,
        "case_counts": {
            "wins": counts["win"],
            "losses": counts["loss"],
            "ties": counts["tie"],
            "total": len(case_rows),
        },
        "seed_pair_counts": {
            "wins": pair_counts["win"],
            "losses": pair_counts["loss"],
            "ties": pair_counts["tie"],
            "total": len(seed_rows),
        },
        "integrity_and_mechanism": {
            "candidate_oracle_feasible_rows": sum(
                row["candidate_oracle_feasible"] for row in seed_rows
            ),
            "reference_oracle_feasible_rows": sum(
                row["reference_oracle_feasible"] for row in seed_rows
            ),
            "candidate_final_intact_locked_group_sum": sum(
                row["candidate_final_intact_locked_groups"] for row in seed_rows
            ),
            "reference_final_intact_locked_group_sum": sum(
                row["reference_final_intact_locked_groups"] for row in seed_rows
            ),
            "candidate_whole_groups_moved_sum": sum(
                row["candidate_whole_groups_moved"] for row in seed_rows
            ),
            "reference_whole_groups_moved_sum": sum(
                row["reference_whole_groups_moved"] for row in seed_rows
            ),
            "candidate_split_group_violation_sum": sum(
                row["candidate_split_group_violations"] for row in seed_rows
            ),
            "reference_split_group_violation_sum": sum(
                row["reference_split_group_violations"] for row in seed_rows
            ),
            "candidate_operator_diagnostics_status": dict(
                Counter(
                    row["candidate_operator_diagnostics_status"] for row in seed_rows
                )
            ),
            "reference_operator_diagnostics_status": dict(
                Counter(
                    row["reference_operator_diagnostics_status"] for row in seed_rows
                )
            ),
        },
        "case_cluster_bootstrap": {
            "subcategory_splits": _bootstrap(
                [row["split_delta_reference_minus_candidate"] for row in case_rows],
                bootstrap,
            ),
            "total_cost": _bootstrap(
                [row["cost_delta_reference_minus_candidate"] for row in case_rows],
                bootstrap,
            ),
            "runtime_ns": _bootstrap(
                [
                    row["runtime_delta_ns_candidate_minus_reference"]
                    for row in case_rows
                ],
                bootstrap,
            ),
        },
        "strata": {
            "lock_bearing": dict(
                Counter(row["outcome"] for row in case_rows if row["lock_bearing"])
            ),
            "lock_free": dict(
                Counter(row["outcome"] for row in case_rows if not row["lock_bearing"])
            ),
            "formal_pair_zero": dict(
                Counter(
                    row["outcome"]
                    for row in case_rows
                    if row["formal_compatible_directed_pairs"] == 0
                )
            ),
            "formal_pair_nonzero": dict(
                Counter(
                    row["outcome"]
                    for row in case_rows
                    if row["formal_compatible_directed_pairs"] > 0
                )
            ),
        },
        "case_rows": case_rows,
        "seed_rows": seed_rows,
    }


def _hierarchical(contrast: Mapping[str, Any]) -> dict[str, Any]:
    for metric in ("subcategory_splits", "total_cost"):
        summary = contrast["case_cluster_bootstrap"][metric]
        median = float(summary["median"])
        low = float(summary["ci_low"])
        high = float(summary["ci_high"])
        if low > 0:
            return {"status": "positive", "metric": metric, **summary}
        if high < 0:
            return {"status": "negative", "metric": metric, **summary}
        if low == 0 and high == 0 and median == 0:
            continue
        return {"status": "uncertain", "metric": metric, **summary}
    return {
        "status": "tie",
        "metric": "total_cost",
        "median": 0.0,
        "ci_low": 0.0,
        "ci_high": 0.0,
    }


def screening_gate_from_protocol(
    contrast: Mapping[str, Any], contract: Mapping[str, Any]
) -> dict[str, Any]:
    """Exact quality-only projection of sealed ``protocol.gates.screening_gate``."""

    cases = contrast["case_counts"]
    pairs = contrast["seed_pair_counts"]
    hierarchical = _hierarchical(contrast)
    win_rate = cases["wins"] / cases["total"] if cases["total"] else 0.0
    median = float(hierarchical["median"])
    threshold = float(contract["screening"]["win_rate_min"])
    practical = float(contract["screening"]["practical_delta_min"])
    reason: tuple[str, ...]
    if win_rate >= threshold and median >= practical:
        outcome = "pass"
        reason = ("SCREENING_PASS",)
    else:
        signal_wins = pairs["wins"] if pairs["total"] else cases["wins"]
        signal_losses = pairs["losses"] if pairs["total"] else cases["losses"]
        signal_ties = pairs["ties"] if pairs["total"] else cases["ties"]
        observed = signal_wins + signal_losses + signal_ties
        loss_heavy = (signal_wins == 0 and signal_losses > 0) or (
            observed > 0
            and signal_losses > signal_wins
            and signal_losses / observed >= 0.5
        )
        low_snr = (
            contract["pairing_validity"] == "trajectory_divergent"
            and win_rate < threshold
            and hierarchical["status"] != "negative"
            and median >= 0
            and float(hierarchical["ci_high"]) >= 0
            and observed > 0
            and not loss_heavy
            and (
                signal_ties / observed >= 0.5
                and signal_wins >= signal_losses
                or signal_wins > 0
                and signal_wins >= signal_losses
            )
        )
        if low_snr:
            outcome = "expand"
            reason = ("SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT",)
        elif win_rate < 0.5:
            outcome = "fail"
            reason = ("SCREENING_FAIL_WIN_RATE",)
        elif win_rate < threshold:
            outcome = "expand"
            reason = ("SCREENING_EXPAND",)
        elif median >= 0:
            outcome = "pass"
            reason = ("SCREENING_PASS_MARGINAL_DELTA",)
        else:
            outcome = "unclear"
            reason = ("SCREENING_INCONCLUSIVE_HIGH_WIN_NEGATIVE_EFFECT",)
    initial_reason = reason
    if outcome == "expand":
        policy = contract["screening"]["expanded_borderline_advance"]
        lower = max(0.0, threshold - float(policy["win_rate_window"]))
        status = "outside_window"
        if bool(policy["enabled"]) and lower <= win_rate < threshold:
            if bool(policy["require_median_delta_nonnegative"]) and median < 0:
                status = "negative_delta"
            elif (
                bool(policy["require_ci_low_nonnegative"])
                and float(hierarchical["ci_low"]) < 0
            ):
                status = "negative_ci_low"
            else:
                status = "pass"
        elif bool(policy["allow_pair_level_signal"]):
            if bool(policy["require_median_delta_nonnegative"]) and median < 0:
                status = "negative_delta"
            elif (
                bool(policy["require_ci_low_nonnegative"])
                and float(hierarchical["ci_low"]) < 0
            ):
                status = "negative_ci_low"
            else:
                decisive = pairs["wins"] + pairs["losses"]
                pair_signal = (
                    pairs["total"] > 0
                    and pairs["total"] >= int(policy["min_pair_total"])
                    and pairs["wins"] >= int(policy["min_pair_wins"])
                    and pairs["wins"] / pairs["total"]
                    >= float(policy["pair_win_rate_min"])
                    and (
                        policy["max_pair_loss_rate"] is None
                        or pairs["losses"] / pairs["total"]
                        <= float(policy["max_pair_loss_rate"])
                    )
                    and decisive > 0
                    and (
                        policy["pair_non_tie_win_rate_min"] is None
                        or pairs["wins"] / decisive
                        >= float(policy["pair_non_tie_win_rate_min"])
                    )
                    and pairs["wins"] - pairs["losses"]
                    >= int(policy["min_pair_win_loss_margin"])
                )
                status = "pair_signal_pass" if pair_signal else "outside_window"
        if status == "pair_signal_pass":
            outcome = "pass"
            reason = (
                "SCREENING_EXPAND_EXHAUSTED_PAIR_SIGNAL_POLICY_PASS",
                "SCREENING_PAIR_LEVEL_SIGNAL_DIAGNOSTIC_VALIDATE",
            )
        elif status == "pass":
            outcome = "pass"
            reason = (
                "SCREENING_EXPAND_EXHAUSTED_BORDERLINE_POLICY_PASS",
                "SCREENING_BELOW_WIN_RATE_MIN_ALLOWED_BY_POLICY",
            )
        elif status == "negative_delta":
            outcome = "fail"
            reason = (
                "SCREENING_EXPAND_EXHAUSTED_BORDERLINE_NEGATIVE_DELTA",
                "SCREENING_BORDERLINE_POLICY_FAIL_CLOSED",
            )
        elif status == "negative_ci_low":
            outcome = "fail"
            reason = (
                "SCREENING_EXPAND_EXHAUSTED_BORDERLINE_NEGATIVE_CI_LOW",
                "SCREENING_BORDERLINE_POLICY_FAIL_CLOSED",
            )
        elif "SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT" in initial_reason:
            outcome = "unclear"
            reason = ("SCREENING_LOW_SNR_EXPAND_EXHAUSTED_CONTINUE",)
        else:
            outcome = "unclear"
            reason = ("SCREENING_EXPAND_EXHAUSTED",)
    return {
        "outcome": outcome,
        "reason_codes": list(reason),
        "win_rate": win_rate,
        "hierarchical": hierarchical,
        "derived_from_contract_sha256": contract["contract_sha256"],
    }


def validation_gate_from_protocol(
    contrast: Mapping[str, Any], contract: Mapping[str, Any]
) -> dict[str, Any]:
    """Exact expanded quality-only projection of sealed ``validation_gate``."""

    counts = contrast["case_counts"]
    hierarchical = _hierarchical(contrast)
    win_rate = counts["wins"] / counts["total"] if counts["total"] else 0.0
    threshold = float(contract["validation"]["win_rate_min"])
    status = hierarchical["status"]
    if status == "positive":
        if win_rate >= threshold:
            outcome, reasons = "pass", ["VALIDATION_PASS_HIERARCHICAL"]
        else:
            outcome, reasons = "fail", ["VALIDATION_FAIL_WIN_RATE"]
    elif status == "negative":
        outcome, reasons = "fail", ["VALIDATION_FAIL_HIERARCHICAL_NEGATIVE"]
    elif status == "uncertain":
        if win_rate >= threshold:
            outcome, reasons = "expand", ["VALIDATION_EXPAND_HIERARCHICAL_UNCERTAIN"]
        else:
            outcome, reasons = "fail", ["VALIDATION_FAIL_WIN_RATE"]
    else:
        outcome, reasons = "fail", ["VALIDATION_FAIL_NO_HIERARCHICAL_GAIN"]
    if outcome == "expand":
        if float(hierarchical["median"]) < 0:
            outcome, reasons = "fail", ["VALIDATION_EXPAND_EXHAUSTED_FAIL"]
        else:
            outcome, reasons = "pass", ["VALIDATION_EXPAND_EXHAUSTED_MARGINAL_PASS"]
    return {
        "outcome": outcome,
        "reason_codes": reasons,
        "win_rate": win_rate,
        "hierarchical": hierarchical,
        "expanded": True,
        "independent_expansion_available": False,
        "derived_from_contract_sha256": contract["contract_sha256"],
    }


def _arm_summaries(
    manifest: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    arm_hashes = {arm["name"]: arm["arm_sha256"] for arm in manifest["arms"]}
    summaries: list[dict[str, Any]] = []
    for arm in ARM_ORDER:
        selected = [row for row in rows if row["arm"] == arm]
        runtimes = [row["objective"]["runner_wall_time_ns"] for row in selected]
        diagnostics = Counter(
            row["operator_runtime_diagnostics"]["status"] for row in selected
        )
        positions = Counter(row["arm_position"] for row in selected)
        summaries.append(
            {
                "arm": arm,
                "arm_sha256": arm_hashes[arm],
                "lock_eligibility_policy": LOCK_POLICIES[arm],
                "row_count": len(selected),
                "oracle_feasible_rows": sum(
                    row["oracle"]["feasible"] for row in selected
                ),
                "final_intact_locked_group_sum": sum(
                    row["locked_groups"]["final_intact_locked_group_count"]
                    for row in selected
                ),
                "whole_groups_moved_sum": sum(
                    row["locked_groups"]["whole_groups_moved_count"] for row in selected
                ),
                "split_group_violation_sum": sum(
                    row["locked_groups"]["split_group_count"] for row in selected
                ),
                "runtime_ns": {
                    "median": _median(runtimes),
                    "minimum": min(runtimes),
                    "maximum": max(runtimes),
                },
                "operator_diagnostics_status": dict(diagnostics),
                "serial_position_counts": {
                    str(position): positions[position] for position in range(4)
                },
            }
        )
    return summaries


def build_report(
    manifest: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    views = manifest["case_contract"]["views"]
    view_cases = {
        "r3_initial_6_cases": views["r3_initial_screening"]["stable_case_ids"],
        "r3_expanded_14_cases": views["r3_expanded_screening"]["stable_case_ids"],
        "r3_validation_5_cases": views["r3_validation"]["stable_case_ids"],
    }
    bootstrap = manifest["analysis_contract"]["bootstrap"]
    report_views = {
        view_name: {
            "case_count": len(case_ids),
            "contrasts": [
                _contrast(
                    rows,
                    candidate_arm=candidate,
                    reference_arm=reference,
                    case_ids=case_ids,
                    bootstrap=bootstrap,
                )
                for candidate, reference in CONTRASTS
            ],
        }
        for view_name, case_ids in view_cases.items()
    }
    expanded = {
        contrast["candidate_arm"]: contrast
        for contrast in report_views["r3_expanded_14_cases"]["contrasts"]
        if contrast["reference_arm"] == "champion"
    }
    validation = {
        contrast["candidate_arm"]: contrast
        for contrast in report_views["r3_validation_5_cases"]["contrasts"]
        if contrast["reference_arm"] == "champion"
    }
    gate_contract = manifest["analysis_contract"]["protocol_gate"]
    eligibility: list[dict[str, Any]] = []
    for arm in ("destroy_only", "merge_only", "cumulative"):
        screening = screening_gate_from_protocol(expanded[arm], gate_contract)
        validation_result = validation_gate_from_protocol(
            validation[arm], gate_contract
        )
        integrity = all(
            row["oracle"]["feasible"] and row["locked_groups"]["split_group_count"] == 0
            for row in rows
            if row["arm"] == arm
        )
        eligibility.append(
            {
                "arm": arm,
                "screening": screening,
                "validation": validation_result,
                "integrity_and_locked_groups_passed": integrity,
                "eligible": screening["outcome"] == "pass"
                and validation_result["outcome"] == "pass"
                and integrity,
            }
        )
    eligible = [row["arm"] for row in eligibility if row["eligible"]]
    if len(eligible) == 1:
        follow_up = {"outcome": "sole_arm_may_be_proposed", "arm": eligible[0]}
    elif not eligible:
        follow_up = {"outcome": "no_arm_advances", "arm": None}
    else:
        follow_up = {
            "outcome": "multiple_arms_no_posthoc_selection",
            "arm": None,
            "eligible_arms": eligible,
        }
    return {
        "schema": REPORT_SCHEMA,
        "posterior_decomposition_only": True,
        "treatment_bundles_not_pure_factorial": True,
        "validation_is_not_fresh_confirmation": True,
        "production_amount_limit_coverage_claimed": False,
        "statistical_unit": "case",
        "seed_aggregation": "strict_case_majority_else_tie",
        "bootstrap": dict(bootstrap),
        "protocol_gate_contract": gate_contract,
        "arm_summaries": _arm_summaries(manifest, rows),
        "views": report_views,
        "eligibility": eligibility,
        "follow_up": follow_up,
        "cell_rows_preserved": True,
        "runtime_and_trajectory_are_observation_only": True,
    }


def build_artifacts(
    manifest: Mapping[str, Any],
    manifest_sha: str,
    rows: Sequence[Mapping[str, Any]],
    raw_identities: Sequence[Mapping[str, Any]],
) -> tuple[bytes, bytes, bytes, dict[str, Any]]:
    aggregate_sha = canonical_sha256(
        {"domain": RESULTS_SCHEMA, "items": list(raw_identities)}
    )
    results = {
        "schema": RESULTS_SCHEMA,
        "manifest_sha256": manifest_sha,
        "row_count": len(rows),
        "raw_identities": list(raw_identities),
        "ordered_aggregate_sha256": aggregate_sha,
        "rows": list(rows),
    }
    results_bytes = render_json(results)
    report = build_report(manifest, rows)
    report_bytes = render_json(report)
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "passed": True,
        "design_sha256": manifest["authority"]["design_sha256"],
        "manifest_sha256": manifest_sha,
        "raw_row_count": len(rows),
        "raw_identities": list(raw_identities),
        "ordered_aggregate_sha256": aggregate_sha,
        "results_sha256": sha256_bytes(results_bytes),
        "report_sha256": sha256_bytes(report_bytes),
        "toolchain": manifest["toolchain"],
        "problem_layer_sources": manifest["problem_layer_sources"],
        "analysis_sources": manifest["analysis_contract"]["source_digests"],
        "source_closures": {
            "source_commit": manifest["source"]["source_commit"],
            "git_blob_aggregate_sha256": manifest["source"][
                "git_blob_aggregate_sha256"
            ],
            "workspaces": {
                entry["arm"]: entry["tree"]["tree_sha256"]
                for entry in manifest["workspaces"]
            },
            "sealed_repository_input_sha256": canonical_sha256(
                {
                    "domain": "scion.warehouse_w3_sealed_repository_inputs.v1",
                    "items": manifest["sealed_repository_inputs"],
                }
            ),
            "sealed_w2_input_sha256": canonical_sha256(
                {
                    "domain": "scion.warehouse_w3_sealed_w2_inputs.v1",
                    "items": manifest["w2_preservation_inputs"],
                }
            ),
        },
        "preflight_fact_sha256": canonical_sha256(
            {
                "domain": "scion.warehouse_w3_greedy_preflight.v1",
                "items": manifest["greedy_preflight"],
            }
        ),
        "schedule_balance": manifest["schedule_balance"],
        "integrity_verdict": "passed",
        "retry": False,
        "resume": False,
        "reuse": False,
    }
    return results_bytes, report_bytes, render_json(receipt), report


def replay_artifacts(
    manifest: Mapping[str, Any],
    manifest_sha256: str,
    row_bytes: Sequence[bytes],
    publication_identities: Sequence[Mapping[str, Any]],
) -> tuple[bytes, bytes, bytes, dict[str, Any]]:
    """Return deterministic artifact bytes; the generic owner publishes them."""

    rows, identities = validate_replay_rows(
        manifest, manifest_sha256, row_bytes, publication_identities
    )
    return build_artifacts(manifest, manifest_sha256, rows, identities)


__all__ = [
    "build_artifacts",
    "build_report",
    "case_majority",
    "replay_artifacts",
    "screening_gate_from_protocol",
    "validation_gate_from_protocol",
]
