#!/usr/bin/env bash
# PreToolUse hook: pulls the latest approved Knowledge Hub docs into
# ~/.claude/memory/{tenant_slug}/ at most once per Cowork session.
#
# Gate file in /tmp keyed by parent PID — same trick as the Conneely
# article — so this runs once per session, not once per subagent.
set -euo pipefail

PPID_GATE="/tmp/kh-synced-${PPID:-$$}"
if [ -f "$PPID_GATE" ]; then
  exit 0
fi
touch "$PPID_GATE"

# Locate the python script next to this shell wrapper.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${KH_PYTHON:-python3}"

# Claude Code injects user_config values as CLAUDE_PLUGIN_OPTION_<key>.
# The python script reads KH_API_BASE_URL, so map it through.
export KH_API_BASE_URL="${CLAUDE_PLUGIN_OPTION_api_base_url:-${KH_API_BASE_URL:-https://api.knowledgehub.com}}"

# Run sync, swallowing output so we never block the tool call.
"$PYTHON_BIN" "$SCRIPT_DIR/sync_canon.py" >/dev/null 2>&1 || true
exit 0
