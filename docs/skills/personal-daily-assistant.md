# Personal Daily Assistant: a daily rhythm that keeps your context

[English](personal-daily-assistant.md) · [Русский](personal-daily-assistant.ru.md)

![Illustration of the rhythm workflow](../../assets/rhythm.png)

Choose a meaningful next step in the morning, capture ideas and small successes during the day, then reflect on what happened. This package brings that rhythm to a private, text-based Telegram assistant powered by OpenClaw.

**Try it:**

> Use personal-daily-assistant to inspect my setup and prepare a private installation plan. Use my chosen direction, focus, and daily questions. Show the dry run before activating schedules. Explain the optional Evening Ten bridge.

## What it does

| Moment | Experience |
| --- | --- |
| Morning | A personal question, the current focus, and a choice of next steps |
| During the day | Vitality check-ins; capture an idea or success; explicitly report starting, finishing, postponing, or skipping a work session |
| Optional 22:00 Ten | Deliver a previously prepared and reviewed list of ten possibilities; save interest or later feedback against its stable numbers |
| Evening | Reflect on available evidence and unfinished ideas; discuss, keep, or skip an idea without a compulsory task |
| Weekly | Review successes, recurring patterns, and the person's own assessment |

Vitality is the person's reported experience, not an assigned score. A completed agent turn or a reported work-session finish does not automatically close a life task. Ideas need not become a 15–30 minute assignment or a material result.

## Version 0.2.0: a bridge to Evening Ten

The standalone [Evening Ten skill](evening-ten.md) prepares the selection from material you authorize. The daily runtime **imports, stores, delivers, and records feedback**; it does not generate a list or collect the day's sources. A preparing person or agent reviews meaning and quality before import. Once the owner enables delivery, no additional manual approval is required every day.

The [complete integration reference](../../skills/personal-daily-assistant/references/evening-ten-integration.md) supplies an export prompt, the exact JSON wrapper, import command, schedule switch, and response rules. For example, with your actual private paths:

```sh
python3 /abs/installed/scripts/evening_ten.py --data-dir /abs/private --timezone UTC ingest --prepared /abs/reviewed.json
```

The date's saved numbering is immutable. No prepared record means `no_data` and no message. Uncertain delivery blocks an automatic repeat; inspect the actual chat before operator reconciliation. There is no reconciliation/reset CLI in this release.

In Telegram:

```text
/ход 2,4
/десятка 2030-04-09 результат 2: I tried it and discovered a missing requirement.
```

`/ход 2,4` records **interest** in today's confirmed delivered list within two hours. It does not create a task. A dated `/десятка` command supports `интерес`, `выбран`, `попробовал`, `результат`, `выполнено`, and `неподходит`; attempted/outcome/completed require a descriptive note. `выполнено` is explicit self-report, not independently verified success or catalog completion. Bare numbers do not route to the Ten. The example date is fictional.

## What is included and required

The package includes a Python journal/dialogue runtime, an OpenClaw transport plugin, blank context templates, dry-run installation and checking, a side-by-side upgrade helper, and tests for the shipped behavior. It is a **bounded public adaptation of the August 2026 runtime with selected September mechanics**, not the latest private assistant. Dialogue commands remain primarily **Russian**; full English dialogue localization is not included.

Use macOS/Linux, Python 3.10+, Node.js, compatible OpenClaw, your Telegram bot, a private token file, the owner's numeric Telegram ID, an IANA timezone, and a private workspace. POSIX file locks and permissions are required. WSL is expected to provide them but is untested; native Windows is unsupported. The package does not provision OpenClaw or guarantee compatibility with every release.

The separate [Personal Codex Assistant](personal-codex-assistant.md) and [Weekly Review](weekly-review.md) work on demand without this Telegram runtime.

## Install and upgrade deliberately

1. Personalize [the context template](../../skills/personal-daily-assistant/assets/templates/active_context.json), replacing every `REPLACE_WITH_YOUR_` value with your chosen meanings. Read [the installation contract](../../skills/personal-daily-assistant/references/installation-contract.md).
2. Inspect `python3 skills/personal-daily-assistant/scripts/install.py --help` and run a plan with explicit private paths. Without `--apply`, the installer only validates and prints the plan. Keep the bot token in an owner-only file, never a prompt or command argument.
3. Apply only to the intended fresh directory. This writes local files and declarations; it does not activate OpenClaw or start messaging. Back up the effective configuration, integrate the fragment for your OpenClaw release, and register schedules once.
4. Run the checker and tests, then an authorized private text-message check. Verify both the delivered reply and stored event. Deletion of technical messages and thread archiving remain off by default.

By default there are **seven schedule declarations**: context refresh at 03:00, morning at 08:00, check-ins at 12:00 / 15:10 / 18:00, evening at 22:00, and weekly review Sunday at 20:00. All use your timezone. Opt in with `--enable-evening-ten` to replace the 22:00 review with **Ten at 22:00 and review at 22:10**, making eight declarations. This switch does not configure preparation or source collection.

For an existing portable installation, `scripts/upgrade.py` stages a new sibling workspace, preserves journal/state and context, and leaves live configuration and schedules untouched. The dry run may happen first; before `--apply`, stop every old job, ingress, and context writer, back up private data/configuration, and keep them stopped through staging and switching. Review preserved instructions and replace the old 22:00 schedule key rather than adding duplicates. If the old context changed after staging, stage again in another fresh directory. [Exact upgrade procedure](../../skills/personal-daily-assistant/references/evening-ten-integration.md#6-upgrade-without-replacing-private-history).

## Data boundaries

Private context, events, prepared Tens, feedback, activity exports, and summaries stay outside this public checkout. The optional Codex activity integration remains **off by default**. Only enable `PDS_INCLUDE_CODEX_ACTIVITY=1` with an absolute `PDS_CODEX_ACTIVITY_SOURCE_DIR` containing exports you selected and reviewed. It can read message excerpts, titles, working directories, and paths; it is not metadata-only or Computer History. Pattern filters do not guarantee anonymization. [Exact activity boundary](../../skills/personal-daily-assistant/references/installation-contract.md#optional-activity-data).

Telegram and model-assisted work still use the services you configure. Local files do not make those transports offline. The assistant accepts text and inline buttons; it does not transcribe voice attachments. It does not infer activity from a timer: `/занятие начало`, `/занятие конец`, `/занятие отложить`, and `/занятие пропустить` record only what you explicitly report. The integration reference explains their syntax.

## Verification and limits

From the repository root:

```sh
python3 -m unittest discover -s skills/personal-daily-assistant/tests -v
python3 -m unittest discover -s skills/personal-daily-assistant/assets/runtime/tests -v
node --test skills/personal-daily-assistant/assets/runtime/openclaw-plugins/personal-daily-transport/test/*.test.mjs
```

These local tests cover the shipped package. They do not prove live Telegram delivery, an active schedule, WSL support, the semantic quality of every generated Ten, or a lasting personal outcome. Installation and delivery need verification in your own environment.

[Open the skill](../../skills/personal-daily-assistant/SKILL.md) · [Installation contract](../../skills/personal-daily-assistant/references/installation-contract.md) · [Evening Ten integration](../../skills/personal-daily-assistant/references/evening-ten-integration.md) · [System map](../system-map.md) · [Skills for Selfdev](../../README.md)
