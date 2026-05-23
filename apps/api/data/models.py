"""SQLAlchemy ORM models for persisting design sessions and user data."""
import uuid
from datetime import datetime

from sqlalchemy import String, JSON, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.data.database import Base


class DesignSession(Base):
    __tablename__ = "design_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String, default="Untitled session")
    goals: Mapped[dict] = mapped_column(JSON, default=dict)
    constraints: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    compositions: Mapped[list["SavedComposition"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class SavedComposition(Base):
    __tablename__ = "saved_compositions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey("design_sessions.id"))
    composition: Mapped[dict] = mapped_column(JSON)        # {"Al": 90, "Mg": 5, "Si": 5}
    properties: Mapped[dict] = mapped_column(JSON, default=dict)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    bookmarked: Mapped[bool] = mapped_column(default=False)
    rejected: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["DesignSession"] = relationship(back_populates="compositions")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey("design_sessions.id"))
    role: Mapped[str] = mapped_column(String)             # "user" | "assistant"
    content: Mapped[str] = mapped_column(String)
    context_type: Mapped[str] = mapped_column(String, default="global")  # "local" | "global"
    selected_element: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["DesignSession"] = relationship(back_populates="messages")
