#!/usr/bin/env python3
"""
Sync the tenant's approved Knowledge Hub docs into ~/.claude/memory/.

Invoked by the PreToolUse hook wrapper. Read-only against the SaaS
(uses a read_canon-scoped PAT). Writes nothing outside
~/.claude/memory/{tenant_slug}/.

Design constraints:
- Idempotent. Tracks last_synced_at in .sync_state.json and uses
  GET /api/canon?since=<iso> to fetch only deltas.
- Never blocks the tool call. Any error is swallowed by the shell
  wrapper; this script just exits non-zero on hard failures.
- Token lives at ~/.config/knowledge-hub/canon-token (mode 0600), or in
  KH_CANON_TOKEN env var (overrides file).
"""
from __future__ import annotations
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone


HOME = Path.home()
CONFIG_DIR = HOME / ".config" / "knowledge-hub"
TOKEN_JSON = CONFIG_DIR / "canon-token.json"
TOKEN_LEGACY = CONFIG_DIR / "canon-token"   # plain-text fallback
MEMORY_ROOT = HOME / ".claude" / "memory"
API_BASE = os.environ.get("KH_API_BASE_URL", "https://api.knowledgehub.com").rstrip("/")
REFRESH_DAYS = 30  # refresh when fewer than this many days remain


def read_token_file() -> tuple[str | None, str | None]:
    """Return (raw_token, expires_at). Handles both JSON and legacy plain-text."""
    env_token = os.environ.get("KH_CANON_TOKEN")
    if env_token:
        return env_token.strip(), None
    if TOKEN_JSON.exists():
        try:
            data = json.loads(TOKEN_JSON.read_text())
            return data.get("token"), data.get("expires_at")
        except Exception:
            pass
    if TOKEN_LEGACY.exists():
        return TOKEN_LEGACY.read_text().strip(), None
    return None, None


def save_token_file(token: str, expires_at: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_JSON.write_text(json.dumps({"token": token, "expires_at": expires_at}))
    TOKEN_JSON.chmod(0o600)


def token_expires_soon(expires_at: str | None) -> bool:
    if not expires_at:
        return True
    try:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        remaining = (expiry - datetime.now(timezone.utc)).days
        return remaining < REFRESH_DAYS
    except Exception:
        return True


def refresh_token(current_token: str) -> tuple[str, str] | None:
    """Call POST /api/tokens/refresh. Returns (new_token, expires_at) or None on error."""
    try:
        req = urllib.request.Request(
            f"{API_BASE}/api/tokens/refresh",
            data=b"{}",
            headers={"Authorization": f"Bearer {current_token}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["token"], data["expires_at"]
    except Exception:
        return None


def read_token() -> str | None:
    """Read token, refreshing from the API if expiry is within REFRESH_DAYS."""
    token, expires_at = read_token_file()
    if not token:
        return None
    if token_expires_soon(expires_at):
        refreshed = refresh_token(token)
        if refreshed:
            token, expires_at = refreshed
            save_token_file(token, expires_at)
    return token


def fetch_canon(token: str, since: str | None) -> dict:
    url = f"{API_BASE}/api/canon"
    if since:
        from urllib.parse import urlencode
        url = f"{url}?{urlencode({'since': since})}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def slugify(s: str) -> str:
    import re
    s = re.sub(r"[^a-z0-9]+", "-", (s or "doc").lower()).strip("-")
    return s[:60] or "doc"


def doc_path(tenant_slug: str, d: dict) -> Path:
    base = MEMORY_ROOT / tenant_slug
    dt = d.get("doc_type")
    title_slug = slugify(d.get("slug") or d.get("title") or "doc")
    if dt == "company":
        return base / "company.md"
    team = slugify(d.get("team") or "general")
    if dt == "team":
        return base / "teams" / team / "team.md"
    if dt == "process":
        return base / "teams" / team / "processes" / f"{title_slug}.md"
    if dt == "project":
        return base / "teams" / team / "projects" / f"{title_slug}.md"
    if dt == "note":
        notes_dir = base / "teams" / team / "notes" if d.get("team") else base / "notes"
        return notes_dir / f"{title_slug}.md"
    return base / f"{title_slug}.md"


def _instructions_hash(instructions: str) -> str:
    import hashlib
    return hashlib.sha256(instructions.encode()).hexdigest()[:16]


def upsert_claude_md(tenant_slug: str, hub_url: str, claude_instructions: str = "") -> None:
    """
    Ensure ~/.claude/CLAUDE.md imports this tenant's memory index and
    has the current instructions from the SaaS.

    - Creates the file + block if neither exists.
    - Appends the block if the tenant isn't referenced yet.
    - Replaces the instructions section if the SaaS-provided text has
      changed (detected via a hash comment embedded in the block).

    The hash comment line looks like:
      # kh-hash:<hex16>
    It is invisible to Claude (treated as a comment) but lets the sync
    hook detect stale instructions and rewrite them in place.
    """
    claude_md = HOME / ".claude" / "CLAUDE.md"
    memory_path = f"~/.claude/memory/{tenant_slug}/memory.md"
    import_line = f"@{memory_path}"
    marker = f"# Company knowledge — {tenant_slug}"

    instructions = claude_instructions.strip() if claude_instructions else (
        f"The files above are a read-only local cache synced from the Knowledge Hub.\n"
        f"To update a doc use the submit_draft_document MCP tool.\n"
        f"Never edit files under ~/.claude/memory/ directly — the next sync overwrites them."
    )
    h = _instructions_hash(instructions)
    hash_line = f"# kh-hash:{h}"

    block = (
        f"\n{marker}\n"
        f"<!-- Source: {hub_url} -->\n"
        f"{import_line}\n"
        f"{hash_line}\n"
        f"\n"
        f"## Updating company knowledge\n\n"
        + instructions
        + "\n"
    )

    existing = claude_md.read_text() if claude_md.exists() else ""

    if marker not in existing:
        # First time for this tenant — append the block.
        with claude_md.open("a") as f:
            f.write(block)
        return

    # Block exists. Check whether the instructions hash has changed.
    if hash_line in existing:
        return  # Already up to date.

    # Hash mismatch — replace the entire tenant block with the new one.
    import re
    # Match from the marker to either the next "# Company knowledge —" or EOF.
    pattern = re.compile(
        r"(\n?" + re.escape(marker) + r".*?)(?=\n# Company knowledge —|\Z)",
        re.DOTALL,
    )
    updated = pattern.sub(block, existing)
    claude_md.write_text(updated)


def rewrite_index(tenant_slug: str) -> None:
    base = MEMORY_ROOT / tenant_slug
    if not base.exists():
        return
    lines = [
        f"# Knowledge Hub: {tenant_slug}",
        "",
        "Index of locally-synced canon. Loaded at session start.",
        "",
    ]
    company = base / "company.md"
    if company.exists():
        lines += ["## Company", "", f"- [company.md](./company.md)", ""]

    teams_dir = base / "teams"
    if teams_dir.exists():
        lines += ["## Teams", ""]
        for team_dir in sorted(p for p in teams_dir.iterdir() if p.is_dir()):
            lines.append(f"### {team_dir.name}")
            team_doc = team_dir / "team.md"
            if team_doc.exists():
                lines.append(f"- [team.md](./teams/{team_dir.name}/team.md)")
            procs = team_dir / "processes"
            if procs.exists():
                for p in sorted(procs.glob("*.md")):
                    lines.append(f"- [{p.name}](./teams/{team_dir.name}/processes/{p.name})")
            projs = team_dir / "projects"
            if projs.exists():
                for p in sorted(projs.glob("*.md")):
                    lines.append(f"- [{p.name}](./teams/{team_dir.name}/projects/{p.name})")
            lines.append("")
    (base / "memory.md").write_text("\n".join(lines).rstrip() + "\n")


def main() -> int:
    token = read_token()
    if not token:
        # No canon token yet — onboarding hasn't completed. Silent no-op.
        return 0

    try:
        # Read existing sync state, if any. We assume a single tenant
        # per machine for V1; multi-tenant sync is a V2 concern.
        state_files = list(MEMORY_ROOT.glob("*/.sync_state.json")) if MEMORY_ROOT.exists() else []
        since = None
        for sf in state_files:
            try:
                data = json.loads(sf.read_text())
                cur = data.get("last_synced_at")
                if cur and (since is None or cur < since):
                    since = cur
            except Exception:
                continue

        canon = fetch_canon(token, since)
    except urllib.error.HTTPError as e:
        # 401 → token revoked. Stop silently; the next onboarding run
        # will mint a new one.
        return 0 if e.code in (401, 404) else 2
    except Exception:
        return 2

    tenant_slug = slugify(canon.get("tenant_slug") or "workspace")
    docs = canon.get("docs", [])
    if not docs:
        return 0

    written = 0
    for d in docs:
        try:
            p = doc_path(tenant_slug, d)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(d.get("content_markdown", ""))
            written += 1
        except Exception:
            continue

    base = MEMORY_ROOT / tenant_slug
    base.mkdir(parents=True, exist_ok=True)
    state_path = base / ".sync_state.json"
    state_path.write_text(json.dumps({
        "last_synced_at": canon.get("fetched_at") or datetime.now(timezone.utc).isoformat(),
        "doc_count": written,
    }))

    rewrite_index(tenant_slug)
    upsert_claude_md(tenant_slug, API_BASE, canon.get("claude_instructions", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
