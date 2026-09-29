"""Long-only targets and an auditable per-session accounting ledger."""

from math import fsum, isclose
from typing import Annotated, Self

from pydantic import Field, StrictFloat, model_validator

from etf_harness.data.models import Currency, PositiveAmount, UTCDateTime
from etf_harness.schemas.domain import Identifier, Model

Weight = Annotated[StrictFloat, Field(ge=0, le=1)]
Nonnegative = Annotated[StrictFloat, Field(ge=0)]


class AssetWeight(Model):
    asset: Identifier
    weight: Weight


class Allocation(Model):
    assets: tuple[AssetWeight, ...]
    cash_weight: Weight

    @model_validator(mode="after")
    def validate_weights(self) -> Self:
        if len({item.asset for item in self.assets}) != len(self.assets):
            raise ValueError("Duplicate asset weights")
        total = fsum([self.cash_weight, *(item.weight for item in self.assets)])
        if not isclose(total, 1.0, rel_tol=0, abs_tol=1e-12):
            raise ValueError("Asset and cash weights must sum to one")
        object.__setattr__(self, "assets", tuple(sorted(self.assets, key=lambda item: item.asset)))
        return self


class RebalanceTarget(Model):
    observed_at: UTCDateTime
    execute_at: UTCDateTime
    allocation: Allocation

    @model_validator(mode="after")
    def validate_lag(self) -> Self:
        if self.execute_at <= self.observed_at:
            raise ValueError("Execution must follow observation")
        return self


class ProportionalCost(Model):
    """Basis points on gross ETF traded notional; research scenarios are external."""

    basis_points: Annotated[StrictFloat, Field(ge=0, lt=10000)]

    @property
    def rate(self) -> float:
        return self.basis_points / 10000.0


class Holding(Model):
    asset: Identifier
    units: Nonnegative
    adjusted_close: PositiveAmount
    market_value: Nonnegative
    weight: Weight


class Trade(Model):
    asset: Identifier
    units: StrictFloat
    notional: StrictFloat


class LedgerEntry(Model):
    close: UTCDateTime
    observation: UTCDateTime | None
    nav_before_trade: PositiveAmount
    nav: PositiveAmount
    cash_before_trade: Nonnegative
    cash: Nonnegative
    cash_weight: Weight
    asset_pnl: StrictFloat
    cash_pnl: StrictFloat
    fee: Nonnegative
    gross_traded_notional: Nonnegative
    gross_turnover: Nonnegative
    half_turnover: Nonnegative
    net_return: StrictFloat | None
    holdings: tuple[Holding, ...]
    trades: tuple[Trade, ...]


class PortfolioResult(Model):
    currency: Currency
    initial_nav: PositiveAmount
    costs: ProportionalCost
    ledger: tuple[LedgerEntry, ...]

    @property
    def total_fees(self) -> float:
        return fsum(row.fee for row in self.ledger)

    @property
    def total_gross_turnover(self) -> float:
        return fsum(row.gross_turnover for row in self.ledger)
