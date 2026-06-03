from types import SimpleNamespace

from scion.core.campaign_composition import _seed_external_mechanism_references
from scion.proposal.search_memory import CampaignSearchMemory


def test_seeds_external_mechanism_references_from_adapter_provider() -> None:
    memory = CampaignSearchMemory()
    adapter = SimpleNamespace(
        external_mechanism_reference_provider=lambda: SimpleNamespace(
            entries=lambda: [
                {
                    "source_ref": "external-control:round10",
                    "mechanism_label": "phase_budgeted_portfolio",
                    "surface": "solver_design",
                    "target_file": "policies/search_phase.py",
                    "positive_signals": ["common-row improvement"],
                    "negative_boundaries": ["advisory metadata is not hard truth"],
                    "required_observations": ["phase_time"],
                    "suggested_actions": ["wire adapter-owned telemetry"],
                    "confidence": "external_control_broad",
                }
            ]
        )
    )

    _seed_external_mechanism_references(
        memory,
        problem_spec=SimpleNamespace(),
        adapter=adapter,
    )

    rendered = memory.render(view="hypothesis")

    assert len(memory.external_mechanism_references) == 1
    assert "External Mechanism References" in rendered
    assert "phase_budgeted_portfolio" in rendered
    assert "wire adapter-owned telemetry" in rendered
    assert "not Decision input" in rendered
