# Console and access

## HDMI is not a console

On Orin there is no Linux console on HDMI or DisplayPort. `/dev/console` is
`ttyTCU0`, the Tegra Combined UART.

UEFI *does* render on HDMI. This is precisely what makes the trap effective: you
watch firmware draw a boot menu on the monitor, select an entry, and the screen
goes dark forever while the kernel boots fine. Nothing is wrong. There was never
going to be text.

A graphical session will appear if the configuration starts one (X or Wayland
with the NVIDIA driver). That is a display server, not a console, and it does
not exist during boot, during an initrd failure, or before the first successful
activation — the three moments you need it.

Plan for exactly three ways in, and have at least two:

1. **SSH** — requires `services.openssh.enable` in the *installed* config.
2. **Type-C USB device mode** — an ACM console plus a network gadget.
3. **UART** — a 3-pin adapter on the debug header. The only one that works when
   the kernel does not.

## The lockout

The single most common way to lose a freshly installed Jetson:

- The installer image enables sshd, avahi and an authorized key.
- `configuration.nix` for the target inherits none of that, because the ISO
  module and the host module are separate files.
- The install succeeds. The board reboots, comes up on NVMe, gets a DHCP lease,
  and answers ICMP.
- Nothing listens. `hostname.local` does not resolve. There is no console on
  the monitor.

Check before installing, not after:

```sh
nix eval --raw --impure --expr '
let f = builtins.getFlake (toString ./.);
    c = f.nixosConfigurations.<host>.config;
in builtins.toJSON {
  openssh  = c.services.openssh.enable;
  avahi    = c.services.avahi.enable;
  firewall = c.networking.firewall.enable;
  tcp      = c.networking.firewall.allowedTCPPorts;
}'
```

`{"avahi":false,"openssh":false,"firewall":true,...}` is the lockout, visible
minutes before it costs anything.

## Distinguishing the failure

```sh
ping -c2 <ip>                        # the kernel is up and networking works
timeout 5 bash -c "echo >/dev/tcp/<ip>/22"
```

| Result | Meaning |
|---|---|
| `connection refused` | the port is reachable, nothing is listening — sshd is off or crashed |
| `connection timed out` | a firewall dropped the packet — the port was never opened |
| ping fails too | link, DHCP, or the kernel never got there |

Ping alive plus every port filtered is the signature of a target config that
never enabled sshd, not of a broken install.

A third case worth naming: sshd that accepts the TCP connection and then dies
before its banner —

```
kex_exchange_identification: read: Connection reset by peer
```

with nmap reporting `tcpwrapped`. That is not a configuration problem. It is
sshd being unable to fault its own pages in, which on a Jetson means the boot
medium is failing. Go to [storage-media.md](storage-media.md).

## USB device mode

Only the **Type-C port** is device-capable — it is driven by `tegra-xudc` as a
peripheral. The USB-A ports are host-only. Connecting the board's USB-A to a
host's USB-A is host-to-host and will never enumerate.

A minimal gadget exposes an ACM console and an NCM ethernet function:

```nix
boot.kernelModules = ["tegra-xudc" "libcomposite"];
```

Build it under `/sys/kernel/config/usb_gadget/`, then bind a UDC — binding is
what makes the port enumerate:

```sh
udc=$(ls /sys/class/udc | head -1)
echo "$udc" > "$g/UDC"
```

Declare NVIDIA's vendor ID (`0x0955`) so existing L4T udev rules and host
drivers keep applying. `0x7020` is the conventional device-mode product ID;
`0x7523` is recovery mode, a different thing entirely.

The ACM function gives `ttyGS0` on the board and `/dev/ttyACM0` on the host.
Pair it with a getty, and set `services.getty.autologinUser` if you want the
serial line to be a way *in* rather than a login prompt you cannot satisfy:

```nix
systemd.services."serial-getty@ttyGS0" = {
  enable = true;
  wantedBy = ["multi-user.target"];
  serviceConfig.Restart = "always";
};
```

The NCM function needs an address on the gadget side (L4T's default is
`192.168.55.1`), a DHCP server bound to that interface, and firewall holes
scoped to it:

```nix
networking.firewall.interfaces.usb0 = {
  allowedTCPPorts = [22 53];
  allowedUDPPorts = [53 67];
};
```

Mark the interface unmanaged in NetworkManager, and set `bind-dynamic` on
dnsmasq — the gadget interface does not exist when dnsmasq starts.

### When the gadget does not appear

```sh
lsusb | grep 0955      # the VID:PID your gadget declares
ls /dev/ttyACM*
ip -br addr            # a new interface on the gadget subnet
```

Nothing in `lsusb` means the port did not enumerate. That is electrical or
physical, never configuration:

1. **Charge-only cable.** USB-A→USB-C cables frequently omit the data pairs.
   They power the board and enumerate nothing. First suspect, every time.
2. **Wrong port.** See above — USB-A on the board is a host port.
3. The `usb-gadget` unit failed, or no UDC was available to bind.

Only the third is worth reading logs for, and you cannot read them without a
console, which is the whole reason to have a second access path.

## mDNS

`avahi` on the installer and not on the target is the usual asymmetry. If
`<host>.local` stops resolving after an install, that is expected and is also
useful evidence: the installer is no longer running, so the board booted from
its real disk.

Tailscale sidesteps the whole question — MagicDNS gives the node a name without
avahi and without being on the same L2. It is a good answer for a board you will
administer remotely, and a bad answer for first contact, because bringing it up
requires the console you do not have yet.
