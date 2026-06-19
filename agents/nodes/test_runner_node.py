"""
TestRunnerNode — 生成されたコードを実際に実行してテスト結果を収集する。

Workers が生成したコードを一時ディレクトリに書き出し、
pytest を subprocess で実行して結果を AgentState に格納する。
CodeReview は静的レビュー + TestRunner の実行結果を両方参照する。
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from agents.Agent_Node import AgentNode


class TestRunnerNode(AgentNode):
    """
    テスト実行専門エージェント。

    責務:
      - 生成されたコード (*_files) を一時ディレクトリに書き出す
      - pytest / 静的解析ツールを subprocess で実行する
      - テスト結果 (pass/fail/coverage/errors) を test_results に格納する
      - 実行ログを code_review が参照できる形式で返す
    """

    node_name = "test_runner"

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @tool
    def write_files_to_tempdir(self, files: dict[str, str]) -> str:
        """
        ファイル辞書 {パス: コード} を一時ディレクトリに書き出す。
        Returns: 一時ディレクトリのパス文字列
        """
        ...

    @tool
    def run_pytest(self, project_dir: str, test_paths: list[str] | None = None) -> dict[str, Any]:
        """
        pytest を subprocess で実行しテスト結果を返す。
        Returns:
            passed   : int    合格テスト数
            failed   : int    失敗テスト数
            errors   : int    エラー数
            coverage : float  カバレッジ (%)
            output   : str    pytest 出力ログ
            success  : bool   全テスト合格か
        """
        ...

    @tool
    def run_ruff_check(self, project_dir: str) -> dict[str, Any]:
        """
        ruff で静的解析を実行する。
        Returns:
            violations : list[{"file": str, "line": int, "code": str, "message": str}]
            clean      : bool  違反なしか
        """
        ...

    @tool
    def run_mypy(self, project_dir: str) -> dict[str, Any]:
        """
        mypy で型チェックを実行する。
        Returns:
            errors : list[{"file": str, "line": int, "message": str}]
            clean  : bool
        """
        ...

    @tool
    def cleanup_tempdir(self, temp_dir: str) -> None:
        """一時ディレクトリを削除する。"""
        ...

    # ------------------------------------------------------------------
    # Internal helpers (実装時に使用)
    # ------------------------------------------------------------------

    def _collect_all_files(self, state: dict[str, Any]) -> dict[str, str]:
        """全エージェントの成果物ファイルを一つの辞書にまとめる。"""
        merged: dict[str, str] = {}
        for key in ("tool_spec_files", "backend_files", "frontend_files", "database_files"):
            merged.update(state.get(key) or {})
        return merged

    def _write_and_run(self, files: dict[str, str]) -> dict[str, Any]:
        """ファイルを書き出して pytest を実行する実装テンプレート。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel_path, code in files.items():
                dest = root / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(code, encoding="utf-8")
            # TODO: pytest を subprocess で実行してパース
            result = subprocess.run(
                ["python", "-m", "pytest", "--tb=short", "-q", str(root)],
                capture_output=True, text=True, cwd=str(root)
            )
        return {
            "output":  result.stdout + result.stderr,
            "success": result.returncode == 0,
            "passed":  0,  # TODO: parse from output
            "failed":  0,
            "errors":  0,
            "coverage": None,
        }

    # ------------------------------------------------------------------
    # Node entry point
    # ------------------------------------------------------------------

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        全成果物ファイルを収集して実行し test_results を更新する。
        """
        response = self._invoke(state)

        all_files = self._collect_all_files(state)

        # TODO: write_files_to_tempdir / run_pytest / run_ruff_check の tool_calls を実行
        test_results: dict[str, Any] = {
            "passed":   0,
            "failed":   0,
            "errors":   0,
            "coverage": None,
            "output":   "",
            "ruff":     {},
            "mypy":     {},
            "success":  False,
        }

        return {
            **state,
            "messages":    state["messages"] + [response],
            "test_results": test_results,
        }
