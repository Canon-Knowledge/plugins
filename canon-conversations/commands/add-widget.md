# Add Canon Widget

Add the Canon embeddable widget to the current app.

> This command covers the **browser widget** (client-side embed). For a
> **server-side API integration** — wiring `/v1/conversations`, validating,
> smoke-testing, and debugging with a `cc_` key — use the
> **canon-api-integration** skill instead.

Use this workflow:

1. Inspect the app's framework, layout entry point, script loading conventions,
   and environment variable naming.
2. Add the widget script only in a browser-rendered layout or page.
3. Keep the public `data-embed-key` separate from secret API keys. The embed key
   is safe in browser code; `CANON_API_KEY` is not.
4. Prefer environment variables for:
   - widget runtime URL
   - embed key
   - title
   - brand color
   - position
5. Avoid multiple widget instances unless the app explicitly needs them.
6. Do not modify Supabase, server database schema, or Canon runtime code from a
   customer app integration.

Expected snippet shape:

```html
<script
  src="https://your-runtime.example/widget.js"
  data-embed-key="public_embed_key"
  data-title="Assistant"
  data-color="#111827"
  data-position="right"
></script>
```

Before finishing, report:

- where the script is loaded
- which env vars must be configured
- whether the widget loads once globally or on a specific page
- any CSP or script loading risks found
