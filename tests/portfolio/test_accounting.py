from math import fsum

import pytest
from pydantic import ValidationError

from etf_harness.backtest.engine import run_portfolio
from etf_harness.backtest.models import Allocation, AssetWeight, ProportionalCost, RebalanceTarget
from etf_harness.backtest.schedule import fixed_targets
from etf_harness.benchmarks import equal_weight, sixty_forty
from etf_harness.data.models import CashReturn, PricePanel


@pytest.mark.parametrize("bps", [0.0, 10.0, 100.0, 9900.0])
@pytest.mark.parametrize("capital", [0.001, 1000.0, 1e12])
def test_accounting_identities_at_every_close(
    panel: PricePanel, cash_returns: tuple[CashReturn, ...], bps: float, capital: float
) -> None:
    targets = fixed_targets(panel.calendar, sixty_forty("EQUITY", "BOND"), frequency="monthly")
    result = run_portfolio(
        panel,
        targets,
        cash_returns=cash_returns,
        costs=ProportionalCost(basis_points=bps),
        initial_nav=capital,
    )
    previous = None
    for row in result.ledger:
        assert row.nav == pytest.approx(
            row.cash + fsum(item.market_value for item in row.holdings), rel=1e-12
        )
        assert row.nav == pytest.approx(row.nav_before_trade - row.fee, rel=1e-11)
        assert row.cash_weight + fsum(item.weight for item in row.holdings) == pytest.approx(1)
        assert row.cash >= 0
        assert all(item.units >= 0 for item in row.holdings)
        assert row.fee == pytest.approx(bps / 10000 * fsum(abs(t.notional) for t in row.trades))
        assert row.cash == pytest.approx(
            row.cash_before_trade - fsum(t.notional for t in row.trades) - row.fee,
            abs=capital * 1e-12,
        )
        assert row.half_turnover == row.gross_turnover / 2
        if previous is not None:
            assert row.nav - previous.nav == pytest.approx(
                row.asset_pnl + row.cash_pnl - row.fee, abs=capital * 1e-11
            )
            for old, new in zip(previous.holdings, row.holdings, strict=True):
                trade_units = next((t.units for t in row.trades if t.asset == old.asset), 0.0)
                assert new.units == pytest.approx(old.units + trade_units, abs=capital * 1e-12)
        if row.observation is not None:
            weights = {item.asset: item.weight for item in row.holdings}
            assert weights == pytest.approx({"EQUITY": 0.6, "BOND": 0.4})
        previous = row


def test_initial_cost_is_financed_and_charged_on_actual_notional(
    panel: PricePanel, cash_returns: tuple[CashReturn, ...]
) -> None:
    targets = fixed_targets(panel.calendar, sixty_forty("EQUITY", "BOND"), frequency="buy_and_hold")
    result = run_portfolio(
        panel,
        targets,
        cash_returns=cash_returns,
        costs=ProportionalCost(basis_points=100.0),
        initial_nav=1000.0,
    )
    initial = result.ledger[1]
    assert initial.nav == pytest.approx(1000 / 1.01)
    assert initial.fee == pytest.approx(1000 / 101)
    assert initial.gross_turnover == pytest.approx(1 / 1.01)
    assert initial.net_return == pytest.approx(1 / 1.01 - 1)
    assert initial.cash == pytest.approx(0, abs=1e-10)
    assert not result.ledger[-1].trades  # No implicit terminal liquidation.


def test_buy_sell_rebalance_matches_analytic_cost_solution(
    panel: PricePanel, cash_returns: tuple[CashReturn, ...]
) -> None:
    targets = fixed_targets(panel.calendar, sixty_forty("EQUITY", "BOND"), frequency="monthly")
    result = run_portfolio(
        panel,
        targets,
        cash_returns=cash_returns,
        costs=ProportionalCost(basis_points=100.0),
        initial_nav=1000.0,
    )
    # At Feb 1 equity is sold and bonds are bought. The signed trade regions
    # give X * (1 - .002) = V - .01 * (equity_value - bond_value).
    equity, bond = 726 / 1.01, 400 / 1.01
    net_nav = (equity + bond - 0.01 * (equity - bond)) / 0.998
    rebalance = result.ledger[3]
    assert rebalance.nav == pytest.approx(net_nav, rel=1e-12)
    assert rebalance.fee == pytest.approx(equity + bond - net_nav, rel=1e-11)
    assert {trade.asset: trade.notional for trade in rebalance.trades} == pytest.approx(
        {"EQUITY": 0.6 * net_nav - equity, "BOND": 0.4 * net_nav - bond}
    )


def test_cash_accrual_and_liquidation_have_independent_closed_form(panel: PricePanel) -> None:
    closes = panel.calendar.closes
    rates = tuple(CashReturn(observed_at=close, simple_return=0.01) for close in closes[1:])
    half_cash = Allocation(assets=(AssetWeight(asset="EQUITY", weight=0.5),), cash_weight=0.5)
    targets = (
        RebalanceTarget(observed_at=closes[0], execute_at=closes[1], allocation=half_cash),
        RebalanceTarget(
            observed_at=closes[1],
            execute_at=closes[2],
            allocation=Allocation(assets=(), cash_weight=1.0),
        ),
    )
    result = run_portfolio(
        panel,
        targets,
        cash_returns=rates,
        costs=ProportionalCost(basis_points=100.0),
        initial_nav=1000.0,
    )
    invested_nav = 1010 / 1.005
    first = result.ledger[1]
    assert first.nav == pytest.approx(invested_nav)
    assert first.cash == pytest.approx(invested_nav / 2)
    second = result.ledger[2]
    equity_value = invested_nav / 2 * 1.1
    expected_cash = invested_nav / 2 * 1.01 + equity_value * 0.99
    assert second.nav == pytest.approx(expected_cash)
    assert second.cash == pytest.approx(expected_cash)
    assert second.fee == pytest.approx(equity_value * 0.01)
    assert second.gross_traded_notional == pytest.approx(equity_value)
    assert result.ledger[-1].nav == pytest.approx(expected_cash * 1.01**3)


def test_buy_and_hold_drifts_instead_of_silently_rebalancing(
    panel: PricePanel, cash_returns: tuple[CashReturn, ...]
) -> None:
    targets = fixed_targets(panel.calendar, sixty_forty("EQUITY", "BOND"), frequency="buy_and_hold")
    result = run_portfolio(
        panel,
        targets,
        cash_returns=cash_returns,
        costs=ProportionalCost(basis_points=0.0),
        initial_nav=1000.0,
    )
    assert result.ledger[-1].nav == pytest.approx(600 * 1.452 + 400 * 1.1)
    assert result.total_gross_turnover == pytest.approx(1)
    assert {h.asset: h.units for h in result.ledger[-1].holdings} == pytest.approx(
        {"EQUITY": 6, "BOND": 4}
    )
    assert {h.asset: h.weight for h in result.ledger[2].holdings}["EQUITY"] != 0.6


def test_all_cash_no_target_and_negative_cash_rate(panel: PricePanel) -> None:
    rates = tuple(
        CashReturn(observed_at=close, simple_return=-0.01) for close in panel.calendar.closes[1:]
    )
    result = run_portfolio(
        panel, (), cash_returns=rates, costs=ProportionalCost(basis_points=20.0), initial_nav=1000.0
    )
    assert result.ledger[-1].nav == pytest.approx(1000 * 0.99**5)
    assert result.total_gross_turnover == 0
    assert result.total_fees == 0


@pytest.mark.parametrize("weight", [-0.1, 1.1, float("inf"), float("nan"), True])
def test_invalid_weight(weight: float) -> None:
    with pytest.raises(ValidationError):
        AssetWeight(asset="EQUITY", weight=weight)


@pytest.mark.parametrize("cash", [0.0, 0.3, 0.6])
def test_weight_sum_rejected(cash: float) -> None:
    with pytest.raises(ValidationError, match="sum to one"):
        Allocation(assets=(AssetWeight(asset="EQUITY", weight=0.5),), cash_weight=cash)


@pytest.mark.parametrize("bps", [-1.0, 10000.0, float("nan"), float("inf"), True])
def test_invalid_cost(bps: float) -> None:
    with pytest.raises(ValidationError):
        ProportionalCost(basis_points=bps)


@pytest.mark.parametrize("capital", [0.0, -1.0, float("nan"), float("inf"), True])
def test_invalid_capital(
    panel: PricePanel, cash_returns: tuple[CashReturn, ...], capital: float
) -> None:
    with pytest.raises(ValueError, match="Initial NAV"):
        run_portfolio(
            panel,
            (),
            cash_returns=cash_returns,
            costs=ProportionalCost(basis_points=0.0),
            initial_nav=capital,
        )


@pytest.mark.parametrize("defect", ["missing", "duplicate", "reordered", "extra"])
def test_cash_alignment_rejected(
    panel: PricePanel, cash_returns: tuple[CashReturn, ...], defect: str
) -> None:
    rates = {
        "missing": cash_returns[:-1],
        "duplicate": cash_returns + cash_returns[:1],
        "reordered": tuple(reversed(cash_returns)),
        "extra": (CashReturn(observed_at=panel.calendar.closes[0], simple_return=0.0),)
        + cash_returns,
    }[defect]
    with pytest.raises(ValueError, match="Cash returns"):
        run_portfolio(
            panel,
            (),
            cash_returns=rates,
            costs=ProportionalCost(basis_points=0.0),
            initial_nav=1000.0,
        )


def test_unknown_asset_and_duplicate_target_fail(
    panel: PricePanel, cash_returns: tuple[CashReturn, ...]
) -> None:
    for assets, defect in [(("UNKNOWN",), "outside"), (panel.assets, "Duplicate")]:
        targets = fixed_targets(panel.calendar, equal_weight(assets), frequency="buy_and_hold")
        if defect == "Duplicate":
            targets += targets
        with pytest.raises(ValueError, match=defect):
            run_portfolio(
                panel,
                targets,
                cash_returns=cash_returns,
                costs=ProportionalCost(basis_points=0.0),
                initial_nav=1000.0,
            )
