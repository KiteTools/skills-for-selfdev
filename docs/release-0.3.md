# Daily assistant update 0.3.0 · 2 October 2026

**English** · [Русский](release-0.3.ru.md)

This update adds a Claude Code assembly path, free-form morning choice and a broader editorial approach to Evening Ten.

## Changes

- [Copyable Claude Code prompt](../prompts/setup-daily-assistant.claude.md), with distinct on-demand and Telegram branches.
- [Component map](guides/daily-assistant-claude-code.md) with requirements and compatibility boundaries.
- `personal-codex-assistant` supports a scoped CLAUDE.md template as well as AGENTS.md. Skill name and data schema remain compatible.
- Morning accepts a step in the owner's words; “Показать задачи” opens the catalog. Numbers, `0`, existing buttons and idempotency remain supported. Free-form choice does not change catalog tasks.
- Recorded intention does not automatically invoke model continuation. An explicit request at the start of a reply is handled by a bounded Russian routing rule, not semantic intent classification.
- Ten explores different ways of participating, preserving evidence and choice. The author's private quotas, beliefs and relationships are not defaults.
- Windows guidance distinguishes portable context/skills from the POSIX Telegram runtime. WSL remains unverified.

## Retained capabilities

Local journal, ideas/successes, explicit activity reports, prepared Ten import, immutable numbering, separate feedback and side-by-side upgrades. Weekly review already accepts selected reflection decisions as decisions, not proof of subsequent action.

## Not exported from the private system

General Computer History/RescueTime/ActivityWatch collectors, private `day_activities` runtime fields, background Ten generation, expanded state capture/annotation commands, personal curator, automatic reaction review, audio, private dashboard and external task synchronization. Supplied summaries remain valid skill inputs. The prompt explains overlap and machine-time boundaries but does not install collectors.

## Upgrade

Review local modifications before replacing skill folders; the root installer refuses overwrite. For a running Telegram assistant follow the [side-by-side upgrade contract](../skills/personal-daily-assistant/references/installation-contract.md#supported-hosts-and-safe-upgrade): new workspace, stop old writers before cutover, backups, preserved data and schedule verification. Copying a skill does not update a running runtime.

Claude/Codex and OpenClaw context schemas remain distinct, without automatic synchronization. Inspect an older private archive's metadata before using `upgrade.py`; if incompatible, preserve it and plan an explicit migration.

## Verification scope

Synthetic tests cover free-form choice, catalog access, legacy numbers/`0`, duplicate delivery, stale callbacks, recovery and intent/execution separation. CI runs package, installation, runtime and transport checks. Claude guidance follows official [skills](https://code.claude.com/docs/en/skills) and [CLAUDE.md](https://code.claude.com/docs/en/memory) documentation; local copying to `.claude/skills/` is exercised. A new owner's live Claude Code, Windows/WSL and Telegram setup is not claimed verified by this release.

[Setup prompt](../prompts/setup-daily-assistant.claude.md) · [Previous release](release-0.2.md)
