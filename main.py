"""
Entry point for the UpWork multi-agent RAG system.

フロー:
  ユーザー仕様 (自然言語)
    → ProjectManager (仕様解析・担当割当・指示生成 / Human-in-the-loop)
    → [Backend | Frontend | Database | ToolSpecialist] (並列実装)
    → TestRunner (pytest / ruff / mypy)
    → CodeReview (横断レビュー + テスト結果評価)
    → ReviewManager (修正ループ制御 / 最大 max_review_loops 回)
    → Writer (UpWork納品物整形)
"""

from __future__ import annotations

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from agents.nodes.analysis_node import AnalysisNode
from agents.nodes.backend_node import BackendNode
from agents.nodes.code_review_node import CodeReviewNode
from agents.nodes.database_node import DatabaseNode
from agents.nodes.frontend_node import FrontendNode
from agents.nodes.project_manager_node import ProjectManagerNode
from agents.nodes.review_manager_node import ReviewManagerNode
from agents.nodes.search_node import SearchNode
from agents.nodes.test_runner_node import TestRunnerNode
from agents.nodes.tool_specialist_node import ToolSpecialistNode
from agents.nodes.writer_node import WriterNode
from config.settings import settings
from graph.workflow import AgentState, MultiAgentWorkflow
from rag.retriever import Retriever


def build_app(use_human_in_loop: bool = True):
    """
    全コンポーネントを組み立ててコンパイル済みグラフを返す。

    Parameters
    ----------
    use_human_in_loop : True (default) のとき MemorySaver を有効化して
                        interrupt() による Human-in-the-loop を使用する。
    """

    # ── LLM ─────────────────────────────────────────────────────────
    llm = ChatAnthropic(
        model=settings.llm.model,
        temperature=settings.llm.temperature,
        max_tokens=settings.llm.max_tokens,
        api_key=settings.anthropic_api_key,  # AWS Secrets Manager 経由
    )

    # ── RAG スタック ─────────────────────────────────────────────────
    # vector_store = VectorStore(backend=<FAISS / Chroma / Pinecone>)
    # retriever    = Retriever(vector_store=vector_store, default_top_k=settings.rag.top_k)
    retriever: Retriever = ...  # TODO: バックエンドを差し込む

    # ── エージェントノード ────────────────────────────────────────────
    project_manager = ProjectManagerNode(llm=llm)
    backend         = BackendNode(llm=llm)
    frontend        = FrontendNode(llm=llm)
    database        = DatabaseNode(llm=llm)
    tool_specialist = ToolSpecialistNode(llm=llm)
    test_runner     = TestRunnerNode(llm=llm)
    search          = SearchNode(llm=llm, retriever=retriever)
    analysis        = AnalysisNode(llm=llm)
    code_review     = CodeReviewNode(llm=llm)
    review_manager  = ReviewManagerNode(llm=llm)
    writer          = WriterNode(llm=llm)

    # ── グラフ ────────────────────────────────────────────────────────
    workflow = MultiAgentWorkflow(
        project_manager_node=project_manager,
        backend_node=backend,
        frontend_node=frontend,
        database_node=database,
        tool_specialist_node=tool_specialist,
        test_runner_node=test_runner,
        search_node=search,
        analysis_node=analysis,
        code_review_node=code_review,
        review_manager_node=review_manager,
        writer_node=writer,
    )

    checkpointer = MemorySaver() if use_human_in_loop else None
    return workflow.compile(checkpointer=checkpointer)


def run(spec: str, thread_id: str = "default") -> str:
    """
    UpWork案件仕様 (自然言語) を受け取り、納品物を返す。

    Human-in-the-loop が有効な場合、ProjectManager の作業計画確認で
    interrupt() が発火する。`thread_id` を指定して再開できる。

    Parameters
    ----------
    spec      : クライアントから受け取った仕様テキスト
    thread_id : Human-in-the-loop 再開用スレッドID

    Returns
    -------
    final_answer : UpWork提出フォーマットの納品物文字列
    """
    app = build_app(use_human_in_loop=True)

    config = {"configurable": {"thread_id": thread_id}}

    initial_state: AgentState = {
        "messages":            [HumanMessage(content=spec)],
        "user_spec":           spec,
        "work_plan":           "",
        "assigned_agents":     [],
        "agent_instructions":  {},
        "human_feedback":      "",
        "tool_spec_files":     {},
        "backend_files":       {},
        "frontend_files":      {},
        "database_files":      {},
        "retrieved_docs":      [],
        "analysis_result":     "",
        "test_results":        {},
        "code_review_feedback": "",
        "fix_targets":         [],
        "review_loop_count":   0,
        "fix_instructions":    {},
        "remaining_issues":    "",
        "next":                "",
        "final_files":         {},
        "final_answer":        "",
    }

    final_state = app.invoke(initial_state, config=config)
    return final_state.get("final_answer", "")


if __name__ == "__main__":
    import sys

    spec = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else (
        "FastAPIとPostgreSQLを使ったTODO管理APIと"
        "ReactフロントエンドをTypeScriptで実装してください。"
        "JWT認証・CRUD操作・ページネーション対応が必要です。"
        "Docker Composeで一発起動できるようにしてください。"
    )

    print("=== UpWork Multi-Agent System ===")
    print(f"レビューループ上限: {settings.workflow.max_review_loops} 回")
    print(f"Human-in-the-loop: {settings.workflow.require_plan_approval}")
    print(f"仕様: {spec}\n")
    result = run(spec)
    print(result)
