"""
ProjectManagerNode — UpWork 案件の最上位オーケストレーター。

Human-in-the-loop: 作業計画確定後に LangGraph interrupt() で停止し、
人間の承認 / 修正指示を受け取ってから実装を開始する。
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool
from langgraph.types import interrupt

from agents.Agent_Node import AgentNode
from config.settings import settings


ASSIGNABLE_AGENTS = ["backend", "frontend", "database", "tool_specialist"]


class ProjectManagerNode(AgentNode):
    """
    プロジェクトマネージャー。

    責務:
      1. クライアント仕様を精読して要件を構造化する
      2. 詳細な作業計画書を作成する
      3. 担当エージェントを選定して具体的な指示文を生成する
      4. (オプション) Human-in-the-loop で計画を人間に承認させる
    """

    node_name = "project_manager"

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @tool
    def parse_requirements(self, spec: str) -> dict[str, Any]:
        """
        仕様書を解析して構造化された要件定義を返す。
        Returns:
            functional_requirements    : list[str]
            non_functional_requirements: list[str]
            tech_constraints           : list[str]
            ambiguities                : list[str]  ← 不明点リスト
            priority                   : dict[str, str]
        """
        ...

    @tool
    def create_work_plan(self, requirements: dict[str, Any]) -> str:
        """
        要件定義から詳細な作業計画書を生成する。
        各エージェントへのタスク分解・依存関係・完了基準・成果物リストを含む。
        """
        ...

    @tool
    def assign_agents(self, work_plan: str) -> dict[str, Any]:
        """
        作業計画から担当エージェントと指示文を生成する。
        Returns:
            assigned_agents    : list[str]
            agent_instructions : dict[str, str]  # エージェント名 → 指示文
        """
        ...

    @tool
    def incorporate_human_feedback(
        self, work_plan: str, human_feedback: str
    ) -> dict[str, Any]:
        """
        人間からのフィードバックを作業計画に反映する。
        Returns: {"work_plan": str, "agent_instructions": dict}
        """
        ...

    # ------------------------------------------------------------------
    # Node entry point
    # ------------------------------------------------------------------

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        仕様を解析して作業計画を立て、必要に応じて人間の承認を待つ。

        Human-in-the-loop フロー:
          1. 作業計画を生成する
          2. settings.workflow.require_plan_approval が True なら interrupt()
          3. 人間が "approve" を返したら実装開始
          4. 修正指示が来た場合は incorporate_human_feedback で計画を更新
        """
        response = self._invoke(state)

        # TODO: tool_calls を実行して以下を取得する
        work_plan: str = ""
        assigned_agents: list[str] = []
        agent_instructions: dict[str, str] = {}

        # ── Human-in-the-loop ────────────────────────────────────────
        if settings.workflow.require_plan_approval:
            human_feedback: str = interrupt({
                "type":             "plan_approval",
                "work_plan":        work_plan,
                "assigned_agents":  assigned_agents,
                "instructions":     agent_instructions,
                "message": (
                    "作業計画を確認してください。\n"
                    "承認する場合は 'approve' を入力してください。\n"
                    "修正が必要な場合は具体的な指示を入力してください。"
                ),
            })

            if human_feedback and human_feedback.strip().lower() != "approve":
                # TODO: incorporate_human_feedback tool_call を実行して計画を更新
                pass

        return {
            **state,
            "messages":           state["messages"] + [response],
            "work_plan":          work_plan,
            "assigned_agents":    assigned_agents,
            "agent_instructions": agent_instructions,
            "human_feedback":     "",
        }
