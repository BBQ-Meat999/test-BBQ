"""
DatabaseNode — データベース設計・実装専門エージェント。

ERD設計・SQLAlchemyモデル・マイグレーション・クエリ最適化・
シードデータ生成を担当する。
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from agents.Agent_Node import AgentNode


class DatabaseNode(AgentNode):
    """
    データベース専門エージェント。

    責務:
      - ER図・スキーマ設計
      - SQLAlchemy ORM モデル生成
      - Alembic マイグレーションスクリプト生成
      - インデックス設計・クエリ最適化
      - シードデータ・テストフィクスチャ生成
      - 接続設定・コネクションプール設定
    """

    node_name = "database"

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @tool
    def design_erd(self, entities: list[str], spec: str) -> str:
        """
        仕様からエンティティ関係図 (ERD) を設計する。
        エンティティ・属性・カーディナリティ・主キー・外部キーを含む。
        """
        ...

    @tool
    def generate_sqlalchemy_models(self, erd: str, db_type: str = "postgresql") -> str:
        """
        ERD から SQLAlchemy ORM モデルを生成する。
        型アノテーション・リレーション・制約・インデックスを含む。
        """
        ...

    @tool
    def generate_alembic_migration(self, models: str, revision_message: str) -> str:
        """
        SQLAlchemy モデルから Alembic マイグレーションスクリプトを生成する。
        upgrade / downgrade 両方を実装する。
        """
        ...

    @tool
    def optimize_queries(self, query_patterns: list[str], models: str) -> str:
        """
        想定クエリパターンに対するインデックス設計と最適化クエリを生成する。
        実行計画の考察も含む。
        """
        ...

    @tool
    def generate_seed_data(self, models: str, count: int = 10) -> str:
        """
        テスト・開発用のシードデータ投入スクリプトを生成する。
        Faker ライブラリを用いたリアルなダミーデータを生成する。
        """
        ...

    @tool
    def generate_db_config(self, db_type: str, use_async: bool = True) -> str:
        """
        データベース接続設定・コネクションプール設定を生成する。
        非同期対応 (asyncpg / aiosqlite) と環境変数ベースの設定を含む。
        """
        ...

    # ------------------------------------------------------------------
    # Node entry point
    # ------------------------------------------------------------------

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        DB設計・実装を行い database_result に格納する。
        ProjectManager または ReviewManager から呼ばれる。
        """
        messages = self._build_messages(state)
        response = self._bound_llm.invoke(messages)

        # TODO: tool_calls を実行してDB成果物を組み立てる
        database_result: str = ""

        return {
            **state,
            "messages":       state["messages"] + [response],
            "database_result": database_result,
        }
