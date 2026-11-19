"""Server-only local demonstration credentials."""

import os, secrets
from pathlib import Path
from fastapi import Header, HTTPException
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def validate_keys():
    operator = os.getenv("CORTEX_OPERATOR_KEY", "")
    reviewer = os.getenv("CORTEX_REVIEWER_KEY", "")
    if (
        len(operator) < 16
        or len(reviewer) < 16
        or secrets.compare_digest(operator, reviewer)
    ):
        raise RuntimeError(
            "Set distinct CORTEX_OPERATOR_KEY and CORTEX_REVIEWER_KEY values of at least 16 characters in root .env."
        )


def require_operator(x_operator_key: str | None = Header(default=None)):
    expected = os.getenv("CORTEX_OPERATOR_KEY", "")
    if (
        not expected
        or not x_operator_key
        or not secrets.compare_digest(expected, x_operator_key)
    ):
        raise HTTPException(401, "INVALID_OPERATOR_CREDENTIAL")
    return "operator"


def require_reviewer(x_reviewer_key: str | None = Header(default=None)):
    expected = os.getenv("CORTEX_REVIEWER_KEY", "")
    if (
        not expected
        or not x_reviewer_key
        or not secrets.compare_digest(expected, x_reviewer_key)
    ):
        raise HTTPException(401, "INVALID_REVIEWER_CREDENTIAL")
    return "reviewer"
