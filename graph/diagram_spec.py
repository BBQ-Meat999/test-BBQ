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

SYSTEM_VERSION = "2.0.0"
SYSTEM_NAME    = "UpWork Multi-Agent System"

# ─────────────────────────────────────────────────────────────────────────────
# ノード定義
# ─────────────────────────────────────────────────────────────────────────────
# layer: "management" | "worker" | "quality" | "delivery"

NODES: list[dict] = [
    # Management
    {
        "id":    "project_manager",
        "label": "ProjectManager",
        "layer": "management",
        "role":  "①モデル選択(利益最大化・システム側) ②仕様解析・担当割当 ③Human-in-the-loop (interrupt)",
        "tools": [
            "ModelSelector(決定論的割当)",
            "WorkPlan構造化出力",
            "interrupt()承認",
            "修正指示の反映(再生成)",
        ],
    },
    {
        "id":    "review_manager",
        "label": "ReviewManager",
        "layer": "management",
        "role":  "レビュー結果解析・修正指示生成・ループ制御 (最大 max_review_loops 回・決定論的)",
        "tools": [
            "escalate判定(決定論的)",
            "ReviewDecision構造化出力",
            "fix_instructions生成",
            "remaining_issues要約",
        ],
    },
    # Workers
    {
        "id":    "backend",
        "label": "BackendNode",
        "layer": "worker",
        "role":  "Python / FastAPI / pytest → backend_files: dict[str, str]",
        "tools": [
            "FileSet構造化出力",
            "API実装+pytest+依存定義",
            "修正指示の上書きマージ",
        ],
    },
    {
        "id":    "frontend",
        "label": "FrontendNode",
        "layer": "worker",
        "role":  "React / TypeScript / CSS → frontend_files: dict[str, str]",
        "tools": [
            "FileSet構造化出力",
            "HTML/CSS/TSコンポーネント+API連携",
            "修正指示の上書きマージ",
        ],
    },
    {
        "id":    "database",
        "label": "DatabaseNode",
        "layer": "worker",
        "role":  "SQLAlchemy / Alembic / ERD → database_files: dict[str, str]",
        "tools": [
            "FileSet構造化出力",
            "ORMモデル+マイグレーション+Repository",
            "修正指示の上書きマージ",
        ],
    },
    {
        "id":    "tool_specialist",
        "label": "ToolSpecialistNode",
        "layer": "worker",
        "role":  "共有ユーティリティ実装 → tool_spec_files: dict[str, str]",
        "tools": [
            "FileSet構造化出力",
            "バリデーション/例外/ログ等の共通基盤",
            "修正指示の上書きマージ",
        ],
    },
    # Quality Gate
    {
        "id":    "test_runner",
        "label": "TestRunnerNode",
        "layer": "quality",
        "role":  "pytest / ruff / mypy 自動実行 (LLM不使用・純Python) → test_results: dict",
        "tools": [
            "一時ディレクトリ展開",
            "pytest subprocess実行",
            "ruff / mypy 静的解析",
            "結果パース",
        ],
    },
    {
        "id":    "code_review",
        "label": "CodeReviewNode",
        "layer": "quality",
        "role":  "品質・整合性・セキュリティ横断レビュー + テスト結果評価",
        "tools": [
            "ReviewResult構造化出力",
            "フルコード+テスト結果の横断評価",
            "OWASP観点セキュリティ確認",
            "fix_targets特定",
        ],
    },
    # Delivery
    {
        "id":    "writer",
        "label": "WriterNode",
        "layer": "delivery",
        "role":  "UpWork納品物整形・品質チェック・ドキュメント生成",
        "tools": [
            "全成果物マージ(純Python)",
            "Delivery構造化出力",
            "README/引き渡しドキュメント生成",
            "final_files + final_answer",
        ],
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# エッジ定義
# ─────────────────────────────────────────────────────────────────────────────
# kind: "normal" | "conditional" | "send_parallel"

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
    # TestRunner → CodeReview → ReviewManager
    {"from": "test_runner",     "to": "code_review",      "label": "テスト結果",                    "kind": "normal"},
    {"from": "code_review",     "to": "review_manager",   "label": "フィードバック",                "kind": "normal"},
    # ReviewManager → Workers (修正ループ / Send API)
    {"from": "review_manager",  "to": "backend",          "label": "修正指示 (loop<max)",           "kind": "send_parallel"},
    {"from": "review_manager",  "to": "frontend",         "label": "修正指示 (loop<max)",           "kind": "send_parallel"},
    {"from": "review_manager",  "to": "database",         "label": "修正指示 (loop<max)",           "kind": "send_parallel"},
    {"from": "review_manager",  "to": "tool_specialist",  "label": "修正指示 (loop<max)",           "kind": "send_parallel"},
    # ReviewManager → Writer (終了条件)
    {"from": "review_manager",  "to": "writer",           "label": "問題なし or loop≥max",          "kind": "conditional"},
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
    # モデル選択 (ProjectManager が ModelSelector で決定論的に決定)
    {"field": "reward_amount",        "type": "float",              "writer": "input",            "desc": "UpWork 報奨金 (USD) — モデル選択の基準"},
    {"field": "model_assignments",    "type": "dict[str, str]",     "writer": "project_manager",  "desc": "node_name → Claude model_id (利益最大化モデル)"},
    {"field": "estimated_cost",       "type": "float",              "writer": "project_manager",  "desc": "期待 API コスト (USD)"},
    {"field": "estimated_profit",     "type": "float",              "writer": "project_manager",  "desc": "期待利益 (USD)"},
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
    "node":         "project_manager",
    "trigger":      "settings.workflow.require_plan_approval == True",
    "mechanism":    "langgraph.types.interrupt()",
    "checkpointer": "MemorySaver (main.py で DI)",
    "resume_key":   "human_feedback",
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
    ("agents/Agent_Node.py",                    "基底クラス: 動的モデル選択・構造化出力・ContextManager"),
    ("agents/schemas.py",                       "★ 構造化出力スキーマ (WorkPlan/FileSet/ReviewResult等)"),
    ("agents/utils/context_manager.py",         "ContextManager: メッセージトリム・アーティファクト要約"),
    ("agents/nodes/project_manager_node.py",    "最上位オーケストレーター + Human-in-the-loop"),
    ("agents/nodes/worker_base.py",             "WorkerNode基底: FileSet生成・修正マージの共通実装"),
    ("agents/nodes/backend_node.py",            "Python/FastAPI専門 → backend_files: dict[str,str]"),
    ("agents/nodes/frontend_node.py",           "フロントエンド専門 → frontend_files: dict[str,str]"),
    ("agents/nodes/database_node.py",           "DB設計・実装専門 → database_files: dict[str,str]"),
    ("agents/nodes/tool_specialist_node.py",    "共有ユーティリティ実装 → tool_spec_files: dict[str,str]"),
    ("agents/nodes/test_runner_node.py",        "pytest/ruff/mypy 自動実行 → test_results: dict"),
    ("agents/nodes/code_review_node.py",        "横断コードレビュー + テスト結果評価"),
    ("agents/nodes/review_manager_node.py",     "レビューループ制御 (max_review_loops)"),
    ("agents/nodes/writer_node.py",             "納品物整形 → final_files + final_answer"),
    ("config/settings.py",                      "設定 (LLM/AWS/Workflow)"),
    ("config/model_selector.py",               "★ 利益最大化モデル選択 (コスト・手戻り率計算)"),
    ("config/systemMessage.py",                 "全エージェントのシステムプロンプト"),
    ("graph/workflow.py",                       "LangGraph StateGraph + MemorySaver定義"),
    ("graph/diagram_spec.py",                   "★ 図の単一情報源 (ここを更新)"),
    ("app_secrets/secrets_manager.py",          "AWS Secrets Manager クライアント (TTLキャッシュ)"),
    ("app_secrets/secret_keys.py",              "シークレット名定数 (標準ライブラリ secrets との衝突回避でリネーム)"),
    ("tools/generate_diagram.py",               "★ Mermaid図自動生成スクリプト"),
    ("docs/architecture.md",                    "★ 生成されたアーキテクチャ図 (自動更新)"),
    ("pyproject.toml",                          "★ uv依存関係管理 (本番+開発)"),
    ("uv.lock",                                 "uv ロックファイル (自動生成・要コミット)"),
    (".python-version",                         "Pythonバージョン固定 (3.11)"),
    (".env.example",                            "非機密設定テンプレート"),
    ("main.py",                                 "エントリポイント・DI組み立て・MemorySaver注入"),
]
