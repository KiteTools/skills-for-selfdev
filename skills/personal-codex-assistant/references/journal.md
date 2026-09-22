# Optional private journal

Append one JSON object per line to the configured file after an explicit user response. Use UTF-8. Do not initialize the journal with sample entries. Keep the original answer in `text`; `rating` is one of `--`, `-`, `=`, `+`, `++`, or null. Normalize explicit Unicode minus signs to ASCII only in the machine field. `--` is the machine representation of `−−`, not an inferred stronger negative sentiment.

Fields:

- `id`: newly generated UUID for this event; retain it during a retry.
- `recorded_at`: current ISO timestamp with timezone offset, obtained from the clock, never guessed.
- `type`: `vitality_response` or `correction`.
- `task_id`: the actual catalog ID, or null when the work has no catalog entry.
- `result`: short description of the confirmed result; avoid unnecessary sensitive detail.
- `rating`: the user's explicit rating or null.
- `text`: the user's own response, preserving “nothing” as a meaningful answer.
- `supersedes`: earlier event ID for a correction, otherwise null.

Before retrying an uncertain write, read the recent tail and look for the same event ID and answer associated with this exchange. Append once; do not count a duplicate. A user may give identical text for separate tasks, so text alone is not an identity. Corrections append a new event referencing the old ID; do not silently rewrite history or remove a reported negative experience. In a requested report, use the latest correction for the effective value and retain the original provenance.

This instruction-based journal assumes one active writer. If another process writes it concurrently, pause journal writes until there is a single writer or an explicitly configured lock-aware writer. Do not claim cross-process transactions, crash recovery or synchronization. If writing fails, keep the answer available in the conversation and report that it was not saved; never claim persistence from intent alone.
