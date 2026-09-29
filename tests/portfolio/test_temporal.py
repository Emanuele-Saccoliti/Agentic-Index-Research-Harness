from datetime import datetime

import pytest
from pydantic import ValidationError

from etf_harness.backtest.engine import run_portfolio
from etf_harness.backtest.models import ProportionalCost, RebalanceTarget
from etf_harness.backtest.schedule import fixed_targets
from etf_harness.benchmarks import equal_sleeve, equal_weight, sixty_forty
from etf_harness.data.models import CashReturn, PricePanel, SessionCalendar


def test_next_close_execution_earns_only_subsequent_returns(
    panel: PricePanel, cash_returns: tuple[CashReturn, ...]
) -> None:
    closes = panel.calendar.closes
    targets = (
        RebalanceTarget(
            observed_at=closes[0], execute_at=closes[1], allocation=equal_weight(("BOND",))
        ),
        RebalanceTarget(
            observed_at=closes[1], execute_at=closes[2], allocation=equal_weight(("EQUITY",))
        ),
    )
    result = run_portfolio(
        panel,
        targets,
        cash_returns=cash_returns,
        costs=ProportionalCost(basis_points=0.0),
        initial_nav=1000.0,
    )
    # Equity rises 10% before its purchase. Only the following 10% is earned.
    assert result.ledger[2].nav == pytest.approx(1000)
    assert result.ledger[3].nav == pytest.approx(1100)
    assert result.ledger[2].observation == closes[1]


def test_future_price_perturbations_preserve_all_earlier_records(
    panel: PricePanel, cash_returns: tuple[CashReturn, ...]
) -> None:
    targets = fixed_targets(panel.calendar, sixty_forty("EQUITY", "BOND"), frequency="monthly")
    original = run_portfolio(
        panel,
        targets,
        cash_returns=cash_returns,
        costs=ProportionalCost(basis_points=25.0),
        initial_nav=1000.0,
    )
    for cutoff in panel.calendar.closes[:-1]:
        raw = panel.model_dump()
        for row in raw["observations"]:
            if row["observed_at"] > cutoff:
                row["adjusted_close"] *= 7.3 if row["asset"] == "EQUITY" else 0.2
        changed_panel = PricePanel.model_validate(raw)
        assert (
            fixed_targets(
                changed_panel.calendar, sixty_forty("EQUITY", "BOND"), frequency="monthly"
            )
            == targets
        )
        changed = run_portfolio(
            changed_panel,
            targets,
            cash_returns=cash_returns,
            costs=ProportionalCost(basis_points=25.0),
            initial_nav=1000.0,
        )
        assert [r for r in changed.ledger if r.close <= cutoff] == [
            r for r in original.ledger if r.close <= cutoff
        ]


@pytest.mark.parametrize("offset", [0, -1, 2])
def test_bad_execution_lags_fail(
    panel: PricePanel, cash_returns: tuple[CashReturn, ...], offset: int
) -> None:
    with pytest.raises(ValueError, match="Execution must follow|next declared"):
        target = RebalanceTarget(
            observed_at=panel.calendar.closes[1],
            execute_at=panel.calendar.closes[1 + offset],
            allocation=equal_weight(panel.assets),
        )
        run_portfolio(
            panel,
            (target,),
            cash_returns=cash_returns,
            costs=ProportionalCost(basis_points=0.0),
            initial_nav=1000.0,
        )


@pytest.mark.parametrize(
    "frequency,indices",
    [
        ("buy_and_hold", [0]),
        ("every_session", [0, 1, 2, 3, 4]),
        ("monthly", [0, 2]),
        ("quarterly", [0]),
    ],
)
def test_schedule_on_fixture_calendar(
    panel: PricePanel, frequency: str, indices: list[int]
) -> None:
    targets = fixed_targets(panel.calendar, equal_weight(panel.assets), frequency=frequency)
    assert [t.observed_at for t in targets] == [panel.calendar.closes[i] for i in indices]
    assert [t.execute_at for t in targets] == [panel.calendar.closes[i + 1] for i in indices]


def test_quarter_weekend_holiday_and_year_boundary() -> None:
    dates = ("2023-12-28", "2023-12-29", "2024-01-02", "2024-03-28", "2024-04-01", "2024-04-02")
    calendar = SessionCalendar(
        closes=tuple(datetime.fromisoformat(f"{d}T20:00:00+00:00") for d in dates)
    )
    targets = fixed_targets(calendar, equal_weight(("A",)), frequency="quarterly")
    assert [t.observed_at for t in targets] == [calendar.closes[i] for i in (0, 1, 3)]
    assert [t.execute_at for t in targets] == [calendar.closes[i] for i in (1, 2, 4)]


def test_single_close_is_initial_cash_only(panel: PricePanel) -> None:
    calendar = SessionCalendar(closes=panel.calendar.closes[:1])
    single = PricePanel(
        calendar=calendar,
        assets=panel.assets,
        currency=panel.currency,
        observations=panel.observations[:2],
    )
    targets = fixed_targets(calendar, equal_weight(panel.assets), frequency="monthly")
    result = run_portfolio(
        single,
        targets,
        cash_returns=(),
        costs=ProportionalCost(basis_points=0.0),
        initial_nav=1000.0,
    )
    assert targets == ()
    assert result.ledger[0].cash == 1000
    assert result.ledger[0].net_return is None


def test_equal_sleeve_is_not_equal_asset_weight() -> None:
    allocation = equal_sleeve({"equity": ("A", "B"), "bonds": ("C",)})
    assert {item.asset: item.weight for item in allocation.assets} == {
        "A": 0.25,
        "B": 0.25,
        "C": 0.5,
    }
    assert allocation == equal_sleeve({"bonds": ("C",), "equity": ("B", "A")})


def test_invalid_benchmarks() -> None:
    with pytest.raises(ValueError):
        equal_weight(())
    with pytest.raises(ValidationError, match="Duplicate"):
        sixty_forty("A", "A")
    for sleeves in ({}, {"empty": ()}, {" ": ("A",)}, {"one": ("A",), "two": ("A",)}):
        with pytest.raises(ValueError):
            equal_sleeve(sleeves)
