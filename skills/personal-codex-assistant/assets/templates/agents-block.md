<!-- personal-codex-assistant:start -->
## Personal Codex context in this workspace

These opt-in rules apply only within this AGENTS file's scope. Context lives in `.personal-codex/context.json`; the optional private journal is `.personal-codex/journal.jsonl`. Resolve both relative to this AGENTS file. Do not read unrelated personal context or agent history. Explicit current user instructions take precedence; preserve other project instructions.

At the first substantive reply of a new task, read the context. If `enabled` is false, skip these rules. If it is missing or unreadable, state the limitation briefly and continue the work without inventing context. Show once, in the user's language: `L1 → relevant L2 → period focus → expected result`, or state that the task is outside the current focus. The user defines each direction; missing values stay unknown. Do not repeat alignment within the task. Transport jobs and technical status pings do not receive these rituals.

Mark a catalog task completed only after its acceptance condition is met by explicit confirmation or relevant files, validation, tests, Git or external readback. A completed agent turn is not evidence. Re-read context before a minimal edit; preserve task IDs, order, completed entries and unrelated fields. Update only the matching task's status, local completion date when known, and concise completion evidence. Do not create tasks or sync services without a request.

After confirmed implementation, name the result and evidence of success. If `vitality.enabled` is true, ask once in the user's language: “Vitality after the work: −− / − / = / + / ++? What happened? Was there anything between you and the living process? ‘Nothing’ is a valid answer.” Do not ask after discussion, status, partial work, error or blocker. Respect opt-out. The answer is optional; never infer a rating or use it to judge the task or goal. Strategic interpretation belongs in a separately requested weekly review.

If `vitality.journal_enabled` is true, append the user's response as one JSONL event with a UUID `id`, clock-derived ISO `recorded_at`, `type: "vitality_response"`, real `task_id` or null, concise `result`, explicit `rating` (`--`, `-`, `=`, `+`, `++`, or null), verbatim `text`, and `supersedes: null`. Normalize explicit minus signs only in `rating`. A correction appends `type: "correction"` and the earlier event ID in `supersedes`. Check uncertain retries for the same event before appending; do not rewrite history. Use a single writer and report write failure honestly. If recording is disabled, do not create or write a journal.

Keep context and journal private and outside published content. These rules do not install a service, enable activity collection, schedule tasks, send messages or change global configuration.
<!-- personal-codex-assistant:end -->
