"""
generate_diagram.py — Mermaid アーキテクチャ図の自動生成スクリプト。

使い方:
    python tools/generate_diagram.py

出力先: docs/architecture.md

【更新フロー】
  1. graph/diagram_spec.py の NODES / EDGES / STATE_FIELDS 等を更新する
  2. このスクリプトを実行する
  3. docs/architecture.md が自動再生成される
  4. Git にコミットする

このスクリプト自体は変更しない。
図の内容は graph/diagram_spec.py だけを編集すること。
"""

from __future__ import annotations

import importlib.util
import textwrap
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# diagram_spec.py をパッケージ初期化を経由せず直接ロード
# (graph/__init__.py が langchain_core を必要とするため)
_spec_path = ROOT / "graph" / "diagram_spec.py"
_spec = importlib.util.spec_from_file_location("diagram_spec", _spec_path)
_mod  = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)                   # type: ignore[union-attr]

NODES               = _mod.NODES
EDGES               = _mod.EDGES
STATE_FIELDS        = _mod.STATE_FIELDS
REVIEW_LOOP         = _mod.REVIEW_LOOP
DIRECTORY_STRUCTURE = _mod.DIRECTORY_STRUCTURE
SYSTEM_NAME         = _mod.SYSTEM_NAME
SYSTEM_VERSION      = _mod.SYSTEM_VERSION

OUTPUT_PATH = ROOT / "docs" / "architecture.md"

# ─────────────────────────────────────────────────────────────────────────────
# レイヤー設定
# ─────────────────────────────────────────────────────────────────────────────

LAYER_META: dict[str, dict] = {
    "management": {"label": "Management Layer",  "style": "fill:#ffecd2,stroke:#e67e22"},
    "worker":     {"label": "Worker Layer",      "style": "fill:#d5f5e3,stroke:#27ae60"},
    "quality":    {"label": "Quality Gate",      "style": "fill:#fde8e8,stroke:#e74c3c"},
    "delivery":   {"label": "Delivery",          "style": "fill:#f8f9fa,stroke:#7f8c8d"},
}

# ─────────────────────────────────────────────────────────────────────────────
# ヘルパー
# ─────────────────────────────────────────────────────────────────────────────

def _node_label(node: dict) -> str:
    return f'{node["id"]}["{node["label"]}\n{node["role"]}"]'


def _edge_arrow(kind: str) -> str:
    return {
        "normal":        "-->",
        "conditional":   "-->",
        "send_parallel": "==>",
        "optional":      "-.->",
    }.get(kind, "-->")


# ─────────────────────────────────────────────────────────────────────────────
# 図1: システム全体フローチャート
# ─────────────────────────────────────────────────────────────────────────────

def build_system_flowchart() -> str:
    lines: list[str] = ["```mermaid", "flowchart TD"]

    # subgraph per layer
    layers: dict[str, list[dict]] = {}
    for n in NODES:
        layers.setdefault(n["layer"], []).append(n)

    for layer_key, meta in LAYER_META.items():
        members = layers.get(layer_key, [])
        if not members:
            continue
        lines.append(f'    subgraph {layer_key.upper()}["{meta["label"]}"]')
        for n in members:
            label_lines = n["label"] + "\\n" + n["role"]
            lines.append(f'        {n["id"]}["{label_lines}"]')
        lines.append("    end")

    # START / END 仮想ノード
    lines.append('    START(["🚀 START"])')
    lines.append('    END(["✅ END"])')

    # エッジ
    for e in EDGES:
        arrow = _edge_arrow(e["kind"])
        label = f'|"{e["label"]}"|' if e["label"] else ""
        lines.append(f'    {e["from"]} {arrow}{label} {e["to"]}')

    # スタイル
    for layer_key, meta in LAYER_META.items():
        members = layers.get(layer_key, [])
        for n in members:
            lines.append(f'    style {n["id"]} {meta["style"]}')

    lines.append("```")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 図2: レビューループ シーケンス図
# ─────────────────────────────────────────────────────────────────────────────

def build_review_sequence() -> str:
    max_loops = REVIEW_LOOP["max_loops"]
    fix_targets = " / ".join(REVIEW_LOOP["fix_targets"])

    return textwrap.dedent(f"""\
    ```mermaid
    sequenceDiagram
        autonumber
        participant PM  as ProjectManager
        participant W   as Workers<br/>({fix_targets})
        participant CR  as CodeReview
        participant RM  as ReviewManager
        participant WR  as Writer

        PM->>W: 仕様・指示を送信 (Send API 並列)
        activate W
        W-->>CR: 実装成果物 (収束)
        deactivate W

        loop 最大 {max_loops} 回
            activate CR
            CR->>RM: レビューフィードバック + fix_targets
            deactivate CR
            activate RM
            alt 問題あり かつ loop_count < {max_loops}
                RM->>W: 修正指示 (Send API 並列)
                activate W
                Note over RM: review_loop_count ++
                W-->>CR: 修正済み成果物
                deactivate W
            else 問題なし または loop_count >= {max_loops}
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
    """).rstrip()


# ─────────────────────────────────────────────────────────────────────────────
# 図3: エージェント役割一覧 (マインドマップ)
# ─────────────────────────────────────────────────────────────────────────────

def build_agent_mindmap() -> str:
    lines = ["```mermaid", "mindmap", f"  root(({SYSTEM_NAME}))"]

    layer_names = {
        "management": "Management",
        "worker":     "Workers",
        "quality":    "Quality Gate",
        "delivery":   "Delivery",
    }
    layers: dict[str, list[dict]] = {}
    for n in NODES:
        layers.setdefault(n["layer"], []).append(n)

    for layer_key, label in layer_names.items():
        members = layers.get(layer_key, [])
        if not members:
            continue
        lines.append(f"    {label}")
        for n in members:
            lines.append(f"      {n['label']}")
            lines.append(f"        {n['role']}")

    lines.append("```")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 図4: AgentState データフロー
# ─────────────────────────────────────────────────────────────────────────────

def build_state_flow() -> str:
    lines = ["```mermaid", "flowchart LR"]

    # writer → field のクラスタ
    writers: dict[str, list[dict]] = {}
    for f in STATE_FIELDS:
        writers.setdefault(f["writer"], []).append(f)

    writer_order = [
        "input", "project_manager", "tool_specialist",
        "backend", "frontend", "database",
        "code_review", "review_manager", "writer", "all",
    ]

    for w in writer_order:
        fields = writers.get(w, [])
        if not fields:
            continue
        lines.append(f'    subgraph {w.replace(" ", "_")}["{w}"]')
        for f in fields:
            safe_id = f["field"].replace(" ", "_")
            lines.append(f'        {safe_id}["{f["field"]}<br/><i>{f["type"]}</i>"]')
        lines.append("    end")

    lines.append("```")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 図5: @tool カタログ
# ─────────────────────────────────────────────────────────────────────────────

def build_tool_table() -> str:
    rows = ["| エージェント | 主な処理 / 出力 | 数 |", "|---|---|---|"]
    for n in NODES:
        tools_str = " / ".join(f"`{t}`" for t in n["tools"])
        rows.append(f'| **{n["label"]}** | {tools_str} | {len(n["tools"])} |')
    return "\n".join(rows)


# ─────────────────────────────────────────────────────────────────────────────
# 図6: ディレクトリ構造
# ─────────────────────────────────────────────────────────────────────────────

def build_directory_tree() -> str:
    lines = ["```", f"{ROOT.name}/"]
    prev_parts: list[str] = []

    for path_str, desc in DIRECTORY_STRUCTURE:
        parts = path_str.split("/")
        depth = len(parts) - 1
        indent = "    " * depth
        filename = parts[-1]

        # ディレクトリ区切り線
        if depth > 0 and (not prev_parts or parts[0] != prev_parts[0]):
            lines.append("│")
        prev_parts = parts

        star = " ★" if "★" in desc else ""
        clean_desc = desc.replace("★ ", "")
        lines.append(f"{indent}├── {filename:<40} # {clean_desc}{star}")

    lines.append("```")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Markdownドキュメント組み立て
# ─────────────────────────────────────────────────────────────────────────────

def build_markdown() -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    total_tools = sum(len(n["tools"]) for n in NODES)

    sections = [
        f"# {SYSTEM_NAME} — Architecture",
        f"> **Version:** {SYSTEM_VERSION}  |  **Generated:** {now}  |  **Source:** `graph/diagram_spec.py`",
        "",
        "> [!WARNING]",
        "> このファイルは自動生成です。直接編集しないでください。",
        "> 変更は `graph/diagram_spec.py` を更新してから `python tools/generate_diagram.py` を実行してください。",
        "",
        "---",

        "## 1. システム全体フロー",
        "",
        build_system_flowchart(),
        "",
        "**凡例**",
        "| 矢印 | 意味 |",
        "|---|---|",
        "| `-->` | 通常遷移 |",
        "| `==>` | Send API 並列実行 |",

        "---",

        "## 2. コードレビューループ シーケンス",
        "",
        f"> 実装 ↔ レビュー のループは最大 **{REVIEW_LOOP['max_loops']} 回** に制限されます。",
        "",
        build_review_sequence(),

        "---",

        "## 3. エージェント役割 マインドマップ",
        "",
        build_agent_mindmap(),

        "---",

        "## 4. AgentState データフロー",
        "",
        "> 各フィールドがどのエージェントによって書き込まれるかを示します。",
        "",
        build_state_flow(),
        "",
        "### State フィールド一覧",
        "",
        "| フィールド | 型 | 書き込みノード | 説明 |",
        "|---|---|---|---|",
        *[
            f'| `{f["field"]}` | `{f["type"]}` | `{f["writer"]}` | {f["desc"]} |'
            for f in STATE_FIELDS
        ],

        "---",

        "## 5. ノード別 主な処理 / 出力",
        "",
        f"> 全ノード合計 **{total_tools} 処理項目**",
        "",
        build_tool_table(),

        "---",

        "## 6. ディレクトリ構造",
        "",
        build_directory_tree(),

        "---",

        "## 7. 更新手順",
        "",
        "システムにエージェント・ノード・ステートを追加したときの手順:",
        "",
        "```bash",
        "# 1. diagram_spec.py を更新 (NODES / EDGES / STATE_FIELDS)",
        "vim graph/diagram_spec.py",
        "",
        "# 2. Mermaid図を再生成",
        "python tools/generate_diagram.py",
        "",
        "# 3. コミット",
        'git add graph/diagram_spec.py docs/architecture.md',
        'git commit -m "docs: アーキテクチャ図更新"',
        "```",
        "",
        "---",
        "",
        f"*Auto-generated by `tools/generate_diagram.py` — {SYSTEM_NAME} v{SYSTEM_VERSION}*",
    ]

    return "\n".join(sections) + "\n"


# ─────────────────────────────────────────────────────────────────────────────
# エントリポイント
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    content = build_markdown()
    OUTPUT_PATH.write_text(content, encoding="utf-8")
    print(f"✅ Generated: {OUTPUT_PATH.relative_to(ROOT)}")
    print(f"   Nodes   : {len(NODES)}")
    print(f"   Edges   : {len(EDGES)}")
    print(f"   Tools   : {sum(len(n['tools']) for n in NODES)}")
    print(f"   Version : {SYSTEM_VERSION}")


if __name__ == "__main__":
    main()
