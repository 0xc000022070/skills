# Patterns to copy

When adding anything new, clone the closest existing pattern. Do not
invent new shapes.

## New per-profile option module

Template: `hm-module/keyboard-shortcuts.nix` (simplest complete example).
Shape: module file taking `{config, lib, pkgs, ...}`, options via
`setAttrByPath modulePath { profiles = mkOption { type = attrsOf
(submodule ...); }; }`, activation under `config`. Register the import in
`hm-module/default.nix`. Required ids are `types.str` UUIDs supplied by
the user — never generated.

## Activation script contract

Reference implementation: the update script in `hm-module/places.nix`.

1. Target file missing → `exit 0` (the browser creates it) — unless the
   flake owns the file entirely (managed-set case, see below).
2. Running guard → warn + `exit 1`. Import `hm-module/running-guard.nix`
   per profile: reads the profile `lock` symlink (target `<ip>:+<pid>`),
   aborts only if that PID is alive AND (Linux) `/proc/<pid>/comm`
   contains "zen". Per-profile, pure (readlink + `kill -0` only,
   guaranteed on the activation PATH), stale-lock and PID-reuse safe.
   Never reintroduce process-name matching.
3. Backup → transform → non-empty output check → replace → drop backup;
   `restore_and_cleanup` trap restores the backup on any failure.
4. jq merge preserves unknown fields: upsert by id, `*`-merge objects so
   declared keys win and browser runtime state survives, append entries
   with unknown ids. Never rewrite whole structures.
5. Hook: `home.activation.<name>-<profile> = lib.hm.dag.entryAfter
   ["writeBoundary"]`; add the producing script's name to the
   `entryAfter` list when one state file depends on another (e.g.
   live-folders runs after `zen-sessions-<profile>`).
6. Compression: activation scripts use `mozlz4a` / `mozlz4a -d`
   (nixpkgs); manual inspection uses `dejsonlz4`.

## Managed-set pattern (flake-fetched content that must be removable)

`hm-module/mods.nix`: keep a `<thing>-nix-managed.json` in the profile
listing what nix installed; on activation diff it against the declared
list and delete de-listed entries from both the JSON registry and the
chrome dir. Sine variant in `sine.nix`. Without this, removing an option
from the config leaks the installed artifact forever.

## Force semantics (three tiers)

Copy from places.nix: plain declare (upsert only), `<x>Force` (prune
undeclared entries), `pinsForceAction = "demote"` (soft prune —
reclassify instead of delete, then rewrite `.index` 0..N per workspace).
Any new destructive option needs the demote-style soft alternative when
user data loss is plausible.

## Version-drift guard

`keyboard-shortcuts.nix`: optional `<x>Version` option; activation greps
`prefs.js` for the browser's schema-version pref and FAILS activation on
mismatch. Use for any state file the browser migrates
(`zen.keyboard.shortcuts.version` ↔ `LATEST_KBS_VERSION` in
`ZenKeyboardShortcuts.mjs`).

## Warnings vs assertions

Both live centrally in `hm-module/default.nix`. Warnings: no-op options,
misconfigurations that degrade (e.g. option ignored for a variant).
Assertions: platform limits, mutually exclusive options (sine × mods),
structural invariants (joinedTabs 2–3 tabs, sizes sum 100). Never inside
feature modules.

## User-overridable defaults

`mkDefault` everywhere the user may want to win: mimeapps values in
`default-browser.nix`, policy defaults (DisableAppUpdate,
DisableTelemetry) in `package.nix`. The `default-browser` VM check
verifies a user override beats the module.

## Package overrides chain (order matters)

`hm-module/package.nix`: unwrapped `.override {policies,
enablePrivateDesktopEntry}` → `applyEnv` overrideAttrs → optional sine
postInstall overrideAttrs → `wrapFirefox {icon}` → wrapper `.override
{extraPrefs, extraPrefsFiles, nativeMessagingHosts}` → optional nixGL.
Insert new hooks at the right layer: files into the lib dir →
postInstall on unwrapped; launcher env → gappsWrapperArgs in preFixup;
prefs/policies → wrapper.

## Test suite

Register in the suites map in `tests/default.nix`; a suite file returns
`{homeModule, testScript}`. Assert cold state first, then wrap with
`wrapWithX11` (Xvfb + 5s real Zen launch) to assert the state file
survives an actual browser run — this is what catches "browser resets the
file on unknown schema" bugs. In-VM inspection: `mozlz4a -d` + `jq` as
the test user. Model: `tests/pins-persistent.nix`.

## Finishing checklist for any option change

`examples/NN-<feature>.nix` (next free number) → `nix run
.#docs-options` → `alejandra <files>` + `deadnix <files>` → targeted
check build. `docs/options.json` is gitignored: regenerate it, never
commit it.
