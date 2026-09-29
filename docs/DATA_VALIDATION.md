# Data and validation policy

## Data design

Implement a provider interface rather than coupling research logic to one vendor.

Initial adapters:

- public market-data downloader for daily ETF prices and volume;
- local CSV or Parquet provider for frozen snapshots and tests;
- optional public cash-rate provider.

A likely first downloader is `yfinance`, but the provider choice remains pending until an availability diagnostic is completed. Research code consumes normalized data only.

## Data manifest

Each snapshot records:

- provider and retrieval timestamp;
- ticker and sleeve metadata;
- requested and actual date ranges;
- price convention;
- missing-data summary;
- transformation version;
- file digest;
- known limitations.

Do not commit licensed or redistributable data without checking its terms. The repository may commit manifests and deterministic download instructions while keeping local caches ignored.

## Temporal controls

- Signals use information available no later than the observation timestamp.
- Portfolio implementation occurs after a documented lag.
- Eligibility uses trailing information only.
- Rolling estimators are shifted before portfolio application.
- Missing future observations must not backfill past eligibility.

## Period design

The exact dates are chosen after inspecting availability and fixed benchmark behavior, before candidate-strategy evaluation.

The intended structure is:

1. development data for methodology design;
2. internal walk-forward folds for parameter selection and stability;
3. a frozen final evaluation period;
4. future forward observations after the final period is spent.

## Required benchmarks

- 60/40;
- equal sleeve;
- static risk parity;
- volatility-controlled 60/40;
- nearest risk-matched control.

## Core metrics

- cumulative and annualized return;
- annualized volatility;
- Sharpe and Sortino on documented return conventions;
- maximum drawdown and recovery time;
- Calmar ratio;
- turnover and cost drag;
- average and maximum concentration;
- sleeve risk contributions;
- tracking and exposure diagnostics.

## Mandatory robustness tests

- walk-forward consistency;
- parameter-neighborhood perturbation;
- rebalance-date or phase perturbation;
- higher-cost scenarios;
- subperiod and stress-period analysis;
- ETF substitution or sleeve-representation sensitivity;
- circular or stationary block bootstrap for paired portfolio-return differences;
- concentration and turnover gates;
- accounting and no-look-ahead checks.

## Multiple testing

Maintain a complete trial count. When many comparisons are reported:

- adjust interpretation for selection;
- report confidence intervals rather than only point estimates;
- use a multiple-comparison procedure where appropriate;
- treat deflated Sharpe or similar selection statistics as supporting diagnostics, not automatic acceptance rules.

## Gate design

Use multiple independent gates. Do not combine every outcome into a single opaque score.

Numerical thresholds are locked before candidate testing. Threshold selection may use economic rationale, implementation feasibility and fixed benchmark diagnostics, but not candidate performance.

## Known limitations to disclose

- fixed public ETF lists can contain survivorship bias;
- adjusted histories may be revised by providers;
- historical AUM and precise index tracking data may be unavailable;
- public liquidity proxies do not reconstruct every historical execution condition;
- an in-repository holdout is governed procedurally rather than hidden cryptographically.
