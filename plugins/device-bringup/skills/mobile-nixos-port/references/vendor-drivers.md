# Vendor drivers that userspace has to start

## Contents

- Built in is not started
- What the loader has to be
- Provisioning proprietary firmware
- MMIO reads on a gated block lie

Android vendor trees routinely ship drivers that never register themselves. The
driver is in the kernel, `/sys/class/net` is empty, and the config symbol you
enabled is set. Nothing is broken; the piece that starts it lives in
`/vendor/bin` and does not exist on a NixOS rootfs.

## Built in is not started

The pattern, using a MediaTek combo chip (Wi-Fi, Bluetooth, GPS, FM) as the
worked example:

- a symbol like `MTK_WCN_REMOVE_KO` turns every sub-driver's `module_init` into
  a plain exported function;
- the only caller is a single `do_connectivity_driver_init()`;
- that is reached through an `ioctl` on a detect character device;
- on Android the ioctl comes from a vendor binary, and nothing else ever issues
  it.

Symptom: no interface, and a network stack reporting hardware missing. It is
indistinguishable from having failed to build the driver, which is why the first
check is the character device, not the config symbol.

Two properties of that call path decide the shape of whatever you write.

**It runs exactly once per boot.** The init sets its `init_before` flag *before*
running anything and returns 0 on every later call, so a failed attempt is not
retried — it is permanently disabled until reboot. Restarting your unit cannot
undo a failed init. Only the power-on that follows it is repeatable.

That single fact rules out the obvious design. `Restart=on-failure` is worse
than useless here: it re-runs a call that now returns success over a chip that
was never initialised.

**Ordering inside the ioctl sequence matters.** Cleanup has to precede init when
two sub-drivers register the same name — one registered at boot, one registered
by the first sub-init — because `driver_register()` refuses a duplicate with
`-EBUSY`:

```
Error: Driver 'mtk_sdio_client' is already registered, aborting...
[HIF-SDIO][I]hif_sdio_init:sdio_register_driver() fail, ret=-16
[WMT-MOD-INIT][I]do_common_drv_init:common driver init finish:-16
[WMT-MOD-INIT][E]do_connectivity_driver_init(43):do common driver not ready
```

Note what is visible and what is not: individual sub-init results are logged at
`PR_DBG` behind a plain global rather than a module parameter, so only the summed
`-16` reaches the log. The driver-core line above is what identifies which
sub-init failed. When a vendor driver reports a sum, find the component error
somewhere else before guessing.

## What the loader has to be

Not a one-shot. The core typically does not locate its own firmware: it stores a
command string, wakes a second character device, and **blocks waiting for
userspace to answer an ioctl**. With nothing on the other end it times out and
the chip comes up with no firmware:

```
wmt_ctrl_ul_cmd(468): wait signal timeout
wmt_ctrl_get_rom_patch_info: wmt_ctrl_ul_cmd fail(-2)
mtk_wcn_soc_rom_patch_dwn(3585): failed to get patch (type: 0, ret: -1)
mtk_wcn_consys_hw_pwr_on: polling_consys_chipid fail
```

So the loader must issue the init ioctl **and then stay running** to service
firmware negotiation. And the second device node is created by the init the
first ioctl triggers, so it cannot be opened beforehand: one process has to do
both, in order. A design with two units, or a unit that exits after init, cannot
work — not as a style preference, but because the node does not exist yet.

Requirements to check against any such daemon you write:

| Requirement | Why |
|---|---|
| single process, ordered | the second node is created by the first ioctl |
| long-running | firmware negotiation is a blocking request from the kernel |
| no restart on failure | init is latched; a retry silently succeeds over a dead chip |
| power-on separated from init | only the power-on write is repeatable |

## Provisioning proprietary firmware

A built-in driver with no firmware fails at `ip link set <iface> up`, which again
looks exactly like not having built it.

The blobs are proprietary and the repository is public, so `requireFile` is the
right mechanism: evaluation fails with instructions until the tarball is in the
store, and after that the build is as reproducible as any other.

Extract from the running device, read-only. A vendor filesystem inside a dynamic
partition can be reached without reassembling anything when its filesystem ends
inside the first extent:

```sh
losetup -r -o <extent-offset> --sizelimit <fs-size> -f --show /dev/<super>
mount -o ro,noload /dev/loop0 /run/vendor-ro     # noload: no journal replay
tar -C /run/vendor-ro -cf - firmware etc/wifi
umount /run/vendor-ro && losetup -d /dev/loop0
```

`-r` on the loop device plus `ro,noload` on the mount is what makes this
provably non-destructive: no journal is replayed and no write reaches the
partition. Offsets come from the LP metadata at the head of `super`; they are
specific to one unit's flash and must be re-read after any repartition. For
reading that metadata, use skill `android-firmware-lab`.

Repack deterministically before hashing, or the hash tracks readdir order rather
than content:

```sh
tar --sort=name --owner=0 --group=0 --numeric-owner --mtime=@0 --format=gnu \
    -C <extracted> -cf <device>-vendor-firmware.tar firmware etc
```

## MMIO reads on a gated block lie

Register dumps taken on a clock-gated block look coherent and are worthless.
Configuration registers have storage and keep returning retained values, so the
dump reads plausible. Pure status registers have no storage and read `0x0`.
Writes do not land, and nothing reports an error.

This is a whole class of wrong conclusion: a status register reading `0x0` gets
diagnosed as dead hardware when it only means the block was gated after a close.
Ungated, the same register read a normal value.

Before trusting any MMIO measurement:

1. **Ungate the block and hold it open**, through the driver's own debug
   interface or by clearing the relevant infra clock-gating bits. Read the
   gating status register and know its polarity — a *set* bit commonly means
   gated.
2. **Prove a write lands.** Pick a harmless writable register, write a changed
   value, read it back, restore it.
3. Only then read the status registers.

The same skepticism applies to vendor error messages. A driver that prints a
variable in its failure path may be printing an initialiser it never assigned,
so the number in the log is not a measurement. Confirm the value came from
hardware before building a theory on it.
