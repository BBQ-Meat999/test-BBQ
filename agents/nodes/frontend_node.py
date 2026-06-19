"""
FrontendNode — フロントエンド実装エージェント。

成果物は dict[str, str] (ファイルパス → コード) で state["frontend_files"] に格納する。
生成ロジックは WorkerNode 基底クラスに集約されている。
"""

from __future__ import annotations

from agents.nodes.worker_base import WorkerNode


class FrontendNode(WorkerNode):
    """
    フロントエンド専門エージェント (デフォルト React + TypeScript)。
    成果物は state["frontend_files"] に格納する。
    """

    node_name = "frontend"
    output_field = "frontend_files"
