# Data boundaries

The repository distributes instructions and code. It has no shared account system, central journal, telemetry service, or collection endpoint.

## What is public

Skill instructions, reusable helpers, empty templates, original illustrations, and clearly marked fictional examples. No real sessions, activity histories, client records, family trees, credentials, or author diaries are included.

## Where your information goes

| Action | Boundary |
| --- | --- |
| Install a skill | Files are copied locally; no personal input is requested or transmitted by the installer |
| Give a transcript to an AI assistant | Your chosen provider's processing and retention policies apply |
| Run local parsers or renderers | Read their arguments; outputs stay in the chosen directory unless you send them elsewhere |
| Generate images or use speech services | The selected image or speech provider may receive the supplied material |
| Use the daily assistant | Your local runtime and Telegram/OpenClaw configuration handle the messages |
| Use Longevity or LK/SendPulse | Read that application's current privacy boundary before submitting information |

Local output does not imply local AI inference. A skill cannot override a provider's retention policy. Browser and speech tools can also have separate data routes.

## Keep private material out of Git

Use a separate data directory outside this checkout for transcripts, notes, reports, and journals. Ignore rules are a backup, not a privacy boundary. Check a diff before committing. Never put tokens in a prompt, issue, example, or repository file; use the private credential mechanism of the service you connect.

Do not share another person's identifiable consultation or family information without appropriate permission. For a public example, write a fictional case from scratch rather than replacing only a name in a real case.

## Reporting a problem

Do not paste sensitive material into public issues. Open a minimal issue describing the affected component and ask for a private reporting route without including the sensitive content.
