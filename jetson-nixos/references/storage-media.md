# Boot media and the install target

## Counterfeit and downgraded SD cards

The failure looks like this. The board boots — UEFI, kernel, initrd, hundreds of
megabytes read successfully — and then the console fills with:

```
mmcblk0: error -84 transferring data, sector ..., nr ...
blk_update_request: critical medium error, dev mmcblk0, sector ...
mmcblk0: recovery failed
```

Read each line for what it proves:

- `-84` is `-EILSEQ`: a CRC mismatch on the data lines. The command was
  understood and the payload came back corrupt.
- `critical medium error` is the block layer classifying it as the medium, not
  the link.
- `recovery failed` is the important one. Before printing it, the MMC layer
  already **retried and re-tuned to a lower bus speed**, and still failed.

That last point is what rules out the cheap explanations. A dirty or badly
seated card fails during the firmware's own reads, long before the kernel has
streamed hundreds of megabytes. If someone proposes cleaning the contacts after
`recovery failed`, the evidence already excludes it.

### Why it passes on your laptop

| Path | Bus mode | Clock |
|---|---|---|
| USB card reader | High Speed | 50 MHz |
| Tegra SD controller | UHS-I SDR104 | 208 MHz |

Reject or downgraded NAND — silicon that failed binning and was re-marked — is
stable at 50 MHz and falls apart at 208 MHz. A card can pass a full write-plus-
readback verification through a reader and be unusable on the board.

**So a host-side `sha256sum` readback does not prove the card is good.** It
proves the announced capacity is real, which excludes one specific fraud and
nothing else. Do the readback anyway — it is cheap and it catches the other
fraud — but do not treat it as a verdict:

```sh
sudo dd if=img.iso of=/dev/sdX bs=4M oflag=direct conv=fsync status=progress
sync; sudo blockdev --flushbufs /dev/sdX
echo 3 | sudo tee /proc/sys/vm/drop_caches      # or you re-read the page cache
sudo sh -c 'head -c $(stat -c %s img.iso) /dev/sdX' | sha256sum
sha256sum img.iso
```

Dropping the caches is not optional. Without it you are comparing the image to
itself.

### Testing capacity

```sh
sudo f3probe --destructive /dev/sdX
```

`Good news: The device '/dev/sdX' is the real thing` with usable equal to
announced clears capacity fraud. It does not clear speed-dependent failures,
because f3probe runs over the same 50 MHz reader.

### You cannot verify the brand through a reader

The manufacturer ID lives in the SD **CID register**. USB mass-storage bridges
do not expose it — the SCSI transport has nowhere to put it. Reading it needs a
native MMC host:

```sh
cat /sys/class/mmc_host/*/mmc*/cid
```

If the host has no SD slot, the brand printed on the card is unverifiable. Say
so rather than implying the card checked out.

### Practical rule

Two cards are diagnostic. A board that fails on one card and installs cleanly
from another has told you the answer, and it costs less than a day of reading
mmc traces.

## Installing to NVMe with disko

`disko-config.nix` for a devkit is ordinary: GPT, a vfat ESP, swap, and an ext4
root. What is worth knowing is the split in how it runs.

**The NixOS module is passive.** `disko.nixosModules.default` translates the
layout into `fileSystems` entries and nothing else:

```
{ "/"     = { device = "/dev/disk/by-partlabel/disk-main-root"; fsType = "ext4"; };
  "/boot" = { device = "/dev/disk/by-partlabel/disk-main-ESP";  fsType = "vfat"; }; }
```

The destructive half is a separate executable, invoked explicitly:

```sh
nix run .#disko -- --mode destroy,format,mount --yes-wipe-all-disks ./disko-config.nix
```

Two consequences. Importing the module into a running system is safe —
`nixos-rebuild switch` never formats. And an install script must run the
executable on purpose; importing the module is not enough to partition.

`--yes-wipe-all-disks` is required when there is no TTY, which includes every
detached or scripted run. Verify the disk is the one you mean first; the flag
removes the only confirmation.

Expose disko from your own flake rather than calling `master`, so the tool that
partitions matches the module that declares:

```nix
inherit (disko.packages.${system}) disko;
```

### disko does not activate swap

It creates the partition. It does not `swapon`. Check, then fix:

```sh
swapon --show                                      # empty is the bug
sudo swapon /dev/disk/by-partlabel/disk-main-swap
```

Do this **before** `nixos-install`. On an 8 GB Orin Nano, the vendor kernel's
LTO link steps are the memory peak of the entire install. Measured during
`lto1-ltrans`: 3.1 GiB resident, 2.9 GiB of 4 GiB swap in use, 359 MiB free RAM,
zero OOM kills. Without the swap partition active that is a coin flip.

## The installer's store is not the constraint

In a NixOS installer image `/nix/store` is an overlay: `lowerdir` is
`/nix/.ro-store` (the squashfs), `upperdir` is `/nix/.rw-store` — **tmpfs, so
RAM**. A few gigabytes free, on a board with 8 GB.

This looks fatal for an install that must build a kernel, and is not.
`nixos-install` builds with `--store "$mountPoint"`, so the closure is realised
directly on the target disk:

```sh
nix build "$flake#$flakeAttr.config.system.build.toplevel" --store "$mountPoint" ...
```

What still lands in RAM is scratch space during individual builds. Point it at
the target:

```sh
sudo TMPDIR=/mnt/tmp nixos-install --flake /path#host --no-root-passwd
```

Run it detached from the SSH session, or a dropped connection kills a
multi-hour build:

```sh
setsid nohup nixos-install --flake ... > install.log 2>&1 < /dev/null &
```

### Reading progress

```sh
df -h /mnt                                  # closure growth
free -h                                     # swap headroom during LTO
ls -l /mnt/nix/var/nix/profiles/            # `system` symlink = done
```

`per-user` alone means it has not finished. The `system` → `system-1-link`
symlink is created in the final step, after activation, and is the only
artifact that proves an install rather than a long build.

If memory does run out, the fallback is a serialised retry — nothing already
built is lost, because it is all in the target's store:

```sh
nixos-install --max-jobs 1 --flake /path#host
```
