"""
FastAPI アプリケーションファクトリ。

lifespan でグラフを一度だけビルドし worker に注入する。
シャットダウン時はスレッドプールが完走するまで待つ (SIGTERM → graceful drain)。
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import worker as worker_module
from api.routers import health, jobs
from discord_bot import notifier as discord_notifier

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
    # ── LangGraph グラフのビルド ──────────────────────────────────────────
    logger.info("Building multi-agent graph (LangGraph compile)...")
    try:
        from main import build_app as build_graph
        compiled = build_graph(use_human_in_loop=True)
        worker_module.set_compiled_app(compiled)
        logger.info("Graph ready. API is accepting requests.")
    except Exception:
        logger.exception("Failed to build graph — check AWS credentials and .env")
        raise

    # ── Discord ボット起動 (設定があれば) ────────────────────────────────
    bot_task: asyncio.Task | None = None
    discord_bot = None
    from config.settings import settings
    if settings.discord_bot_token:
        try:
            from langchain_anthropic import ChatAnthropic

            from discord_bot.bot import UpWorkBot

            # 翻訳用は Haiku で十分 (コスト最小化)
            translate_llm = ChatAnthropic(  # type: ignore[call-arg]
                model="claude-haiku-4-5-20251001",
                temperature=0.3,
                max_tokens=2048,
                api_key=settings.anthropic_api_key,  # type: ignore[arg-type]
            )
            discord_bot = UpWorkBot(
                llm=translate_llm,
                delivery_channel_id=settings.discord_delivery_channel_id,
            )
            discord_notifier.configure(asyncio.get_event_loop(), discord_bot)
            bot_task = asyncio.create_task(discord_bot.start(settings.discord_bot_token))
            logger.info(
                "Discord bot starting (delivery_channel=%s)...",
                settings.discord_delivery_channel_id,
            )
        except Exception:
            logger.exception("Discord bot failed to start — continuing without Discord")
    else:
        logger.info("DISCORD_BOT_TOKEN not configured — Discord integration disabled.")

    yield

    # ── 終了 (SIGTERM → graceful drain) ─────────────────────────────────
    logger.info("Shutdown signal received. Draining worker threads...")
    worker_module._executor.shutdown(wait=True, cancel_futures=False)

    if discord_bot and bot_task and not bot_task.done():
        logger.info("Closing Discord bot...")
        await discord_bot.close()
        with suppress(asyncio.CancelledError):
            await bot_task

    logger.info("Shutdown complete.")


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
