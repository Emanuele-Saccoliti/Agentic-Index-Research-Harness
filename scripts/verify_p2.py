"""Reproduce the checked-in synthetic acceptance case and export its full ledgers."""

import json
from math import isclose
from pathlib import Path

from etf_harness.backtest.engine import run_portfolio
from etf_harness.backtest.models import Allocation, PortfolioResult, ProportionalCost
from etf_harness.backtest.schedule import fixed_targets
from etf_harness.benchmarks import equal_sleeve, equal_weight, sixty_forty
from etf_harness.data.models import CashReturn, PricePanel, SessionCalendar
from etf_harness.data.providers import LocalPriceProvider, write_prices

PROJECT = Path(__file__).resolve().parents[1]
FIXTURES = PROJECT / "tests" / "fixtures"
OUTPUT = PROJECT / "output" / "p2"


def verify(result: PortfolioResult, navs: list[float], notionals: list[float]) -> None:
    for row, nav, notional in zip(result.ledger, navs, notionals, strict=True):
        checks = (
            isclose(row.nav, nav, rel_tol=1e-12),
            isclose(row.gross_traded_notional, notional, rel_tol=1e-12, abs_tol=1e-10),
            isclose(row.gross_turnover, notional / nav, rel_tol=1e-12, abs_tol=1e-12),
        )
        if not all(checks):
            raise AssertionError(f"Synthetic benchmark mismatch at {row.close}")


def write_verified_ledger(
    name: str,
    panel: PricePanel,
    parquet: PricePanel,
    allocation: Allocation,
    navs: list[float],
    notionals: list[float],
) -> None:
    cash = tuple(
        CashReturn(observed_at=close, simple_return=0.0) for close in panel.calendar.closes[1:]
    )
    targets = fixed_targets(panel.calendar, allocation, frequency="monthly")
    result = run_portfolio(
        panel,
        targets,
        cash_returns=cash,
        costs=ProportionalCost(basis_points=0.0),
        initial_nav=1000.0,
    )
    verify(result, navs, notionals)
    replay = run_portfolio(
        parquet,
        targets,
        cash_returns=cash,
        costs=ProportionalCost(basis_points=0.0),
        initial_nav=1000.0,
    )
    if result != replay:
        raise AssertionError("CSV and Parquet ledgers differ")
    (OUTPUT / f"{name}.json").write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    case = json.loads((FIXTURES / "p2_case.json").read_text(encoding="utf-8"))
    calendar = SessionCalendar.model_validate(case["calendar"])
    panel = LocalPriceProvider(FIXTURES / "p2_prices.csv").load(
        calendar=calendar, assets=tuple(case["assets"]), currency=case["currency"]
    )
    expected = json.loads((FIXTURES / "p2_expected.json").read_text(encoding="utf-8"))
    write_prices(panel, OUTPUT / "prices.parquet")
    parquet = LocalPriceProvider(OUTPUT / "prices.parquet").load(
        calendar=calendar, assets=panel.assets, currency=panel.currency
    )
    if parquet != panel:
        raise AssertionError("CSV and Parquet normalized records differ")
    baselines = {
        "sixty_forty": sixty_forty("EQUITY", "BOND"),
        "equal_weight": equal_weight(panel.assets),
        "equal_sleeve": equal_sleeve({"equity": ("EQUITY",), "bonds": ("BOND",)}),
    }
    for name, allocation in baselines.items():
        reference = expected["equal_weight" if name == "equal_sleeve" else name]
        write_verified_ledger(
            name, panel, parquet, allocation, reference["nav"], reference["gross_traded_notional"]
        )
    print(
        f"PASS: 3 synthetic baselines match hand calculations and Parquet replay. Ledgers: {OUTPUT}"
    )


if __name__ == "__main__":
    main()
