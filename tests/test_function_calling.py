"""
function calling (tool-use) ループの単体テスト。

実際の Anthropic 呼び出しは行わず、スクリプト化した Fake チャットモデルで
Agent_Node._run_agent の動作を検証する:
  - 実行可能ツール (write_file) が実際に呼ばれ、ワークスペースへ反映される
  - submit 関数 (結果スキーマ) の引数が Pydantic へ検証されて返る
  - ワーカーノードが tool-use で成果物 dict を組み立てられる
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage

from agents.nodes.backend_node import BackendNode
from agents.schemas import WorkerSubmission, WorkPlan
from agents.tools import FileWorkspace


class FakeToolModel:
    """
    bind_tools/invoke をエミュレートする Fake モデル。

    `script` は「invoke 1 回ごとに返す tool_calls のリスト」を並べたもの。
    bind_tools は自身を返し (tool_choice は無視)、invoke は script を順に消費する。
    """

    def __init__(self, script: list[list[dict[str, Any]]]) -> None:
        self._script = script
        self._i = 0
        self.bound_tools: list[Any] | None = None

    def bind_tools(self, tools: list[Any], **_: Any) -> FakeToolModel:
        self.bound_tools = tools
        return self

    def invoke(self, _messages: list[BaseMessage]) -> AIMessage:
        calls = self._script[self._i]
        self._i += 1
        return AIMessage(content="", tool_calls=[
            {"name": c["name"], "args": c["args"], "id": f"call_{i}"}
            for i, c in enumerate(calls)
        ])


def test_workspace_write_and_read() -> None:
    ws = FileWorkspace(readonly_peers={"peer.py": "x = 1\n"})
    assert ws.write_file("src/app.py", "print('hi')\n").startswith("OK")
    assert ws.files["src/app.py"] == "print('hi')\n"
    assert ws.read_file("peer.py") == "x = 1\n"
    assert "存在しません" in ws.read_file("missing.py")
    # 不正パスは拒否
    assert ws.write_file("/etc/passwd", "x").startswith("ERROR")
    assert ws.write_file("../escape.py", "x").startswith("ERROR")


def test_run_agent_forced_submit() -> None:
    """決定系ノード: submit 関数を 1 回呼ぶだけで結果が返る。"""
    fake = FakeToolModel(script=[[
        {"name": "WorkPlan", "args": {
            "work_plan": "# Plan\n手順...",
            "assigned_agents": ["backend"],
            "agent_instructions": {"backend": "API を作る"},
        }},
    ]])
    node = BackendNode(llm=fake)  # type: ignore[arg-type]
    result = node._run_agent({"model_assignments": {}}, WorkPlan)
    assert isinstance(result, WorkPlan)
    assert result.assigned_agents == ["backend"]
    # tool_choice 強制のため submit スキーマがバインドされている
    assert WorkPlan in (fake.bound_tools or [])


def test_worker_tool_loop_builds_files() -> None:
    """ワーカー: write_file を 2 回 → WorkerSubmission で完了。"""
    script = [
        [{"name": "write_file", "args": {"path": "app.py", "content": "print(1)\n"}}],
        [{"name": "write_file", "args": {"path": "test_app.py", "content": "def test(): assert True\n"}}],
        [{"name": "WorkerSubmission", "args": {"notes": "done"}}],
    ]
    fake = FakeToolModel(script=script)
    node = BackendNode(llm=fake)  # type: ignore[arg-type]
    out = node.run({
        "model_assignments": {},
        "agent_instructions": {"backend": "実装せよ"},
        "backend_files": {},
    })
    files = out["backend_files"]
    assert set(files) == {"app.py", "test_app.py"}
    assert files["app.py"] == "print(1)\n"
    assert "2 ファイル生成" in out["messages"][0].content


def test_worker_submission_schema_default() -> None:
    assert WorkerSubmission().notes == ""
