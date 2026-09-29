# Financial specification

## Research object

A transparent, long-only multi-asset index built from liquid public ETFs and rebalanced on a fixed schedule.

The first release studies strategic and rules-based allocation. It does not attempt single-security alpha or short-horizon trading.

## Candidate universe

Target size: approximately 50–80 ETFs, frozen in a versioned universe manifest.

Indicative sleeves:

1. US equity;
2. developed equity excluding the US;
3. emerging-market equity;
4. short-duration government bonds;
5. intermediate government bonds;
6. long-duration government bonds;
7. inflation-linked bonds;
8. investment-grade credit;
9. high-yield credit;
10. broad commodities;
11. gold;
12. real estate and listed infrastructure.

The final ticker list follows a data-availability and overlap diagnostic. Candidate strategy returns must not influence membership.

## Two-stage index construction

### Stage 1 — eligibility and representation

Within each sleeve, apply point-in-time observable rules where supported:

- minimum history;
- minimum recent price coverage;
- trailing liquidity proxy;
- no duplicate or near-duplicate share class;
- exposure and currency metadata;
- deterministic tie breaking.

The project must disclose that a fixed present-day candidate list does not remove survivorship bias.

### Stage 2 — sleeve allocation

Allocate capital or risk across sleeves using an approved StrategySpec. Sleeve representation and allocation are evaluated separately where possible.

## Initial benchmarks

- static 60/40 equity and government-bond portfolio;
- equal-weight or equal-sleeve multi-asset portfolio;
- static risk-parity portfolio;
- volatility-controlled 60/40;
- a volatility-matched version of the closest baseline to each candidate.

## Initial strategy primitives

Candidate primitives for the catalog, subject to implementation decisions:

- equal weight;
- inverse volatility;
- equal risk contribution;
- volatility targeting;
- time-series momentum or trend filter;
- cross-sleeve momentum tilt;
- covariance shrinkage;
- weight caps and floors;
- turnover-aware rebalance band;
- cash allocation when risk is scaled down.

A hypothesis may combine only primitives listed in its approval artifact.

## Portfolio constraints

Initial design constraints:

- long only;
- weights sum to one, including cash when present;
- minimum sleeve diversification;
- maximum ETF and sleeve weights;
- fixed rebalancing calendar;
- no future information in signals or eligibility;
- transaction costs charged on traded notional;
- deterministic handling of missing observations;
- no implicit leverage unless separately approved.

Exact numerical values are locked before candidate testing.

## Return conventions

The implementation must define and test:

- adjusted total-return price convention;
- signal observation date;
- trade or rebalance effective date;
- lag between observation and portfolio implementation;
- treatment of non-trading days;
- cash return convention;
- turnover convention;
- transaction cost timing.

## Claims discipline

- Compare lower-risk strategies with risk-matched controls.
- Report both total and excess-return metrics where a cash series is available.
- Do not infer economic skill from a small Sharpe difference without uncertainty estimates.
- Report rejected hypotheses and sensitivity failures.
