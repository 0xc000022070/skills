---
name: rust-android-uniffi
description: Ship a shared Rust core inside an Android (Kotlin/Compose) app through UniFFI and cargo-ndk, built from a Nix dev shell, and run the day-to-day device loop - wireless adb installs, headless or remote emulators over ssh, reaching a laptop backend from a phone via adb reverse or a Tailscale tailnet, and restarting a dev server safely. Use when adding a uniffi crate, wiring cargo-ndk and bindgen into Gradle, the build fails with "no such command: ndk", generated Kotlin lands in the wrong package or warns about an old-style --config file, JNA classes vanish in release, a phone cannot reach the dev API over cleartext http, an emulator must be driven over ssh, or the same Rust logic must also run on the server.
allowed-tools: Read Grep Glob Edit Write
disable-model-invocation: false
metadata:
  author: Luis Quiñones
  version: "1.0.0"
  category: mobile
---

# Rust core in an Android app via UniFFI

```
workspace/
  crates/core        # pure Rust logic, no FFI; also linked by the server
  crates/core-ffi    # thin uniffi layer: cdylib + lib, plus a uniffi-bindgen bin
  server/            # depends on crates/core directly
  android/app        # Gradle: cargoNdk -> bindgen -> preBuild
flake.nix            # rust toolchain with android targets, cargo-ndk, jdk
```

Keep the FFI crate thin. Records, enums and one stateful `Object` go in it,
and the logic stays in `core`, where tests and the server use it without
FFI. See [build.md](references/build.md).

## Route the work

| Task | Read |
|---|---|
| Crate layout, Gradle tasks, bindgen, Nix shell, ProGuard | [build.md](references/build.md) |
| Phones, emulators, networking to a dev backend, server restarts | [device-loop.md](references/device-loop.md) |

## Hard rules

- **Build inside the dev shell**: `nix develop -c bash -c 'cd android && ./gradlew -q :app:assembleDebug'`.
  Outside it, Gradle's Exec task hits "no such command: ndk". It does not see
  the shell's cargo-ndk or rustup targets.
- **Generate bindings in library mode from a built `.so`** (`--library`). Put
  `uniffi.toml` next to the FFI crate's `Cargo.toml`, and do not pass
  `--config`: UniFFI >= 0.29 treats that flag as a global config and warns on
  the old flat format. The file is auto-discovered.
- **JNA ships as an AAR on Android**: `implementation("net.java.dev.jna:jna:<v>@aar")`.
  The plain jar has no Android native libs, and the app crashes on load.
- **Keep JNA and the generated package in R8**, or release builds crash with
  missing classes (see [build.md](references/build.md#proguard)).
- **Transcendental math in shared logic goes through the `libm` crate**, so the
  phone and the server compute identical bits (see
  [build.md](references/build.md#cross-platform-determinism)).
- **Restart dev servers by exact PID** (`pgrep -x <name>`). `pkill -f <path>`
  matches the shell running the command and kills your own session.
- **Do not launch apps on a user's personal phone without asking.** Installing
  is fine; opening the app or tapping around on their device is not.
- **Leave emulators you did not start alone**. Other agents or projects may own
  them. Select one explicitly with `ANDROID_SERIAL` or `adb -s`.

## Completion criteria

For a build change: a clean build from `nix develop`, the generated Kotlin
package is correct, and a debug build installs and loads the native library on
a device. For a deploy to a phone, check `dumpsys package <pkg> | grep
lastUpdateTime` against the APK mtime, and that the backend URL baked into
the build answers from the phone's network.
