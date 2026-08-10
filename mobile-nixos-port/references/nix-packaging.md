# Packaging a port in Nix

## Contents

- Consuming Mobile NixOS from a flake
- Evaluate the device twice
- Patching the Mobile NixOS tree
- The kernel derivation
- Selecting a kernel lineage
- What the structured config layer overrides
- Boot image geometry
- Patch discipline

## Consuming Mobile NixOS from a flake

Mobile NixOS ships **no flake**. It pins Nixpkgs with `npins` and exposes
`pkgs.nix` as the entry point. Take it as a non-flake source input and use the
Nixpkgs it pins — that is the one every device was validated against, and
introducing a second Nixpkgs guarantees drift.

```nix
inputs.mobile-nixos = {
  url = "github:mobile-nixos/mobile-nixos/<rev>";
  flake = false;
};

pkgsFor = system: import "${mobile-nixos}/pkgs.nix" { inherit system; };
```

`lib/eval-with-configuration.nix` takes
`{ system ? null, pkgs ? null, device ? null, configuration, additionalConfiguration ? {}, additionalHelpInstructions ? null }`.

- `system` **must be passed explicitly**. Its default is
  `builtins.currentSystem`, which pure flake evaluation forbids.
- Passing both `system` and `pkgs` throws.
- `device` may be a path: it is accepted when
  `builtins.isPath device && builtins.pathExists device`, so a device directory
  in your own repo works without registering anything upstream.

npins calls `builtins.getEnv` for its `NPINS_OVERRIDE_*` escape hatch. In pure
eval that returns `""`, which is harmless.

Android outputs live under `eval.outputs.android`: `android-bootimg`,
`android-recovery`, `android-fastboot-images`. The kernel derivation is
`eval.config.mobile.boot.stage-1.kernel.package`.

## Evaluate the device twice

Bring-up on an old kernel means editing systemd, and every systemd patch
invalidates the whole closure below it. If the device declares a graphical
session, that closure includes xorg-server, mesa, gstreamer, ffmpeg, pango,
cairo and the font trees — none of which is on the path being debugged, all of
which has to be cross-compiled, and most of which is not in the binary cache
once systemd is patched.

The eval function takes a `configuration` argument, so a second arm costs three
lines and shares everything else — same kernel, same initrd, same patch set:

```nix
outputsFor = system: device:
  let
    eval     = evalFor system device { };
    headless = evalFor system device { mobile.session.<session>.enable = false; };
  in {
    "${device}-fastboot-images"          = eval.outputs.android.android-fastboot-images;
    "${device}-system"                   = eval.config.system.build.toplevel;
    "${device}-headless-fastboot-images" = headless.outputs.android.android-fastboot-images;
    "${device}-headless-system"          = headless.config.system.build.toplevel;
  };
```

Spell the session's `enable` in the device file as `lib.mkDefault true`, or the
override collides with it.

Measured on one MT6762G port:

| | full | headless |
|---|---|---|
| toplevel closure | 2.6 GiB, 980 paths | 1.0 GiB, 647 paths |
| `system.img` | 4.08 GiB | 2.22 GiB |

The headless closure was a strict subset — nothing appeared that the full arm
did not already have — and `boot.img` was byte-identical, so switching arms is a
rootfs write with no reflash. **Check that second point before relying on it**;
it holds only while the session changes nothing in stage-1.

Verify the arm still contains what makes the device reachable (sshd, the gadget
network unit, mDNS, the VPN) by listing `etc/systemd/system` in the built
toplevel. A headless arm that also drops your only transport is a reflash.

## Patching the Mobile NixOS tree

Some geometry is not expressible through options — Android boot header v2, for
one. Patch the input rather than overlay around it:

```nix
mobileNixosFor = system: (pkgsFor system).applyPatches {
  name = "mobile-nixos-patched";
  src = mobile-nixos;
  patches = [ ./patches/mobile-nixos/0001-android-bootimg-header-v2.patch ];
};
```

A patch fails loudly when upstream moves. An overlay that reimplements the same
thing silently no-ops instead, which is the worse failure.

## The kernel derivation

`mobile-nixos.kernel-builder` is a **two-level function**: injected dependencies
first, user arguments second. The user argument set ends in `...`, so passing an
injected dependency (`stdenv`, `overrideCC`, …) in the second set is silently
accepted and ignored. Toolchain changes must go through `.override`:

```nix
(mobile-nixos.kernel-builder.override {
  stdenv = overrideCC stdenv buildPackages.gcc13;
}) {
  version = "4.9.190";
  configfile = ./config.aarch64;
  src = fetchFromGitHub { /* pinned rev + hash */ };
  patches = [ ../../../patches/linux/<soc>/0006-....patch ];
  enableRemovingWerror = true;
  isCompressed = "gz";
  isModular = true;
  enableLinuxLogoReplacement = false;
  enableCenteredLinuxLogo = false;
  nativeBuildInputs = [ python3 ];
  makeFlags = [ "KCFLAGS=-fcommon" ];
}
```

Argument notes:

- **`...` in the device kernel's own argument set is load-bearing.** NixOS'
  `boot.kernelPackages` apply function
  (`nixos/modules/system/boot/kernel.nix`) calls
  `super.kernel.override (originalArgs: { randstructSeed; kernelPatches; features; })`,
  so anything evaluating `system.build.toplevel` passes three undeclared
  arguments. The consequence: `boot.kernelPatches` and `boot.kernel.features`
  are **inert** for such a device. Patches go in the builder's `patches` list.
- **Toolchain.** Nixpkgs' current GCC rejects implicit function declarations,
  which a 2019 vendor tree cannot survive. GCC 13 is the newest Nixpkgs release
  that only warns. `buildPackages.gccN` is the cross compiler that runs on the
  build host. This is a real deviation from the vendor's clang and is not proven
  harmless: a successful compile is not ABI compatibility.
- **`enableRemovingWerror`.** A blanket `-Wno-error` does *not* cancel the
  specific `-Werror=<name>` form GCC emits, so the flags have to be stripped out
  of the makefiles.
- **`makeFlags = [ "KCFLAGS=-fcommon" ]`.** gcc10+ defaults to `-fno-common`;
  pre-2020 trees rely on tentative definitions being merged.
- **`modDirVersion`.** The builder compares the declared version against
  `include/config/kernel.release` *after* the whole kernel has compiled.
  Mainline `x.y` tarballs drop `SUBLEVEL` from the filename but not from the
  Makefile, so `version = "6.18"` produces `6.18.0` and fails that check at the
  end of a full build. Declare `modDirVersion` whenever the tarball name and the
  release string can disagree; it is also the `/lib/modules/<x>` directory name.
- **`nativeBuildInputs = [ python3 ]`.** MediaTek trees run
  `tools/dct/DrvGen.py` from `scripts/drvgen/drvgen.mk` to *generate* a `.dtsi`,
  so python is a device-tree dependency, not a helper. The builder's
  `patchShebangs` silently leaves a shebang alone when the interpreter is not on
  PATH, so omitting it fails late and confusingly.

## Selecting a kernel lineage

Keeping a vendor tree and a mainline tree buildable side by side is worth the
cost — one of them is what boots, the other is the upgrade path — but the
selector cannot live wherever it reads best.

Mobile NixOS runs a config validator that aborts evaluation when a
`structuredConfig` assertion names a symbol the source tree does not define, and
`MACH_<soc>` and `ARCH_<vendor>` belong to mutually exclusive Kconfig worlds. So
the module that *contributes* those assertions is the one that has to know which
lineage it is talking about.

**Declare the selector at the layer that asserts the Kconfig.** When a SoC
module contributes `mobile.kernel.structuredConfig`, that layer is the SoC
module, not the device:

```nix
options.mobile.hardware.socs.<soc> = {
  enable = mkOption { /* ... */ };
  kernelTree = mkOption {
    type = types.enum [ "vendor" "mainline" ];
    default = "vendor";
  };
};

config = mkIf cfg.<soc>.enable {
  mobile.kernel.structuredConfig = [
    (helpers: with helpers;
      if cfg.<soc>.kernelTree == "mainline"
      then { ARCH_<vendor> = yes; }
      else { ARCH_<vendor> = no; MACH_<soc> = yes; /* vendor-only symbols */ })
  ];
};
```

A device-level option cannot gate them. The SoC module is evaluated for every
device that enables the SoC and has no business reading a device attribute, so
the assertions would fire before any device value could suppress them. The same
argument covers quirks: a framebuffer refresher that exists only for a vendor
fbdev driver is gated on this selector, not on the device.

Expose the alternate lineage as its own flake output rather than a flag the
default build can trip over:

```nix
mainline = evalFor system device {
  mobile.hardware.socs.<soc>.kernelTree = "mainline";
};
```

This is the general form of the split rule in the skill: kernel-version quirks
follow the kernel version, SoC quirks follow the SoC. An option exists at the
layer whose assertions it controls.

## What the structured config layer overrides

`mobile-nixos/modules/kernel-config.nix` layers structured config over your
defconfig and both adds and overrides symbols. Ones that reliably matter:

| Symbol | Effect |
|---|---|
| `RD_GZIP`, `RD_XZ` | initramfs decompressors; without them the ramdisk never unpacks |
| `FRAMEBUFFER_CONSOLE` | what `console=tty1` actually binds to |
| `CONFIG_LOCALVERSION=""`, `LOCALVERSION_AUTO=n` | release string becomes plain `X.Y.Z`, overriding the defconfig's `-<codename>` suffix |

Normalize the vendor defconfig with an out-of-tree `make olddefconfig` against
the pinned source and check in the normalized file, so the repo matches what is
actually built. It still is not the config the kernel runs with.

## Boot image geometry

Derive geometry from the packager that already worked for the device (Droidian's
`kernel-info.mk`, pmaports' `deviceinfo`), then **check every field against the
unpacked stock image**. Fields that commonly differ from the lead: header
version, `offset_second`, and the dtb section format.

MediaTek DTBO/dtb sections are usually built with
`mkdtboimg create` over the kernel's `dtbs/<vendor>/<soc>.dtb`.

Compare candidate against stock by section size, not by whole-file hash:
`file_size`, `kernel_size`, `ramdisk_size`, `dtb_size`, page size, and the full
cmdline. A one-byte kernel delta is gzip nondeterminism; a ramdisk delta must be
explainable by a specific source change (a stage-1 task lives in the initrd, so
editing its comments changes the image).

## Patch discipline

Group patches by the tree they apply to, not by the device:

```
patches/mobile-nixos/     applied to the Mobile NixOS source tree
patches/systemd/          applied to nixpkgs' systemd via an overlay
patches/linux/<soc>/      applied to a vendor kernel tree
```

Numbering is global; the directory says which tree. Nix stores patch files by
content hash plus basename, so moving a patch between directories without
changing its name or content leaves the derivation unchanged — expect a cache
hit, and treat a rebuild as a signal that something else moved.

Record removed patches in the derivation next to the applied ones when the
removal itself was the finding. A patch deleted without a note gets
reintroduced.
