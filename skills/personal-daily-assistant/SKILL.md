---
name: personal-daily-assistant
description: Use when installing, configuring, repairing, or verifying a private text-only Telegram daily assistant that runs through OpenClaw and keeps a local vitality journal, goal ladder, daily retrospectives, ideas, successes, and weekly patterns.
---

# OpenClaw Personal Daily Assistant

Portable **v0.3.0** keeps the August 2026 journal/runtime base and adds selected
September mechanics: optional idea discussion, explicit activity reports, and
an optional prepared Evening Ten store/transport. It is a bounded modular
adaptation, **not a copy of the latest private assistant**. The deterministic
Telegram dialogue is primarily Russian. Python 3.10+, Node.js and a compatible
OpenClaw installation are required on macOS/Linux. WSL with a Linux filesystem
is an expected POSIX route but has not been tested; native Windows is unsupported
(`fcntl`, permissions and POSIX paths are required).

Install the bundled deterministic runtime as a private local system. Keep the
conversation useful to one owner; treat journaling and automation as background
infrastructure.

## Workflow

1. Read `references/installation-contract.md` completely.
2. Inspect the host before changing it. Use a new dedicated private project
   directory; the installer copies runtime files and writes its AGENTS.md.
   Back up the OpenClaw configuration before integrating its fragment.
3. Ask only for values that cannot be discovered locally. Never request a raw
   bot token in chat; accept only a path to its private file.
4. Personalize `assets/templates/active_context.json`. Remove every
   `REPLACE_WITH_YOUR_` marker before installation.
5. Run `scripts/install.py --help`, then its default dry-run mode. Review the proposed
   file and schedule changes before applying them.
6. Apply the local installation with `--apply`; it copies the operator rules
   into the dedicated workspace. Separately integrate the config fragment and
   schedules using the installed OpenClaw release's supported interface. An
   installer success does not activate the live bot or scheduler.
7. For an existing portable installation, use the side-by-side upgrade described
   in `references/installation-contract.md`; never apply the installer over it.
8. Run the bundled Python and Node tests, followed by `scripts/verify.py`.
9. Perform one live text-message smoke test in the owner's private Telegram
   chat. Do not report success unless the bot reply and local event readback
   both succeed.

## Morning choice

After the morning questions, ask for the owner’s step in their own words. Keep the numbered catalog behind “Показать задачи”. A free-form intention records `morning_intent` without creating or completing a catalog task. Existing numbers, 0 and task buttons remain supported. Recording an intention does not authorize the agent to execute it.

## Optional mechanics

- `идея:` captures an idea. Evening discussion offers **обсудить / оставить /
  пропустить**; no mandatory 15–30 minute task or automatic promotion follows.
- `/занятие начало <title>`, `/занятие конец <result>`, `/занятие отложить
  <reason>`, `/занятие пропустить <reason>` record explicit reports about one
  active activity. A timestamp is when the owner reported it, not independent
  observation. No timer, schedule or computer window completes an activity.
- Evening Ten is **off by default**. `--enable-evening-ten` prepares 22:00 Ten
  and 22:10 journal-retro declarations; otherwise the ordinary retro stays at
  22:00. Neither option registers jobs or sends a message by itself.
- Read `references/evening-ten-integration.md` for the exact bridge from the
  standalone Evening Ten skill: prepare a record, review it (person or agent),
  validate/import it locally, then deliver only when enabled. No source collection
  or generation is bundled. `interested`, `chosen`, `attempted`, reported outcome
  and self-reported completion remain distinct from tasks and successes.

## Guardrails

- Keep `events.jsonl`, state, reports and rendered views in the configured
  private data directory outside Git.
- Restrict Telegram to the configured owner ID and keep the Gateway on
  loopback.
- Preserve append-only events, idempotency and delivery confirmation.
- Use command jobs for scheduled deterministic messages so routine prompts do
  not invoke a model.
- Accept only Telegram text and inline callbacks. Do not configure attachment
  transcription or audio delivery for this assistant.
- Keep Codex activity collection off unless explicitly requested. Opt-in requires
  `PDS_INCLUDE_CODEX_ACTIVITY=1` and an absolute `PDS_CODEX_ACTIVITY_SOURCE_DIR`
  containing selected, reviewed exports. This reads message text, not only
  metadata, and its compact output may reach Telegram/model context. Never
  describe pattern filtering as guaranteed anonymization.
- Keep this installation focused on the bundled assistant; external integrations require their own configuration and authorization.
- Do not overwrite an existing OpenClaw config without a timestamped backup.
- Keep `technicalCleanupEnabled: false` unless the owner specifically opts in
  to the documented technical-message cleanup and thread archiving.
- Do not schedule messages or send a live test without the owner's request to
  activate the assistant. A request to inspect or plan installation is read-only.

## Verification gate

Run:

```bash
python3 scripts/verify.py --help
```

Then run it with the installed project, data and config paths. Resolve every
failed check before telling the owner that the assistant is ready.
