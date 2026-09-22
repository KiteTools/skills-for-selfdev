---
name: life-events
description: Build a source-linked timeline of life events from manual entries, notes, or a transcript; preserve unknown dates and the person's own assessment of each episode. Use for personal life-history capture and review before optional Longevity intake.
---

# Life Events

Turn scattered memories into a reviewable event timeline. This is a portable companion inspired by the SOOV manual-entry and transcript workflow, not a copy of the original application or its calculation model.

## Capture

Work from material the user supplied or explicitly selected. Do not search unrelated journals, messages or family records. Ask one useful question at a time when capturing events conversationally.

For each event, record:

- a stable event ID and a short neutral title;
- subject (use a role or pseudonym unless a name is necessary);
- time as stated, start/end age or date if known, and precision: exact, approximate or unknown;
- what happened, separate from what it meant to the person;
- the person's assessment or impact in their own words, or `not stated`;
- a source reference: transcript timestamp, paragraph, note ID or manual entry;
- status: extracted, confirmed or corrected; unresolved questions where relevant.

Do not convert silence into a neutral assessment. Do not assign emotional scores, life-function coefficients, medical causes or family causality. “Around graduation” stays approximate unless the source gives enough information to calculate a date. Attribute hypotheses to their speaker and keep them outside the event facts.

## Review

Merge repeated mentions of the same episode while retaining all source references. If accounts disagree, show the alternatives without picking a winner. Keep different people's experiences distinct even when they describe the same event.

Present a compact chronology, then only the gaps that would change its interpretation. An extracted event is not confirmed merely because the assistant wrote it down. Accept corrections without erasing the earlier source claim.

## Deliver

Return a Markdown timeline; add JSON only if requested or needed for a named destination. A useful table is `When | Event | Reported impact | Source | Status`. Preserve missing information rather than filling every cell with inference.

Use [references/example.md](references/example.md) for a fictional example and the local JSON shape. This shape is not the Longevity API schema. For Longevity, retrieve the target's current manifest, map only reviewed supported fields, show its privacy notice, and submit the minimal structured facts. Never upload the raw transcript to that app.

Save personal output only to the user's chosen private location. The skill itself contains no storage service, account system, automated publishing or background collection.
