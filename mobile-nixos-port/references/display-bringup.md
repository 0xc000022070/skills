# Getting a console onto the panel

## Contents

- Triage ladder
- The distinct-pixel-value diagnostic
- Is there KMS at all
- fbcon does not always take over
- The palette trap (MediaTek mtkfb, OMAP lineage)
- Nothing pans the framebuffer
- The backlight is a DSI command, and it lies
- Turning the panel off without deadlocking it
- The console is not yours until printk stops writing to it
- Writing the thing that repaints it
- MediaTek display debugfs

## Triage ladder

A dark panel has at least six independent causes. Answer these in order; each
answer is cheap and eliminates a whole class.

1. **Does a framebuffer exist?** `/dev/fb0`, `/sys/class/graphics/fb0/`. If not,
   the driver did not probe — a kernel problem, not a display problem.
2. **Is there KMS?** See below. If not, every Wayland compositor is off the
   table and fbcon is the only console.
3. **Does fbcon own a VT?** The kernel prints
   `Console: switching to colour frame buffer device WWxHH` when it binds. If
   the log only ever says `colour dummy device 80x25`, nothing is drawing.
4. **Is anything panning?** Some drivers only bind the overlay to the
   framebuffer on `FBIOPAN_DISPLAY`. fbcon draws into memory but never pans.
5. **Is the palette non-zero?** Below. Text drawn in `0x00000000` on black is
   indistinguishable from no text.
6. **Is the backlight on?** Check last, because a lit panel showing nothing and
   a dark panel showing something look identical from across the room and are
   opposite bugs.

Symptom mapping worth memorising: **backlight visibly on, panel entirely black
or showing only a band of colour at the top** = rungs 3–5, i.e. fbcon or
compositing, not the panel. The panel is provably alive because the backlight
lit it.

## The distinct-pixel-value diagnostic

Do not count "non-black pixels" in a framebuffer dump. It conflates several
failures and reads as zero for the most interesting one.

**Enumerate the distinct 32-bit values in one framebuffer page.** The cardinality
is the answer:

| Distinct values | Reading |
|---|---|
| 1 (`00000000`) | nothing rendered, or rendered entirely in a zeroed palette |
| 2 (`ff000000`, `ffaaaaaa`) | fbcon is drawing correctly — `0xAAAAAA` is VGA light grey, its default foreground |
| many, structured in rows | something is drawing; suspect stride, format, or panning |
| many, noise | uninitialised memory being scanned out |

Read the page with the geometry the driver reports, not the geometry you assume.
Take `line_length` from `/sys/class/graphics/fb0/stride` or `FBIOGET_FSCREENINFO`
— **stride is not `xres * bpp/8`**. A 720x1600x32 panel was observed with stride
2944 (736 u32 words per row), which makes a page 4710400 bytes, not 4608000.
Slicing rows at the wrong pitch turns readable text into diagonal noise and
sends you chasing the wrong bug.

Also check `virtual_size` — multiple pages behind one visible page is normal, and
the page currently scanned out may not be page 0.

## Is there KMS at all

```sh
cat /sys/class/drm/card0/device/driver   # or readlink -f
ls -d /sys/class/drm/card0-*             # connectors
```

A `card0` whose driver is a GPU render driver (`pvrsrvkm` for PowerVR, and
similar) with **zero `card0-*` connector directories** is a render node. It
cannot modeset. Display is fbdev-only, and Phosh, Plasma Mobile, sway and weston
cannot run on the device as it stands.

This also poisons the task graph — see the `Tasks::Graphics` `:Any` trap in
[stage-1.md](stage-1.md).

## fbcon does not always take over

On some downstream kernels the framebuffer registers but `do_bind_con_driver()`
never runs, so the dummy console keeps the VT. Force it from stage-1 by
unbinding and rebinding the fbcon vtconsole:

```ruby
# find the vtcon whose `name` attribute is "frame buffer device"
# among /sys/class/vtconsole/vtcon0..vtcon3, then:
File.write("#{path}/bind", "0")
File.write("#{path}/bind", "1")
```

The confirmation is the `switching to colour frame buffer device WWxHH` line.
Geometry checks out against the font: 720/8 × 1600/16 = 90x100 for the default
8x16 font.

## The palette trap (MediaTek mtkfb, OMAP lineage)

A framebuffer driver that declares `FB_VISUAL_TRUECOLOR` and hands fbcon a
`pseudo_palette` **must** implement `.fb_setcolreg` or `.fb_setcmap`. `mtkfb`
implements neither.

The chain:

- `fb_set_cmap()` (`drivers/video/fbdev/core/fbcmap.c`) returns `-EINVAL` early
  when both callbacks are absent.
- `fbcon_set_palette()` therefore becomes a no-op.
- `pseudo_palette` stays as `framebuffer_alloc()` left it: **all zeroes**.
- The generic blitters index that array directly —
  `cfbimgblt.c` (`fgcolor`/`bgcolor`) and `cfbfillrect.c` (`fg`) — so every
  console colour resolves to `0x00000000`.

fbcon renders perfectly the entire time, black on black. The vestigial
`.fb_setcolreg = NULL` still sitting in mtkfb's unused dual-display ops table
shows the omission was inherited by copy-paste from the OMAP fbdev skeleton;
expect the same bug in other drivers with that lineage.

The fix is ~28 lines:

```c
static int mtkfb_setcolreg(unsigned int regno, unsigned int red,
	unsigned int green, unsigned int blue, unsigned int transp,
	struct fb_info *info)
{
	u32 *palette = info->pseudo_palette;
	u32 value;

	if (info->fix.visual != FB_VISUAL_TRUECOLOR)
		return -EINVAL;
	if (regno >= 16)
		return -EINVAL;

	value  = (red   >> (16 - info->var.red.length))   << info->var.red.offset;
	value |= (green >> (16 - info->var.green.length)) << info->var.green.offset;
	value |= (blue  >> (16 - info->var.blue.length))  << info->var.blue.offset;

	if (info->var.transp.length)
		value |= ((1 << info->var.transp.length) - 1) << info->var.transp.offset;

	palette[regno] = value;
	return 0;
}
```

**Alpha is load-bearing.** The overlay format is `ARGB8888`/`BGRA8888` with
`var.transp` 8 bits at offset 24 and the layer's own `alpha = 0xff`. A palette
written without forcing opaque alpha yields transparent glyphs — a second,
equally invisible, and equally "correct" render. Skipping the `var.transp` clause
is the most likely way to reimplement this fix and still see a black panel.

Verify with the distinct-value test: one value before, two after.

## Nothing pans the framebuffer

`mtkfb` binds the overlay to framebuffer memory only inside
`mtkfb_pan_display_impl()`, which runs on `FBIOPAN_DISPLAY` and nothing else.
Console text is therefore composited exactly never.

```nix
mobile.quirks.fb-refresher.stage-1.enable = true;
mobile.quirks.fb-refresher.enable = true;
```

`msm-fb-refresher --loop` issues the missing `FBIOPAN_DISPLAY` calls. Despite the
name it is not Qualcomm-specific and Mobile NixOS documents it as applicable to
other vendors.

Related gate: mtkfb latches a `no_update` flag that makes it discard
`FBIOPAN_DISPLAY` outright. It is cleared by writing `bits_per_pixel` in sysfs.

## The backlight is a DSI command, and it lies

On DSI command-driven backlights there is no PWM to poke; brightness is DCS
`0x51` pushed over the link. Two behaviours fight back:

- **`primary_display_setbacklight()` keeps a `static unsigned int last_level`**
  and early-returns when the requested value equals the previous one. Writing
  the same brightness twice does nothing. Alternate between two adjacent values
  (200/201) to guarantee the command is actually sent.
- **The idle manager parks the DSI link in ULPS**
  (`DISP_OPT_IDLEMGR_ENTER_ULPS=1`), after which the panel stops responding.
  Push `/sys/kernel/debug/displowpower/idletime` to its clamped maximum
  (the accepted range is `[33, 1000000]`).

The panel's init table often leaves DCS `0x51` at `0x00` with `0x53 = 0x2C` —
Android's lights HAL raises it at runtime, so stage-1 has to do the same. Vendor
code frequently rescales (`level = level * 72 / 100`) before pushing, so the
value you write is not the value the panel receives.

The bootloader hands over a **live** display: `is_lcm_inited = 1` derived from
`/chosen` `atag,videolfb-*` makes `primary_display_init()` skip panel init
entirely. Do not assume the kernel initialised the panel; usually it did not.

## Turning the panel off without deadlocking it

`FB_BLANK_POWERDOWN` is the portable way to blank a framebuffer. On mtkfb it is
a trap:

```sh
echo 4 > /sys/class/graphics/fb0/blank    # do not
```

The write never returns. The writer and *every* `msm-fb-refresher` — stage-1's
and stage-2's both — end up in `D` at `down`, on a semaphore nothing releases.
Any SSH session that touched it hangs, the console freezes on its last painted
frame, and only a reboot clears it. On a device whose sole debug channel is the
USB gadget, that reboot is a physical power cycle.

Blank the backlight instead, and do not expect it where the class name says:

```sh
ls /sys/class/backlight/                                  # often empty
cat /sys/class/leds/lcd-backlight/{brightness,max_brightness}
```

Save the current level before zeroing it. `max_brightness` is not the level the
bootloader or Android was using, and restoring to it is a bright surprise in a
dark room.

## The console is not yours until printk stops writing to it

Anything that repaints the panel — a status dashboard, a menu, a picker — gets
scrolled away by the kernel unless printk is silenced first, and the usual
mechanisms report success while changing nothing:

```sh
tr ' ' '\n' < /proc/cmdline | grep -E 'console|loglevel'
# console=tty0 console=ttyS0,921600n1 console=tty1 ignore_loglevel loglevel=4
```

`ignore_loglevel` forces **every** message to the console regardless of level, so
`dmesg -n 1` and `setterm --msg off` both return 0 and do nothing. It is a
writable module parameter, so it can be cleared without touching the boot image:

```sh
echo N > /sys/module/printk/parameters/ignore_loglevel   # now kernel.printk applies
```

`console=tty0` follows the *active* VT, so moving the TUI to a different VT does
not isolate it either. Read the cmdline before designing around either mechanism.

A poller on this kind of tree also generates its own noise: reading
`/sys/class/power_supply/*` makes MediaTek fuel-gauge and charger drivers log a
line per read. The printk prefix names the process that caused it —
`(5)[5478:panel][fgauge_read_current]` — which is how you separate a chatty
driver from a chatty reader of your own making.

## Writing the thing that repaints it

A dashboard on a phone panel is a full-screen TUI whose only input is the two or
three hardware keys the keypad driver reports. Two properties decide whether it
is usable, and neither one is about drawing.

**It has to be a single process.** A shell implementation forks per reading —
`nproc`, `stty`, `df`, `ss`, `ip`, `ps`, `who`, `systemctl`, a VPN client — and
on eight in-order A53s thirty forks per repaint measured 420 ms. The damage is
not the frame latency. It is that the key poll degenerates into 50 ms slices
between forks, so presses land late or are dropped entirely, and the device
reads as hung when it is merely busy forking. Read procfs, sysfs, sd-bus and
sd-journal in-process, and drive the loop from `epoll` over the input
descriptors plus a `timerfd` for the refresh.

sd-bus and sd-journal are the ones that pay: they replace forking `systemctl`
and `journalctl` on every repaint, which is usually the largest single item.

**Take input from the event device directly.** On these kernels udev tags
nothing, so logind holds no input descriptors and every framework that expects
it to is silently dead — see
[old-kernel-userspace.md](old-kernel-userspace.md). Read packed `input_event`
structs from `/dev/input/eventN` and decode the key codes yourself.

Both decisions also buy testability, provided the seams are placed on purpose:

- route every filesystem read through one prefix function, so a fixture tree
  stands in for `/proc` and `/sys`;
- decode keys from *any* descriptor rather than from a device path, so a pipe
  can replay a press sequence.

With those two seams the frame renderer and the key state machine both run on
the build host with no device attached. That is worth more here than in ordinary
software: the alternative to a host test is a reflash, a boot, and a physical
power cycle when it wedges.

Compiling such a helper needs no pkg-config. `runCommandCC` with the library in
`buildInputs` already puts the include and library paths into the `$CC` wrapper,
and plain `pkg-config` does not answer under a target prefix when
cross-compiling.

## MediaTek display debugfs

The `process_dbg_opt` command vocabulary (~58 commands) is bound to
`/sys/kernel/debug/mtkfb`, **not** `/sys/kernel/debug/dispsys`. DISP logging goes
to the `dprec` ring buffer, not to dmesg, so `dmesg` staying silent proves
nothing about the display path.

`DISP_OPT_NO_LK` is a dead end: `disp_helper.c` returns a hardcoded `1` and the
option is marked "not use now" in the same file.
