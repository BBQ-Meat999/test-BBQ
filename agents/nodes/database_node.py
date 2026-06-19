"""
DatabaseNode — データベース設計・実装専門エージェント。

成果物は dict[str, str] (ファイルパス → コード) で state["database_files"] に格納する。
生成ロジックは WorkerNode 基底クラスに集約されている。
"""

from __future__ import annotations

from agents.nodes.worker_base import WorkerNode


class DatabaseNode(WorkerNode):
    """
    データベース専門エージェント (SQLAlchemy / Alembic / ERD)。
    成果物は state["database_files"] に格納する。
    """

    node_name = "database"
    output_field = "database_files"
