# Personal Codex Assistant

**English** · [Русский](personal-codex-assistant.ru.md)

![A visual rhythm connecting context, work and reflection](../../assets/rhythm.png)

**Keep your direction visible while Codex helps with real work.**

You open a task to finish a small prototype. The assistant briefly connects that result to the focus you chose, helps complete the work, checks the result, then asks how the experience felt. Your answer can go into a private journal. A difficult experience does not erase a finished result; a good feeling does not prove that a task is complete.

This standalone skill brings the personal context rules into Codex. It needs no Telegram bot, OpenClaw runtime or other installed skill.

## What it does

| Moment | Concrete outcome |
| --- | --- |
| Setup | A blank private context and a carefully merged instruction block for one selected workspace |
| Task opening | One line connecting your main direction, relevant goal, current focus and expected result |
| Confirmed completion | The matching catalog task receives evidence and a completion status, if you use a catalog |
| After the work | An optional vitality question; your answer is saved only when local journaling is enabled |

L1 means your main direction. L2 is a concrete way of pursuing it. Period focus is what matters now. You supply these meanings; the assistant does not choose your beliefs, life goals or priorities. Work outside the focus is allowed and is simply identified as such.

The five vitality choices are **−− / − / = / + / ++**. They are your reported experience, not an automatic score. The assistant asks once after verified implementation, not after a discussion, status update or unfinished attempt. You can skip the answer or disable the question. Strategic conclusions belong in a separately requested weekly review.

## Try it

```text
Use $personal-codex-assistant to prepare a personal work context for my selected
private workspace. Keep my existing AGENTS instructions. Show the proposed
scoped block and blank context before setup. Leave local journaling disabled.
My main direction and current focus are in the notes I have attached.
```

**Input:** your designated workspace, existing instructions, and whatever direction, goals or current focus you choose to supply. Missing values remain empty. **Output:** a proposed or authorized local setup, a task alignment line, evidence-based task updates, and optional private journal entries.

For ordinary use after setup:

```text
Help me complete task sample-01 against its acceptance condition.
Use my current focus, verify the result, and ask the vitality question afterward.
```

The [fictional example](../../examples/personal-codex-assistant/example.md) shows a context, an actual completion boundary and a journal response.

## Files and installation boundary

The package includes [the skill](../../skills/personal-codex-assistant/SKILL.md), a [blank JSON context](../../skills/personal-codex-assistant/assets/templates/context.json), a [scoped AGENTS block](../../skills/personal-codex-assistant/assets/templates/agents-block.md), and instructions for [safe setup](../../skills/personal-codex-assistant/references/setup.md) and [journal records](../../skills/personal-codex-assistant/references/journal.md).

It proposes `.personal-codex/context.json` and an optional `.personal-codex/journal.jsonl` inside your selected private workspace. Existing context is preserved; setup does not reset it to the template. Only the marked AGENTS block is appended or updated. Conflicting instructions and ambiguous markers must be resolved before changing them. No global Codex configuration is modified.

Removing that block or setting context `enabled` to false disables the rules. Disabling journaling preserves earlier entries. No deletion, messaging or scheduling happens automatically.

## Requirements, privacy and release status

Use Codex with permission to read the chosen local files; writing is needed only for authorized setup, catalog updates or journaling. No API key, bot, database or Python/Node runtime is required by this package. There is no executable installer.

Keep context and journal outside public repositories. An ignore rule does not make previously tracked personal data private. Material read in a Codex conversation may be sent to the configured model service; local files do not mean offline inference. The journal assumes one writer and makes no promise of background synchronization or transaction recovery.

**Release status:** portable instructions and clean templates for on-demand Codex use. Package structure and local links are checked; no live installation, scheduled workflow or long-term personal outcome is claimed. This is a separate module from the Telegram-based [Personal Daily Assistant](personal-daily-assistant.md). The [system map](../system-map.md) explains how the modules can connect without making one mandatory for another.

[Open the skill](../../skills/personal-codex-assistant/SKILL.md) · [Browse the catalog](../catalog.md) · [Back to Skills for Selfdev](../../README.md)
