# Install Skills for Selfdev

**English** · [Русский](INSTALL.ru.md) · [Home](README.md)

Start with the result you need. These three routes are independent: reviews do not require Telegram, and the daily assistant does not require computer history.

| Route | What you get | What you need |
| --- | --- | --- |
| [On-demand practices](#on-demand) | Personal context, reviews, and selected skills in your AI agent | Git, Python 3.10+, an agent, and your material |
| [Telegram assistant](#telegram) | A private text dialogue, journal, and scheduled messages | macOS/Linux, Python, Node.js, OpenClaw, your own bot, and an always-on host |
| [Activity sources](#activity) | A reviewed daily summary for later reflection | Prepared notes or authorized exports; Python for local calculations |

**For the installing agent:** read the selected route and the component's `SKILL.md`. Inspect the host, preserve existing settings, and use only sources chosen by the owner. Record the commit SHA, versions, private paths, and verification results in a private `setup-report.md` without secrets. Distinguish installed files from a verified live integration.

## Shared starting point

In a new source directory:

```sh
git clone https://github.com/KiteTools/skills-for-selfdev.git
cd skills-for-selfdev
git rev-parse HEAD
python3 --version
python3 scripts/install.py --list
```

If a checkout already exists, first inspect its changes and selected version. Run all commands below **from the repository root** in a macOS/Linux shell. Replace `/absolute/private/...` examples with your own absolute paths. Keep context, journals, tokens, exports, and reports outside the public checkout.

The collection version is **0.3.3**; the bundled Telegram assistant runtime is **0.3.0**. These are separate versions. Current manifests: [collection](plugin.json), [transport](skills/personal-daily-assistant/assets/runtime/openclaw-plugins/personal-daily-transport/package.json).

| Verification baseline | What it establishes |
| --- | --- |
| CI: Python 3.10 and 3.12, Node.js 22 on Linux | Package checks and tests; live Telegram delivery is not exercised in CI |
| The assistant runtime targets macOS/Linux | Native Windows is unsupported; WSL has not been separately verified |
| The transport manifest declares OpenClaw `>=2026.7.1` | A dependency constraint, not a list of verified releases; check your release during integration |

<a id="on-demand"></a>
## 1. On-demand practices

Start with one practice such as `weekly-review`. Add `personal-codex-assistant` for personal context and `evening-ten` for ten possibilities from your day. The name `personal-codex-assistant` is historical: a [Claude Code route](docs/guides/daily-assistant-claude-code.md) is available.

**Codex:** copy to the user skill directory, `~/.agents/skills/`:

```sh
python3 scripts/install.py personal-codex-assistant weekly-review evening-ten
```

**Claude Code:** copy to the skill directory of your selected private project:

```sh
python3 scripts/install.py personal-codex-assistant weekly-review evening-ten \
  --dest /absolute/private/assistant/.claude/skills
```

Choose the appropriate command. The installer copies complete directories and refuses to overwrite existing skills. It does not create personal context, `CLAUDE.md`, a bot, or a schedule. The [copyable Claude Code prompt](prompts/setup-daily-assistant.claude.md) guides context setup while preserving existing instructions. For another agent, use its supported directory with `--dest`, or supply `SKILL.md` together with its referenced files.

**First run:** open an agent session in the selected project and ask:

> Apply weekly-review to these fictional notes for 15–21 April 2030, UTC: on Monday I prepared a draft; on Tuesday I checked it and corrected two errors. There is no evidence for the other days. Show what is established and preserve the gaps. Do not save anything or schedule work.

You can invoke `$weekly-review` in Codex or `/weekly-review` in Claude Code. If the skill is not discovered, start a new session or restart the application and check the directory. **Ready** means the agent read the installed skill, completed the trial, and did not treat days without records as days without activity. This checks discovery and basic behavior, not the quality of every future response.

**Update and disable:** review changes, move the previous skill directory outside discovery locations, and install the selected version again. Review your `CLAUDE.md`/`AGENTS.md` blocks separately and preserve personal rules. To disable a skill, remove it from the discovery directory; retain context and journals separately. [Requirements for other skills](docs/getting-started.md).

<a id="telegram"></a>
## 2. Telegram assistant

This route installs a separate OpenClaw runtime. Copying the skill into an agent is not sufficient. You need your own bot, numeric Telegram owner ID, private token file, IANA timezone, and an always-available computer. The runtime's commands and dialogues are primarily Russian. OpenClaw and its model are configured separately; an AI application's subscription does not automatically connect a model to OpenClaw.

### Prepare your configuration

Read [SKILL.md](skills/personal-daily-assistant/SKILL.md) and the [installation contract](skills/personal-daily-assistant/references/installation-contract.md). Check `python3 --version`, `node --version`, `openclaw --version`, and `openclaw --help`.

Check the bundled components with fictional data and no live sending:

```sh
python3 -m unittest discover -s skills/personal-daily-assistant/tests
python3 -m unittest discover -s skills/personal-daily-assistant/assets/runtime/tests
node --test skills/personal-daily-assistant/assets/runtime/openclaw-plugins/personal-daily-transport/test/*.test.mjs
```

Save a copy of the [context template](skills/personal-daily-assistant/assets/templates/active_context.json) as a private `context.json`. Replace all `REPLACE_WITH_YOUR_` markers, the focus end date, and the example task with your own values. Do not invent answers to satisfy validation: if you do not want to define this context yet, start with route 1.

Prepare these values in your shell session. All paths are examples; the `assistant` directory must **not exist yet**, even as an empty directory. Keep the data directory separate from it. The token file must already exist and belong to you; never put its contents in chat or command arguments.

```sh
SELFDEV_PRIVATE="/absolute/private/selfdev"
SELFDEV_OWNER_ID="YOUR_NUMERIC_TELEGRAM_ID"
SELFDEV_TIMEZONE="Europe/Paris"
SELFDEV_OPENCLAW_CONFIG="/absolute/private/openclaw/openclaw.json"
SELFDEV_OPENCLAW_SESSIONS="/absolute/private/openclaw/sessions"
SELFDEV_TOKEN_FILE="/absolute/private/secrets/telegram-token"
SELFDEV_PYTHON="$(python3 -c 'import sys; print(sys.executable)')"
SELFDEV_SETUP_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
chmod 600 "$SELFDEV_TOKEN_FILE"
```

### Review the plan, then install files

```sh
python3 skills/personal-daily-assistant/scripts/install.py \
  --project-root "$SELFDEV_PRIVATE/assistant" \
  --data-dir "$SELFDEV_PRIVATE/data" \
  --context-json "$SELFDEV_PRIVATE/context.json" \
  --summaries-dir "$SELFDEV_PRIVATE/summaries" \
  --timezone "$SELFDEV_TIMEZONE" \
  --owner-telegram-id "$SELFDEV_OWNER_ID" \
  --telegram-target "$SELFDEV_OWNER_ID" \
  --openclaw-config "$SELFDEV_OPENCLAW_CONFIG" \
  --openclaw-sessions-dir "$SELFDEV_OPENCLAW_SESSIONS" \
  --token-file "$SELFDEV_TOKEN_FILE" \
  --python-bin "$SELFDEV_PYTHON" \
  --thread-cleanup-cutoff "$SELFDEV_SETUP_AT"
```

Without `--apply`, this validates the inputs and prints JSON with `mode: dry-run`; it does not create installation directories. Review the paths, owner, timezone, and **7 schedule declarations**: 03:00, 08:00, 12:00, 15:10, 18:00, 22:00, and Sunday 20:00. Technical cleanup is disabled; the cutoff parameter does not enable it.

If the plan matches your choices, repeat the same command with `--apply` added. Expect `mode: applied-local-files`, a private journal, and `assistant/setup/openclaw-plugin-fragment.json` and `assistant/setup/schedule-declarations.json`. OpenClaw and the jobs are not yet connected.

### Connect and verify delivery

Back up the effective OpenClaw configuration next to the original. The checker looks for `<config-filename>.backup-<date>`:

```sh
cp -p -n "$SELFDEV_OPENCLAW_CONFIG" "$SELFDEV_OPENCLAW_CONFIG.backup-$SELFDEV_SETUP_AT"
```

Using your installed release's interface, connect the plugin at `assistant/openclaw-plugins/personal-daily-transport`, transfer its settings from the fragment, and configure the token file reference. The fragment's `telegram_guardrails` describes installation requirements; do not paste it as an unknown key into live configuration. Restrict this bot to the owner, disable its group access, keep the Gateway on loopback, and preserve other bots' access. If they cannot be isolated, choose a separate OpenClaw instance.

Register the selected jobs once each, preserving `declaration_key`, timezone, `cwd`, `argv`, and environment variables. Never run the old and new installation against the same journal simultaneously. There is deliberately no universal registration command here: the CLI schema depends on the OpenClaw release.

```sh
python3 skills/personal-daily-assistant/scripts/verify.py \
  --project-root "$SELFDEV_PRIVATE/assistant" \
  --data-dir "$SELFDEV_PRIVATE/data" \
  --token-file "$SELFDEV_TOKEN_FILE" \
  --openclaw-config "$SELFDEV_OPENCLAW_CONFIG"
```

The checker should return `ok: true`; `runtime_verified` remains `false`. It checks files and a supported strict-JSON configuration subset, not a running process. Validate JSON5/includes through your OpenClaw release. Then check plugin loading, effective access restrictions, unique schedules, and one text dialogue with the owner: the reply arrives and its corresponding journal event appears exactly once. Only then is the assistant **working and verified**.

Evening Ten is optional. Preparing installation with `--enable-evening-ten` creates **8 declarations**: Ten delivery at 22:00 and the review at 22:10. It does not add a collector or generator. First configure [preparation, review, and import](skills/personal-daily-assistant/references/evening-ten-integration.md).

**Update and disable:** follow the [side-by-side upgrade](skills/personal-daily-assistant/references/installation-contract.md#supported-hosts-and-safe-upgrade). Stop old jobs and writers, back up context, private data, and configuration, then switch paths. To disable this installation, stop its jobs and ingress and disable its plugin; keep the journal. Rollback requires stopping the new installation before restoring the previous paths and jobs. There is no automatic cutover or rollback.

<a id="activity"></a>
## 3. Activity sources

Start with your own notes: they already support evening and weekly reflection. Device history is optional additional evidence. This route processes selected data; it does not install computer monitoring.

| Source | Included | Connected separately |
| --- | --- | --- |
| Your notes and results | Review practices and explicit assistant journal entries | Selection of material |
| Device data and self-reports | `cross-device-day-review` CLI for normalized JSON | Export from your selected service and reviewed conversion |
| Codex/Cursor machine time | Review rules and completed-interval calculations in the CLI | Metadata collector; no Cursor collector, hooks, or database reader is bundled |
| Selected Codex conversation exports | A separate optional evening-assistant mechanism | Prepared private exports; it reads message text, not only durations |

### Run a fictional example

```sh
SELFDEV_DEMO="$(mktemp -d)"
python3 skills/cross-device-day-review/scripts/day_review.py \
  --config skills/cross-device-day-review/examples/config.json \
  --input skills/cross-device-day-review/examples/day.json \
  --output-dir "$SELFDEV_DEMO/report"
```

Expect `report.md`, `report.json`, and `compact.json` in a new directory. In this example, human intervals total **140 minutes**, machine runtime is **90 minutes**, and machine union wall time is **60 minutes**. The tablet remains a missing source, and an untimed conversation keeps its duration unknown. A `partial` report is valid: it represents incomplete evidence, not failure. The example is fictional and does not access your history.

### Prepare your data

Follow the [input contract](skills/cross-device-day-review/references/input.md) to create private `config.json` and `day.json`, then repeat the command with those paths and a new output directory. The CLI accepts normalized JSON, not arbitrary ActivityWatch, RescueTime, or other service exports. [Adapter boundaries](skills/cross-device-day-review/references/adapters.md) explain what can be extracted and what remains unknown. Do not convert approximate durations into invented exact intervals.

Machine runs require verified starts, ends, and stable pseudonymous IDs. Preserve separate Codex/Cursor sources, deduplicate, and exclude child runs from the root-run total. The CLI computes combined runtime and union wall time; its per-source minutes are **union wall time, not each provider's runtime**. The [review rules](docs/guides/agent-time-retrospectives.md) explain this distinction and daily coverage. Before incorporating a third-party collector's report, check its time definition, timezone, and format.

Give the reviewed summary to your agent and ask for `weekly-review` or `evening-ten`. These files are not automatically imported into the Telegram runtime.

For the separate evening-assistant mechanism that reads selected Codex conversation exports, follow the [integration contract](skills/personal-daily-assistant/references/installation-contract.md#optional-activity-data): both `PDS_INCLUDE_CODEX_ACTIVITY=1` and an absolute `PDS_CODEX_ACTIVITY_SOURCE_DIR` are required. Do not select the entire live history by default. This mechanism extracts message excerpts; output may reach Telegram and model context. Even a transport dry run reads data when this option is enabled.

**Ready** means the source and period are known, conversion has been reviewed, the summary preserves missing evidence, and duplicate records do not increase time. **Disable:** stop supplying the source; for the Codex integration remove the enable flag or set it to `0`. Disable external collectors separately according to their instructions. A skill update does not change them.

## Where to verify the result

[GitHub Actions](https://github.com/KiteTools/skills-for-selfdev/actions) records checks for a specific commit. The [validation guide](docs/validation.md) retains earlier release history; it does not replace checking your installation. Initial file check:

```sh
python3 scripts/check_repo.py
```

In your private `setup-report.md`, separate **working and verified**, **prepared but awaiting live verification**, and **not connected by your choice**. Record how to disable and update the selected route. [Privacy](PRIVACY.md) · [System map](docs/system-map.md) · [Catalog](docs/catalog.md).
