import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, CheckConstraint
from sqlalchemy.orm import relationship

from hackucdbackend.models.base import Base, GUID, StringListType


class User(Base):
    __tablename__ = "users"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False)
    age = Column(Integer, nullable=False)
    sex = Column(String(20), nullable=False)
    activity_level = Column(String(30), default="moderate", nullable=False)
    dietary_flags = Column(StringListType, default=list, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint("role IN ('student', 'parent', 'member')", name="check_user_role"),
        CheckConstraint("sex IN ('male', 'female', 'other')", name="check_user_sex"),
        CheckConstraint("activity_level IN ('sedentary', 'moderate', 'active', 'athlete')", name="check_user_activity"),
    )

    # Relationships
    family_memberships = relationship("FamilyMember", back_populates="user", cascade="all, delete-orphan")
    meals = relationship("Meal", back_populates="user", cascade="all, delete-orphan")
    reactions = relationship("MealReaction", back_populates="user", cascade="all, delete-orphan")

    @property
    def profile_dict(self) -> dict:
        return {
            "age": self.age,
            "sex": self.sex,
            "activity_level": self.activity_level,
            "role": self.role,
        }
