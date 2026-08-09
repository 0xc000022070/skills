# Modern userspace on a pre-5.x kernel

A downstream phone kernel is often 3.18, 4.4 or 4.9. Current systemd assumes
syscalls introduced years later, and its usual reaction to a missing one is to
treat the operation as fatal rather than to fall back.

## Two failure shapes, only one of which leaves logs

The kernel returns `ENOSYS`/`EINVAL` for a syscall systemd's feature-detection
did not gate. Where that happens decides whether you get to read about it:

- **After the journal exists** — noisy, countable, tractable. The table below.
- **Inside PID 1's own startup, before any unit runs** — systemd calls
  `freeze()` and the machine sits there. No journal, no console message, no
  shell, nothing to count. See [Failures with no log at
  all](#failures-with-no-log-at-all).

The second shape is the one that costs days, because every instinct trained on
the first one is useless against it.

## The noisy shape

Symptoms are never "unsupported kernel" — they are large, repetitive counts in
the journal:

| Observed | Cause | Kernel that added it |
|---|---|---|
| thousands of `sd-device` failures | `statx()` `STATX_MNT_ID` | 5.8 |
| udev spawns workers but watches none | `pidfd_open()` | 5.3 |
| hundreds of dropped uevents | synthetic-uuid `kobject_synth_uevent()` | 4.13 |
| workers become permanent zombies | `SIGCHLD` blocked because the pidfd path was assumed | consequence of the above |
| a unit dies instantly with no output, `SystemCallFilter=` set | `SCMP_ACT_KILL_PROCESS` | 4.14 |
| `systemd-machine-id-commit` fails on a namespace check | `NS_GET_NSTYPE` ioctl | 4.11 |
| `systemd-tmpfiles --clean` fails on every path | `STATX_ATTR_MOUNT_ROOT`, used only as a hint but demanded as mandatory | 5.8 |

Each of these was found the same way: boot, read the failure, count it, patch
one thing, boot again. The counts matter — a four-digit repetition identifies a
per-device or per-event code path, a single occurrence identifies a startup path.

Three recurring shapes are worth naming, because the fix follows from the shape:

- **A capability probed at the wrong granularity.** systemd checks that libseccomp
  *knows* `SCMP_ACT_KILL_PROCESS` and concludes the kernel accepts it. The
  correct gate is the kernel's own answer, `seccomp_api_get() >= 3`; fall back to
  `SCMP_ACT_ERRNO`. The symptom is a service that "starts and exits" with an
  empty journal, because the process is killed before it writes anything.
- **An optional attribute treated as mandatory.** `xstatx_full()` returns
  `-EUNATCH` for an attribute the kernel does not report. Where systemd only
  *hints* on the result, the fix is to pass `/* mandatory_attributes= */ 0`, test
  `FLAGS_SET(sx.stx_attributes_mask, …)` before reading the bit, and fall back to
  `is_mount_point_at()`. The `stx_attributes_mask` test is load-bearing: without
  it a kernel that zeroes the field reads as a definite "no".
- **A version gate written against the wrong tree.** An upstream comment saying a
  feature is "6.11+" often dates the *systemd* use, not the kernel interface —
  `NS_GET_NSTYPE` has existed since 4.11, and nsfs already names inodes
  `mnt:[4026531840]`, matching `namespace_info[].proc_name`. Check the kernel
  history, not the comment.

## Failures with no log at all

`mount_setup()` runs in PID 1 before the journal, before the console is usable
for anything structured, before any unit. Every entry in its table carries flags;
an entry marked `MNT_FATAL` that fails to mount or to be *recognised as already
mounted* is unrecoverable, and PID 1 calls `freeze()`. The device is then warm,
powered, on the bus if a gadget was set up in stage-1 — and completely silent.

A worked example, because the shape is more instructive than the fix. Two
kernel-age problems stack inside one call:

1. `statx()` is Linux 4.11. On an older kernel glibc falls back to
   `statx_generic()`, which rejects **any** flag outside
   `{AT_EMPTY_PATH, AT_NO_AUTOMOUNT, AT_SYMLINK_NOFOLLOW}` with `EINVAL`. systemd
   passes `AT_STATX_DONT_SYNC` (0x4000) as an optimisation, so the call fails
   outright — an optimisation flag turning into a hard error.
2. Even with that fixed, `STATX_ATTR_MOUNT_ROOT` is Linux 5.8, and
   `xstatx_full()`'s mandatory-attributes check returns `-EUNATCH` when the
   kernel does not report it.

Either one makes `path_is_mount_point_full()` fail; that failure on a `MNT_FATAL`
entry is what freezes PID 1. The fallbacks are the obvious ones — retry `statx()`
without `AT_STATX_SYNC_TYPE` on `EINVAL`, and compare `st_dev`/`st_ino` against
the parent directory to decide "is this a mount root" when the attribute is
unavailable.

What matters for the next port is the method, since the usual method does not
apply:

- **Do not expect to diagnose this from the device.** There is no log. Read the
  systemd source for the version nixpkgs ships, find every `MNT_FATAL` entry and
  every syscall on that path, and check each against the kernel's version.
- **Establish an out-of-band channel first.** See
  [device-debugging.md](device-debugging.md) — a raw log ring on unused disk,
  written from `boot.postBootCommands` rather than a unit, because the whole
  point is that no unit ever runs.
- **A silent freeze is not a kernel panic and not a hang.** It is systemd
  deciding it cannot continue. Distinguishing them changes where you look:
  panic → pstore, hang → task graph, freeze → PID 1's own startup path.

## Not every failure is a missing syscall

Some units fail because the vendor kernel has a subsystem *half* enabled. These
never appear in a syscall table and no patch fixes them — the fix is
configuration.

The canonical one is nftables. `CONFIG_NF_TABLES=y` is set, so the core
registers the netlink family and every probe succeeds: the module loads, the
socket opens, `nft list ruleset` returns cleanly. Then every rule that uses an
actual expression fails with `ENOENT`, because `NFT_COMPAT`, `NF_TABLES_INET`
and the per-expression modules are unset. NixOS's `firewall.service` dies on its
first real rule.

```nix
networking.nftables.enable = false;
networking.firewall.package = pkgs.iptables-legacy;
```

The lesson generalises past netfilter: **"the subsystem is present" and "the
subsystem is usable" are different measurements on a vendor tree.** A successful
probe against a core that registers itself proves nothing about the leaf modules
that do the work. Test the operation you actually need, not its namespace.

A cheaper instance, and one that bites the moment the port is used for anything:
`zramSwap.algorithm` defaults to `zstd`, which zram gained in **4.18**. The
kernel publishes what it actually has, so ask it rather than the option:

```sh
cat /sys/block/zram0/comp_algorithm    # [lzo] lz4 deflate   <- no zstd
```

Writing an unsupported name returns `EINVAL`, and the failure lands on
`systemd-zram-setup@zram0.service` — so the system boots fine, reports nothing
interesting, and simply has no swap. On a phone with under 2 GB of RAM that is
the binding constraint, and it is invisible unless you look for the unit.

Wi-Fi is the same shape and the most likely thing to be asked for. On a MediaTek
tree `CONFIG_MTK_COMBO_WIFI=y` and a devicetree node for the combo chip are both
present, and neither is the driver: the combo symbols are the *transport* to the
connsys subsystem, while the netdev driver (`wlan_drv_gen4m`) is out of tree and
its firmware blobs live in the vendor partition. The measurement that settles it
takes one command each and none of them is the config:

```sh
ls /sys/class/ieee80211/     # no phy   -> no driver bound
rfkill list                  # empty    -> nothing registered
lsmod                        # empty on an all-builtin kernel; not evidence either way
```

A device that answers "nothing" to all three has silicon and no driver, and the
work is a driver build plus firmware extraction — days, not an evening. Say so as
a rung, and do not let `=y` in a defconfig imply a working radio.

`systemctl show -p MemoryCurrent` is the same shape in miniature: systemd reads
the whole cgroup accounting set to answer it, and on a tree missing `cpu.stat` it
logs a failure for every call. Anything polling it in a loop manufactures its own
journal noise. Read `memory.current` out of the unit's cgroup directly.

## A udev that runs but tags nothing

`systemd-udevd` being active, with `systemctl is-system-running` reporting
`running`, does not mean device events are processed. On a vendor tree the
worker can fail every event with `EINVAL` while the daemon itself stays healthy.
Everything built on udev *tags* — rather than on the device node — then does
nothing, without failing:

- `services.logind.powerKey` never fires. logind only acts on input devices udev
  handed it, and with no tags it holds zero descriptors under `/dev/input/`.
  Measure it, do not infer it:

  ```sh
  ls -l /proc/"$(systemctl show -p MainPID --value systemd-logind)"/fd | grep input
  ```

- triggerhappy is socket-activated off the same tagging and dies the same way.
- `90-backlight.rules` never grants the session write access to `brightness`.
  Use a `systemd.tmpfiles` `z` rule against the `video` group instead.

The node itself is fine, because **devtmpfs** creates it straight from the
driver. Reading evdev directly is the way through: a dozen lines of C around
`read(2)` on `/dev/input/eventN` filtering `EV_KEY` with `value == 1`. Decode
which node and which code from `/proc/bus/input/devices` — its KEY bitmap is a
little-endian word list, so bits 64–127 carry `KEY_POWER` (116) — rather than
guessing. Node numbering is driver probe order, not a convention.

## Where the code lives moves between systemd versions

Before writing a patch, locate the code in the version nixpkgs ships, not the
version you remember. systemd 254 split `src/core/exec-invoke.c` out of
`libsystemd-core-<v>.so` into a separate `/lib/systemd/systemd-executor` binary,
so a patch aimed at the old location applies to a file that is still there and
changes a code path that no longer runs. Verify by finding which artifact
contains the symbol after a build.

**Never hand-swap systemd's private libraries between builds.**
`libsystemd-shared-<v>.so`, `libsystemd-core-<v>.so` and `systemd-executor` are
versioned by release but not by *your patch set*, so mixing them is undetectable
at load time and PID 1 freezes inside `manager_new()` — the silent shape above,
with no log and no way back except a reflash. Deploy whole images. When testing a
systemd change, run the unpatched control arm first so a freeze can be attributed.

## Patching it

Carry the patches in your own repo. Keep the *list* in its own file so nothing
can hold a stale copy of it:

```nix
# patches/systemd/default.nix
[
  ./0002-systemd-mnt-id-fdinfo-fallback.patch
  ./0003-systemd-pidfd-sigchld-fallback.patch
  ./0004-systemd-uevent-no-synthetic-uuid.patch
  ./0005-systemd-block-sigchld-without-pidfd.patch
  ./0006-systemd-statx-sync-flags-and-mount-root.patch
  ./0015-systemd-seccomp-kill-process-api-gate.patch
  ./0016-systemd-ns-get-nstype-fallback.patch
  ./0017-systemd-tmpfiles-mount-root-optional.patch
]
```

Expect this list to reach the high teens on a 4.9 tree before it converges, and
number the files in the order you found them — the numbering is a record of the
boot attempts, and renumbering to close gaps destroys that.

Apply it through an overlay:

```nix
nixpkgs.overlays = [
  (final: prev:
    lib.optionalAttrs prev.stdenv.hostPlatform.isAarch64 {
      systemd = prev.systemd.overrideAttrs (old: {
        patches = (old.patches or [ ]) ++ import ../patches/systemd;
      });
    })
  ];
```

**Scope the overlay to the target platform.** `nixpkgs.overlays` also applies to
`pkgs.buildPackages`, so an unscoped systemd override rebuilds the *native*
systemd and everything downstream of it — qtbase, openjdk, gtk4 — none of which
is cross-compiled and none of which is in the binary cache once patched. The
`lib.optionalAttrs` guard is the difference between a systemd rebuild and an
afternoon.

`systemdMinimal` derives from `systemd` through `override` + `overrideAttrs`, so
it **inherits these patches**. Patching it separately fails to apply.

Name the module after the kernel version it exists for
(`modules/systemd-linux-4.9.nix`), not after the device — the constraint follows
the kernel, and a second device on the same vintage should import the same file.

## Check that the patches still apply, without a device

The expensive failure is a Nixpkgs bump moving systemd far enough that a patch
no longer applies — discovered after a cross-compile, a multi-gigabyte write and
a boot. `applyPatches` against native systemd source answers it in seconds:

```nix
checks = forEachSystem (system: {
  systemd-patches = (pkgsFor system).applyPatches {
    name = "systemd-linux-4.9-patches-apply";
    src = (pkgsFor system).systemd.src;
    patches = import ./patches/systemd;
  };
});
```

`nix flake check` now covers it. Because the check and the overlay import the
same list, the check cannot drift from what actually ships — which is the only
reason it is worth having.

## The alternative and its cost

Pinning Nixpkgs back to a systemd old enough for the kernel removes the patches
but downgrades the entire system, every package, for one component's syscall
baseline. A handful of local fallback patches is the cheaper trade until the
patch count stops converging.

Expect to find more. Each patch header should record the boot attempt and the
observed count that motivated it, so a later reader can tell a still-needed
fallback from one that upstream has since gated properly.
