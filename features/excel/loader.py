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
    return {sheet: xls.parse(sheet) for sheet in xls.sheet_names}