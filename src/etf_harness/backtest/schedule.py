"""Schedule close observations and next-session executions without price data."""

from typing import Literal

from etf_harness.backtest.models import Allocation, RebalanceTarget
from etf_harness.data.models import SessionCalendar

Frequency = Literal["buy_and_hold", "every_session", "monthly", "quarterly"]


def fixed_targets(
    calendar: SessionCalendar, allocation: Allocation, *, frequency: Frequency
) -> tuple[RebalanceTarget, ...]:
    """Initialize at the first observation, then observe on specified period ends.

    The final close cannot create an executable order. A partial terminal period
    is never assumed to be a period end. Quarterly periods are calendar quarters.
    """
    if frequency not in {"buy_and_hold", "every_session", "monthly", "quarterly"}:
        raise ValueError(f"Unsupported rebalance frequency: {frequency}")
    targets: list[RebalanceTarget] = []
    for index, (observed, execution) in enumerate(
        zip(calendar.closes, calendar.closes[1:], strict=False)
    ):
        month_end = (observed.year, observed.month) != (execution.year, execution.month)
        quarter_end = (observed.year, (observed.month - 1) // 3) != (
            execution.year,
            (execution.month - 1) // 3,
        )
        scheduled = (
            frequency == "every_session"
            or (frequency == "monthly" and month_end)
            or (frequency == "quarterly" and quarter_end)
        )
        if index == 0 or scheduled:
            targets.append(
                RebalanceTarget(observed_at=observed, execute_at=execution, allocation=allocation)
            )
    return tuple(targets)
