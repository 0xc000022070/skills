# Building Android firmware

## Contents

- Reproducibility record
- Kernel/GKI builds
- AOSP/ROM builds
- Device bring-up
- Output verification

## Reproducibility record

Record source manifest/commit, local patches, toolchain identity, build configuration, environment, command, inputs, outputs, warnings, and SHA-256 hashes. Do not call an artifact reproducible without a second clean build comparison.

For Android `repo` work, export a revision-locked manifest with `repo manifest -r`. Pinning only the manifest repository leaves subordinate branch revisions movable. A committed Nix `flake.lock` pins Nix inputs, not the Android source forest, blobs, ccache, or mutations made inside the checkout.

## Kernel and GKI builds

Determine the branch/build system from device source. Modern Android common kernels use Kleaf/Bazel; older/vendor trees often use `build.sh`, Make, or vendor wrappers. Follow the tree, not a generic command.

Pin:

- architecture and defconfig/fragments;
- Clang/binutils revisions;
- Android common kernel branch and KMI generation;
- LTO/CFI, module signing and `CONFIG_MODVERSIONS`;
- page size and compression;
- protected/exported symbol lists;
- in-tree and external modules;
- DTB/DTBO sources;
- boot/vendor_boot packaging inputs.

Run kernel tests available to that branch. Compare `vmlinux`, `Image*`, modules, `Module.symvers`, config, ABI reports, and build metadata.

## AOSP and ROM builds

AOSP current development uses `android-latest-release`; exact ROM projects use their own manifest branch. Full AOSP checkout/build needs substantial Linux resources. Initialize manifest, sync pinned revision, source build environment, select exact product/variant, and build declared targets.

Core integration dimensions:

- product/device makefiles and Soong namespaces;
- kernel and boot image configuration;
- proprietary vendor blobs and extraction provenance;
- partition groups, sizes, filesystems, and OTA metadata;
- VINTF manifest/matrix compatibility;
- SELinux policy and file contexts;
- init rc, fstab, ueventd, properties and overlays;
- AVB keys/descriptors and rollback indexes;
- recovery/updater assertions and firmware minimums.

Use `userdebug` for bring-up evidence. A permissive build is not completion.

## Device bring-up

Bring up in layers:

1. Bootloader accepts and loads image.
2. Kernel reaches init with storage, console, timers, interrupts.
3. First-stage mount and SELinux policy load.
4. Vendor/system partitions and data encryption mount.
5. Core native services and Zygote.
6. system_server and UI.
7. HALs: display, input, storage, audio, camera, radio, sensors, biometrics.
8. suspend/resume, charging, thermal, performance, OTA and recovery.

For custom recovery builds, use [recovery-bringup.md](recovery-bringup.md). Do not replace upstream recovery init or patch the source checkout during the build unless the exact diff is versioned and reviewed.

## Output verification

Inspect every produced image before boot. Check names, sizes, headers, timestamps/reproducibility, partition fit, filesystem integrity, AVB descriptors/signatures, OTA metadata, target assertions, and hashes. Archive build log and manifest with outputs.
