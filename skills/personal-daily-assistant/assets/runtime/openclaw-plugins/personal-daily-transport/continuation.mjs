export function buildContinuationPrompt(entry) {
  return [
    "[Personal Daily dual-intent continuation]",
    "daily_transition_already_handled=true",
    `workflow=${entry.workflow ?? "unknown"}`,
    `previous_stage=${entry.previousStage ?? "unknown"}`,
    `next_stage=${entry.nextStage ?? "unknown"}`,
    `telegram_message_id=${entry.messageId}`,
    "",
    "Переход Personal Daily для исходного сообщения уже выполнен и его",
    "детерминированный ответ уже доставлен пользователю.",
    "",
    "Правила этого продолжения:",
    "- не вызывай route-reply или route-callback и не записывай сообщение повторно;",
    "- не повторяй ответ Personal Daily и не утверждай, что что-либо сохранено;",
    "- найди в исходном тексте только самостоятельный запрос или вопрос;",
    "- если самостоятельного намерения нет, не отправляй видимый ответ;",
    "- если оно есть, продолжи его как обычный пользовательский запрос.",
    "",
    "Исходный текст пользователя:",
    entry.originalText,
  ].join("\n");
}

export function dispatchContinuation(api, entry) {
  return api.runtime.gateway.request("sessions.send", {
    key: entry.sessionKey,
    message: buildContinuationPrompt(entry),
    timeoutMs: 0,
    idempotencyKey: entry.idempotencyKey,
  });
}
