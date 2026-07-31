# Modern userspace on a pre-5.x kernel

A downstream phone kernel is often 3.18, 4.4 or 4.9. Current systemd assumes
syscalls introduced years later, and its usual reaction to a missing one is to
treat the operation as fatal rather than to fall back.

## The failure shape

The kernel returns `ENOSYS`/`EINVAL` for a syscall systemd's feature-detection
did not gate. Symptoms are never "unsupported kernel" — they are large,
repetitive counts in the journal:

| Observed | Cause | Kernel that added it |
|---|---|---|
| thousands of `sd-device` failures | `statx()` `STATX_MNT_ID` | 5.8 |
| udev spawns workers but watches none | `pidfd_open()` | 5.3 |
| hundreds of dropped uevents | synthetic-uuid `kobject_synth_uevent()` | 4.13 |
| workers become permanent zombies | `SIGCHLD` blocked because the pidfd path was assumed | consequence of the above |

Each of these was found the same way: boot, read the failure, count it, patch
one thing, boot again. The counts matter — a four-digit repetition identifies a
per-device or per-event code path, a single occurrence identifies a startup path.

## Patching it

Carry the patches in your own repo and apply them through an overlay:

```nix
nixpkgs.overlays = [
  (final: prev: {
    systemd = prev.systemd.overrideAttrs (old: {
      patches = (old.patches or [ ]) ++ [
        ../patches/systemd/0002-systemd-mnt-id-fdinfo-fallback.patch
        ../patches/systemd/0003-systemd-pidfd-sigchld-fallback.patch
        ../patches/systemd/0004-systemd-uevent-no-synthetic-uuid.patch
        ../patches/systemd/0005-systemd-block-sigchld-without-pidfd.patch
      ];
    });
  })
];
```

`systemdMinimal` derives from `systemd` through `override` + `overrideAttrs`, so
it **inherits these patches**. Patching it separately fails to apply.

Name the module after the kernel version it exists for
(`modules/systemd-linux-4.9.nix`), not after the device — the constraint follows
the kernel, and a second device on the same vintage should import the same file.

## The alternative and its cost

Pinning Nixpkgs back to a systemd old enough for the kernel removes the patches
but downgrades the entire system, every package, for one component's syscall
baseline. A handful of local fallback patches is the cheaper trade until the
patch count stops converging.

Expect to find more. Each patch header should record the boot attempt and the
observed count that motivated it, so a later reader can tell a still-needed
fallback from one that upstream has since gated properly.
