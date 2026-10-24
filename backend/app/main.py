"""Local demo API. Outbound email is simulated; no real mail credentials exist."""

from contextlib import asynccontextmanager
import os, uuid
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from .config import validate_keys
from .database import init_db, SessionLocal
from .seed import seed
from .routers.core import router as core_router


@asynccontextmanager
async def lifespan(app):
    validate_keys()
    init_db()
    with SessionLocal() as db:
        seed(db)
    yield


app = FastAPI(title="Cortex Lock", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Operator-Key", "X-Reviewer-Key"],
)
app.include_router(core_router)
try:
    from .routers.intelligence import router as intelligence_router

    app.include_router(intelligence_router)
    INTELLIGENCE_READY = True
except ModuleNotFoundError as error:
    if error.name != "backend.app.routers.intelligence":
        raise
    INTELLIGENCE_READY = False


@app.exception_handler(HTTPException)
async def http_error(request: Request, error: HTTPException):
    return JSONResponse(
        status_code=error.status_code,
        content={
            "error": {
                "code": (
                    error.detail
                    if isinstance(error.detail, str)
                    else "REQUEST_REJECTED"
                ),
                "message": "Request rejected; check the error code and current task state.",
                "request_id": uuid.uuid4().hex,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, error: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "INVALID_REQUEST",
                "message": "Request fields do not match the API schema.",
                "request_id": uuid.uuid4().hex,
            }
        },
    )


@app.exception_handler(Exception)
async def server_error(request: Request, error: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "The request failed; no approval was granted.",
                "request_id": uuid.uuid4().hex,
            }
        },
    )


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "contract_version": "1.0",
        "agent_ready": INTELLIGENCE_READY,
        "model_configured": bool(
            os.getenv("CORTEX_MODEL_API_KEY")
            and os.getenv("CORTEX_MODEL_NAME")
            and os.getenv("CORTEX_MODEL_PROVIDER") == "gemini"
        ),
    }
