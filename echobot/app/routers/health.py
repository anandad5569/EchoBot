from __future__ import annotations

from fastapi import APIRouter, Depends

from ..state import get_app_runtime


router = APIRouter(tags=["health"])


@router.get("/health")
async def get_health(runtime=Depends(get_app_runtime)) -> dict[str, object]:
    return await runtime.health_snapshot()
