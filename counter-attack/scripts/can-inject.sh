#!/usr/bin/env bash
set -euo pipefail

pane="$1"
seq="$2"
here="$(cd "$(dirname "$0")" && pwd)"

no() { echo "no $1"; exit 1; }

cur="$("$here/targets.sh" | jq -c --arg p "$pane" 'select(.pane == $p)')"
[ -n "$cur" ] || no "gone"

status="$(jq -r '.status' <<<"$cur")"
case "$status" in idle|done) ;; *) no "status=$status" ;; esac
[ "$(jq -r '.seq' <<<"$cur")" = "$seq" ] || no "state-changed"
[ "$(jq -r '.pending_bg' <<<"$cur")" = 0 ] || no "background-work"

if [ "$(jq -r '.kind' <<<"$cur")" = claude ]; then
  draft="$(herdr agent explain "$pane" --json | jq -r '
    [.evaluated_rules[] | select(.region == "prompt_box_body") | .evidence.region_preview][0] // ""' |
    sed 's/❯//g' | tr -d '[:space:]')"
  [ -z "$draft" ] || no "user-draft"
fi

echo ok
