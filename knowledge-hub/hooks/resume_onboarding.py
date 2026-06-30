#!/usr/bin/env python3
"""Inject resumable Knowledge Hub state into every new Claude session."""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path


CONFIG = Path.home() / ".config" / "knowledge-hub"


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def api_base() -> str:
    configured = read_json(CONFIG / "config.json").get("api_base_url")
    return (
        os.environ.get("KH_API_BASE_URL")
        or os.environ.get("CLAUDE_PLUGIN_OPTION_api_base_url")
        or configured
        or "https://api.knowledgehub.com"
    ).rstrip("/")


def token() -> str | None:
    for name in ("onboarding-token.json", "write-token.json"):
        value = read_json(CONFIG / name).get("token")
        if value:
            return value
    return None


def main() -> None:
    bearer = token()
    if not bearer:
        return
    request = urllib.request.Request(
        f"{api_base()}/api/onboarding/state",
        headers={"Authorization": f"Bearer {bearer}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            state = json.loads(response.read().decode("utf-8"))
    except Exception:
        return

    pending_uploads = [
        action.get("filename")
        for action in (state.get("pending_actions") or [])
        if action.get("type") == "asset_upload" and action.get("filename")
    ]

    lines = ["<knowledge-hub-session-state>"]
    if state.get("status") == "in_progress":
        lines.extend([
            "Knowledge Hub onboarding is in progress and its credential is already loaded by the MCP.",
            "Proactively tell the user where onboarding stopped and offer to continue now; do not ask for a token or slash command.",
            "Use the Knowledge Hub onboarding tools and follow the installed onboard command workflow from the current checkpoint.",
        ])
    if pending_uploads:
        lines.append("Outstanding Knowledge Hub uploads: " + ", ".join(pending_uploads) + ". Remind the user and offer upload_asset_file after explicit approval.")
    if len(lines) == 1:
        return
    lines.append("</knowledge-hub-session-state>")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
