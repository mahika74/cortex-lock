# Cortex Lock · Protection Console v2

A working redesign of the local Cortex Lock frontend: midnight navy surfaces, cyan controls, a violet Cortex avatar, Space Grotesk headings and Inter body text. Flow highlights, decisions, and timelines reflect actual backend records.

## Upgrade on Windows

1. Stop the Python and Vite servers with Ctrl+C in each terminal. Merge the ZIP's **frontend** and **backend** folders into `C:\Users\Mahika\cortex-lock`. Replace the supplied source files. Keep your existing `.env`, `.venv`, database, and frontend `node_modules` folder.
2. Restart the backend from the repository root:

```powershell
cd C:\Users\Mahika\cortex-lock
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

3. In another terminal, restart the frontend:

```powershell
cd C:\Users\Mahika\cortex-lock\frontend
npm.cmd run dev
```

Open http://localhost:5173, refresh, and connect using the value of `CORTEX_OPERATOR_KEY` in your existing local root `.env`. No dependencies were added. On a fresh machine, run `npm.cmd install` first; the build was tested with Node 24.

**Copy the bundled backend file too.** It adds protected, read-only `GET /api/actions?task_id=...` for exact proposed arguments, reason codes, and execution status. It excludes tool outputs and internal idempotency keys. No database migration is needed.

## The new experience

- Three scenario cards: Complete a task, Test memory poisoning, Request human approval.
- LIVE and REPLAY stay explicit. Mode selection controls the next run; the flow header identifies the actual selected run's mode.
- An SVG Cortex avatar shows recorded run states. Processing animation stops when a run completes, fails, or waits for review.
- The flow separates document intake, memory firewall, action gateway, safe memory retrieval, and quarantine. Only observed approved memories light up the approved-memory route. Quarantined content stays outside it.
- The decision panel shows the recorded tool, resource, recipient, authorization and execution status. An injection scenario does not invent a denied action: a LIVE model may ignore the attack and complete the legitimate task.
- The vault opens the actual Safe to retrieve view, which may include eligible memories from earlier tasks of the same agent and purpose. Storage approval does not verify factual truth.
- Click a flow decision, timeline row, memory, approval action or outbox execution to open the evidence drawer. Inspect exact arguments, reasons, source references, related memories, trusted scope and request integrity hash.
- Scenario cards, buttons, page changes, drawers and gate outcomes have restrained CSS transitions. SVG processing motion respects reduced-motion settings. No animation library or external image assets are required.
- Existing document/memory intake, separate reviewer key, one-time approval, explicit resume, audit ledger, simulated outbox, export and task-loading functions remain connected.
- Responsive layouts stack the flow into readable cards. Mobile navigation retains accessible labels, and a 390-pixel browser viewport had no horizontal overflow.

## Demo sequence

1. Connect, select **Complete a task**, choose **Scripted replay**, then run. Inspect approved memory, the action gateway and simulated outbox.
2. Select **Test memory poisoning**, keep replay, and run. Expect quarantine, denied payroll requests and no outbox entry for this task. Click the quarantine pocket and gateway for evidence.
3. Select **Request human approval** and run a normal replay. In Approvals, enter your local `CORTEX_REVIEWER_KEY` value and approve once. Then explicitly Resume run. Approval does not execute a transfer by itself.
4. Switch to LIVE for actual Gemini proposals. The interface shows the actual result, including a safe completion if Gemini ignores an injection.
5. Workspace utilities retain Create task only, Run current task and boundary probes. Probes only evaluate requests. Their evidence is identified as an operator request and is not attributed to the agent's run.

## Verification

```powershell
# Repository root: 86 backend tests
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p "test_*.py" -v

# Frontend folder: 9 presentation/state tests, then production build
npm.cmd test
npm.cmd run build

# Optional real API checks against the running backend.
# Creates synthetic tasks and simulated records; no Gemini requests.
node --env-file=../.env tests/api-integration.mjs
```

Backend tests, frontend state tests, production build, and real HTTP integration checks passed. Browser checks covered the full disconnected shell, populated components using replay records captured from the real backend, drawer open/close and focus restoration, and mobile layout. The remote browser cannot connect directly to the separately isolated Python process; verify the complete browser-to-backend sequence on your laptop after upgrading.

## Source map

- `src/App.jsx`: orchestration and authenticated integration.
- `src/Cockpit.jsx`: scenarios, avatar, flow, decision panel, timeline and drawer.
- `src/presentation.js`: evidence-derived visual state, covered by tests.
- `src/ui.jsx`: accessible dialogs, icons, badges and connection form.
- `src/api.js`: safe requests, cancellation and errors.
- `src/styles.css`: dark theme, responsive rules and native transitions.

Keys remain in page memory and clear on reload/disconnect. Never put keys in frontend source, browser storage or VITE variables. Gemini stays on the backend. Google Fonts has local font fallbacks. Delivery remains simulated. The ZIP excludes credentials, databases, node_modules, build output and internal QA fixtures. Public deployment is not included.
