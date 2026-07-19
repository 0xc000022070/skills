#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf 'usage: %s --image IMAGE --output DIR [--duration SECONDS] [--serial SERIAL] [--input-device /dev/input/eventN]\n' "$0" >&2
}

image=
output_dir=
duration=60
serial=
input_device=

while (($#)); do
  case "$1" in
    --image)
      image=${2:-}
      shift 2
      ;;
    --output)
      output_dir=${2:-}
      shift 2
      ;;
    --duration)
      duration=${2:-}
      shift 2
      ;;
    --serial)
      serial=${2:-}
      shift 2
      ;;
    --input-device)
      input_device=${2:-}
      shift 2
      ;;
    *)
      usage
      exit 2
      ;;
  esac
done

if [[ ! -f $image || -z $output_dir ]]; then
  usage
  exit 2
fi
if [[ ! $duration =~ ^[0-9]+$ ]] || ((duration < 1 || duration > 300)); then
  printf 'duration must be between 1 and 300 seconds\n' >&2
  exit 2
fi
case "$output_dir" in
  /|/tmp|/home|/var)
    printf 'refusing broad output directory: %s\n' "$output_dir" >&2
    exit 2
    ;;
esac
if [[ -n $input_device && -z $serial ]]; then
  printf '%s\n' '--input-device requires --serial' >&2
  exit 2
fi
if [[ -n $input_device ]] && ! command -v timeout >/dev/null 2>&1; then
  printf 'timeout is required for bounded input capture\n' >&2
  exit 2
fi
if [[ -n $input_device && $input_device != /dev/input/event* ]]; then
  printf 'invalid input device: %s\n' "$input_device" >&2
  exit 2
fi

mkdir -p "$output_dir"
sha256sum "$image" >"$output_dir/candidate.sha256"
{
  printf 'observer_version=1\n'
  printf 'candidate=%s\n' "$(realpath "$image")"
  printf 'duration_seconds=%s\n' "$duration"
  printf 'serial=%s\n' "$serial"
  printf 'input_device=%s\n' "$input_device"
  date -u '+started_utc=%Y-%m-%dT%H:%M:%SZ'
} >"$output_dir/observation.txt"

background_pids=()
cleanup() {
  for pid in "${background_pids[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

if command -v udevadm >/dev/null 2>&1 && command -v timeout >/dev/null 2>&1; then
  timeout "$duration" udevadm monitor --kernel --property --subsystem-match=usb >"$output_dir/udev-usb.log" 2>&1 &
  background_pids+=("$!")
fi
if command -v dmesg >/dev/null 2>&1 && command -v timeout >/dev/null 2>&1; then
  timeout "$duration" dmesg --follow --time-format iso >"$output_dir/host-dmesg.log" 2>&1 &
  background_pids+=("$!")
fi

deadline=$((SECONDS + duration))
adb_captured=0
raw_started=0
while ((SECONDS < deadline)); do
  timestamp=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
  if command -v lsusb >/dev/null 2>&1; then
    {
      printf '=== %s ===\n' "$timestamp"
      lsusb
    } >>"$output_dir/lsusb-timeline.log" 2>&1
  fi
  if command -v adb >/dev/null 2>&1; then
    {
      printf '=== %s ===\n' "$timestamp"
      adb devices -l
    } >>"$output_dir/adb-timeline.log" 2>&1
  fi

  if [[ -n $serial && $adb_captured -eq 0 ]] && adb -s "$serial" get-state >/dev/null 2>&1; then
    adb_captured=1
    printf 'adb_seen_utc=%s\n' "$timestamp" >>"$output_dir/observation.txt"
    adb -s "$serial" shell getprop >"$output_dir/target-properties.txt" 2>&1 || true
    adb -s "$serial" shell cat /proc/cmdline >"$output_dir/target-cmdline.txt" 2>&1 || true
    adb -s "$serial" shell cat /proc/mounts >"$output_dir/target-mounts.txt" 2>&1 || true
    adb -s "$serial" shell dmesg >"$output_dir/target-dmesg.txt" 2>&1 || true
    adb -s "$serial" logcat -b all -d -v threadtime >"$output_dir/target-logcat.txt" 2>&1 || true
    adb -s "$serial" shell getevent -lp >"$output_dir/target-input-devices.txt" 2>&1 || true
  fi

  if [[ -n $serial && -n $input_device && $adb_captured -eq 1 && $raw_started -eq 0 ]]; then
    raw_started=1
    remaining=$((deadline - SECONDS))
    timeout "$remaining" adb -s "$serial" shell getevent -lt "$input_device" >"$output_dir/target-input-events.txt" 2>&1 &
    background_pids+=("$!")
  fi
  sleep 1
done

wait "${background_pids[@]}" 2>/dev/null || true
{
  date -u '+finished_utc=%Y-%m-%dT%H:%M:%SZ'
  printf 'adb_captured=%s\n' "$adb_captured"
  printf 'raw_input_started=%s\n' "$raw_started"
} >>"$output_dir/observation.txt"
