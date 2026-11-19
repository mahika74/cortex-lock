import hashlib
import json
from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import select
from ..models import Memory, Source, Run
from .core import get_task_context, now, new_id, serialize, append_event
from .memory_firewall import MemoryCandidate, SourceEvidence
from .model_adapter import (
    GeminiMemoryAnalyzer,
    AnalysisUnavailable,
    analyze_and_evaluate,
    MemoryAssessment,
)


def source_eligible(source, task):
    return (
        source is not None
        and source.task_id in (None, task.task_id)
        and source.verification_status in ("VERIFIED", "UNVERIFIED")
    )


def require_active(context):
    if context.agent.status != "ACTIVE":
        raise HTTPException(409, "AGENT_SUSPENDED")
    if context.task.expires_at <= now():
        raise HTTPException(409, "TASK_EXPIRED")
    if context.task.policy_version != "1.0":
        raise HTTPException(409, "POLICY_UNAVAILABLE")


def memory_eligible(db, memory, task, seen=None, depth=0):
    seen = set() if seen is None else set(seen)
    if (
        memory is None
        or depth >= 32
        or memory.memory_id in seen
        or memory.status != "APPROVED"
        or memory.agent_id != task.agent_id
        or memory.purpose_tag != task.purpose_tag
        or memory.expires_at <= now()
    ):
        return False
    seen.add(memory.memory_id)
    if not memory.source_ids or any(
        (
            db.get(Source, sid) is None
            or db.get(Source, sid).task_id not in (None, memory.task_id)
            or db.get(Source, sid).verification_status not in ("VERIFIED", "UNVERIFIED")
        )
        for sid in memory.source_ids
    ):
        return False
    return all(
        memory_eligible(db, db.get(Memory, mid), task, seen, depth + 1)
        for mid in memory.derived_memory_ids
    )


def retrieve_memories(db, task_id):
    context = get_task_context(db, task_id)
    require_active(context)
    rows = db.scalars(
        select(Memory)
        .where(
            Memory.agent_id == context.task.agent_id,
            Memory.purpose_tag == context.task.purpose_tag,
            Memory.status == "APPROVED",
        )
        .order_by(Memory.created_at)
    ).all()
    return {
        "items": [serialize(m) for m in rows if memory_eligible(db, m, context.task)]
    }


def evaluate_memory(db, request, analyzer=None, *, configured=False, replay=False):
    context = get_task_context(db, request.task_id)
    require_active(context)
    if request.run_id:
        run = db.get(Run, request.run_id)
        if run is None or run.task_id != request.task_id:
            raise HTTPException(422, "Run does not belong to this task")
    payload = request.model_dump()
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    old = db.scalar(
        select(Memory).where(
            Memory.task_id == request.task_id,
            Memory.idempotency_key == request.idempotency_key,
        )
    )
    if old:
        if old.request_hash != digest:
            raise HTTPException(
                409, "Idempotency key already used with different memory"
            )
        return serialize(old)
    sources = {}
    for sid in request.source_ids:
        source = db.get(Source, sid)
        if not source_eligible(source, context.task):
            raise HTTPException(422, "Source is missing, revoked or outside task scope")
        sources[sid] = SourceEvidence(
            sid, source.source_type, source.verification_status
        )
    parent_rows = [db.get(Memory, mid) for mid in request.derived_memory_ids]
    lineage = all(memory_eligible(db, m, context.task) for m in parent_rows)
    # Direct sources remain scoped to this write. Ancestors retain their own source
    # references through derived_memory_ids, walked on every retrieval.
    candidate = MemoryCandidate(
        request.content, tuple(request.source_ids), tuple(request.derived_memory_ids)
    )
    owned = False
    if analyzer is None and not configured:
        try:
            analyzer = GeminiMemoryAnalyzer.from_environment()
            owned = True
        except AnalysisUnavailable:
            analyzer = None
    try:
        assessment = analyze_and_evaluate(
            candidate, sources, analyzer, lineage_validated=lineage
        )
    finally:
        if owned:
            analyzer.close()
    if replay:
        assessment = MemoryAssessment(
            assessment.decision, "REPLAY", assessment.error_code
        )
    created = now()
    expiry = min(
        [created + timedelta(hours=2), context.task.expires_at]
        + [m.expires_at for m in parent_rows if m is not None]
    )
    memory = Memory(
        memory_id=new_id("mem"),
        task_id=request.task_id,
        agent_id=context.agent.agent_id,
        purpose_tag=context.task.purpose_tag,
        content=request.content,
        source_ids=request.source_ids,
        derived_memory_ids=request.derived_memory_ids,
        status=assessment.decision.status,
        reason_codes=list(assessment.decision.reason_codes),
        idempotency_key=request.idempotency_key,
        request_hash=digest,
        analysis_mode=assessment.analysis_mode,
        error_code=assessment.error_code,
        created_at=created,
        expires_at=expiry,
    )
    db.add(memory)
    append_event(
        db,
        {
            "task_id": request.task_id,
            "run_id": request.run_id,
            "agent_id": context.agent.agent_id,
            "event_type": "MEMORY_" + memory.status,
            "status": memory.status,
            "reason_codes": memory.reason_codes,
            "source_ids": memory.source_ids,
            "memory_ids": [memory.memory_id],
            "summary": "Memory evaluated; original source verification is preserved.",
            "metadata": {"mode": assessment.analysis_mode},
        },
    )
    db.commit()
    return serialize(memory)
