# Start with one useful result

**Using Claude Code?** [Build your daily assistant: copyable prompt and component map](guides/daily-assistant-claude-code.md).

[English](getting-started.md) · [Русский](getting-started.ru.md)

Pick a skill from the [catalog](catalog.md). Read its input, output, and requirements before bringing personal material.

## If you want a personal assistant

Start with the [system map](system-map.md). Install `personal-codex-assistant` for personal context and working agreements. Add `evening-ten` and `weekly-review` when you want those practices. GoR has its own `reflect-on-reaction` skill.

```sh
python3 scripts/install.py personal-codex-assistant evening-ten weekly-review
```

`personal-daily-assistant` is an optional next layer with a runtime and service connections. Copying the skill does not install that runtime or activate Telegram. Its [guide](skills/personal-daily-assistant.md) explains updating an existing assistant.

## Install a standalone skill

Requirements: Git and Python 3.10 or newer for the installer. Your AI assistant must support skills or accept the selected instructions as a file.

```sh
git clone https://github.com/KiteTools/skills-for-selfdev.git
cd skills-for-selfdev
python3 scripts/install.py --list
python3 scripts/install.py learning-notes
```

The default destination is `~/.agents/skills/`, a user skill location supported by Codex. To choose a project location or another agent's supported directory:

```sh
python3 scripts/install.py learning-notes --dest /path/to/project/.agents/skills
```

The installer copies the complete selected skill, including its relative references and helpers. It refuses existing skill destinations, symbolic links inside a skill, and a destination directory that is itself a symbolic link. For an update, review the changes and move your old skill aside yourself before installing again. Installing the whole collection is optional:

```sh
python3 scripts/install.py --all
```

Copying a skill does not run its installer, start services, change schedules, or transmit data. Invoke it deliberately for a first run:

```text
Use $learning-notes with the attached transcript. Write in my language.
Preserve examples and mark anything the source does not establish.
```

If Codex does not show a new skill, restart it. Other agents may use different discovery paths and invocation syntax; consult their documentation. A plain `SKILL.md` can also be supplied as instructions, but this does not give the agent missing tools.

## Plugin packaging

The root `plugin.json` packages the same skills using the portable plugin format. `.codex-plugin/plugin.json` provides the Codex compatibility manifest. Use a host that supports importing this plugin source; this repository is not claiming a listing in an official marketplace. Standalone installation above is the explicit, reproducible path.

See the official [skills documentation](https://developers.openai.com/codex/skills/) and [plugin format](https://developers.openai.com/plugins/build/plugins).

## What requires more setup?

| Workflow | Additional requirements |
| --- | --- |
| Reflection, notes, cleanup, Evening Ten, life events, Disco | An AI assistant and supplied source material |
| Expert interview report | Python; a browser for visual QA; independent analysis contexts for the full review |
| SVG reconstruction | Ability to write SVG and render it for comparison |
| Optional session posters | An image-generation tool; do not imply it is installed automatically |
| Personal daily assistant | Python, Node.js, OpenClaw, a Telegram bot, and private local storage; see its installation contract |
| Longevity intake | The external app; supported browser-agent tools for automated interaction, or manual entry |
| Personal Cabinet + SendPulse | Your own deployed Personal Cabinet and configured accounts; see the integration guide |

## Your first ten minutes

1. Use a short, non-sensitive or fictional source first.
2. Ask for one output in your preferred language.
3. Check a few claims against the original.
4. Keep what is useful; correct what is wrong. Add personal material only after understanding the data route.
