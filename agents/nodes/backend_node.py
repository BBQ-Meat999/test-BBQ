"""
BackendNode — Python専門のバックエンド実装エージェント。

UpWorkクライアントの仕様を受け取り、Pythonコード・APIデザイン・
DBスキーマ・テストコードを生成する。
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from agents.Agent_Node import AgentNode


class BackendNode(AgentNode):
    """
    Python バックエンド専門エージェント。
    state["user_spec"] を読み取り、成果物を state["backend_result"] に書き込む。
    """

    node_name = "backend"

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @tool
    def design_api(self, spec: str, framework: str = "FastAPI") -> str:
        """
        クライアント仕様からREST / GraphQL APIの設計書を生成する。
        エンドポイント一覧・リクエスト/レスポンス型・認証方式を含む。
        """
        ...

    @tool
    def write_python_code(self, design: str, requirements: list[str]) -> str:
        """
        APIデザインと要件リストからPythonソースコードを生成する。
        型ヒント・docstring・例外処理を含む本番品質のコードを出力する。
        """
        ...

    @tool
    def design_database_schema(self, entities: list[str], relations: list[str]) -> str:
        """
        エンティティとリレーション定義からSQLAlchemy / Pydanticモデルを生成する。
        マイグレーションスクリプト (Alembic) も合わせて出力する。
        """
        ...

    @tool
    def write_tests(self, source_code: str, framework: str = "pytest") -> str:
        """
        ソースコードに対するユニットテスト・統合テストを生成する。
        カバレッジ80%以上を目標としたテストケースを出力する。
        """
        ...

    @tool
    def write_requirements(self, source_code: str) -> str:
        """
        ソースコードを解析して requirements.txt / pyproject.toml を生成する。
        バージョンは最新安定版にピン留めする。
        """
        ...

    @tool
    def generate_dockerfile(self, app_type: str, python_version: str = "3.11") -> str:
        """
        アプリ種別に応じた本番用 Dockerfile と docker-compose.yml を生成する。
        マルチステージビルド・非rootユーザー実行を適用する。
        """
        ...

    # ------------------------------------------------------------------
    # Node entry point
    # ------------------------------------------------------------------

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        仕様を分析してバックエンド成果物を生成し、backend_result に格納する。
        LangGraph の並列実行 (Send API) でも呼び出される。
        """
        messages = self._build_messages(state)
        response = self._bound_llm.invoke(messages)
        # TODO: tool_calls を実行して各成果物を組み立てる
        backend_result: str = ""
        return {
            **state,
            "messages": state["messages"] + [response],
            "backend_result": backend_result,
        }
