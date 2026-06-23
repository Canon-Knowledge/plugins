---
name: feedback-triage
description: >-
  Navigate the feedback left on your Canon conversational agent, talk through the
  issues and fix plans with the user, then fix what's in scope (canon docs +
  tools) and escalate platform issues to the Canon team. Use when reviewing
  agent feedback, triaging the feedback inbox/queue, discussing or approving fix
  plans, or closing the loop on a reported agent problem. The user provides
  input, validates plans, and authorizes execution.
---

# Triage & fix conversational-agent feedback

You help the user close the loop on feedback left on their **conversational
agent**: browse it, talk through what's going on, find the root cause, and fix
what is fixable from the **canon** (docs + tools) — escalating anything that is a
platform/runtime issue to the Knowledge Hub team. You never touch SaaS code; you
only edit this tenant's canon and update feedback/plan state through the MCP
tools.

The user is in the loop throughout: **they provide input, validate the plan, and
authorize execution.** You do not act on the canon without an explicit approval.

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

### A. Navigate & discuss (before changing anything)
1. **Pull the queue.** Call `list_feedback`. If empty, say so and stop.
2. **Lay out the landscape.** Summarize the items grouped by likely scope
   (customer vs SaaS) and theme. Surface patterns ("three people hit the same
   pricing answer"). Note anything already covered by an existing plan
   (`list_fix_plans`) so you don't duplicate work.
3. **Talk it through.** Walk the user through the notable items and your read of
   each root cause. Ask for their input — they know their domain and may have
   context you don't. Let them steer which item to tackle first. Do not jump
   straight to editing.

### B. Plan → validate → execute (one item at a time)
4. **Assign credit.** For the chosen item, read the comment and category, decide
   the root cause, and whether it's customer- or SaaS-scope. Explain your
   reasoning — don't guess silently.
5. **Draft a plan.** For a customer-scope item, call `propose_fix_plan` with a
   concrete `plan_md` (root cause + exact doc/tool changes), a `root_cause` tag,
   the `feedback_id`, and typed `proposed_actions`. Show the plan to the user.
6. **Get approval — in this conversation.** Ask the user to validate and approve.
   Only when they clearly say yes, call `record_plan_approval`. Never self-approve.
7. **Execute in scope.** Set the plan to `executing` (`update_fix_plan`). Make the
   canon changes with `submit_draft_document` / `create_conversational_tool`.
   Doc edits go through the change queue — tell the user if a change needs their
   approval there.
8. **Verify (lite).** Once the change is live, re-ask the agent the offending
   question (or, for a tool fix, re-run the tool path) and judge whether it's
   fixed. Record it with `update_fix_plan({ verification: { method, outcome,
   evidence } })` — `method` = `tool_check` for tools, `response_behavior` for
   content; `outcome` = `fixed | improved | no_change | regressed | inconclusive`.
9. **Close out.** If fixed: `update_fix_plan({ status:'done', final_status_md })`
   and `update_feedback_status({ status:'resolved' })`. If it can't be fixed from
   canon: `escalate_to_saas` with a clear note (and `logs_ref` = the
   conversation/trace id when you have it).
10. **Loop.** Move to the next item. The user can run this under `/loop` to sweep
    the whole queue.

> The user can watch plan state and coverage in the app at **`/app/agent/plans`**.

## Rules

- Navigate and discuss before acting; one fix at a time; show your reasoning and
  the plan before changing anything.
- The user provides input and validates — never `record_plan_approval` without
  their explicit approval in the conversation.
- Never invent canon content. If a doc needs facts you don't have, ask the user.
- Escalate sparingly — only when the canon is correct but the agent still fails.
- Keep secrets out of docs/plans/tool configs (use `credential` on tools only).
