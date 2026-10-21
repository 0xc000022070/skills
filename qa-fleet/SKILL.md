---
name: qa-fleet
description: Run a multi-device QA round on a mobile app with one subagent tester per emulator or simulator, driven through the `phone` CLI. Covers sizing the fleet to the host's memory, an isolated QA backend, a restore script that survives host reboots, one charter per tester, scripted cross-device scenes, evidence and resume checkpoints, crash triage, fix verification, a consolidated repro file, teardown, and turning flows that pass into Maestro scripts. Use when asked to QA, bug-bash or dogfood an app across several devices or platforms, before a store release, or to resume or tear down an interrupted QA round.
allowed-tools: Read Grep Glob Edit Write Agent Bash(phone:*)
disable-model-invocation: false
metadata:
  author: Luis Quiñones
  version: "1.0.0"
  category: mobile
---

# QA Fleet

The lead plans, provisions, coordinates and consolidates. Testers drive one
device each and report. Device mechanics (leases, taps, logs, crash buffers,
offline tests) live in `phone-skill`; load it first. Project facts (backend,
build flags, test accounts, test data) live in the project's own skill or
AGENTS.md; read them before planning.

## Step 0: Recursion guard

If your prompt contains `QA-FLEET TESTER`, you are a tester. Do not invoke
this skill. Follow your brief and return your report as your final message.

## Step 1: Size and isolate

- `phone device list` shows what each host may still boot, and
  `phone host budget <host>` its memory budget. Size the fleet to that, not
  to the wish. Tell the user the number and the platform split before
  booting anything.
- Run the round against its own backend: its own database, server and ports,
  never the dev or production one. Testers create accounts, spend rate-limited
  actions and leave junk behind.
- Freeze the binary under test. Copy the server binary and the app build into
  the QA directory, so a rebuild elsewhere cannot swap them mid-round. Name
  builds by fix generation (`app-qa.apk`, `app-qa-fix1.apk`).
- Give each tester its own account. Use throwaway accounts for anything with
  a quota (handle changes, invites per week).
- List the features that depend on services the QA backend lacks (push,
  payments, OAuth, email). Enable them or mark them out of scope in every
  charter. Otherwise a missing service shows up as an app bug.

## Step 2: Write the fleet file and the restore script

Before any tester starts, write `<qa-dir>/fleet.md`: per tester the device
name and host, account, ports forwarded, test data, evidence directory and
charter id; plus the backend's ports and logs.

Then write `<qa-dir>/up.sh`: idempotent, safe to rerun, and it brings up
everything the fleet needs from nothing: database, server, tunnel, then per
device `phone device boot`, `phone device reverse` and `phone app install`.
`phone up` fits only when the project's `phone.toml` points at the QA backend
and one device per platform is enough. Run it once to prove it. A host reboot
mid-round then costs one command, not an hour of rebuilding by hand.

## Step 3: Plan coverage

- One charter per tester, session-based: a mission (area and risk), the
  platform, a time box, the data to use, and what is out of scope.
- Split by area, not by screen count. Make one tester own platform parity
  (safe areas, both languages, the other OS).
- A shared instrument (a counter, a parser, a scoring rule) gets distinct
  inputs on every tester, so the round produces N samples instead of N copies
  of one.
- Write each cross-device scene in advance as numbered beats with an owner per
  beat: "B1 qa-2 sends invite to qa3_tester; B2 qa-3 waits for it, accepts;
  B3 qa-2 checks the duel screen". A tester that reaches a beat owned by
  someone else ends its turn with `WAITING <beat>`; the lead resumes it with
  SendMessage once that beat is reported. Unscripted coordination through the
  lead loses windows and invents bugs.
- Leave a "not covered" list; it goes into the final file.

## Step 4: Brief testers

Each tester is a subagent. Its prompt starts with `QA-FLEET TESTER` and holds:

1. Its device (`-t <name>`), its account, and the rule to touch no other
   device and never pass `--take`.
2. Its charter, scene beats and time box.
3. Read-only access to the backend's data (for example `psql` with
   `PGOPTIONS='-c default_transaction_read_only=on'`), to
   check what the server recorded against what the app shows.
4. `phone` rules: no `sleep`, `wait` for results, screenshots at
   `--scale 0.4 --jpeg 70`, crash triage through the logcat crash and events
   buffers as `phone-skill` describes.
5. Evidence files hold raw output only (screenshots, logs, query results),
   never written-up findings. Their names double as a checkpoint:
   `<evidence-dir>/<case>-<step>.jpg` and `.log`, where `<case>` is the
   charter item. On resume, the tester lists its evidence directory and skips
   the cases already there.
6. The report format below, returned as the final message. Subagents may not
   write report files; do not tell them to work around that.

Report format, kept short so it is not truncated on return:

```
PASS <case> one line each
FAIL <id> <severity> <platforms> <screen>
  steps: 1. … 2. …
  expected: …   actual: …
  evidence: <paths>
SKIP <case> <reason>
```

Long logs go to evidence files, never into the report. A report that stops
mid-item was truncated: SendMessage the tester for the rest.

## Step 5: Run and triage

- Launch testers in parallel, then wait. Release scene beats as their
  prerequisites report back.
- A crash: the tester attaches the crash-buffer stack. Rule out the
  low-memory killer before calling it an app crash. The lead finds and fixes
  the cause under `dev-flow`, builds the next fix generation, installs it on
  one device, and has the reporting tester rerun the exact repro.
- A finding that touches a missing service, or test data of doubtful quality
  (a mislabelled clip, a seeded account in an odd state), is checked by the
  lead before it enters the list.
- An offline test cuts one device only (`phone-skill`, "Testing offline"),
  never the shared server or tunnel.
- A host reboot: run `up.sh`. Devices may still be leased to the dead
  testers' sessions; the lead checks holders in `phone device list` and
  reclaims those only, never one a live session holds. Testers never `--take`.
  Then resume each tester with its brief plus "resume from your evidence
  directory".

## Step 6: Consolidate

Write one repro file, by area: id, severity, platforms, steps, expected,
actual, evidence directory. End with the "not covered" list and the fixes
already landed during the round. Ask the user before committing it; usually
it belongs in `.gitignore` or the tracker, not the repo.

## Step 7: Tear down

`phone release` every device the round held, then shut down the ones the user
does not want running. Stop the QA server and tunnel. Delete test data pushed
onto devices when the project requires it. Ask before deleting devices or the
QA directory. A device another session still holds is reported, not taken.

## Step 8: Keep what passed

A flow that passed and will be rerun next release should become a script, so
the next round starts from it instead of from zero. List those flows in the
final message to the user, with the steps a tester took, as candidates for
Maestro or the project's UI test framework.
