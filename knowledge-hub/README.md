# Knowledge Hub plugin

> **Dual-repo notice** — this directory is the source of truth, but users
> install the plugin from the **public** repo at
> [Canon-Knowledge/plugins](https://github.com/Canon-Knowledge/plugins).
> After any change here, run `scripts/deploy-plugin.sh` from the repo root
> to sync it. The script is idempotent — if nothing changed it exits cleanly.

Adds the `/onboard` slash command to Claude Code. The command conducts
a guided interview with a company admin and drafts the first version
of their Knowledge Hub wiki for a future conversational agent. The docs
must carry router front matter so the adaptive context layer knows when
to load each document. After onboarding, a `PreToolUse` hook
keeps the tenant's approved docs synced into
`~/.claude/memory/<tenant>/` once per session.

Also provides the **`feedback-triage`** skill: it navigates the feedback left on
the tenant's conversational agent, talks the issues and fix plans through with
the user, then fixes what's in canon scope (docs + tools) and escalates platform
issues to the Knowledge Hub team. It auto-triggers on feedback-triage intent and
replaces the former `/triage-feedback` command (single entry point, no overlap).

## Layout

```
.claude-plugin/
  plugin.json                  # Manifest (mcpServers, hooks, userConfig)
commands/
  onboard.md                   # The /onboard slash command + interview script
skills/
  feedback-triage/SKILL.md     # Navigate + triage agent feedback; fix canon, escalate SaaS
hooks/
  sync-canon.sh                # PreToolUse wrapper
  sync_canon.py                # Pull-once-per-session worker
mcp/
  server.js                    # MCP bundle (built from packages/mcp-onboarding/)
```

## Building

```bash
cd ../../packages/mcp-onboarding
npm install
npm run build                  # produces dist/server.js
mkdir -p ../../plugins/knowledge-hub/mcp
cp dist/server.js ../../plugins/knowledge-hub/mcp/server.js
```

The manifest points the MCP `command` at
`${CLAUDE_PLUGIN_ROOT}/mcp/server.js`, so the bundle must live at that
path when the plugin is packaged.

## Installing locally for development

```bash
# In Claude Code:
/plugin marketplace add /absolute/path/to/plugins/knowledge-hub
/plugin install knowledge-hub
# You'll be prompted for api_base_url — use http://localhost:5173 for local SaaS.
```

## Configuration

A single user-overridable value, declared in `plugin.json` under
`userConfig`:

| Key | Where it lands |
|---|---|
| `api_base_url` | Passed to the MCP as `KH_API_BASE_URL` via the `env` block. Passed to the hook via the auto-injected `CLAUDE_PLUGIN_OPTION_api_base_url` env var (mapped to `KH_API_BASE_URL` inside `sync-canon.sh`). |

## Tokens

Two tokens, two purposes:

1. **Onboarding token** — minted in the SaaS at `/onboarding`. Scope
   `["onboarding"]`. 24h expiry. Tenant-admin privileges within the
   tenant. Pasted by the admin once via `/onboard <token>`. Held in
   memory by the MCP server (never on disk). Revoked the instant
   `complete_onboarding` runs.

2. **Canon token** — minted by the SaaS at the end of onboarding.
   Scope `["read_canon"]`. 90-day expiry. Persisted to
   `~/.config/knowledge-hub/canon-token` (0600) by the MCP. The sync
   hook reads it to call `GET /api/canon`. No write capability.

## Invariants

- The command's interview calls **only** the Knowledge Hub MCP tools. No web
  fetches, shell commands, or other tools during onboarding.
- Every submitted doc opens with YAML router front matter:
  `purpose`, `read_when`, `read_full`, `depends_on`, and `code`.
- Every submitted doc passes the server-side linter: front matter,
  ≤ 200 lines, all required sections present, level-1 title heading.
- Conversational tools are created through `create_conversational_tool`;
  secrets go only through the credential field and are redacted from MCP logs.
- The sync hook writes **only** under `~/.claude/memory/<tenant>/`.
- Drive scans return folder + file *names* only. File contents are
  never read, transmitted, or stored.
