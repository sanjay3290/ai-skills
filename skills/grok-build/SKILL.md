---
name: grok-build
description: "Orchestrate coding work by delegating well-specified implementation tasks to xAI's Grok Build CLI (grok) running headlessly, while the coding assistant plans, writes the task specs, reviews every diff, and owns the result. Use when user says: 'use grok', 'grok build', 'delegate to grok', 'have grok implement', 'have grok execute', 'have grok build', 'send to grok', 'execute this plan with grok'. Executes a Markdown implementation plan task-by-task, or ad-hoc tasks with an inline spec."
license: Apache-2.0
metadata:
  author: sanjay3290
  version: "1.0"
---

# Grok Build Orchestration

The coding assistant is the orchestrator: it plans, writes self-contained task specs,
dispatches them to Grok Build headlessly, reviews every diff, and owns the final result.
Grok is the fast, cheap executor. Full CLI details and verified behaviors: `references/cli.md`.

## When to delegate vs keep with the orchestrator

| Delegate to Grok | Keep with the orchestrator |
|---|---|
| Plan tasks with clear acceptance criteria | Ambiguous requirements, architecture decisions |
| Boilerplate, scaffolding, CRUD | Deep cross-file debugging |
| Mechanical refactors | Security-sensitive code |
| Test writing from clear specs | Anything touching production infrastructure |
| UI components from mockups/specs | Tasks where writing the spec ≈ doing the work |

When in doubt, keep it with the orchestrator.

## Session preflight (once, before the first dispatch)

1. `grok update --check --json` — if `updateAvailable` is true, run `grok update` and
   confirm with `grok --version`.
2. `grok models` — if it errors or reports logged out, STOP and ask the user to run
   `grok login`.

## Per-task loop (sequential — the default)

1. **Spec.** Write a self-contained task file (template below) to a temp directory
   OUTSIDE the target repo — the harness scratchpad if one is available, else the OS
   temp dir. Never write it inside the target repo. Grok has zero conversation context:
   no one-liner prompts, ever.
   - POSIX: `mkdir -p "${TMPDIR:-/tmp}/grok-specs"`, then write `task.md` there.
   - Windows (PowerShell): `New-Item -ItemType Directory -Force "$env:TEMP\grok-specs"`,
     then write `task.md` there.
2. **Clean state.** No uncommitted *source* changes — commit or stash first, so the
   post-run diff is exactly Grok's work. Ignore build artifacts (`__pycache__`, `dist/`,
   etc.); if they show in `git status`, they're usually just un-gitignored, not your
   concern. Never dispatch on a dirty source tree.
3. **Dispatch.**

   POSIX:

   ```bash
   grok --prompt-file <task-file> \
     --output-format json \
     --always-approve \
     --max-turns 30 \
     --cwd <repo>
   ```

   Windows (PowerShell) — backtick line-continuation:

   ```powershell
   grok --prompt-file <task-file> `
     --output-format json `
     --always-approve `
     --max-turns 30 `
     --cwd <repo>
   ```

   Parse the JSON output and save `sessionId`. (`--always-approve` is required for
   headless runs — `--permission-mode acceptEdits` silently cancels edits with no
   interactive approver. See `references/cli.md`.) For a high-stakes task, add `--check`
   so Grok self-verifies before you review; skip it otherwise (it ~doubles latency).
4. **Review gate — non-negotiable.**
   - Read the diff yourself (`git diff -- <files from the spec>` to skip artifact noise):
     does it do the task, only the task, and match repo conventions?
   - Run the acceptance commands from the spec.
   - **Pass** → commit with a clear message following the repo's convention → next task.
   - **Fail** → fix-up: `grok --resume <sessionId> -p "<specific feedback>"
     --always-approve --output-format json`. **Max 2 fix-up rounds.** Still failing →
     revert Grok's changes (`git checkout -- .`; `git clean -fd` for new files), do the
     task yourself, and tell the user Grok couldn't complete it.

## Task spec template

```markdown
# Task: <one-line title>

## Context
- Repo: <path> — <one line on what the project is>
- Conventions: <test runner, formatter, a good example file to imitate>

## Files
- Modify: <path>
- Create: <path>

## Task
<precise description of the change>

## Constraints
- Do not modify any files other than those listed above.
- <other constraints>

## Acceptance criteria
- `<exact command>` <expected result>
```

## Executing a Markdown implementation plan

- One plan task per dispatch, in order.
- Check off the plan's task checkboxes (`- [ ]` → `- [x]`) as each task lands and passes
  the review gate.
- If the plan explicitly marks tasks as independent, see Parallel dispatch below;
  otherwise stay sequential.

## Parallel dispatch (opt-in exception, not the default)

Only when a plan explicitly marks tasks independent: dispatch each with
`--worktree=<task-slug>`, run concurrently, then review and merge one worktree at a
time through the same review gate. Merge conflicts usually eat the savings — prefer
sequential.

## Failure handling

| Failure | Action |
|---|---|
| `stopReason: "Cancelled"`, empty text, no diff | Missing `--always-approve` — retry with it |
| CLI error / timeout | Retry once; then do the task yourself and note the fallback |
| Auth expired | Stop; ask the user to run `grok login` |
| 2 fix-up rounds exhausted | Revert Grok's diff; the orchestrator finishes the task |
| Dirty tree at dispatch | Refuse; commit/stash first |

## Models

Default `grok-4.5`. Add `-m grok-composer-2.5-fast` only for trivial mechanical tasks.
