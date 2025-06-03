# features/marketdata/yahoo.py
"""
Lightweight wrappers around yfinance for live quotes and price history.
Requires yfinance >= 0.2.6
"""

from __future__ import annotations

from functools import lru_cache
from datetime import datetime
from typing import Literal, List, Tuple, Dict

import numpy as np
import pandas as pd
import yfinance as yf


Interval = Literal["1m", "5m", "15m", "30m", "60m", "1d", "1wk", "1mo"]


# ----------------------------------------------------------------------- #
# Helpers                                                                 #
# ----------------------------------------------------------------------- #

@lru_cache(maxsize=256)
def _fetch_history_cached(
    ticker: str,
    period: str = "1y",
    interval: Interval = "1d",
) -> pd.DataFrame:
    """One Yahoo call per (ticker, period, interval) per worker session."""
    df = yf.download(
        ticker,
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False,
    )
    if df.empty:
        raise ValueError(f"No price data returned for {ticker!r}")
    return df


def _to_float(x) -> float:
    """
    Coerce a variety of Yahoo-return types to plain float.

    Handles scalars, 0-dim numpy, 1-element or multi-element pandas Series,
    and even small python lists/tuples/arrays by recursively unboxing the first
    numeric element. Falls back to NaN when conversion isn’t possible.
    """
    import numbers
    import numpy as np
    import pandas as pd

    # 1) Simple numeric scalar
    if isinstance(x, numbers.Number):
        return float(x)

    # 2) 0-dim numpy array (np.ndarray([]))
    if isinstance(x, np.ndarray) and x.ndim == 0:
        return float(x.item())

    # 3) pandas Series (length 1  *or* multi-element — pick first numeric)
    if isinstance(x, pd.Series):
        if x.empty:
            return float("nan")
        return _to_float(x.iloc[0])

    # 4) list / tuple / 1-dim numpy — recurse on first element
    if isinstance(x, (list, tuple, np.ndarray)):
        if len(x) == 0:
            return float("nan")
        return _to_float(x[0])

    # 5) Anything else → NaN (won’t crash downstream calcs)
    return float("nan")


# ----------------------------------------------------------------------- #
# Public helpers                                                          #
# ----------------------------------------------------------------------- #

def get_stock_history(
    ticker: str,
    period: str = "1y",
    interval: Interval = "1d",
    col: str = "Adj Close",
) -> list[tuple[str, float]]:
    """
    Fetch historical prices via Ticker.history().  Guaranteed ≥2 rows
    when data exists; falls back to .download('max') then slices.
    """
    import pandas as pd
    import numpy as np
    ticker = ticker.upper()

    def _pull_hist(p: str, i: str) -> pd.Series:
        df = yf.Ticker(ticker).history(period=p, interval=i, auto_adjust=False)
        df.index = pd.to_datetime(df.index, errors="coerce")
        s = (df[col] if col in df else df["Close"]).dropna()
        return s

    # primary call
    s = _pull_hist(period, interval)

    # fallback - wider interval
    if len(s) <= 1 and interval in {"1m", "1d"}:
        s = _pull_hist(period, "1wk")

    # fallback - full max then slice
    if len(s) <= 1:
        max_df = yf.Ticker(ticker).history(period="max", interval="1d",
                                           auto_adjust=False)
        max_df.index = pd.to_datetime(max_df.index, errors="coerce")
        if not max_df.empty:
            days_map = {"1mo": 30, "3mo": 90, "6mo": 180,
                        "1y": 365, "2y": 730, "ytd": 400}
            cutoff = max_df.index.max() - pd.Timedelta(
                days_map.get(period, 365))
            s = (max_df[col] if col in max_df else max_df["Close"]).dropna()
            s = s[s.index >= cutoff]

    # final conversion to list
    return [
        (
            idx.strftime("%Y-%m-%d"),
            float(val) if np.isscalar(val) else float(val.iloc[0])
        )
        for idx, val in s.items()
    ]


def get_stock_quote(ticker: str) -> Dict:
    """
    Return a snapshot dict with latest price & key ratios.
    """
    T = yf.Ticker(ticker.upper())
    info = T.fast_info  # fast_info is lightweight vs .info

    price = float(info["last_price"])
    prev_close = float(info["previous_close"])
    pct = (price / prev_close - 1) * 100 if prev_close else None

    return {
        "symbol": ticker.upper(),
        "price": price,
        "changePct": pct,
        "currency": info.get("currency"),
        "marketCap": info.get("market_cap"),
        "pe": info.get("trailing_pe"),
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }