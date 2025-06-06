# appp.py
# --------------------------------------------------------------------------- #
# PDF-Aware Finance Chatbot (Azure OpenAI) – v2.7                             #
# --------------------------------------------------------------------------- #
from __future__ import annotations  # must be first executable line

import json
from pathlib import Path
import pandas as pd
import streamlit as st

from config.settings import settings
from features.pdfs.indexer import index_pdfs
from features.llm.chat import ask_llm
from features.analytics.charts import draw_pie
from features.analytics.portfolio import (
    compute_portfolio_metrics,
    render_metrics_table,
    yearly_performance,
    max_drawdown,
)
from features.marketdata.yahoo import (
    get_stock_quote,
    get_stock_history,
    get_fx_rate,
)
from features.excel.loader import load_excel, get_fund_series

# --------------------------------------------------------------------------- #
# Streamlit page config                                                       #
# --------------------------------------------------------------------------- #
st.set_page_config(
    page_title="PDF-Aware Finance Chatbot", page_icon="🤖", layout="centered"
)
st.title("🤖 PDF-Aware Finance Chatbot (Azure OpenAI)")

# --------------------------------------------------------------------------- #
# Tabs – sliders                                                              #
# --------------------------------------------------------------------------- #
tab_chat, tab_settings = st.tabs(["💬 Chat", "⚙️ Settings"])
with tab_settings:
    st.subheader("Model & Index Settings")
    st.slider("Chunk size (chars)", 300, 2_000, 600, 100, key="chunk_size")
    st.slider("Chunk overlap (chars)", 0, 1_000, 150, 50, key="chunk_overlap")
    st.slider("Context chunks (k)", 2, 20, 8, 1, key="top_k")
    st.caption("Values persist until you refresh the page.")

# --------------------------------------------------------------------------- #
# Sidebar – PDF upload & indexing                                             #
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.header("📄 PDF Knowledge Base")
    files = st.file_uploader(
        "Upload PDFs", type="pdf", accept_multiple_files=True
    )
    st.caption(f"Embeddings deployment: {settings.EMBED_DEPLOYMENT}")

    if st.button("Build / Update index", disabled=not files):
        vs_existing = st.session_state.get("vectorstore")
        with st.spinner("Indexing…"):
            vectorstore, new_chunks = index_pdfs(
                files,
                chunk_size=st.session_state.get("chunk_size", 600),
                chunk_overlap=st.session_state.get("chunk_overlap", 150),
                existing_vs=vs_existing,
            )
        if vectorstore:
            st.session_state.vectorstore = vectorstore
            if new_chunks:
                st.success(f"Added **{new_chunks:,}** new chunk(s).")
            else:
                st.info("These PDFs were already indexed – nothing new added.")
        else:
            st.error("No readable text found in the uploaded PDFs.")
     
    st.header("📊 Excel Data")
    excel_file = st.file_uploader(
        "Upload Excel",
        type=["xlsx", "xls"],
        accept_multiple_files=False,
        key="excel_upload",
    )

    if excel_file is not None:
        try:
            excel_data = load_excel(excel_file)
            st.session_state["excel_data"] = excel_data
            sheet_names = list(excel_data)
            if sheet_names:
                sheet = st.selectbox("Sheet", sheet_names, key="excel_sheet")
                st.dataframe(excel_data[sheet])
        except Exception as exc:
            st.error(f"Failed to load Excel: {exc}")


# --------------------------------------------------------------------------- #
# Conversation history                                                        #
# --------------------------------------------------------------------------- #
if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    st.chat_message(m["role"]).markdown(m["content"])

# --------------------------------------------------------------------------- #
# Chat loop                                                                   #
# --------------------------------------------------------------------------- #
user_input = st.chat_input("Ask me anything…")
if user_input:
    st.chat_message("user").markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    # ---------------- first LLM call -------------------------------------- #
    response = ask_llm(
        st.session_state.messages,
        st.session_state.get("vectorstore"),
        user_input,
        top_k=st.session_state.get("top_k", 8),
    )
    choice = response.choices[0]
    tool_messages: list[dict[str, str]] = []

    # ---------------- tool dispatcher ------------------------------------- #
    if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
        for call in choice.message.tool_calls:
            name = call.function.name
            args = json.loads(call.function.arguments)

            # ---------- pie ------------------------------------------------ #
            if name == "create_pie_chart":
                draw_pie(args["labels"], args["values"])
                tool_content = "Pie chart rendered."

            # ---------- portfolio metrics --------------------------------- #
            elif name == "calculate_portfolio_metrics":
                ppy = args.get("periods_per_year") or (
                    1
                    if len(args["series"]) <= 12
                    else 12 if len(args["series"]) <= 60 else 252
                )
                metrics = compute_portfolio_metrics(
                    args["series"],
                    is_prices=args.get("is_prices", True),
                    periods_per_year=ppy,
                    returns_are_percent=args.get("returns_are_percent"),
                )
                render_metrics_table(metrics)
                tool_content = f"Portfolio metrics calculated (ppy={ppy})"

            # ---------- yearly perf --------------------------------------- #
            elif name == "calculate_yearly_performance":
                year_df = pd.DataFrame.from_dict(
                    yearly_performance(args["dates"], args["returns"]),
                    orient="index",
                    columns=["Return"],
                ).sort_index()
                st.markdown("### Yearly Performance")
                st.table(year_df.style.format({"Return": "{:.2%}"}))
                tool_content = "Yearly performance table rendered."

            # ---------- live quote ---------------------------------------- #
            elif name == "get_stock_quote":
                q = get_stock_quote(args["ticker"])
                st.markdown(
                    f"**{q['symbol']}** – {q.get('currency','')} "
                    f"{q['price']:.2f} ({q['changePct']:+.2f} %)\n\n"
                    f"Market cap: {q['marketCap'] or 'N/A'}\n\n"
                    f"Trailing P/E: {q['pe'] or 'N/A'}"
                )
                tool_content = json.dumps(q)

            # ---------- fx rate ------------------------------------------- #
            elif name == "get_fx_rate":
                fx = get_fx_rate(args["pair"])
                st.markdown(
                    f"**{fx['pair']}** {fx['rate']:.4f} ({fx['changePct']:+.2f}%)"
                )
                tool_content = json.dumps(fx)

            # ---------- price history ------------------------------------- #
            elif name == "get_stock_history":
                period_hint = args.get("period") or (
                    "6mo"
                    if "6 month" in user_input.lower()
                    else (
                        "3mo"
                        if "3 month" in user_input.lower()
                        else "ytd" if "ytd" in user_input.lower() else "1y"
                    )
                )
                series = get_stock_history(
                    args["ticker"],
                    period=period_hint,
                    interval=args.get("interval", "1d"),
                )
                tool_content = json.dumps({"series": series})

                # cache for later draw-down queries
                st.session_state["last_series"] = [p for _, p in series]

                if len(series) > 1 and "plot" in user_input.lower():
                    dates, prices = zip(*series)
                    st.line_chart(
                        pd.DataFrame(
                            {"Price": prices}, index=pd.to_datetime(dates)
                        )
                    )
                elif len(series) <= 1:
                    st.warning(
                        "Only one data point returned; unable to plot a series."
                    )

            # ---------- max draw-down ------------------------------------- #
            elif name == "calculate_max_drawdown":
                # explicit series? use it
                series_vals = args.get("series") or []

                # fallback 1 – cached series from last history call
                if not series_vals:
                    try:
                        series_vals = [
                            p
                            for _, p in st.session_state.get("last_series", [])
                        ]
                    except Exception:
                        series_vals = st.session_state.get("last_series", [])

                # fallback 2 – fetch via ticker if provided
                if not series_vals and args.get("ticker"):
                    series_vals = [
                        p
                        for _, p in get_stock_history(
                            args["ticker"],
                            period=args.get("period", "1y"),
                            interval=args.get("interval", "1d"),
                        )
                    ]

                if len(series_vals) <= 1:
                    st.warning(
                        "No price series available to compute draw-down."
                    )
                    dd = float("nan")
                else:
                    dd = max_drawdown(
                        series_vals, is_prices=args.get("is_prices", True)
                    )
                    st.markdown(f"**Maximum draw-down:** {dd*100:.2f}%")

                tool_content = json.dumps({"max_drawdown": dd})

                # ---------- excel data --------------------------------------- #
            elif name == "get_excel_data":
                excel_data = st.session_state.get("excel_data")
                if not excel_data:
                    tool_content = "No Excel data available."
                else:
                    sheet = args.get("sheet")
                    rows = int(args.get("rows", 5))
                    df = excel_data.get(sheet)
                    if df is None:
                        tool_content = f"Sheet '{sheet}' not found."
                    else:
                        tool_content = df.head(rows).to_json(orient="records")

            # ---------- fund series from excel ----------------------------- #
            elif name == "get_fund_series":
                excel_data = st.session_state.get("excel_data")
                if not excel_data:
                    tool_content = "No Excel data available."
                else:
                    sheet = args.get("sheet")
                    fund_name = args.get("fund_name")
                    try:
                        series = get_fund_series(excel_data, sheet, fund_name)
                    except Exception as exc:
                        series = None
                        print("FUND SERIES ERROR:", exc)
                    if series is None:
                        tool_content = f"Fund '{fund_name}' not found in sheet '{sheet}'."
                    else:
                        tool_content = json.dumps(series)

            # ---------- fallback ------------------------------------------ #
            else:
                tool_content = f"Unknown tool call: {name}"

            tool_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": name,
                    "content": tool_content,
                }
            )

        # --------------- second LLM call --------------------------------- #
        assistant_call_msg = choice.message.model_dump(exclude_none=True)
        assistant_call_msg["content"] = assistant_call_msg.get("content") or ""

        follow_resp = ask_llm(
            st.session_state.messages + [assistant_call_msg] + tool_messages,
            None,
            "",
            top_k=0,
        )
        assistant_reply = follow_resp.choices[0].message.content or ""
    else:
        assistant_reply = choice.message.content or ""

    st.chat_message("assistant").markdown(assistant_reply)
    st.session_state.messages.append(
        {"role": "assistant", "content": assistant_reply}
    )
