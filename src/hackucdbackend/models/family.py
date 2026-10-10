import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import relationship

from hackucdbackend.models.base import Base, GUID


class FamilyGroup(Base):
    __tablename__ = "family_groups"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    invite_code = Column(String(8), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    members = relationship("FamilyMember", back_populates="family", cascade="all, delete-orphan")
    meals = relationship("Meal", back_populates="family", cascade="all, delete-orphan")
    digests = relationship("WeeklyDigest", back_populates="family", cascade="all, delete-orphan")


class FamilyMember(Base):
    __tablename__ = "family_members"

    family_id = Column(GUID, ForeignKey("family_groups.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    joined_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("family_id", "user_id"),
    )

    # Relationships
    family = relationship("FamilyGroup", back_populates="members")
    user = relationship("User", back_populates="family_memberships")
