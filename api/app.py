"""
FastAPI アプリケーションファクトリ。

lifespan でグラフを一度だけビルドし worker に注入する。
シャットダウン時はスレッドプールが完走するまで待つ (SIGTERM → graceful drain)。
"""

from __future__ import annotations

import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import worker as worker_module
from api.routers import health, jobs

# ─────────────────────────────────────────────────────────────────────────────
# ロギング設定 (systemd journal はタイムスタンプ・PID を付与するため簡潔に)
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # ── 起動 ─────────────────────────────────────────────────────────────
    logger.info("Building multi-agent graph (LangGraph compile)...")
    try:
        from main import build_app as build_graph
        compiled = build_graph(use_human_in_loop=True)
        worker_module.set_compiled_app(compiled)
        logger.info("Graph ready. API is accepting requests.")
    except Exception:
        logger.exception("Failed to build graph — check AWS credentials and .env")
        raise

    yield

    # ── 終了 (SIGTERM → graceful drain) ─────────────────────────────────
    logger.info("Shutdown signal received. Draining worker threads...")
    # cancel_futures=False: 実行中ジョブを途中で打ち切らない
    worker_module._executor.shutdown(wait=True, cancel_futures=False)
    logger.info("All worker threads finished. Goodbye.")


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="UpWork Multi-Agent API",
        description=(
            "LangGraph ベースのマルチエージェントシステム。\n\n"
            "仕様テキストと報奨金を投入すると、ProjectManager → Worker群 → "
            "TestRunner → CodeReview → Writer の順に自動処理し、納品物を生成する。"
        ),
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS (フロントエンドから叩く場合は origins を絞ること)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(jobs.router)

    return app


# uvicorn server:app から参照される
app = create_app()
