"""
WorkerNode — 実装ワーカー (backend / frontend / database / tool_specialist) の共通基底。

全ワーカーは「指示を受け取り dict[str, str] (ファイルパス → コード) を生成する」点で
共通なので、生成ロジックをここに集約する。各ワーカーは output_field を指定するだけでよい。

重要 (並列実行時の安全性):
  ワーカーは Send API で並列実行されるため、各ノードは「自分の出力フィールド」と
  messages だけを返す。state 全体を返すと、複数ワーカーが同一チャネルへ同時書き込みを
  行い LangGraph が InvalidUpdateError を送出する。
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage

from agents.Agent_Node import AgentNode
from agents.schemas import FileSet


class WorkerNode(AgentNode):
    """実装ワーカーの基底クラス。サブクラスは output_field を定義する。"""

    #: このワーカーが書き込む AgentState のフィールド名 (例: "backend_files")
    output_field: str = ""

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        指示に従い成果物を生成する。
        修正指示 (fix_instructions[node_name]) があれば既存ファイルへ上書きマージする。
        """
        if not self.output_field:
            raise NotImplementedError(
                f"{type(self).__name__} は output_field を定義する必要があります"
            )

        existing: dict[str, str] = state.get(self.output_field) or {}
        fix_inst = state.get("fix_instructions", {}).get(self.node_name)

        result: FileSet = self._generate(state, FileSet)

        if fix_inst and existing:
            # 修正ループ: 変更されたファイルを既存成果物に上書きマージ
            files = {**existing, **result.files}
            mode = "fix"
        else:
            files = result.files
            mode = "create"

        summary = f"[{self.node_name}/{mode}] {len(files)} ファイル生成"
        if result.notes:
            summary += f" — {result.notes[:200]}"

        return {
            "messages": [AIMessage(content=summary)],
            self.output_field: files,
        }
