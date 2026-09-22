# Validation and release limits

[English](validation.md) · [Русский](validation.ru.md)

Version 0.2.0 connects standalone practices with personal context and a daily assistant. A useful release is explicit about what was checked and what still depends on your environment.

## Package checks

- Thirteen skill entrypoints checked with the skill frontmatter validator.
- The Codex compatibility manifest checked with the plugin validator.
- Relative Markdown links, skill names, manifest versions, and SVG structure checked by `scripts/check_repo.py`.
- Public files reviewed for private source records, author-specific paths, credentials, and identifying examples. Automated pattern checks supplement that review; they cannot prove arbitrary text anonymous.
- Original illustration renders and GitHub-style Markdown previews inspected. English and Russian README, catalog, and a skill page were rendered at desktop and narrow widths. This checks the content presentation, not every GitHub client.

The local 0.2.0 check passed **224 automated tests**: 201 Python and 23 Node. Additional checks covered copying all 13 skills and refusing reinstallation, Ten import/feedback through the CLI, single delivery under concurrent runs, and stopping after uncertain delivery. Data was fictional and transport was mocked; no live messages were sent.

## Reproducible tests

Run these from the repository root. Python 3.10+ and Node.js are required; the GitHub workflow checks Python 3.10 and 3.12 with Node.js 22.

```sh
python3 scripts/check_repo.py
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s skills/analyze-expert-interview/tests -v
python3 -m unittest discover -s skills/reconstruct-svg/tests -v
python3 -m unittest discover -s skills/personal-daily-assistant/tests -v
python3 -m unittest discover -s skills/personal-daily-assistant/assets/runtime/tests -v
node --test skills/personal-daily-assistant/assets/runtime/openclaw-plugins/personal-daily-transport/test/*.test.mjs
```

The installation tests check copying, refusal to overwrite user changes, invalid names, and symbolic-link handling. Interview tests cover parsing, metrics, quotations, provenance, rendering, and the optional strict evaluation contract. SVG tests check vector structure. Assistant tests cover installation contracts, journal and dialogue behavior, routing, and delivery bookkeeping using synthetic data and mocks.

The [GitHub Actions history](https://github.com/KiteTools/skills-for-selfdev/actions) is the current remote test record. A green run applies to its exact commit, not to a later edit or a configured live service.

## Behavioral and visual spot checks

An independent trial applied Evening Ten to the supplied fictional day. It produced twenty candidates and ten selected possibilities, covered all three source threads, and explicitly marked prior suggestion history as unavailable. This is one trial, not a cross-model evaluation.

The fictional SVG example was rendered and compared with its source. The interview example was run through the parser and metric calculator. A full semantic interview report on a real person's transcript was not generated for this release.

Version 0.2.0 received independent fictional trials: a weekly review with overlapping summaries, an offline correction and unfinished work; a GoR conversation with a rejected causal interpretation, secular framing and a no-save request. These trials preserved gaps, disagreement and the distinction between choice and execution. They are individual scenarios, not a statistical quality evaluation.

A separate Codex Assistant setup trial used a fictional temporary workspace: unrelated instructions and existing context were preserved, repeat setup created no duplicate, a disabled journal stayed absent, and discussion did not complete a task.

The new map, EN/RU home pages and Disco page were checked in a local Markdown preview at 1440 and 390 px: images loaded with no page overflow. The Disco atlas was inspected separately; it contains no EXIF/XMP/IPTC metadata.

## Not certified by these checks

- Accuracy or psychological validity of every model-generated interpretation.
- Medical validity of a conditional life model.
- Compatibility with every AI host, OpenClaw release, or operating system.
- A working Telegram connection, activated schedules, or successful live delivery on your machine.
- Live Personal Cabinet/SendPulse integration on new accounts or SOOV compatibility with legacy data. The separate applications publish their own tests in their respective repositories.
- New images or reports produced in a later user session without inspecting their output.

The personal assistant extends the portable August foundation with separately tested modules; it is not a copy of the author’s entire private system. Dialogue remains primarily Russian. Live configuration remains a separate, explicit setup step. Keep private working data outside this checkout.

[Back to the collection](../README.md)
