# Custom recovery bring-up

## Contents

- Scope and evidence contract
- Select and pin the source generation
- Establish the stock contract
- Audit tree and artifact provenance
- Build without contaminating evidence
- Diagnose by subsystem
- Preserve diagnostics without ADB
- Handle legacy MediaTek devices
- Promote a candidate

## Scope and evidence contract

Treat recovery bring-up as integration work across boot image packaging, kernel and DT, init, input, display, USB gadget, storage, encryption, and verified boot. A recovery that draws a UI has proved only that the bootloader loaded the image, the kernel reached userspace, and graphics initialized.

Keep device observations separate from reusable conclusions:

- Observation: exact candidate hash, screen state, enumeration state, timestamps, and retained logs.
- Device hypothesis: a claim about this kernel, panel, touch controller, UDC, partition, or firmware build.
- Reusable rule: a mechanism corroborated by upstream source or multiple independent devices.

Do not turn one model's property, UDC name, fstab, codename alias, or `TW_*` workaround into a default.

## Select and pin the source generation

Choose the TWRP branch from the device launch generation and upstream support matrix, not the currently installed ROM alone. As of the bundled source review, TeamWin routes devices released with Android 10 or 11 to the Android 11 branch and devices released with Android 12.1 or later to the Android 12.1 branch. Refresh this mapping before a new port.

Pin the complete source forest:

```sh
repo manifest -r -o manifest-lock.xml
repo status
```

A commit in the manifest repository does not pin every project when its XML still names moving branches. Preserve:

- revision-locked manifest;
- local manifests;
- device-tree remote and commit;
- dirty patch or clean status;
- build-system and recovery commits;
- kernel, DTB, DTBO, fstab, module, and proprietary-blob provenance.

Reject a tree whose build history cannot explain where each boot-critical blob came from.

## Establish the stock contract

Acquire the exact stock recovery or boot artifacts for the target fingerprint and region. Record the full package hash before extraction. For every relevant image, record:

- image and partition size;
- boot header version, page size, base, offsets, command line, OS version, and SPL;
- kernel, ramdisk, second stage, DTB, and recovery DTBO hashes;
- ramdisk compression and file manifest;
- AVB footer original image size, descriptor partition name, algorithm, key fingerprint, flags, and rollback fields;
- stock init imports, fstab paths, ueventd rules, USB controller source, and input node permissions.

Derive packaging arguments from the exact stock image. Do not combine base-relative and absolute load addresses. Compare the repacked header fields and component hashes before replacing userspace.

For boot header versions 1 and 2, recovery DTBO can be embedded in the recovery image. Header version 2 also carries DTB size and physical address. Preserve these fields exactly unless evidence requires a change.

Use `avbtool --calc_max_image_size` when adding an AVB footer. The unpadded payload must fit before footer and metadata are appended. A final image equal to the partition size is normal for an AVB-footer image; it does not prove that the unsigned payload fit correctly.

## Audit tree and artifact provenance

Run before building:

```sh
python3 scripts/audit-recovery-tree.py device/vendor/codename \
  --expected codename \
  --expected model-number \
  --launch-android 10 \
  --pretty
```

Add `--forbid` for known sibling or donor identifiers. Treat matches in identity-bearing assignments, fingerprints, assertions, fstab paths, init imports, and update metadata as failures. Do not rely on a fixed global list of foreign codenames.

Require an allowlist of expected device, board, model, SoC, and hardware aliases. A donor tree can be useful evidence, but copied values remain untrusted until matched against stock artifacts or target runtime data.

Keep a provenance table:

| Artifact | Source package/repository | Revision/member | SHA-256 | Target evidence |
|---|---|---|---|---|
| Kernel | exact stock package or source build | package member or commit | hash | stock component match |
| DTB/DTBO | exact stock package or source | member or commit | hash | board/panel match |
| Fstab/init | stock ramdisk or authored patch | source path and diff | hash | target partition/runtime data |
| Proprietary blob | exact target firmware | partition and path | hash | ABI/dependency evidence |

## Build without contaminating evidence

Keep the source checkout immutable during a build. Do not use build scripts that patch global source files with `sed -i`, copy a stock `init.rc` over upstream recovery init, or disable error handling around environment setup. Represent required changes as pinned commits or explicit patches that apply cleanly.

`ALLOW_MISSING_DEPENDENCIES=true` is a bring-up escape hatch, not compatibility evidence. Archive the missing-dependency output and remove the flag before calling the tree complete.

A Nix flake pins the package environment only when `flake.lock` is committed. It does not pin the Android `repo` forest, device blobs, host kernel, mutable ccache, or source-tree edits. For a reproducibility claim, preserve both `flake.lock` and `manifest-lock.xml`, disable or isolate mutable caches, build from two clean workspaces, and compare outputs or explain every nondeterministic byte.

Use the JDK and Python generation required by the selected manifest. An FHS environment improves compatibility with prebuilt Android tools but is not a hermetic build by itself.

## Diagnose by subsystem

### Boot and init

Start from upstream recovery init for the selected branch. Add the smallest device-specific import needed. Replacing core init can silently remove required services, triggers, pstore mounts, binder setup, FunctionFS setup, or recovery hooks.

Compare imports, service definitions, classes, triggers, property conditions, users/groups, SELinux labels, mounts, and device-node creation. Confirm that `${ro.hardware}` resolves to the filename actually packaged.

### Touch and keys

Prove the path in this order:

1. The touch driver probes in `dmesg`.
2. The expected `/dev/input/event*` node exists.
3. Node owner, group, mode, and SELinux label allow recovery to read it.
4. `/proc/bus/input/devices` and `getevent -lp` identify the correct device and coordinate ranges.
5. A bounded `getevent -lt /dev/input/eventN` capture shows touch-down, position, synchronization, and release events.
6. TWRP event logging shows the same device and event sequence.
7. Only then select input blacklist/whitelist, axis flip, rotation, or ignore flags.

Linux multitouch protocol B uses `ABS_MT_SLOT` and `ABS_MT_TRACKING_ID`; `-1` releases a contact. Position events alone do not prove that userspace receives a complete gesture. `TWRP_EVENT_LOGGING` exposes TWRP's event interpretation. Flags such as `TW_IGNORE_MAJOR_AXIS_0`, `TW_IGNORE_MT_POSITION_0`, and `TW_IGNORE_ABS_MT_TRACKING_ID` change release semantics and require raw-event evidence.

A stock DTBO can contain overlays for several panel or touch-controller variants. String matches reveal candidates, not the overlay selected for this boot. Use DTBO entry metadata, bootloader selection data, kernel probe logs, and the resulting input-device name to identify the active variant.

Dead touch with working keys is an input-path failure. Dead touch plus missing USB is not proof of one shared cause; keep the subsystems separate until kernel or init evidence links them.

### USB and ADB

Test layers in order:

1. Host electrical enumeration with `lsusb` and kernel host logs.
2. Target UDC exists under `/sys/class/udc`.
3. Correct device/peripheral role and controller driver are active.
4. Configfs is mounted and the gadget directory exists.
5. VID, PID, strings, configuration, and `ffs.adb` function exist.
6. FunctionFS is mounted at the path used by `adbd`.
7. `adbd` is running and `sys.usb.ffs.ready=1` appears.
8. The function symlink exists in the active configuration.
9. The exact UDC name is written to the gadget `UDC` attribute.
10. Host sees the expected interface and `adb devices` state.

For legacy sysfs gadget mode, inspect `/sys/class/android_usb/android0` instead of assuming configfs. Determine the mechanism from the stock kernel configuration, stock init, and runtime filesystem. Do not guess controller names such as `musb-hdrc`, `dwc3`, or a platform address.

`TW_EXCLUDE_MTP` removes one function; it does not repair ADB enumeration. Starting `adbd` does not bind a USB gadget. Binding a gadget before FunctionFS endpoints are ready can also fail. Capture each layer.

### Storage and encryption

Validate block-device paths against the target partition map. Distinguish bootloader fastboot from fastbootd and physical from logical partitions. Mount read-only first. Do not copy donor fstab entries for `/metadata`, `/cache`, userdata encryption, or dynamic partitions without target evidence.

## Preserve diagnostics without ADB

A failed recovery cannot export volatile logs after the fact when USB, persistent storage, pstore, external media, and UART are all unavailable. Plan the evidence channel before boot.

Bundle `scripts/collect-recovery-diagnostics.sh` into the candidate and invoke it from a one-shot recovery init service. Pass an explicit output directory on storage already proven safe and writable. Preferred destinations:

1. Dedicated `/cache/recovery/bringup/<candidate-hash>/` when `/cache` exists and mounts correctly.
2. `/data/media/0/...` only after userdata mounts and decryption semantics are understood.
3. `/metadata/...` only when its ownership and boot-critical use are understood.
4. External SD or USB storage when its driver and mount path are independently verified.
5. pstore/ramoops for kernel console and pmsg when reserved memory and kernel configuration support it.
6. UART/serial console for early boot and environments with no writable transport.

The diagnostic script never mounts or formats storage. Create and validate the destination separately. Write a completion marker last, then recover the directory from stock system, stock recovery, another known-good recovery, or offline partition extraction.

For TWRP, a small `/system/bin/postrecoveryboot.sh` wrapper is often less invasive than replacing core init because TWRP calls that hook after processing its fstab. The wrapper should:

1. Check `/proc/mounts` and writability for the chosen persistent destination.
2. Invoke the collector with a directory named for the candidate hash or hypothesis.
3. Fall back to `/tmp` only as live-session evidence; `/tmp` does not survive reboot.
4. Never mount, format, decrypt, or repair a filesystem merely to save diagnostics.

If the selected branch does not provide that hook, add a disabled one-shot init service and trigger it only after the chosen destination is known mounted. Preserve the upstream init imports and services.

Preserve `/sys/fs/pstore` before clearing it. AOSP recovery uses pmsg/ramoops plus `recovery-persist` to move recovery logs into `/data/misc/recovery` on devices without `/cache`; reuse that mechanism when the platform already supports it instead of inventing a parallel store.

## Handle legacy MediaTek devices

Treat `mt6762`, `mt6765`, and marketing SoC names as related evidence, not interchangeable identity. Confirm `ro.hardware`, DT compatibles, kernel config, platform device names, boot device path, UDC, storage controller, and panel/touch nodes on the target.

Legacy MediaTek ports commonly combine:

- a dedicated non-A/B recovery partition;
- boot header version 1 or 2 with stock-specific offsets;
- embedded DTB and recovery DTBO;
- a vendor `musb` USB path or legacy Android USB gadget interface;
- 32-bit recovery userspace on a 64-bit-capable SoC;
- bootloader-specific signing, AVB footer, or full-partition padding.

Confirm each item from stock. Do not infer userspace bitness from CPU capability. Do not create preloader aliases or touch boot-region devices during ordinary recovery bring-up.

## Promote a candidate

Compare stock and candidate before every boot:

```sh
python3 scripts/compare-boot-images.py stock-recovery.img candidate-recovery.img \
  --partition-size 67108864 \
  --expected codename \
  --forbid donor-codename \
  --pretty
```

Require:

- exact intended kernel, DTB, DTBO, header, command line, and offsets;
- explainable ramdisk additions, removals, and changes;
- no foreign identity or donor assertions;
- candidate payload and AVB footer fit;
- retained diagnostic route;
- one hypothesis and one material change from the previous candidate.

Name candidates by hypothesis or source commit, not `v2`, `v3`, or `final`. Store the comparison report, build manifest, hash, observation, and recovered diagnostics together.

During a manual boot, correlate the host and target timelines:

```sh
scripts/observe-recovery-boot.sh \
  --image candidate-recovery.img \
  --output logs/candidate-hash \
  --duration 90 \
  --serial SERIAL \
  --input-device /dev/input/eventN
```

Omit `--input-device` until `getevent -lp` identifies the node. Omit `--serial` for host-only USB observation. The helper does not reboot or flash; start it immediately before the user performs the boot action.
