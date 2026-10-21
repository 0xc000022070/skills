# Boot and firmware debugging

## Contents

- Evidence sources
- USB enumeration forensics
- A crashed download agent latches the SoC
- Brick taxonomy
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

## USB enumeration forensics

When a device offers no ADB, no fastboot and no stable download mode, the host's
USB log is the only instrument left. Read it as timing, not as error strings.

```
usb 3-1: new high-speed USB device number 54 using xhci_hcd
usb 3-1: device descriptor read/64, error -71
usb 3-1: Device not responding to setup address.
usb 3-1: device not accepting address 57, error -71
```

Two independent quantities live in that log and only one of them is about the
device:

- **the burst length** is the host's fixed retry ladder in `hub_port_init` — two
  descriptor reads per address, two addresses, then give up. It measures a
  constant ~2.3 s against any broken device and carries no information at all.
- **the interval between `new ... USB device` lines** is the device re-asserting
  its D+ pull-up on its own. That is the only device-side signal in the log.

Track the interval across attempts rather than reading any single burst:

| Interval trend | Reading |
|---|---|
| Growing monotonically | draining and never charging; the power path is not running |
| Shrinking | accumulating charge; the supply is reaching it |
| Fixed and short, matching the loop period | bootloop; USB init is reached each pass |
| No intervals, continuous failure while attached | link layer — cable, connector, host port |

A device that announces itself and then fails **every** control transfer has a
live pull-up and dead signalling. That is a contact fault *or* a controller left
half-initialized by crashed code; the log cannot separate them. Change the
cheapest variable and re-measure the interval.

Do not conclude "bad cable" or "dirty connector" when the same cable and port
enumerated cleanly earlier in the same session. A physical link does not degrade
on its own between two attempts minutes apart — check timestamps before
replacing hardware. What changed is far more likely the device's state.

Test host ports on **different controllers**, not different sockets. Several
sockets on one root hub are one test repeated. `lsusb -t` and
`lspci | grep -i usb` show which is which.

## A crashed download agent latches the SoC

A host flashing tool that uploads its agent and then fails does not leave the
device where it found it:

```
Sending emi data ...
DRAM setup failed: ...
Failed to upload da..
```

The agent already took the chip. The symptoms follow from that and are
diagnostic:

- black panel, no response to any key — mask-ROM and agent code do not read the
  keypad, so every long-press reset that relies on software is inert;
- the charging path never runs, because it lives in the primary loader and in
  the kernel and neither is reached. A wall charger changes nothing, and the
  device stays cold because it never leaves hardware pre-charge;
- therefore the battery drains monotonically, which is exactly the growing
  interval above.

Only removing power clears it. With no removable battery that means opening the
case and unplugging the battery connector. Nothing on the far side is listening,
so no software route exists.

Charge from a dumb 5 V source only *after* the latch is cleared. A device that
has not finished enumerating is capped at 100 mA by specification, so a host
port can never charge it out of a failing handshake — that trap is
self-reinforcing.

## Brick taxonomy

Classify by the lowest stage still executing, and say which one you mean rather
than saying "bricked":

| Observation | Lowest live stage | Route back |
|---|---|---|
| No electrical activity, ever | none | board-level repair |
| Periodic USB pull-up, all transfers fail | mask ROM, or an agent that crashed | cut power at the battery, then download mode |
| Stable download-mode enumeration | mask ROM or primary loader | host flashing tool |
| Bootloader or fastboot reachable | primary loader chain | reflash the failing partition |
| Logo then reboot | kernel load succeeded | reflash the kernel image |

A mask ROM is fixed at fabrication and no flash operation can erase it, so only
the first row is unrecoverable by firmware means. Periodic USB activity is
positive evidence that the silicon executes code.

## Failure-stage matrix

| Observation | Likely domain | First checks |
|---|---|---|
| No enumeration, no bootloader | Boot ROM/PBL, power, storage, hardware | host USB log interval trend, cable/power, SoC download mode, OEM recovery tooling |
| Enumerates repeatedly, every transfer fails | link layer, or a latched download agent | interval trend, controller change, power cut at the battery |
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
