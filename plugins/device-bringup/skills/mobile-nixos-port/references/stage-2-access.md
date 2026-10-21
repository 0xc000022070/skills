# Stage-2: reaching a booted device, and why its config may never have applied

## Contents

- `running` with zero failed units is not evidence
- What `/run` carries across switch_root
- The `.device` unit trap
- Addressing and routing without a `.device` unit
- dhcpcd bids on interfaces that go nowhere
- Two ssh servers on one link
- mDNS, and which resolver answered
- Internet for a device whose only link is the build host
- What to hold off until the last deploy

## `running` with zero failed units is not evidence

A device can reach

```
systemctl is-system-running   ->  running
systemctl --failed            ->  0 loaded units listed
```

across consecutive boots while its network configuration has **never been
applied**. Nothing reports it.

The mechanism is that systemd's green summary counts *failed* units. A unit
whose conditions were not met is **skipped**, and skipped is not failed — it
does not appear in `--failed`, it does not degrade the system state, and it
leaves no log line anyone greps for. `ConditionResult=no` is the only place it
shows.

So the completion criterion for this rung is not "it booted clean". It is:

```sh
systemctl show <unit> -p ConditionResult -p ActiveState -p ExecMainStatus
```

for each unit that was supposed to do something, and then an observation of the
*effect* — `ip route`, `ip addr`, a resolved name — not of the unit.

Corollary: a NixOS option that generates a unit is not proof the option took
effect. On this class of device, assume nothing declarative applied until the
effect is measured.

## What `/run` carries across switch_root

`/run` is a tmpfs that stage-1 mounts and stage-2 **moves**, not recreates.
Everything in it is inherited verbatim. Two inheritances matter, and both are
invisible:

1. **Detached processes** — see the switch_root section of
   [stage-1.md](stage-1.md).
2. **The udev database** at `/run/udev/data/`, exactly as stage-1's udevd wrote
   it.

The second one is the subtler of the two, because it makes stage-2's udevd
*agree* with a record it did not create and would never have written.

## The `.device` unit trap

systemd synthesises `sys-subsystem-net-devices-<if>.device` only for a device
udev has tagged `systemd` (`99-systemd.rules`: `SUBSYSTEM=="net", TAG+="systemd"`).
The initrd's udevd does not ship those rules, so a gadget interface brought up
in stage-1 has a record with no `TAGS` line at all:

```
$ cat /run/udev/data/n<ifindex>
E:LD_LIBRARY_PATH=/nix/store/...-extra-utils-<device>-.../lib
E:PATH=/nix/store/...-extra-utils-<device>-.../bin
E:ID_PROCESSING=1
```

-- the *initrd's* package paths, under stage-2. The chain from there:

| Step | State |
|---|---|
| `sys-subsystem-net-devices-rndis0.device` | never activates |
| `network-addresses-rndis0.service` (`BindsTo=` it) | `ConditionResult=no` |
| `networking-scripted.target` | empty `WantedBy` |
| `networking.interfaces.*` / `networking.defaultGateway` | silently discarded |

`systemd-udev-trigger.service` still reports `Result=success` with
`ExecMainStatus=0`, and the database still holds ~1500 entries, so every
diagnostic aimed at udev says it is healthy. It is: the record is present, just
inherited untagged.

**Why this hides for so long:** the interface keeps working, because stage-1
already set its address by hand (`Tasks::…dhcpd`). The address is there — just
not from the configuration that claims to set it. It surfaces only when you need
something stage-1 *didn't* do, typically a default route.

Two traps while diagnosing:

- **`udevadm info`'s `T:` field is DEVTYPE, not a tag.** `T: gadget` is not a
  tag named `gadget`. Tags appear only as `TAGS=`:
  `udevadm info --query=property /sys/class/net/<if> | grep TAGS`.
- Re-triggering the uevent (`udevadm trigger --subsystem-match=net`) fixes the
  class rather than the instance, and a synthetic `add` on a vendor kernel is a
  gamble on a device whose recovery costs a physical power cycle. Prefer the
  oneshot below.

**Generalise it.** This is not a networking bug. Any NixOS option implemented
through a `.device` unit has the same shape on the same devices — `.mount` and
`.swap` units, and anything with `BindsTo=`/`After=` a device. Suspect it
whenever a declarative setting appears to be ignored on hardware that stage-1
touched first.

## Addressing and routing without a `.device` unit

Bind to nothing. A oneshot ordered against targets rather than devices runs
regardless of what udev thinks:

```nix
systemd.services.usb-network-setup = {
  description = "Addressing on ${cfg.interface}";
  wantedBy = [ "multi-user.target" ];
  wants    = [ "network-pre.target" ];
  after    = [ "network-pre.target" ];
  before   = [ "network.target" ];
  path     = [ pkgs.iproute2 ];
  serviceConfig = { Type = "oneshot"; RemainAfterExit = true; };
  script = ''
    if [ ! -e /sys/class/net/${cfg.interface} ]; then
      echo "${cfg.interface} is absent; the gadget did not survive switch_root" >&2
      exit 1
    fi
    ip link set ${cfg.interface} up
    ip addr replace ${cfg.address}/24 dev ${cfg.interface}
    ip route replace default via ${cfg.hostAddress} dev ${cfg.interface}
  '';
};
```

- `replace`, not `add`, throughout: stage-1 has usually set the address already,
  and this has to be a no-op rather than `EEXIST`.
- The absence check turns "the gadget died at handoff" into a failed unit with a
  sentence in it, instead of a unit that silently succeeds at nothing.
- `networking.nameservers` **does** work — `resolv.conf` is a generated file and
  depends on no device unit. It was the one half of this that landed. Split
  accordingly: files declarative, netlink imperative.

Routing the device's own traffic through the machine it is plugged into needs
that machine to forward and masquerade; without it the default route blackholes
and the symptom is a service that "cannot authenticate" (see below).

## dhcpcd bids on interfaces that go nowhere

`networking.useDHCP` is usually left on for interfaces that do not exist yet
(Wi-Fi). It then also bids on the gadget interface that is meant to be *serving*
DHCP, and on anything else the kernel exposes.

The trap on a vendor kernel is `ifb0`/`ifb1` — **intermediate functional block**
devices, traffic-shaping stubs built into the kernel with no link to anywhere.
dhcpcd cannot tell, bids, finds no server, falls back to IPv4LL, and installs:

```
default dev ifb0 scope link src 169.254.183.20 metric 1001002
```

On a device with no other default route, that *is* the default route, and every
packet leaving the device is handed to a stub that drops it.

```nix
networking.dhcpcd.denyInterfaces = [ cfg.interface "ifb*" ];
```

**The symptom does not look like routing.** A daemon that needs to reach a
control plane (tailscaled, a package fetch, NTP) times out with no error that
mentions the network — tailscaled simply never prints a login URL, which reads
like an authentication problem. Check `ip route` before believing any daemon's
account of why it failed.

## Two ssh servers on one link

If stage-1 runs dropbear (see [stage-1.md](stage-1.md)), it is still running
under stage-2 — `switch_root` does not kill it. Which port answers therefore
identifies the stage:

| Open | Stage | Use |
|---|---|---|
| 2222 only | stage-1 | dropbear, keys baked into the initrd. Authenticates fine. This is the deploy channel. |
| 22 and 2222 | stage-2 is up | use **22** (openssh). 2222 still listens and **refuses your key**. |

**dropbear on 2222 cannot authenticate under stage-2, and this is not fixable
from stage-2.** It survives switch_root but keeps the *initramfs* as its root,
which stage-1 then empties:

```
# head -1 /proc/<dropbear-pid>/mountinfo
0 0 0:1 / / rw - rootfs rootfs rw          <- not the ext4 root PID 1 uses
# ls /proc/<pid>/root/root/.ssh/           -> empty
# ls /proc/<pid>/root/etc/passwd           -> No such file or directory
```

With no `/etc/passwd`, `getpwnam("root")` fails, so there is no home directory
left to search for `authorized_keys`. It offers publickey, rejects the correct
key, and logs nothing. **Writing keys into stage-2's `/root/.ssh` — tmpfiles or
otherwise — is invisible to it**; that filesystem is not one this process can
see. A `systemd.tmpfiles` rule that "fixes" this is dead code that looks like a
fix. Do not add one; document the port number instead.

Leave 2222 open in the firewall anyway: closing it does not stop the process,
and during stage-1 it is the only ssh there is.

Host-side, pin the names once so neither stage needs flags:

```
Host <device> <hostname> <hostname>.local
  HostName 172.16.42.1
  User root
  IdentityFile ~/.ssh/id_ed25519
  IdentitiesOnly yes
  ControlMaster auto
  ControlPath ~/.ssh/cm-%r@%h:%p
  ControlPersist 600

Host <device>-stage1
  HostName 172.16.42.1
  Port 2222
  StrictHostKeyChecking no
  UserKnownHostsFile /dev/null
```

- `IdentitiesOnly=yes` is not optional. Without it the agent offers other keys
  first and dropbear closes with `Permission denied (publickey)` *after* logging
  `Server accepts key`, which reads exactly like a wrong key.
- stage-1's `-R` regenerates the host key every boot, hence the unpinned entry.
- **A full rootfs deploy regenerates stage-2's host keys.** Re-pin after every
  deploy (`ssh-keygen -R`, then `ssh-keyscan`) or the next connection fails with
  a host-key warning that looks like an attack.

## mDNS, and which resolver answered

Publishing the hostname is the difference between an IP the operator has to
remember and a name that survives re-addressing:

```nix
services.avahi = {
  enable = true;
  allowInterfaces = [ cfg.interface ];        # not every interface
  publish = { enable = true; addresses = true; workstation = true; };
  extraServiceFiles.ssh = "${pkgs.avahi}/etc/avahi/services/ssh.service";
  nssmdns4 = true;
};
networking.firewall.interfaces.${cfg.interface}.allowedUDPPorts = [ 5353 ];
```

Bind it to the gadget interface only. Unbound, it also announces the IPv4LL
addresses dhcpcd invented on the stubs above, and the host picks one of those.

avahi runs clean on a 4.9 kernel — it needs none of the syscalls in
[old-kernel-userspace.md](old-kernel-userspace.md).

**Verify from the device, then be careful which host tool you believe.** A build
host commonly runs two independent mDNS clients, and they do not agree:

- `avahi-resolve -n <host>.local` reporting `Timeout reached` may be a statement
  about the *host*. Check the host's `allow-interfaces=` — an avahi pinned to
  the wired and wireless interfaces never joins the multicast group on the USB
  link, and its journal only ever says `New relevant interface wlo1.*`.
- `systemd-resolved` is the second client and usually does have the link
  (`resolvectl status <if>` -> `mDNS/IPv4 mDNS/IPv6`).
- Ask it for `--type=A` explicitly. A bare query answers from the IPv6 cache and
  returns only `fe80::…%<ifindex>`, which needs a scope id and reads like the A
  record is missing:

```sh
resolvectl query --type=A <host>.local
# <host>.local IN A 172.16.42.1   -- link: enp0s20f0u1

ssh <device> 'avahi-browse -rpt _ssh._tcp'     # what the device actually claims
# =;rndis0;IPv4;<host>;_ssh._tcp;local;<host>.local;172.16.42.1;22;
```

## Internet for a device whose only link is the build host

A port with no Wi-Fi driver has exactly one path to the network: the gadget link.
The device already has a default route via the host
([above](#addressing-and-routing-without-a-device-unit)) — what is missing is a
host willing to forward it.

**The correct fix is masquerading on the host**, and it is worth stating first
because everything below is a workaround for not having it:

```sh
sysctl -w net.ipv4.ip_forward=1
nft add table ip nat
nft add chain ip nat postrouting '{ type nat hook postrouting priority 100; }'
nft add rule ip nat postrouting ip saddr 172.16.42.0/24 oifname "<uplink>" masquerade
```

That gives ICMP, UDP, DNS and NAT traversal, and the device needs no
configuration at all — its route is already right. It needs root on the host, and
that is the only reason to look further.

### Without root on either side

`ssh -R` reverse-forwards a port from the device to the host. No privilege is
required at either end, and the transport is the ssh you already have.

The obvious form is reverse *dynamic* forwarding — `ssh -N -R 1080 <device>`,
OpenSSH 7.6+ — which puts a SOCKS5 proxy on the device's `127.0.0.1:1080`
exiting through the host. **It does not work for Go programs.** Measured on one
socket, in one minute:

```
curl --socks5-hostname 127.0.0.1:1080 https://…   ->  200
tailscaled (Go proxy dialer)                      ->  proxyconnect tcp: socks connect
                                                      127.0.0.1:1080->127.0.0.1:1080: EOF
```

Instant EOF, not a timeout. ssh's built-in SOCKS server is minimal and the Go
client's handshake does not survive it. Do not spend the afternoon on it — change
protocol. **HTTP CONNECT is handled natively by every Go client, by `curl`, and
by anything reading `HTTPS_PROXY`.** Run a CONNECT proxy on the host and use a
*plain* remote forward:

```sh
tinyproxy -d -c tinyproxy.conf            # Port 3128, Listen 127.0.0.1, Allow 127.0.0.1
ssh -N -R 127.0.0.1:3128:127.0.0.1:3128 <device>
```

Then point the consumer at it. For a systemd service, an environment drop-in:

```
# /etc/systemd/system/<svc>.service.d/proxy.conf
[Service]
Environment=HTTPS_PROXY=http://127.0.0.1:3128
Environment=HTTP_PROXY=http://127.0.0.1:3128
Environment=NO_PROXY=127.0.0.1,localhost
```

Three traps, each of which cost a debugging round:

- **A host-side listener is the wrong shape.** Binding a proxy on the host's
  `172.16.42.2` and pointing the device at it puts the host firewall in the path;
  on NixOS only port 22 is open on that interface and the connection is simply
  dropped. Reverse-forwarding rides the ssh session that already works.
- **`ControlMaster auto` breaks a persistent `-R` tunnel.** The second session
  reuses the multiplexed socket, its forward request is refused, and
  `ExitOnForwardFailure` exits — under a supervisor that is a restart loop
  (`NRestarts=53` before it was diagnosed). Pass `-o ControlMaster=no -o
  ControlPath=none`.
- **A SIGKILLed client leaves the device-side `sshd-session` holding the port.**
  Every reconnect then fails with `remote port forwarding failed for listen port
  N`, which reads like a config error. Kill the orphan on the device.

Supervise it — a tunnel started from a shell dies with the shell:

```sh
systemd-run --user --unit=<device>-httptunnel --collect \
  --property=Restart=always --property=RestartSec=2 -- <path>/http-tunnel.sh
```

### What a CONNECT proxy can and cannot carry

TCP only. A mesh VPN still enrols and still works, but relayed:

| | over host NAT | over an HTTP CONNECT proxy |
|---|---|---|
| control plane, TLS | yes | yes |
| UDP / NAT traversal | yes | **no** — `netcheck` reports `UDP: false` |
| peer path | direct | DERP relay |
| ICMP | yes | no |

Enrolment through the proxy is genuinely enough to be reachable from anywhere —
confirm it by the relay, not by the login succeeding:

```sh
tailscale status --json | jq '.Self.Relay, .Self.Online'   # "den", true
journalctl -u tailscaled | grep 'derp-'                    # magicsock: derp-16 connected
```

A peer on the same USB link still connects *directly* (`tailscale ping` →
`pong … via 172.16.42.1:41641`), because that path needs no proxy. Off-LAN peers
take the relay. Run `netcheck` from inside the service's environment, not from a
bare shell — without the proxy variables it returns an empty result that looks
like a broken daemon.

### It is not durable until it is in the repo

A `/run/systemd/system/*.d/` drop-in is the fastest way to test this and it does
not survive a reboot. On NixOS you cannot promote it in place either:
`/etc/systemd/system` is a symlink into the store. Persisting the proxy
configuration means a rebuild and a deploy — which destroys the enrolment state
the proxy existed to obtain (below). Decide which you want before you enrol:
host NAT needs no device change at all and therefore no redeploy.

## What to hold off until the last deploy

Anything that stores enrolment state under `/var` — a VPN's node key, a
registered agent, a machine identity — must be enrolled **after** the final
rootfs write. A full-image deploy replaces the filesystem, so state established
before it is gone without a message, and the daemon comes back looking exactly
like a fresh install.

Sequence: deploy, boot, verify routing, *then* enrol.

Once enrolled, that state is a handful of files and re-enrolling is a browser
round trip you cannot automate — so carry it across the next deploy instead of
paying for it again:

```sh
ssh <device> 'tar --exclude="*.log*" -cf - -C /var/lib <daemon>' > <daemon>-state.tar
# deploy, boot
ssh <device> 'systemctl stop <daemon>; tar -xf - -C /var/lib' < <daemon>-state.tar
ssh <device> 'systemctl start <daemon>'
```

Take the backup **before** you need it, and check the archive lists the state
file rather than trusting the exit code — GNU tar treats a misplaced `--exclude`
as an error *after* writing a complete archive, so a non-zero exit here does not
mean an empty one.
