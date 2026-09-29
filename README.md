# Agentic-Index-Research-Harness

This repository implements an **agentic research harness for systematic multi-asset ETF index construction**, covering 50+ ETFs across equities, rates, credit, and commodities. The framework combines autonomous hypothesis generation with rule-based experiment execution and validation.

The research pipeline evaluates 10+ ETF allocation strategies against **60/40, equal-weight, and risk-parity benchmarks** using walk-forward backtesting with transaction costs, turnover constraints, and out-of-sample evaluation.

To keep agent-generated research reproducible and auditable, the harness implements **deterministic validation controls** using Pydantic schemas, including structured-output constraints, provenance tracking, hallucination checks, and experiment audit logs.

An automated **experiment registry** tracks 100+ research runs, recording hypotheses, parameter changes, rejected strategies, validation outcomes, and out-of-sample results. This provides a complete research trail and prevents the agent from silently modifying assumptions or discarding unsuccessful experiments.

## Project status

| Area | Status | Current scope |
|---|---|---|
| Campaign Controller | Complete | P1 deterministic governance slice |
| Financial engine | Not started | No portfolio accounting or backtesting yet |
| Public market data | Not started | No provider, ETF universe or live data selected |
| Research campaigns | Not started | Only synthetic controller workflows are supported |
| Dashboard | Deferred | Planned after the CLI workflow is stable |
| Codex CLI wrapper | Deferred | Not activated in the current phase |

The current release is a synthetic-only governance foundation. It can demonstrate controlled campaign state transitions, approvals, budgets and audit records, but it does not contain investment results or performance claims.

## Current architecture

The current implementation is organized as a small deterministic Python package:

```text
CLI (Typer)
  -> Controller services
      -> Pydantic domain schemas
      -> Policy and approval matching
      -> SQLite append-only registry
          -> events, trials, evidence and replayed state
```

The Coordinator and bounded agent roles operate outside the calculation engine. The Campaign Controller owns state transitions, permissions, approvals, budget reservations and evidence records. The initial workflow is local and interactive. It does not call an LLM API and does not include a financial executor or unattended wrapper.

## Requirements and installation

- Python 3.12 or newer
- Git
- A virtual environment is recommended

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.lock
.venv/bin/python -m pip install --no-build-isolation --no-deps -e .
```

## Commands

Run the test suite and static checks:

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
.venv/bin/mypy src
.venv/bin/etf-harness --help
```

The synthetic CLI workflow is exercised with:

```bash
.venv/bin/python -m pytest -q tests/test_cli.py::test_synthetic_cli_acceptance_lifecycle
```

The CLI accepts UTF-8 JSON artifacts and supports campaign creation, hypothesis proposal, approval import, status inspection and administrative closure. Local SQLite storage is used for the synthetic registry and is not a research result.

## Boundaries and next work

The current release deliberately excludes:

- live or public market-data ingestion;
- portfolio accounting, strategies and backtesting;
- financial performance claims or a completed research campaign;
- final evaluation and production trading;
- a dashboard and unattended Codex execution.

The next bounded engineering task is a deterministic, fixture-based portfolio core with normalized prices, portfolio accounting, rebalance scheduling, transaction costs, benchmark portfolios, accounting-identity tests and no-look-ahead tests. Public data selection and real strategy research remain later, separately authorized work.

