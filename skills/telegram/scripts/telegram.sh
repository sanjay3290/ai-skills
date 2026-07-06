#!/usr/bin/env bash
# telegram.sh — send/receive Telegram messages via the Bot API.
# Deps: bash, curl, jq. Config: env vars or ~/.config/telegram/config.
set -euo pipefail

API_BASE="https://api.telegram.org"
CONFIG_DIR="${TELEGRAM_CONFIG_DIR:-$HOME/.config/telegram}"
CONFIG_FILE="$CONFIG_DIR/config"

usage() {
  cat >&2 <<'EOF'
Usage: telegram.sh <command> [args]

Commands:
  setup [--bot NAME]
      Guided bot registration (BotFather walkthrough + chat-ID discovery)
  send MESSAGE [--to TARGET] [--bot NAME] [--silent] [--format md|html]
      Send a text message (auto-splits over 4096 chars)
  file PATH [CAPTION] [--to TARGET] [--bot NAME] [--silent]
      Send a document (photos for png/jpg/jpeg/gif/webp)
  ask QUESTION [--options "Yes,No"] [--timeout SECS] [--to TARGET] [--bot NAME]
      Ask with inline buttons, wait for tap or text reply; prints answer.
      Exit 0 = answered, 2 = timeout
  read [--limit N] [--bot NAME] [--all]
      Print new incoming messages since last read

Config: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID env vars, or ~/.config/telegram/config
        Named bots: BOT_<NAME>_TOKEN   Named targets: TARGET_<NAME>=<chat_id>
EOF
  exit 1
}

die() { printf 'telegram.sh: %s\n' "$*" >&2; exit 1; }

check_deps() {
  command -v curl >/dev/null 2>&1 || die "curl is required but not found"
  command -v jq >/dev/null 2>&1 || die "jq is required but not found (brew install jq / apt install jq)"
}

# Env vars win; config file fills in whatever the environment didn't set.
load_config() {
  [ -f "$CONFIG_FILE" ] || return 0
  local key val
  while IFS='=' read -r key val; do
    case "$key" in ''|\#*) continue ;; esac
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    if [ -z "${!key:-}" ]; then export "$key=$val"; fi
  done < "$CONFIG_FILE"
}

upper_key() { printf '%s' "$1" | tr '[:lower:]-' '[:upper:]_'; }

resolve_bot() {
  local name="${1:-}"
  if [ -z "$name" ]; then
    BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
    BOT_KEY="default"
    [ -n "$BOT_TOKEN" ] || die "no bot token — run 'telegram.sh setup' or set TELEGRAM_BOT_TOKEN"
  else
    local var
    var="BOT_$(upper_key "$name")_TOKEN"
    BOT_TOKEN="${!var:-}"
    BOT_KEY="$name"
    [ -n "$BOT_TOKEN" ] || die "no token for bot '$name' — run 'telegram.sh setup --bot $name' or set $var"
  fi
}

resolve_target() {
  local t="${1:-}"
  if [ -z "$t" ]; then
    CHAT_ID="${TELEGRAM_CHAT_ID:-}"
    [ -n "$CHAT_ID" ] || die "no default chat — run 'telegram.sh setup' or set TELEGRAM_CHAT_ID"
  elif [[ "$t" =~ ^-?[0-9]+$ ]]; then
    CHAT_ID="$t"
  else
    local var
    var="TARGET_$(upper_key "$t")"
    CHAT_ID="${!var:-}"
    [ -n "$CHAT_ID" ] || die "unknown target '$t' — add $var=<chat_id> to $CONFIG_FILE"
  fi
}

# api METHOD [curl args...] — prints the JSON response, dies if .ok != true
api() {
  local method="$1" resp
  shift
  resp=$(curl -sS --max-time "${TELEGRAM_CURL_TIMEOUT:-35}" \
    "$API_BASE/bot$BOT_TOKEN/$method" "$@") || die "network error calling $method"
  [ "$(jq -r '.ok' <<<"$resp")" = "true" ] \
    || die "$method failed: $(jq -r '.description // "unknown error"' <<<"$resp")"
  printf '%s' "$resp"
}

cmd_send() {
  local msg="" to="" bot="" silent="false" format=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --to) to="$2"; shift 2 ;;
      --bot) bot="$2"; shift 2 ;;
      --silent) silent="true"; shift ;;
      --format) format="$2"; shift 2 ;;
      -*) die "unknown flag for send: $1" ;;
      *) if [ -z "$msg" ]; then msg="$1"; else die "unexpected argument: $1"; fi; shift ;;
    esac
  done
  [ -n "$msg" ] || die "send needs a message (telegram.sh help)"
  resolve_bot "$bot"
  resolve_target "$to"
  api sendMessage -d "chat_id=$CHAT_ID" --data-urlencode "text=$msg" \
    -d "disable_notification=$silent" >/dev/null
}

main() {
  check_deps
  load_config
  [ $# -ge 1 ] || usage
  local cmd="$1"
  shift
  case "$cmd" in
    send) cmd_send "$@" ;;
    -h|--help|help) usage ;;
    *) die "unknown command: $cmd (telegram.sh help)" ;;
  esac
}

main "$@"
