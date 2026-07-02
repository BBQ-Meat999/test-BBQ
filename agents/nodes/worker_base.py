"""
WorkerNode — 実装ワーカー (backend / frontend / database / tool_specialist) の共通基底。

全ワーカーは「指示を受け取り、write_file ツールでファイルを組み立てる」点で共通なので、
tool-use ループをここに集約する。各ワーカーは output_field を指定するだけでよい。

生成方式 (function calling):
  ワーカーは FileWorkspace にバインドされた write_file / read_file / list_files ツールを
  使い、LLM が能動的にファイルを書き出す。完了時に WorkerSubmission を呼ぶと、
  ワークスペースに蓄積されたファイルが成果物となる。

重要 (並列実行時の安全性):
  ワーカーは Send API で並列実行されるため、各ノードは「自分の出力フィールド」と
  messages だけを返す。state 全体を返すと、複数ワーカーが同一チャネルへ同時書き込みを
  行い LangGraph が InvalidUpdateError を送出する。
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage

from agents.Agent_Node import AgentNode
from agents.schemas import WorkerSubmission
from agents.tools import FileWorkspace


class WorkerNode(AgentNode):
    """実装ワーカーの基底クラス。サブクラスは output_field を定義する。"""

    #: このワーカーが書き込む AgentState のフィールド名 (例: "backend_files")
    output_field: str = ""

    def _peer_artifacts(self, state: dict[str, Any]) -> dict[str, str]:
        """read_file で参照できる既存/他ワーカーの成果物を集める (自分の分は除く)。"""
        peers: dict[str, str] = {}
        for key in ("tool_spec_files", "backend_files", "frontend_files", "database_files"):
            if key == self.output_field:
                continue
            peers.update(state.get(key) or {})
        return peers

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        write_file ツールで成果物を組み立てる。
        修正指示 (fix_instructions[node_name]) があれば既存ファイルを初期状態として渡し、
        LLM が read_file → write_file で上書き修正する。
        """
        if not self.output_field:
            raise NotImplementedError(
                f"{type(self).__name__} は output_field を定義する必要があります"
            )

        existing: dict[str, str] = state.get(self.output_field) or {}
        fix_inst = state.get("fix_instructions", {}).get(self.node_name)
        is_fix = bool(fix_inst and existing)

        # 修正ループ時は既存成果物をワークスペースに載せて上書き修正させる
        workspace = FileWorkspace(
            initial=dict(existing) if is_fix else None,
            readonly_peers=self._peer_artifacts(state),
        )

        submission: WorkerSubmission = self._run_agent(
            state,
            WorkerSubmission,
            tools=workspace.as_tools(include_write=True),
        )

        files = workspace.files
        mode = "fix" if is_fix else "create"
        summary = f"[{self.node_name}/{mode}] {len(files)} ファイル生成"
        if submission.notes:
            summary += f" — {submission.notes[:200]}"

        return {
            "messages": [AIMessage(content=summary)],
            self.output_field: files,
        }
