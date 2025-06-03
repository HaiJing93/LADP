# features/analytics/portfolio.py
"""
Portfolio performance metrics utilities (re-revised).

* Fix yearly_performance length-mismatch bug.
* NEW: add max_drawdown(series, is_prices=True) helper so the chatbot
  can answer “What’s the maximum draw-down?” directly.
"""

from __future__ import annotations

import math
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
import streamlit as st

__all__ = [
    "compute_portfolio_metrics",
    "render_metrics_table",
    "yearly_performance",
    "max_drawdown",
    "calculate_max_drawdown",
]

# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _to_series(data: Iterable[float | int], name: str = "value") -> pd.Series:
    """Convert *data* to a float Series (do **not** drop NA)."""
    return pd.Series(list(data), dtype="float64", name=name)


def _ensure_returns(
    series: Iterable[float | int],
    *,
    is_prices: bool,
    returns_are_percent: bool,
) -> pd.Series:
    """Return a **returns** Series (decimal) from *series* regardless of input."""
    s = _to_series(series)

    if is_prices:
        returns = s.pct_change()
    else:
        returns = s.copy()

    if returns_are_percent:
        returns = returns / 100.0

    return returns.dropna()


# --------------------------------------------------------------------------- #
# Max draw-down                                                               #
# --------------------------------------------------------------------------- #


def max_drawdown(series: Sequence[float | int], *, is_prices: bool = True) -> float:
    """
    Return the maximum peak-to-trough draw-down as a **negative decimal**.

    If *is_prices* is False, the numbers are interpreted as arithmetic returns
    and converted to an equity curve before the draw-down calculation.
    """
    if not series:
        return float("nan")

    prices = np.asarray(series, dtype="float64")

    if not is_prices:
        prices = np.cumprod(1.0 + prices)  # build price curve from returns

    peaks = np.maximum.accumulate(prices)
    drawdowns = (prices - peaks) / peaks
    return float(drawdowns.min())  # most negative value


# Simple wrapper so the tool schema can call this directly
def calculate_max_drawdown(
    series: Sequence[float | int],
    *,
    is_prices: bool = True,
) -> dict[str, float]:
    """Return {"max_drawdown": value} – convenient for LLM tool output."""
    return {"max_drawdown": max_drawdown(series, is_prices=is_prices)}


# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #


def compute_portfolio_metrics(
    series: Iterable[float | int],
    *,
    is_prices: bool = True,
    periods_per_year: int = 12,
    risk_free_rate: float = 0.0,  # placeholder, unused
    returns_are_percent: bool | None = False,
) -> Mapping[str, float]:
    """Return cumulative, annualised return and annualised volatility."""

    returns_series = _ensure_returns(
        series,
        is_prices=is_prices,
        returns_are_percent=bool(returns_are_percent),
    )

    if returns_series.empty:
        return {
            "cumulative_return": math.nan,
            "annualized_return": math.nan,
            "annualized_volatility": math.nan,
            "max_drawdown": math.nan,
        }

    cumulative_return = (1.0 + returns_series).prod() - 1.0

    n_periods = len(returns_series)
    annualized_return = (1.0 + cumulative_return) ** (
        periods_per_year / n_periods
    ) - 1.0

    annualized_volatility = returns_series.std(ddof=0) * math.sqrt(periods_per_year)

    mdd = max_drawdown(series, is_prices=is_prices)

    return {
        "cumulative_return": cumulative_return,
        "annualized_return": annualized_return,
        "annualized_volatility": annualized_volatility,
        "max_drawdown": mdd,
    }


# --------------------------------------------------------------------------- #
# Streamlit helper                                                            #
# --------------------------------------------------------------------------- #


def render_metrics_table(metrics: Mapping[str, float]) -> None:
    """Pretty-print *metrics* as a two-column table in Streamlit."""
    df = (
        pd.Series(metrics)
        .to_frame("value")
        .round(4)
        .rename_axis("metric")
        .reset_index()
    )

    pct_cols = {
        "cumulative_return",
        "annualized_return",
        "annualized_volatility",
        "max_drawdown",
    }
    df.loc[df["metric"].isin(pct_cols), "value"] = df.loc[
        df["metric"].isin(pct_cols), "value"
    ].apply(lambda x: f"{x * 100:.2f}%" if pd.notna(x) else "–")

    st.table(df.set_index("metric"))


# --------------------------------------------------------------------------- #
# Yearly performance                                                          #
# --------------------------------------------------------------------------- #


def yearly_performance(
    dates: Iterable[str | pd.Timestamp],
    returns: Iterable[float | int],
    *,
    returns_are_percent: bool | None = False,
) -> dict[int, float]:
    """Aggregate period returns into calendar-year total returns."""
    df = pd.DataFrame({"date": list(dates), "ret": list(returns)})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "ret"])

    if bool(returns_are_percent):
        df["ret"] = df["ret"] / 100.0

    grouped = (1.0 + df["ret"]).groupby(df["date"].dt.year).prod() - 1.0
    return grouped.to_dict()