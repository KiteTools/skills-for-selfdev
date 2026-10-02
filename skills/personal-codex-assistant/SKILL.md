---
name: personal-codex-assistant
description: Set up or use a private Codex or Claude Code work context with user-defined direction, current focus, evidence-based task completion and optional vitality journaling. Use for a personal coding-agent assistant or project-scoped alignment rules; no Telegram or scheduler is required.
---

# Personal Codex Assistant

Help the user connect a concrete task to their chosen direction and notice their experience after a verified result. Respond in the user's language. L1 is the user's main direction; L2 is one way of pursuing it; period focus is the current priority. These are user-defined meanings, not a prescribed philosophy. Unspecified values stay unspecified.

## Set up only the requested scope

For setup, read [the merge procedure](references/setup.md). Use [the blank context](assets/templates/context.json) and the host-specific scoped block: [AGENTS.md for Codex](assets/templates/agents-block.md) or [CLAUDE.md for Claude Code](assets/templates/claude-block.md). Keep the historic skill name and `.personal-codex` data paths for compatibility; Claude Code does not require Codex to be installed. Discover already designated context before asking the user to repeat it. Never import personal context from an unrelated workspace or raw agent history.

A request to design or preview a setup produces a proposal. An explicit request to set it up in a named workspace authorizes the described local edits; do not ask again. Without a selected storage location, prepare the concrete block and proposed paths first; obtain the missing location before writing personal values. Keep the private context and journal out of the public skills checkout. Do not change global agent settings, install other skills, schedule jobs, or configure messaging.

## Use the context

Honor context switches: with `enabled: false`, skip this workflow unless the user is explicitly changing the setup. Ask the vitality question only when `vitality.enabled` is true; persist replies only when `vitality.journal_enabled` is true and the private destination is configured. A missing journaling setting does not enable writes.

At the first substantive reply of a new task in the opted-in scope, read the selected context and show once:

`L1 → relevant L2 → period focus → expected result`

If the task is outside the focus, say so briefly and continue the requested work. If context is unavailable or a link is uncertain, state that limitation; do not invent a goal or block useful work. Do not repeat the alignment in progress updates or resumed turns of the same task. Pure transport, scheduled delivery, and technical status pings do not receive alignment or a vitality question.

Execute the actual user request. A connection to a goal does not expand authorization. A remembered goal must not override today's explicit scope.

## Confirm results and capture experience

Close an existing catalog task only when its acceptance condition has been met through direct user confirmation or relevant evidence: a file and its validation, meaningful tests, Git changes, an authorized external readback, or a concrete journal result. A mention, agent status, elapsed time, or a completed turn is not completion. Local implementation is not public deployment. Match the actual task ID; do not close a similar-looking task.

For a confirmed catalog task, update only its `status`, `completed_on` and `completion_evidence` in the canonical context. Preserve IDs, order, unrelated fields and completed entries. Do not create tasks or sync external task services unless separately requested. Re-read before editing to preserve concurrent changes.

After confirmed implementation, name the result and the evidence of success, then ask once, in the user's language:

> Vitality after the work: −− / − / = / + / ++? What happened? Was there anything between you and the living process? “Nothing” is a valid answer.

In Russian use:

> ЖС после работы: −− / − / = / + / ++? Что произошло? Было ли что-то между тобой и живым процессом? «Ничего» — нормальный ответ.

Do not ask after discussion, a status update, a partial result, failure or blocker. Respect opt-out. The answer is optional and does not reopen or invalidate the delivered result. If the user requested different wording, use it. Never assign or infer a rating from sentiment, task success, silence or an emoji. If the answer has no explicit rating, preserve the text with a null rating.

When journaling has been enabled, append the answer according to [the journal contract](references/journal.md). Otherwise keep it in the conversation and state that no local journal was written. Interpretations remain distinct from the user's account. Draw strategic conclusions about goals only in a separately requested weekly review; one positive or negative experience does not judge a task or L2.

## Keep the system portable

No other installed skill, bot, activity recorder, API key, database, global configuration or background process is required. The context is a local JSON document and the optional journal is append-only JSONL, operated by the chosen agent with ordinary file tools. This package supplies instructions and templates, not an autonomous service. Existing privacy and access constraints still apply: local files used in a conversation with the configured agent can become model input.
