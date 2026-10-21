#!/usr/bin/env bash
set -euo pipefail

state="$1"
interval="${2:-45}"
heartbeat="${3:-6600}"
here="$(cd "$(dirname "$0")" && pwd)"
lock="$state/watch.lock"

exec 9>>"$lock"
if ! flock -n 9; then
  echo "WATCH already-running pid=$(cat "$lock")"
  exit 0
fi
echo $$ >"$lock"

deadline="$(jq -r '.deadline_epoch // 0' "$state/STATE.json")"
reviewed="$(jq -c '.panes // {} | map_values(.leaf)' "$state/STATE.json")"
skip_focused="$(jq -r '.mode == "awake"' "$state/STATE.json")"
active="$(jq -c '[.only[] as $p | select((.panes[$p].status // "watching") | IN("settled", "capped", "gone") | not) | $p]' "$state/STATE.json")"
start="$(date +%s)"

wake() {
  echo "WATCH $1"
  echo "Re-read $state/STATE.json and $(dirname "$here")/SKILL.md before acting."
  exit 0
}

[ "$active" != "[]" ] || wake "all-done"

while :; do
  now="$(date +%s)"
  [ "$deadline" -gt 0 ] && [ "$now" -ge "$deadline" ] && wake "deadline"
  [ $((now - start)) -ge "$heartbeat" ] && wake "heartbeat"

  ready="$("$here/targets.sh" | jq -sc \
    --argjson reviewed "$reviewed" --argjson skip_focused "$skip_focused" --argjson active "$active" '
    map(select((.status == "idle" or .status == "done")
               and .pending_bg == 0
               and .leaf != ($reviewed[.pane] // "")
               and (($skip_focused and .focused) | not)
               and (.pane as $p | $active | index($p))))
    | map(.pane)')"
  [ "$ready" != "[]" ] && wake "ready $ready"
  sleep "$interval"
done
