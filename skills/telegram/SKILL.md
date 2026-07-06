---
name: telegram
description: "Send Telegram messages, files, and alerts via bot API; read replies; ask questions with inline buttons and wait for the answer (approve-from-phone). Supports multiple bots and named chat targets. Use when the user wants to send a Telegram message or alert, get notified on Telegram when a task finishes or needs input, ask for approval via Telegram, or wire Telegram notifications into hooks, cron jobs, or CI. Triggers: 'telegram', 'send me a telegram', 'alert me on telegram', 'ask me on telegram', 'notify me when done'."
---

# Telegram

Send updates, alerts, and files to Telegram; read replies; run ask-and-wait
approval flows. Pure bash + curl + jq — no install beyond a bot token.

First run: `scripts/telegram.sh setup` (guided BotFather walkthrough).

## Commands

```bash
scripts/telegram.sh send "Deploy finished ✅"                    # basic alert
scripts/telegram.sh send "low priority" --silent                # no notification sound
scripts/telegram.sh send "*bold* alert" --format md             # MarkdownV2 (falls back to plain)
scripts/telegram.sh send "hi" --to alerts --bot work            # named target + named bot
scripts/telegram.sh file report.pdf "Q3 report"                 # document (photos auto-detected)
scripts/telegram.sh read                                        # new incoming messages since last read
ANSWER=$(scripts/telegram.sh ask "Deploy to prod?" --options "Yes,No" --timeout 300)
# exit 0 = answered (stdout = answer), 2 = timeout
```

## Config

Env vars win, then `~/.config/telegram/config` (mode 600):

```
TELEGRAM_BOT_TOKEN=123:ABC...     # default bot
TELEGRAM_CHAT_ID=987654321        # default target
BOT_ALERTS_TOKEN=456:DEF...       # --bot alerts   (add via: setup --bot alerts)
TARGET_FAMILY=-100987...          # --to family    (any chat/group/channel id)
```

Replies and answers are only accepted from configured chat IDs.

## Claude Code hooks (settings.json)

Ping your phone when Claude needs input, and when it finishes:

```json
{
  "hooks": {
    "Notification": [{"hooks": [{"type": "command",
      "command": "~/.claude/skills/telegram/scripts/telegram.sh send \"🔔 Claude needs input in $(basename \\\"$PWD\\\")\""}]}],
    "Stop": [{"hooks": [{"type": "command",
      "command": "~/.claude/skills/telegram/scripts/telegram.sh send \"✅ Claude finished in $(basename \\\"$PWD\\\")\" --silent"}]}]
  }
}
```

Approval gate in any script/automation:

```bash
if [ "$(scripts/telegram.sh ask 'Deploy to prod?' --options 'Yes,No')" = "Yes" ]; then
  ./deploy.sh
fi
```
