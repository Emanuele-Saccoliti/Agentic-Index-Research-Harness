from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from etf_harness.data.models import CashReturn, PriceObservation, PricePanel, SessionCalendar
from etf_harness.data.providers import LocalPriceProvider, write_prices


def test_input_permutation_is_canonical(panel: PricePanel) -> None:
    assert (
        PricePanel(
            calendar=panel.calendar,
            assets=tuple(reversed(panel.assets)),
            currency=panel.currency,
            observations=tuple(reversed(panel.observations)),
        )
        == panel
    )


@pytest.mark.parametrize("assets", [(), ("BOND", "BOND"), ("BOND",)])
def test_declared_asset_universe_must_match(panel: PricePanel, assets: tuple[str, ...]) -> None:
    with pytest.raises(ValidationError):
        PricePanel(
            calendar=panel.calendar, assets=assets, currency="USD", observations=panel.observations
        )


@pytest.mark.parametrize("extension", [".csv", ".parquet"])
def test_float_precision_is_preserved(panel: PricePanel, tmp_path: Path, extension: str) -> None:
    raw = panel.model_dump()
    raw["observations"][0]["adjusted_close"] = 1.2345678901234567
    precise = PricePanel.model_validate(raw)
    path = tmp_path / f"precise{extension}"
    write_prices(precise, path)
    restored = LocalPriceProvider(path).load(
        calendar=panel.calendar, assets=panel.assets, currency="USD"
    )
    assert restored == precise


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), -float("inf"), True, "100"])
def test_bad_price_rejected(panel: PricePanel, value: object) -> None:
    row = panel.observations[0].model_dump()
    row["adjusted_close"] = value
    with pytest.raises(ValidationError):
        PriceObservation.model_validate(row)


@pytest.mark.parametrize(
    "change", ["duplicate", "missing_asset", "missing_session", "currency", "outside", "asset"]
)
def test_incomplete_or_misaligned_panels_fail(panel: PricePanel, change: str) -> None:
    raw = panel.model_dump()
    if change == "duplicate":
        raw["observations"] += (raw["observations"][0],)
    elif change == "missing_asset":
        raw["observations"] = raw["observations"][1:]
    elif change == "missing_session":
        raw["observations"] = raw["observations"][2:]
    elif change == "currency":
        raw["observations"][0]["currency"] = "EUR"
    elif change == "outside":
        raw["observations"][0]["observed_at"] += timedelta(days=30)
    else:
        raw["observations"][0]["asset"] = "UNKNOWN"
    with pytest.raises(ValidationError):
        PricePanel.model_validate(raw)


@pytest.mark.parametrize(
    "closes",
    [
        (),
        (datetime(2024, 1, 1),),
        (datetime(2024, 1, 1, tzinfo=timezone(timedelta(hours=1))),),
        (datetime(2024, 1, 2, tzinfo=UTC), datetime(2024, 1, 1, tzinfo=UTC)),
        (datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 1, 1, tzinfo=UTC)),
        (datetime(2024, 1, 1, 12, tzinfo=UTC), datetime(2024, 1, 1, 21, tzinfo=UTC)),
    ],
)
def test_invalid_calendars(closes: tuple[datetime, ...]) -> None:
    with pytest.raises(ValidationError):
        SessionCalendar(closes=closes)


@pytest.mark.parametrize(
    "field,value", [("price_convention", "raw_close"), ("currency", "usd"), ("asset", " ")]
)
def test_price_metadata_rejected(panel: PricePanel, field: str, value: str) -> None:
    raw = panel.observations[0].model_dump()
    raw[field] = value
    with pytest.raises(ValidationError):
        PriceObservation.model_validate(raw)


@pytest.mark.parametrize("rate", [-1.0, -2.0, float("inf"), float("nan"), True])
def test_invalid_cash_return(calendar: SessionCalendar, rate: float) -> None:
    with pytest.raises(ValidationError):
        CashReturn(observed_at=calendar.closes[0], simple_return=rate)


@pytest.mark.parametrize("extension", [".csv", ".parquet"])
@pytest.mark.parametrize(
    "defect", ["extra_column", "missing_column", "missing_value", "duplicate", "raw_price"]
)
def test_file_validation(panel: PricePanel, tmp_path: Path, extension: str, defect: str) -> None:
    frame = pd.DataFrame([row.model_dump(mode="json") for row in panel.observations])
    if defect == "extra_column":
        frame["volume"] = 100
    elif defect == "missing_column":
        frame = frame.drop(columns=["price_convention"])
    elif defect == "missing_value":
        frame.loc[0, "adjusted_close"] = float("nan")
    elif defect == "duplicate":
        frame = pd.concat([frame, frame.iloc[:1]])
    else:
        frame["price_convention"] = "raw_close"
    path = tmp_path / f"broken{extension}"
    if extension == ".csv":
        frame.to_csv(path, index=False)
    else:
        frame.to_parquet(path, index=False)
    with pytest.raises(ValueError):
        LocalPriceProvider(path).load(calendar=panel.calendar, assets=panel.assets, currency="USD")


def test_identifiers_not_interpreted_as_missing(panel: PricePanel, tmp_path: Path) -> None:
    raw = panel.model_dump()
    raw["assets"] = ("NA", "BOND")
    for row in raw["observations"]:
        if row["asset"] == "EQUITY":
            row["asset"] = "NA"
    renamed = PricePanel.model_validate(raw)
    path = tmp_path / "prices.csv"
    write_prices(renamed, path)
    assert (
        LocalPriceProvider(path).load(
            calendar=renamed.calendar, assets=renamed.assets, currency="USD"
        )
        == renamed
    )


def test_unsupported_format(panel: PricePanel, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Only local"):
        LocalPriceProvider(tmp_path / "prices.json").load(
            calendar=panel.calendar, assets=panel.assets, currency="USD"
        )
    with pytest.raises(ValueError, match="Only local"):
        write_prices(panel, tmp_path / "prices.json")
