import matplotlib.pyplot as plt
import streamlit as st


def draw_pie(labels, values):
    """Render a donut‑style pie chart inside Streamlit."""
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
    st.pyplot(fig)