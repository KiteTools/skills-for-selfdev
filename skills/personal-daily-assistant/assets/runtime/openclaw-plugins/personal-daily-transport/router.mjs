export const FAST_PENDING_STAGES = new Set([
  "awaiting_morning_answer",
  "awaiting_control_answer",
  "awaiting_task_choice",
  "awaiting_viability_context",
  "awaiting_activity_gap",
  "awaiting_evening_answer",
  "awaiting_success_action",
  "awaiting_success_reply",
  "awaiting_idea_choice",
  "awaiting_idea_result",
]);

export const CONTINUATION_PENDING_STAGES = new Set([
  "awaiting_morning_answer",
  "awaiting_control_answer",
  "awaiting_task_choice",
  "awaiting_viability_context",
  "awaiting_activity_gap",
  "awaiting_evening_answer",
  "awaiting_success_reply",
  "awaiting_idea_choice",
  "awaiting_idea_result",
]);

export function extractPdCallback(content) {
  const match = String(content ?? "").match(
    /(?:^|\s)callback_data:\s*(pd:[^\s]+)/u,
  );
  return match?.[1] ?? null;
}

export function selectInboundRoute({ content, messageId, pending, eveningTenEnabled = false }) {
  const callbackData = extractPdCallback(content);
  if (callbackData) {
    return { kind: "callback", callbackData };
  }
  const text = String(content || "").trim();
  if (/^\/(?:ход|десятка)(?:\s|$)/iu.test(text)) {
    return eveningTenEnabled && messageId ? { kind: "ten-feedback", text, messageId: String(messageId) } : null;
  }
  if (/^\/занятие(?:\s|$)/iu.test(text) && messageId) {
    return { kind: "activity-command", text, messageId: String(messageId) };
  }
  if (
    messageId &&
    /^идея(?:\s*[:—–-]|\.)\s*\S/iu.test(text)
  ) {
    return {
      kind: "capture",
      eventType: "idea",
      text,
      messageId: String(messageId),
    };
  }
  if (
    !pending?.pending ||
    !FAST_PENDING_STAGES.has(pending.stage) ||
    !messageId
  ) {
    return null;
  }
  if (!text) {
    return null;
  }
  return {
    kind: "reply",
    text,
    messageId: String(messageId),
    pendingStage: pending.stage,
    workflow: pending.workflow,
  };
}

export function shouldCreateContinuation({ route }) {
  if (
    route?.kind !== "reply" ||
    !CONTINUATION_PENDING_STAGES.has(route.pendingStage)
  ) {
    return false;
  }
  if (route.pendingStage === "awaiting_task_choice") {
    // A recorded intention is not permission to execute it. Only an explicit
    // request addressed to the assistant can open an additional model turn.
    return /^(?:пожалуйста[,\s]+)?(?:помоги|сделай|подготовь|разберись|создай|найди|проверь|объясни|ответь|посмотри|давай)(?=$|[\s,.:!?])/iu.test(
      route.text.trim(),
    );
  }
  return (
    /[?？]/u.test(route.text) ||
    /(?:помоги|сделай|подготовь|разберись|создай|найди|проверь|объясни|ответь|посмотри|давай)/iu.test(
      route.text,
    ) ||
    /хочу,\s+чтобы/iu.test(route.text)
  );
}

export function normalizeReplyPayload(response) {
  const payload = { text: response.text };
  if (!Array.isArray(response.buttons) || response.buttons.length === 0) {
    return payload;
  }
  payload.presentation = {
    blocks: [
      {
        type: "buttons",
        buttons: response.buttons.map((button) => ({
          label: button.text,
          value: button.callback_data,
        })),
      },
    ],
  };
  return payload;
}

export function createFastReplyDispatchHandler({
  config,
  continuationOutbox,
  logger,
  prepareContinuationForReply,
  runPds,
}) {
  return async (event, hookContext) => {
    const inbound = event?.ctx ?? {};
    const channelId =
      event?.originatingChannel ??
      inbound.OriginatingChannel ??
      inbound.Surface ??
      inbound.Provider;
    if (
      channelId !== "telegram" ||
      String(inbound.SenderId ?? "") !==
        String(config.ownerTelegramId ?? "")
    ) {
      return;
    }

    const content = String(
      inbound.BodyForCommands ??
        inbound.CommandBody ??
        inbound.RawBody ??
        inbound.Body ??
        "",
    );
    const messageId =
      inbound.MessageSidFull ?? inbound.MessageSid ?? inbound.MessageSidLast;
    const sessionKey = event?.sessionKey ?? inbound.SessionKey;

    try {
      const callbackRoute = selectInboundRoute({
        content,
        messageId,
        pending: { pending: false },
        eveningTenEnabled: config.eveningTenEnabled === true,
      });
      let route = callbackRoute;
      let response;
      if (route?.kind === "callback") {
        response = await runPds(config, [
          "route-callback",
          "--data",
          route.callbackData,
        ]);
      } else if (route?.kind === "ten-feedback" || route?.kind === "activity-command") {
        response = await runPds(config, [route.kind, "--text-base64", Buffer.from(route.text, "utf8").toString("base64"), "--message-id", route.messageId]);
      } else if (route?.kind === "capture") {
        response = await runPds(config, [
          "capture",
          "--type",
          route.eventType,
          "--text-base64",
          Buffer.from(route.text, "utf8").toString("base64"),
          "--message-id",
          route.messageId,
        ]);
      } else {
        const pending = await runPds(config, ["pending"]);
        route = selectInboundRoute({
          content,
          messageId,
          pending,
          eveningTenEnabled: config.eveningTenEnabled === true,
        });
        if (!route || route.kind !== "reply") {
          return;
        }
        response = await runPds(config, [
          "route-reply",
          "--text-base64",
          Buffer.from(route.text, "utf8").toString("base64"),
          "--message-id",
          route.messageId,
        ]);
      }

      if (
        sessionKey &&
        shouldCreateContinuation({ route })
      ) {
        try {
          await prepareContinuationForReply({
            outbox: continuationOutbox,
            route,
            response,
            sessionKey,
          });
        } catch (error) {
          logger?.warn?.(
            `personal-daily continuation staging failed: ${error}`,
          );
        }
      }

      const queuedFinal = hookContext.dispatcher.sendFinalReply(
        normalizeReplyPayload(response),
      );
      hookContext.recordProcessed("completed", {
        reason: "personal-daily-fast-route",
      });
      hookContext.markIdle("personal_daily_fast_route");
      return {
        handled: true,
        queuedFinal,
        counts: hookContext.dispatcher.getQueuedCounts(),
      };
    } catch (error) {
      logger.warn(
        `personal-daily-transport fast path unavailable: ${String(error)}`,
      );
      return;
    }
  };
}

export function isTechnicalTelegramMessage(content) {
  const text = String(content ?? "").trim();
  return (
    /^🛠️\s+Bash\b/u.test(text) ||
    /^🧠\s+Memory Search\b/u.test(text) ||
    /^⏰\s+Cron\b/u.test(text) ||
    /\bBash print lines \d+-\d+ from\b/u.test(text)
  );
}
