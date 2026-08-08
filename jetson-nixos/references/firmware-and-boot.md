# Firmware, JetPack versions and boot

## The version tuple

`hardware.nvidia-jetpack.majorVersion` selects a whole stack, not a flag.

| JetPack | L4T | Kernel |
|---|---|---|
| 5 | 35.x | 5.10.216 |
| 6 | 36.x (36.5.0) | 5.15.185 |
| 7 | 39.2.0 | 6.8.12 |

Orin defaults to JetPack 6 in jetpack-nixos. Setting `majorVersion = "7"` moves
the kernel from 5.15 to 6.8 and the firmware from 36.x to 39.2.0. State the
tuple in a comment next to the option; a bare `"7"` tells the next reader
nothing.

## Where the firmware lives

The UEFI/EDK2 bootloader sits in a **QSPI flash chip on the module**, not on the
removable medium. Rewriting the boot card does not touch it. This is the source
of most confusion about Jetson boot failures: the thing that reads your card is
persistent state you did not write.

On all recent Jetsons **except Xavier AGX**, that same QSPI also stores the UEFI
runtime variables. Two consequences:

- `boot.loader.efi.canTouchEfiVariables = true` is correct on Orin.
  systemd-boot writes real NVRAM entries and `efibootmgr` shows them.
- A firmware upgrade rewrites the region those variables live in. Boot entries
  can disappear across an upgrade. Do not spend effort tidying NVRAM
  immediately before a scheduled firmware update.

## Firmware/kernel compatibility — what is actually true

Upstream warns that JetPack 5 firmware cannot run a JetPack 6 kernel. That
warning is real for that pair. It does **not** generalize.

Measured, Orin Nano Super devkit:

```
Current firmware version is : 36.4.4-f85213c1daaf     <- JetPack 6
Expected firmware version is: 39.2.0-31f5340ece70     <- JetPack 7
```

That board booted a JetPack 7 installer image (kernel 6.8.12) from SD on the
JetPack 6 firmware, reached userspace with networking and mDNS, and completed a
full `nixos-install` to NVMe. The firmware was never the blocker.

**Method:** write the card, try to boot it, and only reach for the flash path
once you have an observed failure. Recovery mode costs a cable, a host, physical
access to the jumper and a long uninterruptible write.

## In-band QSPI upgrade

```nix
hardware.nvidia-jetpack.firmware.autoUpdate = true;
```

With this set, `nixos-install` prints the Current/Expected pair above and
schedules the QSPI write for the **first reboot of the installed system**:

```
An update for Jetson firmware will be applied during the next reboot.
The next reboot may take an extra 5 minutes or so.
Do not disconnect power during the reboot, or the firmware upgrade will not
be applied
```

This is the path that does not need a host, a cable or recovery mode. Plan the
first reboot around it: the board will appear to hang for minutes. Hold power.

## Recovery mode

The fallback when the board genuinely will not boot any medium.

1. Hold `FC_REC` (the recovery pin/jumper) while applying power.
2. Release after ~2 seconds.
3. Confirm on the host: `lsusb | grep 0955:7523`.
4. Run the flash script built from the *same* configuration the medium expects,
   so the firmware and kernel agree:

```nix
flash-firmware = self.nixosConfigurations.installer.config.system.build.flashScript;
```

`FC_REC` is sampled by the **boot ROM**, before any firmware runs. The path
therefore does not depend on the QSPI contents being valid, which is what makes
an interrupted flash retryable rather than fatal. Say this out loud when someone
is scared to start one.

Take the flash script from the installer configuration rather than a generic
jetpack output, so it writes exactly the firmware version the image was built
against.

## Boot entries after an install

systemd-boot writes both a UEFI variable entry and the removable-media path.
Verify the variable entry against the actual ESP rather than trusting the log:

```sh
lsblk -o NAME,PARTUUID,PARTLABEL /dev/nvme0n1
sudo efibootmgr
```

The entry's `HD(1,GPT,<uuid>,…)` must carry the ESP's PARTUUID. Two things go
wrong routinely:

- **Stale entries accumulate.** Every reinstall creates a new ESP with a new
  PARTUUID and leaves the previous `Linux Boot Manager` entries behind. A board
  reinstalled a few times shows a dozen, all but one pointing at partitions that
  no longer exist.
- **BootOrder can leave the install medium first.** `UEFI SD Device` ahead of
  the NVMe entry means the next boot goes back into the installer. Remove the
  medium rather than reordering NVRAM that a pending firmware upgrade may reset.

`\EFI\BOOT\BOOTAA64.EFI` is the removable-media fallback and systemd-boot
installs it alongside the variable entry. It is found by device-path autoboot
with no NVRAM involvement, which makes it the thing that still works after a
firmware upgrade clears the variable store. Confirm it exists before you rely on
the NVRAM entry:

```sh
ls -l /mnt/boot/EFI/BOOT/BOOTAA64.EFI
```

## Reading the failure

| Symptom | Domain |
|---|---|
| No UEFI output on HDMI at all | power, module seating, dead firmware — recovery mode |
| UEFI renders, no medium offered | medium not written, wrong partition scheme, unreadable card |
| Medium boots, kernel panics early | firmware/kernel major mismatch is *plausible* here, and only here |
| Boots hundreds of MB in, then I/O errors | the medium — see [storage-media.md](storage-media.md) |
| Reaches userspace, unreachable | configuration — see [console-and-access.md](console-and-access.md) |

The third row is the only one where the firmware version is a good first
hypothesis. Reaching for it from the fourth or fifth row is the expensive
mistake.
