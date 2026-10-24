# Member 2 Memory Firewall - first component

This is a pure, database-independent memory-write policy. It is the first part
of Member 2's implementation, not the completed agent or memory store.

## Run the tests

From the repository root, with Python 3.11 or newer:

```powershell
python -m unittest discover -s backend/tests -p test_memory.py -v
```

Or use the local virtual environment:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p test_memory.py -v
```

There are no third-party dependencies for this component. The unittest tests can
also be collected by pytest when the shared backend dependencies are ready.

## Behavior

- Normalize common case, compatibility-character and invisible-format variations
  for inspection. Original content is not silently rewritten.
- Quarantine selected persistent instructions, unsupported identity claims and
  obvious credential assignments, even if advisory analysis says APPROVED.
- Require existing source evidence; reject malformed, missing or revoked sources.
- Require the caller to validate ancestors before accepting derived content.
- Validate the seven-field semantic-review schema from contract 1.0 strictly.
- Quarantine on missing analysis. An ordinary external fact is eligible only
  after a clean review; it still retains UNVERIFIED source status.
- Return only APPROVED or QUARANTINED with contract-compatible reason codes.
  These are memory-storage decisions, never permission to use a business tool.
- Avoid echoing candidate content or model explanations into decision summaries.

## Integration contract

The service exports MemoryCandidate, SourceEvidence, SemanticReview,
MemoryDecision and evaluate_memory_candidate. Construct tuple evidence IDs at the
boundary after validating HTTP JSON. SourceEvidence must be read from trusted
server metadata, never a document's self-declared verification status.

The next Member 2 layer must authenticate the caller; resolve agent, task and
source scope from Member 1's models; validate expiry, revoked status, parent
ancestry and cycles; call a real structured semantic-analysis adapter; run this
gate; then persist the result and record its event using the shared services.
If analysis times out or the review schema fails validation, quarantine the
candidate. Do not catch that error and fall back to APPROVED.

Pass lineage_validated=True only after the server has checked all supplied
ancestors. This first pure function cannot itself query or prove lineage. It
also does not implement authentication, idempotency, TTL, retrieval, database
storage, APIs or action execution. Those remain integration work.

## Limitations and presentation

Pattern checks are a first pass, not comprehensive prompt-injection detection.
Some ordinary quoted or reported instructions may be quarantined. Unknown
paraphrases require semantic analysis, which can also make errors; independent
task and action controls remain necessary. Source labels are provenance, not
proof of factual truth.

The clean and suspicious SemanticReview values in the tests are explicitly
synthetic test fixtures. No test makes a real model call and no live-model
performance claim follows from these test results. Later UI demonstrations must
distinguish LIVE runs from labelled REPLAY scenarios.

Member 1's shared files, database and main branch are not changed by this step.
