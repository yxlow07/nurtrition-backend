from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hackucdbackend.core.database import get_db
from hackucdbackend.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from hackucdbackend.models.user import User
from hackucdbackend.schemas.user import (
    UserRegisterRequest,
    UserRegisterResponse,
    UserLoginRequest,
    UserLoginResponse,
    UserResponse,
    UserMeResponse,
    DemographicProfile,
)

router = APIRouter(prefix="", tags=["Auth & Users"])


@router.post(
    "/api/v1/auth/register",
    response_model=UserRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user with password and demographic profile",
)
async def register_user(
    payload: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> UserRegisterResponse:
    # Check if user already exists
    stmt = select(User).where(User.email == payload.email)
    existing = await db.execute(stmt)
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with email '{payload.email}' already exists.",
        )

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        age=payload.age,
        sex=payload.sex,
        activity_level=payload.activity_level,
        dietary_flags=payload.dietary_flags,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id)

    return UserRegisterResponse(
        user=UserResponse.model_validate(user),
        access_token=token,
        token_type="bearer",
    )


@router.post(
    "/api/v1/auth/login",
    response_model=UserLoginResponse,
    summary="Authenticate user with email and password",
)
async def login_user(
    payload: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> UserLoginResponse:
    stmt = select(User).where(User.email == payload.email)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(user.id)

    return UserLoginResponse(
        user=UserResponse.model_validate(user),
        access_token=token,
        token_type="bearer",
    )


@router.get(
    "/api/v1/users/me",
    response_model=UserMeResponse,
    summary="Retrieve current user profile and active family circle",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserMeResponse:
    return UserMeResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        profile=DemographicProfile(
            age=current_user.age,
            sex=current_user.sex,
            activity_level=current_user.activity_level,
            role=current_user.role,
        ),
        dietary_flags=current_user.dietary_flags or [],
        family_id=current_user.family_id,
        created_at=current_user.created_at,
    )
