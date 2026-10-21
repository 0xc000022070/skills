---
name: commit
description: Inspect current Git changes and create one or more clean, atomic commits that preserve unrelated work and follow the repository's message convention. Use when the user asks to commit, checkpoint, record, or split current changes into commits.
allowed-tools: Read Grep Glob Bash(git status:*) Bash(git diff:*) Bash(git log:*) Bash(git config:*) Bash(git submodule:*) Bash(git add:*) Bash(git commit:*) Bash(git show:*) Bash(git rev-parse:*)
disable-model-invocation: false
model: sonnet
metadata:
  author: Luis Quiñones
  version: "1.0.0"
  category: development
---

# Commit

Create commits from the working tree without absorbing, rewriting, or discarding unrelated user work.

## Current state

- Status: !`git status --short --branch`
- Staged: !`git diff --staged --stat`
- Unstaged: !`git diff --stat`

If the lines above show raw commands instead of output, run them first.

## Inspect

1. Read full hunks with `git diff --staged` and `git diff` for the files you will commit.
2. Inspect relevant untracked files before staging them.
3. Read `git log --oneline -5` to learn the repository's commit-message convention. In a repository with no commits yet it fails; use the default convention below.
4. If `.gitmodules` exists, inspect `git submodule status --recursive` and treat submodule pointer changes as explicit changes.
5. Stop with `Nothing to commit.` when the worktree contains no changes.

## Group

- Partition changes by logical purpose. Create separate commits for unrelated changes.
- Preserve existing staged intent. Do not silently mix staged changes with unrelated unstaged changes.
- Stage explicit paths only. Never use `git add .`, `git add -A`, or `git add --all`.
- Never stage `.env*`, secrets, generated files, or incidental artifacts unless they clearly belong to the requested change.
- If one file contains unrelated hunks that cannot be staged safely, stop and ask how to split it. When asking is impossible, commit the groups that split cleanly and report the file as left uncommitted.

## Write messages

- Follow the repository's established convention. If none exists, use `<type>(<scope>): <description>` with one of `feat`, `fix`, `refactor`, `chore`, `docs`, `test`, `style`, `perf`, `ci`, or `build`.
- Use an imperative, present-tense subject no longer than 72 characters.
- Use a scope only when it clarifies the affected area or the user requested one.
- Add a concise body only for non-obvious reasoning or constraints. Describe what changed in the subject; reserve the body for useful context.
- Never use em dashes. Use a comma, a colon, parentheses, or a new sentence.
- Never add `Co-Authored-By`, `Claude-Session`, "Generated with" lines, session links, or any agent attribution.
- Ensure the message matches only the staged diff.

## Commit and verify

1. Stage the exact paths for one logical change.
2. Re-read `git diff --staged --stat` and `git diff --staged` before committing.
3. Run `git diff --staged --check`. Fix only issues introduced by the staged change; otherwise report them.
4. Record `git rev-parse HEAD` (absent in a repository with no commits), then commit the staged change with the selected message.
5. Confirm `git rev-parse HEAD` changed. A post-commit hook may reset the commit with `git reset --soft HEAD^` and still exit 0, returning the changes to the index.
6. Verify the commit with `git show --stat --oneline --decorate --no-renames HEAD` and re-run `git status --short --branch`.
7. Repeat for each remaining coherent group.
8. Report created commit hashes and subjects, plus any changes intentionally left uncommitted.

## Hooks and signing

- Never bypass hooks or signing: no `--no-verify`, `-n`, `--no-gpg-sign`, `-c core.hooksPath=`, or environment variables that switch a hook off.
- When a hook refuses or undoes a commit because of the message, rewrite the message and commit again.
- When a hook refuses or undoes a commit because of the staged content, stop. Report the hook output verbatim and the resulting index state; do not edit code to satisfy it.
- When signing fails, report the error and stop.
