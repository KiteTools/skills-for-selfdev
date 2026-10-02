# Build a daily assistant in Claude Code

**English** · [Русский](daily-assistant-claude-code.ru.md)

Keep what matters in view, choose a useful next step, and learn from what actually happened. Start with conversations and private notes in Claude Code; add Telegram when you want scheduled contact.

**[Copy the complete Claude Code setup prompt →](../../prompts/setup-daily-assistant.claude.md)**

The prompt asks the agent to inspect your environment, learn your preferences, configure selected modules and verify them. No personal data from the author is needed. One practical focus is enough to start.

## Components

| Component | Purpose | Delivered capability |
| --- | --- | --- |
| [Personal context](../skills/personal-codex-assistant.md) | Direction and evidence-based results | Instructions, blank JSON, AGENTS.md and CLAUDE.md blocks, optional journal; no service |
| [Daily assistant](../skills/personal-daily-assistant.md) | Morning, ideas, successes, state and evening in Telegram | Python runtime, OpenClaw plugin, installer, verifier, side-by-side upgrade and tests |
| [Evening Ten](../skills/evening-ten.md) | Find fresh possibilities | On-demand skill and prepared-record import; no automatic collector or generator |
| [Weekly review](../skills/weekly-review.md) | Connect intentions, understanding, action and results | On-demand evidence review with overlap handling and gaps |
| [Reaction reflection](../skills/reflect-on-reaction.md) | Explore a concrete reaction | Separate optional practice, not automatically invoked by a low state rating |
| [Session reflection](../skills/reflect-on-session.md) | Keep chosen understandings from a consultation | Uses supplied material; transfer into context requires your choice |

Collection **0.3.0** updates morning selection, Ten's editorial approach and Claude setup. It is not a release of every private assistant integration. [Release scope](../release-0.3.md).

## Start

Paste the prompt into Claude Code. The agent records the source SHA and selects a private workspace with you. To copy the base skills manually, from the downloaded repository root:

```sh
python3 scripts/install.py personal-codex-assistant weekly-review \
  --dest /absolute/private/assistant/.claude/skills
```

Choose your own path. This copies skills and refuses existing destinations. It does not create CLAUDE.md, context or a bot; the agent handles those steps from the instructions. `personal-codex-assistant` keeps its historical name; Codex is not required. In Claude Code invoke `/personal-codex-assistant` or request the skill in plain language. Start a new session after installation if needed.

Claude Code uses `.claude/skills/` and `CLAUDE.md`. This collection's root plugin manifest is not a Claude plugin manifest. See official [skills](https://code.claude.com/docs/en/skills) and [project memory](https://code.claude.com/docs/en/memory) documentation.

## Keep context contracts distinct

On-demand context is `.personal-codex/context.json`; OpenClaw uses `context/active_context.json`. Select one canonical source for goals and explicitly transfer chosen values:

| Agent context | OpenClaw context | Check |
| --- | --- | --- |
| `l1` string | `l1.text` | Preserve the owner's words |
| `l2[]`, `period_focus` | `focus_groups[]` | Map direction and focus, not whole JSON |
| `tasks[]` | `task_choices[]` | IDs, statuses and acceptance criteria differ |
| `journal.jsonl` | Runtime `events.jsonl` | Separate schemas and writers; do not concatenate |

There is no automatic adapter or two-way synchronization. Weekly review can read selected records from both, preserving provenance.

On-demand context allows unknown directions. The Telegram runtime requires a direction, active understanding, focus date, morning/evening questions, a focus group and at least one task option. Supply your own values; if you do not want to define them yet, keep on-demand use. The agent must not invent values to satisfy validation.

## Telegram requirements

Use your own bot/accounts, private token file, owner ID, timezone, compatible OpenClaw and an always-running host. Claude Code performs setup; it does not provide unattended delivery or automatically share its subscription with OpenClaw. Model access and cost depend on your OpenClaw configuration. Routine command-job messages do not call a model; preparing Ten is separate agent work.

The runtime supports macOS/Linux. WSL on Linux storage is expected but unverified; native Windows is unsupported because of POSIX locking and permission requirements. Windows users can start with on-demand Claude context and skills. The installer never activates a scheduler by itself.

## Completion criteria

For Claude: skills are found, context resolves correctly, existing instructions survive, and an enabled journal records explicit replies. For Telegram: verify owner delivery, exactly one saved event, and active schedule inventory. `verify.py` checks files and a static config subset; it cannot establish live delivery.

Local material read by an agent can reach its configured model provider. Telegram is another external channel. Keep context, journals and tokens outside the public repository.

[System map](../system-map.md) · [Installation](../getting-started.md) · [Privacy](../../PRIVACY.md)
