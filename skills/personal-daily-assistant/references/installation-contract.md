# Installation contract — portable v0.3.0

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
  evening-ten/       # optional immutable daily records + separate feedback
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
- `eveningTenEnabled: false` (opt in only with a prepared Ten workflow)
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

With installer `--enable-evening-ten`, replace the 22:00 retro declaration with
`personal-daily-ten-2200` (`ten`, 22:00) and
`personal-daily-evening-2210` (`evening`, 22:10). There are eight declarations
instead of seven. Ten delivery has `PDS_EVENING_TEN_ENABLED=1`; the plugin has
`eveningTenEnabled: true`. The Ten job only reads that date's prepared private
record. Missing data means no send, without suppressing the later retro. It
never collects history or calls a model. See [the import and feedback bridge](evening-ten-integration.md).

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

## Supported hosts and safe upgrade

Python 3.10+ and Node.js run the bundled checks; live operation additionally
requires a compatible OpenClaw release, Telegram bot/owner configuration and
an always-running host. macOS/Linux are the supported POSIX targets. WSL on a
Linux filesystem is expected to provide the needed `fcntl` locks and permissions,
but this package has not been verified on WSL. Native Windows Python is not
supported. Do not translate these paths to Windows drive paths or install private
data on a shared mounted filesystem whose permissions cannot enforce ownership.
A sleeping or offline laptop cannot deliver scheduled messages on time.

Stage an upgrade from the earlier portable package into a **new sibling
workspace**. Run this from the distributed skill directory:

```bash
python3 scripts/upgrade.py \
  --source-project /absolute/private/assistant-v01 \
  --new-project /absolute/private/assistant-v02 \
  --openclaw-config /absolute/private/openclaw.json
```

This is a dry run. Add `--enable-evening-ten` only if requested. Before
`--apply`, stop every old job, ingress and context writer and back up private data
and effective configuration. Keep them stopped through staging and cutover;
otherwise the copied goal/task context can become stale. Then add `--apply`
to stage local files. The helper reads the old generated fragment and personalized
context, preserves context bytes, reuses the same private data and summaries,
and retains the old workspace. It does not read journal bodies, rewrite state,
activate jobs, merge config or touch Telegram. Symlinks in the private data tree
are rejected before any writes. New workspace permissions are 0700; context is
0600. Existing custom rules are copied to `setup/previous-AGENTS.md` for review;
they are not silently merged into the new runtime's rules.

Before switching, confirm the old writers remain stopped. Compare the new rules with `previous-AGENTS.md`; change the
plugin path and replace declarations using the installed OpenClaw interface.
Never run both workspaces against the same data concurrently. Enabling Ten also
means disabling/removing the old `personal-daily-evening-2200` declaration, not
adding a duplicate retro. Keep the new Ten records separate during any rollback;
the old runtime does not understand this feature. Re-register old paths/jobs only
after stopping the new ones. No automatic live migration or rollback is provided.
An old pending idea-result is accepted as an optional note, without making a task.

Explicit `/занятие` commands require no schedule. They store user-reported
start/end or postpone/skip decisions in the existing append-only journal, with
idempotency by message ID. They do not infer task completion or schedule new work.
