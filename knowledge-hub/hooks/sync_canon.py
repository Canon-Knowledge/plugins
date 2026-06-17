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
REFRESH_DAYS = 30  # refresh when fewer than this many days remain


def _resolve_api_base() -> str:
    # 1. Explicit env vars (set by hook wrapper or user)
    env = os.environ.get("KH_API_BASE_URL") or os.environ.get("CLAUDE_PLUGIN_OPTION_api_base_url")
    if env:
        return env.rstrip("/")
    # 2. config.json written by verify_token on first run (mirrors MCP server logic)
    config_file = CONFIG_DIR / "config.json"
    if config_file.exists():
        try:
            data = json.loads(config_file.read_text())
            if data.get("api_base_url"):
                return data["api_base_url"].rstrip("/")
        except Exception:
            pass
    return "https://api.knowledgehub.com"


API_BASE = _resolve_api_base()


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


def fetch_spaces(token: str) -> dict[str, dict]:
    """
    Map of scope-slug -> {name, description} for the tenant's Spaces.
    Best-effort: returns {} on any error (older SaaS without /api/spaces).
    """
    try:
        req = urllib.request.Request(
            f"{API_BASE}/api/spaces", headers={"Authorization": f"Bearer {token}"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return {s["slug"]: s for s in data.get("spaces", []) if s.get("slug")}
    except Exception:
        return {}


def slugify(s: str) -> str:
    import re
    s = re.sub(r"[^a-z0-9]+", "-", (s or "doc").lower()).strip("-")
    return s[:60] or "doc"


def doc_path(tenant_slug: str, d: dict) -> Path:
    """
    Local cache layout mirrors the wiki:
        <tenant>/<scope>/<doc_type>/<title-slug>.md

    When scope is missing the doc lands directly under the tenant; when
    doc_type is missing it's treated as a flat "doc". This must match the
    layout used by submit_draft_document in the MCP server so cached
    writes and pulls converge on the same path.
    """
    base = MEMORY_ROOT / tenant_slug
    title_slug = slugify(d.get("slug") or d.get("title") or "doc")
    parts: list[Path] = [base]
    scope = d.get("scope")
    if scope:
        parts.append(Path(slugify(scope)))
    dt = d.get("doc_type")
    if dt:
        parts.append(Path(slugify(dt)))
    parts.append(Path(f"{title_slug}.md"))
    result = parts[0]
    for p in parts[1:]:
        result = result / p
    return result


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
        f"Every doc must start with YAML front matter: purpose, read_when, read_full, depends_on, and code.\n"
        f"The adaptive conversational agent router uses purpose/read_when/read_full to choose context.\n"
        f"Use read_full: true rarely, only for identity, tone, and guardrails.\n"
        f"Create runtime tools for live data or actions outside docs; store secrets only as tool credentials.\n"
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


def rewrite_index(tenant_slug: str, space_meta: dict[str, dict] | None = None) -> None:
    """
    Walk the on-disk layout (<tenant>/<scope>/<doc_type>/<title>.md plus any
    legacy flat layout files) and emit memory.md as the entry-point index.

    Grouped by Space (scope), then by doc_type. Files at the tenant root (no
    scope) end up under "## Workspace". When `space_meta` carries a friendly
    name/description for a scope, the section header uses it.
    """
    space_meta = space_meta or {}
    base = MEMORY_ROOT / tenant_slug
    if not base.exists():
        return

    lines = [
        f"# Knowledge Hub: {tenant_slug}",
        "",
        "Index of locally-synced canon. Loaded at session start.",
        "",
    ]

    # Tenant-root .md files (legacy + scope-less docs).
    root_docs = sorted(p for p in base.glob("*.md") if p.name != "memory.md")
    if root_docs:
        lines += ["## Workspace", ""]
        for p in root_docs:
            lines.append(f"- [{p.stem}](./{p.name})")
        lines.append("")

    # New layout: <scope>/<doc_type>/<title>.md
    for scope_dir in sorted(p for p in base.iterdir() if p.is_dir() and not p.name.startswith(".")):
        # The legacy `teams/` and `notes/` roots used the old "team_slug"
        # layout (teams/<team>/processes/*.md). They're handled below.
        if scope_dir.name in ("teams", "notes"):
            continue
        # Exclude the per-Space manifest from the doc listing.
        nested = sorted(p for p in scope_dir.rglob("*.md") if p.name != "_space.md")
        if not nested:
            continue
        meta = space_meta.get(scope_dir.name, {})
        lines += [f"## {meta.get('name') or scope_dir.name}", ""]
        if meta.get("description"):
            lines += [meta["description"], ""]
        # Group by immediate parent directory (= doc_type).
        last_group = None
        for p in nested:
            group = p.parent.name if p.parent != scope_dir else "(uncategorized)"
            if group != last_group:
                lines.append(f"### {group}")
                last_group = group
            rel = p.relative_to(base).as_posix()
            lines.append(f"- [{p.stem}](./{rel})")
        lines.append("")

    # Legacy team layout (kept for backward compatibility).
    teams_dir = base / "teams"
    if teams_dir.exists():
        lines += ["## Teams", ""]
        for team_dir in sorted(p for p in teams_dir.iterdir() if p.is_dir()):
            lines.append(f"### {team_dir.name}")
            team_doc = team_dir / "team.md"
            if team_doc.exists():
                lines.append(f"- [team.md](./teams/{team_dir.name}/team.md)")
            for sub in ("processes", "projects", "notes"):
                sub_dir = team_dir / sub
                if sub_dir.exists():
                    for p in sorted(sub_dir.glob("*.md")):
                        lines.append(f"- [{p.stem}](./teams/{team_dir.name}/{sub}/{p.name})")
            lines.append("")

    notes_root = base / "notes"
    if notes_root.exists():
        lines += ["## Notes", ""]
        for p in sorted(notes_root.glob("*.md")):
            lines.append(f"- [{p.stem}](./notes/{p.name})")
        lines.append("")

    (base / "memory.md").write_text("\n".join(lines).rstrip() + "\n")


def prune_stale(tenant_slug: str, kept_paths: set[Path]) -> int:
    """
    Walk the tenant directory and delete any .md file not in kept_paths.
    Removes empty directories left behind. Returns count of files pruned.
    Preserves memory.md and .sync_state.json.
    """
    base = MEMORY_ROOT / tenant_slug
    if not base.exists():
        return 0
    pruned = 0
    for p in base.rglob("*.md"):
        if p.name in ("memory.md", "_space.md"):
            continue
        if p in kept_paths:
            continue
        try:
            p.unlink()
            pruned += 1
        except Exception:
            continue
    # Remove empty directories left behind by the prune (post-order walk).
    for d in sorted((p for p in base.rglob("*") if p.is_dir()), key=lambda x: -len(x.parts)):
        try:
            d.rmdir()
        except OSError:
            pass  # not empty — leave it
    return pruned


def main() -> int:
    token = read_token()
    if not token:
        # No canon token yet — onboarding hasn't completed. Silent no-op.
        return 0

    try:
        # Full sync: always fetch every active doc. Cheap at MVP scale and
        # the only reliable way to detect deletions (the API has no
        # tombstone feed). The `since` parameter is intentionally omitted.
        canon = fetch_canon(token, None)
    except urllib.error.HTTPError as e:
        # 401 → token revoked. Stop silently; the next onboarding run
        # will mint a new one.
        return 0 if e.code in (401, 404) else 2
    except Exception:
        return 2

    tenant_slug = slugify(canon.get("tenant_slug") or "workspace")
    docs = canon.get("docs", [])
    space_meta = fetch_spaces(token)

    written = 0
    kept_paths: set[Path] = set()
    scopes_seen: set[str] = set()
    for d in docs:
        try:
            p = doc_path(tenant_slug, d)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(d.get("content_markdown", ""))
            kept_paths.add(p)
            written += 1
            if d.get("scope"):
                scopes_seen.add(slugify(d["scope"]))
        except Exception:
            continue

    # Write a per-Space manifest (_space.md) so the local cache is labeled
    # with the Space's friendly name + description. Best-effort.
    base_dir = MEMORY_ROOT / tenant_slug
    for slug in scopes_seen:
        meta = space_meta.get(slug, {})
        name = meta.get("name") or slug.replace("-", " ").title()
        manifest = base_dir / slug / "_space.md"
        try:
            body = f"# Space: {name}\n\n"
            if meta.get("description"):
                body += meta["description"].strip() + "\n\n"
            body += f"Scope slug: `{slug}`\n"
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text(body)
            kept_paths.add(manifest)
        except Exception:
            continue

    # Delete any .md files left over from a previous sync (docs deleted in
    # the Hub, doc_type/scope renames, etc.). Without this the local cache
    # accumulates ghosts and Claude reads stale info.
    prune_stale(tenant_slug, kept_paths)

    base = MEMORY_ROOT / tenant_slug
    base.mkdir(parents=True, exist_ok=True)
    state_path = base / ".sync_state.json"
    state_path.write_text(json.dumps({
        "last_synced_at": canon.get("fetched_at") or datetime.now(timezone.utc).isoformat(),
        "doc_count": written,
    }))

    rewrite_index(tenant_slug, space_meta)
    upsert_claude_md(tenant_slug, API_BASE, canon.get("claude_instructions", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
