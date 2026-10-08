---
name: counter-attack
description: Supervise every coding agent running in a Herdr pane and counterargue its finished work until the result is defined and committed cleanly. A background watcher wakes this session when an agent settles; a fresh reviewer verifies the agent's work with tools and the supervisor sends back only material, falsifiable challenges, then asks the agent to commit, amending when safe instead of stacking commits. Bounded per pane and per run; runs attended or unattended overnight and leaves a morning report. Use when the user invokes /counter-attack, asks to supervise, audit, or challenge the agents in their Herdr panes, or wants agents kept honest while they sleep.
allowed-tools: Read Write Edit Agent AskUserQuestion Bash(herdr agent list:*) Bash(herdr agent get:*) Bash(herdr agent read:*) Bash(herdr agent explain:*) Bash(herdr agent prompt:*) Bash(jq:*)
disable-model-invocation: true
metadata:
  author: Luis Quiñones
  version: "1.0.0"
  category: agents
---

# Counter-Attack

This session is the supervisor. It never does the targets' work, never
reviews inline, and never holds review content in its context. It discovers
targets, spawns reviewers, gates and sends prompts, and keeps state on disk.
The back-and-forth with each target (counter, answer, re-review) is the
whole dialectic; reviewers do not run socratic-debate.

Scripts live in `scripts/` next to this file. Call them by absolute path.

## Step 0: Guards

- `test "${HERDR_ENV:-}" = 1`, else say this session is not inside Herdr and
  stop.
- If your instructions start with `COUNTER-ATTACK REVIEW`, you are a
  reviewer. Follow [references/reviewer.md](references/reviewer.md) instead.

## Step 1: Start or Resume

State root: `${XDG_STATE_HOME:-$HOME/.local/state}/counter-attack/`. If a
run there has `"status": "running"` and its `watch.lock` PID is alive, say
so and resume it; ask nothing.

## Step 2: Ask

Run `scripts/targets.sh`. Zero targets: say so and stop. Then one
AskUserQuestion call with two questions:

1. **Targets**: `All agent panes (<n>)` | `Pick specific panes`.
2. **Mode**:
   - `I'm here`: skip the pane the user has focused; run until told to stop.
   - `Going to sleep`: include every target; stop 8 hours from now.
   - `Audit only`: review and report; never prompt a target.

On `Pick specific panes`, ask a second multi-select question listing live
targets as `<pane> <kind>: <title>` (four at most; the user types other pane
IDs under Other).

## Step 3: Initialize

Create `<root>/<YYYYmmdd-HHMM>/STATE.json`:

```json
{
  "run_id": "", "skill": "<absolute path of this SKILL.md>", "status": "running",
  "mode": "awake|sleep|audit", "deadline_epoch": 0, "only": [],
  "caps": {"rounds": 2, "global": 0}, "prompts_sent": 0,
  "panes": {
    "<pane-id>": {"kind": "", "task": "", "leaf": "", "seq": 0, "rounds": 0,
                  "finalized": false, "status": "watching", "last_review": "",
                  "last_verdict": ""}
  }
}
```

`global` = `max(4, 3 x targets)`; it covers counter and finalize prompts.
Pane `status`: `watching | countered | finalizing | settled | awaiting-human
| capped | delivery-unknown | gone`. Every decision on a pane writes its
current `leaf`, including skips; the watcher only wakes for a leaf it has
not seen.

Sleep mode: an unattended permission prompt blocks the whole night. While
the user is still here, run `scripts/can-inject.sh` on one target and arm
the watcher once. If either asked for approval, tell the user to allow it
permanently or relaunch with `claude --permission-mode bypassPermissions`.

Tell the user, in one line, what runs and until when. Then Step 4 at once:
already-settled work is reviewable now.

## Step 4: Cycle

Run on start and on every watcher exit. First re-read STATE.json and this
file; after compaction they are the only memory.

1. `scripts/targets.sh`. Mark missing panes `gone`. Ready panes: status
   `idle` or `done`, `pending_bg` 0, leaf differs from STATE, not focused in
   awake mode, inside `only` when set.
2. Spawn one fresh reviewer per ready pane with the Agent tool, at most 2 at
   a time, from [references/reviewer.md](references/reviewer.md). Record
   the pane's `seq` first. A reviewer replies with one path; read only the
   first line (`VERDICT ...`). Panes at `capped` get one last review in
   audit mode, then are only recorded.
3. Act on the verdict:

| Verdict | Action |
|---|---|
| `counter` | send `COUNTER.md`; rounds +1; status `countered` |
| `finalize` | send `FINALIZE.md`; `finalized` true; status `finalizing` |
| `settled` | status `settled` |
| `awaiting-human` | status `awaiting-human`; send nothing |
| `in-progress` | status `watching`; send nothing |
| `audit` | record; send nothing |

4. Send only when: mode is not `audit`, `prompts_sent` < global, and
   `scripts/can-inject.sh <pane> <seq>` prints `ok`. A `counter` also needs
   rounds < 2; at the cap the reviewer's next verdict can only be
   `finalize`, `settled`, or `audit`, and the pane ends `capped` if open
   claims remain.

   ```bash
   herdr agent prompt <pane> "$(cat <review-dir>/<FILE>.md)" --wait --timeout 15000
   ```

   `agent_prompt_stalled` or `timeout`: status `delivery-unknown`; never
   resend. `agent_blocked` or a gate `no`: keep status, record the leaf.
5. Write STATE.json, arm the watcher (Step 5), end the turn with one line:
   cycle, prompts sent, panes per status.

A pane's task ends at `settled` or `capped`. New work in that pane after
that is a new task only if the user typed it; reset `rounds` and
`finalized` then.

Never answer approval dialogs, send keys, focus, start, split, or close
anything in a target pane. Blocked targets go in the report only.

## Step 5: Watch

```text
Bash(run_in_background: true, timeout: 7200000):
  <skill-dir>/scripts/watch.sh <state-dir> 45 6600
```

Its exit re-invokes this session. `WATCH ready [...]`: Step 4. `WATCH
heartbeat`: re-arm, end the turn. `WATCH deadline`: Step 6. `WATCH
already-running`: nothing. Never poll in the foreground, never arm two.

## Step 6: Stop

On deadline, user stop, or every target `gone`:

1. Set `"status": "stopped"`; kill the PID in `watch.lock` if alive.
2. Write `<state-dir>/MORNING.md` from [references/report.md](references/report.md).
3. Print its summary table and path.

## Why the Rules

- A `herdr agent prompt` lands as a typed human turn with full user
  authority under the target's permission mode. Every prompt carries a scope
  fence, and the caps bound the run: at most 2 counter rounds and 1
  finalize per task.
- The injected prompt becomes the target's last prompt, so task identity
  comes from the last turn the user typed, never from ours.
- `done` can hide background work that will wake the target by itself;
  `targets.sh` counts unmatched background task IDs in the transcript.
- Panes can share a cwd and a branch; work and commits are attributed from
  the pane's own transcript, and amending is allowed only when nothing else
  sits on top of the task commit.
