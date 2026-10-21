# The cross-compiled installer image

## Why not the generic aarch64 ISO

The upstream NixOS aarch64 image carries a mainline kernel with no Tegra
support. The Jetson needs the L4T kernel and the jetpack module set, so the
installer has to be built from your own `nixosConfiguration`:

```nix
nixosConfigurations.installer = nixpkgs.lib.nixosSystem {
  modules = [ jetpack.nixosModules.default ./installer/iso.nix ];
};
```

## Cross-compiling from x86_64

Set both platforms and the build runs natively on the host toolchain, with no
qemu anywhere:

```nix
nixpkgs.buildPlatform.system = "x86_64-linux";
nixpkgs.hostPlatform.system  = "aarch64-linux";
```

The difference against emulation is roughly an order of magnitude. It also
means the ISO can be built on the machine that will write the card, which
removes a transfer step from the loop.

`hardware.enableAllHardware` pulls in firmware and modules that do not
cross-compile cleanly; force it off in the image:

```nix
hardware.enableAllHardware = lib.mkForce false;
```

Expose the artifacts under `x86_64-linux`, since the flashing tooling ships
x86_64-only binaries:

```nix
packages.x86_64-linux = rec {
  default        = installer-iso;
  installer-iso  = self.nixosConfigurations.installer.config.system.build.isoImage;
  flash-firmware = self.nixosConfigurations.installer.config.system.build.flashScript;
};
```

Taking `flashScript` from the *installer* configuration rather than a generic
jetpack output means it writes the firmware version that image expects to find.

### Cross does not mean the target never builds

The installed system rebuilds the vendor kernel and the L4T out-of-tree modules
natively, because the cross and native derivations hash differently and the
cache holds neither. One to two hours on an Orin Nano. This is expected, not a
misconfiguration, and it is the single largest cost in the whole procedure.

## Put the install in the image

Ship the procedure rather than documenting it. A small derivation on the ISO
beats a README nobody has open while staring at a console:

```sh
git clone <repo> "$DOTS_DIR"
nix run .#disko -- --mode disko ./disko-config.nix
nixos-install --flake .#<host> || nixos-install --max-jobs 1 --flake .#<host>
```

The `--max-jobs 1` retry is the memory fallback; see
[storage-media.md](storage-media.md).

**The script clones from the remote.** Unpushed commits mean the installer
fetches a stale tree — most painfully, one missing the nixpkgs fixes below,
which fails the firmware build on a board with no console. Either push before
installing, or copy the working tree over and install from that path.

### The script is baked in; the flake is not

Packaging the procedure means it lands in the image's `/nix/store` through
`environment.systemPackages`. So the two halves have different ages, and it is
easy to get backwards:

| Artifact | Source at install time |
|---|---|
| the install command in `$PATH` | the image's store — frozen at the build commit |
| `configuration.nix`, `disko-config.nix`, `modules/` | the `git clone` — current |

Pushing a fix to the script does not reach a card that was already written.
Rebuilding and rewriting the image for a one-line shell fix is the wrong answer;
run the freshly cloned copy instead:

```sh
sudo setsid nohup bash "$DOTS_DIR/installer/infection.sh" > install.log 2>&1 </dev/null &
```

Confirm which body is live before assuming. A script invoked as
`bash -c "$(declare -f infect); infect"` prints its whole text in the process
list:

```sh
pgrep -af "[i]nfect"
```

The character class is not decoration — a bare `pkill -f disko` over SSH matches
the pattern inside your own remote shell's command line and kills the session.

## EDK2 firmware and nixpkgs-unstable

The JetPack UEFI firmware build runs a Python toolchain (`edk2-pytool-*`,
`uefi-firmware-parser` and their dependency closure). On unstable these break
regularly, and the failure surfaces as the *firmware* not building, which reads
as a jetpack-nixos problem and is not one.

Keep every workaround in one module, each with the condition under which it can
be deleted. Classes seen in practice:

| Class | Shape of the fix |
|---|---|
| Over-tight dependency bound | `pythonRelaxDeps = ["<dep>"];` |
| Test deps dragging in a heavy closure (scipy via joblib) | `doCheck = false;` |
| Upstream dropped `pkg_resources` (setuptools ≥ 81) | `postPatch` porting to `importlib.metadata` |
| Metadata check failing on a pinned version | `dontCheckPythonMetadata = true;` |

### Overriding a package set without moving the interpreter

`python312.override` changes the interpreter's own store path, which rebuilds
everything downstream of Python — on a cross-compiled image that is most of the
closure. Rebuild only the package set and keep the interpreter fixed:

```nix
prev.python312 // {
  pkgs = pkgs';
  withPackages = f: prev.python312.withPackages (_: f pkgs');
}
```

The interpreter path is untouched; only consumers that go through `pkgs` or
`withPackages` see the patched set.

Match by `pname` when the same package appears under several attribute names in
`python3Packages`, or the override silently misses.

## Writing and verifying the medium

Never trust `dd` exiting zero. Read the block device back and drop the caches
first — see [storage-media.md](storage-media.md) for the full procedure and for
why a passing readback still does not prove the card is sound.

## Checks worth running before writing a card

```sh
nix build .#packages.x86_64-linux.installer-iso
nix eval .#nixosConfigurations.installer.config.services.openssh.enable   # true
nix eval .#nixosConfigurations.<host>.config.services.openssh.enable      # also true
```

The second line is the one people skip. An installer with sshd and a target
without it is the lockout described in
[console-and-access.md](console-and-access.md), and this eval catches it before
any hardware is involved.
