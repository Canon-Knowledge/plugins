# Conversational API Server Example

This example shows the intended server-side integration shape. Use the same
Lovable app origin that serves the Canon control plane as the API base URL.

## Environment

```bash
CANON_API_BASE_URL=https://<your-canon-lovable-app-domain>
CANON_API_KEY=cc_live_...
CANON_AGENT_SLUG=support-agent
CANON_CHANNEL_KEY=production-dashboard-chat
```

## Minimal TypeScript Fetch Client

```ts
type CanonConversation = {
  id: string;
  object: "conversation";
};

type CanonMessageResponse = {
  id: string;
  object: "message";
  response: {
    status: "completed" | "failed" | "cancelled";
    content: Array<{ type: "output_text"; text: string }>;
  };
};

const CANON_API_BASE_URL = process.env.CANON_API_BASE_URL!;
const CANON_API_KEY = process.env.CANON_API_KEY!;

async function canonFetch<T>(
  path: string,
  init: { method: string; body?: unknown; idempotencyKey?: string },
): Promise<T> {
  const res = await fetch(`${CANON_API_BASE_URL}${path}`, {
    method: init.method,
    headers: {
      "authorization": `Bearer ${CANON_API_KEY}`,
      "content-type": "application/json",
      ...(init.idempotencyKey ? { "idempotency-key": init.idempotencyKey } : {}),
    },
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(`${data.code ?? "canon_error"}: ${data.detail ?? data.error?.message ?? "request failed"}`);
  }
  return data as T;
}

export async function createCanonConversation(input: {
  customerUserId: string;
  customerUserDisplay?: string;
}) {
  return canonFetch<CanonConversation>("/v1/conversations", {
    method: "POST",
    idempotencyKey: crypto.randomUUID(),
    body: {
      agent_slug: process.env.CANON_AGENT_SLUG,
      channel: {
        type: "web_app",
        key: process.env.CANON_CHANNEL_KEY,
      },
      end_user: {
        id: input.customerUserId,
        display: input.customerUserDisplay,
        auth: { state: "authenticated" },
      },
    },
  });
}

export async function sendCanonMessage(input: {
  conversationId: string;
  text: string;
}) {
  return canonFetch<CanonMessageResponse>(
    `/v1/conversations/${encodeURIComponent(input.conversationId)}/messages`,
    {
      method: "POST",
      idempotencyKey: crypto.randomUUID(),
      body: {
        role: "user",
        stream: false,
        content: [{ type: "input_text", text: input.text }],
      },
    },
  );
}
```

## Handler Shape

```ts
export async function POST(request: Request) {
  const body = await request.json();
  const conversationId =
    body.conversationId ??
    (await createCanonConversation({
      customerUserId: body.customerUserId,
      customerUserDisplay: body.customerUserDisplay,
    })).id;

  const message = await sendCanonMessage({
    conversationId,
    text: body.message,
  });

  return Response.json({
    conversationId,
    text: message.response.content
      .filter((block) => block.type === "output_text")
      .map((block) => block.text)
      .join(""),
  });
}
```

## Integration Notes

- This route belongs on the customer's server, not in browser code.
- Use the customer's own auth/session layer to determine `customerUserId`.
- Log Canon `X-Request-Id` response headers in production once exposed by the
  concrete client wrapper.
- Store `conversationId` in the customer's session or database if the chat must
  continue across page loads.
