"""SQLAlchemy ORM models for the AI Interview Coach application."""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional
from uuid import uuid4

from sqlalchemy import String, Text, Integer, DateTime, Enum, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class PlanEnum(PyEnum):
    """User plan types."""
    free = "free"
    pro = "pro"


class InterviewStatusEnum(PyEnum):
    """Interview session status."""
    active = "active"
    completed = "completed"


class User(Base):
    """User model for authentication and plan tracking."""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[PlanEnum] = mapped_column(Enum(PlanEnum), default=PlanEnum.free, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Relationships
    interview_sessions: Mapped[list["InterviewSession"]] = relationship("InterviewSession", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username}, plan={self.plan})>"


class InterviewSession(Base):
    """Interview session model."""
    __tablename__ = "interview_sessions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False, index=True)
    interview_types: Mapped[list[str]] = mapped_column(JSON, nullable=False)  # e.g., ["coding", "resume", "technical", "behavioral"]
    job_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resume_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target_position: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)  # 15, 30, or 60
    user_comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # e.g., "Data Structures & Algorithms"
    status: Mapped[InterviewStatusEnum] = mapped_column(Enum(InterviewStatusEnum), default=InterviewStatusEnum.active, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="interview_sessions")
    qa_pairs: Mapped[list["InterviewQA"]] = relationship("InterviewQA", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<InterviewSession(id={self.id}, user_id={self.user_id}, status={self.status})>"


class InterviewQA(Base):
    """Interview Q&A pair model."""
    __tablename__ = "interview_qa"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("interview_sessions.id"), nullable=False, index=True)
    interview_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "coding", "resume", "technical", "behavioral"
    question: Mapped[str] = mapped_column(Text, nullable=False)
    question_focus: Mapped[str] = mapped_column(Text, nullable=False)  # Key concept being tested
    user_answer: Mapped[str] = mapped_column(Text, nullable=False)
    ai_feedback: Mapped[str] = mapped_column(Text, nullable=False)  # Improvement suggestions
    score: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-100
    depth_layer: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # 1, 2, or 3
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Relationships
    session: Mapped["InterviewSession"] = relationship("InterviewSession", back_populates="qa_pairs")

    def __repr__(self) -> str:
        return f"<InterviewQA(id={self.id}, session_id={self.session_id}, type={self.interview_type})>"
