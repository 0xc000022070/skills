#!/usr/bin/env bash
set -euo pipefail

prefix="${1:-counter-}"
self="${HERDR_PANE_ID:-}"

transcript_for() {
  local kind="$1" cwd="$2" sid="$3"
  [ -n "$sid" ] || return 0
  case "$kind" in
    claude)
      local slug
      slug="$(printf '%s' "$cwd" | sed 's#[/.]#-#g')"
      local f="$HOME/.claude/projects/$slug/$sid.jsonl"
      [ -f "$f" ] && printf '%s' "$f"
      ;;
    codex)
      find "$HOME/.codex/sessions" -name "rollout-*-$sid.jsonl" -print -quit 2>/dev/null || true
      ;;
  esac
}

# Background tasks started in a Claude transcript that never produced a
# <task-id> notification. A "done" pane with pending work will wake itself.
pending_bg() {
  local f="$1"
  [ -n "$f" ] || { printf '0'; return; }
  local started finished
  started="$(rg -o --no-filename '(?:with ID: |\(ID: |agentId: )([a-z0-9]+)' -r '$1' "$f" 2>/dev/null | sort -u || true)"
  finished="$(rg -o --no-filename '<task-id>([a-z0-9]+)</task-id>' -r '$1' "$f" 2>/dev/null | sort -u || true)"
  comm -23 <(printf '%s\n' "$started" | sed '/^$/d') <(printf '%s\n' "$finished" | sed '/^$/d') | wc -l | tr -d ' '
}

leaf_of() {
  local f="$1"
  [ -n "$f" ] || return 0
  tail -n 400 "$f" | jq -r 'select(.type == "user" or .type == "assistant" or .type == "response_item") | .uuid // .timestamp // empty' 2>/dev/null | tail -n 1 || true
}

herdr agent list | jq -c '.result.agents[]' | while read -r a; do
  pane="$(jq -r '.pane_id' <<<"$a")"
  name="$(jq -r '.name // ""' <<<"$a")"
  [ "$pane" = "$self" ] && continue
  [ -n "$name" ] && [[ "$name" == "$prefix"* ]] && continue

  kind="$(jq -r '.agent' <<<"$a")"
  cwd="$(jq -r '.cwd' <<<"$a")"
  sid="$(jq -r '.agent_session.value // ""' <<<"$a")"
  tr_path="$(transcript_for "$kind" "$cwd" "$sid")"
  pending=0
  [ "$kind" = claude ] && pending="$(pending_bg "$tr_path")"

  leaf="$(leaf_of "$tr_path")"
  [ -n "$leaf" ] || leaf="seq:$(jq -r '.state_change_seq' <<<"$a")"

  jq -c \
    --arg transcript "$tr_path" \
    --arg leaf "$leaf" \
    --argjson pending "$pending" \
    '{pane: .pane_id, name: (.name // null), kind: .agent, status: .agent_status,
      seq: .state_change_seq, focused: .focused, cwd: .cwd,
      title: .terminal_title_stripped, transcript: $transcript, leaf: $leaf,
      pending_bg: $pending}' <<<"$a"
done
