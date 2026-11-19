"""Exercise the running API with synthetic data; never print credentials."""

from pathlib import Path
import os
import uuid
import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def main():
    load_dotenv(ROOT / ".env")
    key = os.getenv("CORTEX_OPERATOR_KEY")
    reviewer = os.getenv("CORTEX_REVIEWER_KEY")
    if not key or not reviewer:
        raise SystemExit("Run python scripts/setup_local.py first.")
    with httpx.Client(
        base_url="http://127.0.0.1:8000",
        timeout=30,
        trust_env=False,
        headers={"X-Operator-Key": key},
    ) as client:

        def call(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            if not response.is_success:
                raise SystemExit(
                    f"Demo stopped: {method} {path}: HTTP {response.status_code}"
                )
            return response.json()

        print("Health:", call("GET", "/api/health")["status"])

        def task(template):
            return call(
                "POST",
                "/api/tasks",
                json={"agent_id": "finance-agent-001", "template_id": template},
            )["task_id"]

        internal = task("SALES_INTERNAL")

        def action(task_id, resource, recipient):
            return call(
                "POST",
                "/api/actions/evaluate",
                json={
                    "task_id": task_id,
                    "tool": "send_email",
                    "args": {
                        "resource_id": resource,
                        "recipient": recipient,
                        "subject": "October sales summary",
                    },
                    "idempotency_key": str(uuid.uuid4()),
                },
            )

        normal = action(internal, "sales_oct_2026", "manager@company.example")
        assert normal["decision"] == "ALLOW", normal
        sent = call(
            "POST", "/api/actions/execute", json={"action_id": normal["action_id"]}
        )
        assert sent["execution_status"] == "EXECUTED", sent
        call("POST", "/api/actions/execute", json={"action_id": normal["action_id"]})
        assert len(call("GET", f"/api/outbox?task_id={internal}")["items"]) == 1
        print(
            "PASS: normal sales action; repeat execution produces one simulated email."
        )

        for resource, recipient in (
            ("payroll_oct_2026", "manager@company.example"),
            ("sales_oct_2026", "cfo@outside.example"),
        ):
            blocked = action(internal, resource, recipient)
            assert blocked["decision"] == "DENY", blocked
            attempted = call(
                "POST", "/api/actions/execute", json={"action_id": blocked["action_id"]}
            )
            assert attempted["execution_status"] != "EXECUTED", attempted
        assert len(call("GET", f"/api/outbox?task_id={internal}")["items"]) == 1
        print("PASS: payroll and attacker recipient blocked without extra email.")

        external = task("SALES_EXTERNAL_REVIEW")
        pending = action(external, "sales_oct_2026", "finance_auditor@partner.example")
        assert pending["decision"] == "REQUIRE_APPROVAL", pending
        waiting = client.post(
            "/api/actions/execute", json={"action_id": pending["action_id"]}
        )
        assert waiting.status_code == 409, waiting.status_code
        assert not call("GET", f"/api/outbox?task_id={external}")["items"]
        call(
            "POST",
            f"/api/approvals/{pending['approval_id']}/decision",
            json={"decision": "ALLOW_ONCE"},
            headers={"X-Reviewer-Key": reviewer},
        )
        approved = call(
            "POST", "/api/actions/execute", json={"action_id": pending["action_id"]}
        )
        assert approved["execution_status"] == "EXECUTED", approved
        print("PASS: external sales send waits for separate reviewer approval.")

        run = call(
            "POST",
            "/api/runs",
            json={"task_id": internal, "scenario": "injection", "mode": "REPLAY"},
        )
        print(
            "Replay submitted:",
            run["run_id"],
            "(explicit scripted replay; no Gemini call).",
        )
        print("All email delivery is simulated. No real messages were sent.")


if __name__ == "__main__":
    main()
