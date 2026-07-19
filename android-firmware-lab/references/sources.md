# Sources and refresh map

Bundled references contain stable operational knowledge. Use these sources when a volatile fact must be refreshed.

## AOSP primary sources

- https://source.android.com/docs/core/architecture/bootloader/boot-image-header
- https://source.android.com/docs/core/architecture/partitions
- https://source.android.com/docs/core/architecture/partitions/dynamic-partitions
- https://source.android.com/docs/security/features/verifiedboot/avb
- https://android.googlesource.com/platform/external/avb/
- https://android.googlesource.com/platform/system/tools/mkbootimg/
- https://android.googlesource.com/platform/system/extras/+/master/partition_tools/
- https://source.android.com/docs/core/architecture/kernel/generic-kernel-image
- https://source.android.com/docs/setup/build/building-kernels
- https://source.android.com/docs/security/features/selinux
- https://android.googlesource.com/platform/system/core/+/master/init/README.md
- https://developer.android.com/tools/releases/platform-tools

## Upstream root/tool sources

- https://github.com/topjohnwu/Magisk and `docs/`
- https://kernelsu.org/guide/ and https://github.com/tiann/KernelSU
- https://apatch.dev/ and https://github.com/bmax121/APatch
- https://github.com/LSPosed and https://github.com/libxposed
- https://github.com/ssut/payload-dumper-go
- https://github.com/chenxiaolong/avbroot
- https://github.com/osm0sis/AnyKernel3

## Device and recovery sources

- Pixel factory images: https://developers.google.com/android/images
- Pixel full OTA images: https://developers.google.com/android/ota
- Sony Open Devices: https://opendevices.sony.net/
- Samsung Open Source: https://opensource.samsung.com/
- Motorola source: https://github.com/MotorolaMobilityLLC
- Xiaomi kernel source: https://github.com/MiCode/Xiaomi_Kernel_OpenSource
- OnePlus source: https://github.com/OnePlusOSS
- Nothing source: https://github.com/NothingOSS
- LineageOS devices: https://wiki.lineageos.org/devices/
- TeamWin devices: https://twrp.me/Devices/

## Refresh triggers

Re-check live source for current release numbers, supported Android/kernel versions, OEM unlock availability, anti-rollback advisories, firmware downloads, device maintainer status, recent partition changes, and root-detection/attestation behavior.

Community indexes such as `awesome-android-root`, XDA, Reddit, Telegram, and 4PDA are discovery and incident sources. Corroborate their claims against device evidence or upstream material before using them operationally.
