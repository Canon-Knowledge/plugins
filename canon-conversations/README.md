# Canon Conversations plugin

Coding-agent-first integration workflows for Canon conversational agents.

This plugin is separate from `knowledge-hub` on purpose:

- `knowledge-hub` is for tenant onboarding, canon/wiki work, and admin setup.
- `canon-conversations` is for customer application developers integrating the
  runtime API or widget into their own apps.

## Skill

| Skill | Purpose |
|---|---|
| `canon-api-integration` | End-to-end server-side API integration: explain the model, scaffold the integration, validate, run a real smoke test with the developer's `cc_` key, debug Problem-Details errors, and file `integration_bug` feedback when the fault is on Canon's side. Auto-triggers on integration intent. |

The skill is self-contained: it ships the API contract under
[`reference/`](reference/) (`conversational-api.llms.txt`,
`conversational-api.openapi.json`, `conversational-api-server-example.md`), so a
developer integrating in their own repo needs nothing from the Canon codebase —
only their tenant API key.

## Commands

| Command | Purpose |
|---|---|
| `/add-widget` | Add the Canon browser-widget snippet safely (client-side embed). |

> The previous `/integrate` and `/verify` commands were folded into the
> `canon-api-integration` skill so there is a single entry point for the server
> API. `/add-widget` remains for the distinct client-widget path.

## Current Status

The public API is live and served from the app. The skill drives integration,
validation, smoke-testing, and debugging entirely over HTTP with the developer's
tenant API key — it never reads or modifies Canon's source.

A live MCP server is **optional, future** work (see [MCP-ROADMAP.md](MCP-ROADMAP.md)):
verifying keys, creating test conversations, and sending smoke-test messages as
typed tools. Not required for the skill to work today.
