"""
構造化出力スキーマ — 各エージェントが LLM から受け取る型付き結果。

設計意図:
  以前は @tool デコレータを付けたメソッド (本体は ...) でツールを定義していたが、
  LangChain の @tool はインスタンスメソッド (self 付き) を正しく扱えず、
  さらに本体が空のため実際には何も生成できなかった。

  本システムのワーカーは「コードを生成する」のが仕事であり、
  生成処理は Python ではなく LLM が行う。したがって正しいプリミティブは
  `llm.with_structured_output(Schema)` による構造化出力である。

  各ノードはここで定義したスキーマを使って LLM から型付きの結果を受け取り、
  AgentState の専用フィールド (*_files 等) に格納する。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class WorkPlan(BaseModel):
    """ProjectManager が仕様から生成する作業計画。"""

    work_plan: str = Field(
        description="クライアント仕様を構造化した詳細な作業計画書 (Markdown)。"
    )
    assigned_agents: list[str] = Field(
        description=(
            "担当させるワーカー名のリスト。"
            "backend / frontend / database / tool_specialist の部分集合。"
        )
    )
    agent_instructions: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "ワーカー名 → そのワーカーへの具体的な指示文。"
            "「何を・どの技術で・どの条件を満たして作るか」を明確に含める。"
        ),
    )


class FileSet(BaseModel):
    """ワーカーが生成する多ファイル成果物。"""

    files: dict[str, str] = Field(
        description=(
            "ファイルパス → ファイル全文 のマップ。"
            "コピー&ペーストで即動作する完全なコードを格納する。"
        )
    )
    notes: str = Field(
        default="",
        description="実装上の補足・前提・既知の制約 (任意)。",
    )


class ReviewResult(BaseModel):
    """CodeReview が全成果物とテスト結果から生成する横断レビュー結果。"""

    summary: str = Field(
        description=(
            "構造化されたレビューフィードバック。"
            "指摘ごとに severity (critical/high/medium/low)・ファイル・行・修正方針を含める。"
        )
    )
    fix_targets: list[str] = Field(
        default_factory=list,
        description=(
            "修正が必要なワーカー名のリスト。"
            "backend / frontend / database / tool_specialist の部分集合。"
            "問題がなければ空リスト。"
        ),
    )
    passed: bool = Field(
        description="重大な問題がなく納品可能と判断できる場合 True。",
    )


class ReviewDecision(BaseModel):
    """ReviewManager がレビュー結果から下す修正ループ制御の判断。"""

    fix_instructions: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "ワーカー名 → 修正指示文。"
            "どのファイルの何を・どのように直すかを具体的に記述する。"
        ),
    )
    remaining_issues: str = Field(
        default="",
        description=(
            "今回のループで解消しきれず残る課題のサマリー。"
            "ループ上限到達時に Writer が納品物へ注記するために使う。"
        ),
    )


class Delivery(BaseModel):
    """Writer が生成する最終納品ドキュメント群。"""

    readme: str = Field(
        description="プロジェクト README.md。セットアップ・環境変数・デプロイ手順を含む。"
    )
    handover: str = Field(
        description="クライアントへの引き渡しドキュメント。残存課題があれば明記する。"
    )
    summary: str = Field(
        description=(
            "UpWork 提出フォーマットの最終サマリー (Markdown)。"
            "プロジェクト概要・ディレクトリ構造・品質チェック結果・残存課題を含む。"
        )
    )
