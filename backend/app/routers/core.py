from fastapi import APIRouter, Depends
from sqlalchemy import select
from ..config import require_operator, require_reviewer
from ..database import get_db
from ..models import Agent, Approval, Event, Outbox
from ..schemas.core import TaskRequest, ActionRequest, ExecuteRequest, ApprovalDecision
from ..services.core import (
    create_task,
    get_task_context,
    require_task,
    evaluate_action,
    execute_action,
    decide_approval,
    serialize,
)

router = APIRouter(prefix="/api", tags=["Core security"])


@router.get("/actions", dependencies=[Depends(require_operator)])
def action_records(task_id: str, db=Depends(get_db)):
    """Read-only evidence for the UI; controlled tool outputs are not exposed."""
    from ..models import Action

    require_task(db, task_id)
    rows = db.scalars(select(Action).where(Action.task_id == task_id).limit(500))
    items = []
    for row in rows:
        record = serialize(row)
        record.pop("result", None)
        record.pop("idempotency_key", None)
        items.append(record)
    return {"items": items}


@router.get("/agents", dependencies=[Depends(require_operator)])
def agents(db=Depends(get_db)):
    return {"items": [serialize(a) for a in db.scalars(select(Agent))]}


@router.post("/tasks", status_code=201)
def tasks(body: TaskRequest, operator=Depends(require_operator), db=Depends(get_db)):
    return serialize(create_task(db, operator, body.agent_id, body.template_id))


@router.get("/tasks/{task_id}", dependencies=[Depends(require_operator)])
def task(task_id: str, db=Depends(get_db)):
    return serialize(require_task(db, task_id))


@router.post("/actions/evaluate", dependencies=[Depends(require_operator)])
def evaluate(body: ActionRequest, db=Depends(get_db)):
    return evaluate_action(db, get_task_context(db, body.task_id), body)


@router.post("/actions/execute", dependencies=[Depends(require_operator)])
def execute(body: ExecuteRequest, db=Depends(get_db)):
    from ..models import Action
    from fastapi import HTTPException

    action = db.get(Action, body.action_id)
    if not action:
        raise HTTPException(404, "ACTION_NOT_FOUND")
    return execute_action(db, get_task_context(db, action.task_id), body.action_id)


@router.get("/approvals", dependencies=[Depends(require_operator)])
def approvals(task_id: str, db=Depends(get_db)):
    from ..models import Action

    require_task(db, task_id)
    return {
        "items": [
            serialize(a)
            for a in db.scalars(
                select(Approval)
                .join(Action, Approval.action_id == Action.action_id)
                .where(Action.task_id == task_id)
            )
        ]
    }


@router.post("/approvals/{approval_id}/decision")
def approval_decision(
    approval_id: str,
    body: ApprovalDecision,
    reviewer=Depends(require_reviewer),
    db=Depends(get_db),
):
    return serialize(decide_approval(db, approval_id, body.decision, reviewer))


@router.get("/events", dependencies=[Depends(require_operator)])
def events(task_id: str, db=Depends(get_db)):
    require_task(db, task_id)
    return {
        "items": [
            serialize(a)
            for a in db.scalars(
                select(Event)
                .where(Event.task_id == task_id)
                .order_by(Event.timestamp, Event.event_id)
                .limit(500)
            )
        ]
    }


@router.get("/outbox", dependencies=[Depends(require_operator)])
def outbox(task_id: str, db=Depends(get_db)):
    require_task(db, task_id)
    return {
        "items": [
            serialize(a)
            for a in db.scalars(
                select(Outbox)
                .where(Outbox.task_id == task_id)
                .order_by(Outbox.created_at)
            )
        ]
    }
