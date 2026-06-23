"""Branch research-identity projection from verified hypotheses."""

from __future__ import annotations

from scion.core.models import Branch, HypothesisProposal, HypothesisRecord, mechanism_changes


def adopt_verified_hypothesis_identity(
    branch: Branch,
    hypothesis: HypothesisProposal | HypothesisRecord,
) -> bool:
    """Record the verified hypothesis identity on its branch.

    The stored branch identity is proposal/lifecycle context only. Decision
    inputs still come from deterministic protocol features.
    """

    changed = False
    mechanism_ids = tuple(
        dict.fromkeys(
            str(change.id).strip()
            for change in mechanism_changes(hypothesis)
            if str(change.id).strip()
        )
    )
    if mechanism_ids:
        merged = tuple(
            dict.fromkeys(
                [
                    *(
                        str(item).strip()
                        for item in (branch.branch_mechanism_ids or ())
                        if str(item).strip()
                    ),
                    *mechanism_ids,
                ]
            )
        )
        if merged != tuple(branch.branch_mechanism_ids or ()):
            branch.branch_mechanism_ids = merged
            changed = True

    if branch.direction is None:
        change_locus = str(getattr(hypothesis, "change_locus", "") or "").strip()
        text = str(getattr(hypothesis, "hypothesis_text", "") or "")[:100]
        if change_locus or text:
            branch.direction = f"{change_locus}: {text}"
            changed = True

    return changed
