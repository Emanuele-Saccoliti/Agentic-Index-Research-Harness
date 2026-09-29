# Architecture

## Design principle

The Campaign Controller owns the loop. Agents can propose actions and produce artifacts, but only the controller can validate a transition or register an experiment as eligible for promotion.

## Logical layers

```text
Human approval
      |
Codex Coordinator and subagents
      |
Campaign Controller: states, policies, budgets, registry, evidence
      |
Research engine: data, universe, benchmarks, strategies, backtest, validation
      |
Artifacts: manifests, metrics, reports, charts and decisions
```

## Initial interaction flow

```text
Human -> Codex Coordinator -> Codex subagent -> Campaign Controller CLI
```

The Python package never needs to call Codex. Agents invoke deterministic commands and write typed artifacts.

## Future optional flow

```text
Scheduler or local Python wrapper
    -> codex exec
        -> Codex Coordinator task
            -> Campaign Controller CLI
```

This extension must use the same policies and state machine. It cannot gain a direct route to the backtester or registry.

## Campaign states

```text
CREATED
  -> PLANNING
  -> PROPOSED
  -> AWAITING_APPROVAL
  -> APPROVED
  -> IMPLEMENTING
  -> DEVELOPMENT_EVALUATION
  -> FALSIFICATION
  -> AUDIT
  -> ACCEPTED | REJECTED | INCONCLUSIVE | INVALID
```

Terminal states are immutable. Illegal transitions fail closed.

## Planned Python modules

```text
src/etf_harness/
  controller/       state, transitions, approvals and task ownership
  policy/           action catalogue and ALLOW/DENY/REQUIRE_APPROVAL rules
  registry/         append-only campaigns, trials, evidence and provenance
  schemas/          Pydantic domain models
  data/             provider interface, cleaning, cache and manifests
  universe/         sleeves, eligibility and representative selection
  benchmarks/       60/40, equal-sleeve, risk parity and risk-matched controls
  strategies/       validated primitives and approved plugins
  backtest/         portfolio accounting, rebalancing and costs
  validation/       walk-forward, perturbations, bootstrap and gates
  reporting/        artifact-derived tables and reports
  cli/              Typer interface
app/
  streamlit_app.py  read model and approved actions only
```

## Hybrid strategy authoring

Most hypotheses compile from a validated StrategySpec containing:

- universe and sleeve rules;
- signal and estimation windows;
- allocation method;
- overlays;
- weight and risk constraints;
- rebalancing schedule;
- approved parameter ranges.

A hypothesis requiring a new primitive opens a separate engineering change. Existing campaign results remain tied to the previous engine and prompt hashes.

## Evidence granularity

Record evidence at research-action level rather than hashing every shell command. Each valid experiment records:

- campaign and hypothesis identifiers;
- approval identifier;
- Git commit and dirty diff digest;
- data-manifest digest;
- locked-config digest;
- agent-instruction digests;
- executed command;
- environment and dependency versions;
- random seeds;
- output artifact digests;
- state transition and timestamp.

## Inspiration and deliberate differences

The control plane uses explicit state transitions, policy-gated actions, approvals, evidence, critic stages, preregistration and audited reports.

Deliberate differences:

- research campaigns replace point-in-time trading decisions;
- Codex subagents replace in-process LLM calls;
- portfolio experiments replace broker and execution tools;
- declarative strategy specifications reduce arbitrary code generation;
- no C++, MCP, HTTP API or live order path is required initially.

## P1 controller implementation

The owner-approved D014–D017 clarifications supplement the research path above:

- Every nonterminal state may enter `REJECTED` through a separately approved administrative closure. Its evidence explicitly makes no financial conclusion.
- Every nonterminal state may enter `INVALID` on recorded evidence of an actual protocol violation. Preflight refusals leave the state unchanged.
- Terminal states have no outgoing transitions. Subsequent denied requests may append refusal evidence, but cannot change campaign scope, approvals, trials or outcomes.

`schemas` defines versioned Pydantic artifacts; `policy` makes pure decisions; `controller` validates actions and reconstructs campaign state; `registry` persists atomic event batches; `cli` only handles JSON input/output. The SQLite implementation sits behind the `Registry` protocol. It has no update/delete API, rejects SQL replacement of existing records, checks per-campaign sequence/hash chains, and uses expected revisions to reject stale writers. A conflict requires the caller to reload and re-evaluate; there is no blind retry.

P1 represents the full legal research state graph but implements only synthetic planning, proposal, approval, administrative rejection and invalidation. Synthetic experiment registration at `APPROVED` exercises budget controls without claiming that implementation, development evaluation, falsification or audit happened. There is no generic transition command, research executor or path to `ACCEPTED` in P1. Multiple hypotheses may be proposed, but only one selected hypothesis advances in this slice. Later phases must define multiple-hypothesis execution explicitly.

Controller clocks and record-ID factories are injectable. Given the same history and input artifacts, policy, approval digests, state and budget projections are deterministic. Runtime identifiers and timestamps are recorded inputs, not financial calculations.
