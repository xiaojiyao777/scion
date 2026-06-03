from types import SimpleNamespace

from scion.core.campaign_composition import _seed_external_mechanism_references
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.problems.cvrp.external_references import (
    CvrpExternalMechanismReferenceProvider,
)
from scion.proposal.search_memory import CampaignSearchMemory


def test_cvrp_external_reference_provider_exposes_direct_control_mechanisms() -> None:
    entries = tuple(CvrpExternalMechanismReferenceProvider().entries())

    labels = {entry["mechanism_label"] for entry in entries}

    assert "typed_fleet_metadata_soft_preference" in labels
    assert "size_bucketed_construction_portfolio" in labels
    assert "phase_budgeted_local_improvement" in labels
    assert "common_row_broad_safety_evidence" in labels
    assert all(entry["surface"] == "solver_design" for entry in entries)
    assert all(entry["source_ref"].startswith("direct-vrp-control:") for entry in entries)


def test_cvrp_adapter_external_references_seed_search_memory() -> None:
    adapter = CvrpAdapter(SimpleNamespace())  # type: ignore[arg-type]
    memory = CampaignSearchMemory()

    _seed_external_mechanism_references(
        memory,
        problem_spec=SimpleNamespace(),
        adapter=adapter,
    )

    rendered = memory.render(view="hypothesis")

    assert len(memory.external_mechanism_references) == 4
    assert "External Mechanism References" in rendered
    assert "tainted proposal guidance" in rendered
    assert "not Decision input" in rendered
    assert "typed_fleet_metadata_soft_preference" in rendered
    assert "size_bucketed_construction_portfolio" in rendered
    assert "phase_budgeted_local_improvement" in rendered
    assert "common_row_broad_safety_evidence" in rendered
    assert "adapter-owned typed facts" in rendered
