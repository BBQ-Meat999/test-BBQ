"""
ジョブ管理エンドポイント。

POST   /api/v1/jobs                     案件を投入してバックグラウンド処理を開始
GET    /api/v1/jobs                     全ジョブ一覧
GET    /api/v1/jobs/{job_id}            ジョブ詳細・ステータスポーリング
POST   /api/v1/jobs/{job_id}/approve    Human-in-the-loop: 作業計画を承認/修正
GET    /api/v1/jobs/{job_id}/files      完了済みジョブの生成ファイル取得
DELETE /api/v1/jobs/{job_id}            ジョブをレジストリから削除

GET    /api/v1/models/estimate          報奨金に対するモデル選択・コスト試算 (ジョブ実行なし)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage

from api.job_store import Job, job_store
from api.schemas import (
    ApproveJobRequest,
    JobDetail,
    JobStatus,
    JobSummary,
    ModelEstimateResponse,
    SubmitJobRequest,
)
from api.worker import submit_job
from config.model_selector import ModelSelector
from config.settings import settings

router = APIRouter(prefix="/api/v1", tags=["jobs"])


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_initial_state(spec: str, reward_amount: float) -> dict[str, Any]:
    """graph/workflow.py の AgentState の初期値を生成する。"""
    return {
        "messages":             [HumanMessage(content=spec)],
        "user_spec":            spec,
        "reward_amount":        reward_amount,
        "work_plan":            "",
        "assigned_agents":      [],
        "agent_instructions":   {},
        "human_feedback":       "",
        "model_assignments":    {},
        "estimated_cost":       0.0,
        "estimated_profit":     0.0,
        "tool_spec_files":      {},
        "backend_files":        {},
        "frontend_files":       {},
        "database_files":       {},
        "test_results":         {},
        "code_review_feedback": "",
        "fix_targets":          [],
        "review_loop_count":    0,
        "fix_instructions":     {},
        "remaining_issues":     "",
        "next":                 "",
        "final_files":          {},
        "final_answer":         "",
    }


def _to_detail(job: Job) -> JobDetail:
    return JobDetail(
        job_id=job.job_id,
        status=job.status,
        thread_id=job.thread_id,
        interrupt_data=job.interrupt_data,
        result=job.result,
        files=job.files,
        error=job.error,
        estimated_cost=job.estimated_cost,
        estimated_profit=job.estimated_profit,
    )


def _require_job(job_id: str) -> Job:
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return job


# ─────────────────────────────────────────────────────────────────────────────
# Job CRUD
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/jobs",
    response_model=JobDetail,
    status_code=202,
    summary="案件を投入してマルチエージェント処理を開始",
)
async def create_job(body: SubmitJobRequest) -> JobDetail:
    """
    仕様テキストと報奨金を受け取り、バックグラウンドでエージェントを起動する。
    レスポンスの `job_id` を使って `/jobs/{job_id}` でステータスをポーリングする。

    `REQUIRE_PLAN_APPROVAL=true` の場合、最初の `running` → `waiting_approval` へ遷移し、
    `/jobs/{job_id}/approve` で承認を送るまで処理が止まる。
    """
    job = job_store.create(thread_id=body.thread_id)
    initial_state = _build_initial_state(body.spec, body.reward_amount)
    await submit_job(job, initial_state)
    return _to_detail(job)


@router.get("/jobs", response_model=list[JobSummary], summary="全ジョブ一覧")
async def list_jobs() -> list[JobSummary]:
    return [
        JobSummary(job_id=j.job_id, status=j.status, thread_id=j.thread_id)
        for j in job_store.list_all()
    ]


@router.get("/jobs/{job_id}", response_model=JobDetail, summary="ジョブ詳細・ステータス確認")
async def get_job(job_id: str) -> JobDetail:
    """
    ステータスのポーリングに使用する。

    - `waiting_approval`: `interrupt_data` に作業計画が含まれる。`/approve` で承認を送る。
    - `completed`: `result` に最終納品サマリー、`files` に生成ファイルが含まれる。
    - `failed`: `error` にスタックトレースが含まれる。
    """
    return _to_detail(_require_job(job_id))


@router.post(
    "/jobs/{job_id}/approve",
    response_model=JobDetail,
    summary="Human-in-the-loop: 作業計画を承認または修正",
)
async def approve_job(
    job_id: str,
    body: ApproveJobRequest | None = None,
) -> JobDetail:
    """
    ジョブが `waiting_approval` 状態のときに呼ぶ。

    - `feedback="approve"` → そのまま実装フェーズへ進む
    - それ以外の文字列 → ProjectManager が計画を修正してから実装フェーズへ進む
    - リクエストボディ省略時は `feedback="approve"` と同じ扱い
    """
    approved = body or ApproveJobRequest()
    job = _require_job(job_id)
    if job.status != JobStatus.waiting_approval:
        raise HTTPException(
            status_code=409,
            detail=f"Job is not waiting for approval (current status: {job.status})",
        )
    job.submit_feedback(approved.feedback)
    return _to_detail(job)


@router.get(
    "/jobs/{job_id}/files",
    response_model=dict[str, str],
    summary="完了済みジョブの生成ファイル取得",
)
async def get_job_files(job_id: str) -> dict[str, str]:
    """
    `completed` 状態のジョブの全生成ファイルを `{ファイルパス: コード}` で返す。
    backend / frontend / database / tool_specialist の成果物をマージした状態。
    """
    job = _require_job(job_id)
    if job.status != JobStatus.completed:
        raise HTTPException(
            status_code=409,
            detail=f"Job is not completed yet (current status: {job.status})",
        )
    return job.files or {}


@router.delete("/jobs/{job_id}", status_code=204, summary="ジョブをレジストリから削除")
async def delete_job(job_id: str) -> None:
    """
    ジョブのレコードをメモリから削除する。
    進行中のジョブを強制停止はしない — worker スレッドは完走するが結果は捨てられる。
    """
    if not job_store.delete(job_id):
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")


# ─────────────────────────────────────────────────────────────────────────────
# Model / cost estimation
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/models/estimate",
    response_model=ModelEstimateResponse,
    summary="報奨金に対するモデル選択・コスト試算",
)
async def estimate_model(reward_amount: float = 0.0) -> ModelEstimateResponse:
    """
    ジョブを実行せずにモデル選択結果とコスト試算だけを返す。
    `reward_amount` を変えて最適戦略を事前確認するのに使う。
    """
    selection = ModelSelector.select_assignments(
        reward_amount=reward_amount,
        max_review_loops=settings.workflow.max_review_loops,
    )
    return ModelEstimateResponse(
        reward_amount=reward_amount,
        strategy_name=selection["strategy_name"],
        strategy_desc=selection["strategy_desc"],
        estimated_cost=selection["estimated_cost"],
        estimated_profit=selection["estimated_profit"],
        model_assignments=selection["model_assignments"],
    )
