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
