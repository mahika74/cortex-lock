import test from "node:test";
import assert from "node:assert/strict";
import { flowEvidence, avatarState, actionTitle } from "../src/presentation.js";

test("live success stays allowed even when the scenario is injection", () => {
  const run = { run_id: "run1", status: "COMPLETED", scenario: "injection" };
  const action = {
    action_id: "a1",
    decision: "ALLOW",
    execution_status: "EXECUTED",
  };
  const data = {
    actions: [action],
    events: [
      { run_id: "run1", event_type: "ACTION_EXECUTED", action_id: "a1" },
    ],
    memories: [],
  };
  assert.equal(flowEvidence(data, run).actionTone, "good");
  assert.equal(actionTitle(action), "Scoped action executed");
});

test("authorization alone does not become execution", () => {
  assert.equal(
    actionTitle({ decision: "ALLOW", execution_status: "NOT_EXECUTED" }),
    "Authorized, not executed",
  );
});

test("the flow does not invent an action when no action was recorded", () => {
  assert.equal(
    flowEvidence({ events: [], actions: [], memories: [] }, { run_id: "r1" })
      .latest,
    null,
  );
  assert.equal(actionTitle(null), "No decision recorded");
});

test("another run and a manual probe cannot be attributed to this agent run", () => {
  const data = {
    actions: [{ action_id: "probe", decision: "DENY" }],
    memories: [],
    events: [
      { run_id: null, action_id: "probe" },
      { run_id: "other", action_id: "probe" },
    ],
  };
  assert.equal(flowEvidence(data, { run_id: "selected" }).actions.length, 0);
});

test("quarantined current memory does not light up the approved path", () => {
  const data = {
    memories: [{ memory_id: "m1", status: "QUARANTINED", source_ids: ["s1"] }],
    actions: [],
    events: [
      { run_id: "r", event_type: "MEMORY_QUARANTINED", memory_ids: ["m1"] },
      { run_id: null, event_type: "DOCUMENT_RECEIVED", source_ids: ["s1"] },
    ],
  };
  const flow = flowEvidence(data, { run_id: "r" });
  assert.equal(flow.quarantined.length, 1);
  assert.equal(flow.approved.length, 0);
  assert.equal(flow.received.length, 1);
});

test("unrelated document events do not appear in the selected run flow", () => {
  const data = {
    memories: [],
    actions: [],
    events: [{ event_type: "DOCUMENT_RECEIVED", source_ids: ["unrelated"] }],
  };
  assert.equal(flowEvidence(data, { run_id: "r" }).received.length, 0);
});

test("decision order follows audit order, not arbitrary database UUID order", () => {
  const data = {
    memories: [],
    actions: [
      { action_id: "a", decision: "DENY" },
      { action_id: "z", decision: "ALLOW" },
    ],
    events: [
      { run_id: "r", action_id: "z" },
      { run_id: "r", action_id: "a" },
    ],
  };
  assert.equal(flowEvidence(data, { run_id: "r" }).latest.action_id, "a");
});

test("completed and stopped avatars do not imply active model processing", () => {
  assert.equal(avatarState(true, { status: "COMPLETED" }).moving, false);
  assert.equal(avatarState(true, { status: "FAILED" }).moving, false);
  assert.equal(avatarState(false, { status: "RUNNING" }).label, "Offline");
});

test("review state is explicit and does not animate execution", () => {
  const avatar = avatarState(true, { status: "WAITING_APPROVAL" });
  assert.equal(avatar.label, "Awaiting review");
  assert.equal(avatar.moving, false);
  assert.equal(
    actionTitle({ decision: "REQUIRE_APPROVAL" }),
    "Human review required",
  );
});
