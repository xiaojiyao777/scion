"""A fresh campaign inherits ordinary source and optional H-only history."""

import subprocess
import sys
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace

import pytest
from scion.core.campaign import CampaignManager
from scion.core.models import BranchState, ChampionState, Decision, ExperimentStage
from scion.core.research_history import load_research_histories, problem_id_from_spec
from scion.problem.preflight import (
    ResearchEnvironmentPreflightError,
    run_research_environment_preflight,
)
from scion.proposal.mock_client import MockLLMClient
from scion.runtime.workspace import WorkspaceMaterializer, validate_source_tree

from .campaign_test_support import (
    _VALID_HYPOTHESIS,
    _VALID_PATCH_REPAIR,
    AlwaysPassVerificationGate,
    MockExperimentProtocol,
    _campaign,
    _make_protocol_result,
)


@pytest.mark.parametrize("include_history", (False, True))
def test_fresh_campaign_from_terminal_branch_tree(tmp_path, include_history):
    old = _campaign(
        tmp_path / "old",
        experiment_protocol=MockExperimentProtocol(
            results=[_make_protocol_result(ExperimentStage.SCREENING, "fail")]
        ),
    )
    assert old.run(requested_rounds=1).completed
    old_branch = old._branch_ctrl.get_active_branches()[0]
    source = Path(old._branch_workspaces[old_branch.branch_id])
    original_files = {
        path.relative_to(source): path.read_bytes()
        for path in source.rglob("*")
        if path.is_file()
    }
    assert (
        "candidate = solution"
        in original_files[Path("operators/local_search.py")].decode()
    )
    history = (
        load_research_histories(
            [Path(old._campaign_dir) / "research_history.jsonl"],
            expected_problem_id=problem_id_from_spec(old._problem_runtime.spec),
        )
        if include_history
        else ()
    )

    class RecordingClient(MockLLMClient):
        def __init__(self):
            super().__init__(
                hypothesis_response=_VALID_HYPOTHESIS,
                patch_response={
                    **_VALID_PATCH_REPAIR,
                    "new_string": "        return (candidate)\n",
                },
            )
            self.prompts = []

        def call_with_tool(
            self, prompt, tool, model=None, system_blocks=None, request_kind=None
        ):
            self.prompts.append(
                "\n".join([prompt, *(block["text"] for block in (system_blocks or []))])
            )
            return super().call_with_tool(
                prompt,
                tool,
                model=model,
                system_blocks=system_blocks,
                request_kind=request_kind,
            )

    client = RecordingClient()
    fresh = CampaignManager(
        protocol_config=old._protocol_config,
        split_manifest=old._split_manifest,
        seed_ledger=old._seed_ledger,
        llm_client=client,
        champion=ChampionState(
            version=1, operator_pool={}, code_snapshot_path=str(source)
        ),
        campaign_dir=str(tmp_path / "fresh"),
        experiment_protocol=MockExperimentProtocol(results=[]),
        adapter=old._problem_runtime.adapter,
        verification_gate=AlwaysPassVerificationGate(),
        research_history=history,
    )
    snapshot = Path(fresh._champion.code_snapshot_path)
    assert snapshot != source
    assert snapshot.is_relative_to(tmp_path / "fresh")
    assert {
        path.relative_to(snapshot): path.read_bytes()
        for path in snapshot.rglob("*")
        if path.is_file()
    } == original_files
    assert fresh._branch_ctrl.get_active_branches() == []
    assert fresh._step_history == []
    assert fresh._branch_patches == {}
    assert fresh._provider_call_budget.snapshot().budget_admitted == 0
    assert fresh._problem_runtime.research_history == history

    screened = fresh.run_one_step()
    assert screened.decision is Decision.QUEUE_VALIDATE
    branch = fresh._branch_ctrl.get_branch(screened.branch_id)
    assert branch.branch_id != old_branch.branch_id
    assert len(branch.accepted_changes) == 1
    assert "candidate = solution" in client.prompts[0]
    assert "candidate = solution" in client.prompts[1]
    workspace = fresh._branch_workspaces[branch.branch_id]
    calls_after_screening = client._call_count
    assert fresh.run_one_step().decision is Decision.QUEUE_FROZEN
    assert fresh._branch_workspaces[branch.branch_id] == workspace
    assert fresh.run_one_step().decision is Decision.PROMOTE
    assert client._call_count == calls_after_screening
    assert branch.state is BranchState.PROMOTED
    assert {
        path.relative_to(source): path.read_bytes()
        for path in source.rglob("*")
        if path.is_file()
    } == original_files
    state = fresh.get_state()
    assert state["initial_source_tree"] == str(source)
    assert state["champion_source_tree"] == fresh._champion.code_snapshot_path


def test_initial_snapshot_is_isolated_and_existing_snapshot_is_never_replaced(tmp_path):
    source = tmp_path / "chosen"
    source.mkdir()
    (source / "algorithm.py").write_text("VERSION = 2\n")
    materializer = WorkspaceMaterializer(str(tmp_path / "fresh"))
    champion = ChampionState(
        version=1, operator_pool={}, code_snapshot_path=str(source)
    )
    snapshot = Path(
        materializer.create_champion_snapshot(champion, materializer._champions_dir)
    )
    (source / "algorithm.py").write_text("VERSION = 3\n")
    assert (snapshot / "algorithm.py").read_text() == "VERSION = 2\n"
    with pytest.raises(FileExistsError):
        materializer.create_champion_snapshot(champion, materializer._champions_dir)
    assert (snapshot / "algorithm.py").read_text() == "VERSION = 2\n"


def test_source_tree_rejects_missing_directory_and_recursive_output(tmp_path):
    with pytest.raises(ValueError, match="not a directory"):
        validate_source_tree(str(tmp_path / "missing"), str(tmp_path / "fresh"))
    with pytest.raises(ValueError, match="outside the source tree"):
        validate_source_tree(str(tmp_path), str(tmp_path / "fresh"))


def test_research_preflight_checks_selected_tree_instead_of_problem_root(tmp_path):
    package = tmp_path / "package"
    package.mkdir()
    (package / "algorithm.py").write_text("VALUE = 1\n")
    selected = tmp_path / "selected"
    selected.mkdir()
    spec = SimpleNamespace(
        root_dir=str(package),
        research_surfaces=[
            SimpleNamespace(
                name="algorithm",
                targets=SimpleNamespace(
                    files=["algorithm.py"],
                    modify_allowed=True,
                    create_new_allowed=False,
                    remove_allowed=False,
                ),
            )
        ],
    )
    assert run_research_environment_preflight(spec).passed
    with pytest.raises(
        ResearchEnvironmentPreflightError, match="no materialized target"
    ):
        run_research_environment_preflight(spec, source_root=str(selected))


def test_fresh_process_can_research_a_terminal_branch_tree(tmp_path):
    old = _campaign(tmp_path / "old")
    assert old.run(requested_rounds=1).completed
    branch = old._branch_ctrl.get_active_branches()[0]
    source = old._branch_workspaces[branch.branch_id]
    script = dedent("""
        import sys
        from scion.tests.campaign_test_support import (
            _make_problem_spec, _make_protocol_config, _make_split_manifest,
            _make_seed_ledger, _VALID_HYPOTHESIS, _VALID_PATCH_REPAIR,
            AlwaysPassVerificationGate, MockExperimentProtocol,
            CampaignManager, ChampionState, MockLLMClient, protocol_test_adapter,
        )
        protocol = MockExperimentProtocol(results=[])
        spec = _make_problem_spec(sys.argv[1]).model_copy(
            update={"objectives": protocol._metric_specs}
        )
        manager = CampaignManager(
            protocol_config=_make_protocol_config(),
            split_manifest=_make_split_manifest().model_copy(update={"canary": ["canary"]}),
            seed_ledger=_make_seed_ledger().model_copy(update={"canary": [7]}),
            llm_client=MockLLMClient(
                hypothesis_response=_VALID_HYPOTHESIS,
                patch_response={**_VALID_PATCH_REPAIR, "new_string": "        return (candidate)\\n"},
            ),
            champion=ChampionState(version=1, operator_pool={}, code_snapshot_path=sys.argv[1]),
            campaign_dir=sys.argv[2], experiment_protocol=protocol,
            adapter=protocol_test_adapter(protocol._metric_specs, problem_spec=spec),
            verification_gate=AlwaysPassVerificationGate(),
        )
        assert manager._branch_ctrl.get_active_branches() == []
        assert manager._step_history == []
        assert manager._problem_runtime.research_history == ()
        result = manager.run_one_step()
        assert result.branch_id != sys.argv[3]
        assert result.decision.value == "queue_validate", result
    """)
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            source,
            str(tmp_path / "cold"),
            branch.branch_id,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
