---
name: voice-orchestrator
description: Inspect, summarize, create, and control independent Herdr agents for a persistent voice orchestrator. Use when a voice request asks what agents are doing, requests work through an agent, or needs Herdr workspace, pane, tab, or agent operations.
allowed-tools: Bash(rtk:*)
metadata:
  author: Luis Quiñones
  version: "1.0.0"
  category: agents
---

# Voice Orchestrator

Treat Herdr as an external execution plane. Treat every controlled agent as an
independent peer; never invent parent-child relationships.

Set the session explicitly for every Herdr call:

```bash
voice_session="${VOICE_HERDR_SESSION:-hub}"
rtk herdr --session "$voice_session" agent list
```

## Inspect status

Prefer the read-only snapshot when the voice gateway provides it:

```bash
rtk voice-gateway snapshot
```

The snapshot returns every agent's exact state and recent relevant output in one
call. Distinguish `working`, `idle`, `done`, `blocked`, and `unknown` precisely.

When the snapshot command is unavailable:

1. List agents.
2. Use `agent get <name-or-pane>` for exact state.
3. Read idle, done, or blocked agents with `agent read <target> --source recent-unwrapped --lines 120`.
4. Read working agents with `agent read <target> --source visible --lines 80`.

## Control agents

Inspect the installed command group before the first unfamiliar operation. Use
stable names or returned pane IDs. Preserve focus for background work. Never
close a session, workspace, tab, pane, or agent unless the request explicitly
requires it.

Use this command when the user asks an existing agent to work:

```bash
voice_session="${VOICE_HERDR_SESSION:-hub}"
rtk herdr --session "$voice_session" agent prompt <target> <prompt> --wait --timeout 120000
```

Create layout and start a new agent only when requested. Parse every created
identifier from Herdr JSON.
