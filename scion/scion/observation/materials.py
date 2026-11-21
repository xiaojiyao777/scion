"""Ordinary append-only files with caller-supplied visibility, never authority."""
from __future__ import annotations

import base64
from pathlib import Path
import tempfile

from scion.observation.source import ObservationError


class ResearchMaterials:
    def __init__(self, root: Path, *, max_storage_bytes: int, max_read_bytes: int,
                 max_search_matches: int, max_search_scan_bytes: int):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.max_storage_bytes = max_storage_bytes
        self.max_read_bytes = max_read_bytes
        self.max_search_matches = max_search_matches
        self.max_search_scan_bytes = max_search_scan_bytes

    def used_bytes(self):
        return sum(p.stat().st_size for p in self.root.rglob("*") if p.is_file())

    def append(self, kind: str, content: bytes):
        if kind not in {"note", "script", "input"} or type(content) is not bytes:
            raise ObservationError("REQUEST_INVALID")
        if self.used_bytes() + len(content) > self.max_storage_bytes:
            raise ObservationError("GLOBAL_RESEARCH_LIMIT")
        directory = self.root / "materials"
        directory.mkdir(exist_ok=True)
        ordinal = len(tuple(p for p in directory.iterdir() if not p.name.startswith("."))) + 1
        ref = f"materials/{ordinal:06d}.{kind}"
        try:
            with tempfile.NamedTemporaryFile(dir=directory, prefix=".pending-", delete=False) as stream:
                stream.write(content)
                pending = Path(stream.name)
            if (self.root / ref).exists():
                raise OSError("material destination already exists")
            pending.rename(self.root / ref)
        except OSError:
            # A partial file is diagnostic only; it is never returned as a ref.
            raise ObservationError("PERSISTENCE_ERROR") from None
        return ref

    def _file(self, ref: str, visible: tuple[str, ...]):
        if type(ref) is not str or ref not in visible:
            raise ObservationError("REF_NOT_VISIBLE")
        parts = ref.split("/")
        if any(part in {"", ".", ".."} for part in parts) or "\\" in ref:
            raise ObservationError("REF_NOT_VISIBLE")
        path = self.root
        for part in parts:
            path /= part
            if path.is_symlink():
                raise ObservationError("REF_NOT_VISIBLE")
        if not path.is_file() or path.stat().st_nlink != 1:
            raise ObservationError("REF_NOT_VISIBLE")
        return path

    def read(self, ref: str, *, visible: tuple[str, ...], offset: int, length: int):
        if type(offset) is not int or offset < 0 or type(length) is not int or not 0 < length <= self.max_read_bytes:
            raise ObservationError("REQUEST_INVALID")
        path = self._file(ref, visible)
        size = path.stat().st_size
        if offset > size:
            raise ObservationError("REQUEST_INVALID")
        with path.open("rb") as stream:
            stream.seek(offset)
            data = stream.read(length)
        return {"ref": ref, "offset": offset, "next_offset": offset + len(data),
                "total_bytes": size, "encoding": "base64", "data": base64.b64encode(data).decode("ascii"),
                "complete": offset + len(data) == size}

    def search(self, query: str, *, visible: tuple[str, ...], max_matches: int,
               cursor: dict | None = None):
        if (type(query) is not str or not query or type(max_matches) is not int
                or not 0 < max_matches <= self.max_search_matches):
            raise ObservationError("REQUEST_INVALID")
        if len(query) > self.max_search_scan_bytes:
            raise ObservationError("LIMIT_NOT_AVAILABLE")
        try:
            needle = query.encode("utf-8")
        except UnicodeError:
            raise ObservationError("REQUEST_INVALID") from None
        if len(needle) > self.max_search_scan_bytes:
            raise ObservationError("LIMIT_NOT_AVAILABLE")
        refs = tuple(dict.fromkeys(visible))
        start, offset = 0, 0
        if cursor is not None:
            if type(cursor) is not dict or set(cursor) != {"ref", "byte_offset"} or cursor["ref"] not in refs:
                raise ObservationError("REF_NOT_VISIBLE")
            start, offset = refs.index(cursor["ref"]), cursor["byte_offset"]
            if type(offset) is not int or offset < 0:
                raise ObservationError("REQUEST_INVALID")
        matches = []
        remaining = self.max_search_scan_bytes
        for index in range(start, len(refs)):
            ref = refs[index]
            path = self._file(ref, refs)
            size = path.stat().st_size
            if offset > size:
                raise ObservationError("REQUEST_INVALID")
            with path.open("rb") as stream:
                stream.seek(offset)
                data = stream.read(remaining)
            remaining -= len(data)
            end = offset + len(data)
            at_end = end == size
            # Retain the suffix whose match may cross the next page boundary.
            stop = len(data) if at_end else max(0, len(data) - len(needle) + 1)
            pos = 0
            while pos < stop:
                match = data.find(needle, pos)
                if match < 0:
                    break
                matches.append({"ref": ref, "byte_offset": offset + match, "byte_length": len(needle)})
                pos = match + 1
                if len(matches) == max_matches:
                    return {"matches": matches, "next_cursor": {"ref": ref, "byte_offset": offset + pos}, "complete": False}
            if not at_end:
                return {"matches": matches, "next_cursor": {"ref": ref, "byte_offset": offset + stop}, "complete": False}
            offset = 0
            if remaining < len(needle) and index + 1 < len(refs):
                return {"matches": matches, "next_cursor": {"ref": refs[index + 1], "byte_offset": 0}, "complete": False}
        return {"matches": matches, "complete": True}
