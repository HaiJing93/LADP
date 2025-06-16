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
    "compute_portfolio_metrics_from_excel",
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
    print("printing out _ensure_returns: ", returns)
    return returns.dropna()


# --------------------------------------------------------------------------- #
# Max draw-down                                                               #
# --------------------------------------------------------------------------- #


def max_drawdown(
    series: Sequence[float | int],
    *,
    is_prices: bool = True,
) -> float:
    """Return the maximum peak-to-trough draw-down as a **negative decimal**.

    If *is_prices* is False, the numbers are interpreted as arithmetic returns
    and converted to an equity curve before the draw-down calculation.
    """
    if series is None:
        return float("nan")

    prices = np.asarray(series, dtype="float64")

    if not is_prices:
        # Build a price curve from return series
        prices = np.cumprod(1.0 + prices)

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
    periods_per_year: int | None = None,
    risk_free_rate: float = 0.0,  # placeholder, unused
    returns_are_percent: bool | None = False,
    dates: Sequence[str | pd.Timestamp] | None = None,
) -> Mapping[str, float]:
    """Return cumulative, annualised return and annualised volatility.

    If ``periods_per_year`` is ``None`` and ``dates`` are supplied, the function
    will attempt to infer the sampling frequency by examining the median spacing
    between consecutive dates. Common frequencies are mapped to 1 (yearly), 12
    (monthly) and 252 (daily). When neither ``periods_per_year`` nor ``dates``
    are provided, the length based heuristic from the original implementation is
    used.
    """

    returns_series = _ensure_returns(
        series,
        is_prices=is_prices,
        returns_are_percent=bool(returns_are_percent),
    )

    if periods_per_year is None:
        if dates is not None:
            ds = pd.to_datetime(list(dates), errors="coerce")
            ds = ds.dropna()
            if len(ds) > 1:
                med_delta = ds.sort_values().diff().median()
                if pd.notna(med_delta):
                    days = med_delta / pd.Timedelta(days=1)
                    if 350 <= days <= 370:
                        periods_per_year = 1
                    elif 27 <= days <= 31:
                        periods_per_year = 12
                    elif 0.5 <= days <= 1.5:
                        periods_per_year = 252

        if periods_per_year is None:
            n = len(returns_series)
            periods_per_year = 1 if n <= 12 else 12 if n <= 60 else 252

    if returns_series.empty:
        return {
            "cumulative_return": math.nan,
            "annualized_return": math.nan,
            "annualized_volatility": math.nan,
            "max_drawdown": math.nan,
        }

    cumulative_return = (1.0 + returns_series).prod() - 1.0

    n_periods = len(returns_series)
    geometric_mean = (1.0 + cumulative_return) ** (1.0 / n_periods) - 1.0
    annualized_return = (1.0 + geometric_mean) ** periods_per_year - 1.0
    
    annualized_volatility = returns_series.std(ddof=0) * math.sqrt(periods_per_year)

    if is_prices:
        mdd = max_drawdown(series, is_prices=True)
    else:
        mdd = max_drawdown(returns_series, is_prices=False)

    return {
        "cumulative_return": cumulative_return,
        "annualized_return": annualized_return,
        "annualized_volatility": annualized_volatility,
        "max_drawdown": mdd,
    }


def compute_portfolio_metrics_from_excel(
    file: str | bytes,
    *,
    sheet: str | int | None = 0,
    is_prices: bool = True,
    periods_per_year: int | None = None,
    risk_free_rate: float = 0.0,
    returns_are_percent: bool | None = False,
) -> Mapping[str, float]:
    """Read an Excel sheet (first column dates, second values) and compute metrics."""
    df = pd.read_excel(file, sheet_name=sheet)
    if df.shape[1] < 2:
        raise ValueError("Excel sheet must have at least two columns")

    dates = pd.to_datetime(df.iloc[:, 0], errors="coerce")
    values = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    mask = dates.notna() & values.notna()
    dates = dates.loc[mask]
    values = values.loc[mask]

    return compute_portfolio_metrics(
        values.tolist(),
        is_prices=is_prices,
        periods_per_year=periods_per_year,
        risk_free_rate=risk_free_rate,
        returns_are_percent=returns_are_percent,
        dates=dates.tolist(),
    )
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

