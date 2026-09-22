# Contributing

[English](CONTRIBUTING.md) · [Русский](CONTRIBUTING.ru.md)

Improve one real workflow at a time. A useful contribution explains the input, the outcome, and the decision the assistant would otherwise get wrong.

For a skill change, keep its `SKILL.md`, visitor page in `docs/skills/`, and example consistent. Preserve source attribution and uncertainty. Do not add automatic account connections or scheduled actions to a workflow that previously only analyzed supplied material.

Use fictional examples written from scratch. Do not contribute chat exports, client records, tokens, personal paths, or copied third-party course material. A changed name does not anonymize a case.

Run `python3 scripts/check_repo.py` and `python3 -m unittest discover -s tests -v`. If changing a bundled runtime, also run its tests. State what was tested and which integrations remain untested.

The README is organized around a visitor's task. Prefer one concrete example over a list of abstract promises. Keep English and Russian entry pages aligned when adding or removing a capability.
