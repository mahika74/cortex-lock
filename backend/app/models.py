"""Shared SQLAlchemy records. UTC datetimes are stored without timezone offsets."""

from sqlalchemy import Column, String, Text, DateTime, Integer, JSON, UniqueConstraint
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


Base = declarative_base()


class Agent(Base):
    __tablename__ = "agents"
    agent_id = Column(String, primary_key=True)
    owner = Column(String)
    purpose = Column(String)
    status = Column(String, default="ACTIVE")
    allowed_tools = Column(JSON)
    allowed_resource_ids = Column(JSON)


class Task(Base):
    __tablename__ = "tasks"
    task_id = Column(String, primary_key=True)
    agent_id = Column(String, index=True)
    template_id = Column(String)
    purpose_tag = Column(String)
    objective = Column(Text)
    allowed_resource_ids = Column(JSON)
    allowed_recipients = Column(JSON)
    email_subject = Column(String)
    expires_at = Column(DateTime)
    policy_version = Column(String, default="1.0")


class Resource(Base):
    __tablename__ = "resources"
    resource_id = Column(String, primary_key=True)
    classification = Column(String)
    content = Column(Text)
    content_hash = Column(String)


class Source(Base):
    __tablename__ = "sources"
    source_id = Column(String, primary_key=True)
    task_id = Column(String, index=True, nullable=True)
    name = Column(String)
    content_hash = Column(String)
    source_type = Column(String)
    verification_status = Column(String)
    text = Column(Text)
    created_at = Column(DateTime, default=utcnow)


class Memory(Base):
    __tablename__ = "memories"
    __table_args__ = (UniqueConstraint("task_id", "idempotency_key"),)
    memory_id = Column(String, primary_key=True)
    task_id = Column(String, index=True)
    agent_id = Column(String, index=True)
    purpose_tag = Column(String)
    content = Column(Text)
    source_ids = Column(JSON, default=list)
    derived_memory_ids = Column(JSON, default=list)
    status = Column(String)
    reason_codes = Column(JSON, default=list)
    idempotency_key = Column(String)
    request_hash = Column(String)
    analysis_mode = Column(String)
    error_code = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    expires_at = Column(DateTime)


class Action(Base):
    __tablename__ = "actions"
    __table_args__ = (UniqueConstraint("task_id", "idempotency_key"),)
    action_id = Column(String, primary_key=True)
    task_id = Column(String, index=True)
    run_id = Column(String, nullable=True)
    tool = Column(String)
    args = Column(JSON)
    memory_ids = Column(JSON, default=list)
    source_ids = Column(JSON, default=list)
    idempotency_key = Column(String)
    request_hash = Column(String)
    decision = Column(String)
    reason_codes = Column(JSON, default=list)
    explanation = Column(Text)
    approval_id = Column(String, nullable=True)
    execution_status = Column(String, default="NOT_EXECUTED")
    result = Column(JSON, nullable=True)


class Approval(Base):
    __tablename__ = "approvals"
    approval_id = Column(String, primary_key=True)
    action_id = Column(String, unique=True)
    request_hash = Column(String)
    status = Column(String, default="PENDING")
    expires_at = Column(DateTime)
    reviewer_id = Column(String, nullable=True)
    decided_at = Column(DateTime, nullable=True)
    consumed_at = Column(DateTime, nullable=True)


class Run(Base):
    __tablename__ = "runs"
    run_id = Column(String, primary_key=True)
    task_id = Column(String, index=True)
    mode = Column(String)
    scenario = Column(String)
    status = Column(String, default="QUEUED")
    step_count = Column(Integer, default=0)
    output = Column(JSON, nullable=True)
    error = Column(String, nullable=True)
    state = Column(JSON, default=dict)
    pending_action_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    finished_at = Column(DateTime, nullable=True)


class Event(Base):
    __tablename__ = "events"
    event_id = Column(String, primary_key=True)
    timestamp = Column(DateTime, default=utcnow)
    task_id = Column(String, index=True)
    run_id = Column(String, nullable=True)
    agent_id = Column(String, nullable=True)
    event_type = Column(String)
    status = Column(String)
    reason_codes = Column(JSON, default=list)
    source_ids = Column(JSON, default=list)
    memory_ids = Column(JSON, default=list)
    action_id = Column(String, nullable=True)
    summary = Column(Text)
    event_metadata = Column("metadata", JSON, default=dict)
    mode = Column(String, nullable=True)
    policy_version = Column(String, default="1.0")


class Outbox(Base):
    __tablename__ = "outbox"
    message_id = Column(String, primary_key=True)
    action_id = Column(String, unique=True)
    task_id = Column(String, index=True)
    resource_id = Column(String)
    recipient = Column(String)
    subject = Column(String)
    created_at = Column(DateTime, default=utcnow)
