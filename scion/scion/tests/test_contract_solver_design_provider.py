from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from scion.contract.gate import ContractGate
from scion.contract.checks import solver_design_integration as generic_c9e
from scion.contract.checks.problem_integration import (
    ProblemIntegrationProviderError,
    resolve_contract_check_provider,
)
from scion.core.models import PatchProposal
from scion.problem.providers import (
    ProblemProviderError,
    active_subject_policy_matches_path,
    active_subject_policy_payload,
    resolve_solver_design_prompt_provider,
)
from scion.problem.bridge import (
    legacy_problem_spec_from_v1,
    load_problem_spec_v1_from_yaml,
)
from scion.tests.unit.research_surface_helpers import _CVRP_ROOT


def _install_fake_adapter_module(monkeypatch, module_name: str, adapter_cls) -> None:
    package_name = module_name.rsplit(".", 1)[0]
    package = types.ModuleType(package_name)
    package.__path__ = []
    module = types.ModuleType(module_name)
    module.DemoAdapter = adapter_cls
    monkeypatch.setitem(sys.modules, package_name, package)
    monkeypatch.setitem(sys.modules, module_name, module)


class _DemoAdapter:
    def __init__(self, spec) -> None:
        marker = getattr(getattr(spec, "llm_hints", None), "marker", None)
        if marker != "v1":
            raise TypeError("expected v1 spec")
        self._spec = spec

    @property
    def spec(self):
        return self._spec

    def solver_design_prompt_provider(self):
        return SimpleNamespace(marker=getattr(self._spec.llm_hints, "marker", ""))

    def contract_check_provider(self):
        return SimpleNamespace(marker=getattr(self._spec.llm_hints, "marker", ""))

    def render_problem_summary(self):
        return ""

    def render_operator_interface(self):
        return ""

    def load_instance(self, instance_path):
        return instance_path

    def deserialize_solver_output(self, raw_output, instance):
        return SimpleNamespace(
            raw_output=raw_output,
            objective={},
            feasible=True,
            normalized_solution=instance,
        )

    def check_solution_consistency(self, artifact, instance):
        return SimpleNamespace(passed=True, reasons=())

    def check_feasibility(self, artifact, instance):
        return SimpleNamespace(passed=True, reasons=())

    def recompute_objective(self, artifact, instance):
        return {}

    def estimate_lower_bound(self, metric_name, instance_paths):
        return None


def test_solver_design_integration_dispatches_to_problem_owned_provider() -> None:
    calls: list[object] = []

    class Provider:
        def check_solver_design_integration(self, request):
            calls.append(request)
            return SimpleNamespace(passed=False, detail="provider blocked patch")

    class Spec:
        research_surfaces = (
            SimpleNamespace(
                name="solver_design",
                kind="solver_design",
                targets=SimpleNamespace(files=("policies/algorithm.py",)),
            ),
        )

        def contract_check_provider(self):
            return Provider()

    patch = PatchProposal(
        file_path="policies/algorithm.py",
        action="modify",
        code_content="def solve(instance, rng, time_limit_sec, context):\n    return None\n",
    )

    result = generic_c9e.check_solver_design_integration(
        patch,
        problem_spec=Spec(),
        selected_surface="solver_design",
        champion_file_content=lambda file_rel: None,
    )

    assert not result.passed
    assert result.detail == "provider blocked patch"
    assert len(calls) == 1
    assert calls[0].patch is patch


def test_contract_gate_labels_solver_design_as_generic_surface_integration() -> None:
    class Provider:
        def check_solver_design_integration(self, request):
            return SimpleNamespace(passed=True, detail="provider accepted patch")

    class Spec:
        research_surfaces = (
            SimpleNamespace(
                name="solver_design",
                kind="solver_design",
                targets=SimpleNamespace(files=("policies/algorithm.py",)),
            ),
        )

        def contract_check_provider(self):
            return Provider()

    patch = PatchProposal(
        file_path="policies/algorithm.py",
        action="modify",
        code_content="def solve(instance, rng, time_limit_sec, context):\n    return None\n",
    )

    check = ContractGate(Spec())._c9e_solver_design_integration(
        patch,
        selected_surface="solver_design",
    )

    assert check.name == "C9e_solver_design_integration"
    assert check.metadata["generic_check_alias"] == "C9e_surface_integration"
    assert check.metadata["surface_contract"] == "solver_design"
    assert check.metadata["surface_contract_scope"] == "generic_first_class_surface"


def test_production_patch_validation_requires_hypothesis_for_mechanism_surface() -> None:
    class Provider:
        def active_subject_policy(self, context=None, *, surface=None, subject_id=None):
            return {"entrypoint_paths": ("policies/algorithm.py",)}

    class Spec:
        search_space = SimpleNamespace(
            editable=("policies/*.py",),
            frozen=(),
            import_whitelist=(),
        )
        research_surfaces = (
            SimpleNamespace(
                name="solver_design",
                kind="solver_design",
                targets=SimpleNamespace(files=("policies/algorithm.py",)),
                evidence=SimpleNamespace(
                    mechanism_telemetry={
                        "guided_shift": {
                            "activation_runtime_fields": ("guided_shift_calls",)
                        }
                    }
                ),
            ),
        )

        def active_subject_policy_provider(self):
            return Provider()

    patch = PatchProposal(
        file_path="policies/algorithm.py",
        action="modify",
        code_content="def solve(instance, rng, time_limit_sec, context):\n    return None\n",
    )

    result = ContractGate(Spec()).validate_patch(
        patch,
        selected_surface="solver_design",
    )

    c12 = next(check for check in result.checks if check.name == "C12_mechanism_binding")
    assert not result.passed
    assert not c12.passed
    assert "approved_hypothesis is required for production patch validation" in c12.detail
    assert c12.metadata["reason_code"] == "hypothesis_bound_check_required"


def test_preview_patch_validation_marks_hypothesis_bound_check_skipped() -> None:
    class Provider:
        def active_subject_policy(self, context=None, *, surface=None, subject_id=None):
            return {"entrypoint_paths": ("policies/algorithm.py",)}

    class Spec:
        search_space = SimpleNamespace(
            editable=("policies/*.py",),
            frozen=(),
            import_whitelist=(),
        )
        research_surfaces = (
            SimpleNamespace(
                name="solver_design",
                kind="solver_design",
                targets=SimpleNamespace(files=("policies/algorithm.py",)),
                evidence=SimpleNamespace(
                    mechanism_telemetry={
                        "guided_shift": {
                            "activation_runtime_fields": ("guided_shift_calls",)
                        }
                    }
                ),
            ),
        )

        def active_subject_policy_provider(self):
            return Provider()

    patch = PatchProposal(
        file_path="policies/algorithm.py",
        action="modify",
        code_content="def solve(instance, rng, time_limit_sec, context):\n    return None\n",
    )

    result = ContractGate(Spec()).validate_patch(
        patch,
        selected_surface="solver_design",
        validation_mode="preview",
    )

    c12 = next(check for check in result.checks if check.name == "C12_mechanism_binding")
    assert c12.passed
    assert c12.metadata["validation_mode"] == "preview"
    assert c12.metadata["preview_skipped"] is True
    assert c12.metadata["skipped_check"] == "C12_patch_mechanism_echo"


def test_production_active_subject_provider_lookup_fails_closed() -> None:
    class Spec:
        search_space = SimpleNamespace(
            editable=("policies/*.py",),
            frozen=(),
            import_whitelist=(),
        )
        research_surfaces = (
            SimpleNamespace(
                name="solver_design",
                kind="solver_design",
                targets=SimpleNamespace(files=("policies/algorithm.py",)),
            ),
        )

    patch = PatchProposal(
        file_path="policies/algorithm.py",
        action="modify",
        code_content="def solve(instance, rng, time_limit_sec, context):\n    return None\n",
    )

    result = ContractGate(Spec()).validate_patch(
        patch,
        selected_surface="solver_design",
    )

    c9f = next(
        check for check in result.checks if check.name == "C9f_active_subject_provider"
    )
    assert not result.passed
    assert not c9f.passed
    assert c9f.metadata["reason_code"] == "active_subject_provider_unavailable"
    assert "active-subject provider unavailable" in c9f.detail


def test_preview_active_subject_provider_lookup_marks_degraded() -> None:
    class Spec:
        search_space = SimpleNamespace(
            editable=("policies/*.py",),
            frozen=(),
            import_whitelist=(),
        )
        research_surfaces = (
            SimpleNamespace(
                name="solver_design",
                kind="solver_design",
                targets=SimpleNamespace(files=("policies/algorithm.py",)),
            ),
        )

    patch = PatchProposal(
        file_path="policies/algorithm.py",
        action="modify",
        code_content="def solve(instance, rng, time_limit_sec, context):\n    return None\n",
    )

    result = ContractGate(Spec()).validate_patch(
        patch,
        selected_surface="solver_design",
        validation_mode="preview",
    )

    c9f = next(
        check for check in result.checks if check.name == "C9f_active_subject_provider"
    )
    assert c9f.passed
    assert c9f.metadata["validation_mode"] == "preview"
    assert c9f.metadata["preview_degraded"] is True
    assert c9f.metadata["reason_code"] == "active_subject_provider_unavailable"


def test_generic_solver_design_integration_facade_has_no_cvrp_solver_terms() -> None:
    source = Path(generic_c9e.__file__).read_text(encoding="utf-8")

    forbidden_terms = (
        "_ALNSVNSSolver",
        "baseline_modules",
        "baseline_algorithm.py",
        "_Solution",
        "from_routes",
        "max_routes",
        "customer",
        "route",
        "CVRP",
    )
    for term in forbidden_terms:
        assert term not in source


def test_problem_provider_fallback_rejects_mismatched_problem_import_path() -> None:
    legacy = SimpleNamespace(
        name="demo",
        adapter_import_path="scion.problems.other.adapter:DemoAdapter",
        requires_adapter_for_runtime=True,
    )

    with pytest.raises(ProblemProviderError, match="scion\\.problems\\.demo\\."):
        resolve_solver_design_prompt_provider(problem_spec=legacy)

    with pytest.raises(
        ProblemIntegrationProviderError,
        match="scion\\.problems\\.demo\\.",
    ):
        resolve_contract_check_provider(legacy)


def test_problem_provider_fallback_uses_spec_v1_for_adapter_construction(
    monkeypatch,
) -> None:
    module_name = "scion.problems.demo.adapter"
    _install_fake_adapter_module(monkeypatch, module_name, _DemoAdapter)
    spec_v1 = SimpleNamespace(
        id="demo",
        adapter=SimpleNamespace(import_path=f"{module_name}:DemoAdapter"),
        llm_hints=SimpleNamespace(marker="v1"),
    )
    legacy = SimpleNamespace(
        name="demo",
        adapter_import_path=f"{module_name}:DemoAdapter",
        requires_adapter_for_runtime=True,
        spec_v1=spec_v1,
    )

    prompt_provider = resolve_solver_design_prompt_provider(problem_spec=legacy)
    contract_provider = resolve_contract_check_provider(legacy)

    assert prompt_provider.marker == "v1"
    assert contract_provider.marker == "v1"


def test_problem_provider_prefers_loaded_adapter_without_reinstantiating(
    monkeypatch,
) -> None:
    module_name = "scion.problems.demo.adapter"
    _install_fake_adapter_module(monkeypatch, module_name, _DemoAdapter)
    spec_v1 = SimpleNamespace(
        id="demo",
        adapter=SimpleNamespace(import_path=f"{module_name}:DemoAdapter"),
        llm_hints=SimpleNamespace(marker="v1"),
    )
    legacy = SimpleNamespace(
        name="demo",
        adapter_import_path=f"{module_name}:DemoAdapter",
        requires_adapter_for_runtime=True,
        spec_v1=spec_v1,
    )
    loaded_contract_provider = SimpleNamespace(
        marker="loaded",
        check_solver_design_integration=lambda _request: SimpleNamespace(
            passed=False,
            detail="loaded adapter provider",
        ),
    )
    loaded_adapter = SimpleNamespace(
        spec=spec_v1,
        solver_design_prompt_provider=lambda: SimpleNamespace(marker="loaded"),
        contract_check_provider=lambda: loaded_contract_provider,
    )
    patch = PatchProposal(
        file_path="policies/algorithm.py",
        action="modify",
        code_content="def solve(instance, rng, time_limit_sec, context):\n    return None\n",
    )

    prompt_provider = resolve_solver_design_prompt_provider(
        problem_spec=legacy,
        adapter=loaded_adapter,
    )
    contract_provider = resolve_contract_check_provider(
        legacy,
        adapter=loaded_adapter,
    )

    assert prompt_provider.marker == "loaded"
    assert contract_provider.marker == "loaded"
    result = generic_c9e.check_solver_design_integration(
        patch,
        problem_spec=legacy,
        adapter=loaded_adapter,
        selected_surface="solver_design",
        champion_file_content=lambda _file_rel: None,
    )
    assert not result.passed
    assert result.detail == "loaded adapter provider"


def test_cvrp_adapter_exposes_problem_owned_contract_provider(tmp_path: Path) -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    problem_spec = legacy_problem_spec_from_v1(spec_v1)
    provider = resolve_contract_check_provider(problem_spec)

    assert provider is not None
    assert provider.__class__.__module__.startswith(
        "scion.problems.cvrp.contract_checks"
    )

    champion = tmp_path / "champion"
    rel_path = "policies/baseline_modules/local_search.py"
    target = champion / rel_path
    target.parent.mkdir(parents=True)
    base_code = (_CVRP_ROOT / rel_path).read_text(encoding="utf-8")
    target.write_text(base_code, encoding="utf-8")
    patch = PatchProposal(
        file_path=rel_path,
        action="modify",
        code_content=(
            base_code
            + "\n\n"
            + "def _unused_cvrp_contract_probe(solution, context):\n"
            + "    return solution\n"
        ),
    )

    result = generic_c9e.check_solver_design_integration(
        patch,
        problem_spec=problem_spec,
        selected_surface="solver_design",
        champion_file_content=lambda file_rel: (
            (champion / file_rel).read_text(encoding="utf-8")
            if (champion / file_rel).is_file()
            else None
        ),
    )

    assert not result.passed
    assert "new solver_design helper functions are not integrated" in result.detail
    assert "_unused_cvrp_contract_probe" in result.detail


def test_cvrp_active_subject_policy_owns_current_solver_design_paths() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    problem_spec = legacy_problem_spec_from_v1(spec_v1)

    policy = active_subject_policy_payload(
        problem_spec=problem_spec,
        surface="solver_design",
    )

    assert active_subject_policy_matches_path(
        policy,
        "policies/baseline_algorithm.py",
    )
    assert active_subject_policy_matches_path(
        policy,
        "policies/baseline_modules/local_search.py",
    )
    assert active_subject_policy_matches_path(
        policy,
        "policies/solver_algorithm.py",
    )
    assert policy["forbidden_entrypoint_calls"][0]["receiver_name"] == "context"
    assert policy["forbidden_entrypoint_calls"][0]["attribute_name"] == "baseline"


def test_cvrp_provider_forbidden_entrypoint_call_reaches_contract_gate() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    problem_spec = legacy_problem_spec_from_v1(spec_v1)
    gate = ContractGate(problem_spec)
    patch = PatchProposal(
        file_path="policies/baseline_algorithm.py",
        action="modify",
        code_content=(
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    run = context.baseline\n"
            "    return run(time_limit_sec=time_limit_sec)\n"
        ),
    )

    result = gate.validate_patch(patch, selected_surface="solver_design")

    c9 = next(check for check in result.checks if check.name == "C9_sensitive_api")
    assert not c9.passed
    assert "context.baseline alias" in c9.detail


def test_cvrp_provider_entrypoint_delegates_to_focused_modules() -> None:
    from scion.problems.cvrp.contract_checks import solver_design_integration

    source = Path(solver_design_integration.__file__).read_text(encoding="utf-8")

    delegated_helpers = (
        "_solver_design_import_export_error",
        "_additional_wiring_edit_error",
        "_state_model_bridge_api_error",
        "ReachabilityState",
    )
    for helper in delegated_helpers:
        assert f"import {helper}" in source or helper in source
    assert "def _solver_design_import_export_error" not in source
    assert "def _state_model_bridge_api_error" not in source
    assert "def _module_call_references" not in source
