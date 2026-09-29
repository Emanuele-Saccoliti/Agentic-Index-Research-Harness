import json
from pathlib import Path

import pytest

from etf_harness.data.models import CashReturn, PricePanel, SessionCalendar
from etf_harness.data.providers import LocalPriceProvider


@pytest.fixture
def calendar() -> SessionCalendar:
    path = Path(__file__).parents[1] / "fixtures" / "p2_case.json"
    return SessionCalendar.model_validate(json.loads(path.read_text(encoding="utf-8"))["calendar"])


@pytest.fixture
def panel(calendar: SessionCalendar) -> PricePanel:
    path = Path(__file__).parents[1] / "fixtures" / "p2_prices.csv"
    return LocalPriceProvider(path).load(
        calendar=calendar, assets=("EQUITY", "BOND"), currency="USD"
    )


@pytest.fixture
def cash_returns(calendar: SessionCalendar) -> tuple[CashReturn, ...]:
    return tuple(CashReturn(observed_at=close, simple_return=0.0) for close in calendar.closes[1:])
