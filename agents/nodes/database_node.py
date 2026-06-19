"""
DatabaseNode — データベース設計・実装専門エージェント。

成果物は dict[str, str] (ファイルパス → コード) で返す。
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from agents.Agent_Node import AgentNode


class DatabaseNode(AgentNode):
    """
    データベース専門エージェント。
    成果物は state["database_files"] (dict[str, str]) に格納する。
    """

    node_name = "database"

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @tool
    def design_erd(self, entities: list[str], spec: str) -> dict[str, Any]:
        """
        ER 図を設計する。
        Returns:
            entities   : list[{"name": str, "attributes": list, "pk": str}]
            relations  : list[{"from": str, "to": str, "cardinality": str}]
            indexes    : list[str]
        """
        ...

    @tool
    def generate_sqlalchemy_models(self, erd: dict, db_type: str = "postgresql") -> dict[str, str]:
        """
        ERD から SQLAlchemy ORM モデルを生成する。
        Returns: {"src/db/models.py": "...", "src/db/base.py": "..."}
        """
        ...

    @tool
    def generate_alembic_migration(self, models_file: str, revision_message: str) -> dict[str, str]:
        """
        Alembic マイグレーションスクリプトを生成する。
        Returns:
            {"alembic/env.py": "...", "alembic/versions/xxxx_init.py": "..."}
        """
        ...

    @tool
    def generate_repository(self, models: dict[str, str]) -> dict[str, str]:
        """
        各モデルに対応する Repository クラス (CRUD) を生成する。
        Returns: {"src/db/repositories/user_repo.py": "...", ...}
        """
        ...

    @tool
    def optimize_queries(self, query_patterns: list[str], erd: dict) -> dict[str, str]:
        """
        想定クエリパターンに対するインデックス追加マイグレーションを生成する。
        Returns: {"alembic/versions/xxxx_add_indexes.py": "..."}
        """
        ...

    @tool
    def generate_seed_data(self, models_file: str, count: int = 10) -> dict[str, str]:
        """
        シードデータ投入スクリプトを生成する。
        Returns: {"scripts/seed.py": "..."}
        """
        ...

    @tool
    def generate_db_config(self, db_type: str, use_async: bool = True) -> dict[str, str]:
        """
        DB 接続設定を生成する。
        Returns: {"src/db/session.py": "...", "src/db/config.py": "..."}
        """
        ...

    @tool
    def apply_fix(self, current_files: dict[str, str], fix_instruction: str) -> dict[str, str]:
        """修正指示を受けて既存ファイルを修正する。"""
        ...

    # ------------------------------------------------------------------
    # Node entry point
    # ------------------------------------------------------------------

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        response = self._invoke(state)

        fix_inst = state.get("fix_instructions", {}).get(self.node_name)
        existing = state.get("database_files", {})

        if fix_inst and existing:
            # TODO: apply_fix tool_call を実行
            database_files = existing  # stub
        else:
            # TODO: design_erd → generate_sqlalchemy_models → generate_alembic_migration
            #        → generate_repository → generate_db_config → generate_seed_data
            database_files: dict[str, str] = {}

        return {
            **state,
            "messages":       state["messages"] + [response],
            "database_files": database_files,
        }
