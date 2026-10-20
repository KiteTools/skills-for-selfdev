# Cursor and Codex in evening and weekly reviews

**English** · [Русский](agent-time-retrospectives.ru.md)

**See what you did, what you delegated, and which results you actually reviewed.** Agent duration adds context to a day; it does not establish personal effort, understanding or success. The evening review keeps these separate, and the weekly review also makes coverage gaps visible.

## Supply selected evidence

Your notes and selected results are sufficient. Optional machine-time input is a reviewed summary containing dates, timezone, separate Codex/Cursor durations and coverage. If individual runs are available, use pseudonymous IDs, start/end timestamps, root-run status and completion evidence. Prompt bodies, responses and tool output are unnecessary for measuring duration.

Keep source summaries private. Pseudonymous IDs and timing can still be sensitive. Do not publish editor databases, personal project names, conversation contents, keys or home paths.

## Interpret the numbers

| Measure | Meaning |
| --- | --- |
| Human time | Evidenced or explicitly self-reported activities with overlapping intervals counted once |
| Codex / Cursor runtime | Sum of completed root-run durations per provider; parallel runs may overlap |
| Machine union wall time | Time covered by at least one known run, rather than the sum of concurrent runs |
| Known machine subtotal | Available provider runtimes added once, with incomplete coverage disclosed |
| Results and understanding | Reviewed artifacts, tests, observed outcomes and the person's account; not inferred from runtime |

Runtime includes tool and approval waits inside the interval. It is not GPU time, cost or human hours. A foreground Cursor window is not proof of a running agent.

Prefer matched request-start and completed-stop events. A read-only metadata summary spanning request to final assistant message is a partial fallback. `turnDurationMs` may cover only the final work segment, not the full run. Conversation age is not runtime. Missing boundaries or completion leave a run untimed.

Deduplicate the same run observed in hooks and metadata, and exclude child-agent runs from root accounting. Missing means unknown, not zero. A successful CLI test does not prove GUI hook delivery. Tab completion, cloud agents and CLI runs without verified collection remain outside the source's coverage.

## Evening review

Start with human activities and verified results, then show machine time separately. Ask only about meaningful gaps after examining the evidence. Do not treat a large runtime as success, a small one as failure or unavailable Cursor data as inactivity. Evening Ten may use reviewed artifacts to suggest a possibility; runtime alone is not evidence of growth or a reason to assign more work.

## Weekly review

Account for every requested local date, including dates without evening snapshots. Refresh closed dates only through an already authorized, available collector. Otherwise use the supplied summaries and disclose their coverage.

A fresh provider summary replaces that provider's value for that date; recalculate the combined subtotal afterward. Never add Cursor again to a total already containing it. Human/device measurements stay intact. For legacy `agent_time_context` snapshots with schema 1–3, `agent_runtime_min` meant Codex only; do not assume this for other export formats without checking their contracts.

Show observed days, partial days and unavailable dates by provider. A valid zero from a selected export is not proof of full-day observation. Do not extrapolate missing days from averages. Respect the user's timezone and daylight-saving boundaries when clipping intervals.

## Entirely fictional example

The selected week is April 15–21, 2030, UTC. No real diary data is used.

- April 15: Codex 09:00–09:30; Cursor 09:10–09:30. A duplicate observation of the Cursor run is removed. Its child run at 09:15–09:20 is not added. Cursor coverage is partial.
- A separate human report records review of the result at 09:20–09:35: 15 minutes. Agent time is not added to that review.
- April 16: Codex has a completed 20-minute run; Cursor is unknown.
- No summaries exist for the other five dates.

April 15's known machine runtime is **50 minutes: Codex 30, Cursor ≥20; union wall time 30 minutes**. The person's known review time remains 15 minutes separately.

The week's known machine subtotal is **≥70 minutes: Codex 50 across 2/7 dates; Cursor ≥20 across 1/7 dates, that date partial**. This is neither full-week coverage nor a measure of understanding. If fresh Cursor evidence revises April 15 to 25 minutes, the subtotal becomes 75, not 95.

## Ask your agent

> Review these day or week notes with my supplied Codex and Cursor summaries. Keep human time, machine time, reviewed output and understanding separate. Handle duplicates, partial coverage and corrections. Show missing dates. Do not inspect editor history or install collectors without a separate request.

## What ships

Collection 0.3.3 updates weekly-review instructions, the daily assistant's operator rules and Evening Ten's evidence handling. **No Cursor collector, SQLite reader, hook installer or automatic Telegram machine-summary import is included.** The existing optional Codex transcript integration reads content; it is not metadata-only collection.

A GitHub update does not change an existing assistant installation. Compare new operator rules with the private `AGENTS.md`, preserve personal settings and merge only the intended additions. Updating instructions does not alter live OpenClaw jobs or schedules.

[Weekly review](../skills/weekly-review.md) · [Evening assistant](../skills/personal-daily-assistant.md) · [Evening Ten](../skills/evening-ten.md) · [Cross-device review](../skills/cross-device-day-review.md)
