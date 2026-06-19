"""
Entry point for the UpWork multi-agent RAG system.
ユーザーから案件仕様 (自然言語) を受け取り、
バックエンド / フロントエンド / 両方のエージェントへ振り分けて納品物を生成する。
"""

from __future__ import annotations

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

from agents.nodes.analysis_node import AnalysisNode
from agents.nodes.backend_node import BackendNode
from agents.nodes.frontend_node import FrontendNode
from agents.nodes.search_node import SearchNode
from agents.nodes.supervisor_node import SupervisorNode
from agents.nodes.writer_node import WriterNode
from config.settings import settings
from graph.workflow import AgentState, MultiAgentWorkflow
from rag.retriever import Retriever
from rag.vector_store import VectorStore


def build_app():
    """全コンポーネントを組み立ててコンパイル済みグラフを返す。"""

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
    supervisor = SupervisorNode(llm=llm)
    search     = SearchNode(llm=llm, retriever=retriever)
    analysis   = AnalysisNode(llm=llm)
    backend    = BackendNode(llm=llm)
    frontend   = FrontendNode(llm=llm)
    writer     = WriterNode(llm=llm)

    # ── グラフ ────────────────────────────────────────────────────────
    workflow = MultiAgentWorkflow(
        supervisor_node=supervisor,
        search_node=search,
        analysis_node=analysis,
        backend_node=backend,
        frontend_node=frontend,
        writer_node=writer,
    )
    return workflow.compile()


def run(spec: str) -> str:
    """
    UpWork案件仕様 (自然言語) を受け取り、納品物を返す。

    Parameters
    ----------
    spec : クライアントから受け取った仕様テキスト

    Returns
    -------
    final_answer : UpWork提出フォーマットの納品物文字列
    """
    app = build_app()

    initial_state: AgentState = {
        "messages":        [HumanMessage(content=spec)],
        "user_spec":       spec,
        "task_type":       "",
        "next":            "",
        "retrieved_docs":  [],
        "analysis_result": "",
        "backend_result":  "",
        "frontend_result": "",
        "final_answer":    "",
    }

    final_state = app.invoke(initial_state)
    return final_state.get("final_answer", "")


if __name__ == "__main__":
    import sys

    spec = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else (
        "FastAPIを使ったTODO管理APIとReactのフロントエンドを作成してください。"
        "ユーザー認証 (JWT)・CRUD操作・PostgreSQL対応が必要です。"
    )

    print("=== UpWork Multi-Agent System ===")
    print(f"仕様: {spec}\n")
    result = run(spec)
    print(result)
