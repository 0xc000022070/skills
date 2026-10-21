# Morning Report Template

Build it from STATE.json and each pane's latest REVIEW.md. Read review
files now, at the end, not during the run. `settled` means verified with zero
open items; `capped` means the budget ran out first. Never merge the two.

```markdown
# Counter-Attack <run-id>

<start> -> <stop> | mode <awake|sleep|audit> | prompts <sent>/<global cap> | stop reason <deadline|user|all-final>

| Pane | Title | Final verdict | Rounds | Commit | Needs you |
|---|---|---|---|---|---|

## Needs You
- <pane>: <awaiting-human question verbatim | blocked dialog | delivery-unknown | capped with open items | capitulated items | high-blast questions | shared-file commit skipped | commit sprawl | commit plan refused>

## Per Pane
### <pane> - <title>
Task: <verbatim>
Final: <VERDICT line>
Rounds: <per round: items sent -> fixed/defended/conceded/capitulated/unanswered>
Commits: <hashes and subjects, amended/new>
Open items: <from the last review>
Reviews: <paths>
```
