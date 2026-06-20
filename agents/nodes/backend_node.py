"""
BackendNode — Python 専門のバックエンド実装エージェント。

成果物は dict[str, str] (ファイルパス → コード) で state["backend_files"] に格納する。
生成ロジックは WorkerNode 基底クラスに集約されており、本クラスは担当範囲を定義するだけ。
"""

from __future__ import annotations

from agents.nodes.worker_base import WorkerNode


class BackendNode(WorkerNode):
    """
    Python バックエンド専門エージェント。

    state["agent_instructions"]["backend"] または
    state["fix_instructions"]["backend"] の指示に従い、FastAPI 等で実装する。
    成果物は state["backend_files"] に格納する。
    """

    node_name = "backend"
    output_field = "backend_files"
