import pytest

from etf_harness.controller.states import TERMINAL_STATES, validate_transition
from etf_harness.controller.states import CampaignState as S


@pytest.mark.parametrize(
    "source,target",
    [
        (S.CREATED, S.APPROVED),
        (S.PLANNING, S.AUDIT),
        (S.APPROVED, S.ACCEPTED),
        (S.AWAITING_APPROVAL, S.PLANNING),
        (S.APPROVED, S.APPROVED),
    ],
)
def test_illegal_transitions(source: S, target: S) -> None:
    with pytest.raises(ValueError, match="Illegal transition"):
        validate_transition(source, target)


@pytest.mark.parametrize("source", list(TERMINAL_STATES))
@pytest.mark.parametrize("target", list(S))
def test_terminal_states_have_no_exit(source: S, target: S) -> None:
    with pytest.raises(ValueError):
        validate_transition(source, target)


def test_research_path_and_approved_administrative_edges() -> None:
    path = [
        S.CREATED,
        S.PLANNING,
        S.PROPOSED,
        S.AWAITING_APPROVAL,
        S.APPROVED,
        S.IMPLEMENTING,
        S.DEVELOPMENT_EVALUATION,
        S.FALSIFICATION,
        S.AUDIT,
        S.ACCEPTED,
    ]
    for source, target in zip(path, path[1:], strict=False):
        validate_transition(source, target)
    for state in set(S) - TERMINAL_STATES:
        validate_transition(state, S.REJECTED)
        validate_transition(state, S.INVALID)
