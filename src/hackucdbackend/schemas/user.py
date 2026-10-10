from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class DemographicProfile(BaseModel):
    age: int = Field(..., ge=1, le=120, description="Age in years")
    sex: str = Field(..., pattern="^(male|female|other)$", description="Biological sex")
    activity_level: str = Field(
        default="moderate",
        pattern="^(sedentary|moderate|active|athlete)$",
        description="Daily physical activity level",
    )
    role: str = Field(..., pattern="^(student|parent|member)$", description="Role in family/community")


class UserRegisterRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255, description="Unique user email")
    password: str = Field(..., min_length=6, description="User password (min 6 characters)")
    full_name: str = Field(..., min_length=1, max_length=100, description="User full name")
    role: str = Field(..., pattern="^(student|parent|member)$", description="Role: student, parent, or member")
    age: int = Field(..., ge=1, le=120, description="User age")
    sex: str = Field(..., pattern="^(male|female|other)$", description="Sex: male, female, other")
    activity_level: str = Field(
        default="moderate",
        pattern="^(sedentary|moderate|active|athlete)$",
        description="Activity level",
    )
    dietary_flags: List[str] = Field(default_factory=list, description="Dietary flags e.g. halal, vegetarian")


class UserLoginRequest(BaseModel):
    email: str = Field(..., description="User email")
    password: str = Field(..., description="User password")


class UserLoginResponse(BaseModel):
    user: "UserResponse"
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: str
    age: int
    sex: str
    activity_level: str
    dietary_flags: List[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserRegisterResponse(BaseModel):
    user: UserResponse
    access_token: str
    token_type: str = "bearer"


class UserMeResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    profile: DemographicProfile
    dietary_flags: List[str]
    family_id: Optional[UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
