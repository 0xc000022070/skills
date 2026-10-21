# Device-family routing

## Contents

- Universal rule
- Pixel
- Samsung
- Xiaomi/Redmi/POCO
- OnePlus
- Motorola
- Sony

## Universal rule

These are routing hints, not commands. OEM behavior varies by generation, carrier, region, SoC, and bootloader revision.

## Pixel

Use official factory/full OTA images and exact codename. Modern Pixels use A/B, dynamic partitions, GKI, init_boot on newer generations, AVB and rollback protection. Check current factory-image notices: some bootloader updates raise anti-rollback and require both slots to receive a current coherent build. Full OTA sideload is often safer for stock recovery than factory flashing.

## Samsung

Uses Download Mode and Odin protocol rather than normal fastboot for consumer flashing. Firmware packages split BL/AP/CP/CSC; Magisk upstream patches the exact AP archive. Model suffix, region/CSC, bootloader binary revision and SoC matter. Bootloader unlock availability varies sharply; Knox warranty fuse changes can be irreversible. Never apply generic fastboot partition commands.

## Xiaomi, Redmi, POCO

Unlock policy and waiting/account requirements are volatile and region-dependent. Qualcomm and MediaTek variants under the same family can have different recovery paths. Match codename and anti-rollback index. Fastboot ROM and recovery ROM are different package types. EDL access commonly requires authenticated service credentials on modern devices.

## OnePlus

Many models expose fastboot, but modern Qualcomm devices also use dynamic partitions and vendor-specific restore packages. Regional conversions and modem/bootloader mismatches can break radio or boot. MSM/EDL tools are generation-specific and may require authorization.

## Motorola

Official unlock eligibility varies by model/carrier. Firmware packages and blankflash recovery are exact-device/bootloader artifacts. Match product/board, channel, SKU, bootloader revision and radio. Do not treat blankflash as universal partition access.

## Sony

Official Open Devices resources cover supported models and AOSP configurations. Unlock eligibility is device/variant-specific. Unlocking can erase DRM keys and affect camera or proprietary features on some generations. Record exact model identifier, not only Xperia family name.
