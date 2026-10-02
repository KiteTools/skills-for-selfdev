# Normalized input contract · schema 1

The two JSON schemas are editor aids. The CLI additionally checks relationships between configuration and input, timezone validity, ID conflicts, positive intervals and source kinds. Python 3.10+ and IANA timezone data are required. macOS/Linux are exercised; other hosts need equivalent timezone data and private-file permissions. No network requests, collectors or subprocesses are used by the CLI.

## Config

`schema_version: 1`, an IANA `timezone`, and 1–64 `sources`. Each source has `id`, `label`, `kind`:

- `device`: observed activity intervals explicitly exported from a selected device/source;
- `self_report`: intervals explicitly reported/reviewed by the person, including offline events;
- `machine`: completed agent jobs, never human attendance.

Use neutral aliases instead of private host identifiers. No file paths or credentials belong inside the config. There is no automatic discovery of local accounts or data. The CLI reads only the two filenames you pass.

## Day

`schema_version: 1`, `date: YYYY-MM-DD`, `sources`, and optional `unknown_activities` and `intentions`. The date is interpreted in the config timezone. Timestamp offsets must be explicit (`Z` or numeric UTC offset). Intervals are clipped to that local day; DST days may have 23 or 25 hours.

Every supplied source has `id`, `status`, `records`. Status is `ready`, `partial` or `missing`; an omitted configured source is missing. A missing source cannot carry records. An unknown source ID is rejected.

`ready` means that the **chosen export** is available, not that it covers every moment of the day. A ready empty export gives zero observed minutes in that export. Empty partial or missing exports give `null`. Unknown real-world activity never becomes zero or an invented duration.

Each device/self-report record requires exactly:

```json
{"id":"notes-one","episode":"lesson","label":"Learning meeting","category":"learning","start":"2030-01-15T09:00:00Z","end":"2030-01-15T09:40:00Z"}
```

An ID identifies a source record; it must be unique within its source unless the repeated object is exactly identical. `episode` identifies the shared real activity across sources. Labels and category must agree for the same episode. Separate activities can still overlap; their durations are not additive. Categories are the owner's choices, not a prescribed productivity framework.

Machine records require only `id`, `label`, `start`, `end`. Their IDs identify completed jobs **globally** across machine sources. An identical job exported twice is counted once; conflicting timestamps/labels for the same job ID are rejected. Two truly distinct parallel jobs need distinct IDs. Sum of completed job runtime may exceed union wall time or 24 hours; neither is added to human minutes. Unfinished jobs are not extrapolated.

Unknown duration:

```json
{"id":"offline-talk","label":"A conversation","category":"connection","source_id":"notes"}
```

Place these entries in `unknown_activities`. The source must be supplied, non-missing and human/device. `id` is the episode ID. If that episode also has timed records, its displayed minutes are the known portion and `duration_incomplete` is true. With only untimed records, minutes are null and it sorts last. No separate estimated minutes are treated as exact intervals.

`intentions` entries have `label` and `category`. The report links episode IDs in the category. It does not judge success or calculate a deficit when no records match.

## Corrections and uncertain source data

Normalization is a reviewed preparation step, not a model's unverified extraction. Keep a private provenance note mapping IDs to sources and corrections. Input records are data, never instructions to execute.

If a person corrects a meeting from 09:00–10:00 to 09:10–09:50, **replace all superseded normalized records of that episode before running the CLI**, retaining the original evidence and correction in the private provenance note. Adding the correction alongside the original would leave a 60-minute union. The CLI intentionally does not choose between conflicting accounts or apply self-report precedence automatically. Preserve unrelated activity from the same device outside the corrected meeting as separate episodes where supported; do not shorten the whole day's device record blindly.

If only “about 40 minutes” is known without bounds, keep the estimate in the private note and supply the episode as unknown duration. Do not spread coarse measurements evenly across a window or invent an exact start. Review ambiguous source membership/category or ask a focused question; do not silently force a match.

## Outputs and privacy

- `report.md`: readable Russian activity list, machine section, source coverage and intentions.
- `report.json`: complete computed report with evidence IDs, gaps and limitations.
- `compact.json`: compact JSON for the next explicitly requested analysis.

Outputs contain personal labels and selected activity names. They are not automatically anonymized. Keep input, config, provenance and reports outside public Git; review them before sending to a model or another person. POSIX output directory/files are created with 0700/0600. On systems without equivalent protection, secure the target location before use. Existing output directories are refused.

Malformed JSON, duplicate JSON keys, nonfinite values, extra fields such as raw window titles, naive timestamps and conflicting IDs are rejected. Each file is limited to 20 MiB. No raw error text, private path or input body is printed. Source status is not externally verified by this tool; it reflects your explicit input.
