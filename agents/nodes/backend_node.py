"""
BackendNode — Python専門のバックエンド実装エージェント。

成果物は文字列ではなく dict[str, str] (ファイルパス → コード) で返す。
これにより多ファイルプロジェクトに対応し、messages の肥大化を防ぐ。
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from agents.Agent_Node import AgentNode


class BackendNode(AgentNode):
    """
    Python バックエンド専門エージェント。
    state["agent_instructions"]["backend"] または
    state["fix_instructions"]["backend"] の指示に従い実装する。
    成果物は state["backend_files"] (dict[str, str]) に格納する。
    """

    node_name = "backend"

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @tool
    def design_api(self, spec: str, framework: str = "FastAPI") -> dict[str, Any]:
        """
        クライアント仕様から REST / GraphQL API の設計書を生成する。
        Returns:
            endpoints    : list[{"method": str, "path": str, "request": dict, "response": dict}]
            auth_scheme  : str
            framework    : str
        """
        ...

    @tool
    def write_python_code(self, design: dict, requirements: list[str]) -> dict[str, str]:
        """
        API デザインと要件から Python ソースコードを生成する。
        Returns: {"src/main.py": "...", "src/routers/xxx.py": "...", ...}
        """
        ...

    @tool
    def write_tests(self, source_files: dict[str, str], framework: str = "pytest") -> dict[str, str]:
        """
        ソースコードに対するテストを生成する。
        Returns: {"tests/test_xxx.py": "...", ...}
        """
        ...

    @tool
    def write_requirements(self, source_files: dict[str, str]) -> dict[str, str]:
        """
        ソースコードを解析して依存関係ファイルを生成する。
        Returns: {"pyproject.toml": "...", "requirements.txt": "..."}
        """
        ...

    @tool
    def generate_dockerfile(self, app_type: str, python_version: str = "3.11") -> dict[str, str]:
        """
        本番用 Dockerfile と docker-compose.yml を生成する。
        Returns: {"Dockerfile": "...", "docker-compose.yml": "..."}
        """
        ...

    @tool
    def apply_fix(self, current_files: dict[str, str], fix_instruction: str) -> dict[str, str]:
        """
        修正指示 (ReviewManager 由来) を受けて既存ファイルを修正する。
        Returns: 修正後のファイル辞書 (変更されたファイルのみ)
        """
        ...

    # ------------------------------------------------------------------
    # Node entry point
    # ------------------------------------------------------------------

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        バックエンド成果物を生成し backend_files (dict[str, str]) に格納する。
        修正指示がある場合は apply_fix を使用する。
        """
        response = self._invoke(state)

        fix_inst = state.get("fix_instructions", {}).get(self.node_name)
        existing = state.get("backend_files", {})

        if fix_inst and existing:
            # 修正ループ: 既存ファイルを修正する
            # TODO: apply_fix tool_call を実行
            backend_files = existing  # stub
        else:
            # 初回実装
            # TODO: design_api → write_python_code → write_tests → write_requirements → generate_dockerfile
            backend_files: dict[str, str] = {}

        return {
            **state,
            "messages":     state["messages"] + [response],
            "backend_files": backend_files,
        }
