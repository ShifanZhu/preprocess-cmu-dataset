# Portable Coding Agent Prompt Pack

A lightweight prompt pack you copy into any project and use from a running `claude` or `codex` session. The manager coordinates specialist agents, confirms a plan with you, then executes autonomously — stopping for your input at key decision points.

**Important:** Claude Code acts strictly as a coordinator. It does not read source files, search the codebase, write code, or make design decisions on its own. All domain work is delegated to the matching specialist. This is enforced by `CLAUDE_GEMINI_AGENTS.md` at the project root.

## Setup (once per project)

1. Copy this folder into the root of your target project.
2. Copy `CLAUDE_GEMINI_AGENTS.md` (from this pack) into the **project root** — Claude Code loads it automatically at every session start and enforces the coordination protocol.
3. Open `claude` or `codex` from the **project root**.
4. Run the repo mapper to discover the build system, entry points, and key files:
   ```
   Read coding_agent/MANAGER.md and map the repo
   ```
   This populates `docs/summary/repo_navigator.md` and tells you what to put in the next two steps.
5. Fill in `PROJECT_RULES.md` — repository constraints, test/static check/benchmark commands, and safety rules.
6. Fill in `agents/runner/role.md` under `## Commands` with your build and run commands.
7. Fill in `agents/evaluator/role.md` under `## Evaluation` with your metrics, thresholds, and baseline.
2. Copy `CLAUDE_GEMINI_AGENTS.md` (from this pack) into the **project root** — Claude Code loads it automatically at every session start and enforces the coordination protocol.
3. Open `claude` or `codex` from the **project root**.
4. Run the repo mapper to discover the build system, entry points, and key files:
   ```
   Read coding_agent/MANAGER.md and map the repo
   ```
   This populates `docs/summary/repo_navigator.md` and tells you what to put in the next two steps.
5. Fill in `PROJECT_RULES.md` — repository constraints, test/static check/benchmark commands, and safety rules.
6. Fill in `agents/runner/role.md` under `## Commands` with your build and run commands.
7. Fill in `agents/evaluator/role.md` under `## Evaluation` with your metrics, thresholds, and baseline.

## Starting a session

Open `claude` or `codex` from the **project root**. Use the template that matches your situation:
Open `claude` or `codex` from the **project root**. Use the template that matches your situation:

**New task:**
```
You are a coordinator. Follow CLAUDE_GEMINI_AGENTS.md strictly: do not read source files, search the codebase, write code, or make design decisions yourself — delegate everything to the matching specialist.

Read coding_agent/MANAGER.md and start a new task:
- Name: <short-slug>
- Goal: <what you want to achieve>
- Evaluation: <metric and threshold, e.g. "RMSE < 0.05 m" or "all tests pass">
- Notes: <constraints, known risks, or starting point if any>
```

Example:
```
You are a coordinator. Follow CLAUDE_GEMINI_AGENTS.md strictly: do not read source files, search the codebase, write code, or make design decisions yourself — delegate everything to the matching specialist.

Read coding_agent/MANAGER.md and start a new task:
- Name: height-map
- Goal: build accurate height map using current pose and depth data, centered around the robot with a 2m×2m window
- Evaluation: qualitative — save height map images as <timestamp>.png for manual review
- Notes: existing code in Systems/MCSystem/Observers/HeightMapGen may be useful; check before writing anything new


You are a coordinator. Follow GEMINI.md strictly: do not read source files, search the codebase, write code, or make design decisions yourself — delegate everything to the matching specialist.

Read coding_agent/MANAGER.md and start a new task:
- Name: semantic-map
- Goal: based on the already logic of building heightmap, we want to extend the color of height map. Now the color represents the height, I want to have another options to make the color represent the semantic label. The color can come from the color of the semantic image where you can find at data_path_/segmentation
- Evaluation: maintain a color for each semantic class
- Notes: current HeightMapBuilder module works well, so do not modify the mapping logic, just modify the map point paint.
```

**Continue an existing task:**
```
You are a coordinator. Follow CLAUDE_GEMINI_AGENTS.md strictly: do not read source files, search the codebase, write code, or make design decisions yourself — delegate everything to the matching specialist.

Read coding_agent/MANAGER.md and continue the <name> task.
This session: <what specifically to work on or what has changed>
```

**Save progress and stop mid-session:**
```
Save and stop here.
```
The manager will flush the current agent's output, record a checkpoint, and tell you the exact prompt to resume.

**Resume from a checkpoint:**
```
You are a coordinator. Follow CLAUDE_GEMINI_AGENTS.md strictly: do not read source files, search the codebase, write code, or make design decisions yourself — delegate everything to the matching specialist.

Read coding_agent/MANAGER.md and continue the <name> task.
```
The manager reads the checkpoint line in the task file and resumes from exactly where you left off.

**Explore or discuss (no code changes):**
```
You are a coordinator. Follow CLAUDE_GEMINI_AGENTS.md strictly: do not read source files, search the codebase, write code, or make design decisions yourself — delegate everything to the matching specialist.

Read coding_agent/MANAGER.md and <map the repo / review this patch / explore options for X>
```

**Tips:**
- `Evaluation` is optional but highly recommended for tasks with measurable outcomes — it is used by the evaluator agent and avoids ambiguity about what "done" means
- `Notes` is optional — use it to flag known constraints, risky areas, or prior context the agents should know
- For continuation sessions, describe what to focus on this session — the agent reads prior history automatically but a focused hint helps it prioritize

## How a feature implementation works

For any task that involves implementing something new, the sequence is:

```
repo_navigator → brainstormer → reviewer (idea) → [you] → coder → reviewer (code) → runner
```

1. **repo_navigator** maps relevant files, build commands, and — importantly — existing reusable components (utilities, base classes, helpers) the other agents must consider before writing anything new.
2. **brainstormer** proposes **2–4 concrete options** with explicit trade-offs, always including a "reuse/extend existing X" option when one exists. It only proposes from-scratch work when nothing in the repo can serve the need, and states why.
3. **reviewer (idea)** evaluates all options for feasibility, structural fit (correct module/layer/directory), and whether any option reimplements something the repo already provides.
4. **You** — the manager presents all brainstormer options and reviewer findings **in full**, then waits for your input. You discuss, ask questions, or indicate a preferred direction before the coder starts.
5. **coder** implements the agreed approach — checking reusable components again before writing new code.
6. **reviewer (code)** verifies correctness, structure, and test coverage.
7. **runner** executes the build and tests.
- For continuation sessions, describe what to focus on this session — the agent reads prior history automatically but a focused hint helps it prioritize

## How a feature implementation works

For any task that involves implementing something new, the sequence is:

```
repo_navigator → brainstormer → reviewer (idea) → [you] → coder → reviewer (code) → runner
```

1. **repo_navigator** maps relevant files, build commands, and — importantly — existing reusable components (utilities, base classes, helpers) the other agents must consider before writing anything new.
2. **brainstormer** proposes **2–4 concrete options** with explicit trade-offs, always including a "reuse/extend existing X" option when one exists. It only proposes from-scratch work when nothing in the repo can serve the need, and states why.
3. **reviewer (idea)** evaluates all options for feasibility, structural fit (correct module/layer/directory), and whether any option reimplements something the repo already provides.
4. **You** — the manager presents all brainstormer options and reviewer findings **in full**, then waits for your input. You discuss, ask questions, or indicate a preferred direction before the coder starts.
5. **coder** implements the agreed approach — checking reusable components again before writing new code.
6. **reviewer (code)** verifies correctness, structure, and test coverage.
7. **runner** executes the build and tests.

## Common task patterns

| You say | Sequence |
|---|---|
| "Fix this bug: …" | repo_navigator → debugger → coder → reviewer (code) → runner |
| "Implement …" | repo_navigator → brainstormer → reviewer (idea) → **[you]** → coder → reviewer (code) → runner |
| "Explore options for …" | repo_navigator → brainstormer → reviewer (idea) → **[you]** |
| "Fix this bug: …" | repo_navigator → debugger → coder → reviewer (code) → runner |
| "Implement …" | repo_navigator → brainstormer → reviewer (idea) → **[you]** → coder → reviewer (code) → runner |
| "Explore options for …" | repo_navigator → brainstormer → reviewer (idea) → **[you]** |
| "Run and evaluate the results" | runner → evaluator |
| "Review this patch" | reviewer (code) |
| "Continue the <name> task" | manager reads `docs/tasks/<name>.md` → resumes from current state or checkpoint |
| "Continue the <name> task" | manager reads `docs/tasks/<name>.md` → resumes from current state or checkpoint |

## Automated runs with /loop and /schedule

Both `/loop` and `/schedule` start cold — no memory of prior conversations. Bootstrap them by pointing at the files that contain your accumulated knowledge.

**Bootstrap template (add to the start of any /loop or /schedule prompt):**
```
You are a coordinator. Follow CLAUDE_GEMINI_AGENTS.md strictly.
Read coding_agent/MANAGER.md, PROJECT_RULES.md, and docs/tasks/<name>.md before doing anything.
```

### /loop — iterative work within a session

`/loop` re-runs a prompt on a timed or self-paced interval inside your current Claude Code session. Use it when you want active tuning with fast feedback.

**Example 1 — Parameter sweep (height map resolution)**
```
/loop 3m
You are a coordinator. Follow CLAUDE_GEMINI_AGENTS.md strictly.
Read coding_agent/MANAGER.md, PROJECT_RULES.md, and docs/tasks/height-map.md.
Continue the height-map task: try resolution=0.05 → 0.025 → 0.01 m, run the evaluator on each,
and append results to docs/tasks/height-map.md. Stop when RMSE stops improving.
```

**Example 2 — Research loop (explore until an option is approved)**
```
/loop
You are a coordinator. Follow CLAUDE_GEMINI_AGENTS.md strictly.
Read coding_agent/MANAGER.md and docs/tasks/elevation-map.md.
Run: brainstormer → reviewer (idea). Each iteration refine the best option based on the
reviewer's objections and append findings to docs/tasks/elevation-map.md.
Stop when reviewer returns APPROVED.
```

**Example 3 — Repair loop (fix, build, check, repeat)**
```
/loop
You are a coordinator. Follow CLAUDE_GEMINI_AGENTS.md strictly.
Read coding_agent/MANAGER.md, PROJECT_RULES.md, and docs/tasks/consistent-map.md.
Run: coder → reviewer (code) → runner. If runner returns status=fail, loop back to debugger → coder.
Stop when runner returns status=pass.
```

**Example 4 — Auto parameter (automatic parameter tuning)**
```
/loop

Read coding_agent/MANAGER.md, PROJECT_RULES.md, and start a event-auto-parameter-tuning-vector task.

For this task, modify the parameters in vector_state_estimation_config.yaml that are marked [auto-tune] in the end, do not modify other parameters. Update the marked parameters in yaml in an intelligent manner, do not simply brute force all parameter space.

Run runner on all vector dataset sequence by modifying data_path, and then run evaluator agent to get rmse accuracy. Remember to run evaluation on all trajectories and then get the average rmse as final results when evaluate parameter sets.

Append results to the task file.

Save files or scripts into a separate folder in coding_agent/docs/tasks when necessary.

This is a event camera based state estimation and feature initialization is without depth data.
```

### /schedule — unattended runs on a cron schedule

`/schedule` fires a remote agent on a cron schedule, independent of your session. Use it for overnight experiments, periodic sweeps, or evaluation runs you don't want to babysit.

**Example 4 — Nightly evaluation run**
```
/schedule "0 2 * * *"
You are a coordinator. Follow CLAUDE_GEMINI_AGENTS.md strictly.
Read coding_agent/MANAGER.md, PROJECT_RULES.md, and docs/tasks/height-map.md.
Run: runner → evaluator. Append results to docs/tasks/height-map.md and
docs/summary/height-map/evaluator.md. Save output images to docs/results/height-map_<date>/.
```

**Example 5 — Automated parameter search (every 30 min until threshold met)**
```
/schedule "*/30 * * * *"
You are a coordinator. Follow CLAUDE_GEMINI_AGENTS.md strictly.
Read coding_agent/MANAGER.md, PROJECT_RULES.md, and docs/tasks/elevation-map.md.
Read docs/summary/elevation-map/evaluator.md to see what parameters have already been tried.
Pick the next untried combination, run the evaluator, and append the result.
If RMSE < 0.03 m is achieved, update ## Current state with "threshold met" and stop scheduling.
```

**Example 6 — Weekly research digest**
```
/schedule "0 9 * * 1"
You are a coordinator. Follow CLAUDE_GEMINI_AGENTS.md strictly.
Read coding_agent/MANAGER.md and all files under docs/tasks/ and docs/summary/.
Run: brainstormer. Identify open tasks stuck for 7+ days and propose next steps for each.
Append a "weekly-digest: <date>" block to docs/tasks/index.md.
```

### Key rules

- Always include the bootstrap template so the agent reads your accumulated knowledge before acting
- `/loop` agents share your session context across iterations; `/schedule` agents each start fresh — the task file is the **only shared memory** between schedule runs
- For parameter searches: the evaluator's rolling history in `docs/summary/<task>/evaluator.md` prevents re-running already-tried combinations
- Automated agents follow the same safety rules as interactive sessions (`PROJECT_RULES.md` § Safety)

## File layout

```
CLAUDE_GEMINI_AGENTS.md                     standing instructions — lives at project root, loaded automatically
coding_agent/
  MANAGER.md                  coordinator — read this to start every session
  PROJECT_RULES.md            project-specific constraints, commands, and safety rules
  agents/
    <name>/
      role.md                 role definition, focus, output, and rules
      memory.md               persistent notes written only by this agent
  docs/
    tasks/
      index.md                registry of all tasks: name, status, dates, description
      <task-name>.md          one file per named task — open until explicitly closed
    results/
      <task-name>_YYYY-MM-DD/
        result.md             evaluation summary: criteria, output summary, verdict
        *.png / *.jpg         images and binary outputs produced by the runner
    summary/
      <agent>.md              accumulated findings per agent across sessions
      runner_output.md        latest runner text output (read by evaluator)
      runner_outputs/         latest images and binary outputs (read by evaluator)
      evaluator.md            rolling last-10-run history with trend summary
CLAUDE_GEMINI_AGENTS.md                     standing instructions — lives at project root, loaded automatically
coding_agent/
  MANAGER.md                  coordinator — read this to start every session
  PROJECT_RULES.md            project-specific constraints, commands, and safety rules
  agents/
    <name>/
      role.md                 role definition, focus, output, and rules
      memory.md               persistent notes written only by this agent
  docs/
    tasks/
      index.md                registry of all tasks: name, status, dates, description
      <task-name>.md          one file per named task — open until explicitly closed
    results/
      <task-name>_YYYY-MM-DD/
        result.md             evaluation summary: criteria, output summary, verdict
        *.png / *.jpg         images and binary outputs produced by the runner
    summary/
      <agent>.md              accumulated findings per agent across sessions
      runner_output.md        latest runner text output (read by evaluator)
      runner_outputs/         latest images and binary outputs (read by evaluator)
      evaluator.md            rolling last-10-run history with trend summary
```

## How tasks and knowledge persist

**Tasks** live in `docs/tasks/<name>.md` — one file per named task, open until you explicitly close it.

```
## Goal          written once at creation, never changed
## Evaluator     task-specific evaluation criteria — updated in place (optional)
## Current state updated in place each session — what's done, what remains
## Open items    checkbox list, updated in place each session
## Sessions
  ### YYYY-MM-DD (Session 1)   permanent — one line per agent, never edited
  ### YYYY-MM-DD (Session 2)   new block added each session
```

A mid-session stop appends a `checkpoint:` line recording the last completed agent and the remaining sequence, so resumption is unambiguous.
A mid-session stop appends a `checkpoint:` line recording the last completed agent and the remaining sequence, so resumption is unambiguous.

**Knowledge** is maintained in three layers:

| Layer | File | What it holds | Lifetime |
|---|---|---|---|
| Task history | `docs/tasks/<name>.md` `## Sessions` | Every agent action across all sessions | Permanent per task |
| Agent summaries | `docs/summary/<agent>.md` | Durable patterns learned across all tasks | Updated in place, never per-task detail |
| Agent memory | `agents/<name>/memory.md` | Hardest-won insights, max 20 entries | Updated in place |

## Specialists

| Agent | Purpose |
|---|---|
| repo_navigator | map the repo, surface reusable components, identify build/test commands |
| brainstormer | propose 2–4 concrete options with trade-offs; reuse-first |
| reviewer | idea review (structural fit, reuse check) or code review (APPROVED / REJECTED) |
| coder | implement the patch and write tests; reuse-first |
| repo_navigator | map the repo, surface reusable components, identify build/test commands |
| brainstormer | propose 2–4 concrete options with trade-offs; reuse-first |
| reviewer | idea review (structural fit, reuse check) or code review (APPROVED / REJECTED) |
| coder | implement the patch and write tests; reuse-first |
| runner | execute build, test, static check, or benchmark commands |
| debugger | root-cause failures |
| evaluator | measure runner output against metrics and record verdict |

## What Claude Code will NOT do

Even if you ask directly, Claude Code will not:
- Read or search source files to perform analysis (that is `repo_navigator`'s job)
- Propose implementation options or architectural decisions (that is `brainstormer`'s job)
- Write, edit, or delete source files (that is `coder`'s job)
- Run build or test commands on its own initiative (that is `runner`'s job)

If you observe it doing any of the above, it is violating the protocol. Check that `CLAUDE_GEMINI_AGENTS.md` is present at the project root and that you launched Claude Code from the project root.

## What you maintain

- **`CLAUDE_GEMINI_AGENTS.md`** (project root) — update if the coordination rules need to change
- **`CLAUDE_GEMINI_AGENTS.md`** (project root) — update if the coordination rules need to change
- **`PROJECT_RULES.md`** — update when constraints, commands, or safety rules change
- **`agents/runner/role.md`** — update `## Commands` when build or run commands change
- **`agents/evaluator/role.md`** — update `## Evaluation` when metrics or thresholds change
- **`docs/tasks/`** — written and maintained by agents automatically; you only provide task names and declare tasks done
- Everything under `docs/summary/` is written and maintained by agents automatically
