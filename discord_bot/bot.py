"""
UpWork Discord Bot。

機能:
  1. 翻訳コマンド  : @Bot 翻訳 [受注元メッセージ]
                     クライアントのメッセージをネイティブ英語の返信文に変換する。
                     要件の日本語サマリー + コピペ可能な英語返信文を返す。

  2. 成果物通知    : ジョブ完了時に DISCORD_DELIVERY_CHANNEL_ID へ自動投稿。
                     サマリー embed + 全生成ファイルを添付ファイルで送信する。
                     (discord_bot/notifier.py から呼ばれる)
"""

from __future__ import annotations

import logging

import discord
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# 翻訳プロンプト
# ─────────────────────────────────────────────────────────────────────────────

_TRANSLATE_SYSTEM = """\
あなたは UpWork 専門のネイティブ英文ライターです。
クライアントから届いたメッセージを読み取り、以下の形式で出力してください。

【クライアントの要求 (日本語サマリー)】
(受注者が把握すべき要点を 3 行以内で箇条書き)

【ネイティブ英語の返信文】
(コピペしてそのまま送れる完成版。丁寧かつ簡潔。UpWork のプロフェッショナルトーン。)

注意:
- 返信文はクライアントへの返答として書く (一人称は "I" または "we")
- 技術用語は正確に
- 要件の確認・受諾・次のステップの提案を含める"""


# ─────────────────────────────────────────────────────────────────────────────
# Discord クライアント
# ─────────────────────────────────────────────────────────────────────────────

class UpWorkBot(discord.Client):
    """
    UpWork 業務支援 Discord ボット。

    Parameters
    ----------
    llm : 翻訳に使用する ChatAnthropic インスタンス。
          コストを抑えるため Haiku 推奨。
    delivery_channel_id : 成果物を投稿するチャンネル ID。None なら投稿しない。
    """

    def __init__(
        self,
        llm: ChatAnthropic,
        delivery_channel_id: int | None = None,
    ) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.llm = llm
        self.delivery_channel_id = delivery_channel_id

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    async def on_ready(self) -> None:
        logger.info("Discord bot ready: %s (id=%s)", self.user, self.user.id if self.user else "?")

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if not self.user or self.user not in message.mentions:
            return

        # メンション部分を除いたテキストを取得
        text = message.content
        for u in message.mentions:
            text = text.replace(f"<@{u.id}>", "").replace(f"<@!{u.id}>", "")
        text = text.strip()

        if not text:
            await message.reply(
                "使い方: `@Bot 翻訳` に続けてクライアントのメッセージを貼り付けてください。\n"
                "例: `@Bot 翻訳\nHello, I need a FastAPI app...`"
            )
            return

        if text.startswith("翻訳") or text.lower().startswith("translate"):
            # "翻訳" or "translate " 以降が対象テキスト
            sep = "翻訳" if text.startswith("翻訳") else "translate"
            body = text[len(sep):].strip()
            if not body:
                await message.reply("翻訳するメッセージを `翻訳` の後ろに続けてください。")
                return
            await self._handle_translation(message, body)
        else:
            # "翻訳" キーワードなしでもメンションされたら翻訳を試みる
            await self._handle_translation(message, text)

    # ------------------------------------------------------------------
    # Translation
    # ------------------------------------------------------------------

    async def _handle_translation(self, message: discord.Message, client_text: str) -> None:
        """Claude でネイティブ英語の返信文を生成してチャンネルに投稿する。"""
        async with message.channel.typing():
            msgs = [
                SystemMessage(content=_TRANSLATE_SYSTEM),
                HumanMessage(content=f"クライアントのメッセージ:\n\n{client_text}"),
            ]
            try:
                response = await self.llm.ainvoke(msgs)
                reply_text = (
                    response.content
                    if isinstance(response.content, str)
                    else str(response.content)
                )
            except Exception:
                logger.exception("Translation failed")
                await message.reply("翻訳中にエラーが発生しました。しばらくしてからお試しください。")
                return

        # Discord の 2000 文字制限を超える場合は分割送信
        chunks = _split_message(reply_text, limit=1990)
        for i, chunk in enumerate(chunks):
            if i == 0:
                await message.reply(chunk)
            else:
                await message.channel.send(chunk)

    # ------------------------------------------------------------------
    # Job delivery
    # ------------------------------------------------------------------

    async def post_job_result(self, job) -> None:
        """
        ジョブ完了後に delivery_channel_id へサマリーと生成ファイルを投稿する。
        api/worker.py の _run_job_sync から asyncio.run_coroutine_threadsafe で呼ばれる。
        """
        if not self.delivery_channel_id:
            return

        raw_channel = self.get_channel(self.delivery_channel_id)
        if not isinstance(raw_channel, discord.abc.Messageable):
            logger.warning("Delivery channel %s not found or not messageable", self.delivery_channel_id)
            return
        channel: discord.abc.Messageable = raw_channel

        # ── サマリー embed ──────────────────────────────────────────────
        color = discord.Color.green() if job.status.value == "completed" else discord.Color.red()
        embed = discord.Embed(
            title=f"{'✅ 納品完了' if job.status.value == 'completed' else '❌ ジョブ失敗'}",
            color=color,
        )
        embed.add_field(name="Job ID",    value=f"`{job.job_id}`",              inline=False)
        embed.add_field(name="Thread ID", value=f"`{job.thread_id}`",           inline=True)
        if job.estimated_cost is not None:
            embed.add_field(name="APIコスト",  value=f"${job.estimated_cost:.4f}",  inline=True)
        if job.estimated_profit is not None:
            embed.add_field(name="推定利益",   value=f"${job.estimated_profit:.4f}", inline=True)

        if job.result:
            # embed description は 4096 文字まで
            embed.description = job.result[:4000] + ("..." if len(job.result) > 4000 else "")

        if job.error:
            embed.add_field(name="エラー詳細", value=f"```\n{job.error[:1000]}\n```", inline=False)

        await channel.send(embed=embed)

        # ── コードファイルを添付 ────────────────────────────────────────
        if not job.files:
            return

        files_list = list(job.files.items())
        logger.info("Uploading %d files to Discord channel %s", len(files_list), self.delivery_channel_id)

        # Discord は 1 メッセージ最大 10 ファイル
        for batch_start in range(0, len(files_list), 10):
            batch = files_list[batch_start: batch_start + 10]
            attachments = []
            for path, code in batch:
                # ファイル名のスラッシュをアンダースコアに変換 (添付名として安全に)
                safe_name = path.replace("/", "_").replace("\\", "_").lstrip("_")
                content_bytes = code.encode("utf-8")
                # Discord のファイルサイズ上限 (8 MB) を超える場合は末尾を切り詰める
                if len(content_bytes) > 8 * 1024 * 1024:
                    content_bytes = content_bytes[: 8 * 1024 * 1024 - 100] + b"\n# ... (truncated)"
                attachments.append(discord.File(fp=__import__("io").BytesIO(content_bytes), filename=safe_name))

            label = f"生成ファイル {batch_start + 1}〜{batch_start + len(batch)} / {len(files_list)}"
            await channel.send(content=label, files=attachments)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _split_message(text: str, limit: int = 1990) -> list[str]:
    """Discord の文字数制限に合わせてテキストを分割する。"""
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    while text:
        chunks.append(text[:limit])
        text = text[limit:]
    return chunks
