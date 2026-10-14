from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JsonType = JSON().with_variant(JSONB(), "postgresql")


def now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


def _dt(**kw: Any) -> Mapped[datetime | None]:
    return mapped_column(DateTime(timezone=True), nullable=True, **kw)


class Company(Base):
    __tablename__ = "companies"
    name: Mapped[str] = mapped_column(String(300))
    normalized_name: Mapped[str] = mapped_column(String(300), index=True)
    domain: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    website: Mapped[str | None] = mapped_column(String(500))
    stage: Mapped[str | None] = mapped_column(String(100))
    industry: Mapped[str | None] = mapped_column(String(200))
    country: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(String(100))
    employee_range: Mapped[str | None] = mapped_column(String(50))
    is_hiring: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)  # ats slug, unresolved flag
    source: Mapped[str | None] = mapped_column(String(50))
    fetched_at: Mapped[datetime | None] = _dt()
    people: Mapped[list["Person"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    signals: Mapped[list["Signal"]] = relationship(back_populates="company", cascade="all, delete-orphan")


class Person(Base):
    __tablename__ = "people"
    __table_args__ = (Index("ix_people_company_id", "company_id"),)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    full_name: Mapped[str] = mapped_column(String(300))
    title: Mapped[str | None] = mapped_column(String(300))
    role_type: Mapped[str] = mapped_column(String(20), default="other")  # founder|recruiter|exec|other
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    twitter_url: Mapped[str | None] = mapped_column(String(500))
    github_url: Mapped[str | None] = mapped_column(String(500))
    extra: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)  # found_email, found_email_url
    source: Mapped[str | None] = mapped_column(String(50))
    fetched_at: Mapped[datetime | None] = _dt()
    company: Mapped[Company] = relationship(back_populates="people")
    emails: Mapped[list["Email"]] = relationship(back_populates="person", cascade="all, delete-orphan")


class Email(Base):
    __tablename__ = "emails"
    __table_args__ = (UniqueConstraint("person_id", "address"),)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    address: Mapped[str] = mapped_column(String(320), index=True)
    pattern_used: Mapped[str | None] = mapped_column(String(50))
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    mx_valid: Mapped[bool | None] = mapped_column(Boolean)
    smtp_status: Mapped[str] = mapped_column(String(20), default="not_checked")
    verified_at: Mapped[datetime | None] = _dt()
    source: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="unverified")
    person: Mapped[Person] = relationship(back_populates="emails")


class Signal(Base):
    __tablename__ = "signals"
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(20))
    value: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(1000))
    observed_at: Mapped[datetime | None] = _dt()
    source: Mapped[str | None] = mapped_column(String(50))
    company: Mapped[Company] = relationship(back_populates="signals")


class Draft(Base):
    __tablename__ = "drafts"
    __table_args__ = (Index("ix_drafts_status", "status"),)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(String(20))
    llm_provider: Mapped[str] = mapped_column(String(50))
    signals_used: Mapped[list[Any]] = mapped_column(JsonType, default=list)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    reviewed_at: Mapped[datetime | None] = _dt()
    person: Mapped[Person] = relationship()
    company: Mapped[Company] = relationship()


class Suppression(Base):
    __tablename__ = "suppression"
    email_or_domain: Mapped[str] = mapped_column(String(320), unique=True)
    reason: Mapped[str | None] = mapped_column(String(500))


class JobRun(Base):
    __tablename__ = "job_runs"
    __table_args__ = (Index("ix_job_runs_status", "status"),)
    stage: Mapped[str] = mapped_column(String(30))
    source: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    started_at: Mapped[datetime | None] = _dt()
    finished_at: Mapped[datetime | None] = _dt()
    error: Mapped[str | None] = mapped_column(Text)
    stats: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)


class JobLog(Base):
    __tablename__ = "job_logs"
    job_run_id: Mapped[int] = mapped_column(ForeignKey("job_runs.id", ondelete="CASCADE"), index=True)
    level: Mapped[str] = mapped_column(String(10), default="info")
    message: Mapped[str] = mapped_column(Text)


class Schedule(Base):
    __tablename__ = "schedules"
    stage: Mapped[str] = mapped_column(String(30), unique=True)
    cron_expr: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    last_run_at: Mapped[datetime | None] = _dt()
    next_run_at: Mapped[datetime | None] = _dt()


class SourceSetting(Base):
    __tablename__ = "source_settings"
    source_name: Mapped[str] = mapped_column(String(50), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    rate_limit_seconds: Mapped[float] = mapped_column(Float, default=2.0)
    query_filters: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)


class AppSetting(Base):
    """Key/value store. Spec keys: kill_switch, dry_run_default, daily_send_cap (+ internal cancel:<job_id>)."""

    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    value: Mapped[Any] = mapped_column(JsonType)
