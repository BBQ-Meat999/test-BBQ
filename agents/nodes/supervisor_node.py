"""
SupervisorNode — UpWork案件の仕様を解析し、担当エージェントへルーティングする。

仕様がバックエンドのみ → "backend"
仕様がフロントエンドのみ → "frontend"
仕様が両方 → "both" (LangGraph Send API で並列実行)
RAG検索が必要 → "search"
推論・分析が必要 → "analysis"
全作業完了 → "writer"
"""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.tools import tool

from agents.Agent_Node import AgentNode


NEXT_NODES = Literal["backend", "frontend", "both", "search", "analysis", "writer", "END"]


class SupervisorNode(AgentNode):
    """
    UpWork案件オーケストレーター。
    ユーザーから受け取った自然言語仕様を解析し、
    適切なエージェントへ仕事を振り分ける。
    """

    node_name = "supervisor"

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @tool
    def analyze_spec(self, spec: str) -> dict[str, Any]:
        """
        クライアント仕様を解析して作業種別・技術要件・優先度を抽出する。
        Returns:
            task_type   : "backend" | "frontend" | "both"
            tech_stack  : 必要な技術スタック一覧
            priority    : 優先度 ("high" | "medium" | "low")
            needs_search: RAG検索が必要か
        """
        ...

    @tool
    def route(self, destination: NEXT_NODES, reason: str) -> str:
        """
        次に処理すべきエージェントノードを指定する。
        destination: ルーティング先
        reason     : ルーティング理由 (ログ・デバッグ用)
        """
        ...

    @tool
    def check_completion(self, backend_result: str, frontend_result: str, task_type: str) -> bool:
        """
        全タスクが完了しているか確認する。
        task_type が "both" の場合、両方の結果が揃っていることを確認する。
        """
        ...

    # ------------------------------------------------------------------
    # Node entry point
    # ------------------------------------------------------------------

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        仕様を解析してルーティング先を決定する。
        state["next"] にルーティング先を書き込む。
        """
        messages = self._build_messages(state)
        response = self._bound_llm.invoke(messages)

        # TODO: tool_calls からルーティング先と task_type を抽出する
        next_node: str = "END"
        task_type: str = state.get("task_type", "")

        return {
            **state,
            "messages": state["messages"] + [response],
            "next": next_node,
            "task_type": task_type,
        }
