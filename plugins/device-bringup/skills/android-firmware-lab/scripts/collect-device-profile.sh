#!/usr/bin/env bash
set -u

serial_args=()
if [[ $# -eq 2 && $1 == "-s" ]]; then
  serial_args=(-s "$2")
elif [[ $# -ne 0 ]]; then
  printf 'usage: %s [-s SERIAL]\n' "$0" >&2
  exit 2
fi

adb_cmd=(adb "${serial_args[@]}")

if ! "${adb_cmd[@]}" get-state >/dev/null 2>&1; then
  printf 'target is not available through authorized adb\n' >&2
  exit 1
fi

shell() {
  "${adb_cmd[@]}" shell "$@" 2>/dev/null | tr -d '\r'
}

prop() {
  local key=$1
  local value
  value=$(shell getprop "$key")
  printf '%-38s %s\n' "$key" "${value:-<unset>}"
}

printf 'android firmware device profile\n'
printf 'collected_utc                          %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'adb_serial                             %s\n' "$("${adb_cmd[@]}" get-serialno 2>/dev/null)"

printf '\n[identity]\n'
for key in \
  ro.product.manufacturer ro.product.model ro.product.name ro.product.device \
  ro.product.board ro.boot.product.hardware.sku ro.boot.hardware ro.hardware \
  ro.soc.manufacturer ro.soc.model ro.product.cpu.abi ro.product.cpu.abilist; do
  prop "$key"
done

printf '\n[software]\n'
for key in \
  ro.build.fingerprint ro.build.id ro.build.version.incremental \
  ro.build.version.release ro.build.version.sdk ro.build.version.security_patch \
  ro.vendor.build.fingerprint ro.vendor.build.security_patch; do
  prop "$key"
done

printf '\n[boot]\n'
for key in \
  ro.bootloader gsm.version.baseband ro.boot.slot_suffix ro.boot.slot \
  ro.boot.dynamic_partitions ro.boot.super_partition ro.boot.boot_devices \
  ro.boot.bootreason sys.boot.reason ro.boot.verifiedbootstate \
  ro.boot.vbmeta.device_state ro.boot.avb_version ro.boot.flash.locked \
  ro.boot.veritymode ro.boot.selinux; do
  prop "$key"
done

printf '%-38s %s\n' kernel_release "$(shell uname -r)"
printf '%-38s %s\n' kernel_machine "$(shell uname -m)"
printf '%-38s %s\n' page_size "$(shell getconf PAGESIZE)"
printf '%-38s %s\n' selinux "$(shell getenforce)"

printf '\n[kernel_cmdline]\n'
shell sh -c 'cat /proc/cmdline 2>/dev/null || true'
printf '\n[bootconfig]\n'
shell sh -c 'cat /proc/bootconfig 2>/dev/null || true'
printf '\n[partitions_by_name]\n'
shell sh -c 'ls -l /dev/block/by-name 2>/dev/null || ls -l /dev/block/platform/*/by-name 2>/dev/null || true'
printf '\n[mounts]\n'
shell sh -c 'mount 2>/dev/null | grep -E " /(system|system_ext|vendor|product|odm|data)( |/)" || true'
printf '\n[root_indicators]\n'
shell sh -c "for p in /data/adb/magisk /data/adb/ksu /data/adb/ap; do [ -e \"\$p\" ] && echo \"\$p\"; done; command -v su 2>/dev/null || true"
