"""
diagram_spec.py — システム全体のグラフ構造を定義する単一の情報源。

【更新ルール】
  システムにノード・エッジ・ステートフィールドを追加・変更したときは
  必ずこのファイルも更新し、以下のコマンドで図を再生成すること:

      python tools/generate_diagram.py

生成先: docs/architecture.md
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# バージョン管理
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_VERSION = "1.5.0"
SYSTEM_NAME    = "UpWork Multi-Agent RAG System"

# ─────────────────────────────────────────────────────────────────────────────
# ノード定義
# ─────────────────────────────────────────────────────────────────────────────
# layer: "management" | "worker" | "quality" | "rag" | "delivery"

NODES: list[dict] = [
    # Management
    {
        "id":    "project_manager",
        "label": "ProjectManager",
        "layer": "management",
        "role":  "仕様解析・作業計画・担当割当・指示生成 / Human-in-the-loop (interrupt)",
        "tools": [
            "parse_requirements",
            "create_work_plan",
            "assign_agents",
            "incorporate_human_feedback",
        ],
    },
    {
        "id":    "review_manager",
        "label": "ReviewManager",
        "layer": "management",
        "role":  "レビュー結果解析・修正指示生成・ループ制御 (最大 max_review_loops 回)",
        "tools": [
            "prioritize_issues",
            "generate_fix_instruction",
            "should_escalate",
            "summarize_remaining_issues",
        ],
    },
    # Workers
    {
        "id":    "backend",
        "label": "BackendNode",
        "layer": "worker",
        "role":  "Python / FastAPI / pytest → backend_files: dict[str, str]",
        "tools": [
            "design_api",
            "write_python_code",
            "write_tests",
            "write_requirements",
            "generate_dockerfile",
            "apply_fix",
        ],
    },
    {
        "id":    "frontend",
        "label": "FrontendNode",
        "layer": "worker",
        "role":  "React / TypeScript / CSS → frontend_files: dict[str, str]",
        "tools": [
            "design_ui",
            "write_html_css",
            "write_javascript",
            "generate_components",
            "integrate_api",
            "generate_build_config",
            "apply_fix",
        ],
    },
    {
        "id":    "database",
        "label": "DatabaseNode",
        "layer": "worker",
        "role":  "SQLAlchemy / Alembic / ERD → database_files: dict[str, str]",
        "tools": [
            "design_erd",
            "generate_sqlalchemy_models",
            "generate_alembic_migration",
            "generate_repository",
            "optimize_queries",
            "generate_seed_data",
            "generate_db_config",
            "apply_fix",
        ],
    },
    {
        "id":    "tool_specialist",
        "label": "ToolSpecialistNode",
        "layer": "worker",
        "role":  "共有ユーティリティ実装 → tool_spec_files: dict[str, str]",
        "tools": [
            "analyze_utility_requirements",
            "implement_utility",
            "generate_error_handling",
            "generate_logging_config",
            "generate_validation_utils",
            "apply_fix",
        ],
    },
    # Quality Gate
    {
        "id":    "test_runner",
        "label": "TestRunnerNode",
        "layer": "quality",
        "role":  "pytest / ruff / mypy 自動実行 → test_results: dict",
        "tools": [
            "write_files_to_tempdir",
            "run_pytest",
            "run_ruff_check",
            "run_mypy",
        ],
    },
    {
        "id":    "code_review",
        "label": "CodeReviewNode",
        "layer": "quality",
        "role":  "品質・整合性・セキュリティ横断レビュー + テスト結果評価",
        "tools": [
            "review_files",
            "evaluate_test_results",
            "check_cross_consistency",
            "check_security",
            "identify_fix_targets",
            "generate_feedback_summary",
        ],
    },
    # RAG
    {
        "id":    "search",
        "label": "SearchNode",
        "layer": "rag",
        "role":  "ベクトル検索 / キーワード検索",
        "tools": [
            "semantic_search",
            "keyword_search",
        ],
    },
    {
        "id":    "analysis",
        "label": "AnalysisNode",
        "layer": "rag",
        "role":  "技術スタック分析 / 要件抽出",
        "tools": [
            "summarize",
            "extract_facts",
            "compare",
        ],
    },
    # Delivery
    {
        "id":    "writer",
        "label": "WriterNode",
        "layer": "delivery",
        "role":  "UpWork納品物整形・品質チェック・ドキュメント生成",
        "tools": [
            "merge_all_files",
            "write_readme",
            "write_handover_doc",
            "quality_check",
            "format_for_upwork",
        ],
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# エッジ定義
# ─────────────────────────────────────────────────────────────────────────────
# kind: "normal" | "conditional" | "send_parallel" | "optional"

EDGES: list[dict] = [
    # Entry
    {"from": "START",           "to": "project_manager",  "label": "",                              "kind": "normal"},
    # PM → Workers (interrupt() 承認後 / Send API 並列)
    {"from": "project_manager", "to": "backend",          "label": "interrupt() 承認後 / Send API", "kind": "send_parallel"},
    {"from": "project_manager", "to": "frontend",         "label": "interrupt() 承認後 / Send API", "kind": "send_parallel"},
    {"from": "project_manager", "to": "database",         "label": "interrupt() 承認後 / Send API", "kind": "send_parallel"},
    {"from": "project_manager", "to": "tool_specialist",  "label": "interrupt() 承認後 / Send API", "kind": "send_parallel"},
    # Workers → TestRunner (収束)
    {"from": "backend",         "to": "test_runner",      "label": "実装完了",                      "kind": "normal"},
    {"from": "frontend",        "to": "test_runner",      "label": "実装完了",                      "kind": "normal"},
    {"from": "database",        "to": "test_runner",      "label": "実装完了",                      "kind": "normal"},
    {"from": "tool_specialist", "to": "test_runner",      "label": "実装完了",                      "kind": "normal"},
    # TestRunner → CodeReview
    {"from": "test_runner",     "to": "code_review",      "label": "テスト結果",                    "kind": "normal"},
    # CodeReview → ReviewManager
    {"from": "code_review",     "to": "review_manager",   "label": "フィードバック",                "kind": "normal"},
    # ReviewManager → Workers (修正ループ / Send API)
    {"from": "review_manager",  "to": "backend",          "label": "修正指示 (loop<max)",           "kind": "send_parallel"},
    {"from": "review_manager",  "to": "frontend",         "label": "修正指示 (loop<max)",           "kind": "send_parallel"},
    {"from": "review_manager",  "to": "database",         "label": "修正指示 (loop<max)",           "kind": "send_parallel"},
    {"from": "review_manager",  "to": "tool_specialist",  "label": "修正指示 (loop<max)",           "kind": "send_parallel"},
    # ReviewManager → Writer (終了条件)
    {"from": "review_manager",  "to": "writer",           "label": "問題なし or loop≥max",          "kind": "conditional"},
    # RAG (オプション)
    {"from": "project_manager", "to": "search",           "label": "RAG検索 (任意)",                "kind": "optional"},
    {"from": "search",          "to": "analysis",         "label": "",                              "kind": "optional"},
    {"from": "analysis",        "to": "project_manager",  "label": "分析結果",                      "kind": "optional"},
    # Delivery → END
    {"from": "writer",          "to": "END",              "label": "",                              "kind": "normal"},
]

# ─────────────────────────────────────────────────────────────────────────────
# AgentState フィールド定義
# ─────────────────────────────────────────────────────────────────────────────

STATE_FIELDS: list[dict] = [
    # 入力
    {"field": "messages",             "type": "list[BaseMessage]",  "writer": "all",              "desc": "会話履歴 (add_messages reducer)"},
    {"field": "user_spec",            "type": "str",                "writer": "input",            "desc": "UpWork クライアント仕様テキスト"},
    # ProjectManager
    {"field": "work_plan",            "type": "str",                "writer": "project_manager",  "desc": "作業計画書"},
    {"field": "assigned_agents",      "type": "list[str]",          "writer": "project_manager",  "desc": "担当エージェント名リスト"},
    {"field": "agent_instructions",   "type": "dict[str, str]",     "writer": "project_manager",  "desc": "エージェント別指示文"},
    {"field": "human_feedback",       "type": "str",                "writer": "human",            "desc": "interrupt() で受け取る承認/修正指示"},
    # Workers (dict[str, str]: ファイルパス → コード)
    {"field": "tool_spec_files",      "type": "dict[str, str]",     "writer": "tool_specialist",  "desc": "共有ユーティリティ成果物"},
    {"field": "backend_files",        "type": "dict[str, str]",     "writer": "backend",          "desc": "バックエンド成果物"},
    {"field": "frontend_files",       "type": "dict[str, str]",     "writer": "frontend",         "desc": "フロントエンド成果物"},
    {"field": "database_files",       "type": "dict[str, str]",     "writer": "database",         "desc": "データベース成果物"},
    # RAG
    {"field": "retrieved_docs",       "type": "list[dict]",         "writer": "search",           "desc": "ベクトル検索結果"},
    {"field": "analysis_result",      "type": "str",                "writer": "analysis",         "desc": "技術分析結果"},
    # TestRunner
    {"field": "test_results",         "type": "dict[str, Any]",     "writer": "test_runner",      "desc": "pytest/ruff/mypy 実行結果"},
    # CodeReview
    {"field": "code_review_feedback", "type": "str",                "writer": "code_review",      "desc": "横断コードレビュー結果"},
    {"field": "fix_targets",          "type": "list[str]",          "writer": "code_review",      "desc": "修正が必要なエージェントリスト"},
    # ReviewManager
    {"field": "review_loop_count",    "type": "int",                "writer": "review_manager",   "desc": "レビューループ回数 (上限 max_review_loops)"},
    {"field": "fix_instructions",     "type": "dict[str, str]",     "writer": "review_manager",   "desc": "エージェント別修正指示文"},
    {"field": "remaining_issues",     "type": "str",                "writer": "review_manager",   "desc": "ループ上限後の残存課題"},
    {"field": "next",                 "type": "str",                "writer": "review_manager",   "desc": "ルーティングシグナル (fix | writer)"},
    # Writer
    {"field": "final_files",          "type": "dict[str, str]",     "writer": "writer",           "desc": "全納品ファイル (merge済み)"},
    {"field": "final_answer",         "type": "str",                "writer": "writer",           "desc": "UpWork 提出フォーマット納品物"},
]

# ─────────────────────────────────────────────────────────────────────────────
# レビューループ定義
# ─────────────────────────────────────────────────────────────────────────────

REVIEW_LOOP = {
    "max_loops":      "settings.workflow.max_review_loops (default: 2)",
    "loop_counter":   "review_loop_count",
    "trigger_node":   "test_runner → code_review",
    "manager_node":   "review_manager",
    "fix_targets":    ["backend", "frontend", "database", "tool_specialist"],
    "exit_node":      "writer",
    "exit_condition": "問題なし または review_loop_count >= max_review_loops",
}

# ─────────────────────────────────────────────────────────────────────────────
# Human-in-the-loop 定義
# ─────────────────────────────────────────────────────────────────────────────

HUMAN_IN_LOOP = {
    "node":       "project_manager",
    "trigger":    "settings.workflow.require_plan_approval == True",
    "mechanism":  "langgraph.types.interrupt()",
    "checkpointer": "MemorySaver (main.py で DI)",
    "resume_key": "human_feedback",
    "flow": [
        "1. ProjectManager が作業計画を生成する",
        "2. interrupt() でグラフを一時停止し計画を人間に提示",
        "3a. 'approve' → 実装フェーズへ進む",
        "3b. 修正指示 → incorporate_human_feedback で計画を更新してから進む",
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# ディレクトリ構造定義
# ─────────────────────────────────────────────────────────────────────────────

DIRECTORY_STRUCTURE: list[tuple[str, str]] = [
    ("agents/Agent_Node.py",                    "基底クラス: @tool自動収集・LLMバインド・ContextManager"),
    ("agents/utils/context_manager.py",         "ContextManager: メッセージトリム・アーティファクト要約"),
    ("agents/nodes/project_manager_node.py",    "最上位オーケストレーター + Human-in-the-loop"),
    ("agents/nodes/backend_node.py",            "Python/FastAPI専門 → backend_files: dict[str,str]"),
    ("agents/nodes/frontend_node.py",           "フロントエンド専門 → frontend_files: dict[str,str]"),
    ("agents/nodes/database_node.py",           "DB設計・実装専門 → database_files: dict[str,str]"),
    ("agents/nodes/tool_specialist_node.py",    "共有ユーティリティ実装 → tool_spec_files: dict[str,str]"),
    ("agents/nodes/test_runner_node.py",        "pytest/ruff/mypy 自動実行 → test_results: dict"),
    ("agents/nodes/code_review_node.py",        "横断コードレビュー + テスト結果評価"),
    ("agents/nodes/review_manager_node.py",     "レビューループ制御 (max_review_loops)"),
    ("agents/nodes/search_node.py",             "RAGベクトル検索"),
    ("agents/nodes/analysis_node.py",           "技術分析"),
    ("agents/nodes/writer_node.py",             "納品物整形 → final_files + final_answer"),
    ("config/settings.py",                      "設定 (LLM/RAG/AWS/Workflow)"),
    ("config/systemMessage.py",                 "全エージェントのシステムプロンプト (循環インポートなし)"),
    ("graph/workflow.py",                       "LangGraph StateGraph + MemorySaver定義"),
    ("graph/diagram_spec.py",                   "★ 図の単一情報源 (ここを更新)"),
    ("rag/retriever.py",                        "Retriever (semantic/keyword/hybrid)"),
    ("rag/vector_store.py",                     "VectorStore (Protocol抽象化)"),
    ("rag/embeddings.py",                       "EmbeddingModel"),
    ("secrets/secrets_manager.py",              "AWS Secrets Manager クライアント (TTLキャッシュ)"),
    ("secrets/secret_keys.py",                  "シークレット名定数"),
    ("tools/tool_registry.py",                  "グローバル@toolカタログ"),
    ("tools/generate_diagram.py",               "★ Mermaid図自動生成スクリプト"),
    ("docs/architecture.md",                    "★ 生成されたアーキテクチャ図 (自動更新)"),
    ("pyproject.toml",                          "★ uv依存関係管理 (本番+開発)"),
    ("uv.lock",                                 "uv ロックファイル (自動生成・要コミット)"),
    (".python-version",                         "Pythonバージョン固定 (3.11)"),
    (".env.example",                            "非機密設定テンプレート"),
    ("main.py",                                 "エントリポイント・DI組み立て・MemorySaver注入"),
]
