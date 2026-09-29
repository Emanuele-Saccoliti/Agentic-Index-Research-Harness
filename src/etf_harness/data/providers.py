"""CSV and Parquet adapters share one strict normalized record contract."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pandas as pd

from etf_harness.data.models import PriceObservation, PricePanel, SessionCalendar

PRICE_COLUMNS = ("observed_at", "asset", "adjusted_close", "currency", "price_convention")


class PriceProvider(Protocol):
    def load(
        self, *, calendar: SessionCalendar, assets: tuple[str, ...], currency: str
    ) -> PricePanel:
        """Load exactly the requested panel, rejecting missing and extra observations."""
        ...


@dataclass(frozen=True)
class LocalPriceProvider:
    path: Path

    def load(
        self, *, calendar: SessionCalendar, assets: tuple[str, ...], currency: str
    ) -> PricePanel:
        if self.path.suffix.lower() == ".csv":
            # Preserve identifiers such as 'NA' and reject missing numeric fields later.
            frame = pd.read_csv(self.path, keep_default_na=False, dtype=str)
            if "adjusted_close" in frame:
                frame["adjusted_close"] = frame["adjusted_close"].map(float)
        elif self.path.suffix.lower() == ".parquet":
            frame = pd.read_parquet(self.path, engine="pyarrow")
        else:
            raise ValueError("Only local .csv and .parquet files are supported")
        if len(frame.columns) != len(PRICE_COLUMNS) or set(frame.columns) != set(PRICE_COLUMNS):
            raise ValueError(f"Expected exactly these price columns: {PRICE_COLUMNS}")
        observations = tuple(
            PriceObservation.model_validate(row) for row in frame.to_dict(orient="records")
        )
        return PricePanel(
            calendar=calendar, assets=assets, currency=currency, observations=observations
        )


def write_prices(panel: PricePanel, path: Path) -> None:
    """Write normalized data for local snapshots and reproducible fixture round trips."""
    frame = pd.DataFrame([row.model_dump(mode="json") for row in panel.observations])
    if path.suffix.lower() == ".csv":
        frame.to_csv(path, index=False)
    elif path.suffix.lower() == ".parquet":
        frame.to_parquet(path, engine="pyarrow", index=False)
    else:
        raise ValueError("Only local .csv and .parquet files are supported")
