import os
import uuid
import logging
from pathlib import Path
from typing import Optional
import httpx

from hackucdbackend.core.config import settings

logger = logging.getLogger(__name__)

LOCAL_UPLOAD_DIR = Path("uploads")


def get_file_extension(content_type: Optional[str] = None) -> str:
    if content_type:
        if "png" in content_type:
            return "png"
        if "webp" in content_type:
            return "webp"
        if "gif" in content_type:
            return "gif"
    return "jpg"


def get_storage_url(user_id: uuid.UUID, meal_id: uuid.UUID, ext: str = "jpg") -> str:
    """Generate public Supabase Storage object URL."""
    bucket = settings.SUPABASE_STORAGE_BUCKET
    base = settings.SUPABASE_PROJECT_URL.rstrip("/")
    if base:
        return f"{base}/storage/v1/object/public/{bucket}/{user_id}/{meal_id}.{ext}"
    return f"{settings.APP_URL}/static/uploads/{user_id}/{meal_id}.{ext}"


async def upload_image_to_supabase(
    user_id: uuid.UUID,
    meal_id: uuid.UUID,
    image_bytes: bytes,
    content_type: str = "image/jpeg",
) -> str:
    """Upload meal photo to Supabase Object Storage with local disk fallback."""
    ext = get_file_extension(content_type)
    file_path = f"{user_id}/{meal_id}.{ext}"
    bucket = settings.SUPABASE_STORAGE_BUCKET

    public_url = get_storage_url(user_id, meal_id, ext)

    # Attempt upload to Supabase Storage if configured
    if settings.SUPABASE_PROJECT_URL and settings.SUPABASE_PUBLISHABLE_KEY:
        upload_endpoint = f"{settings.SUPABASE_PROJECT_URL.rstrip('/')}/storage/v1/object/{bucket}/{file_path}"
        headers = {
            "Authorization": f"Bearer {settings.SUPABASE_PUBLISHABLE_KEY}",
            "apikey": settings.SUPABASE_PUBLISHABLE_KEY,
            "Content-Type": content_type,
            "x-upsert": "true",
        }
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(upload_endpoint, content=image_bytes, headers=headers)
                if res.status_code in (200, 201):
                    logger.info(f"Successfully uploaded image to Supabase Storage: {file_path}")
                    return public_url
                logger.warning(
                    f"Supabase Storage returned {res.status_code}: {res.text}. Falling back to local store."
                )
        except Exception as e:
            logger.warning(f"Failed to upload to Supabase Storage: {e}. Falling back to local store.")

    # Local storage fallback
    try:
        user_dir = LOCAL_UPLOAD_DIR / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        local_file = user_dir / f"{meal_id}.{ext}"
        local_file.write_bytes(image_bytes)
        logger.info(f"Persisted image to local fallback path: {local_file}")
    except Exception as e:
        logger.error(f"Failed to persist image locally: {e}")

    return public_url
