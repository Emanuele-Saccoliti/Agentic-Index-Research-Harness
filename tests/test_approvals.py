import pytest
from conftest import human_decision

from etf_harness.controller.approvals import approval_matches, approval_scope
from etf_harness.controller.service import ActionRefused, CampaignController
from etf_harness.controller.states import CampaignState
from etf_harness.schemas.domain import Approval, Budget, Campaign, Hypothesis, digest


@pytest.mark.parametrize(
    "field,value",
    [
        ("campaign_digest", digest("different campaign")),
        ("hypothesis_digest", digest("different hypothesis")),
        ("parameter_space_digest", digest("different range")),
        ("budget", Budget(candidate=3)),
        ("locked_config_digest", digest("different config")),
        ("preregistration_digest", digest("different preregistration")),
        ("allowed_paths", ("other/path",)),
        ("allowed_primitives", ("new primitive",)),
        ("synthetic", False),
    ],
)
def test_changed_scope_cannot_use_approval(
    service: CampaignController,
    campaign: Campaign,
    hypothesis: Hypothesis,
    field: str,
    value: object,
) -> None:
    service.create(campaign)
    request = service.propose(hypothesis)
    changed = request.model_copy(update={"scope": request.scope.model_copy(update={field: value})})
    approval = human_decision(changed)
    with pytest.raises(ActionRefused, match="approval_mismatch"):
        service.approve(approval)
    view = service.status(campaign.id)
    assert view.campaign.state == CampaignState.AWAITING_APPROVAL
    assert not view.approvals


def test_action_identity_and_agent_identity_do_not_match(
    service: CampaignController,
    campaign: Campaign,
    hypothesis: Hypothesis,
) -> None:
    from etf_harness.policy.actions import Action

    service.create(campaign)
    request = service.propose(hypothesis)
    approval = human_decision(request)
    assert not approval_matches(
        approval, request.model_copy(update={"action": Action.FINAL_EVALUATION})
    )
    assert not approval_matches(approval.model_copy(update={"decided_by": "Coordinator"}), request)


def test_progress_does_not_change_campaign_approval_identity(
    campaign: Campaign, hypothesis: Hypothesis
) -> None:
    later = campaign.model_copy(update={"state": CampaignState.APPROVED})
    assert approval_scope(campaign, hypothesis) == approval_scope(later, hypothesis)


def test_hypothesis_rejection_leaves_other_proposals_available(
    service: CampaignController,
    campaign: Campaign,
    hypothesis: Hypothesis,
) -> None:
    service.create(campaign)
    first = service.propose(hypothesis)
    second = service.propose(hypothesis.model_copy(update={"id": "HYP-SECOND"}))
    rejection = human_decision(first).model_copy(update={"decision": "REJECTED"})
    service.approve(rejection)
    assert service.status(campaign.id).campaign.state == CampaignState.AWAITING_APPROVAL
    service.approve(human_decision(second, "APR-SECOND"))
    assert service.status(campaign.id).campaign.state == CampaignState.APPROVED


def test_hypothesis_grant_cannot_close_campaign(
    approved: tuple[CampaignController, Approval],
) -> None:
    service, approval = approved
    with pytest.raises(ActionRefused, match="approval_mismatch"):
        service.reject(approval.campaign_id, approval, "stop")
