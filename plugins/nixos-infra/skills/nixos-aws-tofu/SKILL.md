---
name: nixos-aws-tofu
description: Maintain a small fleet of single-purpose NixOS machines on AWS EC2 provisioned with OpenTofu and secrets managed by agenix — add or change a host, deploy a closure to aarch64 Graviton from an x86_64 workstation, rotate a secret and make the service actually pick it up, move ingress rules, and keep two Tofu roots from reaching each other's state. Use when editing hosts/*.nix or modules/*.nix, running tofu plan/apply against a staging or prod root, adding an agenix secret or a recipient, debugging a unit that fails activation with an empty /run/agenix, an SSH or database port that times out, a nixos-rebuild that never finishes evaluating, a flake that cannot see a file you just wrote, or a database password that was applied but does not authenticate. Grounded in the nshard-infra layout (p01 prod, l01 staging, d01 skeleton); the boundary, secret and deploy reasoning generalizes to any tofu-provisions/nix-configures split.
allowed-tools: Read Grep Glob Edit Write Bash(nix:*) Bash(tofu:*) Bash(git status:*) Bash(git diff:*) Bash(git log:*) Bash(getent:*) Bash(ssh-keyscan:*) Bash(dig:*)
disable-model-invocation: false
metadata:
  author: Luis Quiñones
  version: "1.0.0"
  category: nix
---

# NixOS on AWS, provisioned by OpenTofu

Two systems, one machine, a boundary that must not blur:

| Layer | Owns | Never |
|---|---|---|
| `tofu/` | EC2 instance, EIP, security group, DNS record, state buckets | provisioners that configure the OS |
| `hosts/`, `modules/` | packages, users, sshd, firewall, systemd units, PostgreSQL, Redis, Caddy, backups | creating cloud resources |

A machine is `module "host"` plus what is genuinely unique to it. Shared shape
lives in `tofu/modules/host/`, imported by each root — never copied between
them. Scaling means moving module imports between `hosts/*.nix`, not
duplicating config.

Read the repo's own `AGENTS.md` first. It is the authority on scope (no
Kubernetes, no RDS, no HA), naming, and which host may bind a database
publicly. This skill covers the mechanics that document does not.

## Change ladder

Falsifiable states. Do not claim a rung you have not observed, and do not
infer a later rung from an earlier one.

| Rung | Proven by |
|---|---|
| Nix change evaluates | `nix flake check --no-build` passes, every host included |
| Tofu change parses | `tofu validate` and `tofu fmt -check` |
| Tofu change is what you meant | `plan` shows no replacement you did not ask for |
| Provider resources exist | `apply` succeeded, outputs resolve |
| Name resolves | `getent hosts <fqdn>` returns the EIP — not a reachability rung |
| Host reachable | a **port answers**; DNS and ICMP prove nothing |
| Closure deployed | `nixos-rebuild switch` exited 0 **on the target** |
| Unit runs the new config | `systemctl show -p ActiveEnterTimestamp` moved |
| Service accepts the credential | a client authenticates end to end |

The last three are separated deliberately. A rebuild that exits 0 routinely
leaves a service running the *previous* secret, because only the file content
under `/run/agenix` changed and the unit's store path did not. See
[agenix.md](references/agenix.md).

## Route the work

| Task | Read |
|---|---|
| Adding a secret, a recipient, rotation, activation failures, empty `/run/agenix` | [agenix.md](references/agenix.md) |
| State backends, credentials, security groups, instance replacement, ingress | [tofu-aws.md](references/tofu-aws.md) |
| Deploying to aarch64, host modules, PostgreSQL/Redis bring-up, the check VM | [nixos-hosts.md](references/nixos-hosts.md) |

## Hard rules

- **agenix recipients are raw SSH public keys, never `ssh-to-age` output.**
  That conversion is a sops-nix idiom. agenix hands the host's
  `/etc/ssh/ssh_host_ed25519_key` to `age -i`, which opens only `ssh-ed25519`
  stanzas; an `age1...` recipient yields an X25519 stanza the host cannot
  decrypt, and the consuming unit fails with an empty `/run/agenix`.
- **`agenix -e` ignores `$EDITOR` when stdin is not a TTY.** It tests
  `[ -t 0 ]` and otherwise does `cp /dev/stdin "$FILE"`. An `EDITOR` shim
  script therefore writes an **empty** secret and reports success. Non-
  interactive writes must pipe the value in.
- **Never declare a secret a host cannot decrypt.** agenix fails *activation*,
  not just the one unit, so one prod-only secret in a shared module bricks the
  staging rebuild. This is why declarations are split per host.
- **A rebuild does not restart a unit when only secret content changed.**
  Rotating a value and running `nixos-rebuild switch` leaves the old
  credential live. Restart the unit explicitly and verify by authenticating.
- **Flakes see only git-tracked files.** A new `pkgs/*.nix` fails with "is not
  tracked by Git" until `git add`. Staging is enough; a commit is not
  required. The inverse holds on the target: the tarball shipped to a host has
  no `.git`, so the flake there sees *every* file including uncommitted edits.
  Know which of the two you are in before debugging a stale build.
- **`connection timed out` and `connection refused` are different diagnoses.**
  Refused means the host is up and nothing listens. Timed out means a packet
  was dropped — a security group, almost always. Do not merge them into "SSH
  is broken", and do not reach for the AWS console before you have made that
  distinction.
- **Security groups are allow-only and rule-limited.** There is no deny rule,
  and the quota is 60 inbound rules per group (hard ceiling 1000 per network
  interface). Any policy needing an enumerated country or region — hundreds to
  tens of thousands of CIDRs — is not expressible. Do not attempt it.
- **A `/32` allowlist against a residential connection is a time bomb.** CGNAT
  leases rotate; the address you pinned yesterday locks you out today. Pin the
  ISP's allocation, or drop the allowlist for key-only SSH and keep it for the
  database ports, where password auth makes source filtering worth something.
- **Staging's wide ingress must never propagate to prod.** Each root holds its
  own `variables.tf`, which is what keeps an open staging contained. Check
  which root you are editing before changing a CIDR.
- **`ensureUsers` creates roles and ownership but cannot set passwords.** The
  first password is always an out-of-band `ALTER ROLE`.
- **Never invent a SCRAM verifier.** PgBouncer's userlist is copied out of the
  running PostgreSQL after the password is set; a handwritten one cannot
  validate anything.
- **`writeShellApplication` runs shellcheck as a fatal build gate.** A lint
  finding is a build failure, not a warning — fix the shell, do not disable it
  without cause.
- Measure the effect, not the abstraction. A port that answers over a unit
  that is `active`; a `plan` diff over "the variable looks right"; a client
  that authenticates over a rebuild that exited 0.
- One variable per apply. A change that moved an AMI, an instance type and a
  security group and then failed produces no information.

## Verify commands

```sh
nix flake check --no-build                    # every host must still evaluate
nix eval .#nixosConfigurations.<host>.config.<option>
nix run .#local                               # boot the service modules in a VM
nix run .#secret                              # fzf picker -> clipboard

tofu -chdir=tofu/<root> validate
tofu -chdir=tofu/<root> fmt -check
tofu -chdir=tofu/<root> plan                  # read every replacement line

getent hosts <fqdn>                           # resolution only
timeout 5 ssh -o BatchMode=yes root@<fqdn> true   # timed out != refused
curl -s https://checkip.amazonaws.com         # your source address, when locked out

ssh root@<fqdn> systemctl show -p ActiveEnterTimestamp <unit>
ssh root@<fqdn> ls -l /run/agenix/            # empty = recipient or rekey problem
```

## Completion criteria

State which rung was reached and the evidence for it. For a secret change,
report the value's new state, the unit restart, and the authentication that
proved it — not the rebuild's exit code. For an ingress change, report the
source that was tested and from where.

Do not report an infrastructure change as finished while the only proof is a
`plan` that was never applied, a rebuild whose unit was never restarted, or a
port that was never dialled from outside the machine.
