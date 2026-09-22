# Installation contract

## Inputs

Use explicit absolute paths for the project root, private data directory,
summaries directory, OpenClaw config, OpenClaw sessions directory and token
file. Also require an IANA timezone and the numeric Telegram owner ID.

The scheduled Telegram target must exactly equal the configured owner ID. This
is a single-owner assistant; it does not support a separate recipient.

The project root must not exist, even as an empty directory or dangling symlink.
Both the dry run and apply operation reject existing destinations. Apply checks
again immediately before creating the directory; it never merges into an
existing workspace, AGENTS.md or context. Choose a fresh path for a retry after
an incomplete install, and inspect any partial output before removing it.

Never accept the token value as a CLI argument. Read it only through the
OpenClaw-supported private file reference. Require owner-only permissions.

## Installed layout

```text
<project>/
  AGENTS.md
  context/active_context.json
  context/active_context.md
  summaries/
  scripts/
  tests/
  openclaw-plugins/personal-daily-transport/

<private-data>/
  events.jsonl
  state.json
  reports/
  views/
```

The private directory and its files use owner-only permissions. Use a new dedicated private workspace. Context, summaries and compact activity
can also contain personal information: do not publish the installed workspace.
The private data directory must not be inside the project.

## OpenClaw changes

Before writing, copy the existing config beside itself with an ISO timestamp.
Keep the Gateway loopback-only. Limit the Telegram channel and the plugin to the
numeric owner ID; keep groups disabled. Reference the private token file using
the schema supported by the installed OpenClaw release.

Install the bundled plugin and configure:

- `ownerTelegramId`
- `repoRoot`
- `dataDir`
- `openclawSessionsDir`
- `threadCleanupCutoff`
- `technicalCleanupEnabled: false` (leave disabled unless the owner explicitly
  requests technical Telegram deletion and Codex thread archiving)
- optional `pythonBin`

Do not infer config keys from this document when the installed release differs.
Inspect `openclaw --help`, validate the effective config and adapt only the
OpenClaw-facing adapter. Do not change the runtime journal contract.

The installer writes `setup/openclaw-plugin-fragment.json` and
`setup/schedule-declarations.json`; it deliberately does not overwrite an
unknown OpenClaw release's config. Merge the fragment after the backup, then
register the declarations idempotently with the installed CLI.

## Declarative schedules

Create idempotent command jobs with declaration keys:

| Local time | Command |
|---|---|
| 03:00 | context refresh, unfinished-tail review and cleanup preflight |
| 08:00 | `dispatch morning` |
| 12:00 | `dispatch viability` |
| 15:10 | `dispatch viability` |
| 18:00 | `dispatch viability` |
| 22:00 | `dispatch evening`; selected activity exports only with explicit opt-in |
| Sunday 20:00 | `dispatch weekly` |

Pass `PDS_DATA_DIR`, timezone, Telegram target and absolute working directory to
command jobs. Use exact scheduling and local IANA timezone. A retry must update
the same declaration instead of creating a duplicate.

## Optional activity data

Activity collection is **off by default**. The generated schedule does not
need access to Codex history. Evening reflection can use the local journal and
the owner's replies alone; old `context/codex_activity_latest.md` files are not
automatically attached.

For an explicitly requested activity integration, set both variables on the
chosen evening job:

- `PDS_INCLUDE_CODEX_ACTIVITY=1`
- `PDS_CODEX_ACTIVITY_SOURCE_DIR=/absolute/path/to/selected-reviewed-exports`

The selected directory has `sessions/` and/or `archived_sessions/` with selected
JSONL exports, plus an optional `session_index.jsonl`. Nested symlinks outside
that source root are excluded. Do not use the entire live Codex home by default.
Calling the helper directly likewise requires `--codex-home` with an explicit
source directory; it never infers `$CODEX_HOME` or a home-directory fallback.

**Data boundary:** the helper reads each selected JSONL file's contents, then
selects turns for the date window. The window limits the report, not which file
bytes are read. It extracts compact user/assistant message excerpts as well as
titles, working directories, paths and tool names. This is not metadata-only.
Its pattern filters are not a guarantee of anonymization or secret removal.
Use reviewed copies appropriate for downstream use. The resulting local
manifest may be incorporated into the evening Telegram report and subsequent
model context. Keep both the selected exports and installed workspace private.
A dispatch `--dry-run` still builds the local manifest if this opt-in is enabled;
it is a transport dry run, not a no-read mode. To opt out, remove/set the enable
variable to `0`; the next dispatch does not attach the previous manifest.

Summary refresh uses `PDS_SUMMARIES_DIR` when set. A configured empty directory
stays empty; it does not fall back to another summary corpus.

## Required validation

1. JSON and skill validation.
2. Python and Node test suites.
3. Installer dry-run without mutation.
4. Config backup exists before the effective config changes.
5. Gateway listens only on loopback.
6. Exactly one enabled declaration for every schedule.
7. Telegram send/readback works for the owner.
8. A saved event appears once after the Telegram smoke test.

### What the bundled checker can establish

`verify.py` inspects local files and a supported static configuration subset. It
parses strict JSON, checks the actual plugin entry and owner, respects global
plugin enable/allow/deny settings, and requires explicit `gateway.bind` equal to
`loopback`. A disabled plugin or an unknown/public/missing gateway mode fails;
matching words elsewhere in the file are not evidence.

JSON5, includes and release-specific computed configuration are not evaluated by
this checker. Such input is reported as unverified; use the installed OpenClaw
CLI to validate its effective configuration separately. The report always has
`runtime_verified: false`: file checks do not prove a plugin loaded, a gateway
bound a particular network interface, schedules became active or a message was
delivered. Complete those live checks before describing the assistant as ready.
