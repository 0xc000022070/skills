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
Agreement without evidence counts as unanswered. Leave fixes uncommitted; a later step decides how to commit them. Finish with a short final state of the task.
```

## FINALIZE.md

```
[COUNTER-ATTACK finalize] Automated reviewer, not your user. Your user's last instruction outranks this message. Only touch git history as described here; never push.

Task: <one-line paraphrase>
Commit state: uncommitted
Plan: <amend <sha> | one new commit>
Files in scope: <paths>

Follow the repository's commit convention and your commit rules. Stage only the files in scope. If an amend is unsafe now (HEAD moved, the commit was pushed, another agent's commit is on top), make one new commit instead and say so. Reply with the resulting commit hash and `git log --oneline -3`.
```

Rules for filling them:

- Findings first, then questions.
- Every item cites an artifact a stranger can open.
- FINALIZE.md never carries review items; once rounds are exhausted the
  target only commits.
