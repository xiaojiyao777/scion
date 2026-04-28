from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .models import Solution

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")


def plot_routes(solution: Solution, output: str | None = None, show: bool = True) -> Any:
    """Plot CVRP routes and optionally save the figure."""
    import matplotlib.pyplot as plt

    inst = solution.instance
    fig, ax = plt.subplots(figsize=(9, 7))
    cmap = plt.get_cmap("tab20")

    for idx, route in enumerate(solution.routes):
        nodes = [inst.depot] + route.customers + [inst.depot]
        xs = [inst.coords[n, 0] for n in nodes]
        ys = [inst.coords[n, 1] for n in nodes]
        color = cmap(idx % cmap.N)
        ax.plot(xs, ys, "-", color=color, linewidth=1.5, alpha=0.85)
        ax.scatter(xs[1:-1], ys[1:-1], s=22, color=color, alpha=0.9)

    depot_x, depot_y = inst.coords[inst.depot]
    ax.scatter([depot_x], [depot_y], marker="s", s=90, color="red", label="Depot", zorder=5)
    ax.set_title(f"{inst.name}: {solution.total_cost:.3f}")
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")

    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output, dpi=160, bbox_inches="tight")
    if show:
        plt.show()
    return fig


def plot_convergence(
    history: list[dict[str, float]],
    bks_cost: float | None = None,
    output: str | None = None,
    show: bool = True,
) -> Any:
    """Plot best-cost convergence history."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 5))
    xs = [row.get("elapsed", row.get("iteration", 0.0)) for row in history]
    ys = [row["best"] for row in history]
    ax.plot(xs, ys, linewidth=1.8, label="Best")
    if bks_cost is not None and bks_cost > 0:
        ax.axhline(bks_cost, color="red", linestyle="--", linewidth=1.2, label="BKS")
    ax.set_xlabel("Elapsed time (s)")
    ax.set_ylabel("Cost")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")

    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output, dpi=160, bbox_inches="tight")
    if show:
        plt.show()
    return fig
