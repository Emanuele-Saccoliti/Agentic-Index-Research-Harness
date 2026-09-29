# Research campaigns

Each campaign receives an immutable identifier and its own directory.

Suggested layout:

```text
research/campaigns/CAMP-001/
  preregistration.md
  hypotheses/
  approvals/
  specs/
  experiments/
  falsification/
  audit/
  decision/
```

Do not create a campaign directory by hand once the Campaign Controller exists. Use the CLI so the creation event and identifiers enter the registry.

Until P1 is implemented, this directory is informational only.
