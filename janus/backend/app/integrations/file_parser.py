import pandas as pd


def parse_erp_file(file_path: str) -> pd.DataFrame:
    """Parse CSV or Excel file exported from any ERP."""
    lower = file_path.lower()
    if lower.endswith(".csv"):
        # Try auto-detecting separator (comma or semicolon)
        for sep in [None, ";", ","]:
            try:
                df = pd.read_csv(
                    file_path,
                    sep=sep,
                    engine="python",
                    encoding="utf-8",
                    on_bad_lines="skip",
                )
                if len(df.columns) > 1:
                    return df
            except Exception:
                continue
        # Last attempt: latin-1 encoding (common in Brazilian ERPs)
        return pd.read_csv(
            file_path, sep=None, engine="python", encoding="latin-1", on_bad_lines="skip"
        )

    if lower.endswith(".xlsx"):
        return pd.read_excel(file_path, engine="openpyxl")

    if lower.endswith(".xls"):
        return pd.read_excel(file_path)

    raise ValueError(
        f"Formato não suportado: '{file_path}'. Use CSV (.csv) ou Excel (.xlsx / .xls)."
    )
