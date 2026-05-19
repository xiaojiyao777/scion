from __future__ import annotations

from types import SimpleNamespace

from scion.config.problem import ProblemSpec, SearchSpace, SolverConfig
from scion.contract.checks.complexity import check_complexity_bound
from scion.contract.checks.identity import check_surface_instance_identity
from scion.contract.checks.novelty import NoveltyChecker
from scion.contract.checks.randomness import check_non_rng_random
from scion.contract.checks.security import check_import_whitelist, check_sensitive_api
from scion.contract.checks.targeting import (
    check_file_whitelist,
    check_frozen_files,
    check_patch_action_target,
)
from scion.contract.gate import ContractGate
from scion.contract.patch_paths import (
    hypothesis_action_for_patch_action,
    matches_config_pattern,
    patch_action_for_hypothesis_action,
)
from scion.contract.result_payload import build_result, prefix_checks
from scion.contract.schema import (
    mechanism_changes_schema_error,
    normalize_signature_field,
    objective_list_schema_error,
)
from scion.contract.surface_access import SurfaceAccess
from scion.contract.telemetry import (
    mechanism_id_matches_declaration,
    surface_mechanism_telemetry_declarations,
)
from scion.core.models import (
    CheckResult,
    HypothesisProposal,
    HypothesisRecord,
    MechanismChange,
    PatchProposal,
)


def test_result_payload_preserves_first_failure_and_prefixed_metadata() -> None:
    checks = [
        CheckResult(
            name="C1_schema",
            passed=True,
            severity="light",
            detail="ok",
            elapsed_ms=1,
            metadata={"source": "primary"},
        ),
        CheckResult(
            name="C4_file_whitelist",
            passed=False,
            severity="heavy",
            detail="blocked",
            elapsed_ms=2,
            metadata={"path": "x.py"},
        ),
    ]

    prefixed = prefix_checks(checks, "additional_changes[0]")
    result = build_result(prefixed)

    assert result.passed is False
    assert result.failure_reason == (
        "additional_changes[0].C4_file_whitelist: blocked"
    )
    assert result.checks[1].metadata == {"path": "x.py"}


def test_patch_path_helpers_cover_static_action_and_pattern_mapping() -> None:
    assert matches_config_pattern("operators/local.py", "operators/*.py")
    assert not matches_config_pattern("operators/nested/local.py", "operators/*.py")
    assert patch_action_for_hypothesis_action("create_new") == "create"
    assert hypothesis_action_for_patch_action("delete") == "remove"


def test_schema_helpers_validate_objectives_mechanisms_and_signature_fields() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text="change acceptance",
        change_locus="acceptance",
        action="modify",
        target_file="policies/acceptance.py",
        predicted_direction="tradeoff",
        target_objectives=("distance",),
        novelty_signature={"strategy": "late accept"},
        mechanism_changes=(MechanismChange(id="late_accept", change_type="modify"),),
    )

    assert objective_list_schema_error(hypothesis, frozenset({"distance"})) is None
    assert mechanism_changes_schema_error(hypothesis) is None
    assert normalize_signature_field(
        "strategy",
        hypothesis,
        objective_names=frozenset({"distance"}),
    ) == "late accept"
    assert ContractGate.supports_semantic_signature_field("strategy")


def test_surface_access_reads_generic_surface_metadata() -> None:
    surface = SimpleNamespace(
        name="acceptance",
        kind="policy",
        targets=SimpleNamespace(
            files=("policies/acceptance.py",),
            modify_allowed=True,
            create_new_allowed=False,
            remove_allowed=False,
        ),
        novelty=SimpleNamespace(
            strategy="semantic_signature",
            signature_fields=("strategy",),
        ),
    )
    access = SurfaceAccess(SimpleNamespace(research_surfaces=(surface,)))

    assert access.surface_by_name("acceptance") is surface
    assert access.target_matches_surface("policies/acceptance.py", surface)
    assert access.surface_action_allowed(surface, "modify")
    assert not access.surface_action_allowed(surface, "create_new")
    assert access.surface_novelty_strategy(surface) == "semantic_signature"
    assert access.surface_signature_fields(surface) == ["strategy"]


def test_novelty_checker_rejects_duplicate_semantic_signature_without_gate_state() -> None:
    surface = SimpleNamespace(
        name="acceptance",
        kind="policy",
        targets=SimpleNamespace(files=("policies/acceptance.py",)),
        novelty=SimpleNamespace(
            strategy="semantic_signature",
            signature_fields=("strategy",),
        ),
    )
    spec = SimpleNamespace(research_surfaces=(surface,))
    access = SurfaceAccess(spec)
    checker = NoveltyChecker(spec, access)
    candidate = HypothesisProposal(
        hypothesis_text="change acceptance threshold",
        change_locus="acceptance",
        action="modify",
        target_file="policies/acceptance.py",
        novelty_signature={"strategy": "late accept"},
    )
    existing = HypothesisRecord(
        hypothesis_id="h-1",
        branch_id="b-1",
        change_locus="acceptance",
        action="modify",
        status="active",
        target_file="policies/acceptance.py",
        hypothesis_text="older acceptance threshold",
        novelty_signature={"strategy": "late accept"},
    )

    result = checker.check(candidate, [existing], [])

    assert result.name == "C10_novelty"
    assert not result.passed
    assert "duplicate structured novelty_signature" in result.detail


def test_telemetry_helpers_extract_and_match_mechanism_declarations() -> None:
    surface = SimpleNamespace(
        evidence=SimpleNamespace(
            mechanism_telemetry={
                "late_*": SimpleNamespace(
                    activation_runtime_fields=("mechanism.{mechanism}.active",),
                    effect_probe_runtime_fields=(),
                )
            }
        )
    )

    declarations = surface_mechanism_telemetry_declarations(surface)

    assert declarations == ("late_*",)
    assert mechanism_id_matches_declaration("late_accept", declarations)
    assert not mechanism_id_matches_declaration("early_accept", declarations)


def test_targeting_checks_use_spec_and_surface_access_without_gate_state() -> None:
    spec = _make_spec(
        editable=("policies/*.py",),
        frozen=("policies/frozen.py",),
    )
    surface = SimpleNamespace(
        name="acceptance",
        kind="policy",
        targets=SimpleNamespace(
            files=("policies/acceptance.py",),
            modify_allowed=True,
            create_new_allowed=False,
            remove_allowed=False,
        ),
    )
    access = SurfaceAccess(SimpleNamespace(research_surfaces=(surface,)))
    hypothesis = HypothesisProposal(
        hypothesis_text="change acceptance",
        change_locus="acceptance",
        action="modify",
        target_file="policies/acceptance.py",
    )
    patch = PatchProposal(
        file_path="policies/acceptance.py",
        action="modify",
        code_content="def decide():\n    return True\n",
    )

    assert check_file_whitelist(patch, spec).passed
    assert check_frozen_files(patch, spec).passed
    assert check_patch_action_target(
        patch,
        hypothesis,
        surface_access=access,
    ).passed


def test_security_checks_reject_non_whitelisted_import_and_sensitive_api() -> None:
    spec = _make_spec(import_whitelist=("math",))
    import_patch = PatchProposal(
        file_path="operators/op.py",
        action="modify",
        code_content="import subprocess\n",
    )
    sensitive_patch = PatchProposal(
        file_path="operators/op.py",
        action="modify",
        code_content="def run():\n    return __import__('os').system('x')\n",
    )

    assert not check_import_whitelist(import_patch, problem_spec=spec).passed
    assert not check_sensitive_api(sensitive_patch).passed


def test_static_risk_checks_cover_randomness_complexity_and_identity() -> None:
    random_patch = PatchProposal(
        file_path="operators/op.py",
        action="modify",
        code_content="import random as r\ndef choose():\n    return r.choice([1])\n",
    )
    complexity_patch = PatchProposal(
        file_path="operators/op.py",
        action="modify",
        code_content=(
            "import itertools\n"
            "def scan(items):\n"
            "    return list(itertools.product(items, items))\n"
        ),
    )
    identity_patch = PatchProposal(
        file_path="policies/acceptance.py",
        action="modify",
        code_content="def decide(instance):\n    return instance.name == 'case'\n",
    )
    surface = SimpleNamespace(
        name="acceptance",
        kind="policy",
        targets=SimpleNamespace(files=("policies/acceptance.py",)),
    )
    access = SurfaceAccess(SimpleNamespace(research_surfaces=(surface,)))

    assert not check_non_rng_random(random_patch).passed
    assert not check_complexity_bound(
        complexity_patch,
        scale_names=frozenset({"items"}),
        surface_error=None,
    ).passed
    assert not check_surface_instance_identity(
        identity_patch,
        selected_surface="acceptance",
        surface_access=access,
        surface_disallows_instance_name=lambda surface: True,
        champion_file_content=lambda file_rel: None,
    ).passed


def _make_spec(
    *,
    editable: tuple[str, ...] = ("operators/*.py",),
    frozen: tuple[str, ...] = (),
    import_whitelist: tuple[str, ...] = ("math", "itertools"),
) -> ProblemSpec:
    return ProblemSpec(
        name="test_problem",
        root_dir="/tmp/test",
        operator_categories=["acceptance"],
        search_space=SearchSpace(
            editable=list(editable),
            frozen=list(frozen),
            import_whitelist=list(import_whitelist),
        ),
        solver=SolverConfig(),
    )
