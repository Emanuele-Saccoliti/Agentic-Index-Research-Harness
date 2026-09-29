from collections.abc import Iterator
from datetime import UTC, datetime
from itertools import count
from pathlib import Path

import pytest

from etf_harness.controller.service import CampaignController
from etf_harness.registry.sqlite import SQLiteRegistry
from etf_harness.schemas.domain import (
    Approval,
    ApprovalRequest,
    Budget,
    Campaign,
    Experiment,
    Hypothesis,
    ParameterBound,
    Provenance,
    digest,
)

NOW = datetime(2026, 9, 29, tzinfo=UTC)


@pytest.fixture
def campaign() -> Campaign:
    return Campaign(
        id="CAMP-SYNTHETIC",
        campaign_id="CAMP-SYNTHETIC",
        created_at=NOW,
        question="Synthetic controller acceptance, no financial hypothesis",
        scope="P1 control-plane fixture only",
        synthetic=True,
        locked_config_digest=digest("synthetic configuration"),
        preregistration_digest=digest("synthetic preregistration"),
        required_artifacts=("synthetic decision",),
    )


@pytest.fixture
def hypothesis(campaign: Campaign) -> Hypothesis:
    return Hypothesis(
        id="HYP-SYNTHETIC",
        campaign_id=campaign.id,
        created_at=NOW,
        statement="Synthetic bounded configuration",
        mechanism="No financial mechanism",
        expected_benefit="Exercise deterministic authorization",
        fair_benchmark="not applicable",
        allowed_paths=("synthetic/spec.json",),
        allowed_primitives=("synthetic",),
        parameters={"window": ParameterBound(minimum=1, maximum=3)},
        budget=Budget(candidate=2, robustness=1),
        failure_conditions=("Policy bypass",),
        falsification_tests=("Out-of-range request",),
    )


@pytest.fixture
def registry(tmp_path: Path) -> Iterator[SQLiteRegistry]:
    with SQLiteRegistry(tmp_path / "registry.sqlite3") as store:
        yield store


@pytest.fixture
def service(registry: SQLiteRegistry) -> CampaignController:
    sequence = count()
    return CampaignController(
        registry, clock=lambda: NOW, new_id=lambda: f"record-{next(sequence)}"
    )


def human_decision(request: ApprovalRequest, identifier: str = "APR-SYNTHETIC") -> Approval:
    """Synthetic test attestation; never a real human research authorization."""
    return Approval(
        id=identifier,
        campaign_id=request.campaign_id,
        created_at=request.created_at,
        request_id=request.id,
        request_digest=request.request_digest,
        decision="APPROVED",
        decided_by="Synthetic human fixture",
        authority="human",
        source_reference="pytest synthetic fixture; not research approval",
        synthetic=True,
    )


@pytest.fixture
def approved(
    service: CampaignController,
    campaign: Campaign,
    hypothesis: Hypothesis,
) -> tuple[CampaignController, Approval]:
    service.create(campaign)
    request = service.propose(hypothesis)
    approval = human_decision(request)
    service.approve(approval)
    return service, approval


@pytest.fixture
def experiment(campaign: Campaign, hypothesis: Hypothesis) -> Experiment:
    return Experiment(
        id="EXP-SYNTHETIC",
        campaign_id=campaign.id,
        created_at=NOW,
        hypothesis_id=hypothesis.id,
        approval_id="APR-SYNTHETIC",
        parameters={"window": 2},
        strategy_spec_digest=digest("synthetic spec"),
        synthetic=True,
        provenance=Provenance(
            git_commit="a" * 40,
            dirty_diff_digest=digest("synthetic diff"),
            data_manifest_digest=digest("no data"),
            locked_config_digest=campaign.locked_config_digest,
            instruction_digests={
                "AGENTS.md": digest("synthetic instructions"),
                "role": digest("synthetic role"),
                "preregistration": campaign.preregistration_digest,
                "locked_config": campaign.locked_config_digest,
                "task_packet": digest("synthetic task"),
            },
            command="synthetic registration only",
            environment={"python": "synthetic"},
            seeds=(0,),
        ),
    )
