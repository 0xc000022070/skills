# Stage-1: init, tasks, observability, access

## Contents

- The task graph
- Recovery-resident boot selection
- The mruby environment
- Observation channels
- USB gadget
- Networking and SSH
- Common stage-1 failures

## The task graph

Stage-1 init is a dependency-resolved task graph, not a script. A task declares
what it needs and what it satisfies; ordering is derived.

```ruby
class Tasks::DeviceThing < SingletonTask
  def initialize()
    add_dependency(:Task, Tasks::Graphics::FBDev.instance)
    add_dependency(:Mount, "/sys")
    add_dependency(:Files, "/sys/class/leds/lcd-backlight/brightness")
    Targets[:Graphics].add_dependency(:Task, self)
  end

  def run() ... end

  def ux_priority() -50 end
end
```

Register the file with `mobile.boot.stage-1.tasks = [ ./stage-1/thing.rb ];`, or
inline it with `pkgs.writeText` when it must interpolate Nix values.

Dependency kinds: `:Task` (another task instance), `:Mount` (a mountpoint),
`:Files` (a path exists), `:Target` (a named target such as `:Networking`).
Attaching yourself to a target — `Targets[:SwitchRoot].add_dependency(:Task, self)` —
is what makes the task run at all.

**`Tasks::Graphics` is `:Any` of FBDev *or* DRM.** On an SoC whose only DRM node
is a render-only GPU device, the DRM branch resolves seconds before a framebuffer
exists, and a task depending on `Tasks::Graphics` runs against nothing. Anything
that needs `/dev/fb0` must depend on `Tasks::Graphics::FBDev`.

An unresolved dependency does not error — it hangs. `TASKS_HANG_TIMEOUT` with a
list of unresolved tasks is the diagnostic; read the list, it names the missing
resource directly.

## Recovery-resident boot selection

A menu in stage-1 is not GRUB. Boot ROM and the device bootloader have already
selected a partition, loaded its kernel, ramdisk and device tree, and entered
Linux. The menu can choose later policy. It cannot retroactively ask the
bootloader for a different kernel.

Classify each proposed entry by the mechanism it needs:

| Entry | What must be proven |
|---|---|
| another root or NixOS generation under the running kernel | stage-1 can locate the closure, select its init and recover when it is incomplete |
| Android or another boot partition | the exact boot-control field, whether the command is persistent or one-shot, and how the menu returns on the following boot |
| fastboot or recovery | the vendor command or boot-control value, read back before reset |
| another kernel | supported `kexec`, or a verified flash-and-reboot workflow with an independent restore path |

Do not present an entry before its transition has worked outside the menu. A
button that only clears a persistent recovery command may boot Android once and
also remove the menu from every later normal boot. A physical recovery key is a
return path only after it has been tested with the replacement recovery image.

Inventory boot control with `android-firmware-lab`. Android normally stores the
bootloader message in `misc`, but vendor bootloaders may use another partition.
Resolve that partition by label, back it up, limit writes to the documented
field, and read the field back. Observe it before and after every reboot command
used by the design. A command named `reboot recovery` may persist a recovery
request instead of making a one-shot in-memory choice.

Shared storage is a separate gate. If the alternative root replaced Android's
`userdata`, booting Android is not dual boot. Android may format the unfamiliar
filesystem before the menu can recover it. Omit the Android entry until the
layout gives both systems compatible, isolated data storage or the exact stock
mount and format behaviour proves otherwise.

Keep the selector in one process and read input events directly, as described
in [display-bringup.md](display-bringup.md). Define and test the default and
timeout behaviour explicitly. Inactivity must never rewrite boot control merely
because no key was pressed.

## The mruby environment

init is mruby. Notable gaps and traps:

- `Dir` **exists** in the real stage-1 init (`Dir.glob`, `Dir.children`). A bare
  host `mruby` binary lacks mruby-dir, so testing task code against the host
  interpreter produces `NoMethodError` for things that work on device. Test on
  device, or accept the host interpreter is a different environment.
- `Thread` is absent. Anything periodic is a spawned process or a loop.
- `System.mount` consults `System.mount_points`, which bind-mounts procfs at
  `/.proc`; in a minimal initrd that path fails with exit 127. Use
  `System.run("mount", ...)` directly.
- `System.run` is synchronous and raises on failure; `System.spawn` detaches.
- `FileUtils.mkdir_p`, `File.read`, `File.write`, `File.exist?` are available.

## Observation channels

Ranked by how early they exist:

1. **Serial** — `mobile.boot.serialConsole = "ttyS0,921600n1"`. Needs physical
   access to test points on most phones.
2. **Framebuffer console** — `console=tty1`. See
   [display-bringup.md](display-bringup.md); it is far more likely to be
   silently broken than absent.
3. **`/run/log/stage-1.log`** — readable once you have any shell.
4. **USB gadget: adb, then SSH.**
5. **pstore/ramoops** — in principle survives a reboot, so in principle it is the
   only channel for a failure that kills the kernel. **Verify it on your device
   before relying on it.** On a MediaTek MT6762G 4.9 tree with
   `CONFIG_MTK_RAM_CONSOLE`, `PSTORE_RAM` and `PSTORE_CONSOLE` all set, neither
   `/sys/fs/pstore` nor `/proc/last_kmsg` had anything after a power-off. The
   symbols being present is not evidence the region is preserved. Prove it once,
   deliberately: trigger a known panic, power-cycle, look for it.

`/dev/console` (5:1) resolves to the **last** `console=` parameter on the
cmdline. With `console=ttyS0,... console=tty1`, `shellOnFail` lands on the panel,
not on serial. Order the parameters deliberately.

**Userspace writes to `/dev/console` never enter the kernel ring buffer.** So a
userspace loop flooding the console is invisible to `dmesg`, to `/proc/kmsg`,
and to anything built on them — the channel that shows the problem and the
channel you are reading are not the same channel. A backlight task spinning at
two console writes per iteration was found from a *photograph of the panel*
after the logs had been read repeatedly and showed nothing. When the symptom is
"slow" or "hung" and the logs are clean, look at the screen.

`/run/mobile-nixos-init-messages` is a **socket**, not a log file. Reading it as
a file gets you nothing.

Set `mobile.boot.stage-1.shell.shellOnFail = true` for the whole of bring-up. It
converts "the phone is dead" into "the phone is at a prompt with the reason on
screen".

## USB gadget

```nix
mobile.usb.mode = "gadgetfs";
mobile.usb.gadgetfs.functions = {
  rndis = "rndis.usb0";
  adb = "ffs.adb";
};
mobile.adbd.enable = true;
```

`mobile.usb.gadgetfs.functions` is an attrset and therefore **composes** — adb
and a network function coexist in one configuration. The internal
`usb.features` list is assembled from modules (`initrd-usb.nix` contributes
`"rndis"` when networking is enabled, `adb.nix` contributes `"adb"`).

Pick the network function from the *running kernel's* config, not from
preference. A 4.9 vendor tree commonly has `CONFIG_USB_F_RNDIS=y` and
`CONFIG_USB_CONFIGFS_RNDIS=y` with ECM/NCM/EEM unset — RNDIS is then the only
transport, regardless of it being the worse protocol.

## Networking and SSH

`mobile.boot.stage-1.networking.enable = true` gives the device **172.16.42.1**
and leases the host **172.16.42.2** via `udhcpd`; the task tries interfaces
`rndis0`, `usb0`, `eth0` in order.

Do **not** use `mobile.boot.stage-1.ssh.enable`. It runs `passwd -d root` and
starts dropbear with `-B`; upstream's own documentation says it "opens access to
all without a password nor ssh key".

Key-only dropbear as a stage-1 task:

```ruby
System.spawn("dropbear", "-R", "-s", "-E")
```

- `-s` disables password auth entirely; the account is locked anyway
  (`/etc/passwd` is `root:*:0:0:...`, there is no `/etc/shadow`).
- `-R` generates host keys on demand. Baking one in would put a host private key
  in a world-readable `/nix/store` path.
- `-E` logs to stderr, which is `/dev/console`, so failures land next to
  everything else.

Two things that are not obvious:

- **dropbear needs `libnss_files.so.*` copied into the initrd.** The initrd's
  glibc has no compiled-in files backend, so account lookup fails with no useful
  message. Ship it via
  `mobile.boot.stage-1.extraUtils = [{ package = pkgs.dropbear; extraCommand = ''cp -fpv "${pkgs.glibc.out}"/lib/libnss_files.so.* "$out"/lib/''; }]`.
- **Copy `authorized_keys`, do not symlink it into the store.** dropbear rejects
  a file it considers group- or world-writable, and resolving the symlink hands
  it a path it does not own. Write to `/root/.ssh/authorized_keys`, `chmod 700`
  the directory and `600` the file.

Keep the allowed keys in one checked-in file at the repo root, with a comment
saying that a fork which does not replace the list grants its author root.

**Run it on a port stage-2 does not use** — 2222, not 22. It outlives
`switch_root` and would otherwise hold the port openssh wants, and once stage-2
is up it can no longer authenticate anyone at all. Which port answers then tells
you which stage you are talking to, which is worth more than the port number.

## What a spawned task survives at switch_root

`System.spawn` detaches, and a detached process is **not** killed by
`switch_root` — it keeps running with its open binary from the initramfs, which
the kernel holds alive after the initramfs is gone. What it loses is everything
it resolves *by name at runtime*: `PATH` lookups, `/sys` and `/proc` paths, any
file it had not already opened. The process survives; its world does not.

This produces a specific bug shape. A periodic task written as

```ruby
System.spawn("sh", "-c", "while true; do refresh; sleep 1; done")
```

runs correctly for the whole of stage-1, then at handoff loses `sleep` from
`PATH`. `while true` with a failing body and no delay is a busy loop; it pins a
core and, if the body writes to `/dev/console`, floods the console. Observed
still spinning at 428 s of uptime, starving stage-2 badly enough to look like a
stage-2 hang — and it had been present on every boot since the port began.

Anything spawned from stage-1 that outlives it must fail closed:

- absolute store paths for every binary, never `PATH`
- loop on the resource itself (`while File.exist?(node)`), never on `true`
- `|| exit 0` on writes, so a vanished path ends the process instead of
  retrying forever

The general rule: a stage-1 helper that is still running after switch_root is
running in an environment nobody designed. Prefer letting it exit at handoff and
re-establishing the behaviour as a stage-2 unit.

The second worked example is worse, because the process appears to keep working.
dropbear spawned in stage-1 is still listening on its port under stage-2, and
still completes a TCP handshake — but it kept the *initramfs* as its root, and
stage-1 empties that:

```
# head -1 /proc/<dropbear-pid>/mountinfo
0 0 0:1 / / rw - rootfs rootfs rw     <- not the ext4 root PID 1 uses
# ls /proc/<pid>/root/etc/passwd      -> No such file or directory
```

No `/etc/passwd` means `getpwnam("root")` fails, so there is no home directory
to search for `authorized_keys`. It offers publickey, rejects the correct key,
and logs nothing. Nothing you write into stage-2's filesystem can reach it.
An open port is not a working service; see
[stage-2-access.md](stage-2-access.md).

**Processes are not the only thing inherited.** `/run` is a tmpfs that stage-2
moves rather than recreates, so stage-1's udev database arrives intact under
stage-2 — including records for gadget interfaces that were never tagged
`systemd`. That silently disables every declarative NixOS unit bound to those
devices, on a system that reports `running` with zero failed units.
[stage-2-access.md](stage-2-access.md) is the whole of that failure.

## Common stage-1 failures

| Symptom | Cause |
|---|---|
| `TASKS_HANG_TIMEOUT`, unresolved `Tasks::Target<SwitchRoot>` | no rootfs found; `/dev/disk/by-label/NIXOS_SYSTEM` does not exist |
| stage-2 crawls or appears hung, logs clean | a stage-1 helper survived switch_root, lost `PATH`, and is busy-looping on the console |
| Task never runs, no error | nothing attached it to a target |
| Task runs too early against missing hardware | depended on `Tasks::Graphics` instead of `Tasks::Graphics::FBDev` |
| `NoMethodError` on `Dir` when testing locally | host mruby lacks mruby-dir; not a device problem |
| `mount` exits 127 | `System.mount` needs `/.proc`; call `System.run("mount", ...)` |
| SSH refuses every key silently | missing `libnss_files.so.*`, or store-symlinked `authorized_keys` |
| SSH refuses every key **only after stage-2 comes up** | stage-1's dropbear still holds the port; its root is the emptied initramfs, so it has no `/etc/passwd` |
| stage-2 reports `running`, zero failed units, and none of the network config applied | stage-1's udev database was inherited through `/run`; the interface is untagged, so its `.device` unit never activates |
