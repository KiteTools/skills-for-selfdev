# SOOV and the personal cabinet: making the tools independently usable

[English](portable-apps.md) · [Русский](portable-apps.ru.md)

**Status: design proposal with an implementation update.** This document preserves the intended direction. The following status section records what has actually been implemented; later design sections are requirements, not a claim that every feature has shipped.

Independently usable means a concrete outcome: another person can obtain the code and instructions, run the tool with their own data and accounts, update it, back it up and continue without access to the author's infrastructure.

## Current delivery status

- **[Building Your Life Function](https://github.com/KiteTools/soov):** a new, independent event-only browser app with manual input, reviewed import, IndexedDB storage, JSON backup/restore, and CSV export. The original screen was found in [Longevity's source](https://github.com/KiteTools/longevity-webmcp). The old model and legacy file compatibility are not included; the implemented [schema](https://github.com/KiteTools/soov/blob/main/schema.json) is authoritative for this release.
- **[Personal Cabinet](https://github.com/KiteTools/selfdev-cabinet):** clean application source, setup/check scripts, migrations, restricted static build, operator instructions, and a manual SendPulse reconstruction kit. Its transport facade supports `sendpulse` and `local`; local mode stores application data without bot delivery. Telegram login verifies contact ownership in SendPulse mode.
- **Not verified live:** a fresh operator's Netlify/Neon/Telegram/SendPulse installation and full delivery loop. Use the [installation acceptance guide](https://github.com/KiteTools/selfdev-cabinet/blob/main/docs/operator-install.md) with your own accounts.
- **Still proposed:** an outgoing queue/outbox, delivery acknowledgments, universal event deduplication, direct Telegram transport, cloud sync for SOOV, and full migration of old user data. A facade with two adapters does not implement this whole architecture.

## What already exists

| Tool | Established foundation | Missing from the public distribution |
| --- | --- | --- |
| SOOV | Original event screen identified in Longevity; a smaller standalone application and the [life-events](../skills/life-events.md) skill are available as separate source packages. | Cloud sync, an in-app AI service, and a converter for old model files. |
| Personal Cabinet + SendPulse | A standalone source package, setup/migration tools, operator guide, transport facade, and bot reconstruction instructions. | Live verification on new accounts, a reusable private-bot export, outgoing queue, and full data migration. |

## Design sequence

1. **Documentation:** publish the full guide and dependency map. This milestone is complete.
2. **First standalone product:** SOOV with manual entry, reviewable import and export, without a mandatory account.
3. **First cabinet distribution:** reproducible deployment on the existing stack with the operator's own Telegram and SendPulse accounts.
4. **Next cabinet milestone:** an independent core and replaceable adapters. Add a direct Telegram bot or fully standalone mode after verifying the first distribution.

Avoid changing the backend, login system and bot at the same time. The first distribution should demonstrate that another operator can use the existing tool.

<a id="soov"></a>
## SOOV: a local life-event timeline

Consider a fictional example: someone remembers moving at about age 24. They want to record the event, preserve the approximate age and keep their own account of the experience. A form and a file are enough for that; registration adds no immediate value.

### Original first-release requirements

- **Manual entry:** date or age, precision, event description, the person's own assessment and a source note.
- **From a transcript:** life-events prepares a draft in the person's chosen AI assistant; the app presents it for review before saving. Keep the full transcript only if the user separately chooses to do so.
- **Editing:** correct dates and text, delete entries and merge duplicates while preserving sources. Proposals do not become confirmed events automatically.
- **Storage:** a browser database such as IndexedDB, with explicit export and restore. Show the last export date and explain that clearing browser data can erase records.
- **Exchange:** versioned JSON for complete transfer; CSV for spreadsheet viewing, with documented limits on representing nested source records.

Proposed minimum data contract: `schema_version`, `events[]`, a stable `id`, `date` or a range/age, `date_precision`, `description`, optional `self_assessment`, `sources[]` and `review_status`. Identifiers allow repeat imports without duplicating events. This was the design sketch, not the implemented schema. Use the standalone application's schema and import prompt; arbitrary JSON from the skill must not be assumed compatible.

### Authentication

Manual entry and local storage need no account. Cloud sync would need a separate server, login and access control in a later version. Direct API extraction is another optional feature: a server API key must not be embedded in a public page. For the first release, importing a draft prepared in the person's own assistant is enough.

Provide a separate demonstration mode with fictional events. Neither the demo nor the application build should contain real histories. Local storage does not itself encrypt the data or make an external model local.

### Distribution and acceptance

The separate repository is [KiteTools/soov](https://github.com/KiteTools/soov). It includes the application, schema, launch/deployment instructions, fictional example, and backup instructions. Skills for Selfdev keeps the companion skill and application link.

The original screen was located in Longevity. The selected implementation is a small new client for event capture and transfer; it is not an exact copy of the original application or its model.

**Acceptance check:** a new user adds an event without registering, imports a reviewed draft, edits it, exports JSON and restores the same records in another browser without duplicates. Longevity import must be checked separately against its own schema; compatibility is not automatic.

<a id="lk"></a>
## The cabinet: begin with reproducible deployment

Imagine another consultant creating their own accounts, deploying an empty cabinet, starting their own bot and completing the full loop with a fictional consultation. No step requires the author's identity, database or keys. That is the first useful acceptance criterion.

### What to transfer from the existing system

| Component | Found in the source | Needed for independent installation |
| --- | --- | --- |
| Interface and API | Static client and Netlify Functions | Clean source, dependencies, build/deployment commands and an explicit list of public files |
| Storage | Neon/Postgres and numbered SQL migrations | Empty-database setup, migration order, backups, restoration and upgrades |
| Login | Telegram Login Widget / WebApp, server verification and sessions | Own bot, domain, environment variables and the `/start → login → own records` flow |
| SendPulse | API client, contacts, variables and event intake | Bidirectional field map, bot flows, callback URLs and setup order |
| AI jobs | Summaries, journals, analysis, patterns and retrospectives | Own API key, model configuration, error handling and input limits |
| Email | SMTP | Optional setup with the operator's account and clear behavior without email |

This describes the reviewed source, not a live-service test. A fresh deployment still needs verification.

### First distribution contents

The separate source repository is [KiteTools/selfdev-cabinet](https://github.com/KiteTools/selfdev-cabinet). The checklist below describes the intended distribution; source/setup availability and live acceptance are separate statuses.

- Application source **with a new, clean Git history**, excluding private configuration, real records and old uploads.
- An `.env.example` with empty or clearly fictional values and an explanation of every required parameter. Configure secrets on the server; keep them out of the public build.
- Database migrations and a synthetic demonstration dataset separate from working records.
- Keep private contact and variable values out of provider logs. The public adapter removes the original contact/request-payload logging; preserve this boundary when adding integrations and test with fictional data.
- An operator guide covering accounts, domain, login, variables, background jobs, bot setup, upgrades and recovery.
- A **SendPulse setup kit:** flow diagrams, variable types and exchange directions, callback configuration, a synthetic event and its expected result. Include a portable flow export if available and verified; otherwise provide step-by-step reconstruction. Automatic cloning has not been verified.
- The published [user guide](../guides/lk-guide.md), tied to a release version, and an end-to-end check with fictional data.

Keep Telegram login and the existing SendPulse connection in the first version. Independent deployment means **the new operator's own accounts**, not the absence of external dependencies. A cabinet without Telegram would require a different login method; that capability is not claimed today.

### Then separate SendPulse from the core

```mermaid
flowchart LR
    UI[Personal cabinet] --> CORE[Records, summaries, patterns and reviews]
    CORE --> DB[Private database]
    CORE --> OUT[Outgoing event queue]
    OUT --> SP[SendPulse adapter]
    SP --> BOT[Telegram bot]
    BOT --> SP
    SP --> IN[Incoming event intake]
    IN --> CORE
    OUT -. future alternative .-> TG[Direct Telegram adapter]
```

**This is proposed architecture; the current transport facade does not include the outgoing queue shown here.** The primary user identifier belongs to the cabinet; Telegram ID and SendPulse contact ID become external mappings. The core stores records. The adapter translates fields and messages into the service's format, verifies the source of incoming events and retains delivery identifiers.

Add an outgoing queue, retries and duplicate protection. Display “saved in the cabinet,” “sent to SendPulse” and “delivery confirmed” as separate states. Then consider a direct Telegram bot or manual journaling without SendPulse. Replacing the transport still requires reproducing the bot's interaction flows.

### First-distribution acceptance check

A new operator follows the instructions: empty database → own bot → `/start` and login → fictional transcript → summary → preview and apply selected fields → verify bot update → journal entry → retrospective → backup and restore.

The current acceptance run must check account isolation and actual save/delivery outcomes. Duplicate-free incoming delivery and durable retry through a SendPulse outage remain future acceptance goals: the current ingestion routes do not promise idempotency, and sequential remote updates can partially succeed. Do not mark those goals passed from code publication or a local adapter test.

## Method boundary

The cabinet helps organize material and support the person's chosen practice between consultations. AI does not declare a hidden cause established or choose for the client. Within IMT practice, new understanding is joined to the person's decision and a corresponding action; a sustained result is checked over time. An activity counter or a well-written summary cannot replace that check.

[SOOV overview](soov.md) · [Cabinet + SendPulse overview](lk-sendpulse.md) · [Catalog](../catalog.md)
