import React, { useMemo, useId } from "react";
import { Icon, Badge, Modal } from "./ui.jsx";
import {
  actionTitle,
  avatarState,
  flowEvidence,
  humanize,
  shortId,
} from "./presentation.js";

export function CortexAvatar({
  mini = false,
  status = "ready",
  moving = false,
}) {
  const gradientId = useId();
  return (
    <span
      className={`cortex-avatar ${mini ? "mini" : ""} ${moving ? "processing" : ""} ${status}`}
      aria-hidden="true"
    >
      <svg viewBox="0 0 160 160" fill="none">
        <defs>
          <linearGradient
            id={gradientId}
            x1="40"
            y1="20"
            x2="125"
            y2="140"
            gradientUnits="userSpaceOnUse"
          >
            <stop stopColor="#d0c9ff" />
            <stop offset=".5" stopColor="#8d79ff" />
            <stop offset="1" stopColor="#42d8d6" />
          </linearGradient>
        </defs>
        <circle
          className="avatar-orbit outer"
          cx="80"
          cy="80"
          r="72"
          stroke="currentColor"
          strokeWidth="1"
        />
        <circle
          className="avatar-orbit segmented"
          cx="80"
          cy="80"
          r="64"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeDasharray="65 10 28 10"
        />
        <circle cx="80" cy="80" r="55" stroke="#9d8aff" strokeOpacity=".16" />
        <g
          className="avatar-core"
          stroke={`url(#${gradientId})`}
          strokeWidth="1.5"
          strokeLinejoin="round"
        >
          <path
            d="M80 27 116 47 126 88 102 125 64 134 35 100 35 61Z"
            fill="#7e62ef"
            fillOpacity=".46"
          />
          <path
            d="m80 27-10 37 46-17-20 39 30 2-40 23 16 14-38 9 22-23-51-11 35-36-35-3 45-34Z"
            fill="#b1a0ff"
            fillOpacity=".28"
          />
          <path d="M80 27 70 64 116 47Z" fill="#bdb0ff" fillOpacity=".5" />
          <path
            d="m70 64 26 22-10 25-51-11Z"
            fill="#8471f4"
            fillOpacity=".36"
          />
          <path d="m86 111 40-23-24 37-38 9Z" fill="#5cc8ef" fillOpacity=".3" />
          <path d="m35 61 61 25-26-22 16 47-51-11m61-14-10 25 30-64M80 27l16 59 6 39M64 134l6-70" />
          <path d="m35 61 51 50 40-23M70 64l-6 70" strokeOpacity=".65" />
        </g>
        <circle cx="80" cy="8" r="3" fill="currentColor" />
      </svg>
    </span>
  );
}

function FlowNode({
  className,
  icon,
  title,
  subtitle,
  tone = "neutral",
  onClick,
  children,
}) {
  return (
    <button
      className={`flow-node ${className} ${tone}`}
      onClick={onClick}
      disabled={!onClick}
    >
      <span className="node-icon">
        <Icon name={icon} size={23} />
      </span>
      <span>
        <strong>{title}</strong>
        <small>{subtitle}</small>
        {children}
      </span>
    </button>
  );
}

function DecisionCard({ selection, task, onOpen }) {
  const record = selection?.record;
  const memory = selection?.kind === "memory";
  const status = memory ? record.status : record?.decision;
  return (
    <aside className="panel decision-card">
      <div className="section-heading">
        <div>
          <span className="eyebrow">THE WHY BEHIND THE WHAT</span>
          <h2>Decision details</h2>
        </div>
        <span className="corner-marker" />
      </div>
      {record ? (
        <>
          <div className="decision-verdict">
            <Badge value={status} />
            <h3>
              {memory
                ? record.status === "QUARANTINED"
                  ? "Kept outside memory."
                  : "Eligible for scoped storage."
                : actionTitle(record)}
            </h3>
          </div>
          <dl className="decision-facts">
            <div>
              <dt>{memory ? "Memory" : "Tool"}</dt>
              <dd>
                {memory ? shortId(record.memory_id) : humanize(record.tool)}
              </dd>
            </div>
            {!memory && record.args?.resource_id && (
              <div>
                <dt>Resource</dt>
                <dd>{record.args.resource_id}</dd>
              </div>
            )}
            {!memory && record.args?.recipient && (
              <div>
                <dt>Recipient</dt>
                <dd>{record.args.recipient}</dd>
              </div>
            )}
            {!memory && (
              <div>
                <dt>Execution</dt>
                <dd>
                  <Badge value={record.execution_status} />
                </dd>
              </div>
            )}
            <div>
              <dt>Scope</dt>
              <dd>
                {task?.allowed_resource_ids.join(", ") || "No task selected"}
              </dd>
            </div>
          </dl>
          <p className="decision-explanation">
            {memory
              ? record.reason_codes.length
                ? record.reason_codes.map(humanize).join(" · ")
                : "Storage eligibility does not verify factual accuracy."
              : record.explanation}
          </p>
          <div className="decision-reasons">
            {record.reason_codes?.map((reason) => (
              <code key={reason}>{reason}</code>
            ))}
          </div>
          <button
            className="button secondary full"
            onClick={() => onOpen(selection)}
          >
            <Icon name="document" size={17} />
            Open evidence drawer
            <Icon name="arrow" size={15} />
          </button>
        </>
      ) : (
        <div className="decision-empty">
          <span className="outline-shield">
            <Icon name="check" size={35} />
          </span>
          <h3>Evidence, not assumptions.</h3>
          <p>
            Select a recorded decision to see its source, scope, and outcome.
            Your first run brings this panel to life.
          </p>
          <div className="empty-fact">
            <span>Identity</span>
            <span>Task scope</span>
            <span>Provenance</span>
          </div>
        </div>
      )}
    </aside>
  );
}

export default function Cockpit({
  task,
  run,
  data,
  mode,
  setMode,
  scenario,
  setScenario,
  template,
  setTemplate,
  connected,
  health,
  busy,
  locked,
  expired,
  startRun,
  runCurrentTask,
  resume,
  createTask,
  connect,
  probe,
  onView,
  onMemoryView,
  onEvidence,
  pending,
}) {
  const flow = useMemo(() => flowEvidence(data, run), [data, run]);
  const avatar = avatarState(connected, run, data.events);
  const selection = flow.latest
    ? { kind: "action", record: flow.latest }
    : flow.quarantined[0]
      ? { kind: "memory", record: flow.quarantined[0] }
      : flow.memories.at(-1)
        ? { kind: "memory", record: flow.memories.at(-1) }
        : null;
  const selectedScenario =
    template === "SALES_EXTERNAL_REVIEW" ? "approval" : scenario;
  const scenarios = [
    {
      id: "normal",
      icon: "document",
      name: "Complete a task",
      label: "01 / LEGITIMATE WORKFLOW",
      text: "Sales report. Intended recipient. Clear boundaries.",
    },
    {
      id: "injection",
      icon: "lock",
      name: "Test memory poisoning",
      label: "02 / ADVERSARIAL INPUT",
      text: "An untrusted document attempts to rewrite authority.",
    },
    {
      id: "approval",
      icon: "check",
      name: "Request human approval",
      label: "03 / HUMAN OVERSIGHT",
      text: "A scoped external transfer waits for a reviewer.",
    },
  ];
  const recent = flow.events.slice(-5);
  const revealMemory = () => {
    if (flow.memories.length)
      onEvidence({
        kind: "memory",
        record: flow.quarantined[0] || flow.memories.at(-1),
      });
    else onView("memory");
  };

  return (
    <div className="cockpit page-enter">
      <div
        className="scenario-grid"
        role="group"
        aria-label="Choose a protection scenario"
      >
        {scenarios.map((item) => (
          <button
            key={item.id}
            disabled={locked}
            aria-pressed={selectedScenario === item.id}
            className={`scenario-card ${item.id} ${selectedScenario === item.id ? "selected" : ""}`}
            onClick={() => {
              setTemplate(
                item.id === "approval"
                  ? "SALES_EXTERNAL_REVIEW"
                  : "SALES_INTERNAL",
              );
              setScenario(item.id === "injection" ? "injection" : "normal");
            }}
          >
            <span className="scenario-icon">
              <Icon name={item.icon} size={21} />
            </span>
            <span>
              <small>{item.label}</small>
              <strong>{item.name}</strong>
              <p>{item.text}</p>
            </span>
            <span className="scenario-check">
              {selectedScenario === item.id ? "✓" : "↗"}
            </span>
          </button>
        ))}
      </div>

      <div className="execution-toolbar">
        <div className="mode-switch" role="group" aria-label="Execution mode">
          {["LIVE", "REPLAY"].map((m) => (
            <button
              key={m}
              disabled={locked}
              aria-pressed={mode === m}
              className={mode === m ? "selected" : ""}
              onClick={() => setMode(m)}
            >
              <span className={m === "LIVE" ? "mode-dot" : "replay-dot"} />
              {m === "LIVE" ? "Live agent" : "Scripted replay"}
            </button>
          ))}
        </div>
        <p>
          {mode === "LIVE"
            ? "Gemini proposes. The gateway decides."
            : "Deterministic fixtures. No model calls."}
        </p>
        <button
          className="button primary run-primary"
          disabled={
            !connected ||
            locked ||
            (mode === "LIVE" && !health?.model_configured)
          }
          onClick={startRun}
        >
          <Icon name={locked ? "refresh" : "play"} size={17} />
          {busy
            ? "Working…"
            : ["QUEUED", "RUNNING"].includes(run?.status)
              ? "Run in progress…"
              : "Run protected scenario"}
        </button>
        {!connected && (
          <button className="button secondary" onClick={connect}>
            Connect workspace
          </button>
        )}
      </div>
      {connected && mode === "LIVE" && !health?.model_configured && (
        <div className="alert error">
          Gemini is not configured. Choose replay or configure the backend.
        </div>
      )}
      {run?.error && (
        <div className="alert error" role="alert">
          <Icon name="activity" size={17} />
          <span>
            Run stopped: {run.error}. Inspect the recorded evidence before
            starting another run.
          </span>
        </div>
      )}

      <div className="protection-layout">
        <section className="panel flow-panel">
          <div className="section-heading flow-header">
            <div>
              <span className="eyebrow">VISIBILITY AT EVERY BOUNDARY</span>
              <h2>Live protection flow</h2>
            </div>
            <div className="flow-header-tags">
              <span className="outlined-label">
                {run
                  ? run.mode === "LIVE"
                    ? "MODEL PROPOSALS"
                    : "SCRIPTED REPLAY"
                  : "AWAITING RUN"}
              </span>
              {run && <Badge value={run.status} />}
            </div>
          </div>
          <p className="flow-subtitle">
            {run
              ? `Recorded evidence for run ${shortId(run.run_id)}.`
              : "A task-scoped agent. Two independent gates. One visible record."}
          </p>
          <div className={`flow-stage ${avatar.moving ? "is-processing" : ""}`}>
            <div className="flow-grid-texture" />
            <svg
              className="flow-connections"
              viewBox="0 0 1000 480"
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              <defs>
                <marker
                  id="flow-arrow"
                  markerWidth="6"
                  markerHeight="6"
                  refX="5"
                  refY="3"
                  orient="auto"
                >
                  <path d="m0 0 5 3-5 3" fill="none" stroke="context-stroke" />
                </marker>
              </defs>
              <path
                className={flow.received.length ? "path observed" : "path"}
                d="M235 280 H360"
              />
              <path
                className={flow.approved.length ? "path safe" : "path"}
                d="M620 280 H735"
              />
              <path
                className={flow.approved.length ? "path safe" : "path"}
                d="M490 242 V192"
              />
              <path
                className={flow.latest ? `path ${flow.actionTone}` : "path"}
                d="M570 108 H735"
              />
              <path
                className={flow.quarantined.length ? "path bad" : "path"}
                d="M490 322 V387"
              />
              <path className="path boundary" d="M215 108 H348" />
            </svg>
            <div className="scope-chip">
              <Icon name="lock" size={13} />
              {task
                ? task.allowed_resource_ids.includes("sales_oct_2026")
                  ? "Sales report only"
                  : "Task-scoped resources"
                : "Purpose-bound access"}
            </div>
            <div className="agent-center">
              <div className="agent-name">
                <strong>Cortex</strong>
                <span>Task-scoped intelligence</span>
              </div>
              <CortexAvatar moving={avatar.moving} status={avatar.tone} />
              <span className={`avatar-status ${avatar.tone}`}>
                <span />
                {avatar.label}
              </span>
            </div>
            <FlowNode
              className="document-node"
              icon="document"
              title={
                flow.received.length ? "External document" : "Document intake"
              }
              subtitle={
                flow.received.length
                  ? `${flow.received.length} unverified source${flow.received.length === 1 ? "" : "s"}`
                  : "Untrusted content enters here"
              }
              tone={flow.received.length ? "observed" : "neutral"}
              onClick={() => {
                if (flow.received.length)
                  onEvidence({ kind: "event", record: flow.received.at(-1) });
                else onView("memory");
              }}
            />
            <FlowNode
              key={flow.memories.at(-1)?.memory_id || "empty-memory"}
              className="memory-node"
              icon="check"
              title="Memory firewall"
              subtitle={
                flow.memories.length
                  ? `${flow.memories.length} candidate${flow.memories.length === 1 ? "" : "s"} inspected`
                  : "Inspect instructions & provenance"
              }
              tone={
                flow.quarantined.length
                  ? "bad"
                  : flow.approved.length
                    ? "good"
                    : "neutral"
              }
              onClick={revealMemory}
            />
            <FlowNode
              key={
                (flow.latest?.action_id || "empty-action") +
                (flow.latest?.execution_status || "")
              }
              className="gateway-node"
              icon="settings"
              title="Action gateway"
              subtitle={
                flow.latest
                  ? actionTitle(flow.latest)
                  : "Scope & permissions enforced here"
              }
              tone={flow.actionTone}
              onClick={
                flow.latest
                  ? () => onEvidence({ kind: "action", record: flow.latest })
                  : undefined
              }
            >
              {flow.latest && (
                <span className="node-inline-status">
                  {humanize(flow.latest.decision)}
                </span>
              )}
            </FlowNode>
            <FlowNode
              className="vault-node"
              icon="layers"
              title="Memory vault"
              subtitle={
                task
                  ? `${data.safe.length} retrievable fact${data.safe.length === 1 ? "" : "s"}`
                  : "Eligible, scoped facts only"
              }
              tone={data.safe.length ? "good" : "neutral"}
              onClick={() => onMemoryView("SAFE")}
            />
            <button
              className={`quarantine-pocket ${flow.quarantined.length ? "has-evidence" : ""}`}
              onClick={
                flow.quarantined.length
                  ? () =>
                      onEvidence({
                        kind: "memory",
                        record: flow.quarantined.at(-1),
                      })
                  : undefined
              }
              disabled={!flow.quarantined.length}
            >
              <div>
                <Icon name="lock" size={17} />
                <strong>
                  {flow.quarantined.length
                    ? "Quarantined"
                    : "Quarantine boundary"}
                </strong>
                {flow.quarantined.length > 0 && (
                  <span>{flow.quarantined.length}</span>
                )}
              </div>
              <p>
                {flow.quarantined.length
                  ? flow.quarantined.at(-1).content
                  : "Instructions and unsafe claims stay outside retrieval."}
              </p>
              <small>
                {flow.quarantined.length
                  ? "Excluded from safe retrieval"
                  : "No quarantined candidate in this run"}
              </small>
            </button>
          </div>
          <div className="flow-legend">
            <span>
              <i className="cyan" />
              Scoped pathway
            </span>
            <span>
              <i className="violet" />
              Agent context
            </span>
            <span>
              <i className="coral" />
              Quarantine / denial
            </span>
            <small>Highlights follow recorded evidence</small>
          </div>
        </section>
        <DecisionCard selection={selection} task={task} onOpen={onEvidence} />
      </div>

      <section className="panel decision-timeline">
        <div className="section-heading">
          <div>
            <span className="eyebrow">THE RECORD, AS IT HAPPENS</span>
            <h2>Decision timeline</h2>
          </div>
          <button className="text-button" onClick={() => onView("audit")}>
            Open full ledger <Icon name="arrow" size={16} />
          </button>
        </div>
        {recent.length ? (
          <div className="event-rows">
            {recent.map((event, index) => (
              <button
                className={`event-row ${event.status === "DENY" || event.status === "QUARANTINED" ? "blocked" : ""}`}
                key={event.event_id}
                onClick={() =>
                  onEvidence({
                    kind:
                      event.action_id &&
                      data.actions.some((a) => a.action_id === event.action_id)
                        ? "action"
                        : "event",
                    record:
                      data.actions.find(
                        (a) => a.action_id === event.action_id,
                      ) || event,
                  })
                }
              >
                <span className="event-index">{index + 1}</span>
                <span className="event-description">
                  <strong>{humanize(event.event_type)}</strong>
                  <small>{event.summary}</small>
                </span>
                <time dateTime={event.timestamp}>
                  {new Date(event.timestamp).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  })}
                </time>
                <Badge value={event.status} />
                <Icon name="arrow" size={16} />
              </button>
            ))}
          </div>
        ) : (
          <div className="timeline-placeholder">
            <span className="placeholder-point" />
            <div>
              <strong>Your first decision starts the story.</strong>
              <p>
                Run a scenario to see authentic memory and action events here.
              </p>
            </div>
            <span className="outlined-label">NO FABRICATED ACTIVITY</span>
          </div>
        )}
        <div className="task-signal-bar">
          <span>
            <strong>
              {task
                ? data.actions.filter((a) => a.execution_status === "EXECUTED")
                    .length
                : "—"}
            </strong>{" "}
            executed actions
          </span>
          <span>
            <strong>
              {task
                ? data.memories.filter((m) => m.status === "QUARANTINED").length
                : "—"}
            </strong>{" "}
            quarantined memories
          </span>
          <span>
            <strong>{task ? pending : "—"}</strong> pending reviews
          </span>
          <small>Current task · actual backend records</small>
        </div>
      </section>

      <section className="advanced-controls">
        <div>
          <span className="eyebrow">WORKSPACE UTILITIES</span>
          <h3>Inspect. Challenge. Continue.</h3>
          <p>Probes evaluate requests without executing tools.</p>
        </div>
        <div className="utility-actions">
          <button
            className="button secondary small"
            disabled={!connected || locked}
            onClick={createTask}
          >
            <Icon name="plus" size={14} />
            Create task only
          </button>
          <button
            className="button secondary small"
            disabled={
              !task ||
              locked ||
              expired ||
              (mode === "LIVE" && !health?.model_configured)
            }
            onClick={runCurrentTask}
          >
            Run current task
          </button>
          <button
            className="button secondary small"
            disabled={!task || locked || expired}
            onClick={() => probe("payroll")}
          >
            Probe payroll access
          </button>
          <button
            className="button secondary small"
            disabled={!task || locked || expired}
            onClick={() => probe("recipient")}
          >
            Probe attacker recipient
          </button>
          {run?.status === "WAITING_APPROVAL" && (
            <>
              <button
                className="button secondary small"
                onClick={() => onView("approvals")}
              >
                Review transfer
              </button>
              <button
                className="button primary small"
                disabled={busy || expired}
                onClick={resume}
              >
                Resume run
              </button>
            </>
          )}
        </div>
      </section>
      {task && (
        <details className="scope-details">
          <summary>
            <Icon name="lock" size={14} />
            Trusted task boundaries <Icon name="plus" size={14} />
          </summary>
          <dl>
            <div>
              <dt>Resources</dt>
              <dd>{task.allowed_resource_ids.join(", ")}</dd>
            </div>
            <div>
              <dt>Recipients</dt>
              <dd>{task.allowed_recipients.join(", ")}</dd>
            </div>
            <div>
              <dt>Purpose</dt>
              <dd>{task.purpose_tag}</dd>
            </div>
            <div>
              <dt>Expires</dt>
              <dd>{new Date(task.expires_at).toLocaleString()}</dd>
            </div>
          </dl>
        </details>
      )}
    </div>
  );
}

export function EvidenceDrawer({ evidence, task, data, close }) {
  const { kind } = evidence;
  const record =
    kind === "action"
      ? data.actions.find((a) => a.action_id === evidence.record.action_id) ||
        evidence.record
      : kind === "memory"
        ? [...data.memories, ...data.safe].find(
            (m) => m.memory_id === evidence.record.memory_id,
          ) || evidence.record
        : evidence.record;
  const sources = record.source_ids || [];
  const memoryIds =
    kind === "memory"
      ? [record.memory_id, ...(record.derived_memory_ids || [])]
      : record.memory_ids || [];
  const related = [...data.memories, ...data.safe].filter(
    (m, i, array) =>
      memoryIds.includes(m.memory_id) &&
      array.findIndex((item) => item.memory_id === m.memory_id) === i,
  );
  const id = record.action_id || record.memory_id || record.event_id;
  return (
    <Modal
      className="evidence-drawer"
      title="Follow the evidence."
      subtitle="A read-only view of the recorded decision and its provenance."
      close={close}
    >
      <div className="drawer-verdict">
        <Badge value={record.decision || record.status} />
        <span className="outlined-label">{kind.toUpperCase()} RECORD</span>
      </div>
      <section className="drawer-section">
        <h3>Decision reference</h3>
        <code>{id}</code>
        {record.event_type && <p>{humanize(record.event_type)}</p>}
        {kind === "action" && (
          <span className="outlined-label">
            {record.run_id ? "AGENT RUN REQUEST" : "OPERATOR REQUEST"}
          </span>
        )}
        {record.tool && <p className="tool-name">{humanize(record.tool)}</p>}
        {record.execution_status && <Badge value={record.execution_status} />}
        <p>
          {record.explanation ||
            record.summary ||
            (record.status === "QUARANTINED"
              ? "This candidate is not eligible for safe retrieval."
              : "Refer to status and reason codes for this record.")}
        </p>
      </section>
      {record.args && (
        <section className="drawer-section">
          <h3>Exact proposed arguments</h3>
          <dl className="drawer-args">
            {Object.entries(record.args).map(([name, value]) => (
              <div key={name}>
                <dt>{humanize(name)}</dt>
                <dd>
                  {typeof value === "object"
                    ? JSON.stringify(value)
                    : String(value)}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      )}
      {record.content && (
        <section className="drawer-section">
          <h3>Memory candidate</h3>
          <blockquote>{record.content}</blockquote>
          <p className="muted">
            Stored content is evidence, not an operating instruction.
          </p>
        </section>
      )}
      <section className="drawer-section">
        <h3>Reason codes</h3>
        {record.reason_codes?.length ? (
          record.reason_codes.map((code) => (
            <code className="reason-chip" key={code}>
              {code}
            </code>
          ))
        ) : (
          <p>No denial or quarantine reason codes recorded.</p>
        )}
      </section>
      <section className="drawer-section">
        <h3>Source lineage</h3>
        {sources.length ? (
          sources.map((source) => (
            <div className="lineage-row" key={source}>
              <Icon name="document" size={15} />
              <code>{source}</code>
            </div>
          ))
        ) : (
          <p>No source references attached to this record.</p>
        )}
        {related.map((memory) => (
          <div className="lineage-memory" key={memory.memory_id}>
            <Badge value={memory.status} />
            <code>{memory.memory_id}</code>
            <p>{memory.content}</p>
          </div>
        ))}
      </section>
      <section className="drawer-section">
        <h3>Trusted scope</h3>
        <dl className="drawer-args">
          <div>
            <dt>Task</dt>
            <dd>{task?.task_id}</dd>
          </div>
          <div>
            <dt>Resources</dt>
            <dd>{task?.allowed_resource_ids.join(", ")}</dd>
          </div>
          <div>
            <dt>Recipients</dt>
            <dd>{task?.allowed_recipients.join(", ")}</dd>
          </div>
        </dl>
      </section>
      {record.request_hash && (
        <details className="integrity-details">
          <summary>Action / request integrity hash</summary>
          <code>{record.request_hash}</code>
        </details>
      )}
      <p className="drawer-disclaimer">
        Approval permits an eligible action or scoped storage. It does not prove
        that a statement is true. Email delivery is simulated.
      </p>
    </Modal>
  );
}
