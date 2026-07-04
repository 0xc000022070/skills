# External resources

## This project

- https://github.com/0xc000022070/zen-browser-flake — the flake.
  `gh issue list -R 0xc000022070/zen-browser-flake` / `gh pr list` — read
  live, never from stored snapshots.
- Consumers pin `github:0xc000022070/zen-browser-flake` (main) or `/beta`
  (stable branch, force-rebased onto main by CI after beta bumps only —
  it lags main between bumps).

## Upstream browser

- https://github.com/zen-browser/desktop — source + releases. Beta tags
  `1.x.ynb`; twilight re-tags `twilight-1` in place, which is WHY the
  update pipeline mirrors twilight assets into this repo's own releases.
- Releases API: `gh api repos/zen-browser/desktop/releases/latest`.
- For source navigation, state-file formats, prefs: use the
  zen-browser-internals skill.

## home-manager layer

- `mkFirefoxModule`:
  https://github.com/nix-community/home-manager/blob/master/modules/programs/firefox/mkFirefoxModule.nix
  — owns profiles.ini, settings, search, bookmarks, containers,
  extensions, handlers, userChrome/userContent, policies plumbing. Bug
  there → workaround in this flake + PR upstream; never fork the logic.
- Activation DAG: `lib.hm.dag.entryAfter` docs in the home-manager
  manual (`man home-configuration.nix` or
  https://nix-community.github.io/home-manager/).
- `wrapFirefox` / firefox wrapper internals:
  `pkgs/applications/networking/browsers/firefox/wrapper.nix` in nixpkgs.

## Tooling

- `mozlz4a` (nixpkgs) — mozLz4 compress/decompress in scripts and VM
  tests.
- `dejsonlz4` (github.com/avih/dejsonlz4) — preferred for manual
  inspection: `dejsonlz4 file | jq`.
- `alejandra` + `deadnix` — formatting and dead-code lint; run on every
  touched file.
- NixOS VM tests: `nixos-lib.runTest` docs at
  https://nixos.org/manual/nixos/stable/#sec-nixos-tests.
- nixGL (github.com/nix-community/nixGL) — non-NixOS GL wrapping layer
  used by the HM module's `nixGL` option.

## Related ecosystem

- Sine: https://github.com/CosmoCreeper/Sine, bootloader
  https://github.com/sineorg/bootloader, store
  https://github.com/sineorg/store (pinned in `sources.json`
  `.addons.sine`).
- Theme store: https://github.com/zen-browser/theme-store
  (`themes/<uuid>/`).
