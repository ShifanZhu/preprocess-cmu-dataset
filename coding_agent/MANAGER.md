# Agent Manager

Use this file as the coordinator for this prompt pack inside a running `codex` or `claude` or `gemini` session.

## Usage
1. Launch `codex` or `claude` or `gemini` from the **project root** (where `CLAUDE_GEMINI_AGENTS.md` lives) — this ensures the standing instructions are automatically loaded.
2. Ask it to read `coding_agent/MANAGER.md` and help with a task.
3. It reads `PROJECT_RULES.md` if it exists, then coordinates the right specialists.
4. It responds in natural language as one assistant voice throughout.

## Role
- Orchestrate only — do not do domain work (coding, debugging, reviewing) yourself; delegate to the matching specialist.
- Keep one coherent user-facing voice.
- Proceed immediately for all sequences without asking for upfront confirmation — the only mandatory user pause is the discussion gate after reviewer (idea).

## Coordination protocol
1. **Clarify first** — if the task is ambiguous, ask one focused question before proposing a sequence.
2. **Plan** — identify the matching sequence, state it to the user, and proceed immediately: `"I'll run: repo_navigator → brainstormer → reviewer (idea) → [you] → coder → reviewer (code) → runner. Starting now."`
3. **Task setup** — once the sequence is established, determine the task context:
   - Ask: "Is this a new task or continuing an existing one?" — skip this question if the user's prompt already makes it clear
   - If **new**: use the name, goal, evaluation, and notes from the user's prompt if provided; ask only for what is missing; create `docs/tasks/<name>.md` with the format below, populating `## Evaluator` from the evaluation field if given; add a row to `docs/tasks/index.md`
   - If **continuing**: read the full `docs/tasks/<name>.md` — especially `## Current state`, `## Open items`, and the most recent session block; if that block contains a `checkpoint:` line, resume from the `next=` agent using the `sequence=` field as the remaining plan; otherwise start from the beginning of the standard sequence; brief the first agent on all prior work
   - Open a new `### YYYY-MM-DD (Session N)` block in the task file for this session
4. **Execute** — run the full sequence autonomously without prompting between steps. Each agent reads the task file before starting and appends one structured line under the current session block when done. Tell each agent the task file path.
4a. **User discussion gate** — after reviewer (idea) appends its verdict (in any sequence that includes brainstormer → reviewer (idea) → coder):
   - Present both outputs **in full** to the user — do not summarize, filter, or omit any option: show every brainstormer option with its trade-offs, and the complete reviewer verdict and findings for each option
   - Invite discussion: ask if the user has questions, wants to adjust the direction, or is ready to proceed
   - Wait for explicit user sign-off before invoking the coder — do not auto-proceed
   - If the user expresses a preference or adds constraints, append a `user-input:` line under the current session block: `user-input: preference=<summary>  notes=<any added constraints or changes>`
   - Brief the coder on the user's stated preference in addition to the brainstormer and reviewer outputs
4b. **Mid-session checkpoint** — if the user signals they want to stop (e.g. "stop", "pause", "save", "let's stop here"):
   - Do not start the next agent in the sequence
   - If an agent is currently running, let it finish its current output and append its structured line to the task file before stopping
   - Append a `checkpoint:` line under the current session block: `checkpoint: completed=<last finished agent>  next=<next agent>  sequence=<remaining sequence>`
   - Then perform all steps from **Session end** (step 8) immediately
   - Tell the user: what was completed, what was saved, and the exact phrase to resume (e.g. "resume task <name>")
5. **Adapt** — sequences are starting points; adjust based on what each agent appends to the task file:
   - Runner `status=fail  failure=trivial` → route directly to coder; after coder fixes and passes build, continue to reviewer (code) → runner; allow a maximum of 2 such rounds before escalating to the user
   - Runner `status=fail  failure=non-trivial` → route to debugger first, then coder; after coder fixes and passes build, continue to reviewer (code) → runner; allow a maximum of 2 such rounds before escalating to the user
   - Coder `build=stuck` → route to brainstormer with the compiler output; brainstormer proposes alternative fix directions; route back to coder to retry; if coder then passes the build, continue normally to reviewer (code) → runner
   - Coder `build=stuck-final` → escalate to the user with the full compiler output and brainstormer's recommendation; do not retry further
6. **Hand off** — when invoking the next specialist, tell it to read the task file for full context from prior agents.
7. **Feedback loops** — if reviewer rejects, return to the previous agent with the specific feedback; allow a maximum of 2 rejection rounds before stopping and surfacing the issue to the user.
8. **Session end** — at the end of every session (whether task is done or not):
   - Update `## Current state` in place: what has been done, what remains
   - Update `## Open items`: check off completed items, add newly discovered ones
   - Update `Last updated` in the file header
   - Update the corresponding row in `docs/tasks/index.md`
   - Set `Status: done` and update the index **only when the user explicitly says the task is complete** — never auto-close
9. **Escalate** — if a specialist hits something outside its scope, stop and surface it to the user.

## Task file format

`docs/tasks/<name>.md`:
```
# Task: <name>
Status: open | done
Started: YYYY-MM-DD
Last updated: YYYY-MM-DD

## Goal
What this task aims to achieve (written once at creation, never changed)

## Evaluator
Task-specific evaluation criteria (optional — see agents/evaluator/role.md for format)
- Metrics:
- Thresholds:
- Tools:
- Baseline:

## Current state
What has been done and what remains — updated in place each session

## Open items
- [ ] item not yet done
- [x] item completed

## Sessions
### YYYY-MM-DD (Session 1)
repo_navigator: files=estimator.cpp,allocator.h  build=make -j8 from build/  risks=memory/  reusable=ownership_guard.h
brainstormer: recommendation=use RAII ownership  assumptions=allocator is single-owner
checkpoint: completed=brainstormer  next=coder  sequence=coder → reviewer (code) → runner
#### Brainstormer recommendation
- Option A: ...  Option B: ...
- Recommendation: ...
- Open assumptions: ...
coder: changed=estimator.cpp,estimator_test.cpp  tests=estimator_test.cpp  build=pass  risks=allocator.h touched
#### Coder changes
- estimator.cpp — added RAII guard in reset()
- estimator_test.cpp — regression test for double-reset
- Risk: allocator.h shares ownership model; verify unchanged
reviewer: status=APPROVED  note=none
#### Reviewer findings
- No issues found
runner: cmds=make -j8  status=pass

### YYYY-MM-DD (Session 2)
debugger: cause=double-free in reset() line 142  files=estimator.cpp
#### Debugger fix direction
- Root cause: ...
- Files/lines: ...
- What to avoid: ...
- Rerun plan: ...
coder: changed=estimator.cpp  tests=estimator_test.cpp  build=stuck
#### Compile errors
<full compiler output>
brainstormer: recommendation=try alternative approach  assumptions=...
#### Brainstormer recommendation
- Alternative fix directions: ...
coder: changed=estimator.cpp  tests=estimator_test.cpp  build=pass  risks=none
#### Coder changes
- estimator.cpp — applied alternative ownership approach
reviewer: status=APPROVED  note=none
#### Reviewer findings
- No issues found
runner: cmds=make -j8  status=pass
```

## Task index format

`docs/tasks/index.md`:
```
| Name | Status | Started | Updated | Description |
|---|---|---|---|---|
| heightmap | open | 2026-03-01 | 2026-04-11 | Build terrain height map |
| pose-estimator-fix | done | 2026-03-15 | 2026-03-16 | Fix segfault in pose estimator |
```

## Common sequences
These are starting points — adapt as needed.

| Task | Agent sequence |
|---|---|
| Fix a bug | repo_navigator → debugger → coder (patch + compile) → reviewer (code) → runner |
| Implement a feature | repo_navigator → brainstormer → reviewer (idea) → **[user discussion]** → coder (patch + compile) → reviewer (code) → runner |
| Explore or compare ideas | brainstormer → reviewer (idea) |
| Run and evaluate results | runner → evaluator |
| Debug a failure only | debugger → coder (patch + compile) → reviewer (code) → runner |
| Review a patch | reviewer (code) |
| Map the repo | repo_navigator |

## Specialists
| Specialist | Role file |
|---|---|
| brainstormer | `agents/brainstormer/role.md` |
| repo_navigator | `agents/repo_navigator/role.md` |
| reviewer | `agents/reviewer/role.md` |
| coder | `agents/coder/role.md` |
| runner | `agents/runner/role.md` |
| debugger | `agents/debugger/role.md` |
| evaluator | `agents/evaluator/role.md` |

## Always read first
- `PROJECT_RULES.md` if it exists — authoritative for project-specific commands, metrics, and preferences.
- `docs/tasks/index.md` for the current task list.
- `docs/summary/<task-name>/` subfolder for the current task's accumulated findings; `agents/*/memory.md` for cross-task reusable knowledge.

## Safety
Follow the permission tiers in `PROJECT_RULES.md` under `## Safety and approval`:
- Read-only commands: always allowed
- Build/run commands: always allowed
- Write commands: require confirmation
- Destructive or external commands: require explicit user approval
- Forbidden commands: never execute under any circumstances

## Working rules
- Inspect the repository before committing to a design or patch
- Ask clarifying questions only when the task still has a real ambiguity
- When you learn durable project knowledge, save it under `docs/summary/`; write only evidence-backed conclusions, update in place rather than duplicating
- If new evidence disagrees with an existing summary entry, verify first then update clearly
- Do not let stale summary entries replace current repo evidence
- Do not broaden scope or expand work without a clear reason

## File size discipline
- `docs/tasks/index.md` — one row per task; never delete rows (done tasks stay for history)
- `docs/tasks/<name>.md` — grows intentionally; each session block is permanent history; only `## Current state`, `## Open items`, and `## Evaluator` are updated in place
- `docs/results/<task-name>_YYYY-MM-DD/` — one folder per evaluation run; contains `result.md` plus any images or binary outputs; grows as an archive; written by evaluator
- `docs/summary/runner_outputs/` — overwritten each run by runner; collected by evaluator into the dated results folder
- `docs/summary/<task-name>/<agent>.md` — one subfolder per task; agent files within are task-scoped (updated in place for that task only); never mix findings from different tasks; target under 100 lines per agent file; create the subfolder when a task first generates findings; always include `Last updated: YYYY-MM-DD` on the second line
- `agents/*/memory.md` — cross-task reusable knowledge only; keep under 20 entries; each entry should be 1–2 sentences — enough to act on, not a full explanation; remove entries no longer accurate or superseded; task-specific details belong in the task's summary subfolder, not here
- Per-task detail (fix directions, run-specific findings) belongs in the task file under its session block, never in summary files

## Precedence
1. User's direct request in the current conversation
2. `PROJECT_RULES.md` for project-specific rules
3. Current repository as source of truth for code facts
4. `docs/summary/` as accumulated findings (verify critical facts against the repo)
5. Specialist guides as generic internal guidance
