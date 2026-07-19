---
name: android-firmware-lab
description: Inspect, identify, build, unpack, patch-plan, temporary-boot, debug, and recover Android firmware, kernels, boot images, root solutions, ROMs, and device trees. Use for adb/fastboot device inventory, boot or init_boot analysis, GKI/KMI compatibility, AVB/vbmeta and A/B slot reasoning, Magisk/KernelSU/APatch work, kernel or AOSP builds, bootloop diagnosis, custom ROM bring-up, and device-specific firmware planning.
allowed-tools: Read Grep Glob Bash(adb:*) Bash(file:*) Bash(sha256sum:*) Bash(python3:*)
metadata:
  author: Luis Quiñones
  version: "1.0.0"
  category: android-firmware
---

# Android Firmware Lab

Treat every device as a concrete hardware/firmware tuple. Do not infer compatibility from a retail model name or Android version alone.

## Start every device task

1. Read [references/device-profile.md](references/device-profile.md).
2. Run `scripts/host-preflight.sh`.
3. If Android boots with authorized ADB, run `scripts/collect-device-profile.sh > device-profile.txt`.
4. Record exact codename, SKU/region, build fingerprint, security patch, bootloader/baseband revisions, SoC, kernel release, boot header generation, slot scheme, dynamic partitions, verified-boot state, and available recovery artifacts.
5. Classify requested action as inspect, build, temporary boot, flash, root, ROM bring-up, debug, or recover.
6. Load only references named by the routing table.

Stop compatibility analysis when identity is ambiguous. A shared marketing name can cover different SoCs, partition maps, signing rules, and bootloader policies.

## Route the work

| Task | Read |
|---|---|
| Understand startup or choose boot artifact | [boot-chain.md](references/boot-chain.md), [compatibility.md](references/compatibility.md) |
| Inspect `*.img`, OTA, `payload.bin`, `super`, DTB/DTBO, AVB | [images-and-avb.md](references/images-and-avb.md) |
| Plan temporary boot, patching, rooting, or flashing | [workflows.md](references/workflows.md), [recovery.md](references/recovery.md) |
| Diagnose bootloop, kernel panic, init failure, SELinux denial | [debugging.md](references/debugging.md) |
| Build kernel, GKI module, AOSP, recovery, or ROM | [building.md](references/building.md), [compatibility.md](references/compatibility.md) |
| Choose Magisk, KernelSU, APatch, LSPosed, or tooling | [ecosystem.md](references/ecosystem.md) |
| Handle Pixel, Samsung, Xiaomi, OnePlus, Motorola, Sony | [device-families.md](references/device-families.md) |
| Refresh volatile facts or verify provenance | [sources.md](references/sources.md) |

## Evidence hierarchy

Prefer, in order:

1. Facts read from the target device and exact stock firmware.
2. OEM material for the exact codename, region, and build.
3. AOSP specifications and source.
4. Upstream tool/root/ROM documentation.
5. Maintainer device instructions.
6. Community reports as leads, never sole compatibility proof.

Keep external lookup narrow. Use bundled references for stable mechanics. Re-check upstream only for volatile items: current releases, supported kernels/Android versions, OEM unlock policy, anti-rollback notices, current device builds, and exact device instructions.

## Operational model

Move through these states:

`inventory -> acquire exact stock artifacts -> inspect -> compatibility decision -> recovery plan -> build/patch -> offline verification -> temporary boot when supported -> observe -> persistent write only when requested`

Before a device write, produce a concise execution record containing:

- target serial and codename;
- current and target build fingerprints/SPLs;
- current slot and target slot;
- exact partition and resolved fastboot mode;
- input/output SHA-256 hashes;
- why image format and KMI match;
- AVB and rollback implications;
- stock restore artifact and tested route to bootloader/recovery.

Never substitute `fastboot boot` for proof of persistent compatibility. Some bootloaders reject it; some temporary boots exercise a different path from flashing.

## Analyze local artifacts

Run:

```sh
python3 scripts/inspect-image.py path/to/image.img --pretty
file path/to/image.img
sha256sum path/to/image.img
```

Use dedicated upstream tools when available: `unpack_bootimg`, `magiskboot`, `avbtool`, `lpdump`, `lpunpack`, `simg2img`, `payload-dumper-go`, `mkdtimg`, `dtc`, `fsck.erofs`, `debugfs`.

Preserve originals. Write derived artifacts to a separate lab directory. Never repack over the only stock copy.

## Debug by last completed stage

Name the last observed stage before changing anything:

- no USB enumeration / no bootloader: Boot ROM, primary bootloader, power, storage, or hardware;
- bootloader available: image acceptance, partition, slot, signing, rollback, or kernel load;
- logo then reboot: kernel, DTB/DTBO, vendor ramdisk, modules, early mount, AVB;
- boot animation: init services, SELinux, framework, data migration, module injection;
- UI with failures: HAL, framework service, app, permissions, or performance.

Collect evidence according to [references/debugging.md](references/debugging.md). Change one variable per boot attempt.

## Build discipline

Pin source revision, toolchain, configuration, and input artifacts. Record build commands and hashes. For kernel work, match architecture, KMI, symbol list, module ABI, page size, compression, DT inputs, boot header, and vendor module set. For AOSP/ROM work, match device tree, kernel, vendor blobs, VINTF, SELinux, filesystem formats, partition sizes, and AVB configuration.

## Completion criteria

A plan is complete only when it states compatibility evidence, unresolved assumptions, expected observations, failure boundary, and recovery path. A build is complete only when artifacts are identified and hashed. A boot test is complete only when logs and result are captured against the hypothesis.
