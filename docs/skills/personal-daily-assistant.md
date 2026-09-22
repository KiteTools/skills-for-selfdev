# Personal Daily Assistant: a daily rhythm that keeps your context

![Illustration of the rhythm workflow](../../assets/rhythm.png)

Choose a meaningful next step in the morning, capture ideas and small successes during the day, then reflect on what actually happened. This package turns that rhythm into a private, text-based Telegram assistant powered by OpenClaw.

**Try it:**

> Use personal-daily-assistant to inspect my setup and prepare a private installation plan. Help me define my main direction, current focus and daily questions. Show the dry run before activating schedules.

## What it does

| Moment | Experience |
| --- | --- |
| Morning | A personal question, the current focus and a choice of next steps |
| During the day | Short vitality check-ins; capture an idea or success without losing it |
| Evening | Review available activity, fill only the gaps and revisit unfinished ideas |
| Weekly | Review successes, recurring patterns and the person's own assessment |

Vitality is a person's reported experience, not a score that the assistant assigns. A finished agent turn does not automatically mark a life task complete. The journal keeps evidence, interpretation and corrections distinct.

## What is included

- A deterministic Python journal and daily dialogue runtime.
- An OpenClaw transport plugin with idempotent replies and continuation recovery.
- Blank personal-context templates, a dry-run installer and an installation checker.
- Tests for journal behavior, installation, routing, delivery and recovery.

This is a **portable August 2026 snapshot**, adapted for public distribution. It does not claim to be the latest private assistant. The runtime's dialogue and capture commands are primarily **Russian**; visitor documentation is English. Full English dialogue localization is not included.

## Requirements

Use a macOS/Linux machine with Python 3.10+, Node.js and a compatible OpenClaw installation. You also need your own Telegram bot, a private token file, the owner's numeric Telegram ID, an IANA timezone and a dedicated private workspace. The optional Codex activity view is off by default. If explicitly enabled, it reads selected, reviewed transcript exports, including excerpts of user and assistant messages; it is not metadata-only, a screen recorder, or a Computer History service.

The plugin imports the OpenClaw plugin SDK and uses its reply/delivery hooks. OpenClaw-facing configuration must be checked against the installed release; this repository does not pin or provision an OpenClaw service. Telegram, model access and any platform costs remain yours.

## Install deliberately

1. Copy and personalize [the context template](../../skills/personal-daily-assistant/assets/templates/active_context.json). Replace every `REPLACE_WITH_YOUR_` value. L1 is your main direction; L2 is a concrete way of pursuing it; period focus is what matters now.
2. Read [the installation contract](../../skills/personal-daily-assistant/references/installation-contract.md), then inspect `python3 skills/personal-daily-assistant/scripts/install.py --help` from the repository root.
3. Run the installer with explicit local paths. **Without `--apply`, it only validates inputs and prints a plan.** Keep the token in an owner-only file; never paste its value into a prompt or CLI flag.
4. Use `--apply` only for the intended dedicated directory. It writes local files and configuration/schedule declarations; it does **not** activate OpenClaw or start messaging by itself.
5. Back up the existing OpenClaw config, integrate the fragment using that release's schema and register the chosen schedules once. Technical message deletion and thread archiving remain off by default.
6. Run the checker and tests, then an authorized private text-message smoke test. Check both the delivered reply and the saved event.

The supplied schedule declares morning at 08:00, check-ins at 12:00 / 15:10 / 18:00, evening at 22:00 and weekly review on Sunday at 20:00, all in your selected timezone. There is also a 03:00 context refresh. Review these declarations before activating them. The snapshot does not contain the separate later “Ten” reflection rule.

## Private means private files too

The event journal lives outside the project directory with owner-only permissions. Personal context, generated activity and summaries can also contain sensitive information: keep the installed workspace private and out of this public repository. No real journal, contact ID, bot token or personal goal is supplied here; test fixtures are synthetic.

No schedule scans Codex history by default. To add activity, explicitly enable `PDS_INCLUDE_CODEX_ACTIVITY=1` and set an absolute `PDS_CODEX_ACTIVITY_SOURCE_DIR` containing only exports you have selected and reviewed. The helper reads those files and can include message excerpts, titles, working directories and paths in the compact context. Its pattern filters do not guarantee anonymization or removal of secrets. That context can enter your Telegram report and configured model context. See the [exact data boundary](../../skills/personal-daily-assistant/references/installation-contract.md#optional-activity-data) before enabling it.

Telegram messages and any model-assisted conversations still pass through the services you configure. Local storage does not make those transports offline. The bundled assistant accepts text and inline buttons; it does not transcribe voice attachments.

## Verification

From the repository root:

```bash
python3 -m unittest discover -s skills/personal-daily-assistant/tests -v
python3 -m unittest discover -s skills/personal-daily-assistant/assets/runtime/tests -v
node --test skills/personal-daily-assistant/assets/runtime/openclaw-plugins/personal-daily-transport/test/*.test.mjs
```

Automated local checks cover the shipped package. A successful test run is not evidence that your bot is connected, your schedules are active or a live message was delivered.

[Open the skill](../../skills/personal-daily-assistant/SKILL.md) · [Installation contract](../../skills/personal-daily-assistant/references/installation-contract.md) · [Personal cabinet + SendPulse](../integrations/lk-sendpulse.md)

[Back to Skills for Selfdev](../../README.md)
