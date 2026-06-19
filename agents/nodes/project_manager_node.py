"""
ProjectManagerNode — UpWork 案件の最上位オーケストレーター。

責務:
  1. 報奨金に基づき全エージェントの最適モデルを選択する (利益最大化・決定論的)
  2. クライアント仕様を精読し、作業計画・担当割当・指示文を生成する (構造化出力)
  3. Human-in-the-loop: 作業計画確定後に LangGraph interrupt() で停止し、
     人間の承認 / 修正指示を受け取ってから実装を開始する
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import interrupt

from agents.Agent_Node import AgentNode
from agents.schemas import WorkPlan
from config.model_selector import ModelSelector
from config.settings import settings

ASSIGNABLE_AGENTS = ["backend", "frontend", "database", "tool_specialist"]


class ProjectManagerNode(AgentNode):
    """プロジェクトマネージャー。グラフの最初のノード。"""

    node_name = "project_manager"

    def _normalize_assignments(self, plan: WorkPlan) -> list[str]:
        """LLM が返した担当リストを検証する。空/不正なら全ワーカーにフォールバック。"""
        valid = [a for a in plan.assigned_agents if a in ASSIGNABLE_AGENTS]
        return valid or list(ASSIGNABLE_AGENTS)

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        1. 報奨金からモデル割当を決定 (決定論的) し state に注入する
        2. 仕様を解析して作業計画・担当割当を生成する (割当モデルで実行)
        3. require_plan_approval が True なら interrupt() で承認を待つ

        注: interrupt() でグラフが一時停止し再開すると、本ノードは先頭から再実行される
            (LangGraph の HITL 仕様)。承認後の修正指示は再生成で計画へ反映する。
        """
        # ── Step 1: モデル選択 (LLM 不要・決定論的) ──────────────────────
        reward_amount: float = state.get("reward_amount", 0.0)
        selection = ModelSelector.select_assignments(
            reward_amount=reward_amount,
            max_review_loops=settings.workflow.max_review_loops,
        )
        # 以降の全ノードが割当モデルを使えるよう、計画生成より前に注入する
        state_wm = {
            **state,
            "model_assignments": selection["model_assignments"],
            "estimated_cost":    selection["estimated_cost"],
            "estimated_profit":  selection["estimated_profit"],
        }

        # ── Step 2: 仕様解析・計画立案 (PM 自身も割当モデルで実行) ───────
        plan: WorkPlan = self._generate(state_wm, WorkPlan)
        assigned = self._normalize_assignments(plan)

        # ── Step 3: Human-in-the-loop ─────────────────────────────────────
        if settings.workflow.require_plan_approval:
            model_summary = "\n".join(
                f"  {node:<18}: {model_id}"
                for node, model_id in selection["model_assignments"].items()
            )
            feedback: str = interrupt({
                "type":              "plan_approval",
                "work_plan":         plan.work_plan,
                "assigned_agents":   assigned,
                "instructions":      plan.agent_instructions,
                "model_strategy":    selection["strategy_name"],
                "model_assignments": selection["model_assignments"],
                "estimated_cost":    selection["estimated_cost"],
                "estimated_profit":  selection["estimated_profit"],
                "message": (
                    "═══ 作業計画 承認待ち ═══\n\n"
                    f"【モデル戦略】{selection['strategy_name']} — {selection['strategy_desc']}\n"
                    f"【ノード別割当】\n{model_summary}\n\n"
                    "【コスト試算】\n"
                    f"  報奨金       : ${reward_amount:.2f}\n"
                    f"  推定APIコスト: ${selection['estimated_cost']:.4f}\n"
                    f"  推定利益     : ${selection['estimated_profit']:.4f}\n\n"
                    "承認する場合は 'approve' を入力してください。\n"
                    "修正が必要な場合は具体的な指示を入力してください。"
                ),
            })

            # 'approve' 以外のフィードバックは計画へ反映して再生成する
            if feedback and feedback.strip().lower() != "approve":
                revised = self._generate(
                    state_wm,
                    WorkPlan,
                    extra=[HumanMessage(content=(
                        "以下は作業計画に対する人間からの修正指示です。"
                        "これを反映して作業計画・担当割当・指示文を更新してください。\n\n"
                        f"{feedback}"
                    ))],
                )
                plan = revised
                assigned = self._normalize_assignments(plan)

        return {
            "messages":           [AIMessage(content=f"[project_manager] 計画確定・担当={assigned}")],
            "model_assignments":  selection["model_assignments"],
            "estimated_cost":     selection["estimated_cost"],
            "estimated_profit":   selection["estimated_profit"],
            "work_plan":          plan.work_plan,
            "assigned_agents":    assigned,
            "agent_instructions": plan.agent_instructions,
            "human_feedback":     "",
        }
