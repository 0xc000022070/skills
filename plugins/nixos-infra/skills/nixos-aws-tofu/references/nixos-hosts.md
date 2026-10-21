# Hosts, deploys and services

```
flake.nix        nixosConfigurations per machine, packages, check-VM app
hosts/<name>.nix imports + what is unique to that machine
modules/*.nix    one concern each, architecture-agnostic
pkgs/*.nix       operator tooling, callPackage'd from the flake
```

A host file should be imports, a hostname, and the handful of options that are
genuinely unique. Anything reusable belongs in `modules/`. Adding a machine is
a new `hosts/<name>.nix` plus one line in `nixosConfigurations` — if it needs
more than that, the shared module is wrong.

Every host is EC2 Graviton (`aarch64-linux`) and starts from
`"${modulesPath}/virtualisation/amazon-image.nix"`, which supplies the boot
loader, root filesystem, growpart and metadata handling. Do not hand-write a
hardware configuration.

## Flakes see only tracked files

A newly written `pkgs/thing.nix` fails with "path ... is not tracked by Git"
until it is added. **Staging is sufficient — a commit is not:**

```sh
git add pkgs/thing.nix && nix build .#thing
```

The rule inverts on the target host. The tree shipped there has no `.git`, so
its flake sees every file including uncommitted edits. Two opposite
behaviours; know which side you are debugging before concluding a build is
stale.

## Deploying to aarch64 from an x86_64 workstation

The obvious route often does not work:

```sh
nixos-rebuild switch --flake .#<host> --target-host root@<fqdn>   # may be fine
nixos-rebuild switch --flake .#<host> --build-host root@<fqdn>    # trap
```

`--build-host` is unusable when the driver itself is fetched ad-hoc:
`nix run nixpkgs#nixos-rebuild` resolves to the **aarch64** build, so the
driver runs under binfmt emulation and evaluation never finishes. It does not
error — it hangs, which reads like a slow build.

Two routes that do work:

- **Build on the machine.** Ship the tree and rebuild locally there. Robust,
  and the binary cache serves the heavy packages anyway:

  ```sh
  tar czf - --exclude=.git --exclude=.terraform . \
    | ssh root@<fqdn> 'mkdir -p /root/infra && tar xzf - -C /root/infra'
  ssh root@<fqdn> 'NIX_CONFIG="experimental-features = nix-command flakes" \
      nixos-rebuild switch --flake /root/infra#<host>'
  ```

- **Emulate locally**: `boot.binfmt.emulatedSystems = [ "aarch64-linux" ]` on
  the workstation. Slower per build, but keeps the deploy one command.

Never build an application on a small instance. Build it in CI or locally for
`aarch64-linux` and let the host pull the result.

### Small instances cannot evaluate a large closure

A 2 GB machine OOMs during evaluation. Declare swap in the host file — but
note the ordering problem: on a **fresh** instance the swapfile does not exist
until the first successful rebuild, which is the rebuild that needs it. Create
it by hand once:

```sh
fallocate -l 4G /var/swapfile.bootstrap
chmod 600 /var/swapfile.bootstrap
mkswap /var/swapfile.bootstrap && swapon /var/swapfile.bootstrap
```

## Service conventions

- PostgreSQL, PgBouncer and Redis bind to localhost. Caddy is the only public
  ingress. A host that binds a database publicly is an explicit, documented
  exception — check `AGENTS.md` before assuming a new one is allowed.
- **`ensureUsers` creates roles and database ownership but cannot set
  passwords.** Every deployment needs one out-of-band `ALTER ROLE` per role.
  Pipe the value from agenix; never type it.
- **PgBouncer's userlist holds a SCRAM verifier copied out of the running
  server** — read it after the `ALTER ROLE`, never invent it:

  ```sh
  sudo -u postgres psql -Atc \
    "SELECT concat('\"<role>\" \"', rolpassword, '\"') FROM pg_authid WHERE rolname='<role>'"
  ```

  The verifier is `SCRAM-SHA-256$<iters>:<salt>$<StoredKey>:<ServerKey>`. It
  lets PgBouncer *verify* a client but cannot be used to *log in* — deriving
  ClientProof needs ClientKey, and `StoredKey = H(ClientKey)` is one-way. It
  is still an offline brute-force target, so treat it as a secret.
- **Role count follows topology, not habit.** The prod `app_user`/`app_admin`
  split exists to separate PgBouncer's connection path from the admin one. A
  host with no PgBouncer needs one role.
- A beta PostgreSQL pulled from `nixpkgs-unstable` has no on-disk format
  guarantee against the eventual release. Expect a dump/restore and say so in
  the docs rather than discovering it at upgrade time.
- Prisma: `DATABASE_URL` through PgBouncer, `DIRECT_URL` straight to
  PostgreSQL. Migrations never go through the pooler.

## Operator packages

`pkgs/*.nix` built with `writeShellApplication` run **shellcheck at build
time, fatally**. `ls -1 ./*.age` fails SC2012 and the derivation does not
build. Write shell that lints clean — a bash array glob instead of parsing
`ls`, quoted expansions throughout. Inside a Nix string, escape shell
interpolation as `''${VAR}`.

## Verification before handing off

```sh
nix flake check --no-build                      # every host, including ones not yet deployed
nix eval .#nixosConfigurations.<host>.config.<option>
nix run .#local                                 # boot service modules in a VM
tofu -chdir=tofu/<root> validate && tofu -chdir=tofu/<root> fmt -check
```

`nix flake check` catching a host you did not touch is the point — a shared
module edit that breaks an undeployed machine is still a break. When commits
are meant to stand alone, verify each one in a throwaway worktree rather than
trusting that the series evaluates at its tip.
