---
name: site-to-sales-kb
description: >-
  Crawl a website (domain or sitemap) and turn it into a structured Markdown
  knowledge base for a sales-oriented conversational agent — catalog, pricing,
  promotions, locations, B2B, policies, support/FAQ, brand voice and objection
  handling, every fact tied to its source URL. Use when the user gives a URL and
  wants to "map a site", "build a knowledge base for a chatbot / sales bot",
  "scrape a catalog and locations for an AI agent", or during Knowledge Hub
  onboarding when the user's input is a website instead of files. The skill
  produces source Markdown documents; the caller (e.g. onboarding) then turns
  them into wiki docs.
---

# Site → sales knowledge base

Given a website domain (e.g. `https://empresa.com.br/`), map every
sales-relevant area of the site — product/service catalog, locations/units,
B2B/corporate channel, institutional/brand, policies, support/FAQ — and produce
a **complete, source-linked Markdown knowledge base** that a conversational
**sales agent** can answer from. The bar is: everything a human salesperson
would use to answer a customer and close a sale (prices, conditions, promos,
objection handling, contacts) is captured, with the origin URL for every fact.

The skill is **generic** — it must work for any e-commerce/services site that
navigates by categories, not one niche.

## Output contract

- Write all output under a single working folder:
  `site-kb-<domain>-<YYYYMMDD>/` (use the scratchpad dir if temporary).
- Each content domain gets its own file (`01-overview.md`, `02-catalog.md`,
  `03-locations.md`, …). A final `00-knowledge-base.md` compiles everything in
  the canonical schema (see `reference/esquema-documento.md`).
- Markdown is the **primary deliverable** — it is the best format for LLM
  ingestion. Offer `.docx` / `.xlsx` / `.json` only as extras on request.
- **When invoked from Knowledge Hub onboarding**, the compiled Markdown is the
  *source*, not the final artifact: the onboarding flow splits it into atomic,
  front-mattered wiki docs via `submit_draft_document` (overview/tone/guardrails
  → `read_full: true`; catalog/pricing/FAQ → on-demand). Keep the per-section
  files clean so that split is mechanical.

## Workflow

### 1. Intake
Ask the user (use `AskUserQuestion` if available, else ask directly):
- Main URL, plus related subdomains worth crawling (help center, franchise
  portal, blog).
- Output format (default **Markdown**; offer `.docx`/`.xlsx`/`.json` as extras).
- Language of the output (default: match the site).
- Focus: **sales**, **support**, or **both** — this changes what enters the doc.

### 2. Discovery
- Fetch the home page and main menu; map the sections (product/service
  categories, locations, B2B, institutional, support).
- Try `/sitemap.xml` first as a shortcut to enumerate URLs.
- Flag which sections are **large** (long catalogs, many locations, long FAQs) —
  those need dedicated subagents.

### 3. Task plan
Create a task list (`TaskCreate`/`TaskUpdate`) with one item per content domain:
product catalog, service catalog, locations, B2B/corporate, institutional,
support/policies, final compilation, verification, delivery.

### 4. Pagination & completeness — critical rule
Before declaring any section mapped, **explicitly check for pagination**
("Showing X–Y of Z results", page numbers, `?page=` params). If present,
enumerate and fetch **every** page. Always compare the final captured count
against the total the site declares; if they differ, **flag the discrepancy in
the final document** rather than silently omitting items.

### 5. Parallel extraction via subagents
Launch subagents (Agent tool) in parallel, **one per content domain**, with
`model: haiku` by default — repetitive extraction does not need an expensive
model. Each subagent must:
- receive the exact list of URLs to visit,
- extract the structured fields (see the sales schema in step 6),
- write its part to its own Markdown file in the output folder,
- return to the orchestrator only a **short summary** (counts), never the full
  raw content — keep the orchestrator's context small.

### 6. Sales enrichment layer (beyond name/price/link)
For each product/service, besides name/description/price/link, capture when
available:
- Promotions, discounts, bundles/combos, upsell/cross-sell opportunities.
- CTAs and conversion paths (WhatsApp link, buy button, quote form, checkout).
- Objection-handling material: warranties, return/refund policy, FAQ, deadlines.
- Social proof: testimonials, awards, customers-served numbers, ratings.
- Urgency/scarcity triggers (limited-time, seasonal offers).
- Differentiation/USPs and brand positioning lines (taglines).
- **Tone-of-voice samples** (verbatim phrases) for the bot to mimic the brand.
- Lead-capture mechanisms (signup, newsletter, customer account).

### 7. Verification
After compiling, launch a `haiku` subagent to spot-check a sample (8–12 links
across sections) that URLs resolve and match the expected content. Report the
result in the document and in chat.

### 8. Final compilation — canonical schema
Merge everything into one Markdown document using the fixed structure in
`reference/esquema-documento.md` (adapt section names to the business, keep the
logical order). Sections: company overview · catalog · locations · B2B ·
franchises/partnerships · institutional/brand · support · policies · contacts
table · social media · **notes for whoever trains the bot** (known gaps,
JS-only pages, count discrepancies, recommended refresh cadence).

### 9. Output & delivery
Markdown is the primary deliverable. On request, also produce `.docx` (skill
`docx`), `.xlsx` (skill `xlsx`), or a `.json` of the structured catalog for
direct agent integration. Deliver the file(s) via the available file-presentation
mechanism.

### 10. Continuous update
At the end, **always offer to schedule a periodic re-run** (skill `schedule` /
scheduled tasks) — price, stock and locations change.

## Guardrails

- **Never invent data** not found on the site. If a field is missing, mark it
  "not available" and cite the URL where you looked.
- **Always cite the source URL** for every fact/price/condition.
- If a page is empty or clearly **JavaScript-rendered** (content obviously
  incomplete), flag it for manual review / escalation to a real-browser tool
  instead of proceeding with partial data unannounced.
- **Do not** access authenticated pages, user-account pages, or anything
  exposing third parties' personal data.
- **Do not overload the server**: avoid excessive parallel requests to one
  domain; respect `robots.txt` where applicable.
- Treat **duplicate entries** across categories (same product/service in
  multiple categories) as a single entity, noting every category it appears in.

## Before finishing
Run `reference/checklist-verificacao.md`. Do not deliver until every box is
satisfied or its gap is explicitly noted in the "notes for whoever trains the
bot" section.
