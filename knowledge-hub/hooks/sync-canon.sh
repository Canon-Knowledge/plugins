#!/usr/bin/env bash
# PreToolUse hook: pulls the latest approved Knowledge Hub docs into
# ~/.claude/memory/{tenant_slug}/ at most once per Cowork session.
#
# Gate file in /tmp keyed by parent PID — same trick as the Conneely
# article — so this runs once per session, not once per subagent.
#
# Every run appends a JSON line to ~/.config/knowledge-hub/sync.log so a
# silent failure ("Claude says fashionai.md is canonical and we can't
# figure out why") can be diagnosed without re-running anything.
set -euo pipefail

PPID_GATE="/tmp/kh-synced-${PPID:-$$}"
if [ -f "$PPID_GATE" ]; then
  exit 0
fi
touch "$PPID_GATE"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${KH_PYTHON:-python3}"

# Claude Code injects user_config values as CLAUDE_PLUGIN_OPTION_<key>.
# The python script reads KH_API_BASE_URL, so map it through.
export KH_API_BASE_URL="${CLAUDE_PLUGIN_OPTION_api_base_url:-${KH_API_BASE_URL:-https://api.knowledgehub.com}}"

LOG_DIR="${HOME}/.config/knowledge-hub"
LOG_FILE="${LOG_DIR}/sync.log"
mkdir -p "$LOG_DIR"
chmod 700 "$LOG_DIR" 2>/dev/null || true

START_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Run sync. Capture stderr to a tempfile so a failure is logged but
# nothing leaks back to the Claude Code tool call.
ERR_OUT="$(mktemp)"
EXIT_CODE=0
"$PYTHON_BIN" "$SCRIPT_DIR/sync_canon.py" >/dev/null 2>"$ERR_OUT" || EXIT_CODE=$?

# Slurp stderr (first ~400 chars) for the log.
STDERR="$(head -c 400 "$ERR_OUT" | tr '\n' ' ' | tr '"' "'")"
rm -f "$ERR_OUT"

END_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Best-effort doc count snapshot.
DOC_COUNT="$(find "${HOME}/.claude/memory" -name '.sync_state.json' -exec cat {} \; 2>/dev/null \
  | python3 -c "import sys, json
total = 0
for line in sys.stdin.read().splitlines():
    if not line.strip():
        continue
    try:
        total += json.loads(line).get('doc_count', 0)
    except Exception:
        pass
print(total)" 2>/dev/null || echo "?")"

# Append a JSON line.
printf '{"start":"%s","end":"%s","base_url":"%s","exit_code":%d,"doc_count":"%s","stderr":"%s","ppid":%d}\n' \
  "$START_TS" "$END_TS" "$KH_API_BASE_URL" "$EXIT_CODE" "$DOC_COUNT" "$STDERR" "${PPID:-0}" \
  >> "$LOG_FILE"

# Trim log to last 1000 lines so it doesn't grow forever.
if [ -f "$LOG_FILE" ]; then
  tail -n 1000 "$LOG_FILE" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"
fi

exit 0
