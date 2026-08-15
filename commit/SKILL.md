---
name: commit
description: Inspect current Git changes and create one or more clean, atomic commits that preserve unrelated work and follow the repository's message convention. Use when the user asks to commit, checkpoint, record, or split current changes into commits.
allowed-tools: Read Grep Glob Bash(git status:*) Bash(git diff:*) Bash(git log:*) Bash(git config:*) Bash(git submodule:*) Bash(git add:*) Bash(git commit:*) Bash(git show:*)
disable-model-invocation: false
metadata:
  author: Luis Quiñones
  version: "1.0.0"
  category: development
---

# Commit

Create commits from the working tree without absorbing, rewriting, or discarding unrelated user work.

## Inspect

1. Run `git status --short --branch` from the repository root.
2. Inspect staged and unstaged changes separately with `git diff --staged --stat`, `git diff --staged`, `git diff --stat`, and `git diff`.
3. Inspect relevant untracked files before staging them.
4. Read `git log --oneline -5` to learn the repository's commit-message convention.
5. If `.gitmodules` exists, inspect `git submodule status --recursive` and treat submodule pointer changes as explicit changes.
6. Stop with `Nothing to commit.` when the worktree contains no changes.

## Group

- Partition changes by logical purpose. Create separate commits for unrelated changes.
- Preserve existing staged intent. Do not silently mix staged changes with unrelated unstaged changes.
- Stage explicit paths only. Never use `git add .`, `git add -A`, or `git add --all`.
- Do not include generated files, secrets, or incidental artifacts unless they clearly belong to the requested change.
- If one file contains unrelated hunks that cannot be staged safely, stop and ask how to split it.

## Write messages

- Follow the repository's established convention. If none exists, use `<type>(<scope>): <description>` with one of `feat`, `fix`, `refactor`, `chore`, `docs`, `test`, `style`, `perf`, `ci`, or `build`.
- Use an imperative, present-tense subject no longer than 72 characters.
- Use a scope only when it clarifies the affected area or the user requested one.
- Add a concise body only for non-obvious reasoning or constraints. Describe what changed in the subject; reserve the body for useful context.
- Ensure the message matches only the staged diff.

## Commit and verify

1. Stage the exact paths for one logical change.
2. Re-read `git diff --staged --stat` and `git diff --staged` before committing.
3. Run `git diff --staged --check`. Fix only issues introduced by the staged change; otherwise report them.
4. Commit the staged change with the selected message.
5. Verify it with `git show --stat --oneline --decorate --no-renames HEAD` and re-run `git status --short --branch`.
6. Repeat for each remaining coherent group.
7. Report created commit hashes and subjects, plus any changes intentionally left uncommitted.
