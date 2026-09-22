import { execFile } from "node:child_process";
import { join } from "node:path";
import { promisify } from "node:util";

import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";

import {
  handleDeliveredReply,
  prepareContinuationForReply,
  resumeContinuations,
} from "./continuation-runtime.mjs";
import { createContinuationOutbox } from "./continuation-outbox.mjs";
import {
  createFastReplyDispatchHandler,
  isTechnicalTelegramMessage,
} from "./router.mjs";

const execFileAsync = promisify(execFile);

type PluginConfig = Record<string, unknown>;

async function runPds(config: PluginConfig, args: string[]) {
  const repoRoot = String(config.repoRoot);
  const script = join(repoRoot, "scripts", "personal_daily_system.py");
  const pythonBin = String(config.pythonBin || "python3");
  const { stdout } = await execFileAsync(pythonBin, [script, ...args], {
    cwd: repoRoot,
    env: {
      ...process.env,
      PDS_DATA_DIR: String(config.dataDir),
      PDS_TIMEZONE: String(config.timezone),
      PDS_SUMMARIES_DIR: String(config.summariesDir),
    },
    timeout: 3000,
    maxBuffer: 1024 * 1024,
  });
  return JSON.parse(stdout);
}

async function recordDeliveryAndCleanup(
  config: PluginConfig,
  sessionKey: string,
) {
  const repoRoot = String(config.repoRoot);
  const script = join(repoRoot, "scripts", "codex_thread_hygiene.py");
  const pythonBin = String(config.pythonBin || "python3");
  await execFileAsync(
    pythonBin,
    [
      script,
      "record-delivery",
      "--session-key",
      sessionKey,
      "--sessions-dir",
      String(config.openclawSessionsDir),
      "--state-dir",
      String(config.dataDir),
      "--cutoff",
      String(config.threadCleanupCutoff),
    ],
    {
      cwd: repoRoot,
      timeout: 15000,
      maxBuffer: 1024 * 1024,
    },
  );
}

export default definePluginEntry({
  id: "personal-daily-transport",
  name: "Personal Daily Transport",
  description:
    "Handles deterministic personal-daily Telegram transitions before a model turn.",
  register(api) {
    const pluginConfig = (api.pluginConfig ?? {}) as PluginConfig;
    const continuationOutbox = createContinuationOutbox({
      dataDir: String(pluginConfig.dataDir),
    });

    api.registerService({
      id: "personal-daily-continuation-recovery",
      async start() {
        try {
          await resumeContinuations({
            outbox: continuationOutbox,
            api,
          });
        } catch (error) {
          api.logger.warn(
            `personal-daily continuation recovery deferred: ${String(error)}`,
          );
        }
      },
    });

    api.on(
      "reply_dispatch",
      createFastReplyDispatchHandler({
        config: pluginConfig,
        continuationOutbox,
        logger: api.logger,
        prepareContinuationForReply,
        runPds,
      }),
      { priority: 100, timeoutMs: 4000 },
    );

    api.on("message_sent", async (event, ctx) => {
      const config = (api.pluginConfig ?? {}) as PluginConfig;
      if (event.success && ctx.sessionKey) {
        try {
          await handleDeliveredReply({
            outbox: continuationOutbox,
            api,
            sessionKey: ctx.sessionKey,
            content: event.content,
          });
        } catch (error) {
          api.logger.warn(
            `personal-daily continuation dispatch deferred: ${String(error)}`,
          );
        }
      }

      if (
        config.technicalCleanupEnabled === true &&
        ctx.channelId === "telegram" &&
        event.success &&
        ctx.sessionKey
      ) {
        try {
          await recordDeliveryAndCleanup(config, ctx.sessionKey);
        } catch (error) {
          api.logger.warn(`Codex thread hygiene deferred: ${String(error)}`);
        }
      }

      if (
        config.technicalCleanupEnabled === true &&
        ctx.channelId === "telegram" &&
        event.success &&
        event.messageId &&
        isTechnicalTelegramMessage(event.content)
      ) {
        try {
          await execFileAsync(
            "openclaw",
            [
              "message",
              "delete",
              "--channel",
              "telegram",
              "--target",
              String(event.to).replace(/^telegram:/u, ""),
              "--message-id",
              event.messageId,
            ],
            { timeout: 3000 },
          );
        } catch (error) {
          api.logger.warn(
            `technical Telegram cleanup failed: ${String(error)}`,
          );
        }
      }
    });
  },
});
