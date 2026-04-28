from __future__ import annotations

import random


class AdaptiveWeights:
    """Roulette-wheel operator weights with segmented score updates."""

    def __init__(
        self,
        names: list[str],
        reaction_factor: float = 0.1,
        min_weight: float = 0.1,
    ):
        if not names:
            raise ValueError("At least one operator is required")
        self.names = list(names)
        self.weights = [1.0 for _ in names]
        self.scores = [0.0 for _ in names]
        self.usages = [0 for _ in names]
        self.reaction_factor = reaction_factor
        self.min_weight = min_weight

    def choose(self, rng: random.Random) -> int:
        total = sum(self.weights)
        pick = rng.random() * total
        acc = 0.0
        for idx, weight in enumerate(self.weights):
            acc += weight
            if pick <= acc:
                return idx
        return len(self.weights) - 1

    def record(self, idx: int, score: float) -> None:
        self.usages[idx] += 1
        self.scores[idx] += score

    def update(self) -> None:
        r = self.reaction_factor
        for idx, weight in enumerate(self.weights):
            if self.usages[idx] > 0:
                observed = self.scores[idx] / self.usages[idx]
                self.weights[idx] = max(
                    self.min_weight,
                    (1.0 - r) * weight + r * observed,
                )
        self.scores = [0.0 for _ in self.names]
        self.usages = [0 for _ in self.names]

    def snapshot(self) -> dict[str, float]:
        return dict(zip(self.names, self.weights))
