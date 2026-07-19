# Android firmware ecosystem

## Contents

- Root frameworks
- Image tools
- Build and debug tools
- ROM/recovery sources

## Root frameworks

### Magisk

Patches boot-stage ramdisk/integration and supplies root daemon, policy tooling, modules, properties, and Zygisk. Select `boot`, `init_boot`, or `recovery` from actual layout and upstream app result. Patch the exact stock image on the target device. Custom-recovery ZIP installation is legacy/deprecated for modern devices.

### KernelSU

Grants root from kernel space. GKI mode replaces/integrates kernel; LKM mode loads a kernel module through patched ramdisk/init flow. Match full KMI generation, security level, compression, module capability, and vendor kernel assumptions. System modifications require a compatible metamodule/overlay approach.

### APatch

Combines KernelPatch and userspace module support. Targets ARM64 and requires usable kernel symbol information. It patches `boot`, not `init_boot`. Treat its kernel-version support and security requirements as volatile upstream facts.

### LSPosed/libxposed

Hooks Android Runtime through a compatible injection framework. It changes app/framework behavior, not bootloader/kernel compatibility. Match Android/ART/API version and module scope.

## Image tools

| Tool | Purpose |
|---|---|
| AOSP `unpack_bootimg`/`mkbootimg` | Canonical Android boot image fields |
| `magiskboot` | Broad boot compression/unpack/repack handling |
| `avbtool` | AVB descriptors, verification, signing, footers |
| `lpdump`/`lpunpack`/`lpmake` | Dynamic partition metadata and images |
| `simg2img`/`img2simg` | Android sparse conversion |
| `payload-dumper-go` | Full OTA payload extraction |
| `mkdtimg`/`dtc`/`fdtdump` | DTBO tables and device trees |
| `debugfs`/`e2fsck` | ext filesystem inspection |
| `fsck.erofs`/`dump.erofs` | EROFS verification/extraction |
| `brotli`, `lz4`, `gzip`, `cpio` | Common image compression/archive layers |

Avoid old kitchen scripts when they do not preserve modern boot metadata, AVB footers, or vendor boot fragments.

## Build and debug tools

Use AOSP `repo`, Soong/Ninja, Kleaf/Bazel or tree-specific kernel wrappers. Debug with `adb`, `fastboot`, logcat, dumpsys, pstore/ramoops, tombstones, Perfetto, simpleperf, ftrace, trace-cmd, GDB/LLDB, and serial console as available.

## ROM and recovery sources

LineageOS device trees/wiki and TeamWin/OrangeFox sources provide device-specific implementation evidence. Maintainer instructions outrank generic forum posts, but exact firmware requirements and current branch still need verification.
