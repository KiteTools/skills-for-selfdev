# Agent rules for the personal daily system

## One owner

This system serves one person. Vitality, work, ideas and results are views of
the same life, not separate scoreboards. The top criterion is whether the owner
wants to live more, while daily deltas remain contextual observations rather
than verdicts on a task or goal.

## Codex task alignment

In the first substantive reply of a new Codex task, read
`context/active_context.md`. Show once:

`L1 → relevant L2 → period focus → expected result`

or state that the task is outside the current focus. Do not repeat alignment in
intermediate replies.

After confirmed implementation, name the result and success, then ask once:

`Vitality after the work: −− / − / = / + / ++? What happened? Was there
anything between you and the living process? “Nothing” is a valid answer.`

Do not ask after discussion, status, a partial result, an error or a blocker.
Store the answer in the local journal. Draw strategic conclusions only during
the weekly retrospective.

## Telegram routing

OpenClaw is the only Telegram transport. The fast plugin handles callbacks,
explicit `идея:` and `успех:` captures, and replies to active personal
dialogues before a model turn.

This assistant accepts text and inline callbacks only. Do not pass attachments
or incoming voice messages through recognition, and do not send audio replies.

Route exact `утро` before pending-state handling. It opens a compact morning
choice for 30 minutes. Accept several task numbers separated by conjunctions,
commas, spaces or newlines; accept standalone `0` for no focus.

If one message both answers a pending dialogue and contains a new independent
request, deliver the deterministic personal-system reply first, then continue
only the independent request. Never route the same text through the state
machine twice.

## Daily cadence

- 08:00: active understanding and morning 1:1 question; then one pattern
  question; then ladder and task choice.
- 10:00: silently expire an unfinished scheduled morning dialogue.
- 12:00, 15:10, 18:00: rotate one affirmation or understanding and ask for a
  vitality delta with inline buttons.
- 22:00: show compact confirmed activity, ask what is missing, calculate the
  total after the answer, ask the evening 1:1 question, offer one
  `Добавить успех` button and offer optional discussion of one idea.
  With Evening Ten explicitly enabled: Ten at 22:00, this journal retro at 22:10.
- Sunday 20:00: show the vitality sum, successes including every `+` and `++`,
  the week's explicitly named mediators and repeated patterns, then ask for the
  owner's final feeling.

Use date only in the first report line and time-only event rows. Merge duplicate
episodes. Do not expose technical metadata, raw model logs, activity windows or
delta distributions.

## Ideas and tasks

Save `идея:` immediately. Offer one optional discussion with «обсудить»,
«оставить» or «пропустить». No reply creates no debt. Do not demand a timed first
step, infer completion from similar text, or automatically create a task from an
idea. A discussion note is the owner's account, not an objective success.
Existing tasks are preserved; changing their status needs explicit authority and
specific supporting evidence. A completed agent turn is not completion evidence.

Evening Ten feedback is separate from the retro pending interaction. `/ход 2,4`
is interest only; dated `/десятка` commands record explicit later decisions and
reports. Never feed those commands through `route-reply` a second time. A
self-reported completion is labeled as such and does not create a task, success
or vitality score. Keep source IDs and proposals distinct from observed facts.

`/занятие` commands record reported starts/ends, postponement and skip for one
activity at a time. Do not infer attendance or completion from time passing.
The finish text can name an incomplete outcome; it ends the reported activity,
not the user's larger goal. These commands leave any pending daily dialogue intact.

## Data and reports

Store append-only events in the private data directory. Corrections supersede
materialized fields without rewriting history. Keep state and delivery
transitions idempotent by Telegram message ID and workflow key.

Codex activity collection is disabled by default. Do not enable it just because
local sessions exist. An explicitly requested setup may set
`PDS_INCLUDE_CODEX_ACTIVITY=1` and `PDS_CODEX_ACTIVITY_SOURCE_DIR` to an absolute
directory of selected, reviewed transcript exports. Read the installation
contract's data boundary first. The helper reads transcript files, including
message text; it is not a metadata-only collector. Its compact output can
contain user requests, assistant responses, titles, paths and tool names.
Pattern filtering cannot guarantee anonymity or removal of secrets. Use copies
that the owner has reviewed for the intended Telegram/model context; never
point the default schedule at the whole local history. Do not copy reasoning,
raw tool output or credentials into reports. Without this opt-in, use journal
entries and explicit owner replies. Ask only what the available context lacks.

At 03:00, check the explicitly configured `PDS_SUMMARIES_DIR` for a newer summary
(or the local `summaries/` folder when no directory was configured). Import only the active understanding,
questions, warning patterns, affirmations and understandings after validation.
Use the prior context if refresh fails. The new context applies the next
morning.

Technical Telegram deletion and Codex thread archiving are disabled by default
(`technicalCleanupEnabled: false`). Enable them only when the owner explicitly
requests that behavior after reviewing the matching rules and cutoff. Preserve
user-created tasks and substantive conversations. Do not run the cleanup helper
manually as part of routine installation.
