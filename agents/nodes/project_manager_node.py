"""
ProjectManagerNode — UpWork 案件の最上位オーケストレーター。

責務:
  1. 報奨金に基づき全エージェントの最適モデルを選択 (利益最大化)
  2. クライアント仕様を精読して要件を構造化する
  3. 詳細な作業計画書を作成する
  4. 担当エージェントを選定して具体的な指示文を生成する
  5. Human-in-the-loop: 作業計画確定後に LangGraph interrupt() で停止し、
     人間の承認 / 修正指示を受け取ってから実装を開始する
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool
from langgraph.types import interrupt

from agents.Agent_Node import AgentNode
from config.model_selector import ModelSelector
from config.settings import settings


ASSIGNABLE_AGENTS = ["backend", "frontend", "database", "tool_specialist"]


class ProjectManagerNode(AgentNode):
    """
    プロジェクトマネージャー。

    最初のノードとして:
      - 報奨金からモデル割当を決定 (select_models)
      - 仕様を構造化要件に変換
      - 作業計画と担当エージェント指示を生成
      - Human-in-the-loop で計画を承認させる
    """

    node_name = "project_manager"

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @tool
    def select_models(self, reward_amount: float) -> dict[str, Any]:
        """
        報奨金に基づき期待利益を最大化するモデルを各ノードに割り当てる。

        コスト計算の考え方:
          - 安価なモデル: API コストは低いが手戻り率が高い
          - 高価なモデル: 品質が高く手戻りを抑制できる
          - expected_profit = reward × delivery_success_rate - total_api_cost

        Returns:
            model_assignments : dict[str, str]  node_name → Claude model_id
            estimated_cost    : float           期待 API コスト (USD)
            estimated_profit  : float           期待利益 (USD)
            strategy_name     : str             選択戦略名
            strategy_desc     : str             戦略の説明
        """
        return ModelSelector.select_assignments(
            reward_amount=reward_amount,
            max_review_loops=settings.workflow.max_review_loops,
        )

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
        1. 報奨金からモデル割当を決定 (select_models — 決定論的)
        2. 仕様を解析して作業計画を立てる
        3. 必要に応じて Human-in-the-loop で承認を待つ

        Human-in-the-loop フロー:
          1. 作業計画を生成する
          2. settings.workflow.require_plan_approval が True なら interrupt()
          3. 人間が "approve" を返したら実装開始
          4. 修正指示が来た場合は incorporate_human_feedback で計画を更新
        """

        # ── Step 1: モデル選択 (LLM 不要、決定論的) ──────────────────
        reward_amount: float = state.get("reward_amount", 0.0)
        selection = ModelSelector.select_assignments(
            reward_amount=reward_amount,
            max_review_loops=settings.workflow.max_review_loops,
        )

        # ── Step 2: LLM で仕様解析・計画立案 ─────────────────────────
        response = self._invoke(state)

        # TODO: tool_calls を実行して以下を取得する
        work_plan: str = ""
        assigned_agents: list[str] = []
        agent_instructions: dict[str, str] = {}

        # ── Step 3: Human-in-the-loop ─────────────────────────────────
        if settings.workflow.require_plan_approval:
            human_feedback: str = interrupt({
                "type":            "plan_approval",
                "work_plan":       work_plan,
                "assigned_agents": assigned_agents,
                "instructions":    agent_instructions,
                "model_strategy":  selection["strategy_name"],
                "estimated_cost":  selection["estimated_cost"],
                "estimated_profit": selection["estimated_profit"],
                "message": (
                    "作業計画を確認してください。\n"
                    f"使用モデル戦略: {selection['strategy_name']} "
                    f"({selection['strategy_desc']})\n"
                    f"推定コスト: ${selection['estimated_cost']:.4f} / "
                    f"推定利益: ${selection['estimated_profit']:.4f}\n\n"
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
            # ── モデル選択結果 ──────────────────────────────────────────
            "model_assignments":  selection["model_assignments"],
            "estimated_cost":     selection["estimated_cost"],
            "estimated_profit":   selection["estimated_profit"],
        }
