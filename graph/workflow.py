"""
MultiAgentWorkflow — UpWork案件処理の完全版 LangGraph StateGraph。

グラフトポロジー
----------------

  START
    │
    ▼
  ProjectManager  ─── 仕様解析・作業計画・担当割当
    │ (Send API / 並列)
    ├──────────────┬──────────────┬──────────────┐
    ▼              ▼              ▼              ▼
  Backend      Frontend      Database     ToolSpecialist
    └──────────────┴──────────────┴──────────────┘
                         │ (全員 CodeReview へ収束)
                         ▼
                     CodeReview  ─── 横断レビュー (品質・整合性・セキュリティ)
                         │
                         ▼
                    ReviewManager  ─── ループ制御 (最大 MAX_REVIEW_LOOPS 回)
                         │
               ┌─────────┴──────────────────────────────────┐
               │ (問題あり & loop < MAX)                      │ (問題なし or loop >= MAX)
               │ (Send API / 並列 fix)                        ▼
               ├──────────────┬──────────────┐            Writer
               ▼              ▼              ▼              │
           Backend fix    Frontend fix  Database fix        ▼
               └──────────────┴──────────────┘            END
                              │
                              ▼
                          CodeReview  (再レビュー)
                              ▼
                         ReviewManager
                              ...
"""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from langgraph.constants import Send
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from agents.nodes.review_manager_node import MAX_REVIEW_LOOPS


class AgentState(TypedDict):
    """グラフ全体で共有されるステート定義。"""

    # ── 会話履歴 ─────────────────────────────────────────────────────
    messages: Annotated[list[BaseMessage], add_messages]

    # ── 入力 ─────────────────────────────────────────────────────────
    user_spec: str                    # UpWork クライアントからの仕様テキスト

    # ── ProjectManager ────────────────────────────────────────────────
    work_plan: str                    # 作業計画書
    assigned_agents: list[str]        # 担当エージェント名リスト
    agent_instructions: dict[str, str]  # エージェント名 → 指示文

    # ── 実装成果物 ────────────────────────────────────────────────────
    tool_spec_result: str             # ToolSpecialistNode の成果物
    backend_result: str               # BackendNode の成果物
    frontend_result: str              # FrontendNode の成果物
    database_result: str              # DatabaseNode の成果物

    # ── RAG ──────────────────────────────────────────────────────────
    retrieved_docs: list[dict[str, Any]]
    analysis_result: str

    # ── コードレビュー ────────────────────────────────────────────────
    code_review_feedback: str         # CodeReviewNode の総合フィードバック
    fix_targets: list[str]            # 修正が必要なエージェント名リスト

    # ── ReviewManager ────────────────────────────────────────────────
    review_loop_count: int            # レビューループ回数 (上限 MAX_REVIEW_LOOPS)
    fix_instructions: dict[str, str]  # エージェント名 → 修正指示文
    remaining_issues: str             # ループ上限到達後の残存課題
    next: str                         # ルーティングシグナル ("fix" | "writer")

    # ── 最終納品物 ────────────────────────────────────────────────────
    final_answer: str                 # UpWork 提出フォーマットの納品物


class MultiAgentWorkflow:
    """
    UpWork案件処理の完全版 LangGraph StateGraph を組み立てる。
    `.compile()` で実行可能グラフを返す。
    """

    def __init__(
        self,
        project_manager_node,
        backend_node,
        frontend_node,
        database_node,
        tool_specialist_node,
        search_node,
        analysis_node,
        code_review_node,
        review_manager_node,
        writer_node,
    ) -> None:
        self.project_manager  = project_manager_node
        self.backend          = backend_node
        self.frontend         = frontend_node
        self.database         = database_node
        self.tool_specialist  = tool_specialist_node
        self.search           = search_node
        self.analysis         = analysis_node
        self.code_review      = code_review_node
        self.review_manager   = review_manager_node
        self.writer           = writer_node

    # ------------------------------------------------------------------
    # Routing functions
    # ------------------------------------------------------------------

    def _dispatch_from_project_manager(self, state: AgentState) -> str | list:
        """
        ProjectManager が確定した assigned_agents に従いノードへディスパッチ。
        複数エージェントは Send API で並列実行する。
        """
        agents = state.get("assigned_agents", [])

        valid = {"backend", "frontend", "database", "tool_specialist"}
        targets = [a for a in agents if a in valid]

        if not targets:
            return "writer"  # 担当なし → 直接 Writer へ

        if len(targets) == 1:
            return targets[0]

        # 複数: 並列実行 (Send API)
        return [Send(agent, state) for agent in targets]

    def _dispatch_fixes_from_review_manager(self, state: AgentState) -> str | list:
        """
        ReviewManager の判断に基づき修正ディスパッチまたは Writer へルーティング。
        - next == "writer" → Writer へ
        - next == "fix"    → fix_targets を Send で並列修正実行
        """
        if state.get("next") == "writer":
            return "writer"

        fix_targets = state.get("fix_targets", [])
        valid = {"backend", "frontend", "database", "tool_specialist"}
        targets = [t for t in fix_targets if t in valid]

        if not targets:
            return "writer"

        if len(targets) == 1:
            return targets[0]

        return [Send(agent, state) for agent in targets]

    # ------------------------------------------------------------------
    # Graph builder
    # ------------------------------------------------------------------

    def compile(self):
        """StateGraph をビルドしてコンパイル済みグラフを返す。"""
        graph = StateGraph(AgentState)

        # ── ノード登録 ────────────────────────────────────────────────
        graph.add_node("project_manager", self.project_manager.run)
        graph.add_node("backend",         self.backend.run)
        graph.add_node("frontend",        self.frontend.run)
        graph.add_node("database",        self.database.run)
        graph.add_node("tool_specialist", self.tool_specialist.run)
        graph.add_node("search",          self.search.run)
        graph.add_node("analysis",        self.analysis.run)
        graph.add_node("code_review",     self.code_review.run)
        graph.add_node("review_manager",  self.review_manager.run)
        graph.add_node("writer",          self.writer.run)

        # ── エントリ ──────────────────────────────────────────────────
        graph.add_edge(START, "project_manager")

        # ── ProjectManager → 担当エージェントへ並列ディスパッチ ───────
        graph.add_conditional_edges(
            "project_manager",
            self._dispatch_from_project_manager,
            {
                "backend":        "backend",
                "frontend":       "frontend",
                "database":       "database",
                "tool_specialist": "tool_specialist",
                "writer":         "writer",
            },
        )

        # ── 実装ノード → CodeReview へ収束 (全員同じ宛先) ────────────
        for node in ("backend", "frontend", "database", "tool_specialist"):
            graph.add_edge(node, "code_review")

        # ── CodeReview → ReviewManager ───────────────────────────────
        graph.add_edge("code_review", "review_manager")

        # ── ReviewManager → 修正ループ or Writer ─────────────────────
        graph.add_conditional_edges(
            "review_manager",
            self._dispatch_fixes_from_review_manager,
            {
                "backend":         "backend",
                "frontend":        "frontend",
                "database":        "database",
                "tool_specialist": "tool_specialist",
                "writer":          "writer",
            },
        )

        # ── Writer → 完了 ─────────────────────────────────────────────
        graph.add_edge("writer", END)

        return graph.compile()
