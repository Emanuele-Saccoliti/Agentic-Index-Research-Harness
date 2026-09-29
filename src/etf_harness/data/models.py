"""Immutable daily total-return price contracts with explicit session alignment."""

from datetime import datetime
from itertools import product
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, AwareDatetime, Field, StrictFloat, model_validator

from etf_harness.schemas.domain import Identifier, Model


def require_utc(value: datetime) -> datetime:
    """Reject implicit local times and non-UTC offsets."""
    offset = value.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise ValueError("Session timestamps must use UTC")
    return value


UTCDateTime = Annotated[AwareDatetime, AfterValidator(require_utc)]
PositiveAmount = Annotated[StrictFloat, Field(gt=0)]
Currency = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]


class SessionCalendar(Model):
    """Authoritative daily session closes, not inferred from available prices."""

    closes: tuple[UTCDateTime, ...]

    @model_validator(mode="after")
    def validate_closes(self) -> Self:
        if not self.closes or any(
            a >= b for a, b in zip(self.closes, self.closes[1:], strict=False)
        ):
            raise ValueError("Session closes must be nonempty, unique and increasing")
        if len({close.date() for close in self.closes}) != len(self.closes):
            raise ValueError("At most one session close per UTC date is supported")
        return self


class PriceObservation(Model):
    observed_at: UTCDateTime
    asset: Identifier
    adjusted_close: PositiveAmount
    currency: Currency
    price_convention: Literal["adjusted_total_return"]


class PricePanel(Model):
    """A complete rectangular price panel in a single declared currency."""

    calendar: SessionCalendar
    assets: tuple[Identifier, ...]
    currency: Currency
    observations: tuple[PriceObservation, ...]

    @model_validator(mode="after")
    def validate_panel(self) -> Self:
        if not self.assets or len(set(self.assets)) != len(self.assets):
            raise ValueError("Assets must be nonempty and unique")
        keys = {(row.observed_at, row.asset) for row in self.observations}
        expected = set(product(self.calendar.closes, self.assets))
        if len(keys) != len(self.observations):
            raise ValueError("Duplicate session/asset observations")
        if keys != expected:
            raise ValueError("Prices must exactly cover the declared calendar and assets")
        if any(row.currency != self.currency for row in self.observations):
            raise ValueError("Mixed currencies or unexpected base currency")
        object.__setattr__(self, "assets", tuple(sorted(self.assets)))
        object.__setattr__(
            self,
            "observations",
            tuple(sorted(self.observations, key=lambda r: (r.observed_at, r.asset))),
        )
        return self


class CashReturn(Model):
    """Simple return over the entire interval ending at this session close."""

    observed_at: UTCDateTime
    simple_return: Annotated[StrictFloat, Field(gt=-1)]
