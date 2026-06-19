"""
ContextManager — メッセージ履歴の肥大化を防ぐユーティリティ。

【設計原則】
  - コード成果物 (*_files) は AgentState の専用フィールドに格納し、
    messages には含めない。
  - messages にはオーケストレーション用の短いメッセージのみを保持する。
  - messages が max_messages を超えたら古いものをトリムする。
  - 成果物のサマリー (ファイル名リスト) だけを LLM コンテキストに渡す。
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage


class ContextManager:
    """メッセージとアーティファクトのコンテキスト管理。"""

    def __init__(self, max_messages: int = 20) -> None:
        self.max_messages = max_messages

    # ------------------------------------------------------------------
    # Message trimming
    # ------------------------------------------------------------------

    def trim(self, messages: list[BaseMessage]) -> list[BaseMessage]:
        """
        messages が max_messages を超えたら古いメッセージを削除する。
        SystemMessage (index 0) は常に保持する。
        """
        if len(messages) <= self.max_messages:
            return messages
        system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
        other_msgs  = [m for m in messages if not isinstance(m, SystemMessage)]
        keep = other_msgs[-(self.max_messages - len(system_msgs)):]
        return system_msgs + keep

    # ------------------------------------------------------------------
    # Artifact summary (コードを messages に載せない代わりに一覧を渡す)
    # ------------------------------------------------------------------

    @staticmethod
    def artifact_summary(state: dict[str, Any]) -> str:
        """
        各エージェントの成果物ファイル一覧を短いテキストにまとめる。
        フルコードは含めず、ファイルパスと行数だけを示す。
        """
        sections: list[str] = []

        def _fmt(label: str, files: dict[str, str]) -> None:
            if not files:
                return
            entries = [
                f"  {path} ({len(code.splitlines())}行)"
                for path, code in files.items()
            ]
            sections.append(f"[{label}]\n" + "\n".join(entries))

        _fmt("ToolSpecialist", state.get("tool_spec_files",  {}))
        _fmt("Backend",        state.get("backend_files",    {}))
        _fmt("Frontend",       state.get("frontend_files",   {}))
        _fmt("Database",       state.get("database_files",   {}))

        if state.get("test_results"):
            tr = state["test_results"]
            sections.append(
                f"[TestRunner] passed={tr.get('passed', 0)} "
                f"failed={tr.get('failed', 0)} "
                f"coverage={tr.get('coverage', 'N/A')}"
            )

        if state.get("code_review_feedback"):
            sections.append(f"[CodeReview] {state['code_review_feedback'][:200]}...")

        return "\n\n".join(sections) if sections else "成果物なし"

    # ------------------------------------------------------------------
    # Context builder for agent invocation
    # ------------------------------------------------------------------

    def build_context_message(self, state: dict[str, Any]) -> HumanMessage:
        """
        現在のステートから LLM に渡す簡潔なコンテキストメッセージを生成する。
        フルコードではなくサマリーのみを含める。
        """
        parts: list[str] = []

        if state.get("user_spec"):
            parts.append(f"【クライアント仕様】\n{state['user_spec']}")

        if state.get("work_plan"):
            parts.append(f"【作業計画】\n{state['work_plan'][:500]}...")

        instructions = state.get("agent_instructions", {})
        if instructions:
            node_name = state.get("_current_node", "")
            if node_name and node_name in instructions:
                parts.append(f"【あなたへの指示】\n{instructions[node_name]}")

        fix_instructions = state.get("fix_instructions", {})
        if fix_instructions:
            node_name = state.get("_current_node", "")
            if node_name and node_name in fix_instructions:
                parts.append(f"【修正指示】\n{fix_instructions[node_name]}")

        summary = self.artifact_summary(state)
        if summary != "成果物なし":
            parts.append(f"【現在の成果物一覧】\n{summary}")

        if state.get("review_loop_count", 0) > 0:
            parts.append(
                f"【レビューループ】 {state['review_loop_count']} / "
                f"{state.get('_max_review_loops', 2)} 回目"
            )

        return HumanMessage(content="\n\n".join(parts))
