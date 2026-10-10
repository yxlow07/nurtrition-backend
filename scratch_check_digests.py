import asyncio
import uuid
from hackucdbackend.core.database import AsyncSessionLocal
from hackucdbackend.models.digest import WeeklyDigest
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as session:
        fid = uuid.UUID('411c9220-6e89-49bf-8cee-26303843a002')
        res = await session.execute(select(WeeklyDigest).where(WeeklyDigest.family_id == fid))
        try:
            val = res.scalar_one_or_none()
            print("scalar_one_or_none succeeded:", val)
        except Exception as e:
            print("scalar_one_or_none FAILED with:", type(e).__name__, e)

if __name__ == "__main__":
    asyncio.run(main())

