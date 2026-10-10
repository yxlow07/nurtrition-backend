import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from hackucdbackend.core.database import get_db, AsyncSessionLocal
from hackucdbackend.core.security import get_current_user
from hackucdbackend.models.meal import Meal, MealReaction
from hackucdbackend.models.user import User
from hackucdbackend.schemas.meal import (
    MealAuditResponse,
    MealCreateResponse,
    MealUpdateRequest,
    ReactionRequest,
    ReactionResponse,
)
from hackucdbackend.services.ai_engine import run_vision_analysis
from hackucdbackend.services.scoring import (
    calculate_normalized_score,
    calculate_raw_score,
    calculate_score_from_values,
    get_score_breakdown,
)
from hackucdbackend.services.storage import (
    get_file_extension,
    get_storage_url,
    upload_image_to_supabase,
)

router = APIRouter(prefix="/api/v1/meals", tags=["Meals & Ingestion"])

MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


async def persist_meal_storage_background(
    user_id: uuid.UUID,
    meal_id: uuid.UUID,
    image_bytes: bytes,
    content_type: str,
):
    """Background task to push image to Supabase Object Storage."""
    try:
        await upload_image_to_supabase(
            user_id=user_id,
            meal_id=meal_id,
            image_bytes=image_bytes,
            content_type=content_type,
        )
    except Exception as e:
        # Logging without failing caller
        pass


@router.post(
    "/upload",
    response_model=MealCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload plate photo, run vision analysis, compute score, and log meal",
)
async def upload_meal(
    background_tasks: BackgroundTasks,
    image: UploadFile = File(..., description="Meal plate image file (jpeg/png/webp, max 10MB)"),
    preparation_context: str = Form("home_cooked", description="home_cooked, takeout, dining_hall, packaged"),
    family_id: Optional[uuid.UUID] = Form(None, description="Optional family group UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MealCreateResponse:
    # 1. Validate file format and size
    content_type = image.content_type or "image/jpeg"
    if not (content_type.startswith("image/") or "octet-stream" in content_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be a valid image (JPEG, PNG, or WebP).",
        )

    image_bytes = await image.read()
    if len(image_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )
    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image file exceeds maximum allowable size of 10MB.",
        )

    # 2. Run vision analysis synchronously for low latency response
    ai_result = await run_vision_analysis(image_bytes, prep_context=preparation_context)

    # 3. Handle confidence threshold (< 0.50 flag) and compute score
    requires_manual_tags = ai_result.confidence < 0.50
    if requires_manual_tags:
        normalized_score = 50
    else:
        normalized_score = calculate_normalized_score(ai_result, current_user.profile)

    raw_score = calculate_raw_score(ai_result)
    score_breakdown = get_score_breakdown(ai_result)

    # Resolve family_id
    assigned_family_id = family_id or current_user.family_id
    meal_id = uuid.uuid4()
    ext = get_file_extension(content_type)
    image_url = get_storage_url(current_user.id, meal_id, ext)
    now = datetime.now(timezone.utc)

    # 4. Save meal record to database
    meal = Meal(
        id=meal_id,
        user_id=current_user.id,
        family_id=assigned_family_id,
        image_url=image_url,
        preparation_context=preparation_context,
        meal_name=ai_result.meal_name,
        detected_ingredients=ai_result.detected_ingredients,
        plant_colors=ai_result.plant_colors,
        upf_tier=ai_result.upf_tier,
        plant_score=ai_result.plant_points,
        whole_food_score=ai_result.whole_food_points,
        protein_score=ai_result.protein_points,
        penalty_score=ai_result.upf_penalty,
        raw_score=raw_score,
        normalized_score=normalized_score,
        reassurance_note=ai_result.reassurance_note,
        ai_confidence=ai_result.confidence,
        requires_manual_tags=requires_manual_tags,
        created_at=now,
    )
    db.add(meal)
    await db.commit()
    await db.refresh(meal)

    # 5. Delegate storage upload to background task to minimize latency
    background_tasks.add_task(
        persist_meal_storage_background,
        user_id=current_user.id,
        meal_id=meal_id,
        image_bytes=image_bytes,
        content_type=content_type,
    )

    return MealCreateResponse(
        meal_id=meal.id,
        image_url=meal.image_url,
        meal_name=meal.meal_name or "Meal",
        detected_ingredients=meal.detected_ingredients or [],
        plant_colors=meal.plant_colors or [],
        upf_tier=meal.upf_tier,
        confidence=float(meal.ai_confidence) if meal.ai_confidence is not None else None,
        requires_manual_tags=meal.requires_manual_tags,
        scores=score_breakdown,
        normalized_score=meal.normalized_score,
        reassurance_note=meal.reassurance_note or "",
        created_at=meal.created_at,
    )


@router.patch(
    "/{meal_id}",
    response_model=MealAuditResponse,
    summary="Edit detected food, ingredients, plant colors, or UPF tier",
)
@router.put(
    "/{meal_id}",
    response_model=MealAuditResponse,
    summary="Edit detected food, ingredients, plant colors, or UPF tier",
)
async def update_meal_detected_food(
    meal_id: uuid.UUID,
    payload: MealUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MealAuditResponse:
    stmt = (
        select(Meal)
        .options(selectinload(Meal.reactions))
        .where(Meal.id == meal_id)
    )
    res = await db.execute(stmt)
    meal = res.scalar_one_or_none()

    if not meal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meal with ID '{meal_id}' not found.",
        )

    if meal.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit meals that you uploaded.",
        )

    # Apply food detection corrections
    if payload.meal_name is not None:
        meal.meal_name = payload.meal_name
    if payload.detected_ingredients is not None:
        meal.detected_ingredients = payload.detected_ingredients
    if payload.plant_colors is not None:
        meal.plant_colors = payload.plant_colors
    if payload.upf_tier is not None:
        meal.upf_tier = payload.upf_tier

    # Apply points overrides if provided
    if payload.plant_score is not None:
        meal.plant_score = payload.plant_score
    if payload.whole_food_score is not None:
        meal.whole_food_score = payload.whole_food_score
    if payload.protein_score is not None:
        meal.protein_score = payload.protein_score
    if payload.penalty_score is not None:
        meal.penalty_score = payload.penalty_score

    # Recalculate raw and demographic normalized score
    raw_score, normalized_score = calculate_score_from_values(
        plant_points=meal.plant_score,
        whole_food_points=meal.whole_food_score,
        protein_points=meal.protein_score,
        upf_penalty=meal.penalty_score,
        plant_colors=meal.plant_colors or [],
        upf_tier=meal.upf_tier or "unprocessed",
        profile=current_user.profile,
    )
    meal.raw_score = raw_score
    meal.normalized_score = normalized_score
    meal.requires_manual_tags = False  # Mark resolved on user edit

    await db.commit()
    await db.refresh(meal)

    reactions = [r.emoji for r in meal.reactions]
    return MealAuditResponse(
        id=meal.id,
        user_id=meal.user_id,
        family_id=meal.family_id,
        image_url=meal.image_url,
        preparation_context=meal.preparation_context,
        meal_name=meal.meal_name,
        detected_ingredients=meal.detected_ingredients or [],
        plant_colors=meal.plant_colors or [],
        upf_tier=meal.upf_tier,
        plant_score=meal.plant_score,
        whole_food_score=meal.whole_food_score,
        protein_score=meal.protein_score,
        penalty_score=meal.penalty_score,
        raw_score=meal.raw_score,
        normalized_score=meal.normalized_score,
        reassurance_note=meal.reassurance_note,
        ai_confidence=float(meal.ai_confidence) if meal.ai_confidence is not None else None,
        requires_manual_tags=meal.requires_manual_tags,
        reactions=reactions,
        created_at=meal.created_at,
    )


@router.get(
    "/{meal_id}",
    response_model=MealAuditResponse,
    summary="Fetch full meal audit breakdown",
)
async def get_meal_audit(
    meal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MealAuditResponse:
    stmt = (
        select(Meal)
        .options(selectinload(Meal.reactions))
        .where(Meal.id == meal_id)
    )
    res = await db.execute(stmt)
    meal = res.scalar_one_or_none()

    if not meal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meal with ID '{meal_id}' not found.",
        )

    reactions = [r.emoji for r in meal.reactions]

    return MealAuditResponse(
        id=meal.id,
        user_id=meal.user_id,
        family_id=meal.family_id,
        image_url=meal.image_url,
        preparation_context=meal.preparation_context,
        meal_name=meal.meal_name,
        detected_ingredients=meal.detected_ingredients or [],
        plant_colors=meal.plant_colors or [],
        upf_tier=meal.upf_tier,
        plant_score=meal.plant_score,
        whole_food_score=meal.whole_food_score,
        protein_score=meal.protein_score,
        penalty_score=meal.penalty_score,
        raw_score=meal.raw_score,
        normalized_score=meal.normalized_score,
        reassurance_note=meal.reassurance_note,
        ai_confidence=float(meal.ai_confidence) if meal.ai_confidence is not None else None,
        requires_manual_tags=meal.requires_manual_tags,
        reactions=reactions,
        created_at=meal.created_at,
    )


@router.post(
    "/{meal_id}/react",
    response_model=ReactionResponse,
    summary="1-tap toggle reaction emoji on a meal",
)
async def react_to_meal(
    meal_id: uuid.UUID,
    payload: ReactionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReactionResponse:
    # Verify meal exists
    meal_stmt = select(Meal).where(Meal.id == meal_id)
    meal_res = await db.execute(meal_stmt)
    if not meal_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meal with ID '{meal_id}' not found.",
        )

    # Check if this user already reacted with this emoji
    rxn_stmt = select(MealReaction).where(
        MealReaction.meal_id == meal_id,
        MealReaction.user_id == current_user.id,
        MealReaction.emoji == payload.emoji,
    )
    rxn_res = await db.execute(rxn_stmt)
    existing_rxn = rxn_res.scalar_one_or_none()

    if existing_rxn:
        # Toggle off
        await db.delete(existing_rxn)
        action = "removed"
    else:
        # Toggle on
        new_rxn = MealReaction(
            id=uuid.uuid4(),
            meal_id=meal_id,
            user_id=current_user.id,
            emoji=payload.emoji,
        )
        db.add(new_rxn)
        action = "added"

    await db.commit()

    # Fetch updated distinct reactions
    all_rxn_stmt = select(MealReaction.emoji).where(MealReaction.meal_id == meal_id)
    all_res = await db.execute(all_rxn_stmt)
    all_emojis = list(all_res.scalars().all())

    return ReactionResponse(
        action=action,
        emoji=payload.emoji,
        reactions=all_emojis,
    )
