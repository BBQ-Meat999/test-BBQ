"""
バックグラウンド ジョブランナー。

LangGraph の invoke() はブロッキング呼び出しのため ThreadPoolExecutor で実行する。
HITL (Human-in-the-loop) フロー:
  1. invoke() が interrupt() に到達すると返ってくる
  2. get_state().next が空でなければ interrupted と判断
  3. Job.wait_for_approval() でブロック → HTTP ハンドラが submit_feedback() で解除
  4. Command(resume=feedback) で invoke() を再開する
"""

from __future__ import annotations

import asyncio
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from langgraph.types import Command

from api.job_store import Job, JobStatus
from discord_bot import notifier as discord_notifier

logger = logging.getLogger(__name__)

# LangGraph MemorySaver はプロセス内シングルトン。
# workers=1 (uvicorn) + max_workers=4 で並列ジョブ数を制限する。
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="agent-worker")

# サーバー起動時に api/app.py の lifespan で注入される
_compiled_app: Any = None


def set_compiled_app(app: Any) -> None:
    global _compiled_app
    _compiled_app = app


def _is_interrupted(config: dict[str, Any]) -> bool:
    """グラフが interrupt() でポーズ中かどうかを判定する。"""
    try:
        snapshot = _compiled_app.get_state(config)
        return bool(getattr(snapshot, "next", None))
    except Exception:
        return False


def _extract_interrupt_value(config: dict[str, Any]) -> Any:
    """interrupt(value) に渡された値をチェックポイントから取り出す。"""
    try:
        snapshot = _compiled_app.get_state(config)
        for task in getattr(snapshot, "tasks", []):
            for intr in getattr(task, "interrupts", []):
                return getattr(intr, "value", intr)
    except Exception:
        pass
    return None


def _run_job_sync(job: Job, initial_state: dict[str, Any]) -> None:
    """
    ジョブのフルライフサイクルを同期的に実行する (ThreadPoolExecutor 内)。

    Phase 1: invoke() を実行し、interrupt() に到達したら待機
    Phase 2: ユーザー承認後に Command(resume=...) で再開
    """
    config = {"configurable": {"thread_id": job.thread_id}}

    try:
        job.status = JobStatus.running
        logger.info("job_id=%s started thread_id=%s", job.job_id, job.thread_id)

        # ── Phase 1: interrupt() まで (または完走まで) 実行 ────────────
        state = _compiled_app.invoke(initial_state, config=config)

        if _is_interrupted(config):
            interrupt_value = _extract_interrupt_value(config)
            job.interrupt_data   = interrupt_value
            job.estimated_cost   = state.get("estimated_cost")
            job.estimated_profit = state.get("estimated_profit")
            job.status = JobStatus.waiting_approval
            logger.info("job_id=%s waiting for approval", job.job_id)

            # HTTP ハンドラからのフィードバックを待つ (最大1時間)
            feedback = job.wait_for_approval(timeout=3600.0)
            if feedback is None:
                job.status = JobStatus.failed
                job.error  = "Plan approval timeout (3600 s)"
                logger.warning("job_id=%s approval timeout", job.job_id)
                return

            # ── Phase 2: 承認後に再開 ────────────────────────────────
            job.status = JobStatus.running
            logger.info("job_id=%s resuming with feedback=%r", job.job_id, feedback[:80])
            state = _compiled_app.invoke(Command(resume=feedback), config=config)

        # ── 完了処理 ─────────────────────────────────────────────────────
        job.result = state.get("final_answer", "")
        job.files  = {
            **state.get("tool_spec_files", {}),
            **state.get("backend_files",   {}),
            **state.get("frontend_files",  {}),
            **state.get("database_files",  {}),
        }
        job.estimated_cost   = state.get("estimated_cost")
        job.estimated_profit = state.get("estimated_profit")
        job.status = JobStatus.completed
        logger.info(
            "job_id=%s completed files=%d cost=$%.4f profit=$%.4f",
            job.job_id,
            len(job.files),
            job.estimated_cost or 0,
            job.estimated_profit or 0,
        )
        discord_notifier.notify_job_completed(job)

    except Exception:
        job.status = JobStatus.failed
        job.error  = traceback.format_exc()
        logger.exception("job_id=%s failed", job.job_id)
        discord_notifier.notify_job_completed(job)


async def submit_job(job: Job, initial_state: dict[str, Any]) -> None:
    """ジョブをスレッドプールに投入する (fire-and-forget)。"""
    loop = asyncio.get_running_loop()
    loop.run_in_executor(_executor, _run_job_sync, job, initial_state)
