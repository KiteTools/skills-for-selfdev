---
name: cross-device-day-review
description: Review a supplied day's activity across devices and explicit personal notes using an offline normalized-JSON CLI. Merge overlapping intervals, keep agent machine time separate, preserve gaps, and prepare evidence for reflection; does not collect history or configure tracking services.
---

# Cross-device day review

Help the person see what they actually did, compare it with their chosen focus, and bring a grounded account into an evening conversation or weekly review. Devices are evidence sources, not the purpose of the review. Respond in the person's language; the CLI Markdown renderer is Russian.

## Choose and normalize evidence

Read [the input and normalization contract](references/input.md) before preparing input. Use only supplied files or sources explicitly designated by the owner. Installation does not authorize screen capture, reading live logs, connecting accounts, or sending reports. Do not start services or schedulers.

Create a reviewed normalized JSON in a private directory. Use the [config schema](references/config.schema.json), [input schema](references/input.schema.json) and [synthetic example](examples/day.json). The CLI validates types, IDs, source membership, intervals and conflicts without external dependencies. Raw third-party exports are not accepted directly; read [adapter boundaries](references/adapters.md).

- Preserve observations, explicit self-reports and missing sources separately. An application foreground interval is not continuous attention, learning or task completion.
- Give the same real episode the same `episode`, label and category across sources when evidence supports the match. A background meeting and notes made during it may be one episode; do not infer a meeting from an open tab alone.
- **Apply explicit human corrections before analysis.** Replace the superseded meeting bounds across the normalized records for that episode; do not append a correction as another overlapping interval. Keep provenance and superseded evidence in a separate private note. If a conflict cannot be resolved, ask one concrete question or keep it unresolved outside the timed input. The CLI unions supplied intervals; it does not infer precedence or decide which account is true.
- Do not manufacture exact starts/ends from coarse aggregates, estimates or a summary's coverage window. Use `unknown_activities` for untimed episodes. Keep aggregate measurements in a separate private note; this version does not calculate bounds for aggregate bins.
- Use machine sources only for completed job intervals, with a globally stable job ID; do not include prompt content. Machine runtime and overlapping wall time never become human time.

## Run the offline CLI

From this installed skill directory:

```sh
python3 scripts/day_review.py --config /absolute/private/config.json \
  --input /absolute/private/day.json --output-dir /absolute/private/new-day-report
```

The output parent must exist and the output directory must be new. No overwrites. Python 3.10+ with IANA timezone data is required. Outputs: `report.md`, `report.json`, `compact.json`. A `partial` report is useful evidence with gaps, not a failed run. Exit 2 means invalid input or unavailable output; no private input is printed in errors.

## Make sense of the result together

Begin with the main supported activities, ordered by known duration. Unknown duration stays unknown; an episode with both timed and untimed material shows only its known lower bound. Explain coverage once, then use accurate verbs such as discussed, drafted or tested. Do not repeatedly burden every sentence with completion disclaimers.

Total human/device time is the union across selected device and self-reported intervals. Episode totals and per-source totals can overlap and are not additive. No report proves the whole day was observed, even when every supplied source is ready. Distinguish agent summed runtime from its union wall time; both remain separate from the person's time.

Match activities with intentions only through the user's categories. Absence of evidence is not a missed commitment. Ask about specific meaningful gaps after examining available records. Do not infer vitality, motives or inner understanding. A concise human interpretation is separate from the deterministic report.

Offer the reviewed material to a separately requested weekly review or Evening Ten. Do not write goals, complete tasks, import into a Telegram runtime, or publish the report automatically. Those modules have their own contracts. Personal source labels and activity titles remain private; normalization is not guaranteed anonymization.
