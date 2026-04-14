# Scion — LLM-Driven Algorithm Auto-Improvement for Combinatorial Optimization

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests: 289 passed](https://img.shields.io/badge/tests-289%20passed-brightgreen.svg)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version: v0.2](https://img.shields.io/badge/version-v0.2-blue.svg)](#)

**Scion** is an LLM-driven framework for automatically improving combinatorial optimization algorithms through structured hypothesis generation, rigorous experimental validation, and parameter optimization.

> 📖 **Full documentation and experiment results → [`scion/README.md`](scion/README.md)**

## Quick Links

- **Framework code**: [`scion/`](scion/) — 57 Python files, ~11,400 lines, 289 tests
- **Architecture**: [`scion/design/scion-architecture-v3.md`](scion/design/scion-architecture-v3.md)
- **v0.2 Report**: [`scion/docs/v0.2-completion-report.md`](scion/docs/v0.2-completion-report.md)
- **Understanding guides**: [`scion/docs/understanding/`](scion/docs/understanding/) — 11 module deep-dives
- **Surrogate solver**: [`surrogate/`](surrogate/) — Warehouse delivery VNS + Solution Pool

## Repository Structure

```
or-autoresearch-agent/
├── scion/          # Scion framework (main project)
├── surrogate/      # Target problem: warehouse delivery VNS solver
├── docs/blog/      # Blog posts and public write-ups
└── reviews/        # External review documents
```

## License

MIT License
