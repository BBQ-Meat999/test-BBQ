"""ヘルスチェックエンドポイント。ロードバランサ・systemd watchdog 向け。"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str = "ok"


@router.get("/health", response_model=HealthResponse, summary="ヘルスチェック")
async def health() -> HealthResponse:
    return HealthResponse()
