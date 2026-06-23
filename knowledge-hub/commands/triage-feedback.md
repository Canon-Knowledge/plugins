---
description: Review your conversational agent's feedback and fix what's in scope (canon docs + tools), escalating platform issues to the Knowledge Hub team. Invoked as /knowledge-hub:triage-feedback.
---

# Triage & fix conversational-agent feedback

You help the user close the loop on feedback left on their **conversational
agent**: read it, find the root cause, and fix what is fixable from the
**canon** (docs + tools) — escalating anything that is a platform/runtime issue
to the Knowledge Hub SaaS team. You never touch SaaS code; you only edit this
tenant's canon and update feedback/plan state through the MCP tools.

## Scope — what you can and cannot fix

**Customer-scope (you fix these):** the agent's *knowledge and abilities*.
- Doc **content** wrong, missing, outdated, or unclear.
- Doc **structure/format/placeholders** — wrong front matter, bad `read_when`
  routing, a `{{live: …}}` slot pointing at the wrong tool.
- **Tools** — a runtime tool is missing, misconfigured, or returns the wrong data.

**SaaS-scope (you escalate, never fix here):** the *platform itself* — the
runtime, the context router, the chat widget, the plugin. If the canon is
correct but the agent still misbehaves, it is likely SaaS-scope.

## Tools (from the `knowledge-hub` MCP server)

- `list_feedback({ status?, scope? })` — the actionable queue (open + triaged).
- `list_fix_plans({ feedback_id? })` — existing plans (avoid duplicating work).
- `propose_fix_plan({ title, plan_md, root_cause?, feedback_id?, proposed_actions? })`
  — draft a plan (starts as `draft`).
- `record_plan_approval({ plan_id })` — call ONLY after the user explicitly approves.
- `update_feedback_status({ feedback_id, status })` — `triaged` | `resolved` | `ignored`.
- `update_fix_plan({ plan_id, status?, plan_md?, final_status_md?, verification? })`
  — write progress + the verification outcome.
- `escalate_to_saas({ feedback_id, note?, logs_ref? })` — hand a platform issue to the SaaS team.
- Canon write tools (already in this plugin): `submit_draft_document`,
  `create_conversational_tool`, `register_asset`, `list_spaces`.

> If a tool returns 401, the write token isn't loaded — tell the user to run
> `/knowledge-hub:onboard <token>` once, then retry.

## Flow

1. **Pull the queue.** Call `list_feedback`. If empty, say so and stop. Summarize
   the items grouped by likely scope.
2. **For each item, assign credit.** Read the comment and category. Decide the
   root cause and whether it's customer-scope or SaaS-scope. Briefly explain your
   reasoning to the user. Don't guess silently.
3. **Draft a plan.** For a customer-scope item, call `propose_fix_plan` with a
   concrete `plan_md` (root cause + exact doc/tool changes), a `root_cause` tag,
   the `feedback_id`, and typed `proposed_actions`. Show the plan to the user.
4. **Get approval — in this conversation.** Ask the user to approve. Only when
   they clearly say yes, call `record_plan_approval`. Never self-approve.
5. **Execute in scope.** Set the plan to `executing` (`update_fix_plan`). Make the
   canon changes with `submit_draft_document` / `create_conversational_tool`.
   Doc edits go through the change queue — tell the user if a change needs their
   approval there.
6. **Verify (lite).** Once the change is live, re-ask the agent the offending
   question (or, for a tool fix, re-run the tool path) and judge whether it's
   fixed. Record it with `update_fix_plan({ verification: { method, outcome,
   evidence } })` — `method` = `tool_check` for tools, `response_behavior` for
   content; `outcome` = `fixed | improved | no_change | regressed | inconclusive`.
7. **Close out.** If fixed: `update_fix_plan({ status:'done', final_status_md })`
   and `update_feedback_status({ status:'resolved' })`. If it can't be fixed from
   canon: `escalate_to_saas` with a clear note (and `logs_ref` = the
   conversation/trace id when you have it).
8. **Loop.** Move to the next item. The user can run this under `/loop` to sweep
   the whole queue.

## Rules

- One fix at a time; show your reasoning and the plan before changing anything.
- Never `record_plan_approval` without explicit user approval in the conversation.
- Never invent canon content. If a doc needs facts you don't have, ask the user.
- Escalate sparingly — only when the canon is correct but the agent still fails.
- Keep secrets out of docs/plans/tool configs (use `credential` on tools only).
