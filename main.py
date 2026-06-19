"""
Entry point for the multi-agent RAG system.
Wires dependencies together and runs the compiled LangGraph workflow.
"""

from __future__ import annotations

from langchain_anthropic import ChatAnthropic

from agents.nodes.analysis_node import AnalysisNode
from agents.nodes.search_node import SearchNode
from agents.nodes.supervisor_node import SupervisorNode
from agents.nodes.writer_node import WriterNode
from config.settings import settings
from graph.workflow import MultiAgentWorkflow
from rag.retriever import Retriever
from rag.vector_store import VectorStore


def build_app():
    """Instantiate all components and return a compiled LangGraph app."""

    # LLM
    llm = ChatAnthropic(
        model=settings.llm.model,
        temperature=settings.llm.temperature,
        max_tokens=settings.llm.max_tokens,
    )

    # RAG stack (backends are injected — swap without code changes)
    # vector_store = VectorStore(backend=<your backend>)
    # retriever = Retriever(vector_store=vector_store, default_top_k=settings.rag.top_k)
    retriever: Retriever = ...  # TODO: wire concrete backend

    # Agent nodes
    supervisor = SupervisorNode(llm=llm)
    search     = SearchNode(llm=llm, retriever=retriever)
    analysis   = AnalysisNode(llm=llm)
    writer     = WriterNode(llm=llm)

    # Graph
    workflow = MultiAgentWorkflow(
        supervisor_node=supervisor,
        search_node=search,
        analysis_node=analysis,
        writer_node=writer,
    )
    return workflow.compile()


def run(query: str) -> str:
    """Run the multi-agent workflow for a single user query."""
    from langchain_core.messages import HumanMessage

    app = build_app()
    initial_state = {
        "messages":       [HumanMessage(content=query)],
        "next":           "",
        "retrieved_docs": [],
        "analysis_result": "",
        "final_answer":   "",
    }
    final_state = app.invoke(initial_state)
    return final_state.get("final_answer", "")


if __name__ == "__main__":
    import sys
    query = " ".join(sys.argv[1:]) or "What is retrieval-augmented generation?"
    answer = run(query)
    print(answer)
