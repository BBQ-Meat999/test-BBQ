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

SYSTEM_VERSION = "1.4.0"
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
        "role":  "仕様解析・作業計画・担当割当・指示生成",
        "tools": [
            "parse_requirements",
            "create_work_plan",
            "assign_agents",
            "generate_agent_instruction",
        ],
    },
    {
        "id":    "review_manager",
        "label": "ReviewManager",
        "layer": "management",
        "role":  "レビュー結果解析・修正指示生成・ループ制御 (最大2回)",
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
        "role":  "Python / FastAPI / pytest",
        "tools": [
            "design_api",
            "write_python_code",
            "design_database_schema",
            "write_tests",
            "write_requirements",
            "generate_dockerfile",
        ],
    },
    {
        "id":    "frontend",
        "label": "FrontendNode",
        "layer": "worker",
        "role":  "React / TypeScript / CSS",
        "tools": [
            "design_ui",
            "write_html_css",
            "write_javascript",
            "generate_components",
            "integrate_api",
            "generate_assets_config",
        ],
    },
    {
        "id":    "database",
        "label": "DatabaseNode",
        "layer": "worker",
        "role":  "SQLAlchemy / Alembic / ERD",
        "tools": [
            "design_erd",
            "generate_sqlalchemy_models",
            "generate_alembic_migration",
            "optimize_queries",
            "generate_seed_data",
            "generate_db_config",
        ],
    },
    {
        "id":    "tool_specialist",
        "label": "ToolSpecialistNode",
        "layer": "worker",
        "role":  "@tool 設計・実装・ToolRegistry 登録",
        "tools": [
            "analyze_tool_requirements",
            "design_tool_interface",
            "implement_tool",
            "check_tool_conflicts",
            "generate_registry_code",
        ],
    },
    # Quality Gate
    {
        "id":    "code_review",
        "label": "CodeReviewNode",
        "layer": "quality",
        "role":  "品質・整合性・セキュリティ横断レビュー",
        "tools": [
            "review_backend",
            "review_frontend",
            "review_database",
            "review_tools",
            "check_cross_consistency",
            "check_security",
            "identify_fix_targets",
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
            "compile_deliverable",
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
    {"from": "START",           "to": "project_manager",  "label": "",                          "kind": "normal"},
    # PM → Workers (Send API 並列)
    {"from": "project_manager", "to": "backend",          "label": "Send API 並列",             "kind": "send_parallel"},
    {"from": "project_manager", "to": "frontend",         "label": "Send API 並列",             "kind": "send_parallel"},
    {"from": "project_manager", "to": "database",         "label": "Send API 並列",             "kind": "send_parallel"},
    {"from": "project_manager", "to": "tool_specialist",  "label": "Send API 並列",             "kind": "send_parallel"},
    # Workers → CodeReview (収束)
    {"from": "backend",         "to": "code_review",      "label": "実装完了",                  "kind": "normal"},
    {"from": "frontend",        "to": "code_review",      "label": "実装完了",                  "kind": "normal"},
    {"from": "database",        "to": "code_review",      "label": "実装完了",                  "kind": "normal"},
    {"from": "tool_specialist", "to": "code_review",      "label": "実装完了",                  "kind": "normal"},
    # CodeReview → ReviewManager
    {"from": "code_review",     "to": "review_manager",   "label": "フィードバック",             "kind": "normal"},
    # ReviewManager → Workers (修正ループ / Send API)
    {"from": "review_manager",  "to": "backend",          "label": "修正指示 (loop<2)",         "kind": "send_parallel"},
    {"from": "review_manager",  "to": "frontend",         "label": "修正指示 (loop<2)",         "kind": "send_parallel"},
    {"from": "review_manager",  "to": "database",         "label": "修正指示 (loop<2)",         "kind": "send_parallel"},
    {"from": "review_manager",  "to": "tool_specialist",  "label": "修正指示 (loop<2)",         "kind": "send_parallel"},
    # ReviewManager → Writer (終了条件)
    {"from": "review_manager",  "to": "writer",           "label": "問題なし or loop≥2",        "kind": "conditional"},
    # RAG (オプション)
    {"from": "project_manager", "to": "search",           "label": "RAG検索 (任意)",            "kind": "optional"},
    {"from": "search",          "to": "analysis",         "label": "",                          "kind": "optional"},
    {"from": "analysis",        "to": "project_manager",  "label": "分析結果",                  "kind": "optional"},
    # Delivery → END
    {"from": "writer",          "to": "END",              "label": "",                          "kind": "normal"},
]

# ─────────────────────────────────────────────────────────────────────────────
# AgentState フィールド定義
# ─────────────────────────────────────────────────────────────────────────────

STATE_FIELDS: list[dict] = [
    # 入力
    {"field": "messages",            "type": "list[BaseMessage]", "writer": "all",              "desc": "会話履歴 (add_messages reducer)"},
    {"field": "user_spec",           "type": "str",               "writer": "input",            "desc": "UpWork クライアント仕様テキスト"},
    # ProjectManager
    {"field": "work_plan",           "type": "str",               "writer": "project_manager",  "desc": "作業計画書"},
    {"field": "assigned_agents",     "type": "list[str]",         "writer": "project_manager",  "desc": "担当エージェント名リスト"},
    {"field": "agent_instructions",  "type": "dict[str, str]",    "writer": "project_manager",  "desc": "エージェント別指示文"},
    # Workers
    {"field": "tool_spec_result",    "type": "str",               "writer": "tool_specialist",  "desc": "ToolSpecialist 成果物"},
    {"field": "backend_result",      "type": "str",               "writer": "backend",          "desc": "BackendNode 成果物"},
    {"field": "frontend_result",     "type": "str",               "writer": "frontend",         "desc": "FrontendNode 成果物"},
    {"field": "database_result",     "type": "str",               "writer": "database",         "desc": "DatabaseNode 成果物"},
    # RAG
    {"field": "retrieved_docs",      "type": "list[dict]",        "writer": "search",           "desc": "ベクトル検索結果"},
    {"field": "analysis_result",     "type": "str",               "writer": "analysis",         "desc": "技術分析結果"},
    # CodeReview
    {"field": "code_review_feedback","type": "str",               "writer": "code_review",      "desc": "横断コードレビュー結果"},
    {"field": "fix_targets",         "type": "list[str]",         "writer": "code_review",      "desc": "修正が必要なエージェントリスト"},
    # ReviewManager
    {"field": "review_loop_count",   "type": "int",               "writer": "review_manager",   "desc": "レビューループ回数 (上限2)"},
    {"field": "fix_instructions",    "type": "dict[str, str]",    "writer": "review_manager",   "desc": "エージェント別修正指示文"},
    {"field": "remaining_issues",    "type": "str",               "writer": "review_manager",   "desc": "ループ上限後の残存課題"},
    {"field": "next",                "type": "str",               "writer": "review_manager",   "desc": "ルーティングシグナル"},
    # Writer
    {"field": "final_answer",        "type": "str",               "writer": "writer",           "desc": "UpWork 提出フォーマット納品物"},
]

# ─────────────────────────────────────────────────────────────────────────────
# レビューループ定義
# ─────────────────────────────────────────────────────────────────────────────

REVIEW_LOOP = {
    "max_loops":     2,
    "loop_counter":  "review_loop_count",
    "trigger_node":  "code_review",
    "manager_node":  "review_manager",
    "fix_targets":   ["backend", "frontend", "database", "tool_specialist"],
    "exit_node":     "writer",
    "exit_condition": "問題なし または review_loop_count >= 2",
}

# ─────────────────────────────────────────────────────────────────────────────
# ディレクトリ構造定義
# ─────────────────────────────────────────────────────────────────────────────

DIRECTORY_STRUCTURE: list[tuple[str, str]] = [
    ("agents/Agent_Node.py",                    "基底クラス: @tool自動収集・LLMバインド"),
    ("agents/nodes/project_manager_node.py",    "最上位オーケストレーター"),
    ("agents/nodes/backend_node.py",            "Python/FastAPI専門"),
    ("agents/nodes/frontend_node.py",           "フロントエンド専門"),
    ("agents/nodes/database_node.py",           "DB設計・実装専門"),
    ("agents/nodes/tool_specialist_node.py",    "@tool設計・実装専門"),
    ("agents/nodes/code_review_node.py",        "横断コードレビュー"),
    ("agents/nodes/review_manager_node.py",     "レビューループ制御"),
    ("agents/nodes/search_node.py",             "RAGベクトル検索"),
    ("agents/nodes/analysis_node.py",           "技術分析"),
    ("agents/nodes/writer_node.py",             "納品物整形"),
    ("config/settings.py",                      "設定 (LLM/RAG/AWS)"),
    ("config/systemMessage.py",                 "全エージェントのシステムプロンプト"),
    ("graph/workflow.py",                       "LangGraph StateGraph定義"),
    ("graph/diagram_spec.py",                   "★ 図の単一情報源 (ここを更新)"),
    ("rag/retriever.py",                        "Retriever (semantic/keyword/hybrid)"),
    ("rag/vector_store.py",                     "VectorStore (Protocol抽象化)"),
    ("rag/embeddings.py",                       "EmbeddingModel"),
    ("secrets/secrets_manager.py",              "AWS Secrets Manager クライアント"),
    ("secrets/secret_keys.py",                  "シークレット名定数"),
    ("tools/tool_registry.py",                  "グローバル@toolカタログ"),
    ("tools/generate_diagram.py",               "★ Mermaid図自動生成スクリプト"),
    ("docs/architecture.md",                    "★ 生成されたアーキテクチャ図 (自動更新)"),
    ("pyproject.toml",                          "★ uv依存関係管理 (本番+開発)"),
    ("uv.lock",                                 "uv ロックファイル (自動生成・要コミット)"),
    (".python-version",                         "Pythonバージョン固定 (3.11)"),
    (".env.example",                            "非機密設定テンプレート"),
    ("main.py",                                 "エントリポイント・DI組み立て"),
]
