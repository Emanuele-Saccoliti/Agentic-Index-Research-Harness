"""Storage contract. The controller is the sole application writer."""

from collections.abc import Sequence
from typing import Protocol

from etf_harness.schemas.domain import Event, Record


class RegistryError(ValueError):
    """Malformed history or an invalid append."""


class RevisionConflict(RegistryError):
    """A competing writer changed the stream; reload and re-evaluate policy."""


class Registry(Protocol):
    def events(self, campaign_id: str) -> tuple[Event, ...]: ...

    def append(
        self, campaign_id: str, expected_revision: int, records: Sequence[Record]
    ) -> tuple[Event, ...]: ...
