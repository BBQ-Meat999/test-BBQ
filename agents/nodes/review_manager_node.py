"""
ReviewManagerNode — コードレビュー結果を受け取り修正ループを制御するマネージャー。

CodeReview のフィードバックを解釈し、各ワーカーへ具体的な修正指示を送るか、
Writer への移行を決定する。ループ上限は settings.workflow.max_review_loops で管理する。
(MAX_REVIEW_LOOPS をこのファイルに定義すると config/systemMessage.py との
 循環インポートが発生するため settings に集約している)

ループカウンタは単調増加させる (旧実装は escalate 時に 0 リセットしていたため、
最終 state のループ回数が誤って 0 に見える不具合があった)。
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from agents.Agent_Node import AgentNode
from agents.schemas import ReviewDecision
from config.settings import settings


class ReviewManagerNode(AgentNode):
    """レビューマネージャー。修正ループの制御を担う。"""

    node_name = "review_manager"

    @property
    def max_loops(self) -> int:
        return settings.workflow.max_review_loops

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        レビュー結果を解釈し、修正指示を生成するか Writer への移行を決定する。
        escalate 判定は決定論的に行い、ループ上限を確実に守る。
        """
        loop_count  = state.get("review_loop_count", 0)
        feedback    = state.get("code_review_feedback", "")
        fix_targets = state.get("fix_targets", []) or []
        test_ok     = state.get("test_results", {}).get("success", False)

        # ── 決定論的な escalate 判定 (Writer へ移行するか) ────────────────
        escalate = (
            test_ok
            or not fix_targets
            or loop_count >= self.max_loops
        )

        next_loop_count = loop_count + 1  # 単調増加 (リセットしない)

        if escalate:
            remaining_issues = ""
            # 上限到達かつ未解決の指摘が残る場合のみ残存課題を要約する
            if loop_count >= self.max_loops and feedback and not test_ok:
                decision: ReviewDecision = self._run_agent(
                    state,
                    ReviewDecision,
                    extra=[HumanMessage(content=(
                        f"レビューループが上限 ({self.max_loops}回) に達しました。"
                        "未解決の課題を remaining_issues に簡潔にまとめてください。"
                        "fix_instructions は空で構いません。\n\n"
                        f"レビュー指摘:\n{feedback}"
                    ))],
                )
                remaining_issues = decision.remaining_issues or (
                    f"[ループ上限到達 ({loop_count}/{self.max_loops})] {feedback[:500]}"
                )
            return {
                "messages":          [AIMessage(content=f"[review_manager] → writer (loop={next_loop_count})")],
                "fix_instructions":  {},
                "review_loop_count": next_loop_count,
                "remaining_issues":  remaining_issues,
                "next":              "writer",
            }

        # ── 修正ループ継続: 各ワーカーへの修正指示を生成 ─────────────────
        decision = self._run_agent(
            state,
            ReviewDecision,
            extra=[HumanMessage(content=(
                f"修正が必要なワーカー: {fix_targets}\n"
                "各ワーカーに対し、どのファイルの何を・どのように直すかを明示した"
                "fix_instructions を生成してください。\n\n"
                f"レビュー指摘:\n{feedback}"
            ))],
        )
        # 指示は fix_targets のワーカーに限定する
        fix_instructions = {
            agent: inst
            for agent, inst in decision.fix_instructions.items()
            if agent in fix_targets
        }
        # LLM が指示を返さなかったワーカーにはフィードバック全文をフォールバック
        for agent in fix_targets:
            fix_instructions.setdefault(agent, feedback)

        return {
            "messages":          [AIMessage(content=f"[review_manager] → fix {fix_targets} (loop={next_loop_count})")],
            "fix_instructions":  fix_instructions,
            "review_loop_count": next_loop_count,
            "remaining_issues":  "",
            "next":              "fix",
        }
