"""Single deterministic application boundary for campaign mutations.

P1 experiment registration is a synthetic control-plane exercise at APPROVED.
There is deliberately no executor and no public arbitrary-transition operation.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from etf_harness.controller.approvals import approval_matches, approval_scope
from etf_harness.controller.states import TERMINAL_STATES, CampaignState, validate_transition
from etf_harness.policy.actions import Action, Outcome
from etf_harness.policy.rules import ActionPolicy, PolicyContext
from etf_harness.registry.base import Registry, RegistryError
from etf_harness.schemas.domain import (
    Approval,
    ApprovalRequest,
    ApprovalScope,
    Campaign,
    EvidenceRecord,
    Experiment,
    ExperimentOutcome,
    Hypothesis,
    PolicyDecision,
    Record,
    Transition,
    digest,
)


@dataclass
class CampaignView:
    campaign: Campaign
    revision: int
    hypotheses: dict[str, Hypothesis] = field(default_factory=dict)
    requests: dict[str, ApprovalRequest] = field(default_factory=dict)
    approvals: dict[str, Approval] = field(default_factory=dict)
    experiments: dict[str, Experiment] = field(default_factory=dict)
    outcomes: dict[str, ExperimentOutcome] = field(default_factory=dict)
    evidence: dict[str, EvidenceRecord] = field(default_factory=dict)

    def used_budget(self, hypothesis_id: str) -> tuple[int, int]:
        trials = [e for e in self.experiments.values() if e.hypothesis_id == hypothesis_id]
        return len(trials), sum(e.robustness for e in trials)


class ActionRefused(ValueError):
    def __init__(self, decision: PolicyDecision) -> None:
        self.decision = decision
        super().__init__(f"{decision.outcome}: {decision.rule}: {decision.reason}")


class CampaignController:
    def __init__(
        self,
        registry: Registry,
        *,
        clock: Callable[[], datetime] | None = None,
        new_id: Callable[[], str] | None = None,
    ) -> None:
        self.registry = registry
        self.clock = clock or (lambda: datetime.now(UTC))
        self.new_id = new_id or (lambda: str(uuid4()))
        self.policy = ActionPolicy()

    def _evidence(
        self,
        campaign_id: str,
        action: Action,
        decision: PolicyDecision,
        *,
        related: tuple[str, ...] = (),
        note: str | None = None,
    ) -> EvidenceRecord:
        return EvidenceRecord(
            id=self.new_id(),
            campaign_id=campaign_id,
            created_at=self.clock(),
            action=action,
            decision=decision,
            related_ids=related,
            note=note or decision.reason,
        )

    def _transition(
        self,
        view: Campaign,
        target: CampaignState,
        evidence: EvidenceRecord,
    ) -> Transition:
        validate_transition(view.state, target)
        return Transition(
            id=self.new_id(),
            campaign_id=view.id,
            created_at=self.clock(),
            source=view.state,
            target=target,
            evidence_id=evidence.id,
        )

    def _require(
        self,
        view: CampaignView,
        action: Action,
        context: PolicyContext,
    ) -> PolicyDecision:
        decision = self.policy.evaluate(action, context)
        if decision.outcome != Outcome.ALLOW:
            self.registry.append(
                view.campaign.id,
                view.revision,
                [
                    self._evidence(view.campaign.id, action, decision),
                ],
            )
            raise ActionRefused(decision)
        return decision

    def _context(
        self,
        view: CampaignView,
        *,
        approval_present: bool = False,
        approval_matches: bool = False,
        parameters_match: bool = True,
        budget_available: bool = True,
        provenance_matches: bool = True,
        actual_violation: bool = False,
    ) -> PolicyContext:
        return PolicyContext(
            state=view.campaign.state,
            synthetic=view.campaign.synthetic,
            approval_present=approval_present,
            approval_matches=approval_matches,
            parameters_match=parameters_match,
            budget_available=budget_available,
            provenance_matches=provenance_matches,
            actual_violation=actual_violation,
        )

    def _scope(self, view: CampaignView, hypothesis: Hypothesis | None) -> ApprovalScope:
        # A closure request binds every current proposal, so adding one requires a new decision.
        scope = approval_scope(view.campaign, hypothesis)
        if hypothesis is None:
            scope = scope.model_copy(
                update={
                    "hypothesis_digest": digest(
                        [
                            view.hypotheses[key].model_dump(mode="json")
                            for key in sorted(view.hypotheses)
                        ]
                    ),
                }
            )
        return scope

    def _request_current(self, view: CampaignView, request: ApprovalRequest) -> bool:
        hypothesis = view.hypotheses.get(request.hypothesis_id or "")
        if request.hypothesis_id and hypothesis is None:
            return False
        return request.scope == self._scope(view, hypothesis)

    def _experiment_context(self, view: CampaignView, trial: Experiment) -> PolicyContext:
        hypothesis = view.hypotheses.get(trial.hypothesis_id)
        approval = view.approvals.get(trial.approval_id)
        request = view.requests.get(approval.request_id) if approval else None
        used, robustness_used = view.used_budget(trial.hypothesis_id)
        return self._context(
            view,
            approval_present=approval is not None,
            approval_matches=bool(
                approval
                and request
                and approval_matches(approval, request)
                and request.action == Action.APPROVE_HYPOTHESIS
                and request.hypothesis_id == trial.hypothesis_id
                and self._request_current(view, request)
            ),
            parameters_match=bool(
                hypothesis
                and trial.parameters.keys() == hypothesis.parameters.keys()
                and all(
                    bound.contains(trial.parameters[name])
                    for name, bound in hypothesis.parameters.items()
                )
            ),
            budget_available=bool(
                hypothesis
                and used < hypothesis.budget.candidate
                and (not trial.robustness or robustness_used < hypothesis.budget.robustness)
            ),
            provenance_matches=(
                trial.synthetic == view.campaign.synthetic
                and trial.provenance.locked_config_digest == view.campaign.locked_config_digest
                and trial.provenance.instruction_digests.get("locked_config")
                == view.campaign.locked_config_digest
                and trial.provenance.instruction_digests.get("preregistration")
                == view.campaign.preregistration_digest
            ),
        )

    def status(self, campaign_id: str) -> CampaignView:
        events = self.registry.events(campaign_id)
        if not events or not isinstance(events[0].record, Campaign):
            raise RegistryError(f"Campaign not found: {campaign_id}")
        initial = events[0].record
        if initial.state != CampaignState.CREATED or not initial.synthetic:
            raise RegistryError("Invalid P1 campaign genesis")
        view = CampaignView(campaign=initial, revision=len(events))
        for event in events[1:]:
            self._replay(view, event.record)
        return view

    def _replay(self, view: CampaignView, record: Record) -> None:
        if view.campaign.state in TERMINAL_STATES and not (
            isinstance(record, EvidenceRecord)
            and record.decision.outcome == Outcome.DENY
            and record.supersedes is None
            and not record.actual_violation
        ):
            raise RegistryError("Terminal campaign history cannot contain new mutations")
        if isinstance(record, Transition):
            evidence = view.evidence.get(record.evidence_id)
            expected_actions = {
                CampaignState.PLANNING: Action.CREATE_CAMPAIGN,
                CampaignState.PROPOSED: Action.PROPOSE_HYPOTHESIS,
                CampaignState.AWAITING_APPROVAL: Action.PROPOSE_HYPOTHESIS,
                CampaignState.APPROVED: Action.APPROVE_HYPOTHESIS,
                CampaignState.REJECTED: Action.REJECT_CAMPAIGN,
                CampaignState.INVALID: Action.INVALIDATE,
            }
            if (
                record.source != view.campaign.state
                or not evidence
                or evidence.decision.outcome != Outcome.ALLOW
                or expected_actions.get(record.target) != evidence.action
                or (
                    record.target == CampaignState.INVALID
                    and (not evidence.actual_violation or not evidence.artifact_digests)
                )
            ):
                raise RegistryError("Transition lacks matching P1 decision evidence")
            validate_transition(record.source, record.target)
            if record.target in {CampaignState.APPROVED, CampaignState.REJECTED}:
                grants = [
                    view.approvals[key] for key in evidence.related_ids if key in view.approvals
                ]
                if not any(
                    approval_matches(grant, view.requests[grant.request_id])
                    and view.requests[grant.request_id].action == evidence.action
                    and self._request_current(view, view.requests[grant.request_id])
                    for grant in grants
                ):
                    raise RegistryError("Transition has no matching recorded human approval")
            view.campaign = view.campaign.model_copy(update={"state": record.target})
        elif isinstance(record, Hypothesis):
            decision = self.policy.evaluate(Action.PROPOSE_HYPOTHESIS, self._context(view))
            if decision.outcome != Outcome.ALLOW:
                raise RegistryError("Hypothesis recorded in an illegal state")
            view.hypotheses[record.id] = record
        elif isinstance(record, ApprovalRequest):
            if (
                not self._request_current(view, record)
                or record.action not in {Action.APPROVE_HYPOTHESIS, Action.REJECT_CAMPAIGN}
                or (record.action == Action.APPROVE_HYPOTHESIS and not record.hypothesis_id)
                or (
                    record.action == Action.REJECT_CAMPAIGN
                    and (record.hypothesis_id is not None or not record.reason.strip())
                )
            ):
                raise RegistryError("Approval request scope differs from campaign history")
            view.requests[record.id] = record
        elif isinstance(record, Approval):
            request = view.requests.get(record.request_id)
            if (
                not request
                or not approval_matches(record, request, approved_only=False)
                or not self._request_current(view, request)
                or self.policy.evaluate(
                    request.action,
                    self._context(
                        view,
                        approval_present=True,
                        approval_matches=True,
                    ),
                ).outcome
                != Outcome.ALLOW
                or any(a.request_id == record.request_id for a in view.approvals.values())
            ):
                raise RegistryError("Invalid or duplicate approval decision in history")
            view.approvals[record.id] = record
        elif isinstance(record, Experiment):
            decision = self.policy.evaluate(
                Action.REGISTER_EXPERIMENT,
                self._experiment_context(view, record),
            )
            if decision.outcome != Outcome.ALLOW:
                raise RegistryError(f"Invalid trial history: {decision.rule}")
            view.experiments[record.id] = record
        elif isinstance(record, ExperimentOutcome):
            if (
                record.experiment_id not in view.experiments
                or record.experiment_id in view.outcomes
            ):
                raise RegistryError("Unregistered or already completed experiment")
            view.outcomes[record.experiment_id] = record
        elif isinstance(record, EvidenceRecord):
            if record.supersedes and record.supersedes not in view.evidence:
                raise RegistryError("Correction must reference existing evidence")
            view.evidence[record.id] = record
        else:
            raise RegistryError("A campaign may have only one genesis record")

    def _append(self, view: CampaignView, records: Sequence[Record]) -> None:
        # Validate a prospective batch before committing any part of it.
        prospective = copy.deepcopy(view)
        for record in records:
            self._replay(prospective, record)
        self.registry.append(view.campaign.id, view.revision, records)

    def create(self, campaign: Campaign) -> CampaignView:
        campaign = Campaign.model_validate_json(campaign.model_dump_json())
        if campaign.state != CampaignState.CREATED:
            raise ValueError("Campaign creation requires CREATED state")
        if self.registry.events(campaign.id):
            raise ValueError("Campaign already exists")
        decision = self.policy.evaluate(
            Action.CREATE_CAMPAIGN,
            PolicyContext(synthetic=campaign.synthetic),
        )
        if decision.outcome != Outcome.ALLOW:
            raise ActionRefused(decision)
        evidence = self._evidence(campaign.id, Action.CREATE_CAMPAIGN, decision)
        self.registry.append(
            campaign.id,
            0,
            [
                campaign,
                evidence,
                self._transition(campaign, CampaignState.PLANNING, evidence),
            ],
        )
        return self.status(campaign.id)

    def propose(self, hypothesis: Hypothesis) -> ApprovalRequest:
        hypothesis = Hypothesis.model_validate_json(hypothesis.model_dump_json())
        view = self.status(hypothesis.campaign_id)
        decision = self._require(view, Action.PROPOSE_HYPOTHESIS, self._context(view))
        if hypothesis.id in view.hypotheses:
            raise ValueError("Proposal ID already exists; revisions require new IDs")
        request = ApprovalRequest(
            id=self.new_id(),
            campaign_id=hypothesis.campaign_id,
            created_at=self.clock(),
            hypothesis_id=hypothesis.id,
            action=Action.APPROVE_HYPOTHESIS,
            scope=approval_scope(view.campaign, hypothesis),
        )
        evidence = self._evidence(
            hypothesis.campaign_id,
            Action.PROPOSE_HYPOTHESIS,
            decision,
            related=(hypothesis.id,),
        )
        parked = self._evidence(
            hypothesis.campaign_id,
            Action.APPROVE_HYPOTHESIS,
            self.policy.evaluate(
                Action.APPROVE_HYPOTHESIS,
                PolicyContext(
                    state=CampaignState.AWAITING_APPROVAL,
                    synthetic=view.campaign.synthetic,
                ),
            ),
            related=(request.id,),
        )
        records: list[Record] = [hypothesis, request, evidence]
        if view.campaign.state == CampaignState.PLANNING:
            records.extend(
                [
                    self._transition(view.campaign, CampaignState.PROPOSED, evidence),
                    self._transition(
                        view.campaign.model_copy(update={"state": CampaignState.PROPOSED}),
                        CampaignState.AWAITING_APPROVAL,
                        evidence,
                    ),
                ]
            )
        records.append(parked)
        self._append(view, records)
        return request

    def approve(self, approval: Approval) -> CampaignView:
        approval = Approval.model_validate_json(approval.model_dump_json())
        view = self.status(approval.campaign_id)
        request = view.requests.get(approval.request_id)
        matches = bool(
            request
            and request.action == Action.APPROVE_HYPOTHESIS
            and self._request_current(view, request)
            and approval_matches(approval, request, approved_only=False)
            and not any(a.request_id == request.id for a in view.approvals.values())
        )
        decision = self._require(
            view,
            Action.APPROVE_HYPOTHESIS,
            self._context(
                view,
                approval_present=True,
                approval_matches=matches,
            ),
        )
        action = (
            Action.APPROVE_HYPOTHESIS
            if approval.decision == "APPROVED"
            else Action.REJECT_HYPOTHESIS
        )
        evidence = self._evidence(view.campaign.id, action, decision, related=(approval.id,))
        records: list[Record] = [approval, evidence]
        if approval.decision == "APPROVED":
            records.append(self._transition(view.campaign, CampaignState.APPROVED, evidence))
        self._append(view, records)
        return self.status(view.campaign.id)

    def request_rejection(self, campaign_id: str, reason: str) -> ApprovalRequest:
        if not reason.strip():
            raise ValueError("Administrative closure requires a reason")
        view = self.status(campaign_id)
        decision = self.policy.evaluate(Action.REJECT_CAMPAIGN, self._context(view))
        if decision.outcome == Outcome.DENY:
            self._require(view, Action.REJECT_CAMPAIGN, self._context(view))
        request = ApprovalRequest(
            id=self.new_id(),
            campaign_id=campaign_id,
            created_at=self.clock(),
            hypothesis_id=None,
            action=Action.REJECT_CAMPAIGN,
            scope=self._scope(view, None),
            reason=reason,
        )
        for existing in view.requests.values():
            if existing.request_digest == request.request_digest:
                return existing
        self._append(
            view,
            [
                request,
                self._evidence(
                    campaign_id,
                    Action.REJECT_CAMPAIGN,
                    decision,
                    related=(request.id,),
                    note=reason,
                ),
            ],
        )
        return request

    def reject(self, campaign_id: str, approval: Approval, reason: str) -> CampaignView:
        approval = Approval.model_validate_json(approval.model_dump_json())
        view = self.status(campaign_id)
        request = view.requests.get(approval.request_id)
        decision = self._require(
            view,
            Action.REJECT_CAMPAIGN,
            self._context(
                view,
                approval_present=True,
                approval_matches=bool(
                    request
                    and request.action == Action.REJECT_CAMPAIGN
                    and request.reason == reason
                    and approval_matches(approval, request)
                    and self._request_current(view, request)
                    and not any(a.request_id == request.id for a in view.approvals.values())
                ),
            ),
        )
        evidence = self._evidence(
            campaign_id,
            Action.REJECT_CAMPAIGN,
            decision,
            related=(approval.id,),
            note=f"Administrative closure, no financial conclusion: {reason}",
        )
        self._append(
            view,
            [approval, evidence, self._transition(view.campaign, CampaignState.REJECTED, evidence)],
        )
        return self.status(campaign_id)

    def register_experiment(self, experiment: Experiment) -> Experiment:
        experiment = Experiment.model_validate_json(experiment.model_dump_json())
        view = self.status(experiment.campaign_id)
        existing = view.experiments.get(experiment.id)
        if existing:
            if existing != experiment:
                raise ValueError("Experiment ID reuse with different content is forbidden")
            # Idempotent lookup does not create a new trial or alter terminal state.
            return existing
        decision = self._require(
            view,
            Action.REGISTER_EXPERIMENT,
            self._experiment_context(view, experiment),
        )
        self._append(
            view,
            [
                experiment,
                self._evidence(
                    experiment.campaign_id,
                    Action.REGISTER_EXPERIMENT,
                    decision,
                    related=(experiment.id,),
                ),
            ],
        )
        return experiment

    def record_outcome(self, outcome: ExperimentOutcome) -> None:
        outcome = ExperimentOutcome.model_validate_json(outcome.model_dump_json())
        view = self.status(outcome.campaign_id)
        decision = self._require(view, Action.RECORD_OUTCOME, self._context(view))
        self._append(
            view,
            [
                outcome,
                self._evidence(
                    outcome.campaign_id,
                    Action.RECORD_OUTCOME,
                    decision,
                    related=(outcome.id,),
                ),
            ],
        )

    def correct_evidence(self, correction: EvidenceRecord) -> None:
        correction = EvidenceRecord.model_validate_json(correction.model_dump_json())
        view = self.status(correction.campaign_id)
        if not correction.supersedes or correction.action != Action.RECORD_CORRECTION:
            raise ValueError("Corrections require RECORD_CORRECTION and a superseded evidence ID")
        self._require(view, Action.RECORD_CORRECTION, self._context(view))
        self._append(view, [correction])

    def invalidate(self, violation: EvidenceRecord) -> CampaignView:
        violation = EvidenceRecord.model_validate_json(violation.model_dump_json())
        view = self.status(violation.campaign_id)
        if violation.action != Action.INVALIDATE or not violation.artifact_digests:
            raise ValueError("Invalidation requires violation artifact digests")
        decision = self._require(
            view,
            Action.INVALIDATE,
            self._context(
                view,
                actual_violation=violation.actual_violation,
            ),
        )
        evidence = violation.model_copy(update={"decision": decision})
        self._append(
            view, [evidence, self._transition(view.campaign, CampaignState.INVALID, evidence)]
        )
        return self.status(violation.campaign_id)
