import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Text, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from hackucdbackend.models.base import Base, GUID, JSONType


class WeeklyDigest(Base):
    __tablename__ = "weekly_digests"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    family_id = Column(GUID, ForeignKey("family_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    week_start = Column(Date, nullable=False)
    week_end = Column(Date, nullable=False)
    leaderboard_payload = Column(JSONType, nullable=False)
    collective_plant_count = Column(Integer, nullable=False, default=0)
    ai_family_narrative = Column(Text, nullable=False)
    recommended_grocery_swap = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    family = relationship("FamilyGroup", back_populates="digests")
