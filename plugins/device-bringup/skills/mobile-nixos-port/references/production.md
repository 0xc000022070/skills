# Running real workloads on a ported device

## Contents

- A deploy that can undo itself
- Bounding the two things that grow
- The trust boundary is the link set
- Credentials that must not enter the repository
- A VPN daemon needs a real TUN and the right netfilter backend

A port that boots is not a machine you can leave running. Everything below came
out of a device whose only lifeline is a USB gadget and whose recovery is a
physical power cycle with the phone in hand.

## A deploy that can undo itself

The failure that matters is not a build error. It is a switch that succeeds and
takes the only transport with it. There is no keyboard, so the configuration
that breaks the link cannot be fixed from the device.

Make the switch a deadman: arm a timer, and roll the system profile back unless
something confirms.

```
host: deploy-guard arm  ->  switch  ->  wait for the device to answer  ->  confirm
                                   \-> silence -> timer elapses -> rollback + switch
```

Confirming from the *host*, only after the device answers again, is what makes
this a test rather than a ritual. An unreachable device confirms nothing.

Arm from two places, because they cover different failures: from the host before
the switch (covers a switch that dies before activation runs), and from the
activation script (covers `nixos-rebuild switch --target-host` and anything else
that never heard of the guard).

Three implementation details are load-bearing, all found by breaking them:

- **Use a transient unit, not a declared one.** `switch-to-configuration` runs
  the activation script *before* it reloads the manager, so a declared
  `deploy-guard.service` does not exist yet at the moment you arm it, and
  `systemctl start` fails on exactly the fresh install the guard exists to
  protect. `systemd-run` needs no unit file and no reload.
- **A transient unit is also in no generation**, so no switch restarts it. A
  declared guard is restarted by any switch that changed its unit file —
  including the rollback it is performing, halfway through.
- **Do not let a failed arm abort activation.** The activation script runs under
  `set -e`; an unguarded arm that fails leaves the system stranded between two
  generations. Warn and continue: a lost safety net is better than a half-applied
  switch.

Do not arm at boot. `/run/systemd/system` distinguishes the two — stage-2 init
runs the activation script and only then execs systemd — because an unattended
reboot must not roll the device back for not being confirmed.

Report armed state from the timer's next elapse, not from `is-active`. An elapsed
timer systemd has not collected yet still reads active with its next elapse at
infinity, which reports the opposite of the truth: the rollback already ran.

What this cannot cover: a configuration that breaks the *next boot* rather than
the running system. The guard runs inside the system it is judging.

## Bounding the two things that grow

Journal and store, both unbounded by default, on flash you are trying to spare.
Measured on one port six hours after a boot, rootfs 16 GiB with 9.8 GiB free:

| | Size | Default that produced it |
|---|---|---|
| `journalctl --disk-usage` | 907.6 M | `SystemMaxUse` = 10% of the filesystem |
| `/nix/store` | 4.9 G, 23 generations | no gc timer at all |

On a vendor kernel most of the journal is not yours: 380894 of 872463 lines in
that boot were kernel, dominated by MediaTek gauge and charger debug at ~17
lines/s, with no runtime knob to turn it off. Treat the volume as a given and
cap it.

`min-free`/`max-free` matter more than the weekly collection. They are what stops
a `nix copy` of a large closure onto a nearly full rootfs from failing partway
and leaving a generation that cannot be activated.

Keep the gc age comfortably above the rollback window the deploy guard needs —
it rolls back exactly one generation, so any sane age is safe, but say so where
the option is defined.

Skip `nix.optimise`. Hard-linking a multi-gigabyte store reads every file in it,
on the flash the rest of the module exists to protect, to reclaim space that
deleting whole closures already reclaims.

## The trust boundary is the link set

A device with no radio has no general network surface. Both of its links are
point-to-point and already authenticated — one physically, one by the VPN — and
nothing else can route to it.

That inverts the usual binding advice. **Listen on every interface and let the
firewall narrow it**, rather than binding services to a specific address:
binding to the VPN address means ordering units after an address that appears
asynchronously, and units that wait on this class of device tend to wait forever.

Say this out loud in the module. A reader who sees `0.0.0.0` without the
reasoning will "fix" it and hang the boot.

Redis needs both halves. Since Redis 7, protected-mode triggers on *the default
user having no password* rather than on the old "no bind and no requirepass"
pair, so widening the bind alone still returns DENIED to every non-loopback
client — which reads like a firewall problem from the other end. The password is
mandatory, not hardening.

Generate secrets on the device, into a `0700` directory, and keep them out of
the store. When reading `/dev/urandom` for one, read a fixed block into a
variable rather than piping through `head -c`: the pipe closes under a generator
that never ends and leaves `tr: write error: Broken pipe` in the journal on every
start.

## Credentials that must not enter the repository

A Wi-Fi password does not belong in a public flake, and no amount of secret
management makes a declarative network profile the right shape for a network
somebody joins once from the couch. Ship the *tool*, not the credential:
NetworkManager for `nmcli device wifi connect <ssid> --ask`, run on the device.

The dangerous part is that NetworkManager claims every interface it is not told
to leave alone, and the first one it finds is the USB gadget that carries every
ssh session and every deploy. Losing it costs a physical power cycle.

Invert the default rather than listing names:

```nix
networking.networkmanager.unmanaged = [ "*" "except:type:wifi" ];
```

A name list has to be right about every interface that ever appears, and these
kernels already expose `ifb0`, `ifb1` and several tunnel stubs. A type also
survives the udev gap on these devices: an interface whose record carries no
tags is still not Wi-Fi, so it stays unmanaged.

## A VPN daemon needs a real TUN and the right netfilter backend

Two silent degradations, both of which leave a daemon that reports healthy.

**TUN.** Without a real `/dev/net/tun` the daemon falls back to userspace
networking, which can reach the VPN but cannot be reached from it — precisely
backwards for remote management. Verify `CONFIG_TUN=y` and the character device,
do not infer it.

**Backend.** These daemons install their own netfilter rules and must land on the
same backend as the rest of the system. On a 4.x vendor kernel that is legacy
iptables: `CONFIG_NF_TABLES=y` buys nothing when every expression module
(`NFT_COUNTER`, `NFT_SET_HASH`, the `NFT_CHAIN_*` family) is unset, and the
failure names a store path rather than the cause:

```
adding [-j ts-input] in filter/INPUT: running [/nix/store/…-iptables-1.8.13/bin/iptables
  -t filter -I INPUT 1 -j ts-input --wait]: exit status 4:
  iptables v1.8.13 (nf_tables): RULE_INSERT failed (No such file or directory)
```

The backend has to be chosen **inside** the package, not around it. nixpkgs wraps
such daemons with `--prefix PATH` over their own closure, and a prefix outranks
whatever the unit's `path` adds after it, so the unit ends up holding both and
runs the wrong one. Override the package's inputs.
