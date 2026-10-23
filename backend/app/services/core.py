"""Deterministic task enforcement; all tools execute only through this gateway."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib, json, uuid
from fastapi import HTTPException
from sqlalchemy import select, text
from ..models import (
    Agent,
    Task,
    Resource,
    Source,
    Memory,
    Action,
    Approval,
    Run,
    Event,
    Outbox,
)
from ..schemas.core import ActionRequest


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_id(prefix):
    return prefix + "_" + uuid.uuid4().hex


def serialize(record):
    result = {}
    for prop in record.__mapper__.column_attrs:
        value = getattr(record, prop.key)
        result["metadata" if prop.key == "event_metadata" else prop.key] = (
            value.isoformat() + "Z" if isinstance(value, datetime) else value
        )
    return result


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()


def require_task(db, task_id):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(404, "TASK_NOT_FOUND")
    return task


@dataclass
class AgentContext:
    agent: Agent
    task: Task


def get_task_context(db, task_id):
    task = require_task(db, task_id)
    agent = db.get(Agent, task.agent_id)
    if not agent:
        raise HTTPException(404, "AGENT_NOT_FOUND")
    return AgentContext(agent, task)


def append_event(db, event):
    payload = dict(event)
    payload.setdefault("event_id", new_id("evt"))
    payload.setdefault("timestamp", now())
    payload["event_metadata"] = payload.pop(
        "metadata", payload.pop("event_metadata", {})
    )
    payload.setdefault("reason_codes", [])
    payload.setdefault("source_ids", [])
    payload.setdefault("memory_ids", [])
    obj = Event(**payload)
    db.add(obj)
    return obj


def create_task(db, operator, agent_id, template_id):
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "AGENT_NOT_FOUND")
    if agent.status != "ACTIVE":
        raise HTTPException(409, "AGENT_SUSPENDED")
    if template_id not in ("SALES_INTERNAL", "SALES_EXTERNAL_REVIEW"):
        raise HTTPException(422, "UNKNOWN_TEMPLATE")
    task = Task(
        task_id=new_id("task"),
        agent_id=agent_id,
        template_id=template_id,
        purpose_tag="SALES_REPORTING",
        objective="Summarize October sales and send the approved sales report to the template recipient.",
        allowed_resource_ids=["sales_oct_2026"],
        allowed_recipients=[
            (
                "manager@company.example"
                if template_id == "SALES_INTERNAL"
                else "finance_auditor@partner.example"
            )
        ],
        email_subject="October sales summary",
        expires_at=now() + timedelta(hours=2),
        policy_version="1.0",
    )
    db.add(task)
    append_event(
        db,
        dict(
            task_id=task.task_id,
            agent_id=agent_id,
            event_type="TASK_CREATED",
            status="ACTIVE",
            summary="Trusted sales task created.",
        ),
    )
    db.commit()
    return task


def _memory_ok(db, memory, task, seen=None, depth=0):
    seen = set() if seen is None else seen
    if not memory or depth > 32 or memory.memory_id in seen:
        return False
    if (
        memory.agent_id != task.agent_id
        or memory.purpose_tag != task.purpose_tag
        or memory.status != "APPROVED"
        or not memory.expires_at
        or memory.expires_at <= now()
    ):
        return False
    # A memory may persist across tasks of the same purpose; original sources must belong to its original task.
    if not memory.source_ids:
        return False
    for source_id in memory.source_ids:
        source = db.get(Source, source_id)
        if (
            not source
            or source.verification_status not in ("VERIFIED", "UNVERIFIED")
            or source.task_id not in (None, memory.task_id)
        ):
            return False
    seen = seen | {memory.memory_id}
    return all(
        _memory_ok(db, db.get(Memory, p), task, seen, depth + 1)
        for p in memory.derived_memory_ids or []
    )


def _policy(db, context, request):
    agent = db.get(Agent, context.task.agent_id)
    task = require_task(db, request.task_id)

    def deny(code):
        return ("DENY", [code], "The request is outside the current trusted policy.")

    if (
        context.task.task_id != task.task_id
        or not agent
        or agent.agent_id != task.agent_id
    ):
        return deny("IDENTITY_MISMATCH")
    if agent.status != "ACTIVE":
        return deny("AGENT_SUSPENDED")
    if task.expires_at <= now():
        return deny("TASK_EXPIRED")
    if task.policy_version != "1.0":
        return deny("POLICY_UNAVAILABLE")
    if request.run_id:
        run = db.get(Run, request.run_id)
        if not run or run.task_id != task.task_id:
            return deny("RUN_OUTSIDE_TASK")
    if request.tool not in (
        "read_file",
        "lookup_employee",
        "send_email",
    ) or request.tool not in (agent.allowed_tools or []):
        return deny("TOOL_NOT_ALLOWED")
    if len(set(request.source_ids)) != len(request.source_ids) or len(
        set(request.memory_ids)
    ) != len(request.memory_ids):
        return deny("INVALID_EVIDENCE")
    for sid in request.source_ids:
        source = db.get(Source, sid)
        if (
            not source
            or source.task_id not in (None, task.task_id)
            or source.verification_status not in ("VERIFIED", "UNVERIFIED")
        ):
            return deny("SOURCE_OUTSIDE_TASK")
    for mid in request.memory_ids:
        if not _memory_ok(db, db.get(Memory, mid), task):
            return deny("MEMORY_NOT_TRUSTED")
    args = request.args
    expected = {
        "read_file": {"resource_id"},
        "lookup_employee": {"employee_id"},
        "send_email": {"resource_id", "recipient", "subject"},
    }[request.tool]
    if set(args) != expected or any(type(v) is not str for v in args.values()):
        return deny("INVALID_ARGUMENTS")
    if request.tool == "lookup_employee":
        if (
            args["employee_id"] != "manager_emp_001"
            or task.template_id != "SALES_INTERNAL"
        ):
            return deny("EMPLOYEE_OUTSIDE_TASK")
        directory = db.get(Source, "directory_001")
        if not directory or directory.verification_status != "VERIFIED":
            return deny("DIRECTORY_UNAVAILABLE")
    else:
        rid = args["resource_id"]
        resource = db.get(Resource, rid)
        if (
            not resource
            or rid not in (agent.allowed_resource_ids or [])
            or rid not in (task.allowed_resource_ids or [])
        ):
            return deny("RESOURCE_OUTSIDE_TASK")
        if resource.classification != "INTERNAL" or rid != "sales_oct_2026":
            return deny("RESOURCE_CLASSIFICATION_DENIED")
        if request.tool == "send_email":
            if args["recipient"].strip().lower() == "cfo@outside.example":
                return deny("ATTACKER_RECIPIENT_BLOCKED")
            if args["recipient"] not in (task.allowed_recipients or []):
                return deny("RECIPIENT_NOT_ALLOWED")
            if args["subject"] != task.email_subject or len(args["subject"]) > 120:
                return deny("SUBJECT_NOT_ALLOWED")
            if task.template_id == "SALES_EXTERNAL_REVIEW":
                return (
                    "REQUIRE_APPROVAL",
                    ["EXTERNAL_SEND_REQUIRES_REVIEW"],
                    "The scoped external sales transfer requires one-time human review.",
                )
    return ("ALLOW", [], "Request matches the current trusted task policy.")


def _request(action):
    return ActionRequest(
        task_id=action.task_id,
        run_id=action.run_id,
        tool=action.tool,
        args=action.args,
        memory_ids=action.memory_ids,
        source_ids=action.source_ids,
        idempotency_key=action.idempotency_key,
    )


def _result(action):
    return {
        k: getattr(action, k)
        for k in (
            "action_id",
            "decision",
            "reason_codes",
            "explanation",
            "approval_id",
            "execution_status",
            "result",
        )
    }


def evaluate_action(db, context, request):
    if not isinstance(request, ActionRequest):
        request = ActionRequest.model_validate(request)
    fingerprint = digest(request.model_dump())
    old = db.scalar(
        select(Action).where(
            Action.task_id == request.task_id,
            Action.idempotency_key == request.idempotency_key,
        )
    )
    if old:
        if old.request_hash != fingerprint:
            raise HTTPException(409, "IDEMPOTENCY_CONFLICT")
        return _result(old)
    decision, reasons, explanation = _policy(db, context, request)
    action = Action(
        action_id=new_id("act"),
        **request.model_dump(),
        request_hash=fingerprint,
        decision=decision,
        reason_codes=reasons,
        explanation=explanation,
        execution_status="NOT_EXECUTED"
    )
    if decision == "REQUIRE_APPROVAL":
        approval = Approval(
            approval_id=new_id("apr"),
            action_id=action.action_id,
            request_hash=fingerprint,
            status="PENDING",
            expires_at=now() + timedelta(seconds=120),
        )
        db.add(approval)
        action.approval_id = approval.approval_id
        action.execution_status = "WAITING_APPROVAL"
    db.add(action)
    append_event(
        db,
        dict(
            task_id=request.task_id,
            run_id=request.run_id,
            agent_id=context.agent.agent_id,
            event_type="ACTION_EVALUATED",
            status=decision,
            reason_codes=reasons,
            source_ids=request.source_ids,
            memory_ids=request.memory_ids,
            action_id=action.action_id,
            summary=explanation,
        ),
    )
    db.commit()
    return _result(action)


def execute_action(db, context, action_id):
    # BEGIN IMMEDIATE serializes SQLite execution across processes before reading mutable approval state.
    db.rollback()
    db.execute(text("BEGIN IMMEDIATE"))
    try:
        action = db.get(Action, action_id, populate_existing=True)
        if not action or action.task_id != context.task.task_id:
            raise HTTPException(404, "ACTION_NOT_FOUND")
        if action.execution_status == "EXECUTED":
            db.commit()
            return _result(action)
        request = _request(action)
        if digest(request.model_dump()) != action.request_hash:
            raise HTTPException(409, "ACTION_INTEGRITY_FAILURE")
        decision, reasons, explanation = _policy(db, context, request)
        if decision == "DENY" or action.decision == "DENY":
            action.decision = "DENY"
            action.reason_codes = reasons or action.reason_codes
            action.execution_status = "NOT_EXECUTED"
            action.result = None
            append_event(
                db,
                dict(
                    task_id=action.task_id,
                    run_id=action.run_id,
                    agent_id=context.agent.agent_id,
                    event_type="ACTION_BLOCKED",
                    status="DENY",
                    reason_codes=action.reason_codes,
                    action_id=action.action_id,
                    summary="Execution blocked by the current trusted policy.",
                ),
            )
            db.commit()
            return _result(action)
        approval = None
        if decision == "REQUIRE_APPROVAL":
            approval = db.get(Approval, action.approval_id, populate_existing=True)
            if (
                not approval
                or approval.request_hash != action.request_hash
                or approval.action_id != action.action_id
            ):
                raise HTTPException(409, "APPROVAL_BINDING_INVALID")
            if approval.expires_at <= now():
                approval.status = "EXPIRED"
                db.commit()
                raise HTTPException(409, "APPROVAL_EXPIRED")
            if approval.status != "APPROVED":
                raise HTTPException(409, "APPROVAL_NOT_GRANTED")
        args = action.args
        if action.tool == "read_file":
            resource = db.get(Resource, args["resource_id"])
            result = {
                "resource_id": resource.resource_id,
                "content": resource.content,
                "classification": resource.classification,
            }
        elif action.tool == "lookup_employee":
            result = {
                "employee_id": "manager_emp_001",
                "email": "manager@company.example",
            }
        else:
            message = Outbox(
                message_id=new_id("msg"),
                action_id=action_id,
                task_id=action.task_id,
                resource_id=args["resource_id"],
                recipient=args["recipient"],
                subject=args["subject"],
            )
            db.add(message)
            result = {"message_id": message.message_id, "simulation": True}
        if approval:
            approval.status = "CONSUMED"
            approval.consumed_at = now()
        action.result = result
        action.execution_status = "EXECUTED"
        append_event(
            db,
            dict(
                task_id=action.task_id,
                run_id=action.run_id,
                agent_id=context.agent.agent_id,
                event_type="ACTION_EXECUTED",
                status="EXECUTED",
                action_id=action.action_id,
                summary="Controlled tool executed in the local simulated environment.",
            ),
        )
        db.commit()
        return _result(action)
    except Exception:
        db.rollback()
        raise


def decide_approval(db, approval_id, decision, reviewer="reviewer"):
    db.rollback()
    db.execute(text("BEGIN IMMEDIATE"))
    try:
        approval = db.get(Approval, approval_id, populate_existing=True)
        if not approval:
            raise HTTPException(404, "APPROVAL_NOT_FOUND")
        if approval.status != "PENDING":
            raise HTTPException(409, "APPROVAL_ALREADY_DECIDED")
        if approval.expires_at <= now():
            approval.status = "EXPIRED"
            db.commit()
            raise HTTPException(409, "APPROVAL_EXPIRED")
        action = db.get(Action, approval.action_id)
        context = get_task_context(db, action.task_id)
        if (
            digest(_request(action).model_dump()) != approval.request_hash
            or _policy(db, context, _request(action))[0] != "REQUIRE_APPROVAL"
        ):
            raise HTTPException(409, "APPROVAL_NO_LONGER_VALID")
        approval.status = "APPROVED" if decision == "ALLOW_ONCE" else "DENIED"
        approval.reviewer_id = reviewer
        approval.decided_at = now()
        append_event(
            db,
            dict(
                task_id=action.task_id,
                run_id=action.run_id,
                agent_id=context.agent.agent_id,
                event_type="APPROVAL_DECIDED",
                status=approval.status,
                action_id=action.action_id,
                summary="Human review decision recorded.",
            ),
        )
        db.commit()
        return approval
    except Exception:
        db.rollback()
        raise
