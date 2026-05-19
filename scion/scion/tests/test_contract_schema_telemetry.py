"""Focused tests split from test_contract.py."""

from .contract_test_support import *  # noqa: F401,F403

class TestC1Schema:
    def test_valid_hypothesis_passes(self, gate: ContractGate):
        h = HypothesisProposal(
            hypothesis_text="Try tournament selection",
            change_locus="selection",
            action="modify",
            target_file="operators/sel.py",
        )
        result = gate.validate_hypothesis(h, [], [])
        c1 = next(c for c in result.checks if c.name == "C1_schema")
        assert c1.passed

    def test_empty_hypothesis_text_fails(self, gate: ContractGate):
        h = HypothesisProposal(
            hypothesis_text="  ",
            change_locus="selection",
            action="modify",
            target_file="operators/sel.py",
        )
        result = gate.validate_hypothesis(h, [], [])
        c1 = next(c for c in result.checks if c.name == "C1_schema")
        assert not c1.passed
        assert not result.passed

    def test_empty_change_locus_fails(self, gate: ContractGate):
        h = HypothesisProposal(
            hypothesis_text="valid text",
            change_locus="",
            action="modify",
            target_file="operators/sel.py",
        )
        result = gate.validate_hypothesis(h, [], [])
        c1 = next(c for c in result.checks if c.name == "C1_schema")
        assert not c1.passed


def test_hypothesis_expected_telemetry_must_use_declared_surface_fields():
    spec = make_spec(
        categories=("solver",),
        editable=("policies/*.py",),
        frozen=(),
    )
    object.__setattr__(
        spec,
        "research_surfaces",
        [
            SimpleNamespace(
                name="solver",
                kind="solver_design",
                target_files=["policies/solver.py"],
                evidence=SimpleNamespace(
                    required_runtime_fields=[
                        "solver_loaded",
                        "solver_active",
                        "solver_errors",
                        "solver_search_iterations",
                    ],
                ),
            )
        ],
    )
    gate = ContractGate(spec)
    hypothesis = HypothesisProposal(
        hypothesis_text="Run a bounded search loop.",
        change_locus="solver",
        action="modify",
        target_file="policies/solver.py",
        expected_telemetry={"activity": ["missing_search_iterations"]},
    )

    result = gate.validate_hypothesis(hypothesis, [], [])

    assert result.passed is False
    c11 = next(
        check for check in result.checks if check.name == "C11_expected_telemetry"
    )
    assert c11.passed is False
    assert "undeclared runtime field" in c11.detail


def test_mechanism_telemetry_surface_requires_hypothesis_mechanism_change():
    spec = make_spec(
        categories=("solver",),
        editable=("policies/*.py",),
        frozen=(),
    )
    object.__setattr__(
        spec,
        "research_surfaces",
        [
            SimpleNamespace(
                name="solver",
                kind="policy",
                target_files=["policies/solver.py"],
                evidence=SimpleNamespace(
                    mechanism_telemetry={
                        "search_seed": SimpleNamespace(
                            activation_runtime_fields=["mechanisms.search_seed.active"],
                            effect_probe_runtime_fields=["mechanisms.search_seed.delta"],
                        )
                    }
                ),
            )
        ],
    )
    gate = ContractGate(spec)
    hypothesis = HypothesisProposal(
        hypothesis_text="Change the bounded search seed mechanism.",
        change_locus="solver",
        action="modify",
        target_file="policies/solver.py",
    )

    result = gate.validate_hypothesis(hypothesis, [], [])

    c12 = next(check for check in result.checks if check.name == "C12_mechanism_binding")
    assert result.passed is False
    assert c12.passed is False
    assert "must declare mechanism_changes" in c12.detail


def test_mechanism_telemetry_surface_accepts_exact_and_wildcard_ids():
    spec = make_spec(
        categories=("solver",),
        editable=("policies/*.py",),
        frozen=(),
    )
    object.__setattr__(
        spec,
        "research_surfaces",
        [
            SimpleNamespace(
                name="solver",
                kind="policy",
                target_files=["policies/solver.py"],
                evidence=SimpleNamespace(
                    mechanism_telemetry={
                        "search_seed": SimpleNamespace(
                            activation_runtime_fields=["mechanisms.search_seed.active"],
                            effect_probe_runtime_fields=["mechanisms.search_seed.delta"],
                        ),
                        "phase_*": SimpleNamespace(
                            activation_runtime_fields=["mechanisms.{mechanism}.active"],
                            effect_probe_runtime_fields=["mechanisms.{mechanism}.delta"],
                        ),
                    }
                ),
            )
        ],
    )
    gate = ContractGate(spec)

    for mechanism_id in ("search_seed", "phase_restart"):
        hypothesis = HypothesisProposal(
            hypothesis_text="Change one declared generic mechanism.",
            change_locus="solver",
            action="modify",
            target_file="policies/solver.py",
            mechanism_changes=(
                MechanismChange(id=mechanism_id, change_type="modify"),
            ),
        )
        result = gate.validate_hypothesis(hypothesis, [], [])
        c12 = next(
            check for check in result.checks if check.name == "C12_mechanism_binding"
        )
        assert c12.passed


def test_mechanism_telemetry_surface_rejects_undeclared_mechanism_id():
    spec = make_spec(
        categories=("solver",),
        editable=("policies/*.py",),
        frozen=(),
    )
    object.__setattr__(
        spec,
        "research_surfaces",
        [
            SimpleNamespace(
                name="solver",
                kind="policy",
                target_files=["policies/solver.py"],
                evidence=SimpleNamespace(
                    mechanism_telemetry={
                        "search_seed": SimpleNamespace(
                            activation_runtime_fields=["mechanisms.search_seed.active"],
                            effect_probe_runtime_fields=["mechanisms.search_seed.delta"],
                        )
                    }
                ),
            )
        ],
    )
    gate = ContractGate(spec)
    hypothesis = HypothesisProposal(
        hypothesis_text="Change an undeclared generic mechanism.",
        change_locus="solver",
        action="modify",
        target_file="policies/solver.py",
        mechanism_changes=(
            MechanismChange(id="phase_restart", change_type="modify"),
        ),
    )

    result = gate.validate_hypothesis(hypothesis, [], [])

    c12 = next(check for check in result.checks if check.name == "C12_mechanism_binding")
    assert result.passed is False
    assert c12.passed is False
    assert "do not match declared mechanism telemetry" in c12.detail


def test_patch_must_echo_approved_hypothesis_mechanism_ids():
    spec = make_spec(
        categories=("solver",),
        editable=("policies/*.py",),
        frozen=(),
    )
    object.__setattr__(
        spec,
        "research_surfaces",
        [
            SimpleNamespace(
                name="solver",
                kind="policy",
                target_files=["policies/solver.py"],
                evidence=SimpleNamespace(
                    mechanism_telemetry={
                        "search_seed": SimpleNamespace(
                            activation_runtime_fields=["mechanisms.search_seed.active"],
                            effect_probe_runtime_fields=["mechanisms.search_seed.delta"],
                        )
                    }
                ),
            )
        ],
    )
    gate = ContractGate(spec)
    hypothesis = HypothesisProposal(
        hypothesis_text="Change the search seed mechanism.",
        change_locus="solver",
        action="modify",
        target_file="policies/solver.py",
        mechanism_changes=(
            MechanismChange(id="search_seed", change_type="modify"),
        ),
    )
    missing = PatchProposal(
        file_path="policies/solver.py",
        action="modify",
        code_content="VALUE = 1\n",
    )
    echo = PatchProposal(
        file_path="policies/solver.py",
        action="modify",
        code_content="VALUE = 1\n",
        mechanism_changes=(
            MechanismChange(id="search_seed", change_type="modify"),
        ),
    )
    extra = PatchProposal(
        file_path="policies/solver.py",
        action="modify",
        code_content="VALUE = 1\n",
        mechanism_changes=(
            MechanismChange(id="search_seed", change_type="modify"),
            MechanismChange(id="other_seed", change_type="add"),
        ),
    )

    missing_result = gate.validate_patch(missing, approved_hypothesis=hypothesis)
    echo_result = gate.validate_patch(echo, approved_hypothesis=hypothesis)
    extra_result = gate.validate_patch(extra, approved_hypothesis=hypothesis)

    assert missing_result.passed is False
    assert "missing approved mechanism id" in missing_result.failure_reason
    assert echo_result.passed is True
    assert extra_result.passed is False
    assert "unexpected mechanism id" in extra_result.failure_reason
