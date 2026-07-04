# Zen profile state files

Profile dir: Linux `~/.config/zen/<profile>/`, macOS
`~/Library/Application Support/Zen/Profiles/<profile>/`.

| File | Browser writer | Format | Inspect |
|---|---|---|---|
| `zen-sessions.jsonlz4` | `desktop/src/zen/sessionstore/ZenSessionManager.sys.mjs` | mozLz4 JSON | `dejsonlz4 f \| jq` |
| `zen-sessions-backup/` (`clean.jsonlz4`, `zen-sessions-<ts>.jsonlz4`, `recovery.baklz4`) | same module | mozLz4 | same |
| `zen-live-folders.jsonlz4` | `desktop/src/zen/live-folders/ZenLiveFoldersManager.sys.mjs` (JSONFile lz4) | mozLz4 JSON, flat array | `dejsonlz4 f \| jq` |
| `zen-keyboard-shortcuts.json` | `desktop/src/zen/kbs/ZenKeyboardShortcuts.mjs` | plain JSON | `jq` |
| `zen-themes.json` | `desktop/src/zen/mods/ZenMods.mjs` (resets to `{}` on corruption) | plain JSON | `jq` |
| `chrome/zen-themes.css` | generated aggregate, whole-file regen | CSS | text |
| `chrome/zen-themes/<uuid>/` | mod install (chrome.css, preferences.json, readme.md) | dir | — |
| `chrome/sine-mods/mods.json` + dirs | Sine manager JS (external project) | plain JSON | `jq` |
| space-routing JSONFile `{routes:[...]}` | `desktop/src/zen/space-routing/ZenSpaceRoutingManager.sys.mjs` | plain JSON | `jq` |
| `places.sqlite`: `zen_bookmarks_workspaces`, `_changes`, moz_meta key `zen_bookmarks_workspaces_last_change` | `desktop/src/zen/spaces/ZenSpaceBookmarksStorage.js` | sqlite | `sqlite3` |
| `places.sqlite`: `zen_workspaces`, `zen_pins` | LEGACY — migration-only, absent on fresh installs | sqlite | `sqlite3` |
| `lock` (symlink `<ip>:+<pid>`), `.parentlock` (fcntl) | nsProfileLock | — | `readlink lock` |
| `prefs.js`, `user.js`, `containers.json`, `search.json.mozlz4`, `profiles.ini`, `chrome/userChrome.css` | Firefox standard | — | — |

Authoritative shape source when in doubt:
`desktop/src/zen/share/share.schema.json` (JSON Schema for tabs, spaces,
folders, splitViews, gradients).

## zen-sessions.jsonlz4 entry shapes

All UUIDs braced `{uuid}` except live folder ids (verbatim).

- space: `{uuid, name, position, icon, containerTabId, theme:{type,
  gradientColors:[{c:[r,g,b], algorithm, lightness, position, type,
  isCustom, isPrimary}], opacity, rotation, texture},
  hasCollapsedPinnedTabs}`
- pinned tab: `{pinned:true, zenSyncId:"{id}", zenEssential, zenWorkspace,
  userContextId, index, groupId, entries:[{url,title,charset,ID,persist}],
  zenStaticLabel?, id?}`
- folder: entry in `folders[]` (carries `userIcon`) AND in `groups[]`
  (`splitView:false`, color `zen-workspace-color`).
- split view (joined tabs): `groups[]` entry with `splitView:true` +
  `splitViewData` `{groupId, gridType, tabs:[{id}],
  layoutTree:{type:"splitter", direction: vsep→row / hsep→column,
  children:[{type:"leaf", tabId, sizeInParent}]}}`.
- split view nested in a folder: additionally a `folders[]` entry
  `{splitViewGroup:true, parentId:"{folder}", name, pinned:true,
  workspaceId:null}`. Zen nests ONLY entries present in `folders[]`
  (`ZenFolders.mjs` restore); a bare split group renders flat.
- empty-folder guard: SessionStore materializes a folder's group element
  only if some tab references it via `groupId`; childless folders get an
  `about:blank` placeholder tab `{zenIsEmpty:true, id:"<folderId>-empty",
  groupId:"<folderId>"}` listed in the folder's `emptyTabIds`.
- live folder: `folders[]` entry `{isLiveFolder:true, id:<verbatim>,
  emptyTabIds:["<id>-empty"], userIcon, workspaceId}` + `groups[]` entry
  (`splitView:false`) + placeholder tab (always — member tabs are
  browser-ephemeral via `skipSessionStore`). Provider config lives in
  `zen-live-folders.jsonlz4`; the two files join on the folder id, and
  restore drops provider entries without a session folder row
  (`ZenLiveFoldersManager.sys.mjs` #restoreState).

## zen-live-folders.jsonlz4

Flat top-level array. Entry: `{id, type:"rss"|"github",
data:{state:{...}}, dismissedItems:[], tabsState:[]}`.

- rss state: `{url, maxItems, timeRange, interval, lastFetched,
  lastErrorId}` — `interval` self-tunes from the feed's `ttl`.
- github state: `{type:"pull-requests"|"issues", options:{authorMe,
  assignedMe, reviewRequested, repoExcludes}, interval, repos, isJsonApi}`
  — the API url is DERIVED in the provider constructor, never stored;
  `repos`/`isJsonApi` are browser-discovered runtime state.
- Providers: `RssLiveFolder.sys.mjs`, `GithubLiveFolder.sys.mjs` under
  `desktop/src/zen/live-folders/`.
- The manager only runs in the first window-synced window
  (`ZenWindowSync.firstSyncedWindow`) — live folders need window sync
  enabled.

## zen-keyboard-shortcuts.json

`{shortcuts:[{id, key, keycode, group, l10nId, modifiers, action,
disabled, reserved, internal}]}`. Versioned by pref
`zen.keyboard.shortcuts.version` against `LATEST_KBS_VERSION` in
`ZenKeyboardShortcuts.mjs` (19 as of Zen 1.17.x); unknown version → the
browser resets the file. The `migrate()` ladder in the same file shows
every historical schema change.

## zen-themes.json

Object keyed by mod uuid → `{id, name, enabled, author, version, readme,
style, preferences}`. Store fetch endpoints:

- browser: `https://zen-browser.github.io/theme-store/themes/<id>/theme.json`
- raw: `https://raw.githubusercontent.com/zen-browser/theme-store/main/themes/<id>/`
- Sine mods: `https://raw.githubusercontent.com/sineorg/store/main/mods/<id>/mod.zip`
