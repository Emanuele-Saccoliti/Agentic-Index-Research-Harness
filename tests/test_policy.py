import pytest

from etf_harness.controller.states import CampaignState as S
from etf_harness.policy.actions import Action as A
from etf_harness.policy.actions import Outcome as O
from etf_harness.policy.rules import ActionPolicy, PolicyContext


@pytest.mark.parametrize("action", [A.APPROVE_HYPOTHESIS, A.REJECT_CAMPAIGN, A.REJECT_HYPOTHESIS])
def test_human_gates_park_without_approval(action: A) -> None:
    decision = ActionPolicy().evaluate(action, PolicyContext(state=S.AWAITING_APPROVAL))
    assert decision.outcome == O.REQUIRE_APPROVAL


@pytest.mark.parametrize(
    "action", [A.MODIFY_HISTORY, A.MODIFY_LOCKED_CONFIG, A.MODIFY_PROTECTED_LOGIC]
)
def test_approval_never_overrides_protection(action: A) -> None:
    context = PolicyContext(state=S.APPROVED, approval_present=True, approval_matches=True)
    assert ActionPolicy().evaluate(action, context).outcome == O.DENY


def test_unknown_actions_and_live_campaigns_fail_closed() -> None:
    assert ActionPolicy().evaluate("arbitrary_action", PolicyContext()).outcome == O.DENY
    assert (
        ActionPolicy().evaluate(A.CREATE_CAMPAIGN, PolicyContext(synthetic=False)).outcome == O.DENY
    )


def test_preflight_violations_are_denied_not_invalidated() -> None:
    policy = ActionPolicy()
    assert policy.evaluate(A.INVALIDATE, PolicyContext(state=S.APPROVED)).outcome == O.DENY
    assert (
        policy.evaluate(
            A.INVALIDATE, PolicyContext(state=S.APPROVED, actual_violation=True)
        ).outcome
        == O.ALLOW
    )


@pytest.mark.parametrize(
    "action", [A.CREATE_SPEC, A.FINAL_EVALUATION, A.ADD_PRIMITIVE, A.PUBLISH_CLAIM]
)
def test_deferred_actions_cannot_execute_with_approval(action: A) -> None:
    context = PolicyContext(state=S.APPROVED, approval_present=True, approval_matches=True)
    assert ActionPolicy().evaluate(action, context).outcome == O.DENY
