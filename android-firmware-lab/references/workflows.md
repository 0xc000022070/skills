# Firmware workflows

## Contents

- Initialize a lab
- Acquire stock artifacts
- Analyze
- Temporary boot
- Root selection
- Persistent execution record

## Initialize a lab

Create one directory per device/build:

```text
lab/<codename>/<fingerprint-or-build>/
  profile/
  stock/
  extracted/
  build/
  candidate/
  logs/
  recovery/
```

Keep `stock/` immutable. Store hashes beside artifacts. Record host tool versions. Do not mix artifacts from different firmware builds in one candidate.

## Acquire stock artifacts

Prefer exact OEM factory package or full OTA. Next prefer the exact ROM maintainer package. On rooted/test devices, partition reads can confirm deployed content, but inactive slots and logical mappings complicate interpretation.

Extract package first. Do not use another user's patched boot image. For incremental OTA, acquire its exact source build or use a full package.

## Analyze

1. Inventory device.
2. Inventory firmware package.
3. Build partition/artifact table.
4. Inspect boot headers and AVB descriptors.
5. Map slot and dynamic partition behavior.
6. Identify kernel/KMI, modules, DT, page size, compression.
7. State compatible, incompatible, or unknown for every required dimension.

## Temporary boot

Temporary boot is preferred when the bootloader implements `fastboot boot` for the artifact type.

Before attempting it:

- verify exact selected serial;
- verify unlocked state and product/codename;
- verify image size/type/header and provenance;
- keep stock image and recovery route available;
- start a log capture plan;
- know that some devices do not support temporary boot.

After boot, confirm running kernel, fingerprint, slot, verified-boot state, hardware function, storage mount, SELinux, and logs. A successful temporary boot does not automatically authorize persistent flashing.

## Root selection

Use Magisk for userspace/systemless root and broad device support. Use KernelSU when kernel integration, GKI/LKM compatibility, and app profiles fit the device. Use APatch only when its ARM64/kernel requirements and boot-image model fit. Use LSPosed only for ART hooking after a root foundation exists.

Patch on the target device when upstream requires it. Preserve the unpatched exact stock artifact. Record root manager version and output hash.

## Persistent execution record

Generate commands only after resolving variables:

```text
serial:
mode: bootloader-fastboot | fastbootd | download | recovery
product/codename:
current slot:
target slot:
partition:
partition size:
input image and SHA-256:
stock restore image and SHA-256:
unlock/AVB/rollback state:
expected first-boot behavior:
success observations:
failure observations:
restore command/path:
```

Avoid command bundles that hide intermediate failure. Execute and verify one state transition at a time.
