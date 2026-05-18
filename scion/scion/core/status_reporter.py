"""Small JSON status snapshots for long-running campaigns."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from scion.core.public_refs import redact_public_refs


class StatusReporter:
    """Write the latest campaign status to ``status.json`` atomically."""

    def __init__(self, campaign_dir: str, filename: str = "status.json") -> None:
        self._path = Path(campaign_dir) / filename

    @property
    def path(self) -> Path:
        return self._path

    def write(self, payload: Mapping[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **redact_public_refs(dict(payload), base_dir=self._path.parent),
        }
        tmp_path = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(data, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        os.replace(tmp_path, self._path)
