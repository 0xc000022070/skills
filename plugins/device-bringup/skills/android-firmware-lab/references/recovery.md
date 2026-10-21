# Recovery planning

## Contents

- Recovery assets
- Failure classes
- Slot recovery
- Module bootloops
- Alternative-OS boot selection
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

## Alternative-OS boot selection

A selector inside a recovery or alternative-OS initramfs runs after the
bootloader has loaded that kernel. It is not a bootloader menu. Selecting
another boot partition requires a reboot through a mechanism the concrete
bootloader implements. Selecting another kernel additionally requires proven
`kexec` support or a flash-and-reboot workflow.

Map the boot-control state before designing the menu:

- locate the bootloader message by partition name, not a remembered block index;
- save the original bytes and document the writable field boundary;
- record every accepted command and whether it is persistent or one-shot;
- read the field before and after `fastboot reboot recovery`, OEM reboot
  commands and recovery boots;
- prove how the device returns to the selector after every offered choice.

Do not infer `misc`. Some vendor bootloaders store the bootloader message in a
different partition. Do not infer one-shot behaviour from a command name. A
persistent recovery request can create a reset loop, while clearing it to boot
Android can make the selector disappear on later power-ons.

Treat storage coexistence separately from boot selection. If an alternative OS
reformatted Android `userdata`, starting Android may reformat it again and erase
the alternative root. Call that a destructive handoff, not dual boot. Offer
Android only after separate data storage, a compatible shared format, or exact
stock mount and format behaviour has been demonstrated.

Replacing the primary bootloader to gain a menu is not an ordinary porting
step. Require a device-specific authenticated restore path that does not depend
on the bootloader being replaced.

## Limits

No generic skill can recover overwritten bootloader, partition table, modem calibration, EFS/NV, RPMB, or hardware fuses. These are SoC/OEM-specific and often require authenticated service tooling. Do not modify calibration, identity, or secure storage as part of ordinary rooting or ROM work.
