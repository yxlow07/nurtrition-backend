import random
import string
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from hackucdbackend.core.database import get_db
from hackucdbackend.core.security import get_current_user
from hackucdbackend.models.digest import WeeklyDigest
from hackucdbackend.models.family import FamilyGroup, FamilyMember
from hackucdbackend.models.meal import Meal
from hackucdbackend.models.user import User
from hackucdbackend.schemas.family import (
    FamilyCreateRequest,
    FamilyJoinRequest,
    FamilyMemberItem,
    FamilyResponse,
    WeeklyDigestResponse,
)
from hackucdbackend.schemas.meal import FeedItemResponse
from hackucdbackend.services.digest_engine import generate_family_narrative_and_swap

router = APIRouter(prefix="/api/v1/families", tags=["Family & Feed"])


def generate_invite_code(length: int = 8) -> str:
    """Generates an uppercase alphanumeric invite code."""
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


@router.post(
    "/create",
    response_model=FamilyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Instantiate a family circle and return invite code",
)
async def create_family(
    payload: FamilyCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FamilyResponse:
    # Generate unique 8-character code
    invite_code = ""
    for _ in range(10):
        code = generate_invite_code(8)
        chk = await db.execute(select(FamilyGroup).where(FamilyGroup.invite_code == code))
        if not chk.scalar_one_or_none():
            invite_code = code
            break

    if not invite_code:
        invite_code = uuid.uuid4().hex[:8].upper()

    now = datetime.now(timezone.utc)
    family = FamilyGroup(
        id=uuid.uuid4(),
        name=payload.name,
        invite_code=invite_code,
        created_at=now,
    )
    db.add(family)
    await db.flush()

    # Add creator as family member
    member = FamilyMember(
        family_id=family.id,
        user_id=current_user.id,
        joined_at=now,
    )
    db.add(member)
    await db.commit()

    return FamilyResponse(
        id=family.id,
        name=family.name,
        invite_code=family.invite_code,
        members=[
            FamilyMemberItem(
                user_id=current_user.id,
                full_name=current_user.full_name,
                role=current_user.role,
                joined_at=now,
            )
        ],
        created_at=family.created_at,
    )


@router.post(
    "/join",
    response_model=FamilyResponse,
    summary="Join an existing family circle via 8-character invite code",
)
async def join_family(
    payload: FamilyJoinRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FamilyResponse:
    code = payload.invite_code.strip().upper()
    stmt = (
        select(FamilyGroup)
        .options(selectinload(FamilyGroup.members).selectinload(FamilyMember.user))
        .where(FamilyGroup.invite_code == code)
    )
    res = await db.execute(stmt)
    family = res.scalar_one_or_none()

    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No family circle found matching invite code '{code}'.",
        )

    # Check if already a member
    already_member = any(m.user_id == current_user.id for m in family.members)
    if not already_member:
        new_membership = FamilyMember(
            family_id=family.id,
            user_id=current_user.id,
            joined_at=datetime.now(timezone.utc),
        )
        db.add(new_membership)
        await db.commit()

    # Query all members fresh with users
    members_stmt = (
        select(FamilyMember)
        .options(selectinload(FamilyMember.user))
        .where(FamilyMember.family_id == family.id)
    )
    members_res = await db.execute(members_stmt)
    current_members = members_res.scalars().all()

    member_items = [
        FamilyMemberItem(
            user_id=m.user.id,
            full_name=m.user.full_name,
            role=m.user.role,
            joined_at=m.joined_at,
        )
        for m in current_members
    ]

    return FamilyResponse(
        id=family.id,
        name=family.name,
        invite_code=family.invite_code,
        members=member_items,
        created_at=family.created_at,
    )


@router.get(
    "/{id}/feed",
    response_model=List[FeedItemResponse],
    summary="Retrieve chronological paginated meal timeline for a family",
)
async def get_family_feed(
    id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[FeedItemResponse]:
    # Check family existence
    fam_stmt = select(FamilyGroup).where(FamilyGroup.id == id)
    fam_res = await db.execute(fam_stmt)
    if not fam_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Family with ID '{id}' not found.",
        )

    stmt = (
        select(Meal)
        .options(selectinload(Meal.user), selectinload(Meal.reactions))
        .where(Meal.family_id == id)
        .order_by(Meal.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    res = await db.execute(stmt)
    meals = res.scalars().all()

    feed_items = []
    for m in meals:
        reactions = [r.emoji for r in m.reactions]
        feed_items.append(
            FeedItemResponse(
                meal_id=m.id,
                user_name=m.user.full_name if m.user else "Family Member",
                user_role=m.user.role if m.user else "member",
                image_url=m.image_url,
                meal_name=m.meal_name or "Meal",
                normalized_score=m.normalized_score,
                plant_colors=m.plant_colors or [],
                reassurance_note=m.reassurance_note or "",
                reactions=reactions,
                created_at=m.created_at,
            )
        )

    return feed_items


@router.get(
    "/{id}/weekly",
    response_model=WeeklyDigestResponse,
    summary="Current week leaderboard & aggregate goals with AI narrative",
)
async def get_family_weekly_digest(
    id: uuid.UUID,
    force_refresh: bool = Query(False, description="Force re-generation of AI narrative"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WeeklyDigestResponse:
    # 1. Verify family exists
    stmt = (
        select(FamilyGroup)
        .options(selectinload(FamilyGroup.members).selectinload(FamilyMember.user))
        .where(FamilyGroup.id == id)
    )
    res = await db.execute(stmt)
    family = res.scalar_one_or_none()
    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Family with ID '{id}' not found.",
        )

    # 2. Compute week boundaries (Monday to Sunday)
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    # 3. Check if weekly digest already generated for this week
    if not force_refresh:
        digest_stmt = select(WeeklyDigest).where(
            WeeklyDigest.family_id == id,
            WeeklyDigest.week_start == week_start,
            WeeklyDigest.week_end == week_end,
        )
        digest_res = await db.execute(digest_stmt)
        existing = digest_res.scalar_one_or_none()
        if existing:
            return WeeklyDigestResponse.model_validate(existing)

    # 4. Fetch all meals logged by this family during this week
    start_dt = datetime.combine(week_start, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(week_end, datetime.max.time(), tzinfo=timezone.utc)

    meal_stmt = (
        select(Meal)
        .options(selectinload(Meal.user))
        .where(
            Meal.family_id == id,
            Meal.created_at >= start_dt,
            Meal.created_at <= end_dt,
        )
    )
    meal_res = await db.execute(meal_stmt)
    meals = meal_res.scalars().all()

    # 5. Compute leaderboard per member
    member_map = {m.user_id: m.user for m in family.members}
    member_stats = {}
    for uid, u in member_map.items():
        member_stats[str(uid)] = {
            "user_id": str(uid),
            "full_name": u.full_name,
            "role": u.role,
            "meal_count": 0,
            "total_score": 0,
            "avg_score": 0,
            "plant_colors": set(),
            "top_meal": None,
        }

    collective_plant_colors = set()
    recent_meal_names = []

    for m in meals:
        uid_str = str(m.user_id)
        if uid_str not in member_stats:
            member_stats[uid_str] = {
                "user_id": uid_str,
                "full_name": m.user.full_name if m.user else "Member",
                "role": m.user.role if m.user else "member",
                "meal_count": 0,
                "total_score": 0,
                "avg_score": 0,
                "plant_colors": set(),
                "top_meal": None,
            }
        stats = member_stats[uid_str]
        stats["meal_count"] += 1
        stats["total_score"] += m.normalized_score
        if m.plant_colors:
            for color in m.plant_colors:
                stats["plant_colors"].add(color)
                collective_plant_colors.add(color)
        if m.meal_name:
            recent_meal_names.append(m.meal_name)
            if not stats["top_meal"] or m.normalized_score > stats.get("top_score", 0):
                stats["top_meal"] = m.meal_name
                stats["top_score"] = m.normalized_score

    leaderboard_list = []
    for s in member_stats.values():
        c = s["meal_count"]
        s["avg_score"] = round(s["total_score"] / c, 1) if c > 0 else 0
        s["plant_diversity_count"] = len(s["plant_colors"])
        s["plant_colors"] = list(s["plant_colors"])
        s.pop("top_score", None)
        leaderboard_list.append(s)

    # Sort leaderboard by avg_score and meal_count desc
    leaderboard_list.sort(key=lambda x: (x["avg_score"], x["meal_count"]), reverse=True)

    collective_plant_count = len(collective_plant_colors)

    # 6. Generate narrative & swap with AI reasoning engine
    ai_digest = await generate_family_narrative_and_swap(
        family_name=family.name,
        member_stats=leaderboard_list,
        collective_plant_count=collective_plant_count,
        recent_meals=recent_meal_names,
    )

    digest_record = WeeklyDigest(
        id=uuid.uuid4(),
        family_id=id,
        week_start=week_start,
        week_end=week_end,
        leaderboard_payload={"rankings": leaderboard_list, "total_meals": len(meals)},
        collective_plant_count=collective_plant_count,
        ai_family_narrative=ai_digest["ai_family_narrative"],
        recommended_grocery_swap=ai_digest["recommended_grocery_swap"],
        created_at=datetime.now(timezone.utc),
    )
    db.add(digest_record)
    await db.commit()
    await db.refresh(digest_record)

    return WeeklyDigestResponse.model_validate(digest_record)
