"""Self-financing long-only accounting on synthetic adjusted-price units."""

from dataclasses import dataclass
from datetime import datetime
from math import fsum, isclose, isfinite

from etf_harness.backtest.models import (
    Allocation,
    Holding,
    LedgerEntry,
    PortfolioResult,
    ProportionalCost,
    RebalanceTarget,
    Trade,
)
from etf_harness.data.models import CashReturn, PricePanel


@dataclass(frozen=True)
class Execution:
    units: dict[str, float]
    cash: float
    fee: float
    gross_notional: float
    trades: tuple[Trade, ...]


@dataclass(frozen=True)
class _PositionState:
    units: dict[str, float]
    prices: dict[str, float]
    cash: float
    nav: float | None


def _nonnegative(value: float, scale: float) -> float:
    if not isfinite(value) or value < -1e-12 * scale:
        raise ArithmeticError("Nonfinite value or material short position/cash borrowing")
    return max(0.0, value)


def _post_fee_nav(
    nav: float, values: dict[str, float], weights: dict[str, float], rate: float
) -> float:
    if rate == 0:
        return nav
    # Solve in NAV units so convergence is independent of portfolio scale.
    fractions = {asset: value / nav for asset, value in values.items()}
    low, high = 0.0, 1.0
    for _ in range(80):
        fraction = (low + high) / 2
        traded = fsum(abs(weights[asset] * fraction - value) for asset, value in fractions.items())
        if fraction + rate * traded > 1:
            high = fraction
        else:
            low = fraction
    return nav * ((low + high) / 2)


def _execute(
    *,
    prices: dict[str, float],
    units: dict[str, float],
    cash: float,
    nav: float,
    allocation: Allocation,
    costs: ProportionalCost,
) -> Execution:
    values = {asset: units[asset] * price for asset, price in prices.items()}
    weights = dict.fromkeys(prices, 0.0)
    weights.update({item.asset: item.weight for item in allocation.assets})
    net_nav = _post_fee_nav(nav, values, weights, costs.rate)
    new_units = {asset: weights[asset] * net_nav / price for asset, price in prices.items()}
    trades = tuple(
        Trade(
            asset=asset,
            units=new_units[asset] - units[asset],
            notional=(new_units[asset] - units[asset]) * price,
        )
        for asset, price in prices.items()
        if new_units[asset] != units[asset]
    )
    gross_notional = fsum(abs(trade.notional) for trade in trades)
    fee = costs.rate * gross_notional
    cash_after = _nonnegative(fsum([cash, -fee, *(-trade.notional for trade in trades)]), nav)
    if not isclose(
        cash_after, allocation.cash_weight * net_nav, rel_tol=1e-10, abs_tol=1e-12 * nav
    ):
        raise ArithmeticError("Self-financing cash does not match target cash")
    return Execution(new_units, cash_after, fee, gross_notional, trades)


def _validate_inputs(
    panel: PricePanel,
    targets: tuple[RebalanceTarget, ...],
    cash_returns: tuple[CashReturn, ...],
    initial_nav: float,
) -> None:
    if isinstance(initial_nav, bool) or not isfinite(initial_nav) or initial_nav <= 0:
        raise ValueError("Initial NAV must be finite and positive")
    if tuple(row.observed_at for row in cash_returns) != panel.calendar.closes[1:]:
        raise ValueError(
            "Cash returns must exactly align with every interval after the first close"
        )
    executions: set[datetime] = set()
    next_close = dict(zip(panel.calendar.closes, panel.calendar.closes[1:], strict=False))
    for target in targets:
        if next_close.get(target.observed_at) != target.execute_at:
            raise ValueError("Every target must execute at the next declared session close")
        if target.execute_at in executions:
            raise ValueError("Duplicate rebalance execution")
        executions.add(target.execute_at)
        if not {item.asset for item in target.allocation.assets} <= set(panel.assets):
            raise ValueError("Target contains an asset outside the declared panel")


def _holdings(prices: dict[str, float], execution: Execution, nav: float) -> tuple[Holding, ...]:
    return tuple(
        Holding(
            asset=asset,
            units=execution.units[asset],
            adjusted_close=price,
            market_value=execution.units[asset] * price,
            weight=min(1.0, execution.units[asset] * price / nav),
        )
        for asset, price in prices.items()
    )


def _ledger_entry(
    *,
    close: datetime,
    observation: datetime | None,
    prices: dict[str, float],
    execution: Execution,
    nav_before: float,
    cash_before: float,
    asset_pnl: float,
    cash_pnl: float,
    previous_nav: float | None,
) -> LedgerEntry:
    values = {asset: execution.units[asset] * price for asset, price in prices.items()}
    nav = fsum([execution.cash, *values.values()])
    if not isfinite(nav) or nav <= 0:
        raise ArithmeticError("Portfolio NAV must remain finite and positive")
    if not isclose(nav, nav_before - execution.fee, rel_tol=1e-11, abs_tol=0):
        raise ArithmeticError("Portfolio conservation identity failed")
    return LedgerEntry(
        close=close,
        observation=observation,
        nav_before_trade=nav_before,
        nav=nav,
        cash_before_trade=cash_before,
        cash=execution.cash,
        cash_weight=min(1.0, execution.cash / nav),
        asset_pnl=asset_pnl,
        cash_pnl=cash_pnl,
        fee=execution.fee,
        gross_traded_notional=execution.gross_notional,
        gross_turnover=execution.gross_notional / nav_before,
        half_turnover=execution.gross_notional / nav_before / 2,
        net_return=None if previous_nav is None else nav / previous_nav - 1,
        holdings=_holdings(prices, execution, nav),
        trades=execution.trades,
    )


def _advance(
    state: _PositionState,
    close: datetime,
    prices: dict[str, float],
    cash_return: float,
    target: RebalanceTarget | None,
    costs: ProportionalCost,
) -> LedgerEntry:
    cash_pnl = state.cash * cash_return
    cash = _nonnegative(state.cash + cash_pnl, state.cash)
    asset_pnl = fsum(
        state.units[asset] * (price - state.prices[asset]) for asset, price in prices.items()
    )
    nav_before = fsum([cash, *(state.units[asset] * price for asset, price in prices.items())])
    if not isfinite(nav_before) or nav_before <= 0:
        raise ArithmeticError("Portfolio NAV must remain finite and positive")
    execution = (
        _execute(
            prices=prices,
            units=state.units,
            cash=cash,
            nav=nav_before,
            allocation=target.allocation,
            costs=costs,
        )
        if target is not None
        else Execution(state.units, cash, 0.0, 0.0, ())
    )
    return _ledger_entry(
        close=close,
        observation=target.observed_at if target is not None else None,
        prices=prices,
        execution=execution,
        nav_before=nav_before,
        cash_before=cash,
        asset_pnl=asset_pnl,
        cash_pnl=cash_pnl,
        previous_nav=state.nav,
    )


def _indexed_prices(panel: PricePanel) -> dict[datetime, dict[str, float]]:
    by_close: dict[datetime, dict[str, float]] = {close: {} for close in panel.calendar.closes}
    for row in panel.observations:
        by_close[row.observed_at][row.asset] = row.adjusted_close
    return by_close


def run_portfolio(
    panel: PricePanel,
    targets: tuple[RebalanceTarget, ...],
    *,
    cash_returns: tuple[CashReturn, ...],
    costs: ProportionalCost,
    initial_nav: float,
) -> PortfolioResult:
    """Accrue old holdings, then execute targets and deduct fees at each close.

    Inputs are fixed records, not strategy callbacks. This enforces execution lag
    but cannot certify how an external caller selected its target weights.
    """
    _validate_inputs(panel, targets, cash_returns, initial_nav)
    prices_by_close = _indexed_prices(panel)
    targets_by_close = {target.execute_at: target for target in targets}
    rates_by_close = {row.observed_at: row.simple_return for row in cash_returns}
    state = _PositionState(
        dict.fromkeys(panel.assets, 0.0),
        prices_by_close[panel.calendar.closes[0]],
        initial_nav,
        None,
    )
    ledger: list[LedgerEntry] = []
    for close in panel.calendar.closes:
        prices = prices_by_close[close]
        entry = _advance(
            state, close, prices, rates_by_close.get(close, 0.0), targets_by_close.get(close), costs
        )
        ledger.append(entry)
        state = _PositionState(
            {holding.asset: holding.units for holding in entry.holdings},
            prices,
            entry.cash,
            entry.nav,
        )
    return PortfolioResult(
        currency=panel.currency, initial_nav=initial_nav, costs=costs, ledger=tuple(ledger)
    )
