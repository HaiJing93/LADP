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

        # Convert any Unix timestamp columns to human-readable dates.
        for col in df.columns:
            name = str(col).lower()
            if "unix" in name and "ts" in name:
                df[col] = pd.to_datetime(df[col], unit="s", errors="coerce")
                df[col] = df[col].dt.strftime("%d/%m/%y")

        result[sheet] = df

    return result
