"""
MultiAgentWorkflow — UpWork案件処理の完全版 LangGraph StateGraph。

アーキテクチャ全体図は docs/architecture.md を参照。
グラフ定義の単一情報源は graph/diagram_spec.py。
図の更新: python tools/generate_diagram.py

```mermaid
flowchart TD
    START(["🚀 START"]) --> PM

    subgraph MGMT["Management Layer"]
        PM["ProjectManager\n仕様解析・担当割当・指示生成\nHuman-in-the-loop: interrupt()"]
        RM["ReviewManager\nループ制御 MAX=2"]
    end

    subgraph WORKERS["Worker Layer  ＝＝  Send API 並列"]
        BE["BackendNode"]
        FE["FrontendNode"]
        DB["DatabaseNode"]
        TS["ToolSpecialistNode"]
    end

    subgraph QUALITY["Quality Gate"]
        TR["TestRunnerNode\npytest / ruff / mypy"]
        CR["CodeReviewNode\n横断レビュー + テスト結果評価"]
    end

    PM ==>|"interrupt() 承認後"| BE & FE & DB & TS
    BE & FE & DB & TS -->|"収束"| TR
    TR --> CR
    CR --> RM
    RM ==>|"修正 loop<2"| BE & FE & DB & TS
    RM -->|"完了 or loop≥2"| W["WriterNode"]
    W --> END(["✅ END"])
```
"""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import Send
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """グラフ全体で共有されるステート定義。"""

    # ── 会話履歴 ─────────────────────────────────────────────────────
    messages: Annotated[list[BaseMessage], add_messages]

    # ── 入力 ─────────────────────────────────────────────────────────
    user_spec: str                      # UpWork クライアントからの仕様テキスト

    # ── ProjectManager ────────────────────────────────────────────────
    work_plan: str                      # 作業計画書
    assigned_agents: list[str]          # 担当エージェント名リスト
    agent_instructions: dict[str, str]  # エージェント名 → 指示文
    human_feedback: str                 # interrupt() で受け取る人間の承認/修正

    # ── 実装成果物 (dict[str, str]: ファイルパス → コード) ────────────
    tool_spec_files: dict[str, str]
    backend_files:   dict[str, str]
    frontend_files:  dict[str, str]
    database_files:  dict[str, str]

    # ── テスト実行結果 ────────────────────────────────────────────────
    test_results: dict[str, Any]        # TestRunnerNode の実行結果

    # ── コードレビュー ────────────────────────────────────────────────
    code_review_feedback: str           # CodeReviewNode の総合フィードバック
    fix_targets: list[str]              # 修正が必要なエージェント名リスト

    # ── ReviewManager ────────────────────────────────────────────────
    review_loop_count: int              # レビューループ回数 (上限 max_review_loops)
    fix_instructions: dict[str, str]    # エージェント名 → 修正指示文
    remaining_issues: str               # ループ上限到達後の残存課題
    next: str                           # ルーティングシグナル ("fix" | "writer")

    # ── 最終納品物 ────────────────────────────────────────────────────
    final_files:  dict[str, str]        # 全納品ファイル (merge済み)
    final_answer: str                   # UpWork 提出フォーマットの納品物


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
        test_runner_node,
        code_review_node,
        review_manager_node,
        writer_node,
    ) -> None:
        self.project_manager  = project_manager_node
        self.backend          = backend_node
        self.frontend         = frontend_node
        self.database         = database_node
        self.tool_specialist  = tool_specialist_node
        self.test_runner      = test_runner_node
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
            return "writer"
        if len(targets) == 1:
            return targets[0]
        return [Send(agent, state) for agent in targets]

    def _dispatch_fixes_from_review_manager(self, state: AgentState) -> str | list:
        """
        ReviewManager の判断に基づき修正ディスパッチまたは Writer へルーティング。
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

    def compile(self, checkpointer: MemorySaver | None = None):
        """
        StateGraph をビルドしてコンパイル済みグラフを返す。
        checkpointer に MemorySaver を渡すと interrupt() が有効になる。
        """
        graph = StateGraph(AgentState)

        # ── ノード登録 ────────────────────────────────────────────────
        graph.add_node("project_manager", self.project_manager.run)
        graph.add_node("backend",         self.backend.run)
        graph.add_node("frontend",        self.frontend.run)
        graph.add_node("database",        self.database.run)
        graph.add_node("tool_specialist", self.tool_specialist.run)
        graph.add_node("test_runner",     self.test_runner.run)
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
                "backend":         "backend",
                "frontend":        "frontend",
                "database":        "database",
                "tool_specialist": "tool_specialist",
                "writer":          "writer",
            },
        )

        # ── 実装ノード → TestRunner へ収束 ───────────────────────────
        for node in ("backend", "frontend", "database", "tool_specialist"):
            graph.add_edge(node, "test_runner")

        # ── TestRunner → CodeReview → ReviewManager ──────────────────
        graph.add_edge("test_runner",  "code_review")
        graph.add_edge("code_review",  "review_manager")

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

        return graph.compile(checkpointer=checkpointer)
