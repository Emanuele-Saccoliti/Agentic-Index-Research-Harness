"""Legal edges, separate from action prerequisites and human authorization."""

from enum import StrEnum
from types import MappingProxyType


class CampaignState(StrEnum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    PROPOSED = "PROPOSED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    IMPLEMENTING = "IMPLEMENTING"
    DEVELOPMENT_EVALUATION = "DEVELOPMENT_EVALUATION"
    FALSIFICATION = "FALSIFICATION"
    AUDIT = "AUDIT"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    INVALID = "INVALID"


TERMINAL_STATES = frozenset(
    {
        CampaignState.ACCEPTED,
        CampaignState.REJECTED,
        CampaignState.INCONCLUSIVE,
        CampaignState.INVALID,
    }
)
# Explicit normal research edges; closure edges supplement every nonterminal state.
_RESEARCH_TRANSITIONS = {
    CampaignState.CREATED: frozenset({CampaignState.PLANNING}),
    CampaignState.PLANNING: frozenset({CampaignState.PROPOSED}),
    CampaignState.PROPOSED: frozenset({CampaignState.AWAITING_APPROVAL}),
    CampaignState.AWAITING_APPROVAL: frozenset({CampaignState.APPROVED}),
    CampaignState.APPROVED: frozenset({CampaignState.IMPLEMENTING}),
    CampaignState.IMPLEMENTING: frozenset({CampaignState.DEVELOPMENT_EVALUATION}),
    CampaignState.DEVELOPMENT_EVALUATION: frozenset({CampaignState.FALSIFICATION}),
    CampaignState.FALSIFICATION: frozenset({CampaignState.AUDIT}),
    CampaignState.AUDIT: TERMINAL_STATES,
    **{state: frozenset() for state in TERMINAL_STATES},
}
LEGAL_TRANSITIONS = MappingProxyType(
    {
        state: targets
        | (
            frozenset()
            if state in TERMINAL_STATES
            else frozenset({CampaignState.REJECTED, CampaignState.INVALID})
        )
        for state, targets in _RESEARCH_TRANSITIONS.items()
    }
)


def validate_transition(source: CampaignState, target: CampaignState) -> None:
    if target not in LEGAL_TRANSITIONS[source]:
        raise ValueError(f"Illegal transition: {source} -> {target}")
