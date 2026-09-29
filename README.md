# Agentic Index Research Harness

A Codex-native research harness for designing and validating systematic multi-asset ETF index methodologies.

The project combines:

- **financial research**: ETF eligibility, sleeve construction, allocation, rebalancing and benchmark comparison;
- **agentic research**: a Coordinator delegates work to Researcher, Strategy Engineer, Falsifier and Auditor agents;
- **deterministic governance**: a Python Campaign Controller owns states, permissions, budgets, evidence and approvals;
- **responsible evaluation**: preregistration, trial accounting, walk-forward analysis, risk-matched controls and explicit negative outcomes.

## Research question

> Can a transparent, rules-based multi-asset ETF index achieve more robust out-of-sample performance than static and risk-matched benchmarks after costs, without excessive turnover, concentration or parameter instability?

## Operating model

The initial workflow is interactive and does not call an LLM API:

```text
Human
  -> Codex Coordinator
      -> Codex subagents
      -> Campaign Controller CLI
          -> deterministic data, backtest and validation engine
```

A future optional wrapper may launch non-interactive Codex sessions:

```text
Python wrapper -> Codex CLI (`codex exec`) -> repository -> Campaign Controller
```

The wrapper is intentionally deferred until the interactive protocol is stable. See [`docs/CODEX_CLI_WRAPPER.md`](docs/CODEX_CLI_WRAPPER.md).

## Start here

1. Read [`STATUS.md`](STATUS.md) and [`MEMORY.md`](MEMORY.md).
2. Use the source tree and tests as the executable project specification.

## P2: deterministic portfolio core

P2 is complete on synthetic fixtures. It provides validated adjusted total-return
prices, local CSV/Parquet I/O, explicit cash and holdings, next-session execution,
proportional transaction costs and fixed 60/40, equal-weight and equal-sleeve
benchmarks. The controller remains synthetic-only; this milestone introduces no
research campaign executor.

After installing the dependencies below, reproduce the acceptance case:

```bash
.venv/bin/python -m pytest -q tests/portfolio
.venv/bin/python scripts/verify_p2.py
```

The script checks hand-calculated NAV and turnover, compares complete CSV/Parquet
ledgers, and writes reproducible JSON ledgers to `output/p2/` (ignored by Git).
Inputs and independent expected values live in `tests/fixtures/p2_*`.
The full test suite also checks costs, cash accrual, conservation identities,
invalid input and future-price perturbations.

See [`docs/P2_PORTFOLIO_CORE.md`](docs/P2_PORTFOLIO_CORE.md) for the approved
financial conventions, file/API contracts and exact reproduction commands.
Risk-based benchmarks depend on later estimation primitives. No research cost
scenario, public provider, ETF universe or evaluation period is selected by P2.

## Core principle

> The Campaign Controller owns the research loop. Agents propose and execute bounded work; they cannot promote their own results.

## P1: local synthetic Campaign Controller

P1 implements typed artifacts, scope-bound approvals, policy decisions, an append-only SQLite registry and a minimal CLI. It contains no financial engine and rejects non-synthetic campaigns. Approval of the P1 engineering work does not authorize a research hypothesis.

### Install and verify

From the repository root, using Python 3.12:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.lock
.venv/bin/python -m pip install --no-build-isolation --no-deps -e .
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests scripts
.venv/bin/ruff format --check src tests scripts
.venv/bin/mypy src scripts
.venv/bin/etf-harness --help
```

The lock pins runtime, test and build dependencies. Disabling build isolation in the second installation step uses the already pinned build backend. The recorded environment was Python 3.12.0 on macOS arm64; other supported environments should run the same verification commands.

Run the complete synthetic acceptance lifecycle, with isolated temporary JSON files and SQLite storage:

```bash
.venv/bin/python -m pytest -q tests/test_cli.py::test_synthetic_cli_acceptance_lifecycle
```

This test covers creation, proposal, a pending human gate, synthetic approval, a separately approved administrative rejection and reopening the persisted state. Test decisions are explicitly fabricated fixtures, never actual human research approval.

### CLI inputs and commands

Commands consume UTF-8 JSON artifacts. The default registry is `.etf-harness/registry.sqlite3`, ignored by Git because it is synthetic local storage. Use `--registry PATH` before the command to select another location. P1 does not populate `research/campaigns/` or create a live campaign.

`campaign.json` must conform to `Campaign`; for example:

```json
{
  "id": "CAMP-DEMO", "campaign_id": "CAMP-DEMO",
  "created_at": "2026-09-29T00:00:00Z",
  "question": "Can the synthetic approval workflow complete?",
  "scope": "Controller demonstration only", "synthetic": true,
  "locked_config_digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "preregistration_digest": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "required_artifacts": ["synthetic closure decision"]
}
```

Those digests are synthetic placeholders. `hypothesis.json` can contain:

```json
{
  "id": "HYP-DEMO", "campaign_id": "CAMP-DEMO",
  "created_at": "2026-09-29T00:00:00Z",
  "statement": "Exercise bounded synthetic authorization",
  "mechanism": "No financial mechanism",
  "expected_benefit": "Verify policy behavior", "fair_benchmark": "Not applicable",
  "allowed_paths": [], "allowed_primitives": [],
  "parameters": {"example_parameter": {"minimum": 1, "maximum": 3}},
  "budget": {"candidate": 2, "robustness": 1},
  "failure_conditions": ["Unauthorized action succeeds"],
  "falsification_tests": ["Reject out-of-range parameters"]
}
```

After saving those two input files locally:

```bash
.venv/bin/etf-harness campaign create --file campaign.json
.venv/bin/etf-harness hypothesis propose --file hypothesis.json
.venv/bin/etf-harness campaign status CAMP-DEMO
```

The proposal command succeeds with a JSON `REQUIRE_APPROVAL` envelope containing the stored request and `request_digest`. The campaign is now `AWAITING_APPROVAL`. An operator reviews the request and supplies an approval artifact with these fields:

```json
{
  "id": "APR-DEMO", "campaign_id": "CAMP-DEMO",
  "created_at": "<actual human decision time in UTC, after the request>",
  "request_id": "<request.id from the command output>",
  "request_digest": "<request_digest from the command output>",
  "decision": "APPROVED", "authority": "human",
  "decided_by": "<human who explicitly authorized this exact request>",
  "source_reference": "<traceable reference to that authorization>",
  "synthetic": true
}
```

Replace the placeholders only after the human decision. Save it as `approval.json`, then import it:

```bash
.venv/bin/etf-harness hypothesis approve --file approval.json
.venv/bin/etf-harness campaign status CAMP-DEMO
.venv/bin/etf-harness campaign reject CAMP-DEMO --reason "End synthetic demonstration"
```

The last command emits a separate pending closure request and exits with code 2. Obtain a separate human decision using its request ID/digest and a new approval ID, save it as `closure.json`, then run:

```bash
.venv/bin/etf-harness campaign reject CAMP-DEMO --reason "End synthetic demonstration" --approval closure.json
.venv/bin/etf-harness campaign status CAMP-DEMO
```

`hypothesis approve` also imports a human `REJECTED` or `REVISION_REQUIRED` decision without closing the campaign. Artifact IDs are unique across the registry. Revisions use new IDs; previous records remain intact. Commands emit JSON; errors go to stderr. Exit codes: 0 for completed operations (including recording a proposal), 1 for denial/invalid input, 2 for an explicit action parked pending approval.

The authoritative schemas are Pydantic models in `etf_harness.schemas.domain`. To inspect an exact schema:

```bash
.venv/bin/python -c 'import json; from etf_harness.schemas.domain import Approval; print(json.dumps(Approval.model_json_schema(), indent=2))'
```

### Boundaries and next work

The controller has no Codex/LLM calls, generic state setter or financial execution command. It retains multiple proposals but advances one selected hypothesis per campaign in P1. Synthetic trial registration is a Python service seam tested at `APPROVED`; it does not imply later research stages have happened. Candidate and robustness reservations are conservative and never refunded for failed or abandoned registered attempts.

Human decision artifacts are trusted local attestations, not authenticated signatures. Provenance hashes are declared artifact references in P1. SQLite transactions, refusal triggers and hash-chain checks protect application history, but do not secure it against an owner rewriting the database/schema. See `docs/GOVERNANCE.md` for exact semantics.

The next bounded task is P3's public-data and universe diagnostic, starting with
provider/snapshot requirements and eligibility metadata. Provider choice, exact
ETF membership, date splits and research cost scenarios remain pending decisions.
Strategies, real campaigns, final evaluation and performance claims require their
separate approved workflows.
