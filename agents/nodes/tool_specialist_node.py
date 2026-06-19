"""
ToolSpecialistNode — UpWork 納品物に含まれる共有ユーティリティの設計・実装。

【役割の明確化】
  このエージェントは「エージェントシステム自体のツール」ではなく、
  「UpWork クライアントへ納品するプロジェクトの共有ユーティリティ」を生成する。
  例: API クライアントラッパー / バリデーション / 例外・エラーハンドリング基盤 /
      構造化ログ設定 / 日付・文字列ヘルパー。

成果物は dict[str, str] で state["tool_spec_files"] に格納する。
生成ロジックは WorkerNode 基底クラスに集約されている。
"""

from __future__ import annotations

from agents.nodes.worker_base import WorkerNode


class ToolSpecialistNode(WorkerNode):
    """
    共有ユーティリティ実装専門エージェント。
    成果物は state["tool_spec_files"] に格納する。
    """

    node_name = "tool_specialist"
    output_field = "tool_spec_files"
