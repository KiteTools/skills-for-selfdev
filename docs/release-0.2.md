# What changed in 0.2.0

**English** · [Русский](release-0.2.ru.md)

- The home page and catalog now offer two entries: one practice or a personal system.
- The [system map](system-map.md) follows a fictional example and separates suggestion, interest, choice and outcome.
- New standalone skills: [Personal Codex Assistant](skills/personal-codex-assistant.md), [Weekly Review](skills/weekly-review.md), and [GoR Reflection](skills/reflect-on-reaction.md).
- New skills include English and Russian visitor guides, clean templates where needed, and fictional examples.
- Disco now uses the current atlas of 24 original illustrations instead of the generic reflection image.
- [Personal Daily Assistant](skills/personal-daily-assistant.md) is updated separately from Codex context; its guide identifies supported scenarios and migration steps.

## Daily Assistant changes

Evening Ten imports a separately prepared JSON record, retains immutable numbering, and delivers only when enabled. The journal retrospective then moves to 22:10; without this option, the previous evening schedule remains. This bridge does not include an automatic generator or activity collector.

Feedback separates interest, choice, attempts and reported outcomes. An interesting idea creates no task. Work-session commands record explicit starts, finishes, postponements or skips. Updates stage into a sibling workspace while preserving data; stop previous writers before applying. Private-file installation now rejects symlink destinations.

## Updating

Preserve your existing installed skill directory and review your customizations first. The collection installer intentionally refuses to overwrite skills. Replacing instructions does not automatically update a running application, OpenClaw configuration or schedule. Do not replace personal context with a blank template.

Codex context and Daily Assistant use different local data contracts. Combine selected records with an explicit source of truth; do not let two processes independently overwrite one file. The system map does not promise automatic synchronization.

[Validation and limits](validation.md) · [Home](../README.md)
