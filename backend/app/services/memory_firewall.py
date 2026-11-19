"""Pure memory-write policy; persistence, authentication and model calls live elsewhere.

SourceEvidence must come from server records, not an uploaded document's claims.
SemanticReview must come from a validated server-side analysis, never model memory
content or an untrusted HTTP field. No decision here grants tool permissions.
"""

from collections.abc import Mapping
from dataclasses import dataclass
import re
import unicodedata


MAX_CONTENT_BYTES = 8192
MAX_EVIDENCE_IDS = 64
REVIEW_REASONS = frozenset({
    "MEMORY_INSTRUCTION_DETECTED", "SOURCE_AUTHORITY_UNVERIFIED",
    "MEMORY_NOT_TRUSTED", "POLICY_UNAVAILABLE", "INVALID_ARGUMENTS",
})


@dataclass(frozen=True)
class MemoryCandidate:
    content: str
    source_ids: tuple[str, ...]
    derived_memory_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceEvidence:
    source_id: str
    source_type: str  # INTERNAL or EXTERNAL
    verification_status: str  # VERIFIED, UNVERIFIED or REVOKED


@dataclass(frozen=True)
class SemanticReview:
    contains_instruction: bool
    requests_authority_change: bool
    requests_persistence: bool
    sensitive_data_present: bool
    recommended_status: str
    reason_codes: tuple[str, ...]
    explanation: str

    def __post_init__(self):
        for name in (
            "contains_instruction", "requests_authority_change",
            "requests_persistence", "sensitive_data_present",
        ):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be a JSON boolean")
        if self.recommended_status not in ("APPROVED", "QUARANTINED"):
            raise ValueError("Unknown review status")
        if not _valid_ids(self.reason_codes, allow_empty=True):
            raise ValueError("reason_codes must be a tuple of unique strings")
        if not set(self.reason_codes).issubset(REVIEW_REASONS):
            raise ValueError("Unknown review reason code")
        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise ValueError("Review explanation is required")
        if len(self.explanation) > 500:
            raise ValueError("Review explanation is too long")

    @classmethod
    def from_dict(cls, payload: Mapping):
        """Strictly validate the handoff's seven-field structured review schema."""
        required = set(cls.__dataclass_fields__)
        if not isinstance(payload, Mapping) or set(payload) != required:
            raise ValueError("Review fields do not match the analysis schema")
        reasons = payload["reason_codes"]
        if not isinstance(reasons, list):
            raise ValueError("reason_codes must be a JSON array")
        return cls(**{**payload, "reason_codes": tuple(reasons)})


@dataclass(frozen=True)
class MemoryDecision:
    status: str
    reason_codes: tuple[str, ...]
    explanation: str

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "reason_codes": list(self.reason_codes),
            "explanation": self.explanation,
        }


def _valid_ids(values, *, allow_empty=False) -> bool:
    return (
        isinstance(values, tuple)
        and (allow_empty or bool(values))
        and len(values) <= MAX_EVIDENCE_IDS
        and all(isinstance(v, str) and 0 < len(v) <= 128 and v.strip() == v
                for v in values)
        and len(set(values)) == len(values)
    )


def normalize_for_inspection(content: str) -> str:
    """Inspect compatibility characters and common invisible formatting together."""
    normalized = unicodedata.normalize("NFKC", content)
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Cf")
    return " ".join(normalized.casefold().split())


_INSTRUCTIONS = tuple(re.compile(pattern) for pattern in (
    r"\b(?:ignore|disregard|override|bypass)\b.{0,100}"
    r"\b(?:instructions?|rules?|polic\w*|permissions?|checks?|restrictions?)\b",
    r"\b(?:always|from now on|in future|for all future)\b.{0,120}"
    r"\b(?:approve|authorize|trust|allow|send|skip|ignore|grant|treat)\b",
    r"\b(?:remember|memorize|store|save|retain|persist)\b.{0,160}"
    r"\b(?:trust\w*|cfo|manager|admin\w*|authorized|approve|permission\w*|policy|forever|always)\b",
    r"\b(?:send|email|forward|upload|transmit|share)\b.{0,100}"
    r"\b(?:payroll|passwords?|credentials?|bank|secrets?|salary)\b",
))
_AUTHORITY = re.compile(
    r"(?:\b(?:is|as)\b|=)\s+(?:(?:the|an?)\s+)?"
    r"(?:cfo|finance manager|administrator|admin|authorized recipient)\b"
)
_SECRETS = re.compile(
    r"\b(?:password|api[_ -]?key|access[_ -]?token|secret[_ -]?key)\s*[:=]\s*\S+"
)


def _quarantine(*reasons: str, explanation: str) -> MemoryDecision:
    return MemoryDecision("QUARANTINED", tuple(dict.fromkeys(reasons)), explanation)


def evaluate_memory_candidate(
    candidate: MemoryCandidate,
    sources: Mapping[str, SourceEvidence],
    review: SemanticReview | None = None,
    *,
    lineage_validated: bool = False,
) -> MemoryDecision:
    """Return a storage-policy decision without writing anything.

    The integration layer must validate agent/task/source scope and expiry, walk
    ancestor records, then set lineage_validated for candidates with parents.
    Missing semantic analysis fails closed even for a seemingly ordinary fact.
    """
    if not isinstance(candidate, MemoryCandidate) or not isinstance(sources, Mapping):
        return _quarantine("INVALID_ARGUMENTS", explanation="Invalid memory evaluation input.")
    content = candidate.content
    if not isinstance(content, str) or not content.strip():
        return _quarantine("INVALID_ARGUMENTS", explanation="Memory content must be nonempty text.")
    try:
        oversized = len(content.encode("utf-8")) > MAX_CONTENT_BYTES
    except UnicodeError:
        return _quarantine("INVALID_ARGUMENTS", explanation="Memory text has invalid Unicode.")
    if oversized or any(unicodedata.category(c) == "Cc" and c not in "\n\r\t" for c in content):
        return _quarantine("INVALID_ARGUMENTS", explanation="Memory text exceeds size or character limits.")
    if not _valid_ids(candidate.source_ids) or not _valid_ids(candidate.derived_memory_ids, allow_empty=True):
        return _quarantine("INVALID_ARGUMENTS", explanation="Valid unique source and parent IDs are required.")
    if type(lineage_validated) is not bool:
        return _quarantine("INVALID_ARGUMENTS", explanation="Invalid ancestry verification state.")

    selected = []
    for source_id in candidate.source_ids:
        source = sources.get(source_id)
        if (not isinstance(source, SourceEvidence) or source.source_id != source_id
                or source.source_type not in ("INTERNAL", "EXTERNAL")
                or source.verification_status not in ("VERIFIED", "UNVERIFIED", "REVOKED")):
            return _quarantine("SOURCE_AUTHORITY_UNVERIFIED", explanation="Source evidence is missing or invalid.")
        if source.verification_status == "REVOKED":
            return _quarantine("MEMORY_NOT_TRUSTED", explanation="A source has been revoked.")
        selected.append(source)
    if candidate.derived_memory_ids and not lineage_validated:
        return _quarantine("MEMORY_NOT_TRUSTED", explanation="Parent memory lineage has not been validated.")

    normalized = normalize_for_inspection(content)
    if not normalized:
        return _quarantine("INVALID_ARGUMENTS", explanation="Memory text has no inspectable content.")
    reasons = []
    if any(pattern.search(normalized) for pattern in _INSTRUCTIONS):
        reasons.append("MEMORY_INSTRUCTION_DETECTED")
    if _AUTHORITY.search(normalized) and any(
        s.source_type != "INTERNAL" or s.verification_status != "VERIFIED" for s in selected
    ):
        reasons.append("SOURCE_AUTHORITY_UNVERIFIED")
    if _SECRETS.search(normalized):
        reasons.append("MEMORY_NOT_TRUSTED")
    if reasons:
        return _quarantine(*reasons, explanation="Memory contains an operating instruction, unsupported authority claim or sensitive value.")

    if review is None:
        return _quarantine("POLICY_UNAVAILABLE", explanation="Semantic analysis is required before memory can be approved.")
    if not isinstance(review, SemanticReview):
        return _quarantine("INVALID_ARGUMENTS", explanation="Semantic analysis did not match the required schema.")
    if review.contains_instruction or review.requests_authority_change or review.requests_persistence:
        return _quarantine("MEMORY_INSTRUCTION_DETECTED", explanation="Semantic analysis flagged a persistent instruction or authority change.")
    if review.sensitive_data_present:
        return _quarantine("MEMORY_NOT_TRUSTED", explanation="Semantic analysis flagged sensitive data in the proposed memory.")
    if review.recommended_status == "QUARANTINED" or review.reason_codes:
        return _quarantine(*(review.reason_codes or ("MEMORY_NOT_TRUSTED",)),
                           explanation="Semantic analysis did not approve this memory.")
    return MemoryDecision("APPROVED", (), "Fact is eligible for scoped storage; provenance and original verification status must be retained.")
