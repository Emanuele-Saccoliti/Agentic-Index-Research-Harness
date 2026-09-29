# Research protocol

## Unit of work

A **campaign** answers one preregistered research question. A campaign may contain several hypotheses, but only approved hypotheses receive an experiment budget.

## Lifecycle

### 1. Planning

The Coordinator creates the campaign and freezes the broad question, scope and required artifacts.

### 2. Proposal

The Researcher proposes two or three hypotheses. Each hypothesis must state:

- economic mechanism;
- expected benefit;
- closest fair benchmark;
- permitted primitives;
- parameters and ranges;
- failure conditions;
- falsification tests;
- estimated experiment count.

No candidate backtest is run during proposal generation.

### 3. Human approval

The human selects, rejects or requests revision. Approval freezes:

- hypothesis version and digest;
- parameter ranges;
- experiment budget;
- benchmark set;
- development and final periods;
- validation gates;
- permitted files and primitives.

### 4. Implementation

The Strategy Engineer implements the approved specification. A new Python primitive requires a separate approval and test task.

### 5. Development evaluation

The deterministic engine executes only registered configurations within the approved budget. Every attempted configuration enters the trial ledger.

### 6. Falsification

The Falsifier performs the preregistered adversarial checks without editing the strategy or choosing new parameters.

### 7. Audit

The Auditor verifies provenance, policy compliance, trial completeness, calculations and claims.

### 8. Decision

The controller records one terminal outcome:

- `ACCEPTED`: every mandatory gate passes;
- `REJECTED`: one or more decisive gates fail;
- `INCONCLUSIVE`: evidence is insufficient or unstable;
- `INVALID`: protocol, policy or provenance was violated.

## Experiment budget

The budget counts every configuration evaluated on candidate results, including:

- parameter combinations;
- strategy variants;
- overlays switched on or off;
- alternative universe rules;
- changes inspired by an observed result.

Diagnostic runs that inspect only data integrity or fixed benchmarks are labeled separately and may not contain candidate logic.

## Holdout discipline

- Final evaluation requires a separate approval.
- The final period is evaluated once for an approved frozen candidate.
- After results are visible, the period is marked `SPENT`.
- Results from a spent period can be reported but cannot justify a modification.
- A modified strategy starts a new campaign and waits for future unseen data for a new final claim.

This is auditable governance, not cryptographic secrecy. The repository must state that limitation.

## Parallelism

Parallel work is allowed for independent reading, benchmark diagnostics and proposal drafting. Mutations of campaign state, approvals, registries and shared strategy specifications are sequential.

## Mandatory artifacts

A complete campaign contains:

1. preregistration;
2. hypothesis cards;
3. approval record;
4. strategy specification;
5. experiment manifests;
6. trial ledger;
7. falsification report;
8. audit report;
9. decision report.
