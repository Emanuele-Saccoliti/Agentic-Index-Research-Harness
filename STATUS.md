# Project status

## Current phase

**P2 — Deterministic portfolio core complete.**

Completed on 2026-09-30 after the owner authorized P2 and approved financial
conventions D018 in this chat. No real research campaign was run.

## P2 delivery and acceptance

- Validated, immutable adjusted total-return price records and explicit UTC sessions;
- local CSV/Parquet provider with exact calendar/asset alignment and no imputation;
- long-only accounting with holdings, cash accrual, PnL and per-session ledgers;
- next-session execution and buy-and-hold, daily-session, monthly, quarterly schedules;
- self-financing proportional costs on actual traded notional, including initial investment;
- fixed 60/40, equal-weight and equal-sleeve baselines;
- independent fixture expectations, accounting identities and no-look-ahead tests.

Validation: **222 tests passed (118 P1 + 104 P2)**; the standalone fixture
reproduction, Ruff lint/format, strict mypy and Quant Coding audit passed.
The complete ledgers reproduce from CSV and Parquet. See
[`docs/P2_PORTFOLIO_CORE.md`](docs/P2_PORTFOLIO_CORE.md) for acceptance evidence and
[`MEMORY.md`](MEMORY.md) for the session record.

```bash
.venv/bin/python -m pytest -q tests/portfolio
.venv/bin/python scripts/verify_p2.py
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests scripts
.venv/bin/ruff format --check src tests scripts
.venv/bin/mypy src scripts
.venv/bin/python -m pip check
```

P2 is a library/fixture slice. The controller remains synthetic-only and has no
financial executor. Risk-parity and volatility-controlled benchmarks still need
P4 estimation primitives. Public data, point-in-time provenance, universe
eligibility and research execution are later milestones.

## P1 completion record

Completed on 2026-09-29 after the owner approved D014–D017. Historical P1 evidence follows.

## Delivered

- Python 3.12 package with Pydantic Campaign, Hypothesis, Approval, Experiment and EvidenceRecord models;
- explicit campaign state graph and deterministic action policy;
- exact scope-bound local human decision import;
- SQLite append-only event/trial/evidence registry with atomic reservations, revision checks and replay;
- Typer commands: `campaign create`, `hypothesis propose`, `hypothesis approve`, `campaign status`, `campaign reject`;
- conservative candidate/robustness budget accounting and append-only outcomes/corrections;
- documented installation, input artifacts, operating limits and approved decisions.

## Acceptance evidence

The synthetic CLI integration test creates a campaign, records a proposal, parks it at `AWAITING_APPROVAL`, imports a synthetic approval, obtains a separate synthetic administrative-closure approval, reaches `REJECTED`, and reproduces the same status after reopening storage. This establishes the P1 exit criterion without financial code.

Verified in the project virtual environment (Python 3.12.0, macOS arm64):

```bash
.venv/bin/python -m pytest -q                 # 118 passed
.venv/bin/ruff check src tests                # all checks passed
.venv/bin/ruff format --check src tests       # 24 files already formatted
.venv/bin/mypy src                           # no issues in 16 source files
.venv/bin/python -m pip check                # no broken requirements
.venv/bin/python -m pip install --no-build-isolation --no-deps -e .
.venv/bin/etf-harness campaign --help
```

Tests include illegal transitions, terminal immutability, missing/mismatched approval, parameter bounds, budget overflow, failed/abandoned reservations, concurrent competition for the last slot, transaction rollback, SQL update/delete/replacement refusal, malformed history, corrections, replay and the end-to-end CLI lifecycle. A bounded read-only Auditor review found no remaining actionable defects after fixes and regression coverage.

## Known P1 limits

- Synthetic-only controller; no live campaign or financial executor.
- Multiple proposals are retained, but one selected hypothesis advances per campaign.
- Local approvals are trusted attestations, not authenticated signatures.
- Provenance fields are declared digests; automatic source/task provenance capture and financial artifact verification are later work.
- Append-only enforcement and hash chains do not protect against the filesystem owner rewriting the database/schema or truncating its final suffix without an external checkpoint.
- Registration reserves budget conservatively, including attempts later abandoned before execution.

## Next bounded task

P3: design and run a public-data availability diagnostic, then implement the
provider adapter, snapshot/cache manifest, ETF metadata, sleeve taxonomy and
eligibility rules. Resolve provider/snapshot policy and exact universe membership
using data availability and fixed benchmarks, never candidate results. Preserve
D018; ask the owner before changing financial conventions or freezing protected
research choices. P3 has not started in this session.

## Not yet authorized

- Running a research campaign;
- selecting a data period using candidate results;
- executing a final evaluation;
- publishing performance numbers;
- building the Streamlit dashboard;
- implementing the Codex CLI wrapper.

## Open items to resolve during implementation

- exact public market-data provider;
- exact ETF list after a data-availability diagnostic;
- calendar dates for development, validation and final evaluation;
- numerical validation thresholds, set from financial rationale and benchmark diagnostics before candidate testing.
