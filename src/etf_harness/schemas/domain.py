"""Versioned artifacts. All hashes use canonical UTF-8 JSON, never Python repr."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from etf_harness.controller.states import CampaignState
from etf_harness.policy.actions import Action, Outcome

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Text = Annotated[str, Field(min_length=1, pattern=r"\S")]
Scalar = StrictBool | StrictInt | StrictFloat | StrictStr


def canonical_json(value: BaseModel | JsonValue) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def digest(value: BaseModel | JsonValue) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class Artifact(Model):
    schema_version: Literal[1] = 1
    id: Identifier
    campaign_id: Identifier
    created_at: AwareDatetime

    @field_validator("created_at")
    @classmethod
    def utc_only(cls, value: datetime) -> datetime:
        offset = value.utcoffset()
        if offset is None or offset.total_seconds() != 0:
            raise ValueError("Artifact timestamps must use UTC")
        return value


class Budget(Model):
    candidate: Annotated[StrictInt, Field(ge=1)]
    robustness: Annotated[StrictInt, Field(ge=0)] = 0

    @model_validator(mode="after")
    def check_subset(self) -> Self:
        if self.robustness > self.candidate:
            raise ValueError("Robustness cap cannot exceed the total candidate ceiling")
        return self


class ParameterBound(Model):
    """An inclusive numeric interval, or an exact typed categorical set."""

    minimum: StrictInt | StrictFloat | None = None
    maximum: StrictInt | StrictFloat | None = None
    choices: tuple[Scalar, ...] = ()

    @model_validator(mode="after")
    def check_shape(self) -> Self:
        if self.choices:
            if self.minimum is not None or self.maximum is not None:
                raise ValueError("Use either choices or a numeric interval")
        elif self.minimum is None or self.maximum is None or self.minimum > self.maximum:
            raise ValueError("An ordered, closed numeric interval is required")
        return self

    def contains(self, value: Scalar) -> bool:
        if self.choices:
            return any(type(value) is type(choice) and value == choice for choice in self.choices)
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and self.minimum is not None
            and self.maximum is not None
            and self.minimum <= value <= self.maximum
        )


class Campaign(Artifact):
    kind: Literal["campaign"] = "campaign"
    question: Text
    scope: Text
    synthetic: StrictBool
    locked_config_digest: Digest
    preregistration_digest: Digest
    required_artifacts: tuple[Text, ...]
    state: CampaignState = CampaignState.CREATED

    @model_validator(mode="after")
    def check_identity(self) -> Self:
        if self.id != self.campaign_id:
            raise ValueError("Campaign id must equal campaign_id")
        return self


class Hypothesis(Artifact):
    kind: Literal["hypothesis"] = "hypothesis"
    version: Annotated[StrictInt, Field(ge=1)] = 1
    statement: Text
    mechanism: Text
    expected_benefit: Text
    fair_benchmark: Text
    allowed_paths: tuple[Text, ...] = ()
    allowed_primitives: tuple[Text, ...] = ()
    parameters: dict[str, ParameterBound]
    budget: Budget
    failure_conditions: tuple[Text, ...]
    falsification_tests: tuple[Text, ...]


class ApprovalScope(Model):
    campaign_digest: Digest
    hypothesis_digest: Digest | None
    parameter_space_digest: Digest | None
    budget: Budget | None
    locked_config_digest: Digest
    preregistration_digest: Digest
    allowed_paths: tuple[Text, ...] = ()
    allowed_primitives: tuple[Text, ...] = ()
    synthetic: StrictBool


class ApprovalRequest(Artifact):
    kind: Literal["approval_request"] = "approval_request"
    hypothesis_id: Identifier | None
    action: Action
    scope: ApprovalScope
    reason: str = ""

    @property
    def request_digest(self) -> str:
        # Request IDs and creation times identify records, not authorization scope.
        return digest(self.model_dump(mode="json", exclude={"id", "created_at"}))


class Approval(Artifact):
    kind: Literal["approval"] = "approval"
    request_id: Identifier
    request_digest: Digest
    decision: Literal["APPROVED", "REJECTED", "REVISION_REQUIRED"]
    decided_by: Text
    source_reference: Text
    authority: Literal["human"]
    synthetic: StrictBool


class Provenance(Model):
    git_commit: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    dirty_diff_digest: Digest
    data_manifest_digest: Digest
    locked_config_digest: Digest
    instruction_digests: dict[str, Digest]
    command: Text
    environment: dict[str, Text]
    seeds: tuple[StrictInt, ...]

    @model_validator(mode="after")
    def required_provenance(self) -> Self:
        required = {"AGENTS.md", "role", "preregistration", "task_packet", "locked_config"}
        if not required <= self.instruction_digests.keys() or not self.environment:
            raise ValueError("Required instruction and environment provenance is missing")
        return self


class Experiment(Artifact):
    kind: Literal["experiment"] = "experiment"
    hypothesis_id: Identifier
    approval_id: Identifier
    parameters: dict[str, Scalar]
    strategy_spec_digest: Digest
    robustness: StrictBool = False
    synthetic: StrictBool
    provenance: Provenance
    status: Literal["REGISTERED"] = "REGISTERED"


class ExperimentOutcome(Artifact):
    kind: Literal["experiment_outcome"] = "experiment_outcome"
    experiment_id: Identifier
    status: Literal["SUCCEEDED", "FAILED", "ABANDONED"]
    output_digests: dict[str, Digest]
    note: Text


class PolicyDecision(Model):
    outcome: Outcome
    rule: Text
    reason: Text


class EvidenceRecord(Artifact):
    kind: Literal["evidence"] = "evidence"
    action: Action
    decision: PolicyDecision
    related_ids: tuple[Identifier, ...] = ()
    artifact_digests: dict[str, Digest] = Field(default_factory=dict)
    note: Text
    supersedes: Identifier | None = None
    actual_violation: StrictBool = False


class Transition(Artifact):
    kind: Literal["transition"] = "transition"
    source: CampaignState
    target: CampaignState
    evidence_id: Identifier


Record = Annotated[
    Campaign
    | Hypothesis
    | ApprovalRequest
    | Approval
    | Experiment
    | ExperimentOutcome
    | EvidenceRecord
    | Transition,
    Field(discriminator="kind"),
]


class Event(Model):
    schema_version: Literal[1] = 1
    campaign_id: Identifier
    revision: Annotated[StrictInt, Field(ge=1)]
    previous_digest: Digest
    record: Record
    record_digest: Digest
