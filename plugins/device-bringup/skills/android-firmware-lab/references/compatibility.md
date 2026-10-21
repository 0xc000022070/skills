# Compatibility model

## Contents

- Compatibility tuple
- Decision matrix
- Kernel compatibility
- ROM compatibility
- Root compatibility

## Compatibility tuple

An artifact is compatible only when all relevant dimensions match:

```text
device codename + hardware SKU + SoC + architecture + firmware generation
+ bootloader revision + SPL/rollback level + slot/layout + boot header
+ filesystem/page size + AVB chain + kernel/KMI + vendor interfaces
```

Do not replace missing dimensions with confidence language. Mark them unknown.

## Decision matrix

| Question | Required evidence | Failure if wrong |
|---|---|---|
| Correct device? | codename, SKU, board, SoC | hard brick or nonfunctional hardware |
| Correct partition? | by-name map, firmware contents, boot header | overwrite unrelated firmware |
| Correct slot? | current slot, target plan, both-slot state | bootloop or fallback into stale slot |
| Image fits? | partition size and image logical size | truncated/rejected image |
| Bootloader accepts it? | unlock state, signing, rollback, format | flash rejection or no boot |
| Kernel boots vendor? | KMI, modules, DT, config, page size | panic, missing storage/display, reboot |
| Userspace matches vendor? | VINTF matrices, SPL/vendor level, HALs | init/framework/HAL failure |
| AVB remains coherent? | descriptors, chained vbmeta, keys, flags | red state, verification failure, dm-verity reboot |
| Recovery exists? | exact partition map and boot flow | invalid flash command |

## Kernel compatibility

Check:

- ARM64 versus ARM and configured page size;
- GKI versus non-GKI;
- full KMI generation, not only major/minor kernel version;
- required exported symbols and protected symbol lists;
- `CONFIG_MODVERSIONS`, LTO/CFI, module signing, compression;
- vendor_boot ramdisk, DTB/DTBO, bootconfig and command line;
- vendor/system/ODM DLKM modules and their load order;
- firmware blobs expected by drivers;
- SELinux and init services expected by kernel interfaces.

A kernel can reach a logo yet remain incompatible.

## ROM compatibility

Validate device tree and inherited products, proprietary blobs, kernel source/prebuilt, partition sizes, filesystem types, dynamic partition groups, VINTF manifests/matrices, init/fstab, SELinux policy, overlays, AVB keys, OTA assertions, firmware minimums, and required modem/bootloader versions.

GSIs validate Treble interfaces, not full device support. Camera, modem, biometrics, encryption, IMS, refresh rate, suspend, and sensors can still fail.

## Root compatibility

- Magisk chooses `boot`, `init_boot`, or `recovery` based on ramdisk/layout; patch the exact same-device stock artifact.
- KernelSU GKI replacement requires matching KMI and compression; LKM mode requires compatible module loading and correct boot/init_boot patch path.
- APatch targets ARM64 kernels with required kallsyms support and patches `boot`, not `init_boot`.
- LSPosed depends on a compatible root injection path and Android/ART implementation; it is not firmware root by itself.

Never stack root implementations unless their upstream documentation explicitly supports the combination.
