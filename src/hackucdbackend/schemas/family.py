from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class FamilyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Family group name")


class FamilyJoinRequest(BaseModel):
    invite_code: str = Field(..., min_length=4, max_length=12, description="Family invite code")


class FamilyMemberItem(BaseModel):
    user_id: UUID
    full_name: str
    role: str
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FamilyResponse(BaseModel):
    id: UUID
    name: str
    invite_code: str
    members: List[FamilyMemberItem] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WeeklyDigestResponse(BaseModel):
    id: UUID
    family_id: UUID
    week_start: date
    week_end: date
    leaderboard_payload: Dict[str, Any]
    collective_plant_count: int
    ai_family_narrative: str
    recommended_grocery_swap: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
