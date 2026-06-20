"""
uvicorn エントリポイント — systemd 常時起動向け。

起動方法:
  # 直接実行 (開発・テスト)
  uv run python server.py

  # uvicorn CLI で起動 (推奨: リロードなし、シングルワーカー)
  uv run uvicorn server:app --host 0.0.0.0 --port 8080 --workers 1

systemd での使用:
  deploy/upwork-agent.service を参照。
  ExecStart に上記 uvicorn コマンドを記載し、EnvironmentFile で環境変数を注入する。

注意: LangGraph の MemorySaver (チェックポイント) はプロセス内メモリを使うため
      --workers 1 固定。複数プロセスにしたい場合は Redis チェックポインタに移行すること。
"""

from __future__ import annotations

import os

import uvicorn

from api.app import app  # noqa: F401  uvicorn server:app 参照用

if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8080")),
        workers=1,
        loop="asyncio",
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
        access_log=True,
        timeout_graceful_shutdown=30,
    )
