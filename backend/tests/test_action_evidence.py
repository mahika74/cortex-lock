import unittest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from backend.app.models import Base, Outbox
from backend.app.seed import seed
from backend.app.services.core import create_task, get_task_context, evaluate_action
from backend.app.schemas.core import ActionRequest
from backend.app.routers.core import action_records


class ActionEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine, expire_on_commit=False)()
        seed(self.db)
        self.task = create_task(
            self.db, "operator", "finance-agent-001", "SALES_INTERNAL"
        )
        self.other = create_task(
            self.db, "operator", "finance-agent-001", "SALES_INTERNAL"
        )
        self.action = evaluate_action(
            self.db,
            get_task_context(self.db, self.task.task_id),
            ActionRequest(
                task_id=self.task.task_id,
                tool="read_file",
                args={"resource_id": "payroll_oct_2026"},
                idempotency_key="evidence-test",
            ),
        )

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_evidence_preserves_exact_rejected_resource_and_decision(self):
        row = action_records(self.task.task_id, self.db)["items"][0]
        self.assertEqual(row["args"], {"resource_id": "payroll_oct_2026"})
        self.assertEqual(row["decision"], "DENY")
        self.assertEqual(row["execution_status"], "NOT_EXECUTED")

    def test_does_not_expose_tool_output_or_internal_idempotency_key(self):
        row = action_records(self.task.task_id, self.db)["items"][0]
        self.assertNotIn("result", row)
        self.assertNotIn("idempotency_key", row)

    def test_task_scoped_and_read_only(self):
        self.assertEqual(action_records(self.other.task_id, self.db)["items"], [])
        action_records(self.task.task_id, self.db)
        action_records(self.task.task_id, self.db)
        self.assertEqual(len(list(self.db.scalars(select(Outbox)))), 0)

    def test_unknown_task_rejected(self):
        with self.assertRaises(HTTPException) as caught:
            action_records("missing-task", self.db)
        self.assertEqual(caught.exception.status_code, 404)
