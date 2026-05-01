# CI System Guide

This document describes the CI/CD system for this repository and how it
integrates with the [stranske/Workflows](https://github.com/stranske/Workflows)
repository for reusable automation.

## Table of Contents

1. [Overview](#overview)
2. [Workflows Repository Capabilities](#workflows-repository-capabilities)
3. [Local CI Configuration](#local-ci-configuration)
4. [Agent Automation System](#agent-automation-system)
5. [Troubleshooting](#troubleshooting)
6. [Quick Reference](#quick-reference)

---

## Overview

This repository uses a **hybrid CI approach**:

- **Local jobs**: Domain-specific validation for this project
- **Reusable workflows**: Standard CI from stranske/Workflows

```
┌─────────────────────────────────────────────────────────────┐
│                     This Repository                          │
│                    .github/workflows/ci.yml                  │
├─────────────────────────────────────────────────────────────┤
│  Local Jobs                │  Reusable Workflows            │
│  ─────────────────         │  ────────────────────────────  │
│  • Project-specific        │  • python-ci                   │
│    validation              │    (reusable-10-ci-python.yml) │
│  • Custom linting          │  • node-ci                     │
│                            │    (reusable-11-ci-node.yml)   │
├─────────────────────────────────────────────────────────────┤
│                           Gate                               │
│              Aggregates all job results                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Workflows Repository Capabilities

The [stranske/Workflows](https://github.com/stranske/Workflows) repository
provides:

### Reusable CI Workflows

| Workflow | Purpose | When to Use |
|----------|---------|-------------|
| `reusable-10-ci-python.yml` | Python lint (ruff), type check (mypy), test (pytest), coverage | Python projects with pyproject.toml |
| `reusable-11-ci-node.yml` | Node.js lint, format, type check, test | Node.js/TypeScript projects |
| `reusable-12-ci-docker.yml` | Docker build + smoke test | Projects with Dockerfile |
| `reusable-18-autofix.yml` | Automated code formatting fixes | All projects (via autofix label) |

### Agent Automation System

The Workflows repo includes a sophisticated agent automation system:

| Component | Purpose |
|-----------|---------|
| **Agents 63 Issue Intake** | Converts labeled issues into agent work items |
| **Agents 70 Orchestrator** | Central control for readiness, bootstrap, keepalive |
| **Agents 71-73 Codex Belt** | Dispatcher → Worker → Conveyor pipeline for PRs |
| **Keepalive System** | Monitors stalled agent PRs and nudges them |
| **Autofix** | Automatic formatting fixes on PRs |

### Key Features

- **Readiness probes**: Validates agent availability before work
- **Bootstrap**: Creates branches and PRs from labeled issues
- **Keepalive**: Monitors agent PRs and posts reminder comments
- **Conveyor**: Auto-merges successful PRs and cleans up
- **Watchdog**: Detects stalled automation

---

## Local CI Configuration

### Gate Workflow

The `pr-00-gate.yml` workflow aggregates all CI results for branch protection:

```yaml
# Triggered by: push to main, pull_request
# Required status: Gate / gate
```

If your repository has a custom Gate (not using `reusable-10-ci-python.yml`),
it will be specific to your project's needs and is **not synced** automatically.

### Branch Protection

Branch protection on `main` typically requires:
- `Gate / gate` status to succeed
- At least one approving review
- Force pushes blocked to preserve CI integrity

### Adding New Local Jobs

To add a domain-specific job:

1. Edit `.github/workflows/ci.yml` (or create a new workflow file)
2. Add your job with appropriate triggers
3. Include the job in the Gate aggregation (if using custom Gate)

### Cross-repo smoke gate

The `.github/workflows/cross-repo-smoke.yml` workflow gates the planner-side
contract with `stranske/Travel-Plan-Permission`. On every PR and on push to
`main` it:

1. Checks out trip-planner (PR head) into `trip-planner/`.
2. Checks out `stranske/Travel-Plan-Permission` at a pinned ref into
   `Travel-Plan-Permission/` beside the trip-planner checkout.
3. Installs both repos' dev extras and the trip-planner frontend deps.
4. Runs `python scripts/check_full_product_verification.py --live-tpp required`
   with `TPP_REPO_PATH=../Travel-Plan-Permission`, matching the local sibling
   checkout contract used by `make full-product-check`. A green run proves the
   live cross-repo handshake (planner → local TPP subprocess) is intact.

The pinned TPP ref is configurable via a single workflow-level env var:

```yaml
env:
  TPP_PINNED_REF: <40-char SHA>
```

CI logs print both `TPP_PINNED_REF` and the resolved SHA so the actually
checked-out commit is easy to verify.

When this workflow runs through `workflow_call`, the optional `CROSS_REPO_TOKEN`
secret is preferred for the pinned TPP checkout and falls back to `github.token`.
Callers should pass it with `secrets: inherit` when the default token cannot read
the pinned repo or ref.

#### Bumping the pin

The pin is intentionally manual so a TPP-side breakage cannot land green by
racing with `Travel-Plan-Permission@main`. Bump procedure:

1. Open a paired PR on `stranske/Travel-Plan-Permission` that bumps that
   repo's `TRIP_PLANNER_PINNED_REF` to the trip-planner SHA you intend to
   publish.
2. In this repo, bump `TPP_PINNED_REF` in
   `.github/workflows/cross-repo-smoke.yml` to the latest known-good TPP
   `main` SHA.
3. Land the two PRs together; both `cross-repo-smoke` jobs should be green
   on the paired branches before merge.

#### Required-check on `main`

The `cross-repo-smoke.yml` workflow exposes a `workflow_call` trigger and is
called from `pr-00-gate.yml` as the `cross-repo-smoke` job. The gate's
`summary` job declares `needs: [python-ci, runtime-ci, cross-repo-smoke]`, so
a failure in the cross-repo smoke check propagates to the `Gate / gate` commit
status and blocks merge.

Since `Gate / gate` is the required status check on `main`, no additional
branch-protection configuration is needed for day-to-day use. If a repo admin
wants the raw `cross-repo-full-product` job to appear as a named required
check in addition to the gate, they can add it in Settings → Branches →
Branch protection rule for `main` → "Require status checks to pass" after the
first green run. That toggle cannot be set from a workflow file.

---

## Agent Automation System

### Using Agent Labels

See [docs/LABELS.md](LABELS.md) for the complete label reference.

Quick start:

1. **Create an agent task**: Use the "Agent Task" issue template
2. **Add the label**: Apply `agent:codex` label to trigger automation
3. **Monitor progress**: Watch the linked PR for agent activity
4. **Intervene if needed**: Check for `agent:needs-attention` label

### Agent Workflow

```
Issue created → agent:codex label added
                      ↓
          Issue Intake validates
                      ↓
        Bootstrap creates branch + PR
                      ↓
         Agent works on the code
                      ↓
            CI runs on changes
                      ↓
    ┌─────────────────┴─────────────────┐
    │                                    │
 CI passes                          CI fails
    │                                    │
Conveyor merges               Keepalive nudges agent
```

---

## Troubleshooting

### CI is Failing

1. **Check the Actions tab**: Click on the failing workflow run
2. **Look at job logs**: Expand the failed job to see error details
3. **Try autofix**: Add the `autofix` label to attempt automatic fixes
4. **Check branch protection**: Ensure your branch is up to date with main

### Agent Not Responding

1. **Check issue labels**: Ensure `agent:codex` is present
2. **Look for attention label**: `agent:needs-attention` pauses processing
3. **Check PR status**: The agent works through the linked PR
4. **View keepalive comments**: These indicate agent activity status

### Autofix Not Running

1. **PR must not be a draft**: Convert to ready for review
2. **Must be same-repo PR**: Forks cannot trigger autofix
3. **Remove and re-add label**: Labels only trigger once per addition

### Workflow Sync Issues

Consumer repo workflows are synced from the Workflows repository. If you see
unexpected behavior:

1. **Check sync status**: Look at recent "Sync Consumer Repos" workflow runs
2. **Compare versions**: Check if your workflows match the templates
3. **Check drift guard**: Review "Health 68 Consumer Sync Drift Check" results
4. **Report issues**: File an issue in stranske/Workflows

**Note:** Workflows-Integration-Tests uses its own template set and is validated
by a separate integration sync check in the Workflows repo.

---

## Quick Reference

### Important Files

| Path | Purpose |
|------|---------|
| `.github/workflows/` | All workflow files |
| `.github/ISSUE_TEMPLATE/` | Issue templates including Agent Task |
| `.github/codex/` | Agent configuration |
| `docs/LABELS.md` | Label definitions and triggers |
| `docs/AGENT_ISSUE_FORMAT.md` | How to format issues for agents |

### Key Labels

| Label | Effect |
|-------|--------|
| `autofix` | Triggers automatic code formatting |
| `autofix:clean` | Aggressive autofix mode |
| `agent:codex` | Assigns Codex agent to issue |
| `agent:needs-attention` | Pauses agent, needs human help |

### Helpful Links

- [Workflows Repository](https://github.com/stranske/Workflows)
- [SETUP_CHECKLIST.md](https://github.com/stranske/Workflows/blob/main/docs/templates/SETUP_CHECKLIST.md) - Consumer repo setup guide
- [CONSUMER_REPO_MAINTENANCE.md](https://github.com/stranske/Workflows/blob/main/docs/ops/CONSUMER_REPO_MAINTENANCE.md) - Debugging and maintenance

---

*This document is synced from the Workflows repository.*
*Source of truth: stranske/Workflows*
