"""
Entry point for the UpWork multi-agent system.

フロー:
  ユーザー仕様 + 報奨金
    → ProjectManager
        ① 報奨金からモデル割当を決定 (利益最大化)
        ② 仕様解析・担当割当・指示生成
        ③ Human-in-the-loop (interrupt)
    → [Backend | Frontend | Database | ToolSpecialist] (割当モデルで並列実装)
    → TestRunner (pytest / ruff / mypy — 常に Haiku)
    → CodeReview (横断レビュー + テスト結果評価)
    → ReviewManager (修正ループ制御)
    → Writer (UpWork納品物整形)
"""

from __future__ import annotations

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from agents.nodes.backend_node import BackendNode
from agents.nodes.code_review_node import CodeReviewNode
from agents.nodes.database_node import DatabaseNode
from agents.nodes.frontend_node import FrontendNode
from agents.nodes.project_manager_node import ProjectManagerNode
from agents.nodes.review_manager_node import ReviewManagerNode
from agents.nodes.test_runner_node import TestRunnerNode
from agents.nodes.tool_specialist_node import ToolSpecialistNode
from agents.nodes.writer_node import WriterNode
from config.model_selector import ModelSelector
from config.settings import settings
from graph.workflow import AgentState, MultiAgentWorkflow


def _make_llm_factory(base_llm: ChatAnthropic):
    """
    base_llm のパラメータを引き継ぎ、model_id だけ差し替えた
    新しい ChatAnthropic を返すファクトリ関数を生成する。
    AgentNode._get_bound_llm() から呼ばれる。
    """
    def factory(model_id: str) -> ChatAnthropic:
        return ChatAnthropic(
            model=model_id,
            temperature=base_llm.temperature,
            max_tokens=base_llm.max_tokens,
            api_key=base_llm.anthropic_api_key,
        )
    return factory


def build_app(use_human_in_loop: bool = True):
    """
    全コンポーネントを組み立ててコンパイル済みグラフを返す。

    Parameters
    ----------
    use_human_in_loop : True のとき MemorySaver を有効化して interrupt() を使用。
    """

    # ── デフォルト LLM (モデル選択前のフォールバック) ────────────────
    default_llm = ChatAnthropic(
        model=settings.llm.model,
        temperature=settings.llm.temperature,
        max_tokens=settings.llm.max_tokens,
        api_key=settings.anthropic_api_key,  # AWS Secrets Manager 経由
    )
    llm_factory = _make_llm_factory(default_llm)

    # ── エージェントノード (全ノードに llm_factory を渡す) ────────────
    project_manager = ProjectManagerNode(llm=default_llm, llm_factory=llm_factory)
    backend         = BackendNode(llm=default_llm, llm_factory=llm_factory)
    frontend        = FrontendNode(llm=default_llm, llm_factory=llm_factory)
    database        = DatabaseNode(llm=default_llm, llm_factory=llm_factory)
    tool_specialist = ToolSpecialistNode(llm=default_llm, llm_factory=llm_factory)
    test_runner     = TestRunnerNode(llm=default_llm, llm_factory=llm_factory)
    code_review     = CodeReviewNode(llm=default_llm, llm_factory=llm_factory)
    review_manager  = ReviewManagerNode(llm=default_llm, llm_factory=llm_factory)
    writer          = WriterNode(llm=default_llm, llm_factory=llm_factory)

    # ── グラフ ────────────────────────────────────────────────────────
    workflow = MultiAgentWorkflow(
        project_manager_node=project_manager,
        backend_node=backend,
        frontend_node=frontend,
        database_node=database,
        tool_specialist_node=tool_specialist,
        test_runner_node=test_runner,
        code_review_node=code_review,
        review_manager_node=review_manager,
        writer_node=writer,
    )

    checkpointer = MemorySaver() if use_human_in_loop else None
    return workflow.compile(checkpointer=checkpointer)


def run(spec: str, reward_amount: float = 0.0, thread_id: str = "default") -> str:
    """
    UpWork案件仕様と報奨金を受け取り、納品物を返す。

    Parameters
    ----------
    spec          : クライアントから受け取った仕様テキスト
    reward_amount : UpWork 報奨金 (USD)。モデル選択の基準。
                    例: 50.0 → SMART_SMALL、200.0 → SONNET_ALL
    thread_id     : Human-in-the-loop 再開用スレッドID
    """
    app = build_app(use_human_in_loop=True)
    config = {"configurable": {"thread_id": thread_id}}

    initial_state: AgentState = {
        "messages":             [HumanMessage(content=spec)],
        "user_spec":            spec,
        "reward_amount":        reward_amount,
        "work_plan":            "",
        "assigned_agents":      [],
        "agent_instructions":   {},
        "human_feedback":       "",
        "model_assignments":    {},
        "estimated_cost":       0.0,
        "estimated_profit":     0.0,
        "tool_spec_files":      {},
        "backend_files":        {},
        "frontend_files":       {},
        "database_files":       {},
        "test_results":         {},
        "code_review_feedback": "",
        "fix_targets":          [],
        "review_loop_count":    0,
        "fix_instructions":     {},
        "remaining_issues":     "",
        "next":                 "",
        "final_files":          {},
        "final_answer":         "",
    }

    final_state = app.invoke(initial_state, config=config)
    return final_state.get("final_answer", "")


if __name__ == "__main__":
    import sys

    spec = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else (
        "FastAPIとPostgreSQLを使ったTODO管理APIと"
        "ReactフロントエンドをTypeScriptで実装してください。"
        "JWT認証・CRUD操作・ページネーション対応が必要です。"
        "Docker Composeで一発起動できるようにしてください。"
    )
    reward = float(sys.argv[1]) if len(sys.argv) > 1 else 150.0

    print("=== UpWork Multi-Agent System ===")
    print(f"報奨金: ${reward:.2f}")
    print()
    print(ModelSelector.summarize(reward, settings.workflow.max_review_loops))
    print()
    print(f"仕様: {spec}\n")
    result = run(spec, reward_amount=reward)
    print(result)
