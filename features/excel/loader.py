import pandas as pd


def load_excel(file):
    """Load an uploaded Excel file and return a dict of DataFrames keyed by sheet name.

    Parameters
    ----------
    file : streamlit.runtime.uploaded_file_manager.UploadedFile or file‑like
        The object returned from `st.file_uploader` (or any BytesIO).

    Returns
    -------
    dict[str, pandas.DataFrame]
        Mapping of sheet names to DataFrames containing the sheet data.
    """
    # Ensure buffer is at the start
    try:
        file.seek(0)
    except Exception:
        pass

    xls = pd.ExcelFile(file)
    result: dict[str, pd.DataFrame] = {}
    for sheet in xls.sheet_names:
        df = xls.parse(sheet)

        # Convert Unix timestamp columns or columns with epoch-like values
        for col in df.columns:
            name = str(col).lower()
            series = df[col]

            if "unix" in name and "ts" in name:
                # Explicit UNIX timestamp column
                df[col] = pd.to_datetime(series, unit="s", errors="coerce")
            else:
                # Heuristic detection of epoch numbers in seconds or milliseconds
                s = series.dropna()
                if not s.empty and pd.api.types.is_numeric_dtype(s):
                    sample = s.iloc[0]
                    if sample > 1e12:  # likely in milliseconds
                        df[col] = pd.to_datetime(series, unit="ms", errors="coerce")
                    elif sample > 1e9:
                        df[col] = pd.to_datetime(series, unit="s", errors="coerce")

            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].dt.strftime("%d-%b-%Y")

        # Ensure object columns are cast to plain strings for Arrow
        obj_cols = df.select_dtypes(include="object").columns
        for obj in obj_cols:
            df[obj] = df[obj].astype(str)

        result[sheet] = df
    
    return result

def get_fund_series(excel_data: dict[str, pd.DataFrame], sheet: str, fund_name: str) -> list[float] | None:
    """Return numeric values from the column matching *fund_name*.

    The search first checks column headers case-insensitively. If no match is
    found, the first row is scanned for the fund name and the values beneath it
    are returned. Non-numeric values are ignored.
    """
    df = excel_data.get(sheet)
    if df is None or df.empty:
        return None

    def _clean_numeric(col: pd.Series) -> pd.Series:
        """Return numeric values from *col* handling common symbols."""
        cleaned = (
            col.astype(str)
            .str.replace(",", "", regex=False)
            .str.replace("%", "", regex=False)
        )
        return pd.to_numeric(cleaned, errors="coerce").dropna()

    fund_lower = fund_name.strip().lower()

    # 1) match against column labels
    cols_lower = [str(c).strip().lower() for c in df.columns]
    if fund_lower in cols_lower:
        col = df.iloc[:, cols_lower.index(fund_lower)]
        series = _clean_numeric(col)
        return series.tolist()

    # 2) match against first-row values
    first_row = df.iloc[0].astype(str).str.strip().str.lower()
    matches = first_row[first_row == fund_lower]
    if not matches.empty:
        idx = matches.index[0]
        col = _clean_numeric(df.loc[1:, idx])
        return col.tolist()

    return None

def get_fund_month_value(
    excel_data: dict[str, pd.DataFrame],
    sheet: str,
    fund_name: str,
    month: str,
) -> float | None:
    """Return the numeric value for ``fund_name`` at the row matching ``month``.

    The search matches ``fund_name`` against column headers (case-insensitive)
    or the first-row values, just like :func:`get_fund_series`. ``month`` can be
    any string recognised by :func:`pandas.to_datetime`, e.g. ``"Dec 2024"``.
    """
    df = excel_data.get(sheet)
    if df is None or df.empty:
        return None

    fund_lower = fund_name.strip().lower()

    # Find the column for the fund
    col_idx = None
    cols_lower = [str(c).strip().lower() for c in df.columns]
    df_values = df
    if fund_lower in cols_lower:
        col_idx = cols_lower.index(fund_lower)
    else:
        first_row = df.iloc[0].astype(str).str.strip().str.lower()
        matches = first_row[first_row == fund_lower]
        if not matches.empty:
            col_idx = matches.index[0]
            df_values = df.iloc[1:]

    if col_idx is None:
        return None

    # Find the row for the month
    target = pd.to_datetime(month, errors="coerce")
    date_col = pd.to_datetime(df_values.iloc[:, 0], errors="coerce")

    if pd.isna(target):
        mask = (
            df_values.iloc[:, 0]
            .astype(str)
            .str.strip()
            .str.lower()
            == month.strip().lower()
        )
    else:
        mask = (date_col.dt.month == target.month) & (date_col.dt.year == target.year)

    if not mask.any():
        return None

    value = pd.to_numeric(df_values.loc[mask].iloc[0, col_idx], errors="coerce")
    if pd.isna(value):
        return None
    return float(value)

def get_fund_rankings(
    excel_data: dict[str, pd.DataFrame],
    ticker: str,
    sheet: str | None = None,
) -> dict[str, dict[str, float | int]] | None:
    """Return ranking information for ``ticker``.

    The lookup is case-insensitive against column **B** (index 1). If the ticker
    is found, the function extracts rank values from the following columns:

    - ``R`` (Total Points)
    - ``V`` (1‑yr return)
    - ``Y`` (3‑yr return)
    - ``AB`` (5‑yr return)
    - ``AM`` (Maximum Drawdown)
    - ``AO`` (Sharpe Ratio)
    - ``AQ`` (Sortino Ratio)
    - ``AS`` (Treynor Measure)

    Column letters are interpreted using zero-based indices, so if a sheet does
    not contain enough columns the missing ranks are returned as ``None``.
    ``None`` is returned when the ticker cannot be found in any sheet.  The
    result is a dictionary mapping each sheet name that contains the ticker to
    the extracted ranking values, e.g. ``{"Sheet1": {"rank_total_pts": 1, ...}}``.
    """

    def _search(df: pd.DataFrame) -> dict[str, float | int] | None:
        tickers = df.iloc[:, 1].astype(str).str.strip().str.lower()
        mask = tickers == ticker.strip().lower()
        if not mask.any():
            return None
        row = df.loc[mask].iloc[0]

        def _get(col_idx: int) -> float | int | None:
            if col_idx >= len(row):
                return None
            val = row.iloc[col_idx]
            if pd.isna(val):
                return None
            try:
                return float(str(val).replace("%", "").replace(",", ""))
            except Exception:
                return None

        col_map = {
            "rank_total_pts": 17,  # R
            "rank_1yr": 21,       # V
            "rank_3yr": 24,       # Y
            "rank_5yr": 27,       # AB
            "rank_max_dd": 38,    # AM
            "rank_sharpe": 40,    # AO
            "rank_sortino": 42,   # AQ
            "rank_treynor": 44,   # AS
        }
        return {k: _get(idx) for k, idx in col_map.items()}

    results: dict[str, dict[str, float | int]] = {}

    # Search the explicitly provided sheet first if given
    searched: set[str] = set()
    if sheet:
        df = excel_data.get(sheet)
        if df is not None:
            searched.add(sheet)
            res = _search(df)            
            if res is not None:
                results[sheet] = res

    # Search remaining sheets
    for name, df in excel_data.items():
        if name in searched:
            continue
        res = _search(df)
        if res is not None:
            results[name] = res

    return results or None

def get_starred_ticker_overview(
    portfolio_data: dict[str, pd.DataFrame],
    ranking_data: dict[str, pd.DataFrame],
    sheet: str,
) -> list[dict[str, str | float | int]]:
    """Return ranking and detail info for tickers starred in ``sheet``.

    The function searches ``sheet`` in ``portfolio_data`` for rows where column
    A contains ``*`` and extracts the tickers from column B. If no starred rows
    are found there, it falls back to ``ranking_data``.  For each ticker the
    ranking values are pulled from the rankings workbook using
    :func:`get_fund_rankings` and the detailed columns (fund type, currency,
    recent returns, fees, etc.) are pulled using :func:`get_fund_details`.

    Each element in the returned list contains the ticker, the workbook where
    the star was found (``"portfolio"`` or ``"ranking"``), and the combined
    ranking and detail values.
    """

    tickers = get_starred_tickers(portfolio_data, sheet)
    workbook = "portfolio"
    if not tickers:
        tickers = get_starred_tickers(ranking_data, sheet)
        workbook = "ranking"

    rows: list[dict[str, str | float | int]] = []
    for ticker in tickers:
        row: dict[str, str | float | int] = {"ticker": ticker, "workbook": workbook}

        ranks = get_fund_rankings(ranking_data, ticker, sheet)
        if ranks:
            vals = ranks.get(sheet) or next(iter(ranks.values()))
            row.update(vals)

        details = get_fund_details(ranking_data, ticker, sheet)
        if details:
            vals = details.get(sheet) or next(iter(details.values()))
            row.update(vals)

        rows.append(row)

    return rows

def get_starred_ticker_details(
    excel_data: dict[str, pd.DataFrame],
    ranking_data: dict[str, pd.DataFrame],
    sheet: str,
) -> list[dict[str, float | int | str]]:
    """Return ranking and detail rows for tickers marked with ``*`` in ``sheet``.

    The function first looks for starred rows in the portfolio workbook. If none
    are found it falls back to the rankings workbook. Ranking and detailed fund
    information is always pulled from ``ranking_data``.  Each returned mapping
    contains the ticker, the workbook the star was found in, the ranking values
    and fund detail columns (fund type, currency, recent returns and fees).
    """

    portfolio_tickers = get_starred_tickers(excel_data, sheet)
    workbook = "portfolio"
    if portfolio_tickers:
        tickers = portfolio_tickers
    else:
        tickers = get_starred_tickers(ranking_data, sheet)
        workbook = "ranking"

    rows: list[dict[str, float | int | str]] = []
    for ticker in tickers:
        ranks = get_fund_rankings(ranking_data, ticker, sheet) or {}
        if sheet in ranks:
            rank_vals = ranks[sheet]
        elif ranks:
            rank_vals = next(iter(ranks.values()))
        else:
            rank_vals = {}

        details = get_fund_details(ranking_data, ticker, sheet) or {}
        if sheet in details:
            detail_vals = details[sheet]
        elif details:
            detail_vals = next(iter(details.values()))
        else:
            detail_vals = {}

        rows.append({"ticker": ticker, "workbook": workbook, **detail_vals, **rank_vals})

    return rows

def get_fund_details(
    excel_data: dict[str, pd.DataFrame],
    ticker: str,
    sheet: str | None = None,
) -> dict[str, dict[str, str | float]] | None:
    """Return detailed information for ``ticker`` from the workbook.

    The search is case-insensitive against column **B**. If the ticker is
    found, values from various columns (fund type, currency, short-term
    returns, negative-year returns, and fees) are extracted. Long-term and
    prior calendar year returns are omitted. The result is a dictionary keyed
    by sheet name for each sheet containing the ticker. Sharpe Ratio,
    Sortino Ratio and Treynor Measure values are returned in percentage
    form.
    """

    def _clean(val):
        if pd.isna(val):
            return None
        txt = str(val).replace("%", "").replace(",", "").strip()
        try:
            return float(txt)
        except ValueError:
            return str(val).strip()

    def _search(df: pd.DataFrame) -> dict[str, str | float] | None:
        tickers = df.iloc[:, 1].astype(str).str.strip().str.lower()
        mask = tickers == ticker.strip().lower()
        if not mask.any():
            return None
        row = df.loc[mask].iloc[0]

        col_map = {
            "fund_type": 3,           # D
            "long_name": 7,           # H
            "currency": 8,            # I
            "mtd_total_return_pct": 11,  # L
            "qtd_total_return_pct": 12,  # M
            "ytd_total_return_pct": 13,  # N
            "return_neg_1yr": 20,       # U
            "return_neg_2_3yr": 23,     # X
            "return_neg_4_5yr": 26,     # AA
            "downside_risk_ann": 34,    # AI
            "return_volatility": 35,    # AJ
            "maximum_total_return": 36,  # AK
            "maximum_drawdown_pct": 37,  # AL
            "return_sharpe_ratio": 39,  # AN
            "sortino_ratio": 41,       # AP
            "treynor_measure": 43,     # AR
            "fund_manager_fee": 52,    # BA
            "expense_ratio": 53,       # BB
        }

        result = {k: _clean(row.iloc[idx]) if idx < len(row) else None for k, idx in col_map.items()}

        pct_keys = ["return_sharpe_ratio", "sortino_ratio", "treynor_measure"]
        for key in pct_keys:
            val = result.get(key)
            if isinstance(val, (int, float)):
                result[key] = round(val * 100, 4)

        return result

    results: dict[str, dict[str, str | float]] = {}

    searched: set[str] = set()
    if sheet:
        df = excel_data.get(sheet)
        if df is not None:
            searched.add(sheet)
            res = _search(df)
            if res is not None:
                results[sheet] = res

    for name, df in excel_data.items():
        if name in searched:
            continue
        res = _search(df)
        if res is not None:
            results[name] = res

    return results or None

def list_sheets(excel_data: dict[str, pd.DataFrame]) -> list[str]:
    """Return all sheet names present in the uploaded workbook."""
    return list(excel_data)


def count_rows(excel_data: dict[str, pd.DataFrame], sheet: str) -> int:
    """Return the number of rows in ``sheet`` from the uploaded workbook."""
    df = excel_data.get(sheet)
    if df is None:
        return 0
    return int(df.shape[0])
