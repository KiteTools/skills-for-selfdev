import test from "node:test";
import assert from "node:assert/strict";

import {
  handleDeliveredReply,
  prepareContinuationForReply,
  resumeContinuations,
} from "../continuation-runtime.mjs";

function route() {
  return {
    kind: "reply",
    text: "Помоги с кавером",
    messageId: "2174",
    workflow: "morning",
    pendingStage: "awaiting_control_answer",
  };
}

test("prepares the continuation with transition metadata", async () => {
  const calls = [];
  const outbox = {
    prepare: async (value) => {
      calls.push(value);
      return value;
    },
  };

  await prepareContinuationForReply({
    outbox,
    route: route(),
    response: {
      text: "17 задач",
      next_stage: "awaiting_task_choice",
    },
    sessionKey: "agent:main:telegram:direct:10001",
  });

  assert.deepEqual(calls, [
    {
      sessionKey: "agent:main:telegram:direct:10001",
      messageId: "2174",
      originalText: "Помоги с кавером",
      dailyReplyText: "17 задач",
      workflow: "morning",
      previousStage: "awaiting_control_answer",
      nextStage: "awaiting_task_choice",
    },
  ]);
});

test("dispatches only after the daily reply delivery is observed", async () => {
  const events = [];
  const entry = { id: "telegram:2174" };
  const outbox = {
    claimDelivered: async () => {
      events.push("claim");
      return entry;
    },
    complete: async () => events.push("complete"),
    fail: async () => events.push("fail"),
  };

  const handled = await handleDeliveredReply({
    outbox,
    api: {},
    sessionKey: "agent:main:telegram:direct:10001",
    content: "17 задач",
    dispatch: async (api, value) => {
      assert.equal(value, entry);
      events.push("dispatch");
    },
  });

  assert.equal(handled, true);
  assert.deepEqual(events, ["claim", "dispatch", "complete"]);
});

test("marks a rejected gateway continuation as failed", async () => {
  const events = [];
  const outbox = {
    claimDelivered: async () => ({ id: "telegram:2174" }),
    complete: async () => events.push("complete"),
    fail: async (id, error) => events.push(`fail:${id}:${error.message}`),
  };

  const handled = await handleDeliveredReply({
    outbox,
    api: {},
    sessionKey: "session",
    content: "reply",
    dispatch: async () => {
      throw new Error("gateway down");
    },
  });

  assert.equal(handled, true);
  assert.deepEqual(events, ["fail:telegram:2174:gateway down"]);
});

test("resumes delivered outbox entries after plugin restart", async () => {
  const events = [];
  const entries = [{ id: "one" }, { id: "two" }];
  const outbox = {
    listDispatchable: async () => entries,
    complete: async (id) => events.push(`complete:${id}`),
    fail: async (id) => events.push(`fail:${id}`),
  };

  await resumeContinuations({
    outbox,
    api: {},
    dispatch: async (api, entry) => events.push(`dispatch:${entry.id}`),
  });

  assert.deepEqual(events, [
    "dispatch:one",
    "complete:one",
    "dispatch:two",
    "complete:two",
  ]);
});
