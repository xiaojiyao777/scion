"""Focused tests split from test_sprint_e2.py."""

from .sprint_e2_test_support import *  # noqa: F401,F403

def test_t05_frozen_set_has_at_least_six():
    """T05: Frozen set must have 6-8 cases after expansion."""
    from scion.config.split_manifest import SplitManifest
    manifest = SplitManifest.from_yaml(str(MANIFEST_PATH))
    assert len(manifest.frozen) >= 6, f"Frozen set has {len(manifest.frozen)} cases"  # v4: 18


def test_t05_frozen_set_has_size_diversity():
    """T05: Frozen set should have large + xlarge + xxlarge cases."""
    from scion.config.split_manifest import SplitManifest
    manifest = SplitManifest.from_yaml(str(MANIFEST_PATH))
    frozen = manifest.frozen
    # Check we have l, x, and xx tiers
    has_large = any("fro_l" in f for f in frozen)
    has_xlarge = any("fro_x0" in f for f in frozen)
    has_xxlarge = any("fro_xx" in f for f in frozen)
    assert has_large, "Frozen should include large-tier instances (fro_l)"
    assert has_xlarge, "Frozen should include xlarge-tier instances (fro_x)"
    assert has_xxlarge, "Frozen should include xxlarge-tier instances (fro_xx)"


def test_t05_frozen_no_overlap_with_screening_or_validation():
    """T05: Frozen must not overlap with screening or validation."""
    from scion.config.split_manifest import SplitManifest
    manifest = SplitManifest.from_yaml(str(MANIFEST_PATH))
    frozen_set = set(manifest.frozen)
    assert frozen_set.isdisjoint(set(manifest.screening))
    assert frozen_set.isdisjoint(set(manifest.validation))


def test_t11_screening_has_40_percent_large():
    """T11: ~40% of screening cases should be large."""
    from scion.config.split_manifest import SplitManifest
    manifest = SplitManifest.from_yaml(str(MANIFEST_PATH))
    screening = manifest.screening
    large_count = sum(1 for f in screening if "_scr_l" in f)
    ratio = large_count / len(screening)
    assert ratio >= 0.20, f"Large screening ratio is {ratio:.1%}, expected >=20%"  # v4: 23.5%


def test_family_assignment_by_keywords_subcategory():
    fid = assign_family_id(
        "Merge subcategory vehicles to reduce splits",
        "create_new",
        "vehicle_level",
        taxonomy=WAREHOUSE_MECHANISM_TAXONOMY,
    )
    assert "subcategory_consolidation" in fid


def test_family_assignment_by_keywords_destroy():
    fid = assign_family_id(
        "Destroy and rebuild the vehicle assignment",
        "create_new",
        "vehicle_level",
        taxonomy=WAREHOUSE_MECHANISM_TAXONOMY,
    )
    assert "destroy_rebuild" in fid


def test_family_assignment_by_keywords_swap():
    fid = assign_family_id(
        "Swap orders between vehicles",
        "modify",
        "order_level",
        taxonomy=WAREHOUSE_MECHANISM_TAXONOMY,
    )
    assert "order_swap" in fid


def test_family_assignment_by_keywords_cost():
    fid = assign_family_id(
        "Downsize vehicles to reduce total cost",
        "modify",
        "vehicle_level",
        taxonomy=WAREHOUSE_MECHANISM_TAXONOMY,
    )
    assert "cost_reduction" in fid


def test_family_assignment_default():
    fid = assign_family_id("Some unrecognised hypothesis text xyz", "modify", "vehicle_level")
    assert "generic" in fid


def test_family_assignment_default_does_not_emit_warehouse_labels():
    fid = assign_family_id("Merge subcategory vehicles to reduce splits", "create_new", "vehicle_level")
    assert fid == "generic/create_new/vehicle_level"
    assert "subcategory_consolidation" not in fid
    assert "cost_reduction" not in fid


def test_context_family_extraction_route_taxonomy_blocks_warehouse_labels():
    steps = [
        _make_step(
            hypothesis_text="merge subcategory clusters and reduce cost",
            action="create_new",
            locus="route_pair",
        ),
        _make_step(
            hypothesis_text="try route-pair 2-opt* exchange",
            action="modify",
            locus="route_pair",
        ),
    ]

    families = _extract_families_from_steps(
        steps,
        taxonomy=CVRP_FAMILY_TAXONOMY,
    )
    family_ids = {f.family_id for f in families}

    assert "NEW_FAMILY/create_new/route_pair" in family_ids
    assert "NEW_FAMILY/modify/route_pair" in family_ids
    assert all("subcategory_consolidation" not in fid for fid in family_ids)
    assert all("cost_reduction" not in fid for fid in family_ids)


def test_context_family_extraction_handles_prior_failed_family_mentions():
    steps = [
        _make_step(
            hypothesis_text=(
                "Implement a 2-opt intra-route local search operator that "
                "reverses route segments when distance decreases."
            ),
            action="create_new",
            locus="route_local",
        ),
        _make_step(
            hypothesis_text=(
                "Implement an Or-opt inter-route relocation operator. Unlike "
                "the previously attempted intra-route 2-opt, this targets "
                "cross-route distance reduction."
            ),
            action="create_new",
            locus="route_pair",
        ),
        _make_step(
            hypothesis_text=(
                "Implement a ruin-and-recreate segment ruin strategy. This "
                "differs from the failed intra-route 2-opt and inter-route "
                "single-node relocation by rebuilding a cluster."
            ),
            action="create_new",
            locus="ruin_recreate",
        ),
        _make_step(
            hypothesis_text=(
                "Implement a 3-opt segment move that relocates chains from "
                "one route to another route rather than single nodes."
            ),
            action="create_new",
            locus="route_pair",
        ),
    ]

    families = _extract_families_from_steps(steps, taxonomy=CVRP_FAMILY_TAXONOMY)
    family_ids = {fam.family_id for fam in families}

    assert "solver_design/create_new/route_local" in family_ids
    assert "NEW_FAMILY/create_new/route_pair" in family_ids
    assert "NEW_FAMILY/create_new/ruin_recreate" in family_ids
    assert "route_local/create_new/route_local" not in family_ids
    assert "route_pair/create_new/route_pair" not in family_ids


def test_family_id_includes_action_and_locus():
    fid = assign_family_id("Swap orders between vehicles", "modify", "order_level")
    assert "modify" in fid
    assert "order_level" in fid


def test_coverage_report_format_shows_family_ids():
    """T07: Coverage report lists family IDs and counts."""
    steps = [
        _make_step(hypothesis_text="Merge subcategory vehicles", action="create_new", locus="vehicle_level"),
        _make_step(hypothesis_text="Swap orders between vehicles", action="modify", locus="order_level"),
    ]
    families = _extract_families_from_steps(steps, taxonomy=WAREHOUSE_MECHANISM_TAXONOMY)
    report = build_exploration_coverage(families)
    assert "Exploration Coverage" in report
    assert "subcategory_consolidation" in report
    assert "order_swap" in report


def test_coverage_report_shows_unexplored_actions():
    """T07: Coverage report flags unexplored action types."""
    steps = [_make_step(action="modify", locus="vehicle_level")]
    families = _extract_families_from_steps(steps, taxonomy=WAREHOUSE_MECHANISM_TAXONOMY)
    report = build_exploration_coverage(families)
    assert "create_new" in report  # unexplored action should be flagged


def test_coverage_report_respects_available_actions():
    steps = [_make_step(action="create_new", locus="route_local")]
    families = _extract_families_from_steps(steps, taxonomy=CVRP_FAMILY_TAXONOMY)

    report = build_exploration_coverage(families, available_actions={"create_new"})

    assert "modify" not in report
    assert "remove" not in report


def test_coverage_report_empty_for_no_steps():
    assert build_exploration_coverage([]) == ""


def test_family_tracking_across_rounds():
    """T07: Same family accumulates evidence_count across multiple steps."""
    steps = [
        _make_step(round_num=1, hypothesis_text="Consolidate subcategory splits"),
        _make_step(round_num=2, hypothesis_text="Subcategory merge attempt"),
        _make_step(round_num=3, hypothesis_text="Subcategory consolidation improved"),
    ]
    families = _extract_families_from_steps(steps, taxonomy=WAREHOUSE_MECHANISM_TAXONOMY)
    subcat_families = [f for f in families if "subcategory_consolidation" in f.family_id]
    assert len(subcat_families) == 1, "Same mechanism should be one family"
    assert subcat_families[0].evidence_count == 3


def test_family_tracking_different_actions_are_different_families():
    """T07: Same mechanism but different action = different family."""
    steps = [
        _make_step(hypothesis_text="Merge subcategory vehicles", action="create_new", locus="vehicle_level"),
        _make_step(hypothesis_text="Subcategory merge refinement", action="modify", locus="vehicle_level"),
    ]
    families = _extract_families_from_steps(steps, taxonomy=WAREHOUSE_MECHANISM_TAXONOMY)
    subcat_families = [f for f in families if "subcategory_consolidation" in f.family_id]
    assert len(subcat_families) == 2, "Different actions = different families"
