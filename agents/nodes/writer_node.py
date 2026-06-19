"""
WriterNode — UpWork納品物を整形・統合して最終回答を生成する。

BackendNode / FrontendNode の成果物を受け取り、
クライアントへ提出できる形式の納品物パッケージを生成する。
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from agents.Agent_Node import AgentNode


class WriterNode(AgentNode):
    """
    UpWork納品物アセンブラー。
    backend_result・frontend_result・analysis_result を統合し、
    final_answer (クライアント提出用ドキュメント) を生成する。
    """

    node_name = "writer"

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @tool
    def compile_deliverable(
        self,
        backend_result: str,
        frontend_result: str,
        user_spec: str,
    ) -> str:
        """
        バックエンド・フロントエンドの成果物を統合し、
        UpWork納品物パッケージ (README + コード + 設定ファイル) を生成する。
        """
        ...

    @tool
    def write_handover_doc(self, deliverable: str, tech_stack: list[str]) -> str:
        """
        クライアントへの引き渡しドキュメントを生成する。
        セットアップ手順・環境変数・デプロイ方法・注意事項を含む。
        """
        ...

    @tool
    def quality_check(self, deliverable: str, original_spec: str) -> dict[str, Any]:
        """
        成果物がクライアント仕様を満たしているかチェックする。
        未実装項目・改善提案をリストアップする。
        Returns: {"passed": bool, "missing": list[str], "suggestions": list[str]}
        """
        ...

    @tool
    def format_for_upwork(self, deliverable: str, handover_doc: str) -> str:
        """
        UpWork提出フォーマットに整形する。
        Markdownで構造化し、コードブロック・セクション見出しを付与する。
        """
        ...

    # ------------------------------------------------------------------
    # Node entry point
    # ------------------------------------------------------------------

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        全エージェントの成果物を統合して final_answer を生成する。
        並列実行後は backend_result と frontend_result 両方が揃った状態で呼ばれる。
        """
        messages = self._build_messages(state)
        response = self._bound_llm.invoke(messages)
        # TODO: tool_calls を実行して納品物を組み立てる
        final_answer: str = ""
        return {
            **state,
            "messages": state["messages"] + [response],
            "final_answer": final_answer,
        }
