# Evidence and selection contract

Plain-language input is acceptable. Give each supplied source a stable ID without exposing private filenames. For automation or reproducible review, use this shape:

```json
{
  "date": "2030-04-09",
  "timezone": "Etc/UTC",
  "coverage": {"scope_start": "09:00", "scope_end": "18:00", "gaps": ["Offline afternoon not recorded"]},
  "goals": [{"id": "g1", "text": "A goal explicitly stated by the user"}],
  "evidence": [{"id": "e1", "source": "explicit_journal", "text": "The user's supplied account", "scope_start": "09:00", "scope_end": "10:00"}],
  "recent_tens": [],
  "feedback": []
}
```

Dates above are format examples, not a current-day default. Goal descriptions should retain why the goal matters and what the user considers sufficient, when provided. Do not substitute reach, status, or quantity for those criteria.

## Working selection record

Use this structure when a structured deliverable is requested. Do not expose private journal bodies through process arguments or publish the record.

```json
{
  "day_threads": [{"id": "t1", "title": "A concrete activity", "substantive": true, "evidence_ids": ["e1"]}],
  "day_summary": "Observed activity; coverage limits remain explicit.",
  "alignment": null,
  "candidates": [
    {"id": "c1", "text": "A specific opportunity", "goal_id": "g1", "evidence_ids": ["e1"], "thread_id": "t1", "move_type": "reduce scope", "mechanism": "Why this connection may help", "exploratory": true}
  ],
  "selected": ["c1"],
  "checks": {"history_available": false, "coverage_complete_for_supplied_input": true}
}
```

This is a shape illustration, not a valid full Ten. A full package has twenty candidate objects and ten distinct selected IDs. `goal_id` can be null when no goal was supplied. `alignment` can be null for the same reason. Goal-only candidates use `thread_id: null` and only known `goal:` references. Returning ideas additionally include `repeat_of` and `changed_basis_ids` that resolve to current evidence; their text explains what changed.

## Review before delivery

- Every evidence ID belongs to the day map, including non-substantive entries.
- Every cited ID exists. Claims about completion are supported by an explicit result, not an application window title.
- Selection has twenty distinct candidates, ten distinct selections, four move types, and three exploratory selections, or is explicitly marked partial.
- Topic coverage meets the rule for the number of substantive threads.
- Items are concise, understandable without opening notes, and different in meaning.
- History and observation gaps are stated accurately. Missing activity is not invented.
- The list is optional; none of its proposals has been executed by generating it.
