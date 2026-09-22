import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { join } from "node:path";

const FILE_NAME = "personal-daily-continuations.json";

function emptyState() {
  return { schemaVersion: 1, entries: {} };
}

function errorText(error) {
  return error instanceof Error ? error.message : String(error);
}

export function createContinuationOutbox({ dataDir }) {
  const path = join(dataDir, FILE_NAME);
  let mutation = Promise.resolve();

  async function readState() {
    try {
      return JSON.parse(await readFile(path, "utf8"));
    } catch (error) {
      if (error?.code === "ENOENT") return emptyState();
      throw error;
    }
  }

  async function writeState(state) {
    await mkdir(dataDir, { recursive: true, mode: 0o700 });
    const temporaryPath = `${path}.tmp`;
    await writeFile(temporaryPath, `${JSON.stringify(state)}\n`, {
      encoding: "utf8",
      mode: 0o600,
    });
    await rename(temporaryPath, path);
  }

  function mutate(operation) {
    const result = mutation.then(async () => {
      const state = await readState();
      const value = await operation(state);
      await writeState(state);
      return value;
    });
    mutation = result.catch(() => {});
    return result;
  }

  async function prepare(candidate, options = {}) {
    return mutate(async (state) => {
      const id = `telegram:${candidate.messageId}`;
      if (state.entries[id]) return state.entries[id];
      const now = options.now ?? new Date().toISOString();
      const entry = {
        id,
        status: "prepared",
        sessionKey: candidate.sessionKey,
        messageId: candidate.messageId,
        originalText: candidate.originalText,
        dailyReplyText: candidate.dailyReplyText,
        workflow: candidate.workflow,
        previousStage: candidate.previousStage,
        nextStage: candidate.nextStage,
        idempotencyKey: `personal-daily-continuation:${id}`,
        createdAt: now,
        updatedAt: now,
      };
      state.entries[id] = entry;
      return entry;
    });
  }

  async function claimDelivered({ sessionKey, dailyReplyText }, options = {}) {
    return mutate(async (state) => {
      const entry = Object.values(state.entries)
        .filter(
          (item) =>
            item.status === "prepared" &&
            item.sessionKey === sessionKey &&
            item.dailyReplyText === dailyReplyText,
        )
        .sort((left, right) => left.createdAt.localeCompare(right.createdAt))[0];
      if (!entry) return null;
      entry.status = "daily_reply_delivered";
      entry.updatedAt = options.now ?? new Date().toISOString();
      return entry;
    });
  }

  async function setTerminal(id, status, error, options = {}) {
    return mutate(async (state) => {
      const entry = state.entries[id];
      if (!entry) return null;
      entry.status = status;
      entry.updatedAt = options.now ?? new Date().toISOString();
      if (error) entry.error = errorText(error);
      else delete entry.error;
      return entry;
    });
  }

  async function listDispatchable() {
    await mutation;
    const state = await readState();
    return Object.values(state.entries)
      .filter((entry) => entry.status === "daily_reply_delivered")
      .sort((left, right) => left.createdAt.localeCompare(right.createdAt));
  }

  return {
    path,
    prepare,
    claimDelivered,
    complete(id, options) {
      return setTerminal(id, "completed", null, options);
    },
    fail(id, error, options) {
      return setTerminal(id, "failed", error, options);
    },
    listDispatchable,
  };
}
