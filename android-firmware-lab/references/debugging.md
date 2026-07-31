# Boot and firmware debugging

## Contents

- Evidence sources
- Failure-stage matrix
- Kernel and init diagnosis
- Display output diagnosis
- SELinux
- Experiment loop

## Evidence sources

Collect what survives the failure mode:

- `adb logcat -b all -v threadtime` during boot when adbd appears;
- `dmesg` on debuggable/rooted builds;
- `/sys/fs/pstore/console-ramoops*`, `pmsg-ramoops*`, `dmesg-ramoops*` after reboot;
- bootloader variables and screen messages;
- `getprop ro.boot.bootreason`, `sys.boot.reason`, bootconfig and cmdline;
- recovery logs and last_kmsg on legacy devices;
- `init` service status, tombstones, ANRs, dropbox, `dumpsys`;
- AVB state and `avbtool` descriptor output;
- serial console or ramoops for bring-up hardware when available.

Capture host timestamps and exact candidate hash.

When recovery boots but ADB never enumerates, read [recovery-bringup.md](recovery-bringup.md). Instrument persistent capture before the next boot with `scripts/collect-recovery-diagnostics.sh`; a requirement to collect logs is not actionable without an evidence transport.

## Failure-stage matrix

| Observation | Likely domain | First checks |
|---|---|---|
| No enumeration, no bootloader | Boot ROM/PBL, power, storage, hardware | cable/power, SoC recovery mode, OEM recovery tooling |
| Bootloader rejects image | lock/signature/rollback/format/size | exact error, product, unlock, header, AVB, anti-version |
| Immediate return to bootloader | no valid bootable slot/image | slot metadata, image load, AVB, partition target |
| Static logo then watchdog reboot | kernel/DT/vendor_boot/modules | ramoops, kernel release, KMI, DT, ramdisk compression |
| Recovery boots but Android does not | Android init/mount/data/AVB | fstab, logical partitions, encryption, SELinux, logs |
| Boot animation loops | services/framework/data migration/modules | logcat all buffers, init services, system_server crashes |
| UI boots with missing hardware | HAL/VINTF/vendor/kernel driver | service list, VINTF, dmesg, vendor blobs/modules |
| Random reboot under load | kernel panic, thermal, power, memory | pstore, thermal logs, tombstones, stress isolation |

## Kernel and init diagnosis

For kernel failure, preserve the first panic/oops, not only the final reboot. Check exception, call trace, taint, loaded modules, command line, and preceding storage/IOMMU/driver errors.

For init failure, inspect exact action/service, return status, restart count, mount error, property trigger, executable context, capabilities, and SELinux denial. Do not edit rc files until the failing dependency is known.

## Display output diagnosis

A dark or partially painted panel is not one failure. Separate the panel, the
framebuffer, the console binding, compositing, the palette, and the backlight
before changing anything. A lit backlight showing nothing and a dark panel
rendering correctly are opposite bugs that look identical.

Quantify the framebuffer instead of describing it. **Enumerate the distinct
32-bit values in one framebuffer page**; the cardinality is the diagnosis.

| Distinct values | Reading |
|---|---|
| 1, all zero | nothing rendered, or rendered through a zeroed palette |
| 2, one of them `0xAAAAAA` | a text console is drawing correctly; VGA light grey is its default foreground |
| many, row-structured | something draws; suspect stride, pixel format, or panning |
| many, unstructured | uninitialised memory being scanned out |

Counting "non-black pixels" cannot distinguish the first two rows and reads as
zero for the most common downstream bug.

Read the page at the driver's reported `line_length`/stride, not at
`xres * bpp/8`; padded strides are normal and slicing at the wrong pitch turns
readable output into diagonal noise. Check `virtual_size` too — the page being
scanned out is not necessarily page 0.

For the fbdev-specific failure modes behind each of these — missing
`.fb_setcolreg`, a console driver that never binds a VT, a driver that only
composites on `FBIOPAN_DISPLAY`, and DSI command backlights that ignore repeated
values — use skill `mobile-nixos-port`.

## SELinux

Keep enforcing during normal validation. An AVC denial is evidence, not automatic permission to add an allow rule. Determine source context, target context, class, permission, expected ownership boundary, and whether labeling/configuration is wrong. Broad allows hide integration errors and can violate neverallow constraints.

## Experiment loop

1. State one falsifiable hypothesis.
2. Change one artifact or configuration dimension.
3. Hash candidate.
4. Boot using least persistent supported route.
5. Capture logs from power-on through result.
6. Compare against previous attempt.
7. Revert or promote based on evidence.

Do not clear logs before copying the only useful crash record.
