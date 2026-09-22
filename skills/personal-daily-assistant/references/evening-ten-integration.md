# Evening Ten: preparation, import, delivery, and response

This is the v0.2.0 bridge from the standalone [Evening Ten skill](https://github.com/KiteTools/skills-for-selfdev/blob/main/skills/evening-ten/SKILL.md) to the Telegram runtime. The standalone skill prepares a reviewable selection from authorized material. The runtime validates and stores a prepared record, delivers it when enabled, and records explicit responses. It does not collect the day, call a model, or generate ten ideas by itself.

The owner enables delivery once during setup. A new manual approval is **not** required every evening: a person or the preparing agent can perform the preparation review. The importer's structural checks do not establish semantic quality.

## 1. Prepare a complete selection

Use the standalone [evidence and selection contract](https://github.com/KiteTools/skills-for-selfdev/blob/main/skills/evening-ten/references/evidence-contract.md). A full working record has `day_threads`, `day_summary`, `alignment`, twenty `candidates`, ten ordered `selected` IDs, and `checks`. This bridge retains those working fields and adds:

| Field | Bridge requirement |
| --- | --- |
| `schema_version` | Integer `1` |
| `date` | The evidence's local date, `YYYY-MM-DD`; never silently substitute today's date |
| `timezone` | A valid IANA name exactly matching the importer's configured timezone, for example `UTC` |
| `source_manifest` | Exactly `evidence_ids` and `goal_ids`: arrays of unique stable IDs, without raw source bodies |
| `checks.preparation_reviewed` | `true` after the preparing person or agent checks meaning, fit, grounding, novelty, and optional tone |

A full twenty-candidate [fictional schema example](../assets/templates/prepared-ten.schema-example.json) is bundled. Its `preparation_reviewed` flag is deliberately `false`: replace the educational content with the authorized day and complete the quality review before importing it. It is not a ready-to-deliver list.

Keep `checks.history_available` truthful and `checks.coverage_complete_for_supplied_input: true` only if all the supplied input was covered. That flag describes supplied material, not a claim that every hour of the day was observed. The three check fields are exactly `history_available`, `coverage_complete_for_supplied_input`, and `preparation_reviewed`.

A candidate keeps the standalone fields: `id`, `text`, `goal_id`, `evidence_ids`, `thread_id`, `move_type`, `mechanism`, and `exploratory`; a returning idea additionally uses `repeat_of` and `changed_basis_ids`. A goal-only opportunity cites `goal:<id>` and has `thread_id: null`; it does not invent an event. A returning idea names the stored prior selection as `YYYY-MM-DD:<candidate-id>` and cites what changed in current evidence.

The importer checks twenty distinct candidates, ten distinct selected IDs, known references, coverage of supplied evidence and substantive threads, at least four selected move types, and at least three exploratory selections. It checks exact text repeats against stored selections from the previous fourteen days; semantic novelty remains the preparing actor's responsibility. Stored history requires a history check, not a claim that history was unavailable.

Text limits are 650 characters for `day_summary`, 450 for non-null `alignment`, 120 for a thread title, 220 for candidate `text`, 80 for `move_type`, and 240 for `mechanism`. IDs use letters, digits, `_`, `.`, `:`, or `-`, at most 80 characters. The entire prepared file must be at most 100 KB. These constraints support delivery; they do not justify truncating the source day or padding a weak selection.

If evidence cannot support a full, non-repetitive Ten, keep the standalone result as an explicitly partial draft. It is not accepted as a delivery package. Do not fabricate candidates just to pass validation.

### Export prompt

Give this to the assistant preparing the selection, with only the material and recent history you authorize it to read:

```text
Use $evening-ten and its references/evidence-contract.md for the supplied local day.
Prepare all day threads, 20 distinct candidates, and 10 selected candidate IDs
in their intended delivery order. Preserve the supplied date and timezone.

Export the full working selection as one UTF-8 JSON object for the Personal Daily
Assistant v0.2.0 bridge. Keep day_threads, day_summary, alignment, candidates,
selected, and checks. Add schema_version: 1, date, timezone, and source_manifest
containing exactly evidence_ids and goal_ids. Include no raw journal bodies,
private filenames, or extra top-level fields. Source IDs must resolve to the
material I supplied; don't invent observations or goals.

Review grounding, meaning, distinctness, topic coverage, prior suggestions when
available, and whether each possibility leaves me free to decline. Only after
that review set checks.preparation_reviewed to true. Keep history_available
truthful and coverage_complete_for_supplied_input true only when warranted.
If a full package is unsupported, report the limitation instead of marking it ready.

Write the JSON to the private output file I selected. Do not send it, create tasks,
or collect additional sources. I will import it into the configured runtime.
```

The last sentence can be adapted for an already authorized preparation/import automation. Authorization to prepare and import does not itself authorize a new source collector. A future date in an example is a placeholder, not permission to invent that day's evidence.

## 2. Import into the installed runtime

Replace the example absolute paths with your actual installed workspace, private data directory, and reviewed UTF-8 JSON file. Use the same timezone as the installation:

```sh
python3 /abs/installed/scripts/evening_ten.py --data-dir /abs/private --timezone UTC ingest --prepared /abs/reviewed.json
```

`/abs/installed` is the installation root containing `scripts/evening_ten.py`, not the public skill source folder. The importer takes a file path, not private text in command arguments. It does not send a message. Results include `saved`, `already_saved`, or `invalid` with a reason.

The record is stored under `<data-dir>/evening-ten/YYYY-MM-DD.json` with private permissions. The order of `selected` determines numbers 1–10. Once saved, that date's preparation and numbering are immutable: importing the identical record is harmless; a different record for the same date is refused. Fix and review a draft **before** its first import. No replacement command is provided.

Only source IDs enter the manifest, but summaries and ideas can still contain personal information. Keep the prepared file and store private. Do not put them into public examples, issues, or logs.

## 3. Enable the two-stage evening once

Pass `--enable-evening-ten` to the public installer or upgrade helper. Without it, the default seven declarations remain, including the 22:00 evening review. With it, the declarations contain eight jobs: a Ten at 22:00 and the evening review at 22:10, in the configured timezone; the other jobs stay in place.

Installation writes declarations and an OpenClaw fragment. It does not activate jobs or deliver messages by itself. Review and register them using the installed OpenClaw version. For an upgrade, remove/replace the old `personal-daily-evening-2200` job: do not keep it alongside `personal-daily-ten-2200` and `personal-daily-evening-2210`. Keep one effective schedule per declaration key.

The scheduled `ten` job dispatches only the stored record for the current local date. With no record it returns `no_data` and sends nothing. It does not borrow yesterday's list, invoke an AI model, or question the user about missing preparation. The 22:10 review remains usable even when no Ten was prepared.

Delivery persists its attempt before sending. A confirmed transport message ID marks `delivered`; an exception or unknown transport response leaves delivery uncertain. An uncertain attempt blocks automatic repeat delivery. Check the actual chat and stored attempt before any operator repair; there is no reconciliation/reset CLI in this release. Do not delete the record to force a resend. A recorded transport message ID is not evidence that the owner read the message.

## 4. Respond explicitly in Telegram

The command language is Russian. The parser does not route a bare `2` or `2,4` to the Ten; those replies can belong to another dialogue. Use a space after the command.

```text
/ход 2,4
```

This means **interested**, not chosen, attempted, completed, or a new task. It applies only to today's confirmed delivered Ten and only within two hours of delivery. For older dates, or an explicit state, use:

```text
/десятка 2030-04-09 интерес 2,4
/десятка 2030-04-09 выбран 2: I choose to try this when the situation occurs.
/десятка 2030-04-09 попробовал 2: I asked for one concrete example.
/десятка 2030-04-09 результат 2: We found that the instructions were missing a condition.
/десятка 2030-04-09 выполнено 2: I completed the small action I had chosen.
/десятка 2030-04-09 неподходит 4: It does not fit my current situation.
```

The dates and notes above are fictional syntax examples. Replace the date with an actually delivered list. Notes can be in your language.

| Russian action | Recorded meaning |
| --- | --- |
| `интерес` | `interested`: noticed an appealing possibility |
| `выбран` | `chosen`: explicitly chose it; action not yet established |
| `попробовал` | `attempted`: describes an attempted action |
| `результат` | `reported_outcome`: the person's report of what happened |
| `выполнено` | `completed`: explicit self-report of completing the chosen action, without independent verification |
| `неподходит` | `did_not_fit`: did not fit; no pressure to try it |

`попробовал`, `результат`, and `выполнено` require a descriptive note after `:`. Numbers must be distinct and between 1 and 10. Feedback requires a confirmed delivered record for the date. Reprocessing the same transport message ID is idempotent; a different command with the same ID is refused.

No action in this table creates or closes a catalog task or automatically records a success. `completed` is a feedback label, not objective proof. Silence is unknown. Retained feedback can inform later preparation only when supplied or authorized as a source for that run.

## 5. Ideas and explicitly reported work sessions

The ordinary idea dialogue offers `обсудить` (discuss), `оставить` (keep without action), or `пропустить` (skip for now). An idea need not become an artifact, a 15–30 minute assignment, or a task.

The separate work-session commands record the owner's explicit account:

```text
/занятие начало Draft a fictional example
/занятие конец Wrote and checked one fictional example
/занятие отложить Waiting for a missing source
/занятие пропустить No longer relevant today
```

These are syntax alternatives, not one sequence: start a session, then choose one of finish, postpone, or skip. Only one explicitly started session can be active; finish/postpone/skip is refused without one. Text after the action is required and limited to 2,000 characters. Timestamps record when the owner reports the event, not independently observed work.

They are start/finish/decision reports, not automatic timers or evidence of activity between messages. A reported finish does not complete a catalog task. Do not infer minutes, attention, productivity, or task acceptance from a scheduled message or a gap between commands.

## 6. Upgrade without replacing private history

The helper stages a new installation beside the old one. It preserves the existing journal/state directory and copies the existing context into the new workspace. It keeps the former AGENTS file as `setup/previous-AGENTS.md` for review; it does not automatically merge every local customization or change the live OpenClaw configuration/schedules.

From the public repository root, first inspect the plan:

```sh
python3 skills/personal-daily-assistant/scripts/upgrade.py --source-project /abs/old-installed --new-project /abs/new-installed --openclaw-config /abs/private/openclaw.json --enable-evening-ten
```

Use a new, nonexisting sibling destination, not a folder inside the old installation. The dry run can happen while the old installation is running. **Before `--apply`, stop every old job, Telegram ingress, and context writer**, then back up private data and the effective configuration. Keep all writers stopped while staging and switching: the same command with `--apply` copies the personalized context into the new workspace. Review preserved instructions, switch the plugin path, replace schedule keys, and verify before resuming. Never run both installations simultaneously against the shared state. If the old context changed after staging, stage again into another fresh destination after stopping writers; do not switch to the stale copy.

This is a bounded public adaptation of the August runtime with selected September mechanics, not a clone of the latest private assistant. The package targets macOS/Linux with POSIX permissions and file locks. WSL is expected to provide those primitives but has not been verified; native Windows is unsupported. Local tests do not establish compatibility with every OpenClaw release or prove live Telegram delivery.
