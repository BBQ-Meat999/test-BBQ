"""
ReviewManagerNode — コードレビュー結果を受け取り修正ループを制御するマネージャー。

CodeReviewNode からのフィードバックを解釈し、
各実装エージェントへ具体的な修正指示を送る。
ループ上限は config.settings.workflow.max_review_loops で管理する。
(MAX_REVIEW_LOOPS をこのファイルに定義すると config/systemMessage.py との
 循環インポートが発生するため、settings に移動済み)
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from agents.Agent_Node import AgentNode
from config.settings import settings


class ReviewManagerNode(AgentNode):
    """
    レビューマネージャー。

    責務:
      1. CodeReview のフィードバックを優先度付きで整理する
      2. 修正が必要なエージェントを特定し、具体的な修正指示文を生成する
      3. ループカウントを管理し max_review_loops を超えたら Writer へ移行する
      4. 軽微な問題はそのまま Writer へ渡して最終成果物に注記する
    """

    node_name = "review_manager"

    @property
    def max_loops(self) -> int:
        return settings.workflow.max_review_loops

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @tool
    def prioritize_issues(self, feedback: str, test_results: dict) -> list[dict[str, Any]]:
        """
        コードレビューの指摘とテスト結果を重要度順にソートする。
        Returns:
            [{"priority": "critical"|"high"|"medium"|"low",
              "target_agent": str,
              "description": str,
              "action_required": str}]
        """
        ...

    @tool
    def generate_fix_instruction(
        self,
        target_agent: str,
        issues: list[dict[str, Any]],
        current_files: dict[str, str],
    ) -> str:
        """
        特定エージェント向けの具体的な修正指示文を生成する。
        何を・どのファイルの何行目を・どのように直すかを明確に記述する。
        """
        ...

    @tool
    def should_escalate(self, feedback: str, test_success: bool, loop_count: int) -> bool:
        """
        ループ上限到達・問題解消・テスト全通過のいずれかで True を返す (Writer へ移行)。
        """
        return (
            loop_count >= self.max_loops
            or (not feedback.strip())
            or test_success
        )

    @tool
    def summarize_remaining_issues(self, feedback: str, loop_count: int) -> str:
        """
        ループ上限到達時に残存する未解決問題をサマリー化する。
        Writer が最終成果物の注記として使用する。
        """
        ...

    # ------------------------------------------------------------------
    # Node entry point
    # ------------------------------------------------------------------

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        レビュー結果を解釈して修正指示を生成するか、Writer への移行を決定する。
        """
        response   = self._invoke(state)
        loop_count = state.get("review_loop_count", 0)
        feedback   = state.get("code_review_feedback", "")
        fix_targets = state.get("fix_targets", [])
        test_ok    = state.get("test_results", {}).get("success", False)

        # TODO: should_escalate ツール呼び出し結果で判断する
        escalate: bool = (
            loop_count >= self.max_loops
            or not fix_targets
            or test_ok
        )

        # TODO: 各 fix_target 向けに generate_fix_instruction を呼ぶ
        fix_instructions: dict[str, str] = {}

        remaining_issues = ""
        if escalate and loop_count >= self.max_loops and feedback:
            # TODO: summarize_remaining_issues を呼ぶ
            remaining_issues = f"[ループ上限到達 ({loop_count}/{self.max_loops})] {feedback[:500]}"

        return {
            **state,
            "messages":          state["messages"] + [response],
            "fix_instructions":  fix_instructions,
            "review_loop_count": 0 if escalate else loop_count + 1,
            "remaining_issues":  remaining_issues,
            "next":              "writer" if escalate else "fix",
        }
