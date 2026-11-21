"""Lossless paging and visible-only research material access (P2 S12)."""
import base64
from pathlib import Path

import pytest

from scion.observation.materials import ResearchMaterials
from scion.observation.source import ObservationError


def store(tmp_path, **kwargs):
    return ResearchMaterials(tmp_path, **{
        "max_storage_bytes": 2048, "max_read_bytes": 8,
        "max_search_matches": 2, "max_search_scan_bytes": 8, **kwargs})


def test_unicode_bytes_can_be_reassembled(tmp_path):
    materials = store(tmp_path)
    raw = "组合优化😀研究".encode()
    ref = materials.append("note", raw)
    got, offset = b"", 0
    while True:
        page = materials.read(ref, visible=(ref,), offset=offset, length=2)
        got += base64.b64decode(page["data"])
        offset = page["next_offset"]
        if page["complete"]:
            break
    assert got == raw
    assert materials.read(ref, visible=(ref,), offset=len(raw), length=2)["complete"]
    with pytest.raises(ObservationError):
        materials.read(ref, visible=(ref,), offset=len(raw)+1, length=2)


def test_search_preserves_overlaps_pages_and_file_order(tmp_path):
    materials = store(tmp_path)
    refs = tuple(materials.append("note", data) for data in (b"000000ababa0000ababa", b"ababa"))
    cursor = None
    matches = []
    for _ in range(20):
        page = materials.search("aba", visible=refs, max_matches=1, cursor=cursor)
        matches += [(m["ref"], m["byte_offset"]) for m in page["matches"]]
        if page["complete"]:
            break
        assert page["next_cursor"] != cursor
        cursor = page["next_cursor"]
    else:
        pytest.fail("search failed to make progress")
    assert matches == [(refs[0], n) for n in (6, 8, 15, 17)] + [(refs[1], n) for n in (0, 2)]


def test_guessing_a_ref_never_grants_read_or_search_access(tmp_path):
    materials = store(tmp_path)
    public = materials.append("note", b"public")
    private = materials.append("note", b"private")
    with pytest.raises(ObservationError, match="REF_NOT_VISIBLE"):
        materials.read(private, visible=(public,), offset=0, length=4)
    with pytest.raises(ObservationError, match="REF_NOT_VISIBLE"):
        materials.search("private", visible=(public,), max_matches=1,
                         cursor={"ref": private, "byte_offset": 0})
    assert materials.search("private", visible=(public,), max_matches=1)["matches"] == []


def test_no_overwrite_on_budget_failure_or_io_error(tmp_path, monkeypatch):
    materials = store(tmp_path, max_storage_bytes=5)
    ref = materials.append("note", b"loss")
    with pytest.raises(ObservationError, match="GLOBAL_RESEARCH_LIMIT"):
        materials.append("note", b"win")
    assert (tmp_path / ref).read_bytes() == b"loss"
    def fail_rename(*args):
        raise OSError("disk failed")
    monkeypatch.setattr(Path, "rename", fail_rename)
    with pytest.raises(ObservationError, match="PERSISTENCE_ERROR"):
        materials.append("note", b"x")
    assert not (tmp_path / "materials/000002.note").exists()


def test_symlink_and_noncanonical_material_refs_rejected(tmp_path):
    materials = store(tmp_path)
    (tmp_path / "link").symlink_to("/etc/passwd")
    for ref in ("link", "../outside", "/etc/passwd"):
        with pytest.raises(ObservationError, match="REF_NOT_VISIBLE"):
            materials.read(ref, visible=(ref,), offset=0, length=4)
