# Optional export to Personal Daily Assistant 0.2

Use this only when the user requests a prepared package for an installed Personal Daily Assistant. A normal conversation does not need an export or that application.

Start from the [evidence and selection contract](evidence-contract.md). Produce a full, reviewed selection before packaging it. A partial set remains a conversational result; do not pad it to pass an importer.

The runtime envelope contains exactly these fields:

- `schema_version`: `1`.
- `date`: the requested local day, in ISO format.
- `timezone`: the configured IANA timezone, not an inferred default.
- `source_manifest`: an object with `evidence_ids` and `goal_ids` arrays. Include stable identifiers only, not original transcript bodies or private filenames.
- `day_threads`, `day_summary`, `alignment`, `candidates`, `selected`: the corresponding working-selection fields. Use twenty candidates and ten selected IDs. Keep all evidence represented in the day map, including non-substantive threads.
- `checks`: exactly `history_available`, `coverage_complete_for_supplied_input`, and `preparation_reviewed` booleans. The latter records a completed quality review by the preparing person or agent, not a claim that a human approved it. Do not set it true until the review happened.

The daily runtime checks references, coverage, selection size, move variety, exact duplicates and available stored history. It cannot establish factual truth or semantic novelty. Perform the skill's full review before setting `preparation_reviewed` and keep uncertainty visible in the wording.

If previous Tens are available in the user-designated runtime store, use their selected candidate IDs as `YYYY-MM-DD:candidate-id`. A returning idea needs `repeat_of` plus cited `changed_basis_ids` from current evidence. If history is absent, set `history_available` false. Do not label an inaccessible history checked.

Save only when requested, into the selected private data area. Never put a real prepared Ten in a public repository. The package still contains a personal day summary and proposals even though the original sources are excluded.

From the separately installed runtime workspace, the owner can validate and import:

```sh
python3 scripts/evening_ten.py --data-dir /path/to/private-data --timezone Etc/UTC ingest --prepared /path/to/private/prepared-ten.json
```

Replace the example timezone with the actual configured one. Import does not send a message or activate a schedule. Delivery requires the runtime's explicit setup. Do not install or activate that integration just because an export was requested. An import error leaves the conversation's useful result available; report the exact validation issue instead of silently changing its meaning to satisfy the schema.
