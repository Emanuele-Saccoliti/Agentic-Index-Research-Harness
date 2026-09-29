# Governance and policy

## Policy outcomes

Every controlled action resolves to:

- `ALLOW` — execute and record;
- `DENY` — refuse with the rule and reason;
- `REQUIRE_APPROVAL` — park the action until a matching approval exists.

## Initial action policy

| Action | Default outcome |
|---|---|
| Read project documentation | ALLOW |
| Read development artifacts | ALLOW |
| Create a hypothesis proposal | ALLOW |
| Approve or reject a hypothesis | REQUIRE_APPROVAL |
| Create a StrategySpec for an approved hypothesis | ALLOW within scope |
| Run a registered development experiment | ALLOW within budget |
| Exceed experiment budget | DENY |
| Use a parameter outside the approved range | DENY |
| Modify locked campaign configuration | DENY |
| Modify benchmark, split, cost or validation logic during a campaign | DENY |
| Add a new Python strategy primitive | REQUIRE_APPROVAL |
| Run the final evaluation | REQUIRE_APPROVAL |
| Edit an existing evidence or trial record | DENY |
| Publish a performance claim | REQUIRE_APPROVAL after audit |

## Approval identity

An approval is bound to the digest of:

- campaign;
- hypothesis;
- permitted parameter space;
- experiment budget;
- relevant locked configuration;
- requested action.

A changed request needs a new approval.

## Append-only records

Campaign events, trials, evidence and decisions are append only. Corrections are new records that reference the superseded record. The implementation must never mutate history in place.

## Invalidating conditions

A run is `INVALID` when any of the following occurs:

- missing or mismatched approval;
- unregistered candidate experiment;
- unauthorized protected-file diff;
- budget overflow;
- parameter outside approved bounds;
- data, config or prompt digest mismatch;
- future data used in a signal;
- benchmark or gate modified after candidate observation;
- missing required artifact;
- reported number does not resolve to a result artifact.

## Role separation

- Researcher proposes but does not implement or evaluate.
- Strategy Engineer implements but does not approve or audit.
- Falsifier tests but does not tune or promote.
- Auditor verifies but does not repair the candidate.
- Coordinator controls handoffs but cannot replace human approval.

The same model may execute multiple roles at different times, but each role receives a separate task packet and writes only its permitted artifacts.

## Prompt and instruction provenance

Hash the effective contents of:

- `AGENTS.md`;
- the assigned role file;
- approved preregistration;
- task packet;
- relevant locked configuration.

Prompt hashes establish identity, not quality. They allow results produced under changed instructions to be distinguished.

## Reporting policy

All numeric tables are rendered from machine-readable result artifacts. Narrative claims cite artifact identifiers. An audit warning remains visible in the final report.

## P1 operational semantics (owner-approved D014–D017)

### Local human decision records

The CLI imports an `Approval` JSON artifact. It records the human decision time in `created_at`, the human's name in `decided_by`, and a traceable authorization reference in `source_reference`. `authority` must be `human`. A pending `ApprovalRequest` is a separate immutable artifact; its decision is appended, never edited in place. Requests may receive `APPROVED`, `REJECTED` or `REVISION_REQUIRED` decisions. A negative hypothesis decision leaves the campaign awaiting a selection or a revised proposal with a new record ID.

The human must inspect the exact request before authorizing it. A Coordinator may import a decision that the human explicitly gave, but cannot supply its own authorization. This is trusted local operator attestation, not authenticated identity or a signature system. A claimed name alone is not proof of a human decision. Test fixtures identify themselves as synthetic and are never research authorizations.

Canonical SHA-256 request identity includes campaign scope, hypothesis identity/content/version, parameter space, budget, locked configuration, preregistration, allowed paths/primitives, synthetic designation and requested action. Campaign state and consumed budget are excluded. Request record IDs and creation times are not part of the request digest, but an approval must reference the exact stored request ID as well. Closure requests additionally bind all current proposals and the closure reason. A changed proposal set or reason requires a new closure decision.

### Refusal, closure and invalidation

Missing authorization parks a request; mismatched authorization, illegal states, exhausted budgets, invalid bounds and protected changes fail closed. A prevented request does not invalidate the campaign. No protected configuration or policy is edited through the controller. A separate approved engineering task is required to change protected surfaces; it does not rewrite an active campaign.

Administrative campaign closure is a separate `reject_campaign` approval. It requires a reason and records `REJECTED` without asserting failed financial gates. A hypothesis approval cannot authorize this action. An `INVALID` transition requires explicit actual-violation evidence with supporting artifact digests. The controller checks evidence structure and references; P1 does not independently establish the truth of an external report.

### Reservations and history

Every registered synthetic attempt reserves one candidate slot. A robustness attempt also reserves one robustness slot. Failed and abandoned registrations remain counted, including conservatively reserved attempts that never execute. Denied preflight requests consume no slots. An exact retry of the same experiment ID/content returns the existing registration; a new ID counts as a new attempt. Budget reservation, trial record and action evidence commit together. Concurrent stale writers fail before any part of their batch commits.

Outcomes and corrections append records referencing existing entries. Corrections add evidence annotations; they cannot replace scope, approvals, trials or budget accounting. History is immutable through the application and ordinary SQL update/delete/replacement statements. A filesystem owner can still replace the database or change its schema. Hash chains detect internal inconsistency, not a fully rewritten history or deletion of its final suffix without an external checkpoint.

P1 is synthetic-only and has no final-evaluation or publication executor. Provenance fields carry typed declared digests; P1 does not read market data or verify those declarations against executed financial artifacts. StrategySpec-to-parameter validation, source-file provenance capture, task ownership and actual research execution remain later work.
