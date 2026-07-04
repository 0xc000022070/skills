# External resources

## Zen

- https://github.com/zen-browser/desktop — browser source (Zen code +
  patches; `engine/` is the generated Firefox checkout, ignore it).
- https://docs.zen-browser.app — user/dev docs (Surfer build docs live
  here too).
- https://github.com/zen-browser/theme-store — mods registry; per-mod
  `themes/<uuid>/{theme.json, chrome.css, preferences.json, readme.md}`.
- https://zen-browser.github.io/theme-store/themes/<uuid>/theme.json —
  what the browser actually fetches.
- https://github.com/zen-browser/www — website + release notes source.
- Releases API: `gh api repos/zen-browser/desktop/releases` — beta tags
  `1.x.ynb`; twilight is the `twilight-1` tag, re-tagged in place (asset
  URLs are unstable pointers).

## Sine (external mod loader)

- https://github.com/CosmoCreeper/Sine — Sine manager.
- https://github.com/sineorg/bootloader — fx-autoconfig bootloader Sine
  rides on.
- https://github.com/sineorg/store — Sine mod store
  (`mods/<id>/mod.zip`).

## Firefox layer (Zen inherits all of it)

- https://searchfox.org/mozilla-central/ — search Firefox source; Zen
  patches mirror these paths.
- nsProfileLock (profile `lock` symlink + `.parentlock` fcntl):
  `toolkit/profile/nsProfileLock.cpp` on searchfox.
- SessionStore internals: `browser/components/sessionstore/` on
  searchfox — Zen's session extras patch into this.
- mozLz4 format: standard LZ4 block with `mozLz40\0` magic header.
  Decoders: `dejsonlz4` (github.com/avih/dejsonlz4, preferred for manual
  inspection), `mozlz4a` (Python, in nixpkgs — used in scripts).
- Pref reference: https://kb.mozillazine.org + `about:config` in a live
  profile; Zen-specific defaults come from `desktop/prefs/zen/*.yaml`
  only.

## Debug logging

```sh
MOZ_LOG="cubeb:5" zen                      # audio backend
MOZ_LOG="PlatformDecoderModule:5" zen      # codec selection
MOZ_LOG="ProfileService:5" zen             # profile selection/locking
```

`about:policies`, `about:support`, `about:processes` for live-instance
introspection.
