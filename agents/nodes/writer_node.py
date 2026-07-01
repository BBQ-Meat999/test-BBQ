"""
WriterNode — UpWork 納品物を整形・統合して最終回答を生成する。

全ワーカーの dict[str, str] 成果物を統合し、README・引き渡しドキュメントを生成して
クライアントへ提出できる完成品パッケージにまとめる。
残存課題 (remaining_issues) がある場合は納品物に注記する。
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage

from agents.Agent_Node import AgentNode
from agents.schemas import Delivery
from agents.tools import FileWorkspace


class WriterNode(AgentNode):
    """UpWork 納品物アセンブラー。"""

    node_name = "writer"

    @staticmethod
    def _merge_files(state: dict[str, Any]) -> dict[str, str]:
        """全ワーカーの成果物を統合する (パス衝突は後勝ち)。"""
        merged: dict[str, str] = {}
        for key in ("tool_spec_files", "backend_files", "frontend_files", "database_files"):
            merged.update(state.get(key) or {})
        return merged

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """全成果物を統合して final_files と final_answer を生成する。"""
        merged = self._merge_files(state)

        # read_file / list_files で各成果物を精査してから納品物を執筆できるようにする
        workspace = FileWorkspace(readonly_peers=merged)
        delivery: Delivery = self._run_agent(
            state,
            Delivery,
            extra=[self._full_artifacts_message(state)],
            tools=workspace.as_tools(include_write=False),
        )

        final_files = dict(merged)
        final_files["README.md"]   = delivery.readme
        final_files["HANDOVER.md"] = delivery.handover

        return {
            "messages":     [AIMessage(content=f"[writer] 納品物確定 ({len(final_files)} ファイル)")],
            "final_files":  final_files,
            "final_answer": delivery.summary,
        }
