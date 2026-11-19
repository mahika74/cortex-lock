import unittest
from datetime import timedelta
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from backend.app.models import Base, Agent, Action, Approval, Outbox, Source
from backend.app.seed import seed
from backend.app.schemas.core import ActionRequest
from backend.app.services.core import *


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine, expire_on_commit=False)()
        seed(self.db)
        self.task = create_task(
            self.db, "operator", "finance-agent-001", "SALES_INTERNAL"
        )
        self.ctx = get_task_context(self.db, self.task.task_id)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def action(self, tool="read_file", args=None, key=None, **kwargs):
        return evaluate_action(
            self.db,
            self.ctx,
            ActionRequest(
                task_id=self.task.task_id,
                tool=tool,
                args=args or {"resource_id": "sales_oct_2026"},
                idempotency_key=key or new_id("test"),
                **kwargs
            ),
        )

    def external(self):
        self.task = create_task(
            self.db, "operator", "finance-agent-001", "SALES_EXTERNAL_REVIEW"
        )
        self.ctx = get_task_context(self.db, self.task.task_id)

    def send(self, recipient="manager@company.example", key=None):
        return self.action(
            "send_email",
            {
                "resource_id": "sales_oct_2026",
                "recipient": recipient,
                "subject": "October sales summary",
            },
            key,
        )

    def test_sales_allowed(self):
        self.assertEqual(self.action()["decision"], "ALLOW")

    def test_payroll_denied_despite_standing_access(self):
        self.assertEqual(
            self.action(args={"resource_id": "payroll_oct_2026"})["reason_codes"],
            ["RESOURCE_OUTSIDE_TASK"],
        )

    def test_wrong_recipient_denied(self):
        self.assertEqual(self.send("cfo@outside.example")["decision"], "DENY")

    def test_evaluate_no_outbox(self):
        self.send()
        self.assertEqual(len(list(self.db.scalars(select(Outbox)))), 0)

    def test_execute_send_is_idempotent(self):
        action = self.send()
        one = execute_action(self.db, self.ctx, action["action_id"])
        two = execute_action(self.db, self.ctx, action["action_id"])
        self.assertEqual(one, two)
        self.assertEqual(len(list(self.db.scalars(select(Outbox)))), 1)

    def test_external_requires_review(self):
        self.external()
        action = self.send("finance_auditor@partner.example")
        self.assertEqual(action["decision"], "REQUIRE_APPROVAL")
        with self.assertRaises(HTTPException):
            execute_action(self.db, self.ctx, action["action_id"])
        self.assertEqual(len(list(self.db.scalars(select(Outbox)))), 0)

    def test_review_consumed_atomically(self):
        self.external()
        action = self.send("finance_auditor@partner.example")
        decide_approval(self.db, action["approval_id"], "ALLOW_ONCE")
        execute_action(self.db, self.ctx, action["action_id"])
        self.assertEqual(
            self.db.get(Approval, action["approval_id"]).status, "CONSUMED"
        )

    def test_expired_approval_blocks(self):
        self.external()
        action = self.send("finance_auditor@partner.example")
        decide_approval(self.db, action["approval_id"], "ALLOW_ONCE")
        approval = self.db.get(Approval, action["approval_id"])
        approval.expires_at = now() - timedelta(seconds=1)
        self.db.commit()
        with self.assertRaises(HTTPException):
            execute_action(self.db, self.ctx, action["action_id"])
        self.assertEqual(len(list(self.db.scalars(select(Outbox)))), 0)

    def test_subject_exfiltration_denied(self):
        self.assertEqual(
            self.action(
                "send_email",
                {
                    "resource_id": "sales_oct_2026",
                    "recipient": "manager@company.example",
                    "subject": "secret payroll",
                },
            )["decision"],
            "DENY",
        )

    def test_changed_args_detected(self):
        result = self.send()
        action = self.db.get(Action, result["action_id"])
        action.args = {**action.args, "recipient": "cfo@outside.example"}
        self.db.commit()
        with self.assertRaises(HTTPException):
            execute_action(self.db, self.ctx, action.action_id)

    def test_changed_idempotency_payload_conflicts(self):
        self.action(key="fixed")
        with self.assertRaises(HTTPException):
            self.action(args={"resource_id": "payroll_oct_2026"}, key="fixed")

    def test_policy_rechecked_at_execution(self):
        action = self.send()
        self.ctx.agent.status = "SUSPENDED"
        self.db.commit()
        self.assertEqual(
            execute_action(self.db, self.ctx, action["action_id"])["decision"], "DENY"
        )

    def test_expired_task_denied(self):
        self.task.expires_at = now() - timedelta(seconds=1)
        self.db.commit()
        self.assertEqual(self.action()["reason_codes"], ["TASK_EXPIRED"])

    def test_bad_evidence_denied(self):
        self.assertEqual(self.action(source_ids=["missing"])["decision"], "DENY")

    def test_cross_task_source_denied(self):
        self.db.add(
            Source(
                source_id="wrong",
                task_id="other",
                name="x",
                content_hash="hash",
                source_type="EXTERNAL",
                verification_status="UNVERIFIED",
                text="x",
            )
        )
        self.db.commit()
        self.assertEqual(self.action(source_ids=["wrong"])["decision"], "DENY")

    def test_unknown_tool_denied(self):
        self.assertEqual(self.action(tool="shell")["decision"], "DENY")

    def test_unsupported_policy_denied(self):
        self.task.policy_version = "999"
        self.db.commit()
        self.assertEqual(self.action()["reason_codes"], ["POLICY_UNAVAILABLE"])

    def test_wrong_directory_lookup_denied(self):
        self.assertEqual(
            self.action("lookup_employee", {"employee_id": "cfo"})["decision"], "DENY"
        )

    def test_read_result_only_after_execution(self):
        action = self.action()
        self.assertIsNone(action["result"])
        result = execute_action(self.db, self.ctx, action["action_id"])
        self.assertEqual(result["result"]["classification"], "INTERNAL")

    def test_denied_action_never_executes(self):
        action = self.action(args={"resource_id": "payroll_oct_2026"})
        result = execute_action(self.db, self.ctx, action["action_id"])
        self.assertIsNone(result["result"])
        self.assertEqual(result["execution_status"], "NOT_EXECUTED")

    def test_credentials_are_separate(self):
        from backend.app.config import require_operator, require_reviewer
        from unittest.mock import patch
        import os

        with patch.dict(
            os.environ,
            {
                "CORTEX_OPERATOR_KEY": "operator-test-key-123",
                "CORTEX_REVIEWER_KEY": "reviewer-test-key-123",
            },
        ):
            self.assertEqual(require_operator("operator-test-key-123"), "operator")
            self.assertEqual(require_reviewer("reviewer-test-key-123"), "reviewer")
            with self.assertRaises(HTTPException):
                require_reviewer("operator-test-key-123")
            with self.assertRaises(HTTPException):
                require_operator(None)

    def test_parallel_execution_creates_one_outbox(self):
        import tempfile
        from pathlib import Path
        from concurrent.futures import ThreadPoolExecutor

        with tempfile.TemporaryDirectory() as folder:
            engine = create_engine(
                "sqlite:///" + str(Path(folder) / "parallel.db"),
                connect_args={"check_same_thread": False, "timeout": 15},
            )
            Base.metadata.create_all(engine)
            sessions = sessionmaker(bind=engine, expire_on_commit=False)
            with sessions() as db:
                seed(db)
                task = create_task(
                    db, "operator", "finance-agent-001", "SALES_EXTERNAL_REVIEW"
                )
                tid = task.task_id
                request = ActionRequest(
                    task_id=tid,
                    tool="send_email",
                    args={
                        "resource_id": "sales_oct_2026",
                        "recipient": "finance_auditor@partner.example",
                        "subject": "October sales summary",
                    },
                    idempotency_key="parallel-send",
                )
                action = evaluate_action(db, get_task_context(db, tid), request)
                decide_approval(db, action["approval_id"], "ALLOW_ONCE")
                aid = action["action_id"]

            def send_once(_):
                with sessions() as db:
                    return execute_action(db, get_task_context(db, tid), aid)

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(send_once, range(2)))
            with sessions() as db:
                self.assertEqual(len(list(db.scalars(select(Outbox)))), 1)
            self.assertEqual(results[0], results[1])
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
