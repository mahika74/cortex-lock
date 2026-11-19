# Validation of the combined backend

Validated in the development environment on 23 October 2026 with Python 3.12. Your existing memory firewall and model adapter are retained.

- Offline tests cover memory rules, Gemini response validation, shared action policy, document intake, memory persistence and ancestry, and the integrated runner.
- Core security tests include concurrent execution against file-backed SQLite: two requests produce one simulated outbox message.
- The running HTTP API was started with a fresh temporary database and tested using `scripts/demo_backend.py`: normal send, duplicate execution, payroll denial, attacker recipient denial, reviewer approval, and replay submission passed.
- The local setup script was run twice in a temporary project: the existing model key was preserved, credentials were added once, and private data paths were ignored.
- LIVE runner dispatch is tested using a clearly identified fake structured model. The newly integrated LIVE runner has not been called with your real Gemini key in this environment. Your earlier live memory-analysis demo succeeded on your laptop; run LIVE again after installation to verify the whole workflow.

Run the complete test command shown in `TONIGHT_SETUP.md` on your laptop. The server is intended to run locally as a single Uvicorn worker. Restarted processes do not automatically resume interrupted runs; create a new run. Approval processing remains protected by SQLite transactions. Database upgrades/migrations and a durable background job queue are outside this hackathon package.
