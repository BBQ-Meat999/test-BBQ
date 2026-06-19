"""
FrontendNode — フロントエンド実装エージェント。

成果物は dict[str, str] (ファイルパス → コード) で返す。
messages の肥大化を防ぐため、コードは messages に含めない。
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from agents.Agent_Node import AgentNode


class FrontendNode(AgentNode):
    """
    フロントエンド専門エージェント。
    成果物は state["frontend_files"] (dict[str, str]) に格納する。
    """

    node_name = "frontend"

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @tool
    def design_ui(self, spec: str) -> dict[str, Any]:
        """
        クライアント仕様から UI 設計書を生成する。
        Returns:
            pages       : list[{"name": str, "components": list}]
            user_flows  : list[str]
            design_tokens: dict
        """
        ...

    @tool
    def write_html_css(self, design: dict, responsive: bool = True) -> dict[str, str]:
        """
        UI デザインからセマンティック HTML5 と CSS3 を生成する。
        Returns: {"src/index.html": "...", "src/styles/main.css": "...", ...}
        """
        ...

    @tool
    def generate_components(
        self, framework: str, component_list: list[str], design: dict
    ) -> dict[str, str]:
        """
        指定フレームワーク (React / Vue / Svelte 等) でコンポーネントを生成する。
        Returns: {"src/components/Button.tsx": "...", ...}
        """
        ...

    @tool
    def integrate_api(self, api_design: dict, frontend_files: dict[str, str]) -> dict[str, str]:
        """
        バックエンド API と接続する通信レイヤーを生成する。
        Returns: {"src/api/client.ts": "...", "src/hooks/useXxx.ts": "...", ...}
        """
        ...

    @tool
    def generate_build_config(self, framework: str) -> dict[str, str]:
        """
        ビルド設定 (Vite / Next.js 等) と package.json を生成する。
        Returns: {"package.json": "...", "vite.config.ts": "...", ...}
        """
        ...

    @tool
    def apply_fix(self, current_files: dict[str, str], fix_instruction: str) -> dict[str, str]:
        """修正指示を受けて既存ファイルを修正する。"""
        ...

    # ------------------------------------------------------------------
    # Node entry point
    # ------------------------------------------------------------------

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        response = self._invoke(state)

        fix_inst = state.get("fix_instructions", {}).get(self.node_name)
        existing = state.get("frontend_files", {})

        if fix_inst and existing:
            # TODO: apply_fix tool_call を実行
            frontend_files = existing  # stub
        else:
            # TODO: design_ui → generate_components → integrate_api → generate_build_config
            frontend_files: dict[str, str] = {}

        return {
            **state,
            "messages":       state["messages"] + [response],
            "frontend_files": frontend_files,
        }
