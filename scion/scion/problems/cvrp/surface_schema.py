"""CVRP adapter-owned active solver-design preview constants."""
from __future__ import annotations

_POLICY_PREVIEW_TIME_LIMIT_SEC = 5.0
_POLICY_PREVIEW_EXEC_TIMEOUT_SEC = 2.0

_POLICY_INSTANCE_API_TEXT = (
    "Safe CvrpInstance API for solver-design code: use `instance.depot`, "
    "`instance.customer_ids`, `instance.customer_count`, "
    "`instance.demands[customer_id]`, `instance.capacity`, "
    "`instance.distance(i, j)`, `instance.route_load(route)`, and "
    "`instance.route_distance(route)`. `instance.demand(customer_id)` remains "
    "available for direct demand lookup. Never use `instance.customers`; that "
    "attribute is intentionally not defined and will fail preview or runtime "
    "audit when reached."
)
