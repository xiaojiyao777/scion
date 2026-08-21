"""Ordinary source/history inventories for bounded hypothesis research."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from copy import deepcopy
from typing import Any

from scion.core.paths import normalize_relative_patch_path
from scion.proposal.bounded_research import bounded_json, text_line_count
from scion.proposal.context_manager.source_graph import source_graph_links

HISTORY_KEYS = (
    "prior_research_observations",
    "prior_research_history",
    "pre_protocol_observations",
    "experiment_history",
)
_HEADLINE_FIELDS = (
    "text",
    "hypothesis_text",
    "change_locus",
    "action",
    "target_file",
    "predicted_direction",
    "target_weakness",
    "expected_effect",
)
_FACT_FIELDS = (
    "outcome",
    "stage",
    "reason_code",
    "severity",
    "gate_outcome",
    "decision",
    "value",
    "reason_codes",
    "engine_reason_codes",
    "diagnostic_reason_codes",
    "bypass_reason_codes",
)


def build_hypothesis_research_corpus(
    context: Mapping[str, Any],
    *,
    public_sources: Sequence[Mapping[str, Any]] = (),
    qualified_prefixes: tuple[str, ...] = (),
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Return complete ordinary indexes and an identity-free compact context."""

    sources = _sources(
        context,
        public_sources=public_sources,
        qualified_prefixes=qualified_prefixes,
    )
    histories = _histories(context)
    compact = deepcopy(dict(context))
    compact.pop("branch_id", None)
    compact.pop("champion_version", None)
    marker = {"indexed": True, "source_count": len(sources)}
    for key in ("champion_operators_code", "branch_current_code"):
        if key in compact:
            compact[key] = marker
    for key in HISTORY_KEYS:
        if key in compact:
            compact[key] = {
                "indexed": True,
                "record_count": sum(entry["kind"] == key for entry in histories),
            }
    return sources, histories, compact


def iter_string_leaves(value: Any, path: str = "$") -> Iterator[tuple[str, str]]:
    """Yield searchable strings lazily so result caps stop corpus traversal."""

    if isinstance(value, str):
        yield path, value
    elif isinstance(value, Mapping):
        for key, child in value.items():
            yield from iter_string_leaves(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_string_leaves(child, f"{path}[{index}]")


def _sources(
    context: Mapping[str, Any],
    *,
    public_sources: Sequence[Mapping[str, Any]],
    qualified_prefixes: tuple[str, ...],
) -> list[dict[str, Any]]:
    declared = context.get("existing_target_files", [])
    if not isinstance(declared, list) or any(
        not isinstance(path, str) for path in declared
    ):
        raise TypeError("hypothesis source inventory must be an array of paths")
    paths = {_source_path(path) for path in declared}
    found = _parse_bundle(context.get("champion_operators_code"), "champion", paths)
    found.update(_parse_bundle(context.get("branch_current_code"), "branch", paths))
    public = _public_sources(public_sources, forbidden_paths=paths | set(found))
    graph_input = {
        path: found.get(path, ("declared", None))[1]
        for path in sorted(paths | set(found))
    }
    links = source_graph_links(graph_input, qualified_prefixes=qualified_prefixes)
    entries: list[dict[str, Any]] = []
    for number, path in enumerate(sorted(paths | set(found) | set(public)), 1):
        owner, body = found.get(path, ("declared", None))
        public_entry = public.get(path)
        if public_entry is not None:
            owner, body = "development", public_entry["content"]
        ref = f"source-{number:04d}"
        index = {
            "ref": ref,
            "path": path,
            "owner": owner,
            "available": body is not None,
            "chars": len(body) if body is not None else 0,
            "bytes": len(body.encode()) if body is not None else 0,
            "lines": text_line_count(body) if body is not None else 0,
        }
        if public_entry is not None:
            index.update(roles=["public_test"], check_name=public_entry["check_name"])
        else:
            index.update(links.get(path, {"dependencies": (), "callers": ()}))
        entries.append({"ref": ref, "path": path, "body": body, "index": index})
    return entries


def _public_sources(
    values: Sequence[Mapping[str, Any]], *, forbidden_paths: set[str]
) -> dict[str, dict[str, str]]:
    public: dict[str, dict[str, str]] = {}
    for raw in values:
        if not isinstance(raw, Mapping) or set(raw) != {
            "path",
            "check_name",
            "content",
        }:
            raise ValueError("public hypothesis source has unknown or missing fields")
        path = _source_path(raw["path"])
        check_name, content = raw["check_name"], raw["content"]
        if check_name not in {"D3_unit_tests", "D4_regression_tests"}:
            raise ValueError("public hypothesis source has an invalid check_name")
        if not isinstance(content, str):
            raise TypeError("public hypothesis source content must be text")
        if path in forbidden_paths or path in public:
            raise ValueError(f"duplicate hypothesis research source path: {path}")
        public[path] = {"check_name": check_name, "content": content}
    return public


def _parse_bundle(
    value: Any, owner: str, declared: set[str]
) -> dict[str, tuple[str, str | None]]:
    if value is None or value == "":
        return {}
    if not isinstance(value, str):
        raise TypeError("hypothesis source bundle must be text")
    lines, found, cursor = value.splitlines(keepends=True), {}, 0
    while cursor < len(lines):
        heading = lines[cursor].rstrip("\r\n")
        if not heading.startswith("### "):
            cursor += 1
            continue
        path = _heading_path(heading[4:], declared)
        if path is None:
            cursor += 1
            continue
        if path in found:
            raise ValueError(f"duplicate source section in hypothesis context: {path}")
        if cursor + 1 < len(lines) and lines[cursor + 1].startswith("```"):
            end = cursor + 2
            while end < len(lines) and not lines[end].startswith("```"):
                end += 1
            if end == len(lines):
                raise ValueError(
                    f"unterminated source section in hypothesis context: {path}"
                )
            found[path] = (owner, "".join(lines[cursor + 2 : end]))
            cursor = end + 1
        else:
            if "deleted from branch" in heading:
                found[path] = (owner, None)
            cursor += 1
    if not found and len(declared) == 1 and "### " not in value:
        found[next(iter(declared))] = (owner, value)
    return found


def _heading_path(label: str, declared: set[str]) -> str | None:
    matches = [
        path for path in declared if label == path or label.startswith(f"{path} (")
    ]
    if matches:
        return max(matches, key=len)
    try:
        return _source_path(label.split(" (", 1)[0])
    except (TypeError, ValueError):
        return None


def _source_path(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError("hypothesis source path must be text")
    path = normalize_relative_patch_path(value)
    if path != value:
        raise ValueError("hypothesis source path must be canonical")
    return path


def _histories(context: Mapping[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for kind in HISTORY_KEYS:
        records = context.get(kind)
        if records is None:
            continue
        if not isinstance(records, list) or any(
            not isinstance(item, Mapping) for item in records
        ):
            raise TypeError(f"hypothesis {kind} must be an array of records")
        for ordinal, raw in enumerate(records, 1):
            record = deepcopy(dict(raw))
            ref = f"history-{len(entries) + 1:04d}"
            index: dict[str, Any] = {
                "ref": ref,
                "kind": kind,
                "ordinal": ordinal,
                "sections": sorted(record),
            }
            headline = next(
                (
                    record[key]
                    for key in ("hypothesis", "proposal_intent")
                    if isinstance(record.get(key), Mapping)
                ),
                None,
            )
            if headline:
                index["hypothesis"] = {
                    field: deepcopy(headline[field])
                    for field in _HEADLINE_FIELDS
                    if field in headline
                }
            facts = _facts(record)
            if facts:
                index["outcomes"] = facts
            patch = record.get("patch")
            changes = patch.get("changes") if isinstance(patch, Mapping) else None
            if isinstance(changes, list):
                index["patch_change_count"] = len(changes)
            entries.append(
                {
                    "ref": ref,
                    "kind": kind,
                    "ordinal": ordinal,
                    "record": record,
                    "body": bounded_json(record),
                    "index": index,
                }
            )
    return entries


def _facts(value: Any, path: str = "$") -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        selected = {
            key: deepcopy(value[key])
            for key in _FACT_FIELDS
            if key in value
            and (
                value[key] is None
                or isinstance(value[key], (str, bool, int, float))
                or (
                    isinstance(value[key], list)
                    and all(isinstance(item, str) for item in value[key])
                )
            )
        }
        if selected:
            facts.append({"field": path, **selected})
        for key, child in value.items():
            if key not in {"patch", "source", "code", "content"}:
                facts.extend(_facts(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            facts.extend(_facts(child, f"{path}[{index}]"))
    return facts


__all__ = [
    "build_hypothesis_research_corpus",
    "iter_string_leaves",
]
