# Build

## Nix dev shell

```nix
rust = pkgs.rust-bin.stable.latest.default.override {       # oxalica/rust-overlay
  extensions = [ "rust-src" "rust-analyzer" "clippy" "rustfmt" ];
  targets = [ "aarch64-linux-android" "armv7-linux-androideabi" "x86_64-linux-android" ];
};
devShells.default = pkgs.mkShell { packages = [ rust pkgs.cargo-ndk pkgs.jdk21 ]; };
```

The Android SDK and NDK can stay outside Nix (`~/Android/Sdk` or
`ANDROID_HOME`); cargo-ndk finds the NDK from there. Iterate systems with
`nixpkgs.lib.genAttrs`, not flake-utils.

## FFI crate

```toml
[lib]
name = "mycore"                 # -> libmycore.so
crate-type = ["cdylib", "lib"]  # lib lets the bindgen bin link it

[[bin]]
name = "uniffi-bindgen"
required-features = ["bindgen"]

[features]
bindgen = ["uniffi/cli"]        # keeps the CLI out of the Android build

[dependencies]
core = { path = "../core" }
uniffi = "0.32"
thiserror = "2"
```

```rust
// src/bin/uniffi-bindgen.rs
fn main() { uniffi::uniffi_bindgen_main() }
```

```toml
# uniffi.toml, next to Cargo.toml, auto-discovered in library mode
[bindings.kotlin]
package_name = "com.example.core"
cdylib_name = "mycore"
```

Use proc-macros only (`uniffi::setup_scaffolding!()`, `#[uniffi::export]`,
`#[derive(uniffi::Record | Enum | Error | Object)]`), with no UDL file.

API shape that works well:

- One `Object` for the stateful session (`Mutex` inside), with methods
  `push(t, floats)`, `count()`, `phase()` and `encode()`.
- Pass bulk per-frame data as a flat `Vec<f32>` with a known stride. Validate
  its length and timestamp order in Rust, and return a typed error.
- Mirror core enums in the FFI crate, rather than deriving uniffi on core
  types, so core stays FFI-free for the server.
- Export constants as functions (`rules_version()`, `depth_goal()`) so UI
  code never hardcodes a value the core owns.

## Gradle wiring

```kotlin
val workspace = rootProject.projectDir.parentFile
val rustSources = fileTree(workspace.resolve("crates")) { include("**/*.rs", "**/Cargo.toml", "**/uniffi.toml") }

val cargoNdk = tasks.register<Exec>("cargoNdk") {
    inputs.files(rustSources)
    outputs.dir(layout.buildDirectory.dir("rust/jniLibs"))
    workingDir = workspace
    commandLine("cargo", "ndk", "-t", "arm64-v8a", "-t", "x86_64", "-P", "26",
        "-o", layout.buildDirectory.dir("rust/jniLibs").get().asFile.path,
        "build", "-p", "core-ffi", "--release")
}

val bindgen = tasks.register<Exec>("bindgen") {
    dependsOn(cargoNdk)
    inputs.files(rustSources)
    outputs.dir(layout.buildDirectory.dir("rust/kotlin"))
    workingDir = workspace
    commandLine("cargo", "run", "-q", "-p", "core-ffi", "--features", "bindgen", "--bin", "uniffi-bindgen", "--",
        "generate", "--no-format", "--language", "kotlin",
        "--library", layout.buildDirectory.file("rust/jniLibs/x86_64/libmycore.so").get().asFile.path,
        "--out-dir", layout.buildDirectory.dir("rust/kotlin").get().asFile.path)
}
tasks.named { it == "preBuild" }.configureEach { dependsOn(bindgen) }

android {
    defaultConfig { ndk { abiFilters += listOf("arm64-v8a", "x86_64") } }
    sourceSets["main"].apply {
        jniLibs.directories += layout.buildDirectory.dir("rust/jniLibs").get().asFile.path
        kotlin.directories += layout.buildDirectory.dir("rust/kotlin").get().asFile.path
    }
}
dependencies { implementation("${libs.jna.get()}@aar") }
```

- The two ABIs cover real phones (arm64) and emulators (x86_64). Add armv7
  only for old low-end devices.
- Declared inputs and outputs let Gradle skip Rust when nothing changed.
- `--no-format` avoids needing ktlint on the path.
- Running bindgen against the x86_64 `.so` is fine: the metadata is the same
  for every ABI.
- After changing `uniffi.toml`, delete `build/rust/kotlin`, or stale files in
  the old package linger.

## Build-time configuration

Read per-machine values from a `-P` flag or `local.properties` (which is not
committed) into `BuildConfig`:

```kotlin
val local = Properties().apply { rootProject.file("local.properties").takeIf { it.exists() }?.inputStream()?.use(::load) }
fun prop(name: String, default: String = "") = providers.gradleProperty(name).orNull ?: local.getProperty(name) ?: default
buildConfigField("String", "API_URL", "\"${prop("app.apiUrl", "http://10.0.2.2:8080")}\"")
```

Each machine or phone then gets its own build without editing shared files.

## ProGuard

```
-keep class com.sun.jna.** { *; }
-keep class * extends com.sun.jna.** { *; }
-keep class com.example.core.** { *; }
-dontwarn java.awt.**
```

## Cross-platform determinism

When the server must reproduce the phone's result exactly:

- Rust never fuses multiply-adds into FMA or enables fast-math on its own.
- `+ - * /` and `sqrt` are IEEE-exact on every target.
- `acos`, `atan2`, `hypot`, `exp`, `ln` and `pow` call the platform libm
  (bionic on Android, glibc or musl on servers), and those differ in the last
  ulp. Call `libm::acos(..)` and friends from the `libm` crate instead of the
  `f64` methods.
- Quantize inputs to the upload format before computing, on both sides.

## Tests

- `cargo test --workspace` and `cargo clippy --workspace --all-targets` run
  on the host with no Android involvement. Keep all logic tests in `core`.
- The Android side needs only an instrumentation smoke test that loads the
  library and calls one function, plus whatever exercises the device
  pipeline.
