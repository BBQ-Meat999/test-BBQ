"""
FileWorkspace — エージェントがファンクションコーリングで操作する仮想ファイルシステム。

各ワーカー (backend / frontend / database / tool_specialist) と Writer は、
`with_structured_output` で成果物 dict をまとめて返すのではなく、
LLM が `write_file` / `read_file` / `list_files` ツールを能動的に呼び出して
成果物を組み立てる (Anthropic function calling / tool use)。

ワークスペースは 1 ノード 1 インスタンス。書き込みは `files` に蓄積され、
ノードはループ完了後に `files` を成果物フィールドへ格納する。
`readonly_peers` に他ワーカーの成果物を渡しておくと、`read_file` で参照できる
(修正ループ時に既存コードや他ワーカーのコードを読んで整合を取るため)。
"""

from __future__ import annotations

from pathlib import PurePosixPath

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field


class _WriteArgs(BaseModel):
    path: str = Field(description="プロジェクトルートからの相対パス (例: src/app.py)。絶対パス・.. は不可。")
    content: str = Field(description="ファイルの全文。コピー&ペーストで即動作する完成コード。")


class _ReadArgs(BaseModel):
    path: str = Field(description="読み込む相対パス。自分が書いたファイルまたは既存の成果物。")


class _ListArgs(BaseModel):
    pass


def _is_safe_relpath(path: str) -> bool:
    """相対パスかつ親ディレクトリ参照・絶対パスでないことを検証する。"""
    if not path or path.startswith("/") or path.startswith("~"):
        return False
    pp = PurePosixPath(path)
    if pp.is_absolute():
        return False
    return not any(part == ".." for part in pp.parts)


class FileWorkspace:
    """LLM がツール経由で読み書きする仮想ファイルシステム。"""

    def __init__(
        self,
        initial: dict[str, str] | None = None,
        readonly_peers: dict[str, str] | None = None,
    ) -> None:
        # 自ノードが書き込む成果物 (これが最終的な output になる)
        self.files: dict[str, str] = dict(initial or {})
        # 参照専用: 他ワーカー成果物や既存コード
        self.readonly_peers: dict[str, str] = dict(readonly_peers or {})

    # ------------------------------------------------------------------
    # Tool implementations (LLM から呼ばれる本体)
    # ------------------------------------------------------------------

    def write_file(self, path: str, content: str) -> str:
        if not _is_safe_relpath(path):
            return f"ERROR: 不正なパス '{path}'。プロジェクトルートからの相対パスを使うこと。"
        existed = path in self.files
        self.files[path] = content
        verb = "上書き" if existed else "作成"
        return f"OK: {path} を{verb}しました ({len(content.splitlines())} 行)。"

    def read_file(self, path: str) -> str:
        if path in self.files:
            return self.files[path]
        if path in self.readonly_peers:
            return self.readonly_peers[path]
        available = sorted({*self.files, *self.readonly_peers})
        return (
            f"ERROR: '{path}' は存在しません。"
            f"利用可能なファイル: {available if available else '(なし)'}"
        )

    def list_files(self) -> str:
        lines: list[str] = []
        if self.files:
            lines.append("[自分の成果物]")
            lines += [f"  {p} ({len(c.splitlines())}行)" for p, c in sorted(self.files.items())]
        if self.readonly_peers:
            lines.append("[参照可能な既存/他ワーカー成果物 (read_file で読める)]")
            lines += [
                f"  {p} ({len(c.splitlines())}行)"
                for p, c in sorted(self.readonly_peers.items())
            ]
        return "\n".join(lines) if lines else "(ファイルはまだありません)"

    # ------------------------------------------------------------------
    # LangChain ツールの生成
    # ------------------------------------------------------------------

    def as_tools(self, *, include_write: bool = True) -> list[BaseTool]:
        """
        このワークスペースにバインドされた LangChain ツール群を返す。

        include_write=False にすると read_file / list_files のみ (レビュー用)。
        """
        tools: list[BaseTool] = [
            StructuredTool.from_function(
                func=self.read_file,
                name="read_file",
                description="指定した相対パスのファイル全文を読み込む。整合性確認や既存コード修正の前に使う。",
                args_schema=_ReadArgs,
            ),
            StructuredTool.from_function(
                func=self.list_files,
                name="list_files",
                description="現在のワークスペースにあるファイル一覧 (パスと行数) を返す。",
                args_schema=_ListArgs,
            ),
        ]
        if include_write:
            tools.insert(
                0,
                StructuredTool.from_function(
                    func=self.write_file,
                    name="write_file",
                    description=(
                        "ファイルを作成/上書きする。同じパスへ再度書くと上書き。"
                        "成果物はすべてこのツールで書き出すこと。"
                    ),
                    args_schema=_WriteArgs,
                ),
            )
        return tools
