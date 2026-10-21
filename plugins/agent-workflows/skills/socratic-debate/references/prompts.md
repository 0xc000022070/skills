# Spawn Templates

Fill the angle-bracket fields. Paths are absolute. Never add persona text.
Every prompt starts with the run marker so the receiver does not re-invoke
the skill.

## Single-Agent Pass (L1, fresh spawn)

```
SOCRATIC-DEBATE RUN <run-id> | ROLE: single-pass
Do not invoke the socratic-debate skill.

Decision: <decision>
User constraints (axioms, verbatim):
<constraints>
Stakes: <reversibility, blast radius>
Incumbent claims and rationale, to interrogate, not to trust:
<claims with IDs, rationale, abandoned options>
Evidence pointers: <paths, commands, output files>
Experiment scope: <scratch dir or worktree>; do not modify <repo paths>.

Protocol: <absolute path to references/protocol.md>
Run dir: <run-dir>

In one session:
1. Challenge the framing: is this the right question, what option or
   constraint is missing? Record what you searched.
2. Decompose into atomic claims. Verify every checkable one with tools;
   save raw output to <run-dir>/obs-<k>.txt.
3. Question each remaining judgment claim with a materiality line; revise
   and re-verify where needed.
4. Write a flip line for each open claim and an omission declaration.
Write everything to <run-dir>/R1-single.md and update <run-dir>/LEDGER.md.
Reply only with the paths.
```

## Socrates (L2+)

```
SOCRATIC-DEBATE RUN <run-id> | ROLE: socrates | EXCHANGE: <n>
Do not invoke the socratic-debate skill.

Decision: <decision>
User constraints (axioms, verbatim):
<constraints>
Protocol: <path to references/protocol.md>
Read first: <run-dir>/LEDGER.md, <your prior R*-socrates.md>, <latest R*-plato.md>

Your moves: question (target a claim ID, with materiality line),
counterexample, request-test, discharge (cite artifact), split, flip.
Verify claims yourself with tools; do not accept paraphrase as evidence.
<n = 1 only> Start with Round 0: challenge the framing and record the
missing-option search.
<final exchange> Write a flip line for each open claim and an omission
declaration.
Write to <run-dir>/R<n>-socrates.md, starting with the line
state: <HEAD sha> + <diff hash>. Reply only with the path.
```

## Plato (L2+, when fresh)

```
SOCRATIC-DEBATE RUN <run-id> | ROLE: plato | EXCHANGE: <n>
Do not invoke the socratic-debate skill.

Decision: <decision>
User constraints (axioms, verbatim):
<constraints>
Protocol: <path to references/protocol.md>
Read first: <run-dir>/LEDGER.md, <your prior R*-plato.md>, <latest R*-socrates.md>

<n = 1> State the strongest thesis as atomic claims, each with a
justification and falsifier. Ground each one with tools.
<n > 1> Answer each open question with exactly one move: defend (with
evidence), revise (new ID, with its own evidence), concede (name the
cause), refer (propose a check), or split.
Write to <run-dir>/R<n>-plato.md, starting with the line
state: <HEAD sha> + <diff hash>. Reply only with the path.
```

## Investigator

```
SOCRATIC-DEBATE RUN <run-id> | ROLE: investigator
Do not invoke the socratic-debate skill.

Question: <neutral question>
H1: <hypothesis> | predicts: <observable>
H2: <hypothesis> | predicts: <observable>
Pre-registration (verbatim):
<procedure / supports / refutes / inconclusive / repetitions>
Write scope: <scratch dir or worktree only>.

Run the procedure. Save raw output, redacted, to <run-dir>/obs-<k>.txt with
an env header. Write <run-dir>/INV-<k>.md: procedure, commands, output
paths, result against each prediction, threats to validity, uncertainties.
Give no recommendation. Reply only with the path.
```

## Omission Sweeper (L3)

```
SOCRATIC-DEBATE RUN <run-id> | ROLE: omission-sweeper
Do not invoke the socratic-debate skill.

Decision: <decision>
User constraints (verbatim): <constraints>
Final ledger: <run-dir>/LEDGER.md
Evidence pointers: <list>

Answer one question: what load-bearing alternative or constraint is absent
from this ledger? Ground the answer with tools. Write to
<run-dir>/SWEEP.md and reply only with the path.
```
