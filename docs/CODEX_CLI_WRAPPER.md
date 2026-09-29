# Optional Codex CLI wrapper

## Status

**Deferred. Do not implement during the initial vertical slice.**

## Purpose

Later, a local wrapper may launch bounded Codex tasks from a scheduler or Python process without integrating an LLM API into the research package.

```text
Python wrapper
  -> Codex CLI (`codex exec`)
      -> repository instructions and task packet
          -> Campaign Controller
```

Codex remains an operator of the Campaign Controller. The wrapper never writes campaign state, runs the backtester directly or promotes results.

## Why defer it

Automating an unstable workflow makes failures faster and harder to inspect. First prove that:

- the interactive campaign lifecycle works;
- task packets are unambiguous;
- controller policies reject unauthorized actions;
- artifacts are machine-validated;
- repeated manual runs produce consistent handoffs.

## Activation criteria

Implementation may begin only after:

1. P1 through P6 are complete;
2. at least one interactive campaign reaches a valid terminal state;
3. every agent role has a stable input and output schema;
4. commands are non-interactive and return meaningful exit codes;
5. controller tests cover approval, budget and protected-surface violations;
6. the human explicitly approves wrapper development.

## Intended interface

The wrapper receives:

- task packet path;
- assigned role;
- campaign and hypothesis identifiers;
- allowed workspace root;
- time and experiment budget;
- expected output schema and path.

It records:

- start and finish timestamps;
- Codex session or thread identifier when available;
- exit status;
- JSONL event log or final-message artifact;
- Git diff digest;
- resulting controller events.

## Illustrative local invocation

Official OpenAI documentation describes `codex exec` as the non-interactive mode for scripts and pipelines. A future wrapper can use an explicit workspace sandbox and machine-readable output, for example:

```bash
cat task-packet.md | codex exec - \
  --sandbox workspace-write \
  --json > artifacts/codex-events.jsonl
```

For a stable final response, the wrapper may use `--output-schema` and `--output-last-message`. Exact flags must be verified against the installed CLI before implementation.

Reference: [OpenAI Codex non-interactive mode](https://developers.openai.com/codex/noninteractive).

## Authentication boundary

For local use, `codex exec` can reuse saved Codex CLI authentication. The wrapper must never copy, log or commit authentication files or tokens.

CI or remote unattended execution has a different credential and threat model and is outside the initial scope.

## Safety requirements

- Use the least permissive sandbox that completes the role.
- Keep the wrapper inside the project root.
- Pass complete task packets rather than assembling shell commands from untrusted text.
- Never use the wrapper to bypass a human approval state.
- Treat nonzero exit, schema failure, timeout or unexpected diff as failure.
- Preserve stdout/stderr and controller evidence without exposing credentials.
- Run mutating roles sequentially.

## Non-goals

- replacing the Campaign Controller;
- autonomous final evaluation;
- automated publication or Git push;
- live trading;
- arbitrary recursive agent spawning;
- API-backed orchestration inside the research engine.
