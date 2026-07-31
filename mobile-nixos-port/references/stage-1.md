# Stage-1: init, tasks, observability, access

## Contents

- The task graph
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
5. **pstore/ramoops** — survives the reboot, so it is the only channel for a
   failure that kills the kernel.

`/dev/console` (5:1) resolves to the **last** `console=` parameter on the
cmdline. With `console=ttyS0,... console=tty1`, `shellOnFail` lands on the panel,
not on serial. Order the parameters deliberately.

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

## Common stage-1 failures

| Symptom | Cause |
|---|---|
| `TASKS_HANG_TIMEOUT`, unresolved `Tasks::Target<SwitchRoot>` | no rootfs found; `/dev/disk/by-label/NIXOS_SYSTEM` does not exist |
| Task never runs, no error | nothing attached it to a target |
| Task runs too early against missing hardware | depended on `Tasks::Graphics` instead of `Tasks::Graphics::FBDev` |
| `NoMethodError` on `Dir` when testing locally | host mruby lacks mruby-dir; not a device problem |
| `mount` exits 127 | `System.mount` needs `/.proc`; call `System.run("mount", ...)` |
| SSH refuses every key silently | missing `libnss_files.so.*`, or store-symlinked `authorized_keys` |
