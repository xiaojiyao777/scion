"""Constants shared by the direct V3 contract checks."""

from __future__ import annotations

import re

PREDICTED_DIRECTIONS = frozenset({"improve", "tradeoff", "exploratory"})
MECHANISM_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
