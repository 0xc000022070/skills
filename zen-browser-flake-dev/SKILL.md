---
name: zen-browser-flake-dev
description: Development map for the 0xc000022070/zen-browser-flake repo (Nix flake + home-manager module packaging Zen Browser). Use when adding or changing HM options, writing activation scripts for profile state files, touching packaging/wrapping/runtime libs, working the update pipeline (sources.json, update.sh, CI), running the VM test suites, or triaging user issues against the right layer. Covers repo architecture, the activation-script contract, hard rules, and workflows. For browser-side formats and source navigation, use zen-browser-internals.
allowed-tools: Read Grep Glob Edit Write Bash(nix:*) Bash(gh:*) Bash(alejandra:*) Bash(deadnix:*) Bash(rg:*) Bash(git:*)
disable-model-invocation: false
metadata:
  author: Luis Quiñones
  version: "1.0.0"
  category: nix
---

# zen-browser-flake — how to develop it

Repo: https://github.com/0xc000022070/zen-browser-flake. If the checkout
has a repo-local skill (`.claude/skills/zen-browser-flake/`), load it too:
it carries the maintained file:line anchors; this skill carries the
architecture, contracts, and workflows.

## Architecture

| Layer | Files | Owns |
|---|---|---|
| Sources | `sources.json` (machine-managed), `default.nix` (variant selection: beta / twilight / twilight-official) | version, urls, hashes per variant × arch |
| Package | `package.nix` | unpack, runtime libs (buildInputs / runtimeDependencies / LD_LIBRARY_PATH preFixup), policies merge, desktop entries, darwin/linux install |
| HM module | `hm-module/default.nix` (imports + warnings + assertions), one file per concern: `package.nix` (wrapping/env/nixGL/sine injection), `places.nix` (spaces/pins/folders/joinedTabs → zen-sessions.jsonlz4), `live-folders.nix`, `keyboard-shortcuts.nix`, `mods.nix`, `sine.nix`, `default-browser.nix`, `running-guard.nix` | options + activation scripts |
| Upstream HM | `mkFirefoxModule` import in `hm-module/default.nix` | profiles.ini, settings, search, bookmarks, containers, extensions, handlers, userChrome, policies plumbing — bug there → workaround here + upstream PR, never fork it |
| Update pipeline | `.github/update.sh` + `zen-update.yml` (hourly cron) | bumps sources.json, mirrors twilight assets to this repo's releases (upstream re-tags `twilight-1` in place), test-builds |
| Tests | `tests/default.nix` suites map, one file per suite | NixOS VM checks; `wrapWithX11` = Xvfb + real 5s Zen launch |
| Docs/examples | `examples/NN-*.nix`, `nix run .#docs-options` → `docs/options.json` (gitignored — regenerate, never commit) | every option change updates both |

Branches: `main` = development; `beta` git branch = stable channel,
force-rebased onto main by CI only after beta version bumps (beta lags
main between bumps — a consumer pinned to `/beta` does not see freshly
merged options until the next bump).

## Hard rules

- Activation scripts that rewrite profile state MUST: skip when the
  target file is missing (browser creates it) → running guard → backup →
  transform → non-empty check → replace → drop backup, with a
  restore-on-failure trap. Reference: `hm-module/places.nix` update
  script; guard: `hm-module/running-guard.nix`.
- Running guard is the profile-lock check (readlink `lock` symlink →
  `kill -0` PID → `/proc/<pid>/comm` contains "zen"). Per-profile, pure,
  stale-lock and PID-reuse safe. NEVER process-name matching — `pgrep
  zen` matches zenith/zenity and is global across profiles (PR #319).
- One writer per state file: everything in `zen-sessions.jsonlz4` goes
  through the places.nix jq filter. A second script writing the same file
  is a bug by construction.
- jq merges are upserts preserving unknown fields: match by id, `*`-merge
  (declared wins for declared keys, browser wins for runtime state),
  append unknown entries. Never rewrite whole structures.
- UUIDs are user-supplied `types.str`, stored braced `{uuid}` in session
  files (live folder ids: verbatim). Never generate ids at eval time —
  eval must stay pure and reproducible.
- Profile paths come from one place (`hm-module/default.nix`): Linux
  `~/.config/zen`, darwin `~/Library/Application Support/Zen` +
  `/Profiles`. Never hardcode elsewhere.
- Warnings and assertions live centrally in `hm-module/default.nix`, not
  inside feature modules.
- NEVER hand-edit hashes in `sources.json`; the update script owns it
  (`nix store prefetch-file` for one-off verification only).
- No flake-utils.

## Workflows

**New/changed option**: copy the closest pattern
([references/patterns.md](references/patterns.md)) → register import in
`hm-module/default.nix` → example `examples/NN-<feature>.nix` (next free
number) → `nix run .#docs-options` → `alejandra <files>` + `deadnix
<files>` → targeted VM check → PR to main.

**Issue triage** (in order): reproduces with nixpkgs firefox → not ours;
profiles.ini/search/containers/extensions → upstream mkFirefoxModule;
missing-lib symptoms (no audio/video/GL) → package.nix runtime libs;
state not applied → activation layer (was Zen closed during rebuild?);
else browser source → switch to zen-browser-internals skill. Read issues
live: `gh issue view <n> -R 0xc000022070/zen-browser-flake --comments`.

**After a major Zen version bump**: re-check
`zen.keyboard.shortcuts.version` vs `LATEST_KBS_VERSION` in
`ZenKeyboardShortcuts.mjs`; diff `ls desktop/src/zen/` against module
options to refresh the feature gap list; run the full check suite.

## Verify commands

```sh
nix build .#beta                                      # package builds
nix build .#checks.x86_64-linux.<suite> -L            # suites in tests/default.nix
nix flake check --no-build                            # eval, warnings, assertions
nix run .#docs-options                                # regenerate option docs
dejsonlz4 ~/.config/zen/<p>/zen-sessions.jsonlz4 | jq # inspect real state
```

## References

- [references/patterns.md](references/patterns.md) — the copyable
  patterns: option module shape, activation contract, managed-set, force
  tiers, version-drift guard, package override chain, test suite.
- [references/external-resources.md](references/external-resources.md) —
  upstream repos, home-manager internals, tooling.
