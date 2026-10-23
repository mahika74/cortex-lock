// Presentation is derived from observed records, never from the scenario selected.
export const humanize = (value) =>
  String(value || "Not recorded")
    .replaceAll("_", " ")
    .toLowerCase();
export const shortId = (value) =>
  value ? value.slice(0, 8) + "…" + value.slice(-6) : "Not recorded";

export function avatarState(connected, run, events = []) {
  if (!connected) return { label: "Offline", tone: "neutral", moving: false };
  if (!run)
    return { label: "Ready for a task", tone: "neutral", moving: false };
  if (run.status === "WAITING_APPROVAL")
    return { label: "Awaiting review", tone: "warn", moving: false };
  if (run.status === "COMPLETED")
    return { label: "Run completed", tone: "good", moving: false };
  if (run.status === "FAILED")
    return { label: "Run stopped", tone: "bad", moving: false };
  if (run.status === "QUEUED")
    return { label: "Task queued", tone: "neutral", moving: true };
  const latest = events.filter((e) => e.run_id === run.run_id).at(-1);
  return {
    label: latest?.event_type?.startsWith("MEMORY_")
      ? "Processing scoped context"
      : latest?.event_type?.startsWith("ACTION_")
        ? "Processing actions"
        : "Processing task",
    tone: "good",
    moving: true,
  };
}

export function flowEvidence(data, run) {
  const allEvents = data.events || [];
  const events = run
    ? allEvents.filter((e) => e.run_id === run.run_id)
    : allEvents;
  const memoryIds = new Set(events.flatMap((e) => e.memory_ids || []));
  const memories = run
    ? (data.memories || []).filter((m) => memoryIds.has(m.memory_id))
    : data.memories || [];
  const actionIds = events.filter((e) => e.action_id).map((e) => e.action_id);
  const records = new Map((data.actions || []).map((a) => [a.action_id, a]));
  const unique = [...new Set(actionIds)];
  // Preserve audit event ordering; action UUIDs have no chronological meaning.
  const actions = unique.map((id) => records.get(id)).filter(Boolean);
  const latest = actions.at(-1) || null;
  const quarantined = memories.filter((m) => m.status === "QUARANTINED");
  const approved = memories.filter((m) => m.status === "APPROVED");
  const sourceIds = new Set(memories.flatMap((m) => m.source_ids || []));
  const received = allEvents.filter(
    (e) =>
      e.event_type === "DOCUMENT_RECEIVED" &&
      (e.source_ids || []).some((id) => sourceIds.has(id)),
  );
  const actionTone =
    latest?.decision === "DENY"
      ? "bad"
      : latest?.execution_status === "EXECUTED"
        ? "good"
        : latest?.decision === "REQUIRE_APPROVAL"
          ? "warn"
          : "neutral";
  return {
    events,
    memories,
    actions,
    latest,
    quarantined,
    approved,
    received,
    actionTone,
  };
}

export function actionTitle(action) {
  if (!action) return "No decision recorded";
  if (action.decision === "DENY") return "Request blocked";
  if (action.execution_status === "EXECUTED") return "Scoped action executed";
  if (action.decision === "REQUIRE_APPROVAL") return "Human review required";
  return "Authorized, not executed";
}
