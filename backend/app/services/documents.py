import hashlib
import unicodedata
from fastapi import HTTPException
from ..models import Source
from .core import get_task_context, now, new_id, serialize, append_event


def create_document(db, request):
    from .memory_store import require_active

    context = get_task_context(db, request.task_id)
    require_active(context)
    if not request.name.strip() or not request.content.strip():
        raise HTTPException(422, "Name and content must contain text")
    try:
        encoded = request.content.encode("utf-8")
    except UnicodeError:
        raise HTTPException(422, "Invalid Unicode") from None
    if len(encoded) > 51200 or any(
        unicodedata.category(c) == "Cc" and c not in "\r\n\t" for c in request.content
    ):
        raise HTTPException(422, "Document exceeds size or character limits")
    if any(unicodedata.category(c).startswith("C") for c in request.name):
        raise HTTPException(422, "Invalid document name")
    source = Source(
        source_id=new_id("src"),
        task_id=request.task_id,
        name=request.name.strip(),
        text=request.content,
        content_hash=hashlib.sha256(encoded).hexdigest(),
        source_type="EXTERNAL",
        verification_status="UNVERIFIED",
        created_at=now(),
    )
    db.add(source)
    append_event(
        db,
        {
            "task_id": request.task_id,
            "agent_id": context.agent.agent_id,
            "event_type": "DOCUMENT_RECEIVED",
            "status": "UNVERIFIED",
            "source_ids": [source.source_id],
            "summary": "External text received with unverified provenance.",
        },
    )
    db.commit()
    return serialize(source)
