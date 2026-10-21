#!/system/bin/sh
set -u

output_dir=${1:-}

if [ -z "$output_dir" ] || [ "${output_dir#/}" = "$output_dir" ]; then
  printf 'usage: %s /absolute/output/directory\n' "$0" >&2
  exit 2
fi

case "$output_dir" in
  /|/cache|/data|/metadata|/system|/vendor)
    printf 'refusing broad output directory: %s\n' "$output_dir" >&2
    exit 2
    ;;
esac

if ! mkdir -p "$output_dir"; then
  printf 'cannot create output directory: %s\n' "$output_dir" >&2
  exit 1
fi

capture() {
  name=$1
  shift
  if command -v "$1" >/dev/null 2>&1; then
    "$@" >"$output_dir/$name" 2>&1
  else
    printf 'unavailable: %s\n' "$1" >"$output_dir/$name"
  fi
}

copy_if_present() {
  source_path=$1
  destination_name=$2
  case "$output_dir/" in
    "$source_path"/*)
      printf 'skipped recursive source: %s\n' "$source_path" >"$output_dir/${destination_name}.copy-error"
      return
      ;;
  esac
  if [ -e "$source_path" ]; then
    cp -R "$source_path" "$output_dir/$destination_name" 2>"$output_dir/${destination_name}.copy-error" || true
  fi
}

capture_values() {
  destination=$1
  shift
  : >"$output_dir/$destination"
  for value_path in "$@"; do
    if [ -f "$value_path" ]; then
      printf '%s=' "$value_path" >>"$output_dir/$destination"
      cat "$value_path" >>"$output_dir/$destination" 2>/dev/null || printf '<unreadable>\n' >>"$output_dir/$destination"
    fi
  done
}

{
  printf 'collector_version=1\n'
  printf 'output_dir=%s\n' "$output_dir"
  date -u '+captured_utc=%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || true
  printf 'uptime_seconds='
  cut -d' ' -f1 /proc/uptime 2>/dev/null || printf 'unknown\n'
} >"$output_dir/meta.txt"

capture uname.txt uname -a
capture properties.txt getprop
capture dmesg.txt dmesg
capture logcat.txt logcat -b all -d -v threadtime
capture mounts.txt mount
capture processes.txt ps -A -Z
capture input-devices.txt getevent -lp
capture dev-input.txt ls -la /dev/input
capture dev-block.txt ls -laR /dev/block
capture sys-class-udc.txt ls -laR /sys/class/udc
capture configfs-gadgets.txt ls -laR /config/usb_gadget
capture kernel-configfs-gadgets.txt ls -laR /sys/kernel/config/usb_gadget
capture usb-legacy.txt ls -laR /sys/class/android_usb/android0
capture usb-ffs.txt ls -laR /dev/usb-ffs
capture_values udc-values.txt \
  /sys/class/udc/*/state \
  /sys/class/udc/*/function \
  /sys/class/udc/*/current_speed \
  /sys/class/udc/*/maximum_speed \
  /sys/class/udc/*/device/uevent
capture_values configfs-values.txt \
  /config/usb_gadget/*/UDC \
  /config/usb_gadget/*/idVendor \
  /config/usb_gadget/*/idProduct \
  /config/usb_gadget/*/strings/*/serialnumber \
  /config/usb_gadget/*/configs/*/strings/*/configuration \
  /sys/kernel/config/usb_gadget/*/UDC \
  /sys/kernel/config/usb_gadget/*/idVendor \
  /sys/kernel/config/usb_gadget/*/idProduct
capture selinux-enforce.txt cat /sys/fs/selinux/enforce
capture proc-cmdline.txt cat /proc/cmdline
capture proc-bootconfig.txt cat /proc/bootconfig
capture proc-mounts.txt cat /proc/mounts
capture proc-partitions.txt cat /proc/partitions
capture proc-bus-input-devices.txt cat /proc/bus/input/devices
capture proc-filesystems.txt cat /proc/filesystems

copy_if_present /sys/fs/pstore pstore
copy_if_present /tmp/recovery.log recovery.log
copy_if_present /tmp/recovery.log.old recovery.log.old
copy_if_present /cache/recovery cache-recovery
copy_if_present /data/misc/recovery data-misc-recovery

printf 'complete\n' >"$output_dir/CAPTURE_COMPLETE"
