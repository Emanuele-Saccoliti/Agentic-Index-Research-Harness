# Project status

## Current phase

**P1 — Campaign Controller complete.**

Completed on 2026-09-29 after the owner approved the implementation plan and D014–D017 clarifications. No real research campaign was run.

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

Plan P2's deterministic fixture-based portfolio core. Read the finance/data specifications before proposing normalized price schemas, portfolio accounting, rebalance timing and transaction-cost interfaces. Define accounting-identity and no-look-ahead tests before implementation. Do not select public data, implement strategies, start a research campaign or activate the optional wrapper as part of that planning task.

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
