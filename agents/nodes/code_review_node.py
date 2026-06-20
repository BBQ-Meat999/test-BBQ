"""
CodeReviewNode — 全エージェントの生成コードと TestRunner 結果を横断レビューする。

dict[str, str] 形式の多ファイル成果物のフルコードと、TestRunner の実行結果を受け取り、
品質・整合性・セキュリティ (OWASP 観点)・テスト結果を統合評価する。
結果は code_review_feedback (要約) と fix_targets (修正対象ワーカー) に格納する。
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from agents.Agent_Node import AgentNode
from agents.schemas import ReviewResult

ASSIGNABLE_AGENTS = ["backend", "frontend", "database", "tool_specialist"]


class CodeReviewNode(AgentNode):
    """コードレビュー専門エージェント。"""

    node_name = "code_review"

    def _test_results_message(self, state: dict[str, Any]) -> HumanMessage:
        tr = state.get("test_results", {}) or {}
        return HumanMessage(content=(
            "【TestRunner 実行結果】\n"
            f"  pytest: passed={tr.get('passed', 0)} "
            f"failed={tr.get('failed', 0)} errors={tr.get('errors', 0)} "
            f"success={tr.get('success', False)}\n"
            f"  ruff_clean={tr.get('ruff', {}).get('clean')}  "
            f"mypy_clean={tr.get('mypy', {}).get('clean')}\n"
            f"  pytest出力(末尾):\n{tr.get('output', '')[:1500]}"
        ))

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """全成果物と TestRunner 結果をレビューし feedback / fix_targets を更新する。"""
        extra = [self._full_artifacts_message(state), self._test_results_message(state)]
        result: ReviewResult = self._generate(state, ReviewResult, extra=extra)

        fix_targets = [t for t in result.fix_targets if t in ASSIGNABLE_AGENTS]

        # テストが失敗しているのにレビューが「問題なし」と返した場合の安全網
        test_ok = state.get("test_results", {}).get("success", False)
        if not test_ok and not fix_targets:
            fix_targets = list(ASSIGNABLE_AGENTS)

        return {
            "messages":             [AIMessage(content=f"[code_review] passed={result.passed} fix_targets={fix_targets}")],
            "code_review_feedback": result.summary,
            "fix_targets":          fix_targets,
        }
