from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class AIMealAnalysis(BaseModel):
    meal_name: str = Field(description="Name or concise description of the plate")
    detected_ingredients: List[str] = Field(default_factory=list, description="Identifiable ingredients on plate")
    plant_colors: List[str] = Field(
        default_factory=list,
        description="Detected plant colors: green, red, orange, yellow_white, purple",
    )
    upf_tier: str = Field(
        description="One of: unprocessed, minimally_processed, processed, ultra_processed"
    )
    plant_points: int = Field(ge=0, le=50, description="Additive plant diversity points")
    whole_food_points: int = Field(ge=0, le=30, description="Points based on whole ingredient density")
    protein_points: int = Field(ge=0, le=20, description="Points for presence of lean/whole protein")
    upf_penalty: int = Field(ge=0, le=20, description="Deduction if ultra-processed foods dominate")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in food detection")
    reassurance_note: str = Field(description="A warm, single-sentence note framed for parents")


class MealScoreBreakdown(BaseModel):
    plant_points: int
    whole_food_points: int
    protein_points: int
    upf_penalty: int
    raw_total: int


class MealCreateResponse(BaseModel):
    meal_id: UUID
    image_url: str
    meal_name: str
    detected_ingredients: List[str] = Field(default_factory=list, description="Foods and ingredients detected on the plate")
    plant_colors: List[str] = Field(default_factory=list, description="Detected plant botanical colors")
    upf_tier: Optional[str] = Field(None, description="Processing classification level")
    confidence: Optional[float] = Field(None, description="Vision detection confidence")
    requires_manual_tags: bool = Field(False, description="Flag indicating if low confidence requires user verification")
    scores: Dict[str, int]
    normalized_score: int
    reassurance_note: str
    created_at: datetime


class MealUpdateRequest(BaseModel):
    meal_name: Optional[str] = Field(None, max_length=150, description="Corrected or updated meal name")
    detected_ingredients: Optional[List[str]] = Field(None, description="Corrected list of detected foods/ingredients")
    plant_colors: Optional[List[str]] = Field(None, description="Corrected botanical plant colors")
    upf_tier: Optional[str] = Field(
        None,
        pattern="^(unprocessed|minimally_processed|processed|ultra_processed)$",
        description="Corrected UPF tier",
    )
    plant_score: Optional[int] = Field(None, ge=0, le=50, description="Optional manual override of plant points")
    whole_food_score: Optional[int] = Field(None, ge=0, le=30, description="Optional manual override of whole food points")
    protein_score: Optional[int] = Field(None, ge=0, le=20, description="Optional manual override of protein points")
    penalty_score: Optional[int] = Field(None, ge=0, le=20, description="Optional manual override of penalty score")


class FeedItemResponse(BaseModel):
    meal_id: UUID
    user_name: str
    user_role: str
    image_url: str
    meal_name: str
    normalized_score: int
    plant_colors: List[str]
    reassurance_note: str
    reactions: List[str]
    created_at: datetime


class MealAuditResponse(BaseModel):
    id: UUID
    user_id: UUID
    family_id: Optional[UUID] = None
    image_url: str
    preparation_context: str
    meal_name: Optional[str] = None
    detected_ingredients: List[str]
    plant_colors: List[str]
    upf_tier: Optional[str] = None
    plant_score: int
    whole_food_score: int
    protein_score: int
    penalty_score: int
    raw_score: int
    normalized_score: int
    reassurance_note: Optional[str] = None
    ai_confidence: Optional[float] = None
    requires_manual_tags: bool
    reactions: List[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReactionRequest(BaseModel):
    emoji: str = Field(..., min_length=1, max_length=10, description="Reaction emoji")


class ReactionResponse(BaseModel):
    action: str = Field(description="'added' or 'removed'")
    emoji: str
    reactions: List[str]
