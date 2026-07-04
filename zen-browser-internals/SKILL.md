---
name: zen-browser-internals
description: Map of Zen Browser internals — source tree, feature managers, profile state files (jsonlz4 session store, live folders, shortcuts, mods), prefs system, and profile locking. Use when diagnosing Zen behavior, decoding a profile state file, locating the code behind a feature ("why does Zen do X"), checking a pref default, or verifying how the browser persists spaces, pins, folders, split views, or live folders. Browser-side knowledge only; for the Nix flake that packages Zen, use zen-browser-flake-dev.
allowed-tools: Read Grep Glob Bash(rg:*) Bash(dejsonlz4:*) Bash(jq:*) Bash(sqlite3:*) Bash(git:*)
disable-model-invocation: false
metadata:
  author: Luis Quiñones
  version: "1.0.0"
  category: browsers
---

# Zen Browser internals

Zen is a Firefox fork. Everything Firefox-standard (prefs.js, containers.json,
places.sqlite core tables, search.json.mozlz4) behaves exactly like Firefox;
this skill covers only what Zen adds on top.

## Getting the source

```sh
git clone https://github.com/zen-browser/desktop   # Zen-original code + patches
```

`desktop/engine/` appears after `surfer download` — it is the generated
Firefox checkout. NEVER search it; it is huge and not Zen's code.

## Question → where to look

| Question | Look at |
|---|---|
| Why does feature X behave like this? | `desktop/src/zen/<feature>/` (see [references/feature-map.md](references/feature-map.md)) |
| What did Zen change in stock Firefox? | `desktop/src/**/*.patch` (~250 patches, paths mirror mozilla-central) + `desktop/src/external-patches/manifest.json` |
| What is the default of pref `zen.*`? | `desktop/prefs/zen/*.yaml` |
| What is stored in profile file Y? | [references/state-files.md](references/state-files.md) |
| Canonical JSON shape for tabs/spaces/folders/splitViews/gradients | `desktop/src/zen/share/share.schema.json` |
| Where does an error string come from? | `rg "<string>" desktop/src/zen desktop/prefs` |
| Is Zen running with profile P? | `lock` symlink in the profile dir (see Profile locking) |

## Source tree rules

- `desktop/src/zen/<feature>/`: `.mjs` files are per-window globals
  (`gZenFolders`, `gZenViewSplitter`, ...), `.sys.mjs` are process-wide
  modules. `jar.inc.mn` maps them to
  `chrome://browser/content/zen-components/`.
- C++ backends exist for mods (`nsZenModsBackend`), boosts
  (`nsZenBoostsManager`), drag-and-drop. Base classes in `common/`:
  `nsZenDOMOperatedFeature`, `nsZenPreloadedFeature`,
  `nsZenMultiWindowFeature`.
- Prefs YAML conditions: `@IS_TWILIGHT@`, `defined(MOZILLA_OFFICIAL)`.
  `type: static` prefs are compiled into C++ — flipping them at runtime
  may not do what the YAML default suggests.

## Session store invariants (the ones that bite)

- All UUIDs in `zen-sessions.jsonlz4` are braced `{uuid}` — EXCEPT live
  folder ids, stored verbatim.
- A folder only nests if it has an entry in `folders[]`; SessionStore only
  materializes a folder's group element if some tab references it via
  `groupId`. A childless folder silently vanishes on restore — the browser
  guards this with an `about:blank` placeholder tab
  (`ZenFolders.mjs` createFolder) listed in the folder's `emptyTabIds`.
- Live folders join TWO files on the folder id: the session folder row
  (`isLiveFolder: true`) and the provider entry in
  `zen-live-folders.jsonlz4`. Restore drops provider entries whose session
  row is missing (`ZenLiveFoldersManager.sys.mjs` #restoreState). Member
  tabs are browser-ephemeral (`skipSessionStore`) — never persisted.
- `places.sqlite`: `zen_bookmarks_workspaces` is live;
  `zen_workspaces` / `zen_pins` tables are legacy, read once for migration,
  absent on fresh installs.

## Profile locking (how to detect a running Zen)

Inherited from Firefox `nsProfileLock`, per profile dir:

- `lock` — symlink with target `<ip>:+<pid>` created at startup. Can go
  STALE after crash/SIGKILL: presence means nothing, the embedded PID's
  liveness is the signal. Check: `readlink lock`, strip through `+`,
  `kill -0 <pid>`, then confirm `/proc/<pid>/comm` contains `zen`
  (guards PID reuse; comm is the executable basename, 15-char truncated).
- `.parentlock` — the authoritative kernel lock: `fcntl(F_SETLK)`, dies
  with the process. No coreutils tool can probe it (`flock(1)` uses
  `flock(2)`, a different lock type that does not interact with fcntl).
- Never detect Zen by process-name matching (`pgrep zen` matches zenith,
  zenity; it is also global, not per-profile).

## Tools

```sh
dejsonlz4 <profile>/zen-sessions.jsonlz4 | jq .   # decode any .jsonlz4 (mozLz4)
jsonlz4 in.json out.jsonlz4                        # re-encode
sqlite3 <profile>/places.sqlite '.tables'
MOZ_LOG="cubeb:5" zen                              # audio; PlatformDecoderModule:5 for codecs
rg <pattern> desktop/src/zen desktop/prefs         # never desktop/engine
```

Profile dirs: Linux `~/.config/zen/<profile>/`, macOS
`~/Library/Application Support/Zen/Profiles/<profile>/`.

## References

- [references/state-files.md](references/state-files.md) — every Zen state
  file: writer module, format, entry shapes, inspect command.
- [references/feature-map.md](references/feature-map.md) — feature →
  source dir, window global, key prefs.
- [references/external-resources.md](references/external-resources.md) —
  repos, docs, stores, release channels.
