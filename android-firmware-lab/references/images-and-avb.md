# Images, partitions, and AVB

## Contents

- Recognition
- Inspection pipeline
- Sparse and dynamic images
- AVB
- OTA payloads
- Repacking checks

## Recognition

Common magic values:

| Format | Magic/location |
|---|---|
| Android boot | `ANDROID!` at offset 0 |
| Vendor boot | `VNDRBOOT` at offset 0 |
| AVB vbmeta | `AVB0` at offset 0 |
| AVB footer | `AVBf` in final 64 bytes |
| Android sparse | little-endian `0xed26ff3a` at offset 0 |
| OTA payload | `CrAU` at offset 0 |
| DTBO table | big-endian `0xd7b7ab1e` at offset 0 |
| EROFS | little-endian `0xe0f5e1e2` at filesystem superblock |
| ext4 | little-endian `0xef53` at superblock offset 0x438 |

Run `scripts/inspect-image.py` for a first pass. Then use canonical format tools.

## Inspection pipeline

1. Hash and preserve input.
2. Identify container and compression with `file`, magic, and size.
3. Inspect metadata without unpacking when possible.
4. Extract into a new directory.
5. Record every derived hash.
6. Compare original versus repacked header fields, sections, sizes, compression, command line, and AVB footer.

For boot images use AOSP `unpack_bootimg` or current `magiskboot`. For AVB use `avbtool info_image`, `verify_image`, and descriptor inspection. For DTBO use `mkdtimg dump`; for DTBs use `fdtdump`/`dtc`. For `super`, use `lpdump` before `lpunpack`.

## Sparse and dynamic images

Android sparse is a transport representation of a larger logical block image. Compare logical expanded size against partition capacity. `simg2img` expands it; never mount the sparse file as raw ext4.

Dynamic partitions are logical extents described by metadata inside `super`. Flash logical partitions in userspace fastboot (`fastbootd`) when device tooling requires it. Bootloader fastboot and fastbootd are distinct even though both use the host `fastboot` client. Check `fastboot getvar is-userspace`.

Virtual A/B snapshots can make the live mapping differ during OTA merge. Do not resize or rewrite logical partitions mid-merge.

## AVB

AVB verifies images through hash/hashtree descriptors, signatures, chained vbmeta images, rollback index locations, and a bootloader root of trust. The lock state changes enforcement but does not make image relationships irrelevant.

Before modifying an AVB-protected image, identify:

- root and chained vbmeta images;
- descriptors covering the target partition;
- signing keys and algorithms;
- rollback index and location;
- partition size/footer requirements;
- dm-verity hashtree and FEC layout;
- bootloader lock state and custom-key support.

Disabling verification is not a generic repair. It may erase data, violate the intended chain, or fail on an OEM bootloader. Prefer coherent signing when developing a full firmware set.

## OTA payloads

`payload.bin` contains update operations and metadata, not a simple archive. Full payloads can reconstruct partitions; incremental payloads require exact source blocks. Use the package metadata to bind extracted images to build fingerprint/SPL. Preserve OTA signatures and payload properties when studying update behavior.

## Repacking checks

Verify header version, page alignment, kernel/ramdisk compression, DT placement, bootconfig, command line, OS version/SPL fields, partition size, AVB footer offset, and hash. A tool reporting “repacked” proves syntax, not boot compatibility.
