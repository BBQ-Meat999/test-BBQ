# UpWork Multi-Agent System — Architecture
> **Version:** 1.6.0  |  **Generated:** 2026-06-19 13:20 UTC  |  **Source:** `graph/diagram_spec.py`

> [!WARNING]
> このファイルは自動生成です。直接編集しないでください。
> 変更は `graph/diagram_spec.py` を更新してから `python tools/generate_diagram.py` を実行してください。

---
## 1. システム全体フロー

```mermaid
flowchart TD
    subgraph MANAGEMENT["Management Layer"]
        project_manager["ProjectManager\n仕様解析・作業計画・担当割当・指示生成 / Human-in-the-loop (interrupt)"]
        review_manager["ReviewManager\nレビュー結果解析・修正指示生成・ループ制御 (最大 max_review_loops 回)"]
    end
    subgraph WORKER["Worker Layer"]
        backend["BackendNode\nPython / FastAPI / pytest → backend_files: dict[str, str]"]
        frontend["FrontendNode\nReact / TypeScript / CSS → frontend_files: dict[str, str]"]
        database["DatabaseNode\nSQLAlchemy / Alembic / ERD → database_files: dict[str, str]"]
        tool_specialist["ToolSpecialistNode\n共有ユーティリティ実装 → tool_spec_files: dict[str, str]"]
    end
    subgraph QUALITY["Quality Gate"]
        test_runner["TestRunnerNode\npytest / ruff / mypy 自動実行 → test_results: dict"]
        code_review["CodeReviewNode\n品質・整合性・セキュリティ横断レビュー + テスト結果評価"]
    end
    subgraph DELIVERY["Delivery"]
        writer["WriterNode\nUpWork納品物整形・品質チェック・ドキュメント生成"]
    end
    START(["🚀 START"])
    END(["✅ END"])
    START --> project_manager
    project_manager ==>|"interrupt() 承認後 / Send API"| backend
    project_manager ==>|"interrupt() 承認後 / Send API"| frontend
    project_manager ==>|"interrupt() 承認後 / Send API"| database
    project_manager ==>|"interrupt() 承認後 / Send API"| tool_specialist
    backend -->|"実装完了"| test_runner
    frontend -->|"実装完了"| test_runner
    database -->|"実装完了"| test_runner
    tool_specialist -->|"実装完了"| test_runner
    test_runner -->|"テスト結果"| code_review
    code_review -->|"フィードバック"| review_manager
    review_manager ==>|"修正指示 (loop<max)"| backend
    review_manager ==>|"修正指示 (loop<max)"| frontend
    review_manager ==>|"修正指示 (loop<max)"| database
    review_manager ==>|"修正指示 (loop<max)"| tool_specialist
    review_manager -->|"問題なし or loop≥max"| writer
    writer --> END
    style project_manager fill:#ffecd2,stroke:#e67e22
    style review_manager fill:#ffecd2,stroke:#e67e22
    style backend fill:#d5f5e3,stroke:#27ae60
    style frontend fill:#d5f5e3,stroke:#27ae60
    style database fill:#d5f5e3,stroke:#27ae60
    style tool_specialist fill:#d5f5e3,stroke:#27ae60
    style test_runner fill:#fde8e8,stroke:#e74c3c
    style code_review fill:#fde8e8,stroke:#e74c3c
    style writer fill:#f8f9fa,stroke:#7f8c8d
```

**凡例**
| 矢印 | 意味 |
|---|---|
| `-->` | 通常遷移 |
| `==>` | Send API 並列実行 |
| `-.->` | オプション (RAG) |
---
## 2. コードレビューループ シーケンス

> 実装 ↔ レビュー のループは最大 **settings.workflow.max_review_loops (default: 2) 回** に制限されます。

```mermaid
sequenceDiagram
    autonumber
    participant PM  as ProjectManager
    participant W   as Workers<br/>(backend / frontend / database / tool_specialist)
    participant CR  as CodeReview
    participant RM  as ReviewManager
    participant WR  as Writer

    PM->>W: 仕様・指示を送信 (Send API 並列)
    activate W
    W-->>CR: 実装成果物 (収束)
    deactivate W

    loop 最大 settings.workflow.max_review_loops (default: 2) 回
        activate CR
        CR->>RM: レビューフィードバック + fix_targets
        deactivate CR
        activate RM
        alt 問題あり かつ loop_count < settings.workflow.max_review_loops (default: 2)
            RM->>W: 修正指示 (Send API 並列)
            activate W
            Note over RM: review_loop_count ++
            W-->>CR: 修正済み成果物
            deactivate W
        else 問題なし または loop_count >= settings.workflow.max_review_loops (default: 2)
            RM->>WR: 残存課題サマリー (あれば)
            deactivate RM
        end
    end

    activate WR
    WR-->>WR: 全成果物を統合
    WR->>WR: UpWork納品物整形
    Note over WR: final_answer 生成
    deactivate WR
```
---
## 3. エージェント役割 マインドマップ

```mermaid
mindmap
  root((UpWork Multi-Agent System))
    Management
      ProjectManager
        仕様解析・作業計画・担当割当・指示生成 / Human-in-the-loop (interrupt)
      ReviewManager
        レビュー結果解析・修正指示生成・ループ制御 (最大 max_review_loops 回)
    Workers
      BackendNode
        Python / FastAPI / pytest → backend_files: dict[str, str]
      FrontendNode
        React / TypeScript / CSS → frontend_files: dict[str, str]
      DatabaseNode
        SQLAlchemy / Alembic / ERD → database_files: dict[str, str]
      ToolSpecialistNode
        共有ユーティリティ実装 → tool_spec_files: dict[str, str]
    Quality Gate
      TestRunnerNode
        pytest / ruff / mypy 自動実行 → test_results: dict
      CodeReviewNode
        品質・整合性・セキュリティ横断レビュー + テスト結果評価
    Delivery
      WriterNode
        UpWork納品物整形・品質チェック・ドキュメント生成
```
---
## 4. AgentState データフロー

> 各フィールドがどのエージェントによって書き込まれるかを示します。

```mermaid
flowchart LR
    subgraph input["input"]
        user_spec["user_spec<br/><i>str</i>"]
    end
    subgraph project_manager["project_manager"]
        work_plan["work_plan<br/><i>str</i>"]
        assigned_agents["assigned_agents<br/><i>list[str]</i>"]
        agent_instructions["agent_instructions<br/><i>dict[str, str]</i>"]
    end
    subgraph tool_specialist["tool_specialist"]
        tool_spec_files["tool_spec_files<br/><i>dict[str, str]</i>"]
    end
    subgraph backend["backend"]
        backend_files["backend_files<br/><i>dict[str, str]</i>"]
    end
    subgraph frontend["frontend"]
        frontend_files["frontend_files<br/><i>dict[str, str]</i>"]
    end
    subgraph database["database"]
        database_files["database_files<br/><i>dict[str, str]</i>"]
    end
    subgraph code_review["code_review"]
        code_review_feedback["code_review_feedback<br/><i>str</i>"]
        fix_targets["fix_targets<br/><i>list[str]</i>"]
    end
    subgraph review_manager["review_manager"]
        review_loop_count["review_loop_count<br/><i>int</i>"]
        fix_instructions["fix_instructions<br/><i>dict[str, str]</i>"]
        remaining_issues["remaining_issues<br/><i>str</i>"]
        next["next<br/><i>str</i>"]
    end
    subgraph writer["writer"]
        final_files["final_files<br/><i>dict[str, str]</i>"]
        final_answer["final_answer<br/><i>str</i>"]
    end
    subgraph all["all"]
        messages["messages<br/><i>list[BaseMessage]</i>"]
    end
```

### State フィールド一覧

| フィールド | 型 | 書き込みノード | 説明 |
|---|---|---|---|
| `messages` | `list[BaseMessage]` | `all` | 会話履歴 (add_messages reducer) |
| `user_spec` | `str` | `input` | UpWork クライアント仕様テキスト |
| `work_plan` | `str` | `project_manager` | 作業計画書 |
| `assigned_agents` | `list[str]` | `project_manager` | 担当エージェント名リスト |
| `agent_instructions` | `dict[str, str]` | `project_manager` | エージェント別指示文 |
| `human_feedback` | `str` | `human` | interrupt() で受け取る承認/修正指示 |
| `tool_spec_files` | `dict[str, str]` | `tool_specialist` | 共有ユーティリティ成果物 |
| `backend_files` | `dict[str, str]` | `backend` | バックエンド成果物 |
| `frontend_files` | `dict[str, str]` | `frontend` | フロントエンド成果物 |
| `database_files` | `dict[str, str]` | `database` | データベース成果物 |
| `test_results` | `dict[str, Any]` | `test_runner` | pytest/ruff/mypy 実行結果 |
| `code_review_feedback` | `str` | `code_review` | 横断コードレビュー結果 |
| `fix_targets` | `list[str]` | `code_review` | 修正が必要なエージェントリスト |
| `review_loop_count` | `int` | `review_manager` | レビューループ回数 (上限 max_review_loops) |
| `fix_instructions` | `dict[str, str]` | `review_manager` | エージェント別修正指示文 |
| `remaining_issues` | `str` | `review_manager` | ループ上限後の残存課題 |
| `next` | `str` | `review_manager` | ルーティングシグナル (fix | writer) |
| `final_files` | `dict[str, str]` | `writer` | 全納品ファイル (merge済み) |
| `final_answer` | `str` | `writer` | UpWork 提出フォーマット納品物 |
---
## 5. @tool カタログ

> 全エージェント合計 **50 ツール**

| エージェント | @tool 一覧 | 数 |
|---|---|---|
| **ProjectManager** | `parse_requirements` / `create_work_plan` / `assign_agents` / `incorporate_human_feedback` | 4 |
| **ReviewManager** | `prioritize_issues` / `generate_fix_instruction` / `should_escalate` / `summarize_remaining_issues` | 4 |
| **BackendNode** | `design_api` / `write_python_code` / `write_tests` / `write_requirements` / `generate_dockerfile` / `apply_fix` | 6 |
| **FrontendNode** | `design_ui` / `write_html_css` / `write_javascript` / `generate_components` / `integrate_api` / `generate_build_config` / `apply_fix` | 7 |
| **DatabaseNode** | `design_erd` / `generate_sqlalchemy_models` / `generate_alembic_migration` / `generate_repository` / `optimize_queries` / `generate_seed_data` / `generate_db_config` / `apply_fix` | 8 |
| **ToolSpecialistNode** | `analyze_utility_requirements` / `implement_utility` / `generate_error_handling` / `generate_logging_config` / `generate_validation_utils` / `apply_fix` | 6 |
| **TestRunnerNode** | `write_files_to_tempdir` / `run_pytest` / `run_ruff_check` / `run_mypy` | 4 |
| **CodeReviewNode** | `review_files` / `evaluate_test_results` / `check_cross_consistency` / `check_security` / `identify_fix_targets` / `generate_feedback_summary` | 6 |
| **WriterNode** | `merge_all_files` / `write_readme` / `write_handover_doc` / `quality_check` / `format_for_upwork` | 5 |
---
## 6. ディレクトリ構造

```
test-BBQ/
│
    ├── Agent_Node.py                            # 基底クラス: @tool自動収集・LLMバインド・ContextManager
        ├── context_manager.py                       # ContextManager: メッセージトリム・アーティファクト要約
        ├── project_manager_node.py                  # 最上位オーケストレーター + Human-in-the-loop
        ├── backend_node.py                          # Python/FastAPI専門 → backend_files: dict[str,str]
        ├── frontend_node.py                         # フロントエンド専門 → frontend_files: dict[str,str]
        ├── database_node.py                         # DB設計・実装専門 → database_files: dict[str,str]
        ├── tool_specialist_node.py                  # 共有ユーティリティ実装 → tool_spec_files: dict[str,str]
        ├── test_runner_node.py                      # pytest/ruff/mypy 自動実行 → test_results: dict
        ├── code_review_node.py                      # 横断コードレビュー + テスト結果評価
        ├── review_manager_node.py                   # レビューループ制御 (max_review_loops)
        ├── writer_node.py                           # 納品物整形 → final_files + final_answer
│
    ├── settings.py                              # 設定 (LLM/AWS/Workflow)
    ├── systemMessage.py                         # 全エージェントのシステムプロンプト
│
    ├── workflow.py                              # LangGraph StateGraph + MemorySaver定義
    ├── diagram_spec.py                          # 図の単一情報源 (ここを更新) ★
│
    ├── secrets_manager.py                       # AWS Secrets Manager クライアント (TTLキャッシュ)
    ├── secret_keys.py                           # シークレット名定数
│
    ├── generate_diagram.py                      # Mermaid図自動生成スクリプト ★
│
    ├── architecture.md                          # 生成されたアーキテクチャ図 (自動更新) ★
├── pyproject.toml                           # uv依存関係管理 (本番+開発) ★
├── uv.lock                                  # uv ロックファイル (自動生成・要コミット)
├── .python-version                          # Pythonバージョン固定 (3.11)
├── .env.example                             # 非機密設定テンプレート
├── main.py                                  # エントリポイント・DI組み立て・MemorySaver注入
```
---
## 7. 更新手順

システムにエージェント・ノード・ステートを追加したときの手順:

```bash
# 1. diagram_spec.py を更新 (NODES / EDGES / STATE_FIELDS)
vim graph/diagram_spec.py

# 2. Mermaid図を再生成
python tools/generate_diagram.py

# 3. コミット
git add graph/diagram_spec.py docs/architecture.md
git commit -m "docs: アーキテクチャ図更新"
```

---

*Auto-generated by `tools/generate_diagram.py` — UpWork Multi-Agent System v1.6.0*
