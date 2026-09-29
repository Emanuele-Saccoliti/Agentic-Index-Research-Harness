import json
from pathlib import Path

import pytest

from etf_harness.backtest.engine import run_portfolio
from etf_harness.backtest.models import ProportionalCost
from etf_harness.backtest.schedule import fixed_targets
from etf_harness.benchmarks import equal_sleeve, equal_weight, sixty_forty
from etf_harness.data.models import CashReturn, PricePanel
from etf_harness.data.providers import LocalPriceProvider, write_prices


@pytest.mark.parametrize("baseline", ["sixty_forty", "equal_weight", "equal_sleeve"])
@pytest.mark.parametrize("extension", [".csv", ".parquet"])
def test_hand_calculated_benchmark_acceptance(
    panel: PricePanel,
    cash_returns: tuple[CashReturn, ...],
    tmp_path: Path,
    baseline: str,
    extension: str,
) -> None:
    path = tmp_path / f"prices{extension}"
    write_prices(panel, path)
    loaded = LocalPriceProvider(path).load(
        calendar=panel.calendar, assets=panel.assets, currency="USD"
    )
    assert loaded == panel
    allocation = (
        sixty_forty("EQUITY", "BOND") if baseline == "sixty_forty" else equal_weight(panel.assets)
    )
    if baseline == "equal_sleeve":
        allocation = equal_sleeve({"equity": ("EQUITY",), "bonds": ("BOND",)})
    targets = fixed_targets(loaded.calendar, allocation, frequency="monthly")
    result = run_portfolio(
        loaded,
        targets,
        cash_returns=cash_returns,
        costs=ProportionalCost(basis_points=0.0),
        initial_nav=1000.0,
    )
    expected = json.loads(
        (Path(__file__).parents[1] / "fixtures" / "p2_expected.json").read_text()
    )["equal_weight" if baseline == "equal_sleeve" else baseline]
    navs = expected["nav"]
    notionals = expected["gross_traded_notional"]
    assert [row.nav for row in result.ledger] == pytest.approx(navs, rel=1e-12)
    assert [row.gross_traded_notional for row in result.ledger] == pytest.approx(
        notionals, abs=1e-10
    )
    assert [row.gross_turnover for row in result.ledger] == pytest.approx(
        [n / v for n, v in zip(notionals, navs, strict=False)]
    )
    assert result.ledger[0].net_return is None
    assert [row.net_return for row in result.ledger[1:]] == pytest.approx(
        [b / a - 1 for a, b in zip(navs, navs[1:], strict=False)]
    )
    assert result.total_gross_turnover == pytest.approx(
        sum(n / v for n, v in zip(notionals, navs, strict=False))
    )
    assert result.total_fees == 0
    # Full ledger and canonical serialization, not just terminal NAV, reproduce.
    replay = run_portfolio(
        panel,
        targets,
        cash_returns=cash_returns,
        costs=ProportionalCost(basis_points=0.0),
        initial_nav=1000.0,
    )
    assert result.model_dump_json() == replay.model_dump_json()
