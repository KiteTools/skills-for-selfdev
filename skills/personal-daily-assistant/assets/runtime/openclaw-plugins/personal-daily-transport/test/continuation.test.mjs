import test from "node:test";
import assert from "node:assert/strict";

import {
  buildContinuationPrompt,
  dispatchContinuation,
} from "../continuation.mjs";

function entry() {
  return {
    id: "telegram:2174",
    sessionKey: "agent:main:telegram:direct:10001",
    messageId: "2174",
    originalText:
      "Сегодня хочу опубликовать ролик. Помоги с кавером и описанием",
    workflow: "morning",
    previousStage: "awaiting_control_answer",
    nextStage: "awaiting_task_choice",
    idempotencyKey: "personal-daily-continuation:telegram:2174",
  };
}

test("builds a continuation prompt with the bypass contract", () => {
  const prompt = buildContinuationPrompt(entry());

  assert.match(prompt, /daily_transition_already_handled=true/u);
  assert.match(prompt, /не вызывай route-reply или route-callback/u);
  assert.match(prompt, /не отправляй видимый ответ/u);
  assert.match(prompt, /Помоги с кавером и описанием/u);
  assert.match(prompt, /awaiting_control_answer/u);
});

test("dispatches the continuation to the same session idempotently", async () => {
  const calls = [];
  const api = {
    runtime: {
      gateway: {
        request: async (...args) => {
          calls.push(args);
          return { ok: true, runId: "run-1" };
        },
      },
    },
  };

  const result = await dispatchContinuation(api, entry());

  assert.deepEqual(result, { ok: true, runId: "run-1" });
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], "sessions.send");
  assert.equal(calls[0][1].key, entry().sessionKey);
  assert.equal(calls[0][1].timeoutMs, 0);
  assert.equal(calls[0][1].idempotencyKey, entry().idempotencyKey);
  assert.match(calls[0][1].message, /daily_transition_already_handled=true/u);
});
