# Cortex Lock: combined backend

This package adds Member 1's shared backend and integrates Member 2's memory components. Arjun can continue the frontend independently against the API below.

## Windows setup from the repository root

1. Copy the ZIP's **backend**, **scripts**, and **docs** folders into `C:\Users\Mahika\cortex-lock`. Merge folders. Keep your existing `.env` and `.venv`.
2. Install and prepare local demo credentials:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe scripts/setup_local.py
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p "test_*.py" -v
```

3. Start the server:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/docs. In a second terminal run:

```powershell
.\.venv\Scripts\python.exe scripts/demo_backend.py
```

The setup script appends separate random operator/reviewer keys to `.env`; it does not replace your Gemini settings. Do not share or commit `.env`. Use the values locally in Swagger or enter them into the frontend at runtime. Keys must not be compiled into frontend code.

## Integration for Arjun

- API origin: `http://127.0.0.1:8000`; frontend origins `http://localhost:5173` and `http://127.0.0.1:5173` are permitted.
- Operator endpoints require `X-Operator-Key`; only approval decisions require `X-Reviewer-Key`.
- Swagger `/docs` supplies the current request schemas. Responses use `task_id`, `run_id`, `action_id`, `memory_id`, and `source_id`.
- Create a task with `agent_id: finance-agent-001` and `template_id: SALES_INTERNAL` or `SALES_EXTERNAL_REVIEW`.
- Run: `POST /api/runs` with `{task_id, scenario: normal|injection, mode: LIVE|REPLAY}`. Poll `GET /api/runs/{run_id}`. Polling never executes actions.
- Display actions and events as actually recorded. `ALLOW` means authorized; only `execution_status: EXECUTED` means completed.
- External sales sends wait for a reviewer. After the approval decision, explicitly `POST /api/runs/{run_id}/resume` with `{}`.
- Memory inspection: `GET /api/memories?agent_id=finance-agent-001&task_id=...`. Safe retrieval: `GET /api/memories/retrieve?task_id=...`.
- Timeline: `GET /api/events?task_id=...`; simulated mail: `GET /api/outbox?task_id=...`.
- Show a clear LIVE or REPLAY badge. REPLAY is a scripted demonstration with no provider calls. LIVE needs your existing local Gemini configuration.

## Demonstrate these outcomes

1. A sales task sends its permitted sales report to its permitted manager through the simulated outbox.
2. The same agent's standing payroll access does not allow payroll in a sales-only task.
3. An external document claiming a new CFO cannot grant recipient authority. Instructional memory is quarantined and excluded from retrieval.
4. An external auditor send requires a separate, expiring, single-use reviewer approval.
5. Repeating execution does not duplicate a simulated email. Expired tasks, revoked sources, and suspended agents fail closed.

## Practical limits

This is a local hackathon demonstration, using synthetic records and simulated email. Memory approval does not verify a statement's truth. Model classification is fallible; the separate action gate enforces the task's permissions. No production identity system, real email delivery, enterprise connectors, or autonomous internet tools are included. Live Gemini behavior must also be checked on your laptop with your key; offline tests do not establish live model accuracy.

Keep SQLite files local. Do not commit `backend/data/`, `.env`, `.venv`, or `__pycache__`. Commit source and tests on your feature branch after checking `git status --short`.
