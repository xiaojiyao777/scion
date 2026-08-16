from scion.proposal.mechanism_labels import extract_mechanism_label


def test_mechanism_label_is_generic_without_problem_taxonomy() -> None:
    assert extract_mechanism_label("merge subcategories for consolidation") == "generic"


def test_mechanism_label_uses_problem_taxonomy_aliases() -> None:
    taxonomy = {
        "families": ["local_search", "route_exchange"],
        "aliases": {"route_exchange": ["two opt exchange"]},
    }

    assert (
        extract_mechanism_label("Try a bounded two-opt exchange", taxonomy)
        == "route_exchange"
    )
