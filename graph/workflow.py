"""
MultiAgentWorkflow — UpWork案件処理のLangGraph StateGraph。

グラフトポロジー
----------------
                    ┌──────────────┐
       START ──────►│  Supervisor  │◄──────────────────┐
                    └──────┬───────┘                   │
           ┌───────────────┼───────────────┐           │
           │               │               │           │
           ▼               ▼               ▼           │
       ┌───────┐      ┌─────────┐    ┌──────────┐     │
       │Search │      │Analysis │    │  "both"  │     │
       └───┬───┘      └────┬────┘    │(並列Send)│     │
           └───────────────┘         └──┬───┬───┘     │
                    │                   │   │          │
                    └───────────────────┘   │          │
                                            ▼          │
                ┌─────────┐         ┌─────────────┐   │
                │ Backend │         │  Frontend   │   │
                └────┬────┘         └──────┬──────┘   │
                     └──────────┬──────────┘           │
                                ▼                      │
                           ┌────────┐                  │
                           │ Writer │                  │
                           └────┬───┘                  │
                                ▼
                               END
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from langchain_core.messages import BaseMessage
from langgraph.constants import Send
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """グラフ全体で共有されるステート定義。"""

    # 会話履歴 (add_messages でメッセージを追記マージ)
    messages: Annotated[list[BaseMessage], add_messages]

    # UpWork クライアントから受け取った元仕様
    user_spec: str

    # supervisor が解析した作業種別 ("backend" | "frontend" | "both")
    task_type: str

    # supervisor が次に向けるルーティング先
    next: str

    # RAG 検索結果
    retrieved_docs: list[dict[str, Any]]

    # 分析結果
    analysis_result: str

    # 各エージェントの成果物
    backend_result: str
    frontend_result: str

    # 最終納品物 (UpWork 提出フォーマット)
    final_answer: str


class MultiAgentWorkflow:
    """
    UpWork案件処理の LangGraph StateGraph を組み立てる。
    `.compile()` で実行可能グラフを返す。
    """

    def __init__(
        self,
        supervisor_node,
        search_node,
        analysis_node,
        backend_node,
        frontend_node,
        writer_node,
    ) -> None:
        self.supervisor  = supervisor_node
        self.search      = search_node
        self.analysis    = analysis_node
        self.backend     = backend_node
        self.frontend    = frontend_node
        self.writer      = writer_node

    # ------------------------------------------------------------------
    # Routing functions
    # ------------------------------------------------------------------

    def _route_from_supervisor(self, state: AgentState) -> str | list:
        """
        Supervisor の next フィールドに基づいてルーティングする。
        "both" の場合は Send API で backend / frontend を並列実行する。
        """
        next_node = state.get("next", END)

        if next_node == "both":
            # LangGraph Send API: 同一ステートを両ノードに同時送信
            return [
                Send("backend",  state),
                Send("frontend", state),
            ]

        return next_node if next_node in {"search", "analysis", "backend", "frontend", "writer"} else END

    # ------------------------------------------------------------------
    # Graph builder
    # ------------------------------------------------------------------

    def compile(self):
        """StateGraph をビルドしてコンパイル済みグラフを返す。"""
        graph = StateGraph(AgentState)

        # ── ノード登録 ────────────────────────────────────────────────
        graph.add_node("supervisor", self.supervisor.run)
        graph.add_node("search",     self.search.run)
        graph.add_node("analysis",   self.analysis.run)
        graph.add_node("backend",    self.backend.run)
        graph.add_node("frontend",   self.frontend.run)
        graph.add_node("writer",     self.writer.run)

        # ── エントリエッジ ────────────────────────────────────────────
        graph.add_edge(START, "supervisor")

        # ── Supervisor からの条件付きルーティング ──────────────────────
        # "both" → Send([backend, frontend]) で並列
        # その他 → 対応ノードへ直接
        graph.add_conditional_edges(
            "supervisor",
            self._route_from_supervisor,
            {
                "search":   "search",
                "analysis": "analysis",
                "backend":  "backend",
                "frontend": "frontend",
                "writer":   "writer",
                END:        END,
            },
        )

        # ── Search / Analysis はループバック ─────────────────────────
        graph.add_edge("search",   "supervisor")
        graph.add_edge("analysis", "supervisor")

        # ── 作業ノードは Writer へ集約 ────────────────────────────────
        # 単独実行・並列実行ともに Writer が最終統合する
        graph.add_edge("backend",  "writer")
        graph.add_edge("frontend", "writer")

        # ── Writer → 完了 ─────────────────────────────────────────────
        graph.add_edge("writer", END)

        return graph.compile()
