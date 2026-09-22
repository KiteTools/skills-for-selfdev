import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { createContinuationOutbox } from "../continuation-outbox.mjs";

async function createFixture() {
  const dataDir = await mkdtemp(join(tmpdir(), "pds-continuation-"));
  const outbox = createContinuationOutbox({ dataDir });
  return { dataDir, outbox };
}

function candidate(overrides = {}) {
  return {
    sessionKey: "agent:main:telegram:direct:10001",
    messageId: "2174",
    originalText:
      "Сегодня хочу опубликовать ролик. Помоги с кавером и описанием",
    dailyReplyText: "Задачи:\n1. Встроить ЖС\n2. Опубликовать ролик",
    workflow: "morning",
    previousStage: "awaiting_control_answer",
    nextStage: "awaiting_task_choice",
    ...overrides,
  };
}

test("prepares one durable entry per Telegram message", async () => {
  const { dataDir, outbox } = await createFixture();
  const first = await outbox.prepare(candidate(), {
    now: "2026-07-26T09:34:00+01:00",
  });
  const second = await outbox.prepare(candidate(), {
    now: "2026-07-26T09:35:00+01:00",
  });

  assert.deepEqual(second, first);
  assert.equal(first.status, "prepared");
  assert.equal(
    first.idempotencyKey,
    "personal-daily-continuation:telegram:2174",
  );
  const stored = JSON.parse(
    await readFile(
      join(dataDir, "personal-daily-continuations.json"),
      "utf8",
    ),
  );
  assert.deepEqual(Object.keys(stored.entries), ["telegram:2174"]);
});

test("claims a delivered daily reply exactly once", async () => {
  const { outbox } = await createFixture();
  await outbox.prepare(candidate());

  const claimed = await outbox.claimDelivered({
    sessionKey: candidate().sessionKey,
    dailyReplyText: candidate().dailyReplyText,
  });
  const duplicate = await outbox.claimDelivered({
    sessionKey: candidate().sessionKey,
    dailyReplyText: candidate().dailyReplyText,
  });

  assert.equal(claimed.status, "daily_reply_delivered");
  assert.equal(duplicate, null);
});

test("persists completion and failure outcomes", async () => {
  const { outbox } = await createFixture();
  await outbox.prepare(candidate());
  const claimed = await outbox.claimDelivered({
    sessionKey: candidate().sessionKey,
    dailyReplyText: candidate().dailyReplyText,
  });
  const completed = await outbox.complete(claimed.id);
  assert.equal(completed.status, "completed");

  await outbox.prepare(candidate({ messageId: "2175" }));
  const failedClaim = await outbox.claimDelivered({
    sessionKey: candidate().sessionKey,
    dailyReplyText: candidate().dailyReplyText,
  });
  const failed = await outbox.fail(failedClaim.id, new Error("gateway down"));
  assert.equal(failed.status, "failed");
  assert.equal(failed.error, "gateway down");
});

test("a new outbox instance resumes delivered entries after restart", async () => {
  const { dataDir, outbox } = await createFixture();
  await outbox.prepare(candidate());
  await outbox.claimDelivered({
    sessionKey: candidate().sessionKey,
    dailyReplyText: candidate().dailyReplyText,
  });

  const restarted = createContinuationOutbox({ dataDir });
  const dispatchable = await restarted.listDispatchable();

  assert.equal(dispatchable.length, 1);
  assert.equal(dispatchable[0].messageId, "2174");
  assert.equal(dispatchable[0].status, "daily_reply_delivered");
});
