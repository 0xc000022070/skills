---
name: jetson-nixos
description: Run NixOS on NVIDIA Jetson hardware via jetpack-nixos — cross-compile an aarch64 installer image from x86_64, pick a JetPack major version and reconcile it with the QSPI firmware, install to NVMe with disko, and keep a console on a board whose HDMI carries no Linux console. Use when building a Jetson installer ISO, choosing between JetPack 5/6/7, deciding whether a recovery-mode QSPI flash is actually required, fighting an EDK2 firmware build that fails on nixpkgs-unstable Python packages, diagnosing a board that boots partway and then throws mmc I/O errors, installing to NVMe on an Orin Nano or Orin Nano Super devkit, recovering a board that pings but answers on no port, or locked out of one whose password nobody knows. Specific to Orin where it matters; the boot, console and media reasoning generalizes across Tegra.
allowed-tools: Read Grep Glob Edit Write Bash(nix:*) Bash(lsusb:*) Bash(lsblk:*) Bash(sha256sum:*) Bash(efibootmgr:*) Bash(dmesg:*) Bash(free:*) Bash(df:*)
disable-model-invocation: false
metadata:
  author: Luis Quiñones
  version: "1.1.0"
  category: nix
---

# NixOS on Jetson

Upstream: https://github.com/anduril/jetpack-nixos — one flake providing
`hardware.nvidia-jetpack.*`, the L4T kernel, the EDK2 firmware build and the
flash scripts. Read the `som`, `carrierBoard` and `majorVersion` options before
anything else: they select a different kernel, a different firmware and a
different set of failure modes.

Bring-up is a chain of falsifiable states. Do not claim a rung you have not
observed, and do not infer a later rung from an earlier one.

## Bring-up ladder

| Rung | Proven by |
|---|---|
| Image builds for aarch64 from an x86_64 host | artifact exists, no qemu in the build log |
| Medium written | `sha256sum` of the *block device*, read back, equals the image |
| Medium sound at the target's bus speed | the board reads past early boot — a host-side readback proves nothing |
| Firmware accepts the image | it boots instead of landing in the Boot Manager |
| Kernel reaches userspace | something answers on `ttyTCU0` or on the network |
| Target disk laid out | `lsblk` on the target shows the disko layout mounted at `/mnt` |
| Closure installed | `/mnt/nix/var/nix/profiles/system` resolves to a store path |
| Boot entry written | `efibootmgr` shows an entry whose PARTUUID matches the real ESP |
| Installed system boots unaided | the install medium is removed and it still comes up |
| Installed system is reachable | a **port answers** — ping is not a rung |
| You can get in | a credential authenticates — a port answering is not a login |
| Firmware major matches kernel major | `nixos-install` reports Current == Expected |

The last rungs are separated from "it boots" deliberately. A Jetson that
completed an install, boots from NVMe, and answers ICMP can still be a board you
cannot get into at all, because nothing on it listens and its only console is a
serial line you did not wire. A board that does listen and rejects every
credential you have is the same dead end one step later. Both states are common
and neither is a partial success.

## Route the work

| Task | Read |
|---|---|
| Cross-compiled installer image, EDK2 firmware failing on nixpkgs Python | [installer-image.md](references/installer-image.md) |
| JetPack/L4T/kernel versions, QSPI, `autoUpdate`, recovery mode, UEFI entries | [firmware-and-boot.md](references/firmware-and-boot.md) |
| No console on HDMI, `ttyTCU0`, Type-C device mode, unknown password, login managers fighting over tty1, moving sshd off 22 | [console-and-access.md](references/console-and-access.md) |
| SD cards that fail only on the board, mmc errors, disko, NVMe, OOM during install | [storage-media.md](references/storage-media.md) |

## Hard rules

- **A recovery-mode QSPI flash is a fallback, not a prerequisite.** Measured on
  an Orin Nano Super devkit: QSPI at `36.4.4` (JetPack 6) booted a JetPack 7
  installer — kernel `6.8.12`, L4T `39.2.0` — to userspace and completed a full
  install to NVMe. Upstream's warning that JetPack 5 firmware cannot run a
  JetPack 6 kernel does not generalize to every pair. Try the card first;
  reaching for the USB-C cable before you have a failed boot costs hours.
- **Enable `services.openssh` in the installed configuration, not only in the
  ISO.** The installer image ships sshd and avahi; a target config that inherits
  neither produces a board that installs perfectly and is then unreachable.
  Decide the console story before the install, not after.
- **Use `hashedPassword`, not `initialHashedPassword`.** The latter applies only
  when the account is created, so a wrong or unrecorded hash cannot be fixed by
  any later rebuild. Pair it with `users.mutableUsers = false` so the flake owns
  `/etc/shadow` and the credential is reproducible. Recovering with `init=/bin/sh`
  and `passwd` fixes one board and proves nothing about the configuration.
- **Declare one login manager.** greetd claims tty1 and silently displaces
  `services.getty.autologinUser`, removing the passwordless door with no warning.
  lightdm sits on tty7 and coexists.
- **The install script baked into the image and the flake it clones have
  different ages.** Pushing a fix to the script does not reach a card that was
  already written; only `configuration.nix` and friends are fetched fresh.
- **Never verify an install by reading `/mnt/etc`.** Those are symlinks to
  absolute `/nix/store` paths and resolve into the *installer's* store. Compare
  `system.build.toplevel` against the installed profile instead — one
  content-addressed path settles it.
- **A host-side readback does not prove a card is good.** USB readers negotiate
  High Speed at 50 MHz; the Tegra controller runs UHS-I SDR104 at 208 MHz.
  Downgraded NAND passes the first and fails the second. `sha256sum` through a
  reader rules out capacity fraud and nothing else.
- **disko creates the swap partition and does not activate it.** Run `swapon`
  yourself before `nixos-install`, or the kernel's LTO link steps OOM on an 8 GB
  board.
- Measure the effect, not the abstraction. `efibootmgr` output over
  `canTouchEfiVariables`, a PARTUUID compared against `lsblk` over "systemd-boot
  said it installed", a port that answers over a unit that is `active`.
- One variable per boot attempt. A board that changed firmware, card and config
  and then failed produces no information.
- `connection refused` and `connection timed out` are different diagnoses.
  Refused means nothing listens. Timed out means a firewall dropped it. Do not
  merge them into "SSH is broken".
- Pin `cudaCapabilities` to the board's real compute capability (`"8.7"` on
  Orin). Leaving it unset builds every architecture.
- The vendor kernel and the L4T out-of-tree modules will rebuild **on the
  device** even when the ISO was cross-compiled, because the native and cross
  derivations hash differently. Budget one to two hours and do not read it as a
  configuration error.

## Verify commands

```sh
nix build .#packages.x86_64-linux.installer-iso     # cross-built, no qemu
nix eval .#nixosConfigurations.<host>.config.services.openssh.enable
nix eval .#nixosConfigurations.<host>.config.networking.firewall.allowedTCPPorts

# medium: compare the device, not the file you just wrote
sudo sh -c 'head -c $(stat -c %s img.iso) /dev/sdX' | sha256sum
sha256sum img.iso
sudo f3probe --destructive /dev/sdX                 # real vs announced capacity

# target, from the installer
lsblk -o NAME,PARTUUID,PARTLABEL,SIZE /dev/nvme0n1
swapon --show                                       # empty after disko is the bug
ls -l /mnt/nix/var/nix/profiles/                    # `system` symlink = installed
sudo efibootmgr                                     # entry PARTUUID vs the ESP

lsusb | grep 0955                                   # 7523 = recovery, 7020 = gadget
ls /dev/ttyACM*                                     # host end of the ACM console

# what was installed, without reading /mnt/etc into the wrong store
nix eval --raw .#nixosConfigurations.<host>.config.system.build.toplevel
readlink -f /mnt/nix/var/nix/profiles/system        # equal = same closure

pgrep -af "[i]nfect"                                # bare -f matches your own ssh line
```

## Completion criteria

State the rung reached, the evidence, and the access path that survives a
reboot. Report the firmware version transition explicitly: whether the QSPI was
upgraded, whether it is scheduled for the next boot, and whether power was held
through it.

Do not report an install as finished while the only way back into the board is
the medium you are about to remove, or while the credential that opens it is one
nobody has tested.
