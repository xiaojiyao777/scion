"""The normal CLI selects a source value without reopening campaign state."""

from types import SimpleNamespace

import pytest
from scion.cli.commands import init_run
from scion.cli.main import app
from scion.core import campaign
from typer.testing import CliRunner

from .campaign_test_support import _campaign


@pytest.mark.parametrize("explicit", (False, True))
def test_run_selects_source_tree_and_its_problem_configuration(
    tmp_path, monkeypatch, explicit
):
    original = _campaign(tmp_path / "original")
    adapter = original._problem_runtime.adapter
    monkeypatch.setattr(init_run, "_load_cli_problem_adapter", lambda _path: adapter)
    definition = tmp_path / "problem.yaml"
    definition.write_text("name: test_vrp\n")
    chosen = tmp_path / "chosen"
    chosen.mkdir()
    (chosen / "registry.yaml").write_text(
        "operators:\n"
        "  - name: selected\n"
        "    file_path: operators/selected.py\n"
        "    category: local_search\n"
        "    weight: 1.0\n"
        "    class_name: Selected\n"
    )
    captured = {}

    class RecordingManager:
        def __init__(self, **values):
            captured.update(values)

        def run(self, **_kwargs):
            return SimpleNamespace(completed=True)

        def get_state(self):
            return {"n_experiments": 0, "champion_version": 1, "n_active_branches": 0}

    monkeypatch.setattr(campaign, "CampaignManager", RecordingManager)
    arguments = [
        "run",
        "--mock-llm",
        "--rounds",
        "1",
        "--problem",
        str(definition),
        "--campaign-dir",
        str(tmp_path / "fresh"),
    ]
    if explicit:
        arguments += ["--source-tree", str(chosen)]
    result = CliRunner().invoke(app, arguments)

    assert result.exit_code == 0, result.output
    assert captured["adapter"] is adapter
    assert captured["champion"].version == 1
    assert captured["champion"].weight_revision == 0
    assert captured["champion"].code_snapshot_path == (
        str(chosen) if explicit else adapter.spec.root_dir
    )
    assert set(captured["champion"].operator_pool) == (
        {"selected"} if explicit else set()
    )
    assert captured["research_history"] == ()


def test_cli_missing_source_fails_before_provider_or_campaign(tmp_path, monkeypatch):
    original = _campaign(tmp_path / "original")
    monkeypatch.setattr(
        init_run,
        "_load_cli_problem_adapter",
        lambda _path: original._problem_runtime.adapter,
    )
    definition = tmp_path / "problem.yaml"
    definition.write_text("name: test_vrp\n")

    def must_not_construct(**_kwargs):
        pytest.fail("invalid source must be rejected before constructing a campaign")

    monkeypatch.setattr(campaign, "CampaignManager", must_not_construct)
    result = CliRunner().invoke(
        app,
        [
            "run",
            "--mock-llm",
            "--problem",
            str(definition),
            "--source-tree",
            str(tmp_path / "missing"),
            "--campaign-dir",
            str(tmp_path / "fresh"),
        ],
    )
    assert result.exit_code == 1
    assert "source tree is not a directory" in result.output
    assert not (tmp_path / "fresh").exists()
