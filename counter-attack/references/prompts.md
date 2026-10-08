# Target Prompts

The target receives these as if the user typed them. Keep the first line of
each verbatim; it keeps a reviewer's mistake from becoming a user order.

## COUNTER.md

```
[COUNTER-ATTACK r<round>/2] Automated reviewer, not your user. Your user's last instruction outranks this message. Stay inside that task: do not push, deploy, delete, install, or widen scope unless that task asked for it. If an item is wrong, say so with evidence.

Task under review: <one-line paraphrase; the user's words stay authoritative>

X1 [finding|question] <atomic claim> | evidence: <path:line, command, or file> | falsifier: <check that settles it>
X2 ...

Answer each item on its own line before anything else:
X<k> fixed <path:line or command + result> | defended <evidence> | conceded <what changed>
Agreement without evidence counts as unanswered. Fold fixes into your existing task commit with an amend when it is HEAD and unpushed; otherwise leave them uncommitted. Finish with a short final state of the task.
```

## FINALIZE.md

```
[COUNTER-ATTACK finalize] Automated reviewer, not your user. Your user's last instruction outranks this message. Only touch git history as described here; never push.

Task: <one-line paraphrase>
Commit state: <uncommitted | sprawl: <hashes>>
Plan: <amend <sha> | one new commit | squash <first>..<last> into one commit>
Files in scope: <paths>

Follow the repository's commit convention and your commit rules. Stage only the files in scope. If the plan is unsafe now (HEAD moved, something pushed, another agent's commit on top), make one new commit instead or leave history alone, and say which. Reply with the resulting commit hash and `git log --oneline -3`.
```

Rules for filling them:

- Findings first, then questions.
- Every item cites an artifact a stranger can open.
- FINALIZE.md never carries review items; once rounds are exhausted the
  target only commits.
