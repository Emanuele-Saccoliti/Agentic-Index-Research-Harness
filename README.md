# Agentic-Index-Research-Harness

This repository implements an **agentic research harness for systematic multi-asset ETF index construction**, covering 50+ ETFs across equities, rates, credit, and commodities. The framework combines autonomous hypothesis generation with rule-based experiment execution and validation.

The research pipeline evaluates 10+ ETF allocation strategies against **60/40, equal-weight, and risk-parity benchmarks** using walk-forward backtesting with transaction costs, turnover constraints, and out-of-sample evaluation.

To keep agent-generated research reproducible and auditable, the harness implements **deterministic validation controls** using Pydantic schemas, including structured-output constraints, provenance tracking, hallucination checks, and experiment audit logs.

An automated **experiment registry** tracks 100+ research runs, recording hypotheses, parameter changes, rejected strategies, validation outcomes, and out-of-sample results. This provides a complete research trail and prevents the agent from silently modifying assumptions or discarding unsuccessful experiments.
