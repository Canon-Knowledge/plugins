# Canon Conversations MCP Roadmap

The public API is now live and the `canon-api-integration` skill drives the full
integration/validate/test/debug flow over plain HTTP with the developer's tenant
API key — **no MCP server is required today**. The tools below are an optional
future enhancement (typed guardrails instead of free-form HTTP), not a blocker.

Planned tools:

| Tool | Purpose | Requires migrations |
|---|---|---|
| `get_openapi_schema` | Return the active OpenAPI schema. | No |
| `get_sdk_example` | Return framework-specific integration examples. | No |
| `verify_api_key` | Validate key shape, scopes, and tenant. | Yes |
| `create_test_conversation` | Start a real test conversation. | Yes |
| `send_test_message` | Send a smoke-test user message. | Yes |
| `get_widget_snippet` | Return a widget snippet for a channel. | Yes |
| `estimate_usage_for_test` | Return raw usage for a test conversation. | Yes |

Initial implementation recommendation:

1. Start with a local MCP server that serves static OpenAPI/examples from the
   plugin package.
2. Add authenticated API-key verification only after `api_keys` exists.
3. Add smoke-test conversation tools only after the public runtime endpoints
   write conversations, messages, traces, and usage events.
4. Never return API keys, end-user auth tokens, tool credentials, hidden prompts,
   or raw provider payloads from MCP tools.
