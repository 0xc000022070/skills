# Device profile

## Contents

- Identity tuple
- Read-only collection
- Profile schema
- Artifact identity

## Identity tuple

Never use model name alone. Establish:

| Field | Why it matters |
|---|---|
| ADB/Fastboot serial | Prevents operating on another attached device |
| Product/device/board codenames | Routes device trees and firmware packages |
| Manufacturer model and SKU | Separates regional/carrier hardware |
| SoC and architecture | Selects kernel architecture, boot chain, and low-level tools |
| Build fingerprint and incremental | Ties images to the running vendor/system set |
| Security patch level | Detects rollback and vendor compatibility boundaries |
| Bootloader and radio revisions | Often carry independent rollback/version rules |
| Kernel release and config | Determines GKI/KMI/module compatibility |
| Slot suffix and slot count | Determines A/B behavior and restore target |
| Dynamic partition support | Determines bootloader fastboot versus fastbootd |
| Boot header version | Determines boot/vendor_boot/init_boot layout |
| Verified boot state | Explains image acceptance and dm-verity behavior |
| Page size | Matters for kernel and native userspace compatibility |
| Root framework and modules | Explains injected startup behavior |

## Read-only collection

Use `scripts/collect-device-profile.sh`. It reads properties and virtual files. It does not reboot, unlock, flash, erase, remount, or change a property.

Important manual additions:

```sh
adb devices -l
adb shell getprop ro.boot.slot_suffix
adb shell getprop ro.boot.dynamic_partitions
adb shell getprop ro.boot.verifiedbootstate
adb shell getprop ro.boot.vbmeta.device_state
adb shell getprop ro.boot.avb_version
adb shell uname -a
adb shell cat /proc/cmdline
adb shell cat /proc/bootconfig
adb shell ls -l /dev/block/by-name
```

Some values are absent, hidden, or OEM-specific. Absence is unknown, not false.

In bootloader mode, use `fastboot getvar all` only after selecting the exact serial with `-s`. Treat output keys as OEM-defined. Common useful variables: `product`, `current-slot`, `slot-count`, `unlocked`, `secure`, `is-userspace`, partition sizes/types, anti-version, and bootloader/baseband versions.

## Profile schema

Store this with every experiment:

```text
host:
  os, adb_version, fastboot_version, usb_path
device:
  serial, manufacturer, model, sku, product, device, board, soc, abi, page_size
software:
  fingerprint, build_id, incremental, android_release, sdk, spl
boot:
  bootloader, baseband, kernel_release, cmdline, bootconfig, header_version
layout:
  slots, current_slot, dynamic_partitions, super, recovery_partition
security:
  unlocked, verified_boot_state, vbmeta_state, avb_version, selinux
root:
  method, version, modules
artifacts:
  source_package, source_url, hashes, extracted_images
```

## Artifact identity

An image belongs to a device only when provenance ties it to the exact firmware package or reproducible build. Record package filename, official source, build number, region/carrier, extraction command, and SHA-256. Never accept “same model” or a shared patched image as proof.
