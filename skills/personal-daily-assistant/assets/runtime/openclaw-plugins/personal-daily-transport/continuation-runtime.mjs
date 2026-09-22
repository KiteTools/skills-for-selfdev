import { dispatchContinuation } from "./continuation.mjs";

export function prepareContinuationForReply({
  outbox,
  route,
  response,
  sessionKey,
}) {
  return outbox.prepare({
    sessionKey,
    messageId: route.messageId,
    originalText: route.text,
    dailyReplyText: response.text,
    workflow: route.workflow,
    previousStage: route.pendingStage,
    nextStage: response.next_stage,
  });
}

async function dispatchAndRecord({
  outbox,
  api,
  entry,
  dispatch = dispatchContinuation,
}) {
  try {
    await dispatch(api, entry);
    await outbox.complete(entry.id);
  } catch (error) {
    await outbox.fail(entry.id, error);
  }
}

export async function handleDeliveredReply({
  outbox,
  api,
  sessionKey,
  content,
  dispatch = dispatchContinuation,
}) {
  const entry = await outbox.claimDelivered({
    sessionKey,
    dailyReplyText: content,
  });
  if (!entry) return false;
  await dispatchAndRecord({ outbox, api, entry, dispatch });
  return true;
}

export async function resumeContinuations({
  outbox,
  api,
  dispatch = dispatchContinuation,
}) {
  const entries = await outbox.listDispatchable();
  for (const entry of entries) {
    await dispatchAndRecord({ outbox, api, entry, dispatch });
  }
}
