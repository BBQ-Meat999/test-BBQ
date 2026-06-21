"""
Discord 通知ブリッジ。

api/worker.py の worker スレッドからスレッドセーフに Discord へ通知を送る。
asyncio.run_coroutine_threadsafe を使ってスレッド→イベントループへ橋渡しする。

使い方:
    # サーバー起動時 (api/app.py lifespan) に呼ぶ
    notifier.configure(loop=loop, bot=bot)

    # ジョブ完了後 (worker スレッドから呼ぶ)
    notifier.notify_job_completed(job)
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api.job_store import Job
    from discord_bot.bot import UpWorkBot

logger = logging.getLogger(__name__)

_loop: asyncio.AbstractEventLoop | None = None
_bot: UpWorkBot | None = None


def configure(loop: asyncio.AbstractEventLoop, bot: UpWorkBot) -> None:
    """lifespan で一度だけ呼ぶ。"""
    global _loop, _bot
    _loop = loop
    _bot = bot


def notify_job_completed(job: Job) -> None:
    """
    ジョブ完了後に worker スレッドから呼ぶ。スレッドセーフ。
    Discord が未設定の場合は何もしない。
    """
    if _loop is None or _bot is None:
        return
    if not _loop.is_running():
        return
    asyncio.run_coroutine_threadsafe(_bot.post_job_result(job), _loop)
