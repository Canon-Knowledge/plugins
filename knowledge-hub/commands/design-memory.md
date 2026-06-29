---
description: Design or refine what your conversational agent remembers about each end user — the memory schema (fact taxonomy + settings) for a space/bot. Invoked as /knowledge-hub:design-memory [space-slug].
argument-hint: [space-slug]
---

# Design the agent's memory schema

The user wants to define (or refine) **what their conversational agent durably
remembers about each end user** — the *memory schema* for one bot. A good schema
is the difference between an agent that re-asks everything and one that knows its
customers. You produce a small, business-fit **fact taxonomy** plus a few
settings, and write it to the space's `memory_config`.

The first argument, if present, is the **space slug** (the bot/business unit).
If absent, ask which space, or call `list_spaces` and let the user pick.

## How memory works here (so you design the right thing)

Memory is a set of typed **facts** per contact: `(fact_type, fact_key) → value`
with a confidence and evidence. The agent injects high-confidence facts into
every turn so it never re-asks. `fact_type` is a **controlled vocabulary** — the
schema. There are two layers:

- **Core types** (always available, do not redefine): `identity, contact, org,
  preference, intent, constraint, objection, issue, lifecycle, history` plus the
  commerce/post-sales cluster `order, return, payment, case, delivery`, and
  `other`.
- **Extensions** — business-specific types you add for *this* bot (e.g.
  `warranty`, `loyalty_tier`, `appointment`, `matter`).

You are choosing the **extensions** and the **settings**, not rebuilding the core.

## Steps

1. **Read the current state.** Call `get_memory_schema` with the space slug to
   see the built-in core types, the tenant default, and any existing space
   config. Don't propose what already exists.
2. **Understand the business.** Use `pull_canon` / the canon docs and a sample of
   real conversations to infer: the vertical (e-commerce, services, …), whether
   it's sales / support / both, and what the agent repeatedly needs to know or
   keeps re-asking. Note the lifecycle stages that matter (e.g. lead → customer →
   repeat, or open → resolved for support).
3. **Propose a schema.** Present, in plain language, for the user to approve:
   - Which **core** types are relevant (for orientation; they're always on).
   - The **extensions** to add, each with 1–3 example `fact_key`s and why.
   - **Settings**: `memory_mode` (default on), `min_inject_confidence`
     (default 0.65 — raise for stricter injection), `member_visibility`
     (`full` | `masked` | `admin_only`), `retention_days` (or none).
   Keep it tight — a handful of high-value extensions beats a sprawling list.
4. **Get explicit approval.** Do not write until the user says yes.
5. **Write it.** Call `set_memory_schema` (level defaults to `space`; pass the
   space slug). Default `mode` is `merge`, so you only send what changed — e.g.
   `{ taxonomy: { extensions: ["warranty","loyalty_tier"] }, member_visibility:
   "masked" }`. Use `mode: "set"` only to fully replace.
6. **Confirm** what was written and remind the user it applies to **new** memory
   going forward; existing facts are never rewritten (they're aliased on read).

## Guardrails

- Never put secrets, passwords, payment card data, or sensitive special-category
  data into the taxonomy — the runtime already filters these.
- Extensions are snake_case type names; keep them few and meaningful.
- This configures memory for **one space (bot)**. For an account-wide default,
  set `level: "tenant"` — but prefer per-space unless the user asks.
