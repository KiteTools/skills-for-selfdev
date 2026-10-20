---
name: weekly-review
description: Review a supplied week's notes, activity summaries, decisions, and results to trace learning into practice, separate evidence from interpretation, and choose one optional next experiment. Works on demand without a bot or activity tracker.
---

# Weekly review

Help the user understand how the week unfolded and what, if anything, they want to change. Trace **source → active understanding → chosen practice → observed result**. This is a reflection, not a productivity score or an assessment of someone's spiritual state.

## Scope and evidence

Establish the date range and timezone from the request or supplied material. A calendar week means Monday–Sunday in the user's timezone unless they choose otherwise. Do not invent a timezone. With date-only notes, review the named dates and disclose that time-window alignment is unavailable.

Use only supplied or explicitly designated sources. A short diary is sufficient. Optional inputs include journal exports, completed reflection decisions, calendars, authorized summarized activity, user-selected artifacts, Git/test evidence, and external readback. OpenClaw, Computer History, and any particular personal framework are not required. Installing this skill does not authorize collection, scheduling, messages, or changes to tasks.

Start with existing evidence, not a request that the user reconstruct the entire week. Preserve source IDs and coverage. A summary window is not continuous engagement; an opened document is not understood material; generated output is not reviewed work; an agent's completion status is not a verified result. A calendar appointment is a plan until attendance is evidenced.

Prefer explicit user statements for internal experience and offline events. Apply later corrections to prior interpretations; retain provenance. If a correction and independent evidence still conflict, show the conflict rather than silently choosing. Do not infer awareness, vitality, motivation, spiritual connection, or understanding from app usage.

## Optional Codex and Cursor machine time

Use selected, reviewed metadata summaries only when supplied or explicitly authorized. No collector or hook installer ships with this skill. Keep **human elapsed time**, **agent runtime**, **reviewed output**, and **understanding** separate. Cursor in the foreground is not proof that an agent was running; an agent running is not proof the person was reading or learning.

For each date, preserve separate `codex_agent_runtime_min` and `cursor_agent_runtime_min`, source/coverage status, and the known combined `agent_runtime_min`. Missing means unknown, not zero. A known subtotal with a missing provider is incomplete. Sum provider values once; do not add a provider to a total that already includes it. For supplied legacy `agent_time_context` snapshots with schema 1–3, `agent_runtime_min` means Codex only; this convention does not apply to arbitrary third-party exports without checking their schema.

- Prefer matched, completed root request-to-stop hook intervals. Deduplicate repeats and the same run observed by both hooks and a metadata fallback. Exclude child/subagent runs from the root total; distinct parallel root runs can overlap and still contribute to summed runtime.
- If only an explicitly authorized read-only Cursor metadata summary is available, label it partial. Use evidenced request-to-final-message bounds plus a completion marker. `turnDurationMs` may describe only the final work segment; never substitute it for the full run or use the age of a conversation. Missing start/end or completion leaves that run untimed.
- Runtime includes tool and approval waits within the measured interval; it is not GPU time, cost, human effort, or a productivity score. Distinguish sum of root-run durations from their union wall time. Clip intervals to the user's local dates before aggregation, respecting timezone offsets and daylight saving changes.
- Before weekly aggregation, refresh every date, including days without an evening snapshot, **only if an authorized collector is available**. Otherwise use the supplied summary and disclose its age/coverage. Replace that day's provider value when incorporating a fresher summary; recalculate the combined subtotal without rewriting human observations. Never fill unavailable days with zeros.
- Show coverage by provider: days with numeric observations / days requested, partial days, and unavailable days. Preserve valid observed zeros with their coverage. A partial numeric estimate is an observed lower bound, not a complete total. Unknown providers stay visible even when other providers have usable numbers.
- Configured hooks or a CLI smoke test do not establish that the editor delivered events. A metadata fallback does not establish full historical coverage. Tab completion, cloud agents and CLI runs without confirmed collection remain outside the measurement.

Keep run identifiers pseudonymous and stable for deduplication. Do not request or copy prompts, responses, reasoning, tool output, credentials, personal project names or absolute home paths to calculate duration. Pseudonymous metadata can still be sensitive and stays private. Do not repurpose a transcript-content collector as a metadata-only collector.

## Build the week

1. Create a compact evidence ledger: date/window, source ID, episode, what it supports, duration basis, and unresolved gaps. Label facts, self-reports, interpretations, and proposals separately. Give supplied records stable local IDs if they lack them; those IDs do not create external verification.
2. Deduplicate the same event across diary, activity summary, and outcome report. A completed GoR decision can be included as a decision; it does not prove the matching action happened. Paused reflections and suggested actions are not completed decisions. Do not count a decision twice when several exports repeat its ID.
3. For learning-oriented reviews, offer or use these five lenses unless the user specified another framework:
   - **Encounter a source:** direct contact with material the user considers relevant. Do not decide which teachings are authoritative for them.
   - **Work toward understanding:** questions, explanations in their own words, source checks, objections, and actual review. Agent processing alone does not qualify.
   - **Apply to yourself:** an actually attempted practice, reflection, or action. Separate insight, decision, attempt, and reported outcome.
   - **Apply with people who requested it:** distinguish direct interaction (`live`) from preparation, content, administration, and infrastructure (`support`). Preparation is not time spent in conversation.
   - **Apply in life situations:** observed episodes plus the person's own account of their response. Preserve missing duration and unknown internal experience.
4. Make a day-by-day map, including uncovered days. An interval can support multiple lenses, but its minutes count only once in total elapsed time. Overlapping lens totals are not additive. Keep estimates as ranges, unknowns as unknowns, and frequencies distinct from minutes. Never import a private default such as “one check-in = five minutes” or “one broadcast = one hour.” Apply an estimated convention only if the user explicitly chose it and label it as an estimate.
5. Compare against goals or time targets only when supplied or confirmed by the user. Otherwise describe patterns without inventing a hierarchy, target, deficit, or duty. Partial coverage cannot support a full-week time percentage. A low count may reflect missing evidence, not lack of practice.
6. Before finalizing, ask one compact question only about specific unresolved windows or contradictions that materially affect the review. Do not ask again about recorded offline events. If the user declines or has no answer, keep the gap; if the sources suffice, skip the question.

## Interpret without overclaiming

For each important pattern, show the supporting episodes and at least one plausible alternative when evidence is weak. Distinguish time spent, an artifact produced, a choice made, and an effect observed. A recurring interpretation is a hypothesis, not an established cause. A meaningful change can be small, unfinished, or a decision to stop.

Optional personal lenses—attention, responsibility, vitality, spiritual language, relationships, or humor—come from the user. Use their meanings and explicit reports; do not assign a spiritual grade or introduce a roast unless invited. Do not equate a five-lens framework with five obligations for every day.

## Deliver

Start with a brief human account of the week: the strongest supported connection, a useful contrast, and the main limit of the evidence. For a deep review, provide a detailed Markdown artifact with:

- a daily five-lens table (or the user's chosen lenses), source references, and coverage;
- source → understanding → application for the meaningful episodes;
- observed results and open decisions, keeping people-facing live/support work separate;
- human time estimates or counts with overlap handling, and comparison to supplied targets only;
- when supplied, a separate Codex/Cursor machine-time row with known subtotal, union wall time only if evidenced, and coverage by day;
- recurring helpful patterns and distractions, including counterexamples;
- confidence limits: supported, approximate, self-reported, and unknown;
- **one small proposed experiment** grounded in this week, with a way to observe the outcome.

Offer the experiment as a choice, not a new task already accepted. No response means unknown. If a visual is useful and the environment supports it, show a compact overview alongside the detailed artifact. Otherwise a readable table is sufficient; do not require an external visualization service. Never chart unknown inner experience as invented hours.

Persist only to the user's requested destination. Do not update goals, create calendar events, send a report, or schedule next week's review unless separately authorized. End by distinguishing what the review established from what remains to be tried.
