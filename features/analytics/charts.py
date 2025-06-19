import io
from typing import Iterable

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st


def _store_chart(entry: dict) -> None:
    """Append a chart entry to ``st.session_state.charts``."""
    st.session_state.setdefault("charts", []).append(entry)


def draw_pie(labels: Iterable[str], values: Iterable[float], title: str = "Pie Chart") -> None:
    """Render a donut‑style pie chart inside Streamlit and persist it."""
    fig, ax = plt.subplots(figsize=(6, 6))
    colors = plt.cm.tab20.colors[: len(labels)]
    explode = [0.05] * len(labels)

    wedges, *_ = ax.pie(
        values,
        labels=None,
        colors=colors,
        explode=explode,
        autopct="%1.1f%%",
        pctdistance=0.8,
        startangle=130,
        wedgeprops={"linewidth": 1, "edgecolor": "white"},
    )

    ax.add_artist(plt.Circle((0, 0), 0.5, color="white"))
    ax.legend(
        wedges,
        labels,
        title="Categories",
        loc="center left",
        bbox_to_anchor=(1, 0, 0.5, 1),
    )
    ax.set_aspect("equal")

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)

    _store_chart({"type": "pie", "title": title, "image": buf.getvalue()})

    st.subheader(title)
    st.image(buf.getvalue())


def draw_line_chart(dates: Iterable[str], values: Iterable[float], title: str = "Line Chart") -> None:
    """Render a line chart inside Streamlit and persist it."""
    df = pd.DataFrame({"value": list(values)}, index=pd.to_datetime(list(dates)))
    _store_chart({"type": "line", "title": title, "data": df})
    st.subheader(title)
    st.line_chart(df)
