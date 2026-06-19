"""
ModelSelector — 報奨金に基づきエージェントごとの最適 Claude モデルを選択する。

利益最大化の考え方:
  expected_profit = reward × delivery_success_rate - total_expected_api_cost

  total_expected_api_cost =
      Σ_node(avg_input_tok × input_rate + avg_output_tok × output_rate)
      × (1 + P(rework) × rework_cost_multiplier)

  安価なモデルほど per-call コストは低いが、コード品質が落ちて手戻りループが
  発生しやすくなる。手戻り 1 回 = Worker×4 + TestRunner + CodeReview + ReviewManager
  が再実行されるため実質コストは乗数的に増える。

選択戦略 (5 段階):
  HAIKU_ONLY         : 報奨金 < $30
  SMART_SMALL        : $30-$150   (管理・品質=Sonnet / Worker=Haiku)
  SONNET_ALL         : $150-$500
  SMART_LARGE        : $500-$2000 (管理・品質=Opus / Worker=Sonnet)
  OPUS_ALL           : $2000+
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# ─────────────────────────────────────────────────────────────────────────────
# モデル定義
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    input_cost_per_mtok: float   # USD / 100万入力トークン
    output_cost_per_mtok: float  # USD / 100万出力トークン
    rework_rate: float           # Worker 1ノードあたりの手戻り確率 (0-1)
    delivery_success_rate: float # クライアント受諾確率 (0-1)


MODELS: dict[str, ModelSpec] = {
    "haiku": ModelSpec(
        model_id             = "claude-haiku-4-5-20251001",
        input_cost_per_mtok  = 0.80,
        output_cost_per_mtok = 4.00,
        rework_rate          = 0.45,   # コード品質が低く手戻りが多い
        delivery_success_rate= 0.70,
    ),
    "sonnet": ModelSpec(
        model_id             = "claude-sonnet-4-6",
        input_cost_per_mtok  = 3.00,
        output_cost_per_mtok = 15.00,
        rework_rate          = 0.15,
        delivery_success_rate= 0.90,
    ),
    "opus": ModelSpec(
        model_id             = "claude-opus-4-8",
        input_cost_per_mtok  = 15.00,
        output_cost_per_mtok = 75.00,
        rework_rate          = 0.05,   # ほぼ完璧なコードを生成
        delivery_success_rate= 0.97,
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# ノード役割分類
# ─────────────────────────────────────────────────────────────────────────────

class NodeRole(Enum):
    MANAGEMENT = "management"   # 意思決定の中枢 — 品質への影響が最大
    QUALITY    = "quality"      # 品質ゲート — レビュー精度が手戻り率を左右
    WORKER     = "worker"       # 実装 — 本数が多く手戻り時の再実行コストが高い
    DELIVERY   = "delivery"     # 納品整形 — 最終成果物の品質を決定

NODE_ROLES: dict[str, NodeRole] = {
    "project_manager":  NodeRole.MANAGEMENT,
    "review_manager":   NodeRole.MANAGEMENT,
    "code_review":      NodeRole.QUALITY,
    "test_runner":      NodeRole.QUALITY,
    "backend":          NodeRole.WORKER,
    "frontend":         NodeRole.WORKER,
    "database":         NodeRole.WORKER,
    "tool_specialist":  NodeRole.WORKER,
    "writer":           NodeRole.DELIVERY,
}

# TestRunner は subprocess 実行が主体でほぼ LLM を使わないため常に Haiku
_FORCE_HAIKU_NODES = {"test_runner"}


# ─────────────────────────────────────────────────────────────────────────────
# 平均トークン使用量 (per call)
# ─────────────────────────────────────────────────────────────────────────────

AVG_INPUT_TOKENS: dict[str, int] = {
    "project_manager": 2_000,
    "backend":         3_500,
    "frontend":        3_500,
    "database":        2_500,
    "tool_specialist": 2_000,
    "test_runner":       500,
    "code_review":     6_000,
    "review_manager":  2_500,
    "writer":          7_000,
}

AVG_OUTPUT_TOKENS: dict[str, int] = {
    "project_manager": 1_500,
    "backend":         5_000,
    "frontend":        5_000,
    "database":        3_500,
    "tool_specialist": 2_500,
    "test_runner":       200,
    "code_review":     2_000,
    "review_manager":  1_000,
    "writer":          8_000,
}

WORKER_NODES = {"backend", "frontend", "database", "tool_specialist"}


# ─────────────────────────────────────────────────────────────────────────────
# 選択戦略定義
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Strategy:
    name: str
    description: str
    role_to_tier: dict[NodeRole, str]   # NodeRole → モデルキー


STRATEGIES: list[Strategy] = [
    Strategy(
        name        = "HAIKU_ONLY",
        description = "全ノード Haiku — 最小コスト・高リスク",
        role_to_tier= {r: "haiku" for r in NodeRole},
    ),
    Strategy(
        name        = "SMART_SMALL",
        description = "管理・品質=Sonnet / 実装=Haiku — バランス重視",
        role_to_tier= {
            NodeRole.MANAGEMENT: "sonnet",
            NodeRole.QUALITY:    "sonnet",
            NodeRole.WORKER:     "haiku",
            NodeRole.DELIVERY:   "sonnet",
        },
    ),
    Strategy(
        name        = "SONNET_ALL",
        description = "全ノード Sonnet — 安定品質",
        role_to_tier= {r: "sonnet" for r in NodeRole},
    ),
    Strategy(
        name        = "SMART_LARGE",
        description = "管理・品質=Opus / 実装=Sonnet — 高品質・効率的",
        role_to_tier= {
            NodeRole.MANAGEMENT: "opus",
            NodeRole.QUALITY:    "opus",
            NodeRole.WORKER:     "sonnet",
            NodeRole.DELIVERY:   "opus",
        },
    ),
    Strategy(
        name        = "OPUS_ALL",
        description = "全ノード Opus — 最高品質",
        role_to_tier= {r: "opus" for r in NodeRole},
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# 逆引きマップ: model_id → ModelSpec
# ─────────────────────────────────────────────────────────────────────────────

_MODEL_ID_TO_SPEC: dict[str, ModelSpec] = {
    spec.model_id: spec for spec in MODELS.values()
}

def _spec_by_id(model_id: str) -> ModelSpec:
    """model_id から ModelSpec を返す。未知の場合は Sonnet にフォールバック。"""
    return _MODEL_ID_TO_SPEC.get(model_id, MODELS["sonnet"])


# ─────────────────────────────────────────────────────────────────────────────
# コスト・利益計算
# ─────────────────────────────────────────────────────────────────────────────

def _node_call_cost(node: str, tier: str) -> float:
    """単一ノード 1 回呼び出しのAPIコスト (USD)。tier はモデルキー ('haiku' 等)。"""
    spec = MODELS[tier]
    input_tok  = AVG_INPUT_TOKENS.get(node, 2000)
    output_tok = AVG_OUTPUT_TOKENS.get(node, 1000)
    return (
        input_tok  / 1_000_000 * spec.input_cost_per_mtok
        + output_tok / 1_000_000 * spec.output_cost_per_mtok
    )


def _node_cost_by_model_id(node: str, model_id: str) -> float:
    """単一ノード 1 回呼び出しのAPIコスト (USD)。model_id ベース版。"""
    spec = _spec_by_id(model_id)
    input_tok  = AVG_INPUT_TOKENS.get(node, 2000)
    output_tok = AVG_OUTPUT_TOKENS.get(node, 1000)
    return (
        input_tok  / 1_000_000 * spec.input_cost_per_mtok
        + output_tok / 1_000_000 * spec.output_cost_per_mtok
    )


# ─────────────────────────────────────────────────────────────────────────────
# 修正ループコストのモデリング定数
# ─────────────────────────────────────────────────────────────────────────────

# 1回目の修正後、コードが改善されて2回目に手戻りが発生する確率の減衰係数
# 0.6 = 1回修正すると手戻り確率が元の60%に下がる (40%の問題が解決される)
_FIX_IMPROVEMENT_FACTOR: float = 0.6

# 2回目のループは入力トークンが増加する倍率
# 理由: Worker は「元コード + 1回目の修正指示 + 1回目の修正済みコード」を入力として受け取る
#       CodeReview も蓄積されたコードを全量レビューするため入力が膨らむ
_SECOND_LOOP_INPUT_MULTIPLIER: float = 1.3


def estimate_cost(
    assignments: dict[str, str],
    max_review_loops: int = 2,
) -> float:
    """
    ワークフロー全体の期待 API コスト (USD) を計算する。

    修正ループのコスト構造 (max_review_loops=2 の場合):
    ─────────────────────────────────────────────────────
    初回実行:
      PM → Workers(×4) → TestRunner → CodeReview → ReviewManager → Writer
      ↑ 全ノード 1 回ずつ

    1回目修正ループ (確率 p1 = rework_rate):
      Workers(×4) → TestRunner → CodeReview → ReviewManager
      → 問題解消なら Writer へ / 問題継続なら 2回目ループへ (loop_count=1)

    2回目修正ループ (確率 p1 × p2, p2 = p1 × FIX_IMPROVEMENT_FACTOR):
      Workers(×4) → TestRunner → CodeReview → ReviewManager → Writer (強制終了)
      ※ 入力コンテキストが膨らむため 1ループ目より高コスト
        (前回コード + 修正指示 が蓄積 → × SECOND_LOOP_INPUT_MULTIPLIER)

    間違いやすいポイント:
      × expected_loops = rework_rate × max_loops  ← 確率を単純掛けしているだけ
      ○ E[cost] = p1×cost_L1 + (p1×p2)×cost_L2  ← 条件付き確率で計算
    ─────────────────────────────────────────────────────
    """
    # ── 初回実行コスト ────────────────────────────────────────────────
    base_cost = sum(
        _node_cost_by_model_id(node, model_id)
        for node, model_id in assignments.items()
    )

    # ── 修正ループに関わるノードのコスト基準 ────────────────────────
    rework_nodes = list(WORKER_NODES) + ["test_runner", "code_review", "review_manager"]
    loop1_base_cost = sum(
        _node_cost_by_model_id(node, assignments.get(node, MODELS["sonnet"].model_id))
        for node in rework_nodes
    )

    # ── 1 回目の修正ループの期待コスト ────────────────────────────────
    worker_model_ids = [assignments.get(n, MODELS["sonnet"].model_id) for n in WORKER_NODES]
    p1 = max(_spec_by_id(mid).rework_rate for mid in worker_model_ids)

    rework_cost = p1 * loop1_base_cost

    # ── 2 回目の修正ループの期待コスト (max_review_loops >= 2 の場合のみ) ──
    if max_review_loops >= 2:
        # 1回目の修正後に問題が残る確率 (条件付き確率)
        p2 = p1 * _FIX_IMPROVEMENT_FACTOR
        # 2回目は前回コード+修正指示が蓄積されるため入力トークンが増える
        loop2_cost = loop1_base_cost * _SECOND_LOOP_INPUT_MULTIPLIER
        rework_cost += (p1 * p2) * loop2_cost

    return base_cost + rework_cost


# 役割ごとの重み: 納品品質への貢献度
_ROLE_WEIGHT: dict[NodeRole, float] = {
    NodeRole.MANAGEMENT: 0.25,  # PM・ReviewManager: 設計品質・修正精度
    NodeRole.QUALITY:    0.30,  # CodeReview: バグ検出精度が手戻りを左右
    NodeRole.WORKER:     0.35,  # Worker: 実コードの品質が最大の決定因子
    NodeRole.DELIVERY:   0.10,  # Writer: 整形品質、重要だが再現性が高い
}


def _weighted_success_rate(assignments: dict[str, str]) -> float:
    """
    役割重みを考慮した納品成功率の加重平均を計算する。

    min() でなく加重平均を使う理由:
      例えば SMART_SMALL (管理=Sonnet, 実装=Haiku) は
      管理精度が高いことで Haiku の弱点を一定カバーできる。
      min() だと管理ノードのモデルアップグレードが全く評価されない。
    """
    total_weight = 0.0
    weighted_sum = 0.0
    for node, role in NODE_ROLES.items():
        weight = _ROLE_WEIGHT.get(role, 0.0)
        model_id = assignments.get(node, MODELS["sonnet"].model_id)
        success = _spec_by_id(model_id).delivery_success_rate
        weighted_sum  += weight * success
        total_weight  += weight
    return weighted_sum / total_weight if total_weight > 0 else 0.0


def estimate_profit(
    reward_amount: float,
    assignments: dict[str, str],
    max_review_loops: int = 2,
) -> float:
    """
    期待利益 = 報奨金 × 加重納品成功率 - 期待APIコスト。

    加重納品成功率は役割の重要度を考慮:
      - 管理・品質ノードを高品質モデルにすると、
        実装ノードが安価でも品質改善効果がある
    """
    success_rate = _weighted_success_rate(assignments)
    cost = estimate_cost(assignments, max_review_loops)
    return reward_amount * success_rate - cost


# ─────────────────────────────────────────────────────────────────────────────
# メイン API
# ─────────────────────────────────────────────────────────────────────────────

class ModelSelector:
    """報奨金から最適モデル割当を選択するファサード。"""

    @staticmethod
    def select_assignments(
        reward_amount: float,
        max_review_loops: int = 2,
    ) -> dict:
        """
        期待利益を最大化するモデル割当を選択して返す。

        Returns
        -------
        dict with keys:
            model_assignments : dict[str, str]   node_name → model_id
            estimated_cost    : float             期待 API コスト (USD)
            estimated_profit  : float             期待利益 (USD)
            strategy_name     : str               選択された戦略名
            strategy_desc     : str               戦略の説明
        """
        best_strategy  = STRATEGIES[0]
        best_profit    = float("-inf")

        for strategy in STRATEGIES:
            assignments = ModelSelector._build_assignments(strategy)
            profit = estimate_profit(reward_amount, assignments, max_review_loops)
            if profit > best_profit:
                best_profit    = profit
                best_strategy  = strategy

        best_assignments = ModelSelector._build_assignments(best_strategy)
        cost = estimate_cost(best_assignments, max_review_loops)

        return {
            "model_assignments": best_assignments,
            "estimated_cost":    round(cost, 6),
            "estimated_profit":  round(best_profit, 6),
            "strategy_name":     best_strategy.name,
            "strategy_desc":     best_strategy.description,
        }

    @staticmethod
    def _build_assignments(strategy: Strategy) -> dict[str, str]:
        """Strategy の role_to_tier からノード別 model_id dict を生成する。"""
        result: dict[str, str] = {}
        for node, role in NODE_ROLES.items():
            if node in _FORCE_HAIKU_NODES:
                tier = "haiku"
            else:
                tier = strategy.role_to_tier.get(role, "sonnet")
            result[node] = MODELS[tier].model_id
        return result

    @staticmethod
    def summarize(reward_amount: float, max_review_loops: int = 2) -> str:
        """全戦略の比較サマリーを文字列で返す (デバッグ・ログ用)。"""
        lines = [
            f"報奨金: ${reward_amount:.2f}  |  最大レビューループ: {max_review_loops}回",
            f"{'戦略':<20} {'コスト(USD)':>12} {'期待利益(USD)':>14} {'説明'}",
            "-" * 80,
        ]
        for strategy in STRATEGIES:
            asgn   = ModelSelector._build_assignments(strategy)
            cost   = estimate_cost(asgn, max_review_loops)
            profit = estimate_profit(reward_amount, asgn, max_review_loops)
            lines.append(
                f"{strategy.name:<20} ${cost:>10.4f}  ${profit:>12.4f}  {strategy.description}"
            )
        return "\n".join(lines)
