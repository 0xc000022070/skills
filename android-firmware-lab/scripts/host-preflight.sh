#!/usr/bin/env bash
set -u

tools=(adb fastboot python3 file sha256sum)
optional=(unpack_bootimg mkbootimg magiskboot avbtool lpdump lpunpack simg2img payload-dumper-go mkdtimg dtc fdtdump fsck.erofs debugfs lz4 lsusb udevadm timeout)

printf 'required tools\n'
missing=0
for tool in "${tools[@]}"; do
  if path=$(command -v "$tool" 2>/dev/null); then
    printf 'ok      %-20s %s\n' "$tool" "$path"
  else
    printf 'missing %-20s\n' "$tool"
    missing=1
  fi
done

printf '\noptional tools\n'
for tool in "${optional[@]}"; do
  if path=$(command -v "$tool" 2>/dev/null); then
    printf 'ok      %-20s %s\n' "$tool" "$path"
  else
    printf 'absent  %-20s\n' "$tool"
  fi
done

printf '\nversions\n'
adb --version 2>/dev/null | head -n 2 || true
fastboot --version 2>/dev/null | head -n 1 || true
python3 --version 2>/dev/null || true

exit "$missing"
