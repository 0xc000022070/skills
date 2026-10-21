# Android boot chain

## Contents

- Stage model
- SoC download modes
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

## SoC download modes

Stage 1 usually exposes two distinct recovery entry points, and they are not
interchangeable. On MediaTek they are the Boot ROM and the preloader; other
vendors have analogues with different names and different capabilities.

| Entry | Runs from | DRAM | Reachable when |
|---|---|---|---|
| Mask ROM | ROM fixed at fabrication | not initialized | always; no flash operation can erase it |
| Primary loader | dedicated boot storage | initialized by this stage | its own image is intact |

Host flashing tools upload a download agent that has to buffer partition data
somewhere, and that somewhere is DRAM. On MediaTek the DRAM timings live in the
preloader, not in the SoC, so entering through the Boot ROM fails at agent
upload unless the tool is handed the device's own preloader image.

The practical consequence is counter-intuitive: **the key combination that
forces mask-ROM entry is the wrong one for ordinary recovery.** Prefer the
primary-loader window. Start the host tool first and attach the cable with no
keys held, because the window is often under a second.

Reach for mask-ROM entry only when the primary loader itself is unbootable, and
supply the matching loader image with it. A loader from another variant carries
another board's memory parameters and executes before everything else on the
chip.

A device that bootloops is not only a failure — each pass runs the primary
loader to completion before dying, which is a repeated, catchable download-mode
window that needs no external loader image.

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
