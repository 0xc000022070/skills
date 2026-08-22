---
name: mobile-nixos-port
description: Port Mobile NixOS to an Android phone or tablet — package a downstream vendor kernel in Nix, build an Android boot image the bootloader accepts, bring up stage-1 (framebuffer console, backlight, USB gadget, SSH), and diagnose an initramfs that boots but shows nothing. Use when adding a device to a mobile-config-style ports repo, writing or debugging stage-1 mruby tasks, wiring mobile.* options, fighting fbdev/mtkfb or a SoC with no KMS driver, keeping a vendor and a mainline kernel tree buildable for the same device, writing the single-process on-panel dashboard that a few hardware keys drive, running modern systemd on a pre-5.x kernel, chasing a device that switch_roots and then goes silent with no logs, reaching a device that boots clean yet is unreachable or ignoring its own network config, giving a driverless device internet through the build host, starting a vendor driver that is built in but never registers itself, provisioning proprietary firmware blobs, or keeping a ported device running unattended — self-rolling-back deploys, journal and store growth, sizing services for a phone, and remote management over a VPN. For stock Android artifacts, AVB, recovery trees, GKI/KMI, SoC download modes and root solutions, use android-firmware-lab.
allowed-tools: Read Grep Glob Edit Write Bash(nix:*) Bash(adb:*) Bash(fastboot:*) Bash(sha256sum:*) Bash(file:*)
disable-model-invocation: false
metadata:
  author: Luis Quiñones
  version: "1.4.0"
  category: nix
---

# Mobile NixOS device ports

Reference implementation: https://github.com/0xc000022070/mobile-config — one
Nix flake, a device registry, per-device kernel pins, patches grouped by the
tree they apply to. Read the device README before touching any device: it
records the exact hardware/firmware tuple the port was written against.

A port is a chain of falsifiable states. Do not skip a rung, and do not claim a
rung you have not observed.

## Bring-up ladder

| Rung | Proven by |
|---|---|
| Kernel builds for the target arch | artifact exists, `file`, hashes recorded |
| Image geometry matches stock | unpacked header report vs stock, fits partition |
| Bootloader accepts the image | it boots instead of returning to fastboot |
| Kernel reaches stage-1 init | any observation channel produces output |
| Observation channel is bidirectional | serial, USB gadget, or SSH shell |
| Panel shows readable console | text on the panel, not just a lit backlight |
| Stage-2 switch_root | a rootfs exists and is found by label |
| PID 1 reaches a service manager | a unit ran — journal on disk, or adbd back after handoff |
| Stage-2 configuration applied | the *effect* is observed: `ip route`, a resolved name, a reachable port |
| Session starts | the UI is on the panel and takes input |

Each rung has its own failure domain. Naming the last rung you actually reached
is the whole of the debugging method; guessing past it wastes boot attempts.

The last rungs are separated deliberately. `switch_root` succeeding proves the
rootfs is readable and the label resolved — it proves nothing about systemd
starting, and a PID 1 that freezes in its own startup path leaves a device that
is warm, powered and silent. "It boots" is not a rung.

Nor is `systemctl is-system-running` = `running`. A device reaches that state,
with zero failed units, while its network configuration was never applied —
units whose conditions were not met are *skipped*, and skipped is not failed.
The rung is the effect, never the unit.

## Route the work

| Task | Read |
|---|---|
| Flake, device registry, kernel derivation, keeping a vendor and a mainline tree buildable, boot image, patch discipline | [nix-packaging.md](references/nix-packaging.md) |
| Write or debug a stage-1 task, recovery-resident boot selector, USB gadget, networking, SSH, logs | [stage-1.md](references/stage-1.md) |
| Black panel, white band, lit-but-blank, no KMS, fbcon, backlight, blanking the panel, keeping printk off a console TUI, writing the dashboard that repaints it | [display-bringup.md](references/display-bringup.md) |
| systemd/udev failing on a 4.x kernel, missing syscalls, PID 1 freezing silently, a udev that tags nothing so logind and hotkeys go dead | [old-kernel-userspace.md](references/old-kernel-userspace.md) |
| Device drops off USB at handoff, no logs, writing a rootfs over adb | [device-debugging.md](references/device-debugging.md) |
| Booted but unreachable, no default route, declarative config ignored, ssh/mDNS, giving a device internet through the build host | [stage-2-access.md](references/stage-2-access.md) |
| A driver that is built in but never starts, a vendor loader daemon, proprietary firmware blobs, register dumps on a gated block | [vendor-drivers.md](references/vendor-drivers.md) |
| Leaving it running: deploys that can undo themselves, journal and store growth, sizing services, wifi credentials, VPN for remote management | [production.md](references/production.md) |
| Stock artifacts, AVB, partition maps, recovery trees, rooting | skill `android-firmware-lab` |

## Hard rules

- Flash to `recovery`, not `boot`, for the whole of stage-1 bring-up. A working
  Android `boot` is the way back from every experiment. Never write `super` or
  `userdata` before stage-1 is repeatable.
- A stage-1 boot menu runs after the bootloader has selected and loaded a
  kernel. Treat it as recovery policy, not GRUB. Do not claim it can select
  Android, another kernel or another NixOS generation until that exact
  transition and its return path have both run on the device.
- A raw kernel in `recovery` is not itself a safety net. It is one while the
  kernel reaches stage-1, because stage-1 gives back a channel; a kernel from an
  untested lineage that panics before userspace leaves no ADB, no gadget, no
  console and no logs, and the only way back is the SoC download mode. Before
  flashing a lineage that has never run on the hardware, put a real recovery
  there first and confirm it boots — a recovery with its own ADB can rewrite the
  partition from the device. Keep a hash-verified copy of what the partition
  held, taken by reading the partition back, not reconstructed from the build.
- One variable per boot attempt. A boot that changed three things and failed
  produces no information.
- Pin the kernel by revision and hash, never by branch. Vendor forks rebase.
- The defconfig you ship is the *input*. Mobile NixOS layers structured config
  on top and overrides symbols (`RD_GZIP`, `FRAMEBUFFER_CONSOLE`,
  `CONFIG_LOCALVERSION`, …). Reasoning about runtime behaviour from the
  checked-in config file produces confident wrong answers. Enable
  `CONFIG_IKCONFIG` and read `/proc/config.gz` off the running device.
- Every patch header records the measurement that motivated it — the boot
  attempt, the file:line, the observed value. A patch whose header only states
  intent cannot be re-audited later.
- Do not use `mobile.boot.stage-1.ssh.enable`. Upstream documents it as opening
  root access with no password and no key. Write a task that runs dropbear with
  `-s` and an explicit `authorized_keys`.
- A build is not a boot. A boot is not an installation. One hardware revision
  proves nothing about another. A unit that ran is not an effect that happened.
- Any switch that can break the only transport must be able to undo itself. Arm
  a rollback timer before the switch and confirm it from the host only after the
  device answers again — a device that is gone confirms nothing and is rolled
  back by the generation it just replaced.
- Establish the device's idle baseline before reading any metric as a fault. A
  vendor kernel parks dozens of threads in D state, so a load average in the
  twenties can be a healthy device doing nothing.
- Measure the effect, not the abstraction that was supposed to produce it. `ip
  route` over `networking.defaultGateway`, a resolved name over an active
  `avahi-daemon`, a re-read of the block device over the page cache that just
  served the write.
- Deploy whole images. Hand-swapping individual components of a patched systemd
  between builds freezes PID 1 with no log and costs a reflash.
- Never turn a panel off through `/sys/class/graphics/fb0/blank`. On mtkfb the
  write deadlocks the driver and every framebuffer refresher with it, and the
  only way out is a power cycle. Drive the backlight LED instead.

## Verify commands

```sh
nix build .#<device>-boot-img -L
nix build .#<device>-kernel -L
nix eval .#packages.x86_64-linux --apply builtins.attrNames

unpack_bootimg --boot_img result --out /tmp/unpacked   # geometry vs stock
sha256sum result
stat -c %s result                                      # vs measured partition size

adb shell 'reboot bootloader'      # `adb reboot bootloader` fails on some MTK
fastboot flash recovery result
fastboot reboot recovery           # `fastboot oem reboot-recovery` often absent
```

x86_64 cross-compiles; both `x86_64-linux` and `aarch64-linux` are built. A cold
build fetches on the order of a gigabyte per device.

## Adding a device

1. `devices/<vendor>-<codename>/` with `default.nix` (identity, boot image
   geometry, cmdline, USB) and `kernel/` (source pin, toolchain, defconfig).
2. Register it in the `devices` attrset in `flake.nix`. Do not add a flake
   `default` output — a bare `nix build` must not silently build the wrong phone.
3. Write the device README before the first flash: exact model, codename, SoC,
   hardware revision, panel, touch controller, kernel release, firmware build
   and SPL, verified-boot state, slot scheme.
4. Anything shared moves to `modules/` only once a second device needs it. Split
   by lifetime, not by device: kernel-version quirks follow the kernel version,
   SoC quirks follow the SoC, panel quirks stay with the device.

## Completion criteria

State the rung reached, the evidence that proves it, the unresolved assumptions,
and the restore path. Report untested hardware as untested — touch, Wi-Fi,
audio, modem, charging and suspend are not implied by a console.

Keep `supportLevel = "broken"` until each of those has been exercised, and say
in the device file what it marks: what is *untested*, not what is failing. A
port that boots to a clean multi-user system with a shell over the network is
still broken by that definition, and describing it accurately is what stops the
next reader from trusting a rung nobody climbed.
