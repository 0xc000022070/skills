# Feature → source dir, window global, key prefs

All under `desktop/src/zen/` in https://github.com/zen-browser/desktop.

| Feature | Dir | Global / module | Key prefs |
|---|---|---|---|
| Spaces (workspaces) + gradient themes | `spaces/` | `gZenWorkspaces` (ZenSpaceManager.mjs), `gZenThemePicker` (ZenGradientGenerator.mjs) | `zen.workspaces.*`, `zen.theme.*`, `zen.view.window.scheme` |
| Pinned tabs / essentials | `tabs/` | `gZenPinnedTabManager` (ZenPinnedTabManager.mjs) | `zen.pinned-tab-manager.*`, `zen.tabs.essentials.max` (=12) |
| Folders | `folders/` | `gZenFolders` (ZenFolders.mjs) | `zen.folders.*` |
| Split view | `split-view/` | `gZenViewSplitter` (ZenViewSplitter.mjs) | `zen.splitView.*` |
| Live folders (RSS / GitHub) | `live-folders/` | `ZenLiveFoldersManager.sys.mjs`, providers `RssLiveFolder.sys.mjs` / `GithubLiveFolder.sys.mjs` | `zen.live-folders.*` |
| Keyboard shortcuts | `kbs/` | `ZenKeyboardShortcuts.mjs` (+ `ZenUBGlobalActions.sys.mjs` command id space) | `zen.keyboard.shortcuts.version` |
| Mods (theme store) | `mods/` | `gZenMods` (ZenMods.mjs) + C++ `nsZenModsBackend` | `zen.mods.*`, `zen.themes.disable-all` |
| Boosts (per-site CSS zaps) | `boosts/` | C++ `nsZenBoostsManager` | `zen.boosts.*` |
| Space routing (URL → space rules) | `space-routing/` | `ZenSpaceRoutingManager.sys.mjs`, JSONFile `{routes:[...]}` | — |
| Session persistence | `sessionstore/` | `ZenSessionManager.sys.mjs` | — |
| Window sync | `sync/` dir + `common/` | `ZenWindowSync` (`firstSyncedWindow` gates single-window managers) | `zen.window-sync.*` |
| Firefox Sync engine for spaces | `sync/` | `ZenWorkspacesEngine` | `services.sync.engine.spaces` (twilight-only) |
| Glance (peek preview) | `glance/` | `gZenGlanceManager` | `zen.glance.*` |
| Compact mode | `compact-mode/` | `gZenCompactModeManager` | `zen.view.compact.*` |
| URL bar | `urlbar/` | `ZenUrlbarProviderGlobalActions`, commands `cmd_zen*` | `zen.urlbar.*` |
| Media controller | `media/` | `gZenMediaController` | — |
| Share import/export | `share/` | `share.schema.json` (canonical shapes) | — |
| Welcome, downloads, drag-and-drop | `welcome/`, `downloads/`, `drag-and-drop/` (C++) | — | — |
| Startup / UI base | `common/` | `gZenUIManager`, `ZenUIMigration.sys.mjs`, base classes `nsZenDOMOperatedFeature` / `nsZenPreloadedFeature` / `nsZenMultiWindowFeature` | — |
| Workspace ↔ bookmark binding | `spaces/ZenSpaceBookmarksStorage.js` | writes `places.sqlite` `zen_bookmarks_workspaces` | — |

## Search order for "why does Zen do X"

1. `desktop/src/zen/<feature>/` — Zen-original code.
2. `desktop/src/**/*.patch` — modified Firefox code (~250 patches; file
   paths mirror mozilla-central, so a patch to
   `browser/components/sessionstore/...` tells you which Firefox module
   was touched).
3. `desktop/prefs/zen/*.yaml` — pref defaults. Conditions `@IS_TWILIGHT@`
   and `defined(MOZILLA_OFFICIAL)`; `type: static` prefs are compiled
   into C++.
4. `desktop/src/external-patches/manifest.json` — third-party patches
   pulled in at build time.

Never search `desktop/engine/` (generated Firefox checkout, appears after
`surfer download`).

## Release channels

- beta — versioned releases (`1.x.ynb` tags on GitHub).
- twilight — rolling; upstream re-tags `twilight-1` in place on every
  build, so an asset URL is NOT a stable pointer. Binary name
  `zen-twilight`, shares the config dir naming with beta.
