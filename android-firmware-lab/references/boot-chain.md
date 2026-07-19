# Android boot chain

## Contents

- Stage model
- Boot image generations
- Partition roles
- GKI split
- Recovery and slots

## Stage model

1. Boot ROM selects an authenticated first-stage loader from immutable or SoC-controlled storage.
2. Bootloader initializes memory/storage, selects slot/mode, enforces lock and rollback policy, verifies images, loads kernel/ramdisks/DT, and transfers control to the kernel.
3. Kernel initializes architecture, drivers, memory, scheduler, security, and filesystems, then executes first userspace `init`.
4. First-stage init mounts early partitions, loads SELinux policy, switches root when needed, and enters second-stage init.
5. Android init parses rc files, starts services, mounts remaining partitions, and launches core daemons and Zygote.
6. Zygote/system_server bring up the Java framework; boot animation ends after framework readiness.

Bootloader does not execute Android init. Kernel starts init.

## Boot image generations

All standard boot images begin with `ANDROID!`. Header version is stored at offset 40.

| Header | Typical launch generation | Important layout |
|---|---|---|
| 0 | Android 8 and older | Kernel, ramdisk, second stage, legacy addresses/page size |
| 1 | Android 9 | Adds header size and recovery DTBO/ACPIO fields |
| 2 | Android 10 | Adds DTB size/address |
| 3 | Android 11 | Fixed 4096 layout; DTB/vendor data move to `vendor_boot` |
| 4 | Android 12+ GKI | Adds boot signature; vendor_boot v4 supports ramdisk fragments |

Android 13 introduced `init_boot` for the generic ramdisk on launching devices. Android version alone does not prove the partition exists; inspect firmware and partition map.

## Partition roles

| Partition/image | Typical content |
|---|---|
| `boot` | Kernel plus generic ramdisk on older layouts; mainly GKI kernel on Android 13+ GKI |
| `init_boot` | Generic ramdisk on Android 13+ launching layouts |
| `vendor_boot` | Vendor ramdisk, DTB, bootconfig/vendor boot data |
| `vendor_kernel_boot` | Additional vendor kernel boot data on newer implementations |
| `dtbo` | Device-tree overlays applied by bootloader |
| `recovery` | Dedicated recovery on non-A/B/legacy layouts; may not exist on A/B devices |
| `vbmeta*` | AVB descriptors, keys, hashes/hashtrees, rollback metadata |
| `super` | Container metadata and extents for logical partitions |
| `system`, `system_ext`, `product` | Framework and system/product components |
| `vendor`, `odm` | Hardware/vendor implementation and board customizations |
| `system_dlkm`, `vendor_dlkm`, `odm_dlkm` | Kernel modules split by ownership |
| `metadata` | Metadata-encryption keys and update state; not user backup storage |
| `misc` | Boot/recovery control messages and other small state |

Partition names and responsibilities evolve. Inspect exact image headers, fstab, bootconfig, device tree, and build configuration.

## GKI split

GKI separates a generic Android common kernel from vendor-specific modules and ramdisk content. Compatibility depends on Kernel Module Interface, symbol lists, module signatures/options, Android kernel branch, architecture, page size, and vendor implementation. `5.10` alone is not a KMI identity.

For release string `5.10.101-android12-9-...`, the KMI generation is commonly `5.10-android12-9`. Sublevel can vary within a compatible KMI, but security patch and vendor assumptions still matter.

## Recovery and slots

A/B devices maintain bootable slot sets. Recovery can live in boot/init ramdisk instead of a `recovery` partition. Never issue `fastboot flash recovery` until the partition is proven to exist for the exact device.

Virtual A/B uses snapshots during OTA; it does not mean every physical partition is duplicated. Slot switching can expose an old bootloader or mismatched partition set. Treat both slots as coordinated firmware sets.
