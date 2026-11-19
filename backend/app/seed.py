"""Idempotent synthetic fixtures; never resets existing user or run state."""

import hashlib
from .database import init_db, SessionLocal
from .models import Agent, Resource, Source


def seed(db):
    if not db.get(Agent, "finance-agent-001"):
        db.add(
            Agent(
                agent_id="finance-agent-001",
                owner="Finance",
                purpose="Scoped sales assistance",
                status="ACTIVE",
                allowed_tools=["read_file", "lookup_employee", "send_email"],
                allowed_resource_ids=["sales_oct_2026", "payroll_oct_2026"],
            )
        )
    for rid, classification, content in [
        (
            "sales_oct_2026",
            "INTERNAL",
            "Synthetic report: October sales increased by 12 percent. Total sales: INR 1200000.",
        ),
        (
            "payroll_oct_2026",
            "CONFIDENTIAL",
            "SYNTHETIC payroll: Demo Employee A; salary INR 50000; invented account DEMO0001.",
        ),
    ]:
        if not db.get(Resource, rid):
            db.add(
                Resource(
                    resource_id=rid,
                    classification=classification,
                    content=content,
                    content_hash=hashlib.sha256(content.encode()).hexdigest(),
                )
            )
    if not db.get(Source, "directory_001"):
        content = "manager_emp_001: manager@company.example"
        db.add(
            Source(
                source_id="directory_001",
                task_id=None,
                name="Verified synthetic employee directory",
                content_hash=hashlib.sha256(content.encode()).hexdigest(),
                source_type="INTERNAL",
                verification_status="VERIFIED",
                text=content,
            )
        )
    db.commit()


if __name__ == "__main__":
    init_db()
    with SessionLocal() as db:
        seed(db)
    print("Synthetic Cortex Lock fixtures are ready; existing records preserved.")
