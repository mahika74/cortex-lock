"""Bounded background runner. LIVE uses model proposals; REPLAY uses labelled fixtures."""

import threading
import time
from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import select
from ..database import SessionLocal
from ..models import Run, Source
from ..schemas.core import ActionRequest
from ..schemas.intelligence import DocumentRequest, MemoryRequest
from .core import (
    get_task_context,
    now,
    new_id,
    serialize,
    append_event,
    evaluate_action,
    execute_action,
)
from .documents import create_document
from .memory_store import evaluate_memory, retrieve_memories, require_active
from .memory_firewall import SemanticReview
from .model_adapter import GeminiMemoryAnalyzer, AnalysisUnavailable
from .agent_model import generate_plan
from .scenarios import NORMAL_TEXT, INJECTION_TEXT, replay_plan

_locks = {}
_guard = threading.Lock()


def run_lock(run_id):
    with _guard:
        return _locks.setdefault(run_id, threading.Lock())


class ReplayFixtureAnalyzer:
    """Offline fixture classifier only. Never used as a LIVE fallback."""

    def review(self, candidate, sources, **kwargs):
        if candidate.content != NORMAL_TEXT:
            return SemanticReview(
                False,
                False,
                False,
                False,
                "QUARANTINED",
                ("MEMORY_NOT_TRUSTED",),
                "Replay fixture is not a recognized benign fact.",
            )
        return SemanticReview(
            False, False, False, False, "APPROVED", (), "Benign synthetic replay fact."
        )


def create_run(db, request):
    context = get_task_context(db, request.task_id)
    require_active(context)
    run = Run(
        run_id=new_id("run"),
        task_id=request.task_id,
        mode=request.mode,
        scenario=request.scenario,
        status="QUEUED",
        step_count=0,
        output=None,
        error=None,
        state={},
        created_at=now(),
    )
    db.add(run)
    append_event(
        db,
        {
            "task_id": request.task_id,
            "run_id": run.run_id,
            "agent_id": context.agent.agent_id,
            "event_type": "RUN_QUEUED",
            "status": "QUEUED",
            "summary": "Run queued.",
            "metadata": {"mode": run.mode},
        },
    )
    db.commit()
    return serialize(run)


def get_run(db, run_id):
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    # Reads expose no model plan or internal scheduling state.
    data = serialize(run)
    data.pop("state", None)
    return data


def _finish(db, run, status, error=None):
    run.status = status
    run.error = error
    if status in ("COMPLETED", "FAILED"):
        run.finished_at = now()
    run.output = {
        "simulation": True,
        "mode": run.mode,
        "proposal_source": "MODEL" if run.mode == "LIVE" else "SCRIPTED_REPLAY",
        "actions": (run.state or {}).get("actions", []),
        "memory_id": (run.state or {}).get("memory_id"),
    }
    append_event(
        db,
        {
            "task_id": run.task_id,
            "run_id": run.run_id,
            "event_type": "RUN_" + status,
            "status": status,
            "summary": "Run " + status.lower().replace("_", " ") + ".",
            "metadata": {"mode": run.mode},
        },
    )
    db.commit()


def process_run(run_id):
    with run_lock(run_id):
        with SessionLocal() as db:
            run = db.get(Run, run_id)
            if run is None or run.status not in ("QUEUED", "WAITING_APPROVAL"):
                return
            analyzer = None
            started = time.monotonic()
            previous_seconds = (run.state or {}).get("processing_seconds", 0)
            deadline = now() + timedelta(seconds=max(0, 90 - previous_seconds))
            try:
                context = get_task_context(db, run.task_id)
                require_active(context)
                run.status = "RUNNING"
                db.commit()
                if now() >= deadline:
                    raise AnalysisUnavailable("RUN_TIME_LIMIT")
                if run.pending_action_id:
                    try:
                        result = execute_action(db, context, run.pending_action_id)
                    except HTTPException as error:
                        if (
                            error.status_code == 409
                            and error.detail == "APPROVAL_NOT_GRANTED"
                        ):
                            _finish(db, run, "WAITING_APPROVAL")
                            return
                        raise
                    if result["execution_status"] == "WAITING_APPROVAL":
                        _finish(db, run, "WAITING_APPROVAL")
                        return
                    state = dict(run.state)
                    state["actions"] = state.get("actions", []) + [
                        {
                            "action_id": result["action_id"],
                            "decision": result["decision"],
                            "execution_status": result["execution_status"],
                        }
                    ]
                    run.state = state
                    run.pending_action_id = None
                    db.commit()
                    if result["execution_status"] != "EXECUTED":
                        _finish(db, run, "FAILED", "REVIEW_NOT_EXECUTABLE")
                        return
                state = dict(run.state or {})
                if "calls" not in state:
                    if run.mode == "LIVE":
                        analyzer = GeminiMemoryAnalyzer.from_environment()
                    else:
                        analyzer = ReplayFixtureAnalyzer()
                    text = (
                        INJECTION_TEXT if run.scenario == "injection" else NORMAL_TEXT
                    )
                    doc = create_document(
                        db,
                        DocumentRequest(
                            task_id=run.task_id,
                            name="Synthetic " + run.scenario + " fixture",
                            content=text,
                        ),
                    )
                    memory = evaluate_memory(
                        db,
                        MemoryRequest(
                            task_id=run.task_id,
                            run_id=run.run_id,
                            content=text,
                            source_ids=[doc["source_id"]],
                            idempotency_key=run.run_id + "-fixture-memory",
                        ),
                        analyzer,
                        configured=True,
                        replay=run.mode == "REPLAY",
                    )
                    if memory["analysis_mode"] == "FAILED":
                        raise AnalysisUnavailable(
                            memory["error_code"] or "MEMORY_ANALYSIS_FAILED"
                        )
                    documents = [
                        {
                            "source_id": s.source_id,
                            "name": s.name,
                            "text": s.text,
                            "verification_status": s.verification_status,
                        }
                        for s in db.scalars(
                            select(Source)
                            .where(Source.task_id == run.task_id)
                            .order_by(Source.created_at.desc())
                            .limit(20)
                        ).all()
                    ]
                    memories = retrieve_memories(db, run.task_id)["items"]
                    directory_source = db.get(Source, "directory_001")
                    directory = (
                        {"manager_emp_001": "manager@company.example"}
                        if (
                            directory_source
                            and directory_source.source_type == "INTERNAL"
                            and directory_source.verification_status == "VERIFIED"
                        )
                        else {}
                    )
                    calls = (
                        generate_plan(
                            analyzer, context.task, documents, memories, directory
                        )
                        if run.mode == "LIVE"
                        else replay_plan(context.task, run.scenario)
                    )
                    if sum(call["tool"] == "propose_memory" for call in calls) > 1:
                        raise AnalysisUnavailable("TOO_MANY_MEMORY_PROPOSALS")
                    # Analyze proposed memories before any business side effect.
                    for index, call in enumerate(calls):
                        if call["tool"] == "propose_memory":
                            if now() >= deadline:
                                raise AnalysisUnavailable("RUN_TIME_LIMIT")
                            proposed = MemoryRequest(
                                task_id=run.task_id,
                                run_id=run.run_id,
                                idempotency_key=run.run_id + "-proposal-" + str(index),
                                **call["args"]
                            )
                            assessed = evaluate_memory(
                                db,
                                proposed,
                                analyzer,
                                configured=True,
                                replay=run.mode == "REPLAY",
                            )
                            if assessed["analysis_mode"] == "FAILED":
                                raise AnalysisUnavailable(
                                    assessed["error_code"] or "MEMORY_ANALYSIS_FAILED"
                                )
                    state = {
                        "calls": calls,
                        "cursor": 0,
                        "actions": [],
                        "memory_id": memory["memory_id"],
                        "source_ids": [d["source_id"] for d in documents],
                        "memory_ids": [m["memory_id"] for m in memories[:64]],
                    }
                    run.state = state
                    db.commit()
                calls = state["calls"]
                while state["cursor"] < len(calls):
                    if now() >= deadline:
                        raise AnalysisUnavailable("RUN_TIME_LIMIT")
                    if run.step_count >= 8:
                        raise AnalysisUnavailable("RUN_STEP_LIMIT")
                    index = state["cursor"]
                    call = calls[index]
                    run.step_count += 1
                    state = {**state, "cursor": index + 1}
                    run.state = state
                    db.commit()
                    if call["tool"] == "propose_memory":
                        continue
                    if call["tool"] == "retrieve_memories":
                        if call["args"]:
                            raise AnalysisUnavailable("INVALID_TOOL_ARGUMENTS")
                        retrieve_memories(db, run.task_id)
                        continue
                    request = ActionRequest(
                        task_id=run.task_id,
                        run_id=run.run_id,
                        tool=call["tool"],
                        args=call["args"],
                        source_ids=state.get("source_ids", []),
                        memory_ids=state.get("memory_ids", []),
                        idempotency_key=run.run_id + "-step-" + str(index),
                    )
                    result = evaluate_action(db, context, request)
                    if result["decision"] == "REQUIRE_APPROVAL":
                        run.pending_action_id = result["action_id"]
                        _finish(db, run, "WAITING_APPROVAL")
                        return
                    if result["decision"] == "ALLOW":
                        result = execute_action(db, context, result["action_id"])
                    state = {
                        **state,
                        "actions": state["actions"]
                        + [
                            {
                                "action_id": result["action_id"],
                                "decision": result["decision"],
                                "execution_status": result["execution_status"],
                            }
                        ],
                    }
                    run.state = state
                    db.commit()
                _finish(db, run, "COMPLETED")
            except Exception as error:
                db.rollback()
                run = db.get(Run, run_id)
                if run:
                    code = (
                        str(error)
                        if isinstance(error, AnalysisUnavailable)
                        else "RUN_FAILED"
                    )
                    _finish(db, run, "FAILED", code)
            finally:
                if run is not None:
                    state = dict(run.state or {})
                    state["processing_seconds"] = (
                        previous_seconds + time.monotonic() - started
                    )
                    run.state = state
                    db.commit()
                if isinstance(analyzer, GeminiMemoryAnalyzer):
                    analyzer.close()
