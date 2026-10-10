import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, Numeric, Boolean,
    DateTime, ForeignKey, CheckConstraint, UniqueConstraint
)
from sqlalchemy.orm import relationship

from hackucdbackend.models.base import Base, GUID, StringListType


class Meal(Base):
    __tablename__ = "meals"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    family_id = Column(GUID, ForeignKey("family_groups.id", ondelete="CASCADE"), nullable=True, index=True)
    image_url = Column(Text, nullable=False)
    preparation_context = Column(String(30), default="home_cooked", nullable=False)
    meal_name = Column(String(150), nullable=True)
    detected_ingredients = Column(StringListType, default=list, nullable=False)
    plant_colors = Column(StringListType, default=list, nullable=False)
    upf_tier = Column(String(30), nullable=True)
    plant_score = Column(Integer, default=0, nullable=False)
    whole_food_score = Column(Integer, default=0, nullable=False)
    protein_score = Column(Integer, default=0, nullable=False)
    penalty_score = Column(Integer, default=0, nullable=False)
    raw_score = Column(Integer, default=0, nullable=False)
    normalized_score = Column(Integer, default=0, nullable=False)
    reassurance_note = Column(Text, nullable=True)
    ai_confidence = Column(Numeric(3, 2), nullable=True)
    requires_manual_tags = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "preparation_context IN ('home_cooked', 'takeout', 'dining_hall', 'packaged')",
            name="check_prep_context"
        ),
        CheckConstraint(
            "upf_tier IS NULL OR upf_tier IN ('unprocessed', 'minimally_processed', 'processed', 'ultra_processed')",
            name="check_upf_tier"
        ),
    )

    # Relationships
    user = relationship("User", back_populates="meals")
    family = relationship("FamilyGroup", back_populates="meals")
    reactions = relationship("MealReaction", back_populates="meal", cascade="all, delete-orphan")


class MealReaction(Base):
    __tablename__ = "meal_reactions"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    meal_id = Column(GUID, ForeignKey("meals.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    emoji = Column(String(10), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("meal_id", "user_id", "emoji", name="uq_meal_user_emoji"),
    )

    # Relationships
    meal = relationship("Meal", back_populates="reactions")
    user = relationship("User", back_populates="reactions")
