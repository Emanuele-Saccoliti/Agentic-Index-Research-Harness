"""Pure, fail-closed authorization rules. No storage, clock or external calls."""

from dataclasses import dataclass

from etf_harness.controller.states import TERMINAL_STATES, CampaignState
from etf_harness.policy.actions import Action, Outcome
from etf_harness.schemas.domain import PolicyDecision


@dataclass(frozen=True)
class PolicyContext:
    state: CampaignState | None = None
    synthetic: bool = True
    approval_present: bool = False
    approval_matches: bool = False
    parameters_match: bool = True
    budget_available: bool = True
    provenance_matches: bool = True
    actual_violation: bool = False


class ActionPolicy:
    def evaluate(self, action: Action | str, context: PolicyContext) -> PolicyDecision:
        def result(outcome: Outcome, rule: str, reason: str) -> PolicyDecision:
            return PolicyDecision(outcome=outcome, rule=rule, reason=reason)

        try:
            action = Action(action)
        except ValueError:
            return result(Outcome.DENY, "unknown_action", "Unknown actions fail closed")
        if action in {Action.READ_DOCUMENTATION, Action.READ_DEVELOPMENT}:
            return result(Outcome.ALLOW, "read", "Read-only action")
        if action in {
            Action.MODIFY_HISTORY,
            Action.MODIFY_LOCKED_CONFIG,
            Action.MODIFY_PROTECTED_LOGIC,
        }:
            return result(
                Outcome.DENY, "protected", "Protected history and campaign scope are immutable"
            )
        if context.state in TERMINAL_STATES:
            return result(Outcome.DENY, "terminal", "Terminal campaigns cannot be changed")
        if not context.synthetic:
            return result(Outcome.DENY, "p1_synthetic_only", "P1 does not authorize live research")
        if not context.parameters_match:
            return result(Outcome.DENY, "parameter_scope", "Parameters differ from approved bounds")
        if not context.budget_available:
            return result(Outcome.DENY, "budget", "Experiment budget exhausted")
        if not context.provenance_matches:
            return result(Outcome.DENY, "provenance", "Provenance does not match locked scope")
        if action == Action.CREATE_CAMPAIGN:
            if context.state is not None:
                return result(Outcome.DENY, "exists", "Campaign already exists")
            return result(Outcome.ALLOW, "create", "Create synthetic planning campaign")
        if context.state is None:
            return result(Outcome.DENY, "missing_campaign", "Campaign does not exist")
        if action == Action.PROPOSE_HYPOTHESIS:
            if context.state not in {CampaignState.PLANNING, CampaignState.AWAITING_APPROVAL}:
                return result(
                    Outcome.DENY, "proposal_state", "Proposals require a planning campaign"
                )
            return result(Outcome.ALLOW, "proposal", "Record a proposal without execution")
        if action == Action.INVALIDATE:
            if not context.actual_violation:
                return result(
                    Outcome.DENY, "violation_evidence", "Actual violation evidence is required"
                )
            return result(Outcome.ALLOW, "violation", "Record demonstrated protocol violation")
        required_states = {
            Action.APPROVE_HYPOTHESIS: {CampaignState.AWAITING_APPROVAL},
            Action.REJECT_HYPOTHESIS: {CampaignState.AWAITING_APPROVAL},
            Action.CREATE_SPEC: {CampaignState.APPROVED},
            Action.REGISTER_EXPERIMENT: {CampaignState.APPROVED},
        }
        if action in required_states and context.state not in required_states[action]:
            return result(Outcome.DENY, "action_state", "Action is illegal in the current state")
        approval_actions = {
            Action.APPROVE_HYPOTHESIS,
            Action.REJECT_HYPOTHESIS,
            Action.REJECT_CAMPAIGN,
            Action.CREATE_SPEC,
            Action.REGISTER_EXPERIMENT,
            Action.ADD_PRIMITIVE,
            Action.FINAL_EVALUATION,
            Action.PUBLISH_CLAIM,
        }
        if action == Action.PUBLISH_CLAIM:
            return result(Outcome.DENY, "p1_no_claims", "P1 has no audited financial evidence")
        if action in approval_actions:
            if not context.approval_present:
                return result(
                    Outcome.REQUIRE_APPROVAL, "human_gate", "A matching human decision is required"
                )
            if not context.approval_matches:
                return result(
                    Outcome.DENY, "approval_mismatch", "Approval does not authorize this request"
                )
        if action in {Action.ADD_PRIMITIVE, Action.FINAL_EVALUATION, Action.CREATE_SPEC}:
            return result(Outcome.DENY, "deferred", "This action has no P1 implementation")
        if action in {
            Action.APPROVE_HYPOTHESIS,
            Action.REJECT_HYPOTHESIS,
            Action.REJECT_CAMPAIGN,
            Action.REGISTER_EXPERIMENT,
            Action.RECORD_OUTCOME,
            Action.RECORD_CORRECTION,
        }:
            return result(Outcome.ALLOW, "authorized", "Action is within the permitted P1 scope")
        return result(Outcome.DENY, "unsupported", "Action has no explicit P1 allow rule")
