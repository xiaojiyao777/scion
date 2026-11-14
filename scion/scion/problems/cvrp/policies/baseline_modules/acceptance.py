"""Adaptive operator weighting and acceptance rules."""
from __future__ import annotations

import math


class _AdaptiveWeights:
    def __init__(self, names, reaction_factor=0.1, min_weight=0.1):
        if not names:
            raise ValueError("at least one operator is required")
        self.names = list(names)
        self.weights = [1.0 for _ in self.names]
        self.scores = [0.0 for _ in self.names]
        self.usages = [0 for _ in self.names]
        self.reaction_factor = reaction_factor
        self.min_weight = min_weight

    def choose(self, rng):
        total = sum(self.weights)
        pick = rng.random() * total
        acc = 0.0
        for idx, weight in enumerate(self.weights):
            acc += weight
            if pick <= acc:
                return idx
        return len(self.weights) - 1

    def record(self, idx, score):
        self.usages[idx] += 1
        self.scores[idx] += float(score)

    def update(self):
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


class _SimulatedAnnealing:
    def __init__(self, initial_cost, estimated_iterations, start_ratio=0.05, end_ratio=0.0001):
        base = max(float(initial_cost), 1.0)
        self.start_temp = max(base * start_ratio, 1e-9)
        self.end_temp = max(base * end_ratio, 1e-12)
        self.temperature = self.start_temp
        estimated_iterations = max(1, int(estimated_iterations))
        self.cooling_rate = (self.end_temp / self.start_temp) ** (1.0 / estimated_iterations)

    def accept(self, current_cost, candidate_cost, rng):
        delta = float(candidate_cost) - float(current_cost)
        if delta <= 0:
            return True
        if self.temperature <= 0:
            return False
        return rng.random() < math.exp(-delta / self.temperature)

    def cool(self):
        self.temperature = max(self.end_temp, self.temperature * self.cooling_rate)
