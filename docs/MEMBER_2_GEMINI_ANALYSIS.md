# Member 2 Gemini memory analysis

This adds structured semantic analysis to the existing pure Memory Firewall.
It does not yet implement the database, authenticated APIs, agent task runner,
memory retrieval or business-action execution.

## Setup

Use the project's existing virtual environment and ignored root .env file.
Install google-genai and python-dotenv. Configure CORTEX_MODEL_PROVIDER=gemini,
CORTEX_MODEL_NAME with the free-tier model you verified, and
CORTEX_MODEL_API_KEY locally. Never commit the actual .env or paste its key.
There is no automatic fallback to a different model or paid service.

## Offline tests

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p "test_*.py" -v
```

These tests use a mocked Gemini transport, not real LLM responses. The original
22 rule tests are retained, and the adapter tests exercise safe failures,
structured-output validation, provenance checks and request construction.

## Small live demonstration

```powershell
.\.venv\Scripts\python.exe -m backend.app.services.memory_demo
```

The three synthetic candidates are an ordinary sales fact, a known poisoning
pattern, and a paraphrased future instruction. The known pattern is stopped
locally. At most two model requests are made. Intended decisions are APPROVED,
QUARANTINED, QUARANTINED. Actual semantic decisions depend on the model; inspect
the real result rather than assuming success. analysis_mode is RULES_ONLY,
LIVE or FAILED. A failed model call returns quarantine and a safe error code.

Each provider request has no tools, no prior conversation and store=False.
This disables the Interactions conversation-storage feature, not all provider
retention or free-tier data policies. The configured SDK timeout is 25 seconds
and automatic retry attempts are limited to one. Test only synthetic content.

## Shared backend integration

The application loads configuration once and creates GeminiMemoryAnalyzer.
Member 2's persistence service first resolves authenticated task/agent scope,
valid source records, expiry and all ancestor checks from Member 1's models.
It then calls analyze_and_evaluate(candidate, sources, analyzer), persists the
decision and provenance, and writes the shared event. Supply
lineage_validated=True only after database-backed ancestry verification.

The adapter parses the seven-field contract 1.0 schema through
SemanticReview.from_dict. Extra fields, string booleans, unknown reasons,
duplicate JSON keys, missing fields, empty output and invalid JSON fail closed.
Final independent policy checks override a permissive model recommendation.
No model explanation or raw provider exception is echoed into result summaries.

## Known limits

Separation of system instructions and candidate data reduces ambiguity but does
not prove prompt-injection immunity. Both patterns and semantic analysis can
make mistakes. Independent action authorization remains required. APPROVED is
eligibility for scoped storage, not factual verification or a permission grant.
Persistence, retrieval, approvals and cross-session behavior still need their
separate implementation and integration tests.

Official references checked 22 October 2026:
- https://ai.google.dev/gemini-api/docs/structured-output
- https://ai.google.dev/gemini-api/docs/interactions-overview
- https://googleapis.github.io/python-genai/
