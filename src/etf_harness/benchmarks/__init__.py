"""Fixed-weight benchmarks; risk estimation belongs to later primitives."""

from collections.abc import Mapping, Sequence

from etf_harness.backtest.models import Allocation, AssetWeight


def sixty_forty(equity: str, government_bond: str) -> Allocation:
    """Caller declares asset roles; no real ETF universe is inferred."""
    return Allocation(
        assets=(
            AssetWeight(asset=equity, weight=0.6),
            AssetWeight(asset=government_bond, weight=0.4),
        ),
        cash_weight=0.0,
    )


def equal_weight(assets: Sequence[str]) -> Allocation:
    if not assets:
        raise ValueError("At least one asset is required")
    return Allocation(
        assets=tuple(AssetWeight(asset=asset, weight=1.0 / len(assets)) for asset in assets),
        cash_weight=0.0,
    )


def equal_sleeve(sleeves: Mapping[str, Sequence[str]]) -> Allocation:
    """Equal capital across explicit sleeves and equally across each sleeve's assets."""
    if not sleeves or any(not name.strip() or not assets for name, assets in sleeves.items()):
        raise ValueError("Nonempty named sleeves with at least one asset each are required")
    weights: list[AssetWeight] = []
    for assets in sleeves.values():
        weight = 1.0 / (len(sleeves) * len(assets))
        weights.extend(AssetWeight(asset=asset, weight=weight) for asset in assets)
    return Allocation(assets=tuple(weights), cash_weight=0.0)
