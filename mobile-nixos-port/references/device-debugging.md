# Debugging a device that will not stay on the bus

## Contents

- The problem
- The ext4 magic latch
- A log ring on unused disk
- Writing a rootfs over adb
- Host tooling belongs in the flake

## The problem

Once stage-1 hands off, the observation channels from
[stage-1.md](stage-1.md) are gone: `boot.postBootCommands` in upstream
`adb.nix` runs `pkill -x adbd`, so USB drops at handoff *by design*. If stage-2
then fails before a service manager exists, there is nothing left — no journal,
no adbd, no shell.

What remains is the window between kernel start and handoff. On a 4.9 MediaTek
device that is roughly **16 seconds**. Sixteen seconds per boot, for a failure
that takes many boots to characterise, is not a debugging loop. The techniques
below exist to turn it into one.

## The ext4 magic latch

The single most useful trick available. The ext4 superblock magic is a `__le16`
0xEF53 — bytes `53 ef` — at absolute offset **1080** (1024 + 56). Zero it:

```sh
# arm: park the device in stage-1
printf '\0\0'     | adb exec-in 'dd of=/dev/mmcblk0p41 bs=1 seek=1080 conv=notrunc; sync'
# disarm: let the next boot proceed to stage-2
printf '\x53\xef' | adb exec-in 'dd of=/dev/mmcblk0p41 bs=1 seek=1080 conv=notrunc; sync'
```

With the magic zeroed, stage-1 cannot mount root, so `shellOnFail` drops to a
shell that blocks on `/dev/console` forever. adbd stays up **indefinitely**. The
16-second window becomes an open-ended session, and the change is two bytes,
reversible, and touches nothing else in the filesystem.

Arm it by racing the window: start a poller *before* powering the phone on, and
have it busy-poll for the device rather than sleep between attempts.

This is what makes everything else on this page possible. Establish it before
you need it.

## A log ring on unused disk

When PID 1 freezes before any unit runs (see
[old-kernel-userspace.md](old-kernel-userspace.md)), a logging *service* is
useless by construction, and journald never gets to flush. Two constraints
follow: the writer must run from `boot.postBootCommands`, which is stage-2 init
before `exec systemd`, and the reader must not need to mount anything.

A rootfs image is usually a few gigabytes on a partition of twenty-plus. The
tail is untouched by any filesystem, so it can hold a log the reader gets at with
one `dd`:

```nix
# modules/bringup-log/layout.nix — imported by BOTH the writer and the reader
rec {
  slotA = 4194304;              # 16 GiB, in 4096-byte blocks
  slotBlocks = 16384;           # 64 MiB per slot
  slotB = slotA + slotBlocks;
  payloadBlocks = slotBlocks - 1;   # block 0 is the header
  magic = "PORTNAME-LOG1";
}
```

Design notes that are not obvious:

- **One file defines the offsets, imported by the device writer and the host
  reader.** Two copies of a magic number drift, and drift here means reading
  garbage and believing it.
- **Two slots, alternating on `seq % 2`.** A power cut can then only damage the
  slot being written; the other still holds the previous iteration. The reader
  picks the higher `seq`.
- **Payload before header.** Same discipline as the superblock rule below: the
  header names a byte count, so writing it first advertises data that is not
  there yet.
- **Not a systemd unit.** The failure being diagnosed is systemd freezing. A
  unit that would have logged it never runs.

**The cost of this trick is that the filesystem must never grow into the ring.**
Record the ceiling next to the layout, in the resize instructions, and in the
handoff — a later "reclaim the free space on the rootfs partition" is a
completely reasonable thing to do and it silently destroys the mechanism.

## Writing a rootfs over adb

`adb exec-in` truncates bulk streams. Chunk the image, hash each chunk on the
device, and rewrite only what does not match.

Two failure modes must stay distinguishable, because their responses are
opposite:

| Verify result | Meaning | Response |
|---|---|---|
| hash mismatch | the chunk was truncated | rewrite the chunk |
| **empty output, exit 0** | adbd dropped the transport | wait, re-verify — the data may be fine |

Treating an empty verify as corruption means rewriting good data over a dead
transport. 64 MiB chunks killed adbd partway through; 32 MiB ran clean.

**Write the chunk holding the superblock last.** Offset 1080 lives in chunk 0,
so chunk 0 goes last, mirroring how `mkfs` writes the primary superblock after
the metadata it points at. Writing it first restores a valid superblock
describing a half-written filesystem — the device then boots the corpse and
freezes, and you have lost both the rootfs and the latch. With the magic held at
zero until every other chunk verifies, an interrupted run simply re-parks the
device in stage-1 and the write can resume.

Verify with a full-partition read after `echo 3 > /proc/sys/vm/drop_caches`, as
a separate step from the write. Verifying through the page cache verifies the
page cache.

Note that `adb reboot` does not work from a stage-1 shell (`reboot failed: -1`);
`sync; sync; echo b > /proc/sysrq-trigger` does.

## Host tooling belongs in the flake

These operations start life as shell scripts in `/tmp`. That costs real work
twice over:

- `nix-gc` wipes `/tmp` on the same run that collects the store, so the scripts
  and the image they existed to write disappear together. Related: `nix build
  --no-link --print-out-paths` creates **no GC root** — always `--out-link` for
  anything that took an hour to cross-compile.
- The scripts carry the operational knowledge that is most expensive to
  rediscover — chunk 0 last, truncation versus transport death, which partition
  is the fallback. That belongs under review like any other part of the port.

Expose them as flake apps: `nix run .#<device>-latch`, `-log`, `-deploy`,
`-verify`, `-flash-bootimg`, `-reboot`. `writeShellApplication` runs shellcheck
and fails the build on findings, so the scripts stay honest.

Three things worth building in:

- **An identity guard.** Every tool checks a device-unique string from
  `/proc/cmdline` before touching a block device, and exits non-zero if it does
  not match. Bring-up involves a lot of `dd` against paths that mean different
  things on different hardware.
- **Resolve partitions by name, never by index.** `/dev/block/by-name/<part>`,
  then refuse anything that does not resolve to a `mmcblk` partition node. A
  wrong index writes over `lk`, `nvram` or the partition table — the partitions
  that are not recoverable over USB.
- **Name the tool for the image, not the partition.** A tool called
  `flash-boot` that defaults to `boot` will eventually be run on a port that
  boots from `recovery`, and it will overwrite the stock Android that was the
  only way back. Default to the partition the port actually boots from, print
  the resolved target before writing, and warn when the fallback is the target.

Also worth knowing while building this: **flakes cannot see untracked files**, so
a new patch or module must be `git add`-ed — staged, not committed — before
`nix build` can evaluate it. Modified *tracked* files are visible without
staging, which makes the failure mode confusing the first time.
