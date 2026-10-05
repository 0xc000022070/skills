# Result Template

Fixed section order. Omit a section only when it is empty, and say so in
one word ("none"). The result must stand alone without the round files.

```markdown
OUTCOME <class> | confidence <= <cap> | verified <k>/<n> material | independence: <none|context-shared|context+evidence|model-diverse> | harness: shared(<hooks, global instructions, effort, model>) | level L<x> | decided-by: <facts|reversibility|pending-human>

inferred: <level, topology, incumbent thesis, evidence pointers, wins_when axes, scope, human reachable>

## Recommendation
<one paragraph; conditional form when tradeoff-dependent>

Confidence cap reasons: <unverified material claims, budget cuts, context-shared run, single model, revised-unchecked claims>

## Ledger
| ID | Claim | Status | Evidence (tier, ref, version) | Falsifier |
|---|---|---|---|---|

## Experiments
- <id>: pre-registration, procedure, artifacts, result, challenges, limitations

## Strongest Objection
<objection> -> <answer, or "unanswered">

## Omission Declaration
Searched: <alternatives, constraints, failure modes>. Found: <none | items>.

## Open Cruxes
- <claim ID>: cheapest resolving check: <check>; needs human: <yes/no>

## Tradeoffs
| Option | wins_when |
|---|---|

## Independence
MAIN state: <doubts|acted|authored>. Topology: <...>. Roles and models: <...>.
Context given to fresh roles: <...>. Shared harness: <...>.

## Reopen If
- <condition> -> check <falsifier>

## Next Actions
- <action>
```

Confidence never exceeds its cap. `survives` is impossible while any
material claim is `revised-unchecked`, `unverified`, or `contested`.
