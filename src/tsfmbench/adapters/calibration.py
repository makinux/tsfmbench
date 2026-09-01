"""Shared empirical ratio calibration for realized-variance forecasts."""

from __future__ import annotations

from collections import deque
from collections.abc import Hashable, Iterable
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

PROBABILITIES = np.arange(0.1, 1.0, 0.1, dtype="float64")


def variance_ratio_sample(forecasts: Any, realized: Any) -> np.ndarray:
    """Return valid pre-origin ratios ``realized / forecast``."""

    f = np.asarray(forecasts, dtype="float64").reshape(-1)
    rv = np.asarray(realized, dtype="float64").reshape(-1)
    if f.size != rv.size:
        raise ValueError("forecast and realized calibration arrays must have equal length")
    valid = np.isfinite(f) & np.isfinite(rv) & (f > 0) & (rv > 0)
    # Division can still overflow even when both operands are finite (for
    # example, a subnormal forecast and an ordinary realized variance).  Such
    # an infinity makes numpy's interpolated upper quantiles partly NaN.  A
    # calibration pair is valid only when the *ratio itself* is finite.
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        ratios = rv[valid] / f[valid]
    return ratios[np.isfinite(ratios) & (ratios > 0)]


@dataclass
class _OrderNode:
    key: float
    count: int = 1
    height: int = 1
    size: int = 1
    left: _OrderNode | None = None
    right: _OrderNode | None = None


def _height(node: _OrderNode | None) -> int:
    return node.height if node is not None else 0


def _size(node: _OrderNode | None) -> int:
    return node.size if node is not None else 0


def _refresh(node: _OrderNode) -> _OrderNode:
    node.height = 1 + max(_height(node.left), _height(node.right))
    node.size = node.count + _size(node.left) + _size(node.right)
    return node


def _rotate_left(node: _OrderNode) -> _OrderNode:
    root = node.right
    assert root is not None
    node.right = root.left
    root.left = _refresh(node)
    return _refresh(root)


def _rotate_right(node: _OrderNode) -> _OrderNode:
    root = node.left
    assert root is not None
    node.left = root.right
    root.right = _refresh(node)
    return _refresh(root)


def _balance(node: _OrderNode) -> _OrderNode:
    _refresh(node)
    tilt = _height(node.left) - _height(node.right)
    if tilt > 1:
        assert node.left is not None
        if _height(node.left.left) < _height(node.left.right):
            node.left = _rotate_left(node.left)
        return _rotate_right(node)
    if tilt < -1:
        assert node.right is not None
        if _height(node.right.right) < _height(node.right.left):
            node.right = _rotate_right(node.right)
        return _rotate_left(node)
    return node


def _insert(node: _OrderNode | None, key: float) -> _OrderNode:
    if node is None:
        return _OrderNode(key)
    if key < node.key:
        node.left = _insert(node.left, key)
    elif key > node.key:
        node.right = _insert(node.right, key)
    else:
        node.count += 1
        return _refresh(node)
    return _balance(node)


def _minimum(node: _OrderNode) -> _OrderNode:
    while node.left is not None:
        node = node.left
    return node


def _discard(node: _OrderNode | None, key: float, *, all_counts: bool = False) -> _OrderNode | None:
    if node is None:
        raise KeyError(key)
    if key < node.key:
        node.left = _discard(node.left, key, all_counts=all_counts)
    elif key > node.key:
        node.right = _discard(node.right, key, all_counts=all_counts)
    elif node.count > 1 and not all_counts:
        node.count -= 1
        return _refresh(node)
    elif node.left is None:
        return node.right
    elif node.right is None:
        return node.left
    else:
        successor = _minimum(node.right)
        node.key, node.count = successor.key, successor.count
        node.right = _discard(node.right, successor.key, all_counts=True)
    return _balance(node)


def _kth(node: _OrderNode, index: int) -> float:
    left_size = _size(node.left)
    if index < left_size:
        assert node.left is not None
        return _kth(node.left, index)
    if index < left_size + node.count:
        return node.key
    assert node.right is not None
    return _kth(node.right, index - left_size - node.count)


class RollingRatioCalibration:
    """Incremental fixed-window empirical variance-ratio distribution.

    Pair insertion/removal and order-statistic lookup are O(log n).  Pair
    identities are retained even for invalid observations so that advancing a
    window removes exactly the intended old pair without ever converting a
    partly-invalid sample into a partly-null forecast row.
    """

    def __init__(self, *, min_pairs: int = 60) -> None:
        self.min_pairs = int(min_pairs)
        self._pairs: deque[tuple[Hashable, float | None]] = deque()
        self._root: _OrderNode | None = None

    @property
    def pair_count(self) -> int:
        return _size(self._root)

    @property
    def first_id(self) -> Hashable | None:
        return self._pairs[0][0] if self._pairs else None

    @property
    def last_id(self) -> Hashable | None:
        return self._pairs[-1][0] if self._pairs else None

    @staticmethod
    def _ratio(forecast: float, realized: float) -> float | None:
        if not np.isfinite(forecast) or not np.isfinite(realized) or forecast <= 0 or realized <= 0:
            return None
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            ratio = float(realized / forecast)
        return ratio if np.isfinite(ratio) and ratio > 0 else None

    def append(self, identity: Hashable, forecast: float, realized: float) -> None:
        if self._pairs and identity <= self._pairs[-1][0]:
            raise ValueError("calibration pair identities must be strictly increasing")
        ratio = self._ratio(float(forecast), float(realized))
        self._pairs.append((identity, ratio))
        if ratio is not None:
            self._root = _insert(self._root, ratio)

    def drop_before(self, identity: Hashable) -> None:
        while self._pairs and self._pairs[0][0] < identity:
            _, ratio = self._pairs.popleft()
            if ratio is not None:
                self._root = _discard(self._root, ratio)

    def clear(self) -> None:
        self._pairs.clear()
        self._root = None

    def rebuild(self, pairs: Iterable[tuple[Hashable, float, float]]) -> None:
        self.clear()
        for identity, forecast, realized in pairs:
            self.append(identity, forecast, realized)

    def ratios_quantile(self, probabilities: Any = PROBABILITIES) -> np.ndarray:
        probs = np.asarray(probabilities, dtype="float64")
        count = self.pair_count
        if count < self.min_pairs:
            return np.full(probs.shape, np.nan, dtype="float64")
        assert self._root is not None
        result = np.empty(probs.shape, dtype="float64")
        for output_index, probability in np.ndenumerate(probs):
            position = float(probability) * (count - 1)
            lower = int(np.floor(position))
            upper = int(np.ceil(position))
            low_value = _kth(self._root, lower)
            high_value = _kth(self._root, upper)
            result[output_index] = low_value + (position - lower) * (high_value - low_value)
        return result

    def calibrated(self, forecast: float, probabilities: Any = PROBABILITIES) -> np.ndarray:
        return float(forecast) * self.ratios_quantile(probabilities)


def calibrated_rv_quantiles(
    forecast: float,
    past_forecasts: Any,
    past_realized: Any,
    *,
    min_pairs: int = 60,
    probabilities: Any = PROBABILITIES,
) -> np.ndarray:
    """Scale empirical RV/forecast ratio quantiles by a variance forecast.

    This intentionally calibrates *variance ratios*.  Squared return
    quantiles are neither accepted nor used anywhere in the benchmark.
    """

    ratios = variance_ratio_sample(past_forecasts, past_realized)
    probs = np.asarray(probabilities, dtype="float64")
    if ratios.size < int(min_pairs):
        return np.full(probs.shape, np.nan, dtype="float64")
    return float(forecast) * np.quantile(ratios, probs)


def ratio_quantiles(
    forecast: float, forecasts: Any, realized: Any, *, min_pairs: int = 60
) -> np.ndarray:
    """Backward-friendly alias for :func:`calibrated_rv_quantiles`."""

    return calibrated_rv_quantiles(forecast, forecasts, realized, min_pairs=min_pairs)


def calibration_pairs_previous(series: pd.DataFrame, h: int, target: str) -> tuple[np.ndarray, np.ndarray]:
    """Build causal NaivePrev forecasts and matching realized targets."""

    values = pd.to_numeric(series["y"], errors="coerce").to_numpy(dtype="float64")
    if target == "sum" and h > 1:
        offset = len(values) % h
        blocks = np.asarray(
            [values[start : start + h].sum() for start in range(offset, len(values), h) if start + h <= len(values)],
            dtype="float64",
        )
        return blocks[:-1], blocks[1:]
    return values[:-1], values[1:]
