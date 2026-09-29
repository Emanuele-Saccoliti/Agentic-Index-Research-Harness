from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier

import pytest
from conftest import NOW, human_decision

from etf_harness.controller.service import ActionRefused, CampaignController
from etf_harness.controller.states import CampaignState as S
from etf_harness.policy.actions import Action, Outcome
from etf_harness.registry.base import RegistryError, RevisionConflict
from etf_harness.registry.sqlite import SQLiteRegistry
from etf_harness.schemas.domain import (
    Approval,
    Budget,
    Campaign,
    EvidenceRecord,
    Experiment,
    ExperimentOutcome,
    Hypothesis,
    PolicyDecision,
    Transition,
    digest,
)


def test_pending_approval_is_parked_not_invalid(
    service: CampaignController,
    campaign: Campaign,
    hypothesis: Hypothesis,
    experiment: Experiment,
) -> None:
    service.create(campaign)
    service.propose(hypothesis)
    view = service.status(campaign.id)
    assert view.campaign.state == S.AWAITING_APPROVAL
    assert any(e.decision.outcome == Outcome.REQUIRE_APPROVAL for e in view.evidence.values())
    with pytest.raises(ActionRefused):
        service.register_experiment(experiment)
    assert service.status(campaign.id).campaign.state == S.AWAITING_APPROVAL
    assert service.status(campaign.id).used_budget(hypothesis.id) == (0, 0)


def test_failed_and_abandoned_trials_count_and_duplicates_do_not(
    approved: tuple[CampaignController, Approval],
    experiment: Experiment,
) -> None:
    service, _ = approved
    service.register_experiment(experiment)
    service.register_experiment(experiment)
    service.record_outcome(
        ExperimentOutcome(
            id="OUT-1",
            campaign_id=experiment.campaign_id,
            created_at=NOW,
            experiment_id=experiment.id,
            status="FAILED",
            output_digests={},
            note="Synthetic failure",
        )
    )
    second = experiment.model_copy(update={"id": "EXP-2", "robustness": True})
    service.register_experiment(second)
    service.record_outcome(
        ExperimentOutcome(
            id="OUT-2",
            campaign_id=experiment.campaign_id,
            created_at=NOW,
            experiment_id=second.id,
            status="ABANDONED",
            output_digests={},
            note="Synthetic abandonment",
        )
    )
    with pytest.raises(ActionRefused, match="budget"):
        service.register_experiment(experiment.model_copy(update={"id": "EXP-3"}))
    view = service.status(experiment.campaign_id)
    assert view.used_budget(experiment.hypothesis_id) == (2, 1)
    assert len(view.outcomes) == 2
    assert view.campaign.state == S.APPROVED


@pytest.mark.parametrize(
    "parameters", [{"window": 4}, {"window": True}, {}, {"window": 2, "other": 1}]
)
def test_out_of_scope_parameters_never_reserve_budget(
    approved: tuple[CampaignController, Approval],
    experiment: Experiment,
    parameters: dict,
) -> None:
    service, _ = approved
    with pytest.raises(ActionRefused, match="parameter_scope"):
        service.register_experiment(experiment.model_copy(update={"parameters": parameters}))
    assert service.status(experiment.campaign_id).used_budget(experiment.hypothesis_id) == (0, 0)


def test_robustness_cap_does_not_bypass_candidate_ceiling(
    approved: tuple[CampaignController, Approval],
    experiment: Experiment,
) -> None:
    service, _ = approved
    service.register_experiment(experiment.model_copy(update={"robustness": True}))
    with pytest.raises(ActionRefused, match="budget"):
        service.register_experiment(
            experiment.model_copy(update={"id": "EXP-2", "robustness": True})
        )
    assert service.status(experiment.campaign_id).used_budget(experiment.hypothesis_id) == (1, 1)


def test_mismatched_provenance_is_not_registered(
    approved: tuple[CampaignController, Approval],
    experiment: Experiment,
) -> None:
    service, _ = approved
    altered = experiment.model_copy(
        update={
            "provenance": experiment.provenance.model_copy(
                update={"locked_config_digest": digest("changed")},
            )
        }
    )
    with pytest.raises(ActionRefused, match="provenance"):
        service.register_experiment(altered)


def test_reopen_reproduces_state_and_budget(
    approved: tuple[CampaignController, Approval],
    experiment: Experiment,
    tmp_path: Path,
) -> None:
    service, _ = approved
    service.register_experiment(experiment)
    before = service.status(experiment.campaign_id)
    with SQLiteRegistry(tmp_path / "registry.sqlite3") as reopened:
        assert CampaignController(reopened).status(experiment.campaign_id) == before


def test_closure_is_separately_approved_and_terminal(
    approved: tuple[CampaignController, Approval],
    experiment: Experiment,
) -> None:
    service, approval = approved
    request = service.request_rejection(approval.campaign_id, "End synthetic demonstration")
    assert service.status(approval.campaign_id).campaign.state == S.APPROVED
    view = service.reject(
        approval.campaign_id, human_decision(request, "APR-CLOSE"), request.reason
    )
    assert view.campaign.state == S.REJECTED
    with pytest.raises(ActionRefused, match="terminal"):
        service.register_experiment(experiment)
    assert service.status(approval.campaign_id).campaign.state == S.REJECTED


def test_new_proposal_invalidates_old_closure_scope(
    service: CampaignController,
    campaign: Campaign,
    hypothesis: Hypothesis,
) -> None:
    service.create(campaign)
    request = service.request_rejection(campaign.id, "close")
    service.propose(hypothesis)
    with pytest.raises(ActionRefused, match="approval_mismatch"):
        service.reject(campaign.id, human_decision(request), "close")


def test_correction_preserves_original_and_cannot_refund_budget(
    approved: tuple[CampaignController, Approval],
    experiment: Experiment,
) -> None:
    service, _ = approved
    service.register_experiment(experiment)
    view = service.status(experiment.campaign_id)
    original = next(iter(view.evidence.values()))
    correction = EvidenceRecord(
        id="CORRECTION",
        campaign_id=experiment.campaign_id,
        created_at=NOW,
        action=Action.RECORD_CORRECTION,
        decision=PolicyDecision(
            outcome=Outcome.ALLOW,
            rule="annotation",
            reason="Correct explanatory text only",
        ),
        supersedes=original.id,
        note="Synthetic addendum",
    )
    service.correct_evidence(correction)
    after = service.status(experiment.campaign_id)
    assert after.evidence[original.id] == original
    assert after.evidence[correction.id] == correction
    assert after.used_budget(experiment.hypothesis_id) == (1, 0)


def test_actual_violation_can_invalidate(approved: tuple[CampaignController, Approval]) -> None:
    service, approval = approved
    violation = EvidenceRecord(
        id="VIOLATION",
        campaign_id=approval.campaign_id,
        created_at=NOW,
        action=Action.INVALIDATE,
        actual_violation=True,
        decision=PolicyDecision(
            outcome=Outcome.ALLOW, rule="violation", reason="Synthetic violation"
        ),
        artifact_digests={"violation report": digest("synthetic unregistered attempt")},
        note="Synthetic test of an actual protocol violation",
    )
    assert service.invalidate(violation).campaign.state == S.INVALID


def test_replay_rejects_outcome_after_terminal(
    approved: tuple[CampaignController, Approval],
    experiment: Experiment,
) -> None:
    service, approval = approved
    service.register_experiment(experiment)
    request = service.request_rejection(approval.campaign_id, "close")
    view = service.reject(approval.campaign_id, human_decision(request, "APR-CLOSE"), "close")
    service.registry.append(
        view.campaign.id,
        view.revision,
        [
            ExperimentOutcome(
                id="LATE",
                campaign_id=view.campaign.id,
                created_at=NOW,
                experiment_id=experiment.id,
                status="FAILED",
                output_digests={},
                note="Malformed externally appended history",
            )
        ],
    )
    with pytest.raises(RegistryError, match="Terminal"):
        service.status(view.campaign.id)


def test_replay_rejects_invalidation_without_artifact_evidence(
    approved: tuple[CampaignController, Approval],
) -> None:
    service, approval = approved
    view = service.status(approval.campaign_id)
    evidence = EvidenceRecord(
        id="BAD-EVIDENCE",
        campaign_id=view.campaign.id,
        created_at=NOW,
        action=Action.INVALIDATE,
        actual_violation=True,
        note="Unsupported assertion",
        decision=PolicyDecision(outcome=Outcome.ALLOW, rule="violation", reason="Unsupported"),
    )
    service.registry.append(
        view.campaign.id,
        view.revision,
        [
            evidence,
            Transition(
                id="BAD-TRANSITION",
                campaign_id=view.campaign.id,
                created_at=NOW,
                source=S.APPROVED,
                target=S.INVALID,
                evidence_id=evidence.id,
            ),
        ],
    )
    with pytest.raises(RegistryError, match="evidence"):
        service.status(view.campaign.id)


def test_concurrent_reservations_cannot_overdraw(
    tmp_path: Path,
    service: CampaignController,
    campaign: Campaign,
    hypothesis: Hypothesis,
    experiment: Experiment,
) -> None:
    service.create(campaign)
    request = service.propose(hypothesis.model_copy(update={"budget": Budget(candidate=1)}))
    service.approve(human_decision(request))
    barrier = Barrier(2)

    class SynchronizedRegistry(SQLiteRegistry):
        def append(self, campaign_id, expected_revision, records):
            barrier.wait(timeout=10)
            return super().append(campaign_id, expected_revision, records)

    def reserve(identifier: str) -> str:
        with SynchronizedRegistry(tmp_path / "registry.sqlite3") as store:
            controller = CampaignController(store, clock=lambda: datetime.now(UTC))
            try:
                controller.register_experiment(experiment.model_copy(update={"id": identifier}))
                return "reserved"
            except RevisionConflict:
                return "stale"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(reserve, ["EXP-A", "EXP-B"]))
    assert sorted(results) == ["reserved", "stale"]
    assert service.status(campaign.id).used_budget(hypothesis.id) == (1, 0)
