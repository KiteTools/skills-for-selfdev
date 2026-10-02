import test from "node:test";
import assert from "node:assert/strict";

import * as router from "../router.mjs";
import {
  CONTINUATION_PENDING_STAGES,
  FAST_PENDING_STAGES,
  extractPdCallback,
  isTechnicalTelegramMessage,
  normalizeReplyPayload,
  selectInboundRoute,
  shouldCreateContinuation,
} from "../router.mjs";

test("extracts only pd callbacks", () => {
  assert.equal(
    extractPdCallback("callback_data: pd:v:20260726:1200:p2"),
    "pd:v:20260726:1200:p2",
  );
  assert.equal(extractPdCallback("callback_data: other:value"), null);
});

test("claims only supported personal pending stages", () => {
  for (const stage of FAST_PENDING_STAGES) {
    assert.deepEqual(
      selectInboundRoute({
        content: "ответ",
        messageId: "2170",
        pending: { pending: true, stage },
      }),
      {
        kind: "reply",
        text: "ответ",
        messageId: "2170",
        pendingStage: stage,
        workflow: undefined,
      },
    );
  }
  assert.equal(
    selectInboundRoute({
      content: "свободный вопрос",
      messageId: "2171",
      pending: { pending: false },
    }),
    null,
  );
});

test("routes an explicit idea before any pending dialogue", () => {
  assert.deepEqual(
    selectInboundRoute({
      content: "Идея: собрать карту своих артефактов",
      messageId: "2401",
      pending: { pending: true, stage: "awaiting_evening_answer" },
    }),
    {
      kind: "capture",
      eventType: "idea",
      text: "Идея: собрать карту своих артефактов",
      messageId: "2401",
    },
  );
  assert.equal(
    selectInboundRoute({
      content: "",
      messageId: "2402",
      pending: { pending: false },
    }),
    null,
  );
});

test("creates continuations only for free-text pending replies", () => {
  for (const pendingStage of CONTINUATION_PENDING_STAGES) {
    assert.equal(
      shouldCreateContinuation({
        route: {
          kind: "reply",
          text: "Мои инструменты меня греют, останавливаться не планирую",
          messageId: "2170",
          pendingStage,
        },
      }),
      false,
    );
  }
  assert.equal(
    shouldCreateContinuation({
      route: {
        kind: "callback",
        callbackData: "pd:m:20260726:f03",
      },
    }),
    false,
  );
});

test("handles a Personal Daily reply through reply_dispatch without a model turn", async () => {
  assert.equal(typeof router.createFastReplyDispatchHandler, "function");

  const calls = [];
  let preparedContinuations = 0;
  const sent = [];
  const processed = [];
  const idleReasons = [];
  const handler = router.createFastReplyDispatchHandler({
    config: { ownerTelegramId: "10001" },
    continuationOutbox: {},
    logger: { warn() {} },
    prepareContinuationForReply: async () => {
      preparedContinuations += 1;
    },
    runPds: async (_config, args) => {
      calls.push(args);
      if (args[0] === "pending") {
        return {
          pending: true,
          stage: "awaiting_morning_answer",
          workflow: "morning",
        };
      }
      return {
        workflow: "morning",
        next_stage: "awaiting_control_answer",
        text:
          "Как сегодня заметишь, что продолжаешь цель только из-за уже вложенных сил?",
      };
    },
  });

  const result = await handler(
    {
      originatingChannel: "telegram",
      sessionKey: "agent:main:telegram:direct:10001",
      ctx: {
        Surface: "telegram",
        SenderId: "10001",
        BodyForCommands: "Соберу свои артефакты",
        MessageSid: "2308",
      },
    },
    {
      dispatcher: {
        sendFinalReply(payload) {
          sent.push(payload);
          return true;
        },
        getQueuedCounts() {
          return { final: sent.length, tool: 0 };
        },
      },
      recordProcessed(outcome, details) {
        processed.push([outcome, details]);
      },
      markIdle(reason) {
        idleReasons.push(reason);
      },
    },
  );

  assert.deepEqual(calls[0], ["pending"]);
  assert.equal(calls[1][0], "route-reply");
  assert.equal(preparedContinuations, 0);
  assert.deepEqual(sent, [
    {
      text:
        "Как сегодня заметишь, что продолжаешь цель только из-за уже вложенных сил?",
    },
  ]);
  assert.deepEqual(processed, [
    ["completed", { reason: "personal-daily-fast-route" }],
  ]);
  assert.deepEqual(idleReasons, ["personal_daily_fast_route"]);
  assert.deepEqual(result, {
    handled: true,
    queuedFinal: true,
    counts: { final: 1, tool: 0 },
  });
});

test("captures an explicit idea without pending lookup or a model turn", async () => {
  const calls = [];
  const sent = [];
  let preparedContinuations = 0;
  const handler = router.createFastReplyDispatchHandler({
    config: { ownerTelegramId: "10001" },
    continuationOutbox: {},
    logger: { warn() {} },
    prepareContinuationForReply: async () => {
      preparedContinuations += 1;
    },
    runPds: async (_config, args) => {
      calls.push(args);
      return { status: "recorded", text: "Идея сохранена." };
    },
  });

  const result = await handler(
    {
      originatingChannel: "telegram",
      sessionKey: "agent:main:telegram:direct:10001",
      ctx: {
        Surface: "telegram",
        SenderId: "10001",
        BodyForCommands: "Идея: собрать карту своих артефактов",
        MessageSid: "2401",
      },
    },
    {
      dispatcher: {
        sendFinalReply(payload) {
          sent.push(payload);
          return true;
        },
        getQueuedCounts() {
          return { final: sent.length, tool: 0 };
        },
      },
      recordProcessed() {},
      markIdle() {},
    },
  );

  assert.equal(result.handled, true);
  assert.equal(preparedContinuations, 0);
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], "capture");
  assert.deepEqual(calls[0].slice(1, 3), ["--type", "idea"]);
  assert.equal(calls[0].at(-2), "--message-id");
  assert.equal(calls[0].at(-1), "2401");
  assert.deepEqual(sent, [{ text: "Идея сохранена." }]);
});

test("sends the deterministic reply even when continuation staging fails", async () => {
  const sent = [];
  const handler = router.createFastReplyDispatchHandler({
    config: { ownerTelegramId: "10001" },
    continuationOutbox: {},
    logger: { warn() {} },
    prepareContinuationForReply: async () => {
      throw new Error("outbox unavailable");
    },
    runPds: async (_config, args) => {
      if (args[0] === "pending") {
        return {
          pending: true,
          stage: "awaiting_task_choice",
          workflow: "morning",
        };
      }
      return {
        workflow: "morning",
        next_stage: "awaiting_control_answer",
        text: "Контрольный вопрос.",
      };
    },
  });

  const result = await handler(
    {
      originatingChannel: "telegram",
      sessionKey: "agent:main:telegram:direct:10001",
      ctx: {
        Surface: "telegram",
        SenderId: "10001",
        BodyForCommands: "Помоги выбрать задачу и подготовь обложку",
        MessageSid: "2309",
      },
    },
    {
      dispatcher: {
        sendFinalReply(payload) {
          sent.push(payload);
          return true;
        },
        getQueuedCounts() {
          return { final: sent.length, tool: 0 };
        },
      },
      recordProcessed() {},
      markIdle() {},
    },
  );

  assert.deepEqual(sent, [{ text: "Контрольный вопрос." }]);
  assert.equal(result.handled, true);
});

test("does not continue short valid task choices", () => {
  for (const text of ["0", "1", "9", "10", "17"]) {
    assert.equal(
      shouldCreateContinuation({
        route: {
          kind: "reply",
          text,
          messageId: "2170",
          pendingStage: "awaiting_task_choice",
        },
      }),
      false,
    );
  }
  assert.equal(
    shouldCreateContinuation({
      route: {
        kind: "reply",
        text: "Помоги выбрать задачу и подготовь обложку",
        messageId: "2170",
        pendingStage: "awaiting_task_choice",
      },
    }),
    true,
  );
});

test("does not start a model continuation for several arbitrary task numbers", () => {
  for (const text of ["18 и 21", "18, 21", "18\n21"]) {
    assert.equal(
      shouldCreateContinuation({
        route: {
          kind: "reply",
          text,
          messageId: "2501",
          pendingStage: "awaiting_task_choice",
        },
      }),
      false,
    );
  }
});

test("converts deterministic buttons to OpenClaw presentation", () => {
  assert.deepEqual(
    normalizeReplyPayload({
      text: "Ретро сохранено.",
      buttons: [
        {
          text: "Добавить успех",
          callback_data: "pd:e:2026-07-26:addsuccess",
        },
      ],
    }),
    {
      text: "Ретро сохранено.",
      presentation: {
        blocks: [
          {
            type: "buttons",
            buttons: [
              {
                label: "Добавить успех",
                value: "pd:e:2026-07-26:addsuccess",
              },
            ],
          },
        ],
      },
    },
  );
});

test("matches only the approved technical Telegram notices", () => {
  assert.equal(isTechnicalTelegramMessage("🛠️ Bash print lines 1-20"), true);
  assert.equal(isTechnicalTelegramMessage("🧠 Memory Search heartbeat"), true);
  assert.equal(isTechnicalTelegramMessage("⏰ Cron доставка"), true);
  assert.equal(
    isTechnicalTelegramMessage(
      "Полезный ответ со словом Bash, который должен остаться",
    ),
    false,
  );
});

test('explicit Ten feedback is opt-in and never consumes numeric retrospective replies', () => {
  const pending = { pending: true, stage: 'awaiting_evening_answer' };
  assert.equal(selectInboundRoute({ content: '/ход 2,4', messageId: 'synthetic', pending, eveningTenEnabled: true }).kind, 'ten-feedback');
  assert.equal(selectInboundRoute({ content: '2,4', messageId: 'synthetic', pending, eveningTenEnabled: true }).kind, 'reply');
  assert.equal(selectInboundRoute({ content: '/ход 2', messageId: 'synthetic', pending, eveningTenEnabled: false }), null);
});

test('explicit Ten and activity commands bypass pending and never request a continuation', async () => {
  for (const [text, kind] of [['/ход 2,4', 'ten-feedback'], ['/занятие начало Пример', 'activity-command']]) {
    const calls = [];
    const handler = router.createFastReplyDispatchHandler({
      config: { ownerTelegramId: 'synthetic-owner', eveningTenEnabled: true }, logger: { warn: assert.fail },
      continuationOutbox: {}, prepareContinuationForReply: async () => assert.fail('no model continuation'),
      runPds: async (_, args) => { calls.push(args); return { text: 'Synthetic acknowledgement' }; },
    });
    const result = await handler({ originatingChannel: 'telegram', sessionKey: 'synthetic-session', ctx: { SenderId: 'synthetic-owner', BodyForCommands: text, MessageSid: 'synthetic-message' } }, {
      dispatcher: { sendFinalReply: () => true, getQueuedCounts: () => ({ final: 1 }) }, recordProcessed() {}, markIdle() {},
    });
    assert.equal(result.handled, true);
    assert.equal(calls.length, 1);
    assert.equal(calls[0][0], kind);
    assert.equal(Buffer.from(calls[0][2], 'base64').toString('utf8'), text);
  }
});

test('morning intentions do not authorize agent work through embedded wording', () => {
  for (const text of [
    'Хочу, чтобы прототип помог людям учиться',
    'Сегодня понять, как создать полезный результат?',
    'Собрать памятку с разделом «Помоги выбрать задачу»',
    'Показать задачи',
  ]) {
    assert.equal(shouldCreateContinuation({route: {
      kind: 'reply', text, pendingStage: 'awaiting_task_choice', messageId: 'synthetic-intent',
    }}), false, text);
  }
});

test('a direct request remains distinct from recording a morning intention', () => {
  assert.equal(shouldCreateContinuation({route: {
    kind: 'reply', text: 'Пожалуйста, помоги сравнить две задачи',
    pendingStage: 'awaiting_task_choice', messageId: 'synthetic-request',
  }}), true);
  assert.equal(selectInboundRoute({
    content: 'Подготовь план прототипа', messageId: 'synthetic-separate-request',
    pending: {pending: false},
  }), null, 'outside the daily interaction ordinary requests stay with the normal agent');
});
