"""Approval identity is immutable scope, never current state or trial usage."""

from etf_harness.schemas.domain import (
    Approval,
    ApprovalRequest,
    ApprovalScope,
    Campaign,
    Hypothesis,
    digest,
)


def approval_scope(campaign: Campaign, hypothesis: Hypothesis | None) -> ApprovalScope:
    return ApprovalScope(
        campaign_digest=digest(campaign.model_dump(mode="json", exclude={"state"})),
        hypothesis_digest=digest(hypothesis) if hypothesis else None,
        parameter_space_digest=(
            digest(
                {
                    name: bound.model_dump(mode="json")
                    for name, bound in hypothesis.parameters.items()
                }
            )
            if hypothesis
            else None
        ),
        budget=hypothesis.budget if hypothesis else None,
        locked_config_digest=campaign.locked_config_digest,
        preregistration_digest=campaign.preregistration_digest,
        allowed_paths=hypothesis.allowed_paths if hypothesis else (),
        allowed_primitives=hypothesis.allowed_primitives if hypothesis else (),
        synthetic=campaign.synthetic,
    )


def approval_matches(
    approval: Approval,
    request: ApprovalRequest,
    *,
    approved_only: bool = True,
) -> bool:
    return (
        approval.campaign_id == request.campaign_id
        and approval.request_id == request.id
        and approval.request_digest == request.request_digest
        and approval.synthetic == request.scope.synthetic
        and approval.created_at >= request.created_at
        and (not approved_only or approval.decision == "APPROVED")
        and approval.authority == "human"
        and bool(approval.decided_by.strip())
        and bool(approval.source_reference.strip())
        and approval.decided_by.casefold()
        not in {
            "coordinator",
            "researcher",
            "strategy engineer",
            "falsifier",
            "auditor",
            "codex",
        }
    )
