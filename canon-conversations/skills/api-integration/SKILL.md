---
name: canon-api-integration
description: >-
  Integrate, validate, smoke-test, and debug a server-side integration with the
  Canon Conversational API using a tenant API key (cc_live_… / cc_test_…). Use
  when integrating Canon conversational agents into an app, wiring the
  /v1/conversations endpoints, handling cc_ API keys, or debugging Canon API
  errors (Problem Details / request_id). Files bug reports to Canon staff when
  the fault is on Canon's side.
---

# Canon Conversational API integration

You help a **customer application developer** integrate the Canon Conversational
API into **their own app**. You do everything from the developer's side using
their **tenant API key** and the bundled reference contract — and when you hit a
fault that is on Canon's side, you file feedback for Canon staff.

## Hard guardrails — read first

- **Token is the only scope.** You operate solely with the developer's
  `cc_live_…` / `cc_test_…` key. Never ask for, accept, or use Supabase URLs,
  anon/publishable keys, service-role keys, DB connection strings, or
  `SUPABASE_*` secrets. If someone offers them, decline — the API key is all you
  need.
- **Never touch Canon's source.** You do not have, read, request, echo, or
  modify Canon's app, runtime, or database. You never run migrations. If a
  problem can only be fixed inside Canon, you **report it** (see step 6), you do
  not try to fix it.
- **Work only in the developer's repo.** All code you write lives in the
  customer's application. The Canon contract is read-only reference.
- **Keep the key server-side.** The API key must never appear in browser,
  mobile, or any public/client-side bundle or env. Browsers talk to the
  developer's backend; the backend talks to Canon.
- **Render only end-user-visible output.** Never surface tool calls, internal
  prompts, traces, hidden context, or raw provider payloads to end users.

## Reference contract (bundled — use these, they are authoritative)

- `${CLAUDE_PLUGIN_ROOT}/reference/conversational-api.llms.txt` — integration
  guide written for coding agents. Read this first.
- `${CLAUDE_PLUGIN_ROOT}/reference/conversational-api.openapi.json` — the OpenAPI
  contract (request/response shapes, Problem Details).
- `${CLAUDE_PLUGIN_ROOT}/reference/conversational-api-server-example.md` — a
  minimal server-side example to adapt.

If the developer also has these under `docs/` in their repo, prefer the bundled
copies — they match the deployed API.

## How the API works (explain this to the developer)

- **Conversation-scoped, server-managed history.** The developer creates a
  conversation once, stores the returned `conversation_id`, and then sends only
  the **next user turn** each time. Canon reconstructs the full prior transcript
  from `conversation_id` server-side and persists both the user message and the
  assistant reply. **The developer never resends history** — there is no field
  for client-supplied history.
- **Three core endpoints:**
  - `POST /v1/conversations` → `{ id, agent_slug, … }` (store the `id`).
  - `POST /v1/conversations/{conversation_id}/messages` → assistant reply with
    `response.content[]` `output_text` blocks.
  - `POST /v1/conversations/{conversation_id}/feedback` → end-user feedback (and
    the staff bug-report channel, see step 6).
- **Auth:** `Authorization: Bearer cc_live_…` (server-to-server only).
- **Idempotency:** send `Idempotency-Key` on every POST that creates a
  conversation, message, or feedback.
- **End-user identity:** pass a stable, opaque `end_user.id` (Canon hashes it).
  Do not send raw emails.
- **Errors:** non-stream errors are `application/problem+json` — read
  `code`, `detail`, and `request_id`. Log `request_id` + `conversation_id`.

## Workflow

Pick up where the developer is. Do not run every step blindly.

### 1. Explain how it works
Summarize the model above in terms of the developer's app. Confirm the agent
reference (`agent_id` or `agent_slug`), the channel key, and where conversation
ids will be stored. Read `conversational-api.llms.txt` for specifics.

### 2. Integrate (server-side, in the developer's repo)
Add a backend route/service that:
- creates a Canon conversation when there is no `conversation_id` yet, and stores it;
- sends user messages and renders `output_text` back to the end user;
- passes a stable `end_user.id` and uses `Idempotency-Key` on POSTs;
- logs the returned `X-Request-Id` for support.

Use these server-side env vars (document them; never hardcode the key):
`CANON_API_BASE_URL`, `CANON_API_KEY`, `CANON_AGENT_ID` (or `CANON_AGENT_SLUG`),
`CANON_CHANNEL_KEY`.

Add the smallest client change needed to call the developer's backend — never
call Canon directly from the browser.

### 3. Validate
Review the integration and report findings (severity-ordered, with file:line):
1. `CANON_API_KEY` used **only** server-side; no client/mobile reference to it.
2. POST requests send `Idempotency-Key`.
3. A stable, opaque `end_user.id` is passed.
4. Errors handle Problem Details (`code`, `detail`, `request_id`).
5. UI renders only end-user-visible assistant output — no tool calls, traces,
   prompts, or provider payloads.
6. No logging of API keys, `Authorization` headers, customer auth tokens, or
   signed file URLs.
7. Conversation ids persisted in a way that matches the product UX.

### 4. Test (real smoke test with the developer's token)
Prefer a `cc_test_…` key. Using the developer's own HTTP client (curl or a small
script in their repo) against `CANON_API_BASE_URL`:
1. `POST /v1/conversations` with the agent reference + a test channel → expect
   `200` and capture `id`.
2. `POST /v1/conversations/{id}/messages` with a `user` turn → expect `200` and
   a non-empty `output_text`.
3. Report status codes, the reply text, and any `request_id`s.

Minimal shape (adapt to the developer's stack; never inline the real key):
```bash
curl -sS -X POST "$CANON_API_BASE_URL/v1/conversations" \
  -H "Authorization: Bearer $CANON_API_KEY" -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{"agent_id":"'"$CANON_AGENT_ID"'","channel":{"type":"api","key":"'"$CANON_CHANNEL_KEY"'"},"end_user":{"id":"smoke-user"}}'
```

### 5. Debug
Decode the Problem Details `code` and act:

| `code` | HTTP | Meaning | Developer-side fix |
|---|---|---|---|
| `invalid_api_key` | 401 | Key missing/invalid/expired/revoked, or env mismatch (`cc_live_` vs `cc_test_`) | Check the key value (no stray whitespace/newline), env, and that it isn't revoked. |
| `missing_scope` | 403 | Key lacks a scope, or agent/channel not allowed for this key | Use a key with the needed scope / allowed agent / allowed channel. |
| `agent_not_found` | 404 | `agent_id`/`agent_slug` doesn't match this tenant | Fix the agent reference (Build → Agents). |
| `agent_not_published` | 409 | Agent has no published version | Publish the agent in the Canon app. |
| `invalid_request` | 400 | Body doesn't match the contract | Compare against the OpenAPI reference. |
| `not_configured` | 501 | Endpoint/feature not enabled on Canon's side | **Canon-side** — go to step 6. |
| `upstream_unavailable` / `internal_error` / `tool_execution_failed` | 5xx | Fault inside Canon | **Canon-side** — go to step 6. |

Always read `request_id` from the body (or the `X-Request-Id` response header)
and include it when reporting.

### 6. Report a Canon-side bug (feedback for staff)
When the fault is **on Canon's side** (`not_configured`, 5xx, or a clear contract
mismatch you cannot fix from the developer's app), file it so Canon staff can
triage it. Create or reuse a test conversation, then:

```bash
curl -sS -X POST "$CANON_API_BASE_URL/v1/conversations/$CID/feedback" \
  -H "Authorization: Bearer $CANON_API_KEY" -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{"category":"integration_bug","severity":"high","comment":"<what failed, the endpoint, the request_id(s), and a minimal repro>"}'
```

- Always set `category:"integration_bug"` and `severity:"high"` so triage routes
  it to Canon (SaaS) scope.
- Put the failing endpoint, the `request_id`(s), and a minimal repro in `comment`.
- Tell the developer what you reported and that Canon staff will triage it.
- This needs the `feedback:write` scope on the key.

## Finishing
Report: files changed (in the developer's repo), env vars required, how
conversation ids are stored, how `end_user.id` is chosen, how you verified
(smoke-test results), anything reported to Canon, and remaining manual setup.

> For the **browser widget** integration (a client-side embed instead of the
> server API), use the `/add-widget` command instead.
