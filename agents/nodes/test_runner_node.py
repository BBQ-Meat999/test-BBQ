"""
TestRunnerNode — 生成されたコードを実際に実行して検証結果を収集する。

Workers が生成した全ファイルを一時ディレクトリへ書き出し、
pytest / ruff / mypy を subprocess で実行して結果を test_results に格納する。
このノードは LLM を使わず、決定論的にツールを実行するだけ (常に Haiku 割当だが実質未使用)。
CodeReview は静的レビュー + ここで得た実行結果の両方を参照する。
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage

from agents.Agent_Node import AgentNode

# subprocess のタイムアウト (秒) — 生成コードが無限ループしても全体を止めない
_TIMEOUT = 120


class TestRunnerNode(AgentNode):
    """テスト実行専門エージェント (純 Python 実行)。"""

    node_name = "test_runner"

    # ------------------------------------------------------------------
    # File collection
    # ------------------------------------------------------------------

    def _collect_all_files(self, state: dict[str, Any]) -> dict[str, str]:
        """全エージェントの成果物ファイルを一つの辞書にまとめる。"""
        merged: dict[str, str] = {}
        for key in ("tool_spec_files", "backend_files", "frontend_files", "database_files"):
            merged.update(state.get(key) or {})
        return merged

    # ------------------------------------------------------------------
    # Subprocess helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _run(cmd: list[str], cwd: str) -> subprocess.CompletedProcess[str] | None:
        """コマンドを実行する。ツール未インストール時は None を返す。"""
        try:
            return subprocess.run(
                cmd, cwd=cwd, capture_output=True, text=True, timeout=_TIMEOUT
            )
        except FileNotFoundError:
            return None
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(cmd, returncode=124, stdout="", stderr="timeout")

    @staticmethod
    def _parse_pytest(output: str) -> dict[str, int]:
        """pytest の終了サマリー行から passed/failed/errors を抽出する。"""
        counts = {"passed": 0, "failed": 0, "errors": 0}
        for key in counts:
            m = re.search(rf"(\d+) {key}", output)
            if m:
                counts[key] = int(m.group(1))
        return counts

    def _run_pytest(self, root: Path) -> dict[str, Any]:
        has_tests = any(
            p.name.startswith("test_") or p.name.endswith("_test.py")
            for p in root.rglob("*.py")
        )
        if not has_tests:
            return {"ran": False, "passed": 0, "failed": 0, "errors": 0,
                    "success": True, "output": "テストファイルなし — スキップ"}
        proc = self._run(
            [sys.executable, "-m", "pytest", "--tb=short", "-q", str(root)], str(root)
        )
        if proc is None:
            return {"ran": False, "passed": 0, "failed": 0, "errors": 0,
                    "success": True, "output": "pytest 未インストール — スキップ"}
        out = (proc.stdout or "") + (proc.stderr or "")
        counts = self._parse_pytest(out)
        return {
            "ran": True,
            **counts,
            "success": proc.returncode == 0,
            "output": out[-4000:],
        }

    def _run_ruff(self, root: Path) -> dict[str, Any]:
        proc = self._run(["ruff", "check", str(root)], str(root))
        if proc is None:
            return {"ran": False, "clean": True, "output": "ruff 未インストール — スキップ"}
        out = (proc.stdout or "") + (proc.stderr or "")
        return {"ran": True, "clean": proc.returncode == 0, "output": out[-2000:]}

    def _run_mypy(self, root: Path) -> dict[str, Any]:
        proc = self._run(["mypy", "--ignore-missing-imports", str(root)], str(root))
        if proc is None:
            return {"ran": False, "clean": True, "output": "mypy 未インストール — スキップ"}
        out = (proc.stdout or "") + (proc.stderr or "")
        return {"ran": True, "clean": proc.returncode == 0, "output": out[-2000:]}

    # ------------------------------------------------------------------
    # Node entry point
    # ------------------------------------------------------------------

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """全成果物を一時ディレクトリに展開して検証し test_results を更新する。"""
        files = self._collect_all_files(state)

        if not files:
            results = {"passed": 0, "failed": 0, "errors": 0, "success": False,
                       "pytest": {}, "ruff": {}, "mypy": {}, "output": "成果物なし"}
            return {
                "messages": [AIMessage(content="[test_runner] 成果物なし — 検証スキップ")],
                "test_results": results,
            }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel_path, code in files.items():
                # パストラバーサル防止: 一時ディレクトリ外への書き込みを拒否
                dest = (root / rel_path).resolve()
                if not str(dest).startswith(str(root.resolve())):
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(code, encoding="utf-8")

            pytest_res = self._run_pytest(root)
            ruff_res   = self._run_ruff(root)
            mypy_res   = self._run_mypy(root)

        success = pytest_res.get("success", False) and ruff_res.get("clean", True)
        results = {
            "passed":  pytest_res.get("passed", 0),
            "failed":  pytest_res.get("failed", 0),
            "errors":  pytest_res.get("errors", 0),
            "success": success,
            "pytest":  pytest_res,
            "ruff":    ruff_res,
            "mypy":    mypy_res,
            "output":  pytest_res.get("output", ""),
        }
        summary = (
            f"[test_runner] pytest passed={results['passed']} "
            f"failed={results['failed']} errors={results['errors']} "
            f"ruff_clean={ruff_res.get('clean')} mypy_clean={mypy_res.get('clean')}"
        )
        return {
            "messages": [AIMessage(content=summary)],
            "test_results": results,
        }
