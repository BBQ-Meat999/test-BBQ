"""
FastAPI リクエスト/レスポンスの Pydantic スキーマ。

agents/schemas.py (LangGraph 構造化出力用) とは別物。
こちらは HTTP 境界のモデル定義。
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(StrEnum):
    pending          = "pending"
    running          = "running"
    waiting_approval = "waiting_approval"
    completed        = "completed"
    failed           = "failed"


class SubmitJobRequest(BaseModel):
    spec: str = Field(..., min_length=10, description="クライアントからの仕様テキスト")
    reward_amount: float = Field(default=0.0, ge=0.0, description="UpWork 報奨金 (USD)")
    thread_id: str | None = Field(
        default=None,
        description="LangGraph チェックポイント用スレッドID。省略時は job_id を使用。"
    )


class ApproveJobRequest(BaseModel):
    feedback: str = Field(
        default="approve",
        description="'approve' で承認。それ以外の文字列は修正指示として計画を再生成する。",
    )


class JobSummary(BaseModel):
    job_id:    str
    status:    JobStatus
    thread_id: str


class JobDetail(BaseModel):
    job_id:           str
    status:           JobStatus
    thread_id:        str
    interrupt_data:   dict[str, Any] | None = None  # waiting_approval 時の計画内容
    result:           str | None            = None  # completed 時の最終納品サマリー
    files:            dict[str, str] | None = None  # completed 時の生成ファイル
    error:            str | None            = None  # failed 時のエラー詳細
    estimated_cost:   float | None          = None
    estimated_profit: float | None          = None


class ModelEstimateResponse(BaseModel):
    reward_amount:     float
    strategy_name:     str
    strategy_desc:     str
    estimated_cost:    float
    estimated_profit:  float
    model_assignments: dict[str, str]
