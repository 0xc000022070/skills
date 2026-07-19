# Recovery planning

## Contents

- Recovery assets
- Failure classes
- Slot recovery
- Module bootloops
- Limits

## Recovery assets

Before experimentation, acquire exact stock firmware and identify routes to bootloader/download/recovery/SoC emergency mode. Preserve stock `boot`, `init_boot`, `vendor_boot`, `dtbo`, `vbmeta*`, and any device-specific bootloader package needed for restoration. Know whether OEM tools require accounts, signed packages, Windows, authorization, or online service.

A good recovery plan includes a second USB cable/port, charged battery, latest platform tools, correct drivers/udev rules, exact serial targeting, and commands tested only for discovery before the experiment.

## Failure classes

- Soft brick: bootloader or recovery remains reachable. Restore exact stock artifact/set.
- Slot failure: one slot fails while another coherent slot boots. Preserve good slot; inspect metadata before switching.
- Verification/data failure: boot reaches recovery or wipes due to AVB/encryption mismatch. Restore coherent signed set; do not repeatedly toggle flags.
- Bootloader failure: normal fastboot/download mode absent. Requires OEM/SoC-specific recovery and may require signed programmers.
- Hardware/storage failure: software flashing is not repair.

## Slot recovery

Slots are coherent sets. Restoring only `boot` can fail when `vendor_boot`, `dtbo`, `vbmeta`, system, or vendor differ. Record active slot before changes. Do not mark a slot successful until Android completes boot; boot control may decrement retries and fall back automatically.

Anti-rollback can make an older inactive slot unbootable after a bootloader update. Use current OEM notices and exact packages.

## Module bootloops

When a root module caused the failure, prefer framework-supported safe mode/removal. Magisk can remove modules through its supported command when ADB is available. KernelSU provides safe-mode/rescue behavior documented by its current release. Otherwise disable/remove the specific module from recovery only when its storage layout is known.

Restoring stock boot image removes boot-level injection but may leave module data. Do not delete root databases wholesale as first response.

## Limits

No generic skill can recover overwritten bootloader, partition table, modem calibration, EFS/NV, RPMB, or hardware fuses. These are SoC/OEM-specific and often require authenticated service tooling. Do not modify calibration, identity, or secure storage as part of ordinary rooting or ROM work.
