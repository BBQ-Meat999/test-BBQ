"""
ProjectManagerNode — UpWork案件の最上位オーケストレーター。

ユーザーから受け取った自然言語仕様を解析し、
詳細な作業計画を立てて各専門エージェントへ適切な指示を送る。
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from agents.Agent_Node import AgentNode


# 割り当て可能なエージェント一覧
ASSIGNABLE_AGENTS = ["backend", "frontend", "database", "tool_specialist"]


class ProjectManagerNode(AgentNode):
    """
    プロジェクトマネージャー。

    責務:
      1. クライアント仕様を精読して要件を構造化する
      2. 必要な専門エージェントを選定し作業指示を生成する
      3. 各エージェントへの具体的な指示文を state["agent_instructions"] に格納する
      4. 担当エージェントリストを state["assigned_agents"] に格納する
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
            functional_requirements : 機能要件リスト
            non_functional_requirements: 非機能要件リスト
            tech_constraints        : 技術的制約
            priority                : 優先度マップ
        """
        ...

    @tool
    def create_work_plan(self, requirements: dict[str, Any]) -> str:
        """
        要件定義から詳細な作業計画書を生成する。
        各エージェントへのタスク分解・依存関係・完了基準を含む。
        """
        ...

    @tool
    def assign_agents(self, work_plan: str) -> dict[str, list[str]]:
        """
        作業計画から担当エージェントを選定する。
        Returns:
            assigned_agents     : 担当エージェント名リスト
            agent_instructions  : エージェント名 → 指示文のマッピング
        """
        ...

    @tool
    def generate_agent_instruction(self, agent: str, task: str, context: str) -> str:
        """
        個別エージェントへの具体的な実装指示文を生成する。
        agent  : 対象エージェント名
        task   : 実装タスク内容
        context: 関連する仕様・制約・依存情報
        """
        ...

    # ------------------------------------------------------------------
    # Node entry point
    # ------------------------------------------------------------------

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        仕様を解析して作業計画を立て、担当エージェントと指示を確定する。
        """
        messages = self._build_messages(state)
        response = self._bound_llm.invoke(messages)

        # TODO: tool_calls を実行して以下を取得する
        work_plan: str = ""
        assigned_agents: list[str] = []
        agent_instructions: dict[str, str] = {}

        return {
            **state,
            "messages":          state["messages"] + [response],
            "work_plan":         work_plan,
            "assigned_agents":   assigned_agents,
            "agent_instructions": agent_instructions,
        }
