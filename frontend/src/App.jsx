import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { makeApi } from "./api.js";
import { Icon, Badge, Empty, Modal, ConnectionDialog } from "./ui.jsx";
import Cockpit, { CortexAvatar, EvidenceDrawer } from "./Cockpit.jsx";

const AGENT = "finance-agent-001";
const NAV = [
  ["overview", "Control room", "grid"],
  ["memory", "Memory vault", "layers"],
  ["approvals", "Approvals", "check"],
  ["audit", "Evidence ledger", "activity"],
  ["outbox", "Outbox", "mail"],
];
const TITLES = {
  overview: [
    "Intelligence, within boundaries.",
    "See what your agent knows. Control what it can do.",
  ],
  memory: [
    "Memory, with boundaries.",
    "Inspect every fact, its provenance, and the decision to retain it.",
  ],
  approvals: [
    "A human in the loop.",
    "Review scoped external transfers before any action can execute.",
  ],
  audit: [
    "Every decision, accounted for.",
    "A chronological record of the selected task, directly from the backend.",
  ],
  outbox: [
    "Only the intended destination.",
    "Inspect the simulated messages created by controlled tool execution.",
  ],
};

function App() {
  const [view, setView] = useState("overview");
  const [operatorKey, setOperatorKey] = useState("");
  const [connected, setConnected] = useState(false);
  const [health, setHealth] = useState(null);
  const [dialog, setDialog] = useState(null);
  const [task, setTask] = useState(null);
  const [run, setRun] = useState(null);
  const [data, setData] = useState({
    memories: [],
    safe: [],
    events: [],
    approvals: [],
    outbox: [],
    actions: [],
  });
  const [mode, setMode] = useState("LIVE");
  const [scenario, setScenario] = useState("normal");
  const [template, setTemplate] = useState("SALES_INTERNAL");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [lastSynced, setLastSynced] = useState(null);
  const [clock, setClock] = useState(Date.now());
  const [history, setHistory] = useState([]);
  const [memoryFilter, setMemoryFilter] = useState("ALL");
  const [reviewerKey, setReviewerKey] = useState("");
  const [documentForm, setDocumentForm] = useState({ name: "", content: "" });
  const [documentResult, setDocumentResult] = useState(null);
  const [memoryContent, setMemoryContent] = useState("");
  const [loadForm, setLoadForm] = useState({ task: "", run: "" });
  const [auditFilter, setAuditFilter] = useState("");
  const [evidence, setEvidence] = useState(null);
  const closeEvidence = useCallback(() => setEvidence(null), []);
  const generation = useRef(0);
  const commandLock = useRef(false);
  const api = useMemo(() => makeApi(operatorKey), [operatorKey]);
  const closeDialog = useCallback(() => setDialog(null), []);
  const running = ["QUEUED", "RUNNING"].includes(run?.status);
  const expired = task ? new Date(task.expires_at).getTime() <= clock : false;
  const locked = busy || running;
  const pending = data.approvals.filter(
    (a) => a.status === "PENDING" && new Date(a.expires_at).getTime() > clock,
  );

  useEffect(() => {
    const timer = setInterval(() => setClock(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  const refresh = useCallback(
    async (taskId, runId, signal) => {
      const ticket = generation.current;
      const q = "?task_id=" + encodeURIComponent(taskId);
      const [
        newTask,
        memories,
        safe,
        events,
        approvals,
        outbox,
        actionRecords,
        newRun,
      ] = await Promise.all([
        api("/tasks/" + encodeURIComponent(taskId), { signal }),
        api("/memories" + q + "&agent_id=" + AGENT, { signal }),
        api("/memories/retrieve" + q, { signal }).catch((e) => {
          if (e.status === 409) return { items: [] };
          throw e;
        }),
        api("/events" + q, { signal }),
        api("/approvals" + q, { signal }),
        api("/outbox" + q, { signal }),
        api("/actions" + q, { signal }),
        runId ? api("/runs/" + encodeURIComponent(runId), { signal }) : null,
      ]);
      if (ticket !== generation.current || signal?.aborted) return;
      if (newRun && newRun.task_id !== taskId)
        throw new Error("This run belongs to a different task.");
      setTask(newTask);
      setRun(newRun);
      setData({
        memories: memories.items,
        safe: safe.items,
        events: events.items,
        approvals: approvals.items,
        outbox: outbox.items,
        actions: actionRecords.items,
      });
      setLastSynced(new Date());
      setHistory((prev) =>
        [
          {
            task_id: newTask.task_id,
            run_id: newRun?.run_id,
            template_id: newTask.template_id,
          },
          ...prev.filter((t) => t.task_id !== taskId),
        ].slice(0, 12),
      );
      return actionRecords.items;
    },
    [api],
  );

  useEffect(() => {
    if (
      !connected ||
      !task ||
      !run ||
      !["QUEUED", "RUNNING", "WAITING_APPROVAL"].includes(run.status)
    )
      return;
    const controller = new AbortController();
    let timer;
    const poll = async () => {
      try {
        await refresh(task.task_id, run.run_id, controller.signal);
      } catch (err) {
        if (!controller.signal.aborted) setError(err.message);
      }
      if (!controller.signal.aborted) timer = setTimeout(poll, 2500);
    };
    timer = setTimeout(poll, 1200);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [connected, task?.task_id, run?.run_id, run?.status, refresh]);

  async function command(fn) {
    if (commandLock.current) return;
    commandLock.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (err) {
      setError(err.message || "The operation could not be completed.");
    } finally {
      setBusy(false);
      commandLock.current = false;
    }
  }

  async function connect(key) {
    setBusy(true);
    try {
      const client = makeApi(key);
      const [h, agents] = await Promise.all([
        client("/health"),
        client("/agents"),
      ]);
      if (!agents.items.some((a) => a.agent_id === AGENT))
        throw new Error(
          "The seeded finance agent is missing. Restart the backend.",
        );
      generation.current++;
      setEvidence(null);
      setHealth(h);
      setOperatorKey(key);
      setConnected(true);
      setDialog(null);
      setError("");
      setTask(null);
      setRun(null);
      setData({
        memories: [],
        safe: [],
        events: [],
        approvals: [],
        outbox: [],
        actions: [],
      });
      setHistory([]);
      setDocumentResult(null);
      setDocumentForm({ name: "", content: "" });
      setMemoryContent("");
      setLastSynced(null);
      setNotice("Workspace connected. Create a task to begin.");
    } finally {
      setBusy(false);
    }
  }

  function disconnect() {
    generation.current++;
    setEvidence(null);
    setOperatorKey("");
    setReviewerKey("");
    setConnected(false);
    setHealth(null);
    setTask(null);
    setRun(null);
    setHistory([]);
    setData({
      memories: [],
      safe: [],
      events: [],
      approvals: [],
      outbox: [],
      actions: [],
    });
    setDialog(null);
    setLastSynced(null);
    setError("");
    setNotice("Workspace disconnected. Access keys cleared.");
  }

  async function newTask() {
    generation.current++;
    setEvidence(null);
    const created = await api("/tasks", {
      method: "POST",
      body: { agent_id: AGENT, template_id: template },
    });
    setTask(created);
    setRun(null);
    setDocumentResult(null);
    setMemoryContent("");
    setData({
      memories: [],
      safe: [],
      events: [],
      approvals: [],
      outbox: [],
      actions: [],
    });
    await refresh(created.task_id);
    return created;
  }

  function startRun() {
    command(async () => {
      const created = await newTask();
      const result = await api("/runs", {
        method: "POST",
        body: { task_id: created.task_id, scenario, mode },
      });
      setRun(result);
      await refresh(created.task_id, result.run_id);
      setNotice(
        mode === "LIVE"
          ? "Live run submitted. The monitor shows the backend’s current state."
          : "Scripted replay started. No Gemini requests are made.",
      );
    });
  }

  function runCurrentTask() {
    command(async () => {
      const result = await api("/runs", {
        method: "POST",
        body: { task_id: task.task_id, scenario, mode },
      });
      setRun(result);
      await refresh(task.task_id, result.run_id);
      setNotice("A new run has started on the current task.");
    });
  }

  function loadTask(e) {
    e.preventDefault();
    command(async () => {
      generation.current++;
      setEvidence(null);
      await refresh(loadForm.task.trim(), loadForm.run.trim() || undefined);
      setDocumentResult(null);
      setMemoryContent("");
      setDialog(null);
      setView("overview");
      setNotice("Task loaded from the backend.");
    });
  }

  function probe(kind) {
    command(async () => {
      const args =
        kind === "payroll"
          ? { resource_id: "payroll_oct_2026" }
          : {
              resource_id: "sales_oct_2026",
              recipient: "cfo@outside.example",
              subject: task.email_subject,
            };
      const result = await api("/actions/evaluate", {
        method: "POST",
        body: {
          task_id: task.task_id,
          tool: kind === "payroll" ? "read_file" : "send_email",
          args,
          idempotency_key: crypto.randomUUID(),
        },
      });
      // Evaluation only: the test never calls execution, regardless of the decision.
      const records = await refresh(task.task_id, run?.run_id);
      const recorded = records?.find((a) => a.action_id === result.action_id);
      if (recorded) setEvidence({ kind: "action", record: recorded });
      setNotice("Boundary probe evaluated. No tool was executed by this test.");
    });
  }

  function review(approval, decision) {
    command(async () => {
      const client = makeApi(operatorKey, reviewerKey.trim());
      await client("/approvals/" + approval.approval_id + "/decision", {
        method: "POST",
        reviewer: true,
        body: { decision },
      });
      setReviewerKey("");
      await refresh(task.task_id, run?.run_id);
      setNotice(
        decision === "ALLOW_ONCE"
          ? "Approved once. Select Resume run to continue explicitly."
          : "Transfer denied. Resume the waiting run to record its final outcome.",
      );
    });
  }

  function resume() {
    command(async () => {
      await api("/runs/" + run.run_id + "/resume", {
        method: "POST",
        body: {},
      });
      await refresh(task.task_id, run.run_id);
      setNotice(
        "Resume requested. The gateway rechecks the approval and current policy.",
      );
    });
  }

  function upload(e) {
    e.preventDefault();
    command(async () => {
      if (new TextEncoder().encode(documentForm.content).length > 51200)
        throw new Error("Document text must be 50 KB or less.");
      const doc = await api("/documents", {
        method: "POST",
        body: { task_id: task.task_id, ...documentForm },
      });
      setDocumentResult(doc);
      setMemoryContent(documentForm.content.slice(0, 8192));
      setNotice(
        "Document received as external and unverified. Propose a memory below.",
      );
      await refresh(task.task_id, run?.run_id);
    });
  }

  function evaluateMemory(e) {
    e.preventDefault();
    command(async () => {
      const result = await api("/memories/evaluate", {
        method: "POST",
        body: {
          task_id: task.task_id,
          content: memoryContent,
          source_ids: [documentResult.source_id],
          derived_memory_ids: [],
          idempotency_key: crypto.randomUUID(),
        },
      });
      await refresh(task.task_id, run?.run_id);
      setNotice("Memory decision: " + result.status + ".");
      setDialog(null);
      setView("memory");
    });
  }

  function exportReport() {
    const report = {
      product: "Cortex Lock",
      exported_at: new Date().toISOString(),
      email_delivery: "SIMULATED",
      task,
      run,
      ...data,
    };
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `cortex-lock-${task.task_id}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  const shownMemories =
    memoryFilter === "SAFE"
      ? data.safe
      : data.memories.filter(
          (m) => memoryFilter === "ALL" || m.status === memoryFilter,
        );
  const shownEvents = data.events.filter((e) =>
    (e.event_type + " " + e.summary + " " + e.reason_codes.join(" "))
      .toLowerCase()
      .includes(auditFilter.toLowerCase()),
  );
  const statusTime = (value) =>
    new Date(value).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });

  const timeline = (events) => (
    <ol className="timeline">
      {events.map((event) => (
        <li key={event.event_id}>
          <span
            className={
              "timeline-marker " +
              (["DENY", "QUARANTINED", "FAILED"].includes(event.status)
                ? "red"
                : "")
            }
          />
          <div className="timeline-content">
            <div className="timeline-top">
              <strong>
                {event.event_type.replaceAll("_", " ").toLowerCase()}
              </strong>
              <time dateTime={event.timestamp}>
                {statusTime(event.timestamp)}
              </time>
            </div>
            <p>{event.summary}</p>
            <div className="timeline-meta">
              <Badge value={event.status} />
              {event.reason_codes.map((code) => (
                <code key={code}>{code}</code>
              ))}
            </div>
            <button
              className="text-button"
              onClick={() => {
                const action = data.actions.find(
                  (a) => a.action_id === event.action_id,
                );
                const memory = data.memories.find((m) =>
                  event.memory_ids?.includes(m.memory_id),
                );
                setEvidence(
                  action
                    ? { kind: "action", record: action }
                    : memory
                      ? { kind: "memory", record: memory }
                      : { kind: "event", record: event },
                );
              }}
            >
              Open evidence drawer <Icon name="arrow" size={14} />
            </button>
            {view === "audit" && (
              <details>
                <summary>View evidence</summary>
                <pre>
                  {JSON.stringify(
                    {
                      event_id: event.event_id,
                      run_id: event.run_id,
                      action_id: event.action_id,
                      source_ids: event.source_ids,
                      memory_ids: event.memory_ids,
                      metadata: event.metadata,
                    },
                    null,
                    2,
                  )}
                </pre>
              </details>
            )}
          </div>
        </li>
      ))}
    </ol>
  );

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setView("overview");
          }}
        >
          <span className="brand-mark">
            <CortexAvatar mini status="brand" />
          </span>
          <span>
            Cortex Lock<span className="brand-caption">AGENT SECURITY</span>
          </span>
        </a>
        <div className="workspace-label">
          WORKSPACE <span>01</span>
        </div>
        <nav aria-label="Main navigation">
          {NAV.map(([id, label, icon]) => (
            <button
              key={id}
              aria-label={label}
              className={"nav-item " + (view === id ? "active" : "")}
              onClick={() => setView(id)}
              aria-current={view === id ? "page" : undefined}
            >
              <Icon name={icon} />
              <span>{label}</span>
              {id === "approvals" && pending.length > 0 && (
                <b className="nav-count">{pending.length}</b>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="agent-profile">
            <CortexAvatar mini status={connected ? "ready" : "offline"} />
            <div>
              <strong>Finance agent</strong>
              <span className={connected ? "agent-online" : ""}>
                {connected ? "Workspace connected" : "Not connected"}
              </span>
            </div>
          </div>
          <p>Purpose. Provenance. Permission.</p>
          {connected && (
            <button
              className="disconnect-button"
              disabled={busy}
              onClick={disconnect}
            >
              Disconnect workspace
            </button>
          )}
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace<span>/</span>
            <strong>{NAV.find((n) => n[0] === view)[1]}</strong>
          </div>
          <div className="topbar-actions">
            <span
              className={"connection-status " + (connected ? "online" : "")}
            >
              <span />
              {connected ? "Backend connected" : "Workspace offline"}
            </span>
            <button
              className="icon-button"
              aria-label="Connection settings"
              onClick={() => setDialog("connection")}
              disabled={busy}
            >
              <Icon name="settings" />
            </button>
          </div>
        </header>
        <main id="main">
          <div className="page-heading">
            <div>
              <span className="eyebrow">AI AGENT SECURITY / CONTROL PLANE</span>
              <h1>{TITLES[view][0]}</h1>
              <p>{TITLES[view][1]}</p>
            </div>
            <button
              className="button secondary export"
              disabled={!task || busy}
              onClick={exportReport}
            >
              <Icon name="download" />
              Export evidence
            </button>
          </div>
          <div aria-live="polite">
            {error && (
              <div className="alert error">
                <Icon name="activity" />
                <span>{error}</span>
                <button
                  className="icon-button"
                  aria-label="Dismiss error"
                  onClick={() => setError("")}
                >
                  <Icon name="close" size={16} />
                </button>
              </div>
            )}
            {notice && (
              <div className="alert notice">
                <Icon name="check" />
                <span>{notice}</span>
                <button
                  className="icon-button"
                  aria-label="Dismiss notice"
                  onClick={() => setNotice("")}
                >
                  <Icon name="close" size={16} />
                </button>
              </div>
            )}
          </div>
          <div className="scope-bar">
            <span className="scope-icon">
              <Icon name="grid" size={16} />
            </span>
            <div>
              <span className="small-label">CURRENT TASK</span>
              <strong title={task?.task_id}>
                {task ? task.task_id : "No task selected"}
              </strong>
            </div>
            {task && <Badge value={expired ? "EXPIRED" : "ACTIVE"} />}
            <div className="scope-buttons">
              <button
                className="text-button"
                disabled={!connected || locked}
                onClick={() => {
                  setLoadForm({ task: "", run: "" });
                  setDialog("load");
                }}
              >
                Load existing
              </button>
              <button
                className="icon-button"
                aria-label="Refresh task data"
                disabled={!task || busy}
                onClick={() =>
                  command(() => refresh(task.task_id, run?.run_id))
                }
              >
                <Icon name="refresh" size={17} />
              </button>
            </div>
          </div>

          {view === "overview" && (
            <Cockpit
              task={task}
              run={run}
              data={data}
              mode={mode}
              setMode={setMode}
              scenario={scenario}
              setScenario={setScenario}
              template={template}
              setTemplate={setTemplate}
              connected={connected}
              health={health}
              busy={busy}
              locked={locked}
              expired={expired}
              startRun={startRun}
              runCurrentTask={runCurrentTask}
              resume={resume}
              createTask={() =>
                command(async () => {
                  await newTask();
                  setNotice(
                    "Task created. Add a document in Memory vault, then run on the current task.",
                  );
                })
              }
              connect={() => setDialog("connection")}
              probe={probe}
              onView={setView}
              onMemoryView={(filter) => {
                setMemoryFilter(filter);
                setView("memory");
              }}
              onEvidence={setEvidence}
              pending={pending.length}
            />
          )}

          {view === "memory" && (
            <section className="panel">
              <div className="section-heading">
                <div>
                  <h2>Knowledge under review</h2>
                  <p className="muted">
                    Approval permits scoped storage; it does not verify a fact’s
                    truth.
                  </p>
                </div>
                <button
                  className="button primary small"
                  disabled={!task || locked || expired}
                  onClick={() => setDialog("document")}
                >
                  <Icon name="plus" size={16} />
                  Add document
                </button>
              </div>
              <div className="tabs" role="group" aria-label="Filter memories">
                {[
                  ["ALL", "All entries"],
                  ["APPROVED", "Approved"],
                  ["QUARANTINED", "Quarantined"],
                  ["SAFE", "Safe to retrieve"],
                ].map(([id, label]) => (
                  <button
                    key={id}
                    aria-pressed={memoryFilter === id}
                    className={memoryFilter === id ? "selected" : ""}
                    onClick={() => setMemoryFilter(id)}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {shownMemories.length ? (
                <div className="memory-list">
                  {shownMemories.map((memory) => (
                    <article className="memory-card" key={memory.memory_id}>
                      <div className="memory-top">
                        <Badge value={memory.status} />
                        <span className="outlined-label">
                          {memory.analysis_mode}
                        </span>
                      </div>
                      <p className="memory-content">{memory.content}</p>
                      <button
                        className="text-button"
                        onClick={() =>
                          setEvidence({ kind: "memory", record: memory })
                        }
                      >
                        Inspect provenance <Icon name="arrow" size={14} />
                      </button>
                      <div className="memory-reasons">
                        {memory.reason_codes.map((r) => (
                          <code key={r}>{r}</code>
                        ))}
                      </div>
                      <dl className="memory-meta">
                        <div>
                          <dt>Memory reference</dt>
                          <dd>{memory.memory_id}</dd>
                        </div>
                        <div>
                          <dt>Expires</dt>
                          <dd>
                            {new Date(memory.expires_at).toLocaleString()}
                          </dd>
                        </div>
                        <div>
                          <dt>Source references</dt>
                          <dd>{memory.source_ids.join(", ")}</dd>
                        </div>
                        <div>
                          <dt>Parent memories</dt>
                          <dd>
                            {memory.derived_memory_ids.length
                              ? memory.derived_memory_ids.join(", ")
                              : "None"}
                          </dd>
                        </div>
                      </dl>
                      {memory.error_code && (
                        <p className="form-error">
                          Analysis error: {memory.error_code}
                        </p>
                      )}
                    </article>
                  ))}
                </div>
              ) : (
                <Empty
                  title={
                    task
                      ? "No entries in this view."
                      : "A clean slate for agent memory."
                  }
                >
                  {task
                    ? "Run a workflow or add a document to inspect memory decisions."
                    : "Create or load a task to inspect its stored memories."}
                </Empty>
              )}
            </section>
          )}

          {view === "approvals" && (
            <section className="panel">
              <div className="section-heading">
                <div>
                  <h2>Review queue</h2>
                  <p className="muted">
                    Approvals expire after two minutes and apply to one exact
                    action.
                  </p>
                </div>
                <Badge value={pending.length ? "PENDING" : "ACTIVE"}>
                  {pending.length} awaiting review
                </Badge>
              </div>
              {data.approvals.length ? (
                <>
                  <label className="review-key">
                    Reviewer key
                    <input
                      type="password"
                      autoComplete="off"
                      placeholder="Paste CORTEX_REVIEWER_KEY for this decision"
                      value={reviewerKey}
                      onChange={(e) => setReviewerKey(e.target.value)}
                    />
                    <small>
                      Separate from the operator key. Cleared after a successful
                      decision.
                    </small>
                  </label>
                  {data.approvals.map((a) => {
                    const status =
                      ["PENDING", "APPROVED"].includes(a.status) &&
                      new Date(a.expires_at).getTime() <= clock
                        ? "EXPIRED"
                        : a.status;
                    return (
                      <article className="approval-card" key={a.approval_id}>
                        <div>
                          <Badge value={status} />
                          <h3>External sales transfer</h3>
                          <p>
                            {task?.allowed_resource_ids.join(", ")}{" "}
                            <span aria-hidden="true">→</span>{" "}
                            {task?.allowed_recipients.join(", ")}
                          </p>
                          <code>{a.action_id}</code>
                          <button
                            className="text-button"
                            disabled={
                              !data.actions.some(
                                (record) => record.action_id === a.action_id,
                              )
                            }
                            onClick={() =>
                              setEvidence({
                                kind: "action",
                                record: data.actions.find(
                                  (record) => record.action_id === a.action_id,
                                ),
                              })
                            }
                          >
                            Inspect proposed action{" "}
                            <Icon name="arrow" size={14} />
                          </button>
                          <p className="small-muted">
                            Expires {statusTime(a.expires_at)} · exact action
                            bound to approval
                          </p>
                        </div>
                        <div className="approval-controls">
                          <button
                            className="button danger small"
                            disabled={
                              busy ||
                              status !== "PENDING" ||
                              !reviewerKey.trim()
                            }
                            onClick={() => review(a, "DENY")}
                          >
                            Deny
                          </button>
                          <button
                            className="button primary small"
                            disabled={
                              busy ||
                              status !== "PENDING" ||
                              !reviewerKey.trim()
                            }
                            onClick={() => review(a, "ALLOW_ONCE")}
                          >
                            Approve once
                          </button>
                        </div>
                      </article>
                    );
                  })}
                  {run?.status === "WAITING_APPROVAL" && (
                    <div className="resume-bar">
                      <p>
                        A review decision does not execute the transfer. Resume
                        the run explicitly.
                      </p>
                      <button
                        className="button primary"
                        disabled={busy || expired}
                        onClick={resume}
                      >
                        Resume run <Icon name="arrow" size={16} />
                      </button>
                    </div>
                  )}
                </>
              ) : (
                <Empty icon="check" title="Nothing waiting for your decision.">
                  Choose the external sales task to demonstrate a transfer
                  requiring reviewer approval.
                </Empty>
              )}
            </section>
          )}

          {view === "audit" && (
            <section className="panel audit-panel">
              <div className="section-heading">
                <div>
                  <h2>Decision ledger</h2>
                  <p className="muted">
                    Oldest first · up to 500 backend events for this task
                  </p>
                </div>
                <label className="search-label">
                  <span className="sr-only">Filter events</span>
                  <input
                    type="search"
                    placeholder="Filter events or reasons…"
                    value={auditFilter}
                    onChange={(e) => setAuditFilter(e.target.value)}
                  />
                </label>
              </div>
              {shownEvents.length ? (
                timeline(shownEvents)
              ) : (
                <Empty icon="activity" title="No matching events.">
                  {task
                    ? "Try another filter or start a run."
                    : "Select a task to inspect its audit trail."}
                </Empty>
              )}
            </section>
          )}

          {view === "outbox" && (
            <section className="panel">
              <div className="section-heading">
                <div>
                  <h2>Controlled delivery</h2>
                  <p className="muted">
                    Every entry is simulated. No real email is sent.
                  </p>
                </div>
                <span className="outlined-label">SIMULATED OUTBOX</span>
              </div>
              {data.outbox.length ? (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Destination</th>
                        <th>Resource</th>
                        <th>Subject</th>
                        <th>Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.outbox.map((m) => (
                        <tr key={m.message_id}>
                          <td>
                            <strong>{m.recipient}</strong>
                            <small>{m.message_id}</small>
                            <button
                              className="text-button"
                              disabled={
                                !data.actions.some(
                                  (record) => record.action_id === m.action_id,
                                )
                              }
                              onClick={() =>
                                setEvidence({
                                  kind: "action",
                                  record: data.actions.find(
                                    (record) =>
                                      record.action_id === m.action_id,
                                  ),
                                })
                              }
                            >
                              Inspect execution <Icon name="arrow" size={14} />
                            </button>
                          </td>
                          <td>
                            <span className="resource-chip">
                              <Icon name="document" size={14} />
                              {m.resource_id}
                            </span>
                          </td>
                          <td>{m.subject}</td>
                          <td>{statusTime(m.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <Empty icon="mail" title="No messages have left this task.">
                  An entry appears only after the action gateway authorizes and
                  executes a simulated send.
                </Empty>
              )}
            </section>
          )}

          {!connected && (
            <section className="connect-banner">
              <div>
                <CortexAvatar mini status="brand" />
                <div>
                  <strong>Your control room is ready.</strong>
                  <p>
                    Connect the local backend to start seeing real decisions.
                  </p>
                </div>
              </div>
              <button
                className="button primary"
                onClick={() => setDialog("connection")}
              >
                Connect workspace <Icon name="arrow" size={16} />
              </button>
            </section>
          )}
          <footer className="page-footer">
            <span>
              <span className="footer-dot" />
              Local demonstration · simulated delivery
            </span>
            <span>
              {lastSynced
                ? "Synced " + lastSynced.toLocaleTimeString()
                : "Waiting for workspace connection"}
              <span className="footer-divider">/</span>Contract 1.0
            </span>
          </footer>
        </main>
      </div>
      {evidence && (
        <EvidenceDrawer
          evidence={evidence}
          task={task}
          data={data}
          close={closeEvidence}
        />
      )}
      {dialog === "connection" && (
        <ConnectionDialog
          close={closeDialog}
          connect={connect}
          currentKey={operatorKey}
          busy={busy}
        />
      )}
      {dialog === "load" && (
        <Modal
          title="Return to a task"
          subtitle="Use references from a previous run. Records remain in the local backend database."
          close={closeDialog}
        >
          <form onSubmit={loadTask}>
            <label>
              Task reference
              <input
                required
                value={loadForm.task}
                onChange={(e) =>
                  setLoadForm({ ...loadForm, task: e.target.value })
                }
                placeholder="task_…"
              />
            </label>
            <label>
              Run reference <span className="small-muted">optional</span>
              <input
                value={loadForm.run}
                onChange={(e) =>
                  setLoadForm({ ...loadForm, run: e.target.value })
                }
                placeholder="run_…"
              />
            </label>
            {history.length > 0 && (
              <label>
                Recent in this session
                <select
                  value=""
                  onChange={(e) => {
                    const item = history.find(
                      (h) => h.task_id === e.target.value,
                    );
                    if (item)
                      setLoadForm({
                        task: item.task_id,
                        run: item.run_id || "",
                      });
                  }}
                >
                  <option value="">Choose a task…</option>
                  {history.map((h) => (
                    <option key={h.task_id} value={h.task_id}>
                      {h.template_id} · {h.task_id.slice(-8)}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {error && (
              <p className="form-error" role="alert">
                {error}
              </p>
            )}
            <button className="button primary full" disabled={busy}>
              {busy ? "Loading…" : "Load task"}
              <Icon name="arrow" size={16} />
            </button>
          </form>
        </Modal>
      )}
      {dialog === "document" && (
        <Modal
          title="Inspect external knowledge"
          subtitle="Documents always enter as external and unverified. Only plain text is accepted."
          close={closeDialog}
        >
          <form onSubmit={upload}>
            <label>
              Document name
              <input
                required
                maxLength={120}
                value={documentForm.name}
                onChange={(e) =>
                  setDocumentForm({ ...documentForm, name: e.target.value })
                }
                placeholder="e.g. October sales attachment"
              />
            </label>
            <label>
              Document text
              <textarea
                required
                rows={5}
                value={documentForm.content}
                onChange={(e) =>
                  setDocumentForm({ ...documentForm, content: e.target.value })
                }
                placeholder="Paste synthetic document text…"
              />
            </label>
            <div className="document-actions">
              <span className="small-muted">50 KB maximum · plain text</span>
              <button
                className="button secondary small"
                type="submit"
                disabled={busy}
              >
                Receive document
              </button>
            </div>
          </form>
          {documentResult && (
            <form className="memory-proposal" onSubmit={evaluateMemory}>
              <Badge value="UNVERIFIED" />
              <p className="small-muted">
                Source: <code>{documentResult.source_id}</code>
              </p>
              <label>
                Proposed memory
                <textarea
                  rows={3}
                  required
                  maxLength={8192}
                  value={memoryContent}
                  onChange={(e) => setMemoryContent(e.target.value)}
                />
              </label>
              <button className="button primary full" disabled={busy}>
                {busy ? "Analyzing…" : "Evaluate memory"}
                <Icon name="arrow" size={16} />
              </button>
            </form>
          )}
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
        </Modal>
      )}
      {connected && dialog === "connection" && (
        <span className="sr-only">Currently connected</span>
      )}
    </div>
  );
}

export default App;
