# Debugging a device that will not stay on the bus

## Contents

- The problem
- The ext4 magic latch
- A log ring on unused disk
- Writing a rootfs over adb
- Retiring adb for ssh
- Vendor baselines that look like faults
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

**It can also be armed from a running stage-2, with no power cycle.** ext4 keeps
no private copy of the superblock — `sbi->s_es` points into a `buffer_head` in
the block device's page cache — so zeroing offset 1080 on the mounted partition
takes effect on the next mount, and an orderly `sync; sync; echo b >
/proc/sysrq-trigger` parks the device in stage-1 on the way back up. That turns
the latch from a race into a one-line loop: latch, reboot, deploy over stage-1,
reboot, verify.

This is what makes everything else on this page possible. Establish it before
you need it.

**Never boot the stock OS while the magic is zeroed.** Android reacts to an
unmountable `userdata` by reformatting it, which destroys both the rootfs and
any log ring past it. The latch is safe only against your own stage-1.

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

The mechanism that grows it is `mobile.system.autoResize`, and it has **two**
effects: `Tasks::AutoResize` in the initrd, and an `x-systemd.growfs` mount
option in stage-2. Disabling one leaves the other, so the filesystem re-grows
onto the ring on every boot while the config appears to forbid it. Force both
off, then size the filesystem deliberately (`resize2fs <dev> <blocks>` with the
ring's start block as the ceiling) rather than leaving it at the image default.

Watch for the NixOS `filterOverrides` trap while doing this: an upstream
`mkDefault` on a *whole attrset* is discarded wholesale by any sibling
definition of higher priority, taking the attributes you did not mean to
override with it. Put `mkDefault` on the leaves and `mkForce` inside, not
outside.

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

## Retiring adb for ssh

Once stage-1 runs dropbear on the gadget network
([stage-1.md](stage-1.md)), stop deploying over adb. The transports fail
independently — adb and RNDIS are separate functions on the same gadget, and
adbd wedging in `ffs_epfile_io` with the gadget still `CONFIGURED` and no host
disconnect is a routine event — so ssh is both a second channel and a better
one:

| | `adb exec-in` | ssh |
|---|---|---|
| bulk write | truncates silently, needs per-chunk hashing | streams whole |
| exit status | not propagated; empty output is ambiguous | real exit code |
| measured throughput | 32 MiB chunks with verification | 12.6 MB/s host to device |

Keep the chunking logic anyway — it is what makes an interrupted deploy
resumable, and it is the only thing standing between a dead transport and a
half-written superblock. What ssh removes is the *ambiguity*, not the need to
verify.

Reach for ssh first whenever adb goes quiet, and use the port to tell which
stage answered before concluding the device is dead
([stage-2-access.md](stage-2-access.md)).

## Vendor baselines that look like faults

Establish what idle looks like on the device before treating any reading as
evidence. A vendor kernel parks threads in states a mainline system never would,
and the usual health metrics report them as trouble.

**Load average.** One port idles at `load average: 24.21, 24.03, 20.54` with
`top` showing 94% idle. Both numbers are correct: Linux counts uninterruptible
sleep in the load average, and this kernel parks 23 threads in D state
permanently — the sensor hub, five fuel-gauge and charger threads, four display
threads, a DVFS IPI waiter, one watchdog kicker per CPU, hang detection, and the
port's own framebuffer refresher. None is stuck on I/O and none is spinning.

So a high load average on such a device means nothing on its own. Write the
baseline count down. Only a figure meaningfully above it, or a D-state entry not
on the list, carries information — check `%Cpu(s)` and the D-state set before
concluding anything about a hang, an I/O stall or a restart loop.

**Do not sweep `/dev`.** Opening and closing every node to see what answers
reboots this class of device, and a skip list does not save you because the
node that does it is not knowable in advance. Read single known nodes instead.
The cost of getting this wrong is a physical power cycle.

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

Five things worth building in:

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
- **Refuse to write a mounted filesystem.** Compare the target's `major:minor`
  from `/proc/self/mountinfo`, not device paths — `/dev/block/mmcblk0p41`,
  `/dev/mmcblk0p41` and a by-name symlink are one partition under three names,
  and a string comparison passes all three.
- **Refuse to write on a flat battery.** A phone in bring-up is often
  discharging even while plugged into a PC port, and a deploy interrupted by a
  power-off lands mid-image. A `MIN_BATTERY` floor around 40% costs nothing and
  prevents the one failure with no recovery path over USB.

Resolve the partition by its **GPT label**, via `PARTNAME=` in the sysfs
`uevent`, rather than trusting the `by-name` directory to exist — stage-1's
minimal `/dev` frequently does not populate it, and falling back to an index at
that moment is exactly the mistake the rule above exists to prevent.

Also worth knowing while building this: **flakes cannot see untracked files**, so
a new patch or module must be `git add`-ed — staged, not committed — before
`nix build` can evaluate it. Modified *tracked* files are visible without
staging, which makes the failure mode confusing the first time.
