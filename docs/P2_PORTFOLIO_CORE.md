# P2 deterministic portfolio core

## Scope and acceptance plan

Implement local normalized CSV/Parquet input, a pure accounting engine, fixed
session-based schedules and fixed-weight benchmarks. This is synthetic engineering
validation, not a registered research experiment or a campaign executor.

Baseline constructors cover 60/40, equal asset weights and equal sleeve weights
(equal weights within each supplied sleeve). Risk-parity and volatility-controlled
benchmarks depend on the estimation primitives in P4 and research validation in P5;
P2 does not estimate risk or select a universe.

Before implementation, the acceptance checks are:

1. Hand-calculated fixture NAV, returns and turnover for 60/40 and equal weight.
2. Identical results from CSV and Parquet and from permuted input rows.
3. NAV equals marked positions plus cash; NAV change equals asset PnL plus cash
   accrual minus fees; cash movement equals negative signed trades minus fees.
4. Actual gross traded notional determines fees, including the initial purchase;
   post-fee target weights sum to one with no borrowing.
5. Decisions at t execute at the next supplied session close; old holdings earn
   the return up to that close. Perturbing future prices cannot alter earlier
   results. No forced liquidation at the last observation.
6. Reject duplicate, missing, nonfinite, nonpositive or mixed-currency prices,
   invalid weights, unaligned cash returns and same-close execution.
7. Month/quarter boundaries follow the supplied calendar, including weekends,
   holidays and a partial terminal month, without guessing an exchange calendar.
8. Existing P1 tests, formatting, lint and strict type checks still pass.

## Approved financial conventions

The owner explicitly approved the following in this chat on 2026-09-30 (D018):

- Adjusted total-return prices; dividends/splits are already represented in the
  series and are not credited again. Positions are synthetic adjusted-price units,
  not executable ETF share counts. All series use one explicit base currency.
- Observation at close t, execution at the next session close. New holdings earn
  returns only after execution. The initial portfolio is cash at the first close;
  the first order is observed there and executed at the next close.
- A supplied sequence of timezone-aware UTC session closes is authoritative.
  Missing observations fail; there is no forward-fill, backfill or inferred holiday.
- Cash simple returns are explicit for every close after the first. Each applies
  over the entire interval since the preceding close, including intervening
  non-trading days. Fixture cash returns are zero unless a test says otherwise.
- Gross turnover is ETF purchases plus sales divided by pre-trade NAV, excluding
  cash. Half-turnover is also reported. This includes initial investment.
- Proportional costs apply to actual ETF traded notional at execution, including
  initial investment. A test's basis-point input is not an approved research cost
  scenario. No additional dividends, FX conversion, interest day count, slippage,
  tax, settlement lag or market impact is inferred.
- Long only; asset and explicit cash target weights sum to one; no leverage.

## Numerical design

Use immutable, validated Pydantic inputs and result records. Pandas and PyArrow
exist only at the local file boundary; the accounting engine consumes normalized
records. Canonical asset ordering makes results independent of CSV row order.

For marked asset values v, pre-trade NAV V, ETF target weights w and cost rate c,
solve for post-fee NAV X:

```text
X + c * sum(abs(w_i * X - v_i)) = V
trade_i = w_i * X - v_i
fee = c * sum(abs(trade_i))
cash_after = cash_before - sum(trade_i) - fee
```

For 0 <= c < 1 and long-only unlevered targets, the equation is strictly increasing
and has a unique positive root. A bounded deterministic bisection avoids estimating
fees on weights and then borrowing to pay them. Numerical tolerances are internal
accounting tolerances, not research acceptance gates.

The engine records pre/post-trade NAV, PnL, cash accrual, signed trades, fees,
turnover, holdings and weights for every session. It reports net interval returns,
including fees on their execution date; no fictitious return precedes the initial
close. Costs and cash returns are mandatory inputs, with no research defaults.

## Boundaries

The engine enforces timestamps and accounting, not the provenance of externally
constructed weights or point-in-time adjusted-price revisions. P3 must supply
snapshot manifests; P4/P5 must enforce trailing estimation and approved strategy
construction. No real-data provider, risk estimates, performance statistics,
campaign transitions or final-evaluation workflow are introduced here.

## File and API contracts

CSV/Parquet files have exactly these columns:

| Column | Meaning |
|---|---|
| `observed_at` | Timezone-aware UTC session close; ISO 8601 for CSV. |
| `asset` | Unique declared asset identifier, preserved without guessing tickers. |
| `adjusted_close` | Finite, strictly positive total-return price in adjusted units. |
| `currency` | One explicit three-letter uppercase currency throughout the panel. |
| `price_convention` | Literal `adjusted_total_return`. |

The caller separately supplies `SessionCalendar`, assets and currency to
`LocalPriceProvider.load`. Every session/asset pair must occur exactly once;
unexpected rows/columns are rejected. Rows are canonically sorted. CSV and Parquet
use the same validator. Input filenames are local `Path` objects.

`run_portfolio(panel, targets, cash_returns=..., costs=..., initial_nav=...)` is
the pure accounting entry point. Cash returns must cover every interval in order.
Targets specify `observed_at`, `execute_at` and an `Allocation` containing asset
weights and explicit `cash_weight`; omitted assets have zero target weight.
Duplicate executions, unknown assets and any lag other than one supplied session
fail before calculation. Immutable result records serialize with `model_dump_json`.

`fixed_targets` supports buy-and-hold, every-session, monthly and calendar-quarterly
schedules. Each starts with an observation at the first close. Subsequent monthly
or quarterly observations occur at the last supplied close of the period, with
execution at the next close. Calendar dates here are fixture inputs, not approved
research evaluation dates.

## Reproduce and inspect

From the project root, after the README installation commands:

```bash
.venv/bin/python -m pytest -q tests/portfolio
.venv/bin/python scripts/verify_p2.py
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests scripts
.venv/bin/ruff format --check src tests scripts
.venv/bin/mypy src scripts
.venv/bin/python -m pip check
```

Versioned inputs are `tests/fixtures/p2_case.json`, `p2_prices.csv` and
`p2_expected.json`. Generated files are `output/p2/prices.parquet` and the three
benchmark JSON ledgers in that directory; all are reproducible and ignored by Git.
The expected file was calculated independently: after initial investment at 100,
the monthly 60/40 holds 6 equity units and 4 bond units until Feb 1. Its pre-trade
values are 726 and 400, then 675.6 and 450.4 after a zero-cost rebalance. Therefore
gross traded notional is 100.8. Equal weight follows the same calculation from
5 units of each asset, producing 105 of gross traded notional. These are synthetic
accounting checks, not evidence of investment performance.

Acceptance passed on 2026-09-30: **222 tests** across P1 and P2, including **104 P2
tests**; the fixture reproduction script, Ruff lint/format, strict mypy and the
Quant Coding static audit passed. Tests include initial investment and mixed
buy/sell costs checked against closed-form solutions, full liquidation, positive
and negative cash accrual, scales from 0.001 to 1e12, future-price perturbations,
calendar boundaries and malformed CSV/Parquet inputs.
