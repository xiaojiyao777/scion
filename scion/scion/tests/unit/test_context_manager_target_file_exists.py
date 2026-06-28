from __future__ import annotations

from scion.proposal.context_manager.manager import _target_file_exists_in_root


def test_target_file_exists_in_root_uses_current_imports(tmp_path):
    target = tmp_path / "policies" / "candidate.py"
    target.parent.mkdir()
    target.write_text("VALUE = 1\n", encoding="utf-8")

    assert _target_file_exists_in_root(
        str(tmp_path),
        "policies/candidate.py",
    )
    assert not _target_file_exists_in_root(
        str(tmp_path),
        "policies/missing.py",
    )
