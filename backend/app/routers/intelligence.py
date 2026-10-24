from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from ..config import require_operator
from ..database import get_db
from ..models import Memory
from ..schemas.intelligence import (
    DocumentRequest,
    MemoryRequest,
    RunRequest,
    ResumeRequest,
)
from ..services.core import serialize
from ..services.documents import create_document
from ..services.memory_store import evaluate_memory, retrieve_memories
from ..services.agent_runner import create_run, get_run, process_run

router = APIRouter(
    prefix="/api", dependencies=[Depends(require_operator)], tags=["intelligence"]
)


@router.post("/documents", status_code=201)
def document(request: DocumentRequest, db=Depends(get_db)):
    return create_document(db, request)


@router.post("/memories/evaluate")
def memory(request: MemoryRequest, db=Depends(get_db)):
    return evaluate_memory(db, request)


@router.get("/memories/retrieve")
def retrieve(task_id: str, db=Depends(get_db)):
    return retrieve_memories(db, task_id)


@router.get("/memories")
def list_memories(
    agent_id: str,
    task_id: str | None = None,
    status: str | None = None,
    db=Depends(get_db),
):
    query = select(Memory).where(Memory.agent_id == agent_id)
    if task_id:
        query = query.where(Memory.task_id == task_id)
    if status:
        if status not in ("APPROVED", "QUARANTINED", "REVOKED"):
            raise HTTPException(422, "Unknown memory status")
        query = query.where(Memory.status == status)
    return {
        "items": [
            serialize(m)
            for m in db.scalars(query.order_by(Memory.created_at).limit(500)).all()
        ]
    }


@router.post("/runs", status_code=202)
def run(request: RunRequest, background: BackgroundTasks, db=Depends(get_db)):
    created = create_run(db, request)
    background.add_task(process_run, created["run_id"])
    created.pop("state", None)
    return created


@router.get("/runs/{run_id}")
def read_run(run_id: str, db=Depends(get_db)):
    return get_run(db, run_id)


@router.post("/runs/{run_id}/resume", status_code=202)
def resume(
    run_id: str, request: ResumeRequest, background: BackgroundTasks, db=Depends(get_db)
):
    run = get_run(db, run_id)
    if run["status"] == "WAITING_APPROVAL":
        background.add_task(process_run, run_id)
    return run
