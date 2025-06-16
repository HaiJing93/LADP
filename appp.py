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
from openai import OpenAIError
from features.analytics.charts import draw_pie
from features.analytics.portfolio import (
    compute_portfolio_metrics,
    compute_portfolio_metrics_from_excel,
    render_metrics_table,
    yearly_performance,
    max_drawdown,
)
from features.marketdata.yahoo import (
    get_stock_quote,
    get_stock_history,
    get_fx_rate,
)
from features.excel.loader import (
    load_excel,
    get_fund_series,
    get_fund_month_value,
)

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
    try:
        response = ask_llm(
            st.session_state.messages,
            st.session_state.get("vectorstore"),
            user_input,
            top_k=st.session_state.get("top_k", 8),
        )
    except OpenAIError as exc:
        st.error(f"LLM request failed: {exc}")
        st.stop()
    except Exception as exc:
        st.error(f"Unexpected error: {exc}")
        st.stop()

    if not response or not getattr(response, "choices", None):
        st.error("No response from LLM.")
        st.stop()

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
                try:
                    metrics = compute_portfolio_metrics(
                        args["series"],
                        is_prices=args.get("is_prices", True),
                        periods_per_year=args.get("periods_per_year"),
                        returns_are_percent=args.get("returns_are_percent"),
                        dates=args.get("dates"),
                    )
                    
                    # Check if any metrics could be calculated
                    valid_metrics = {k: v for k, v in metrics.items() if not pd.isna(v)}
                    
                    if not valid_metrics:
                        tool_content = "Unable to calculate portfolio metrics. The provided data may be insufficient (empty series, all NaN values, or only one data point). Please check that you have provided a valid time series of prices or returns."
                        st.warning("Portfolio metrics could not be calculated from the provided data.")
                    else:
                        render_metrics_table(metrics)
                        # Include the actual metrics in the tool response
                        metrics_summary = []
                        for key, value in metrics.items():
                            if pd.isna(value):
                                metrics_summary.append(f"{key}: Unable to calculate")
                            else:
                                if key in ["cumulative_return", "annualized_return", "annualized_volatility", "max_drawdown"]:
                                    metrics_summary.append(f"{key}: {value*100:.2f}%")
                                else:
                                    metrics_summary.append(f"{key}: {value:.4f}")
                        
                        tool_content = f"Portfolio metrics calculated. Results: {'; '.join(metrics_summary)}"
                        
                except Exception as exc:
                    tool_content = f"Error calculating portfolio metrics: {exc}. Please ensure the data is a valid numeric series."
                    st.error(f"Error calculating portfolio metrics: {exc}")

            # ---------- portfolio metrics from excel -------------------- #
            elif name == "calculate_portfolio_metrics_from_excel":
                excel_data = st.session_state.get("excel_data")
                if not excel_data:
                    tool_content = "No Excel data available. Please upload an Excel file first."
                else:
                    sheet = args.get("sheet")
                    if sheet not in excel_data:
                        sheet = next(iter(excel_data))
                    df = excel_data[sheet]
                    is_prices = args.get("is_prices", False)
                    returns_are_percent = args.get("returns_are_percent", False)
                    try:
                        ppy = args.get("periods_per_year", 12)
                        dates = pd.to_datetime(df.iloc[:, 0], errors="coerce")
                        values = pd.to_numeric(df.iloc[:, 1], errors="coerce")
                        mask = dates.notna() & values.notna()
                        metrics = compute_portfolio_metrics(
                            values[mask].tolist(),
                            is_prices=is_prices,
                            periods_per_year=ppy,
                            returns_are_percent=returns_are_percent,
                            dates=dates[mask].tolist(),
                        )

                        valid_metrics = {k: v for k, v in metrics.items() if not pd.isna(v)}
                        if not valid_metrics:
                            tool_content = "Unable to calculate portfolio metrics from Excel data."
                            st.warning("Portfolio metrics could not be calculated from the Excel data.")
                        else:
                            render_metrics_table(metrics)
                            metrics_summary = []
                            for key, value in metrics.items():
                                if pd.isna(value):
                                    metrics_summary.append(f"{key}: Unable to calculate")
                                else:
                                    if key in ["cumulative_return", "annualized_return", "annualized_volatility", "max_drawdown"]:
                                        metrics_summary.append(f"{key}: {value*100:.2f}%")
                                    else:
                                        metrics_summary.append(f"{key}: {value:.4f}")
                            tool_content = f"Portfolio metrics calculated from sheet '{sheet}'. Results: {'; '.join(metrics_summary)}"
                    except Exception as exc:
                        tool_content = f"Error calculating portfolio metrics from Excel: {exc}"
                        st.error(tool_content)

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
                    try:
                        series_vals = [
                            p
                            for _, p in get_stock_history(
                                args["ticker"],
                                period=args.get("period", "1y"),
                                interval=args.get("interval", "1d"),
                            )
                        ]
                    except Exception as exc:
                        st.error(f"Failed to fetch stock history for {args.get('ticker')}: {exc}")

                if len(series_vals) <= 1:
                    st.warning(
                        "No price series available to compute draw-down."
                    )
                    dd = float("nan")
                    tool_content = f"Unable to calculate maximum drawdown: insufficient data (only {len(series_vals)} data point(s) available). Need at least 2 data points for drawdown calculation."
                else:
                    try:
                        dd = max_drawdown(
                            series_vals, is_prices=args.get("is_prices", True)
                        )
                        if pd.isna(dd):
                            st.warning("Maximum drawdown calculation returned NaN.")
                            tool_content = "Maximum drawdown could not be calculated (result was NaN). This may indicate invalid data in the price series."
                        else:
                            st.markdown(f"**Maximum draw-down:** {dd*100:.2f}%")
                            tool_content = f"Maximum drawdown calculated: {dd*100:.2f}% (based on {len(series_vals)} data points)"
                    except Exception as exc:
                        dd = float("nan")
                        tool_content = f"Error calculating maximum drawdown: {exc}"
                        st.error(f"Error in drawdown calculation: {exc}")

                # Include the numeric result for further processing
                tool_content += f" | JSON: {json.dumps({'max_drawdown': dd})}"

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
                    tool_content = "No Excel data available. Please upload an Excel file first."
                else:
                    sheet = args.get("sheet")
                    fund_name = args.get("fund_name")
                    
                    # Check if sheet exists
                    if sheet not in excel_data:
                        available_sheets = list(excel_data.keys())
                        tool_content = f"Sheet '{sheet}' not found. Available sheets: {', '.join(available_sheets)}"
                    else:
                        try:
                            series = get_fund_series(excel_data, sheet, fund_name)
                            if series is None:
                                # Provide more helpful information about what was searched
                                df = excel_data[sheet]
                                col_names = [str(c) for c in df.columns]
                                first_row_values = df.iloc[0].astype(str).tolist() if not df.empty else []
                                
                                search_info = f"Searched in column headers: {col_names[:10]}{'...' if len(col_names) > 10 else ''}"
                                if first_row_values:
                                    search_info += f" and first row values: {first_row_values[:10]}{'...' if len(first_row_values) > 10 else ''}"
                                
                                tool_content = f"Fund '{fund_name}' not found in sheet '{sheet}'. {search_info}. Please check the exact fund name spelling or try a different sheet."
                            else:
                                tool_content = json.dumps(series)
                                # Also provide summary info
                                if len(series) > 0:
                                    tool_content += f" (Found {len(series)} data points for fund '{fund_name}')"
                                else:
                                    tool_content = f"Fund '{fund_name}' column found but contains no valid numeric data."
                        except Exception as exc:
                            tool_content = f"Error retrieving fund series for '{fund_name}': {exc}"
                            st.error(f"Error retrieving fund data: {exc}")

            # ---------- fund value for specific month -------------------- #
            elif name == "get_fund_month_value":
                excel_data = st.session_state.get("excel_data")
                if not excel_data:
                    tool_content = "No Excel data available. Please upload an Excel file first."
                else:
                    sheet = args.get("sheet")
                    fund_name = args.get("fund_name")
                    month = args.get("month")
                    if sheet not in excel_data:
                        available_sheets = list(excel_data.keys())
                        tool_content = (
                            f"Sheet '{sheet}' not found. Available sheets: {', '.join(available_sheets)}"
                        )
                    else:
                        try:
                            value = get_fund_month_value(excel_data, sheet, fund_name, month)
                            if value is None:
                                tool_content = (
                                    f"Value for fund '{fund_name}' in '{month}' not found."
                                )
                            else:
                                tool_content = json.dumps({"value": value})
                        except Exception as exc:
                            tool_content = f"Error retrieving fund value: {exc}"
                            st.error(f"Error retrieving fund value: {exc}")

            # ---------- combined fund metrics ----------------------------- #
            elif name == "calculate_fund_metrics":
                excel_data = st.session_state.get("excel_data")
                if not excel_data:
                    tool_content = "No Excel data available. Please upload an Excel file first."
                else:
                    fund_name = args.get("fund_name")
                    sheet = args.get("sheet", "Main Funds")
                    is_prices = args.get("is_prices", False)
                    returns_are_percent = args.get("returns_are_percent", False)
                    
                    # Try multiple sheet names if the specified one doesn't exist
                    sheets_to_try = [sheet] if sheet in excel_data else []
                    if not sheets_to_try:
                        # Add common sheet names to try
                        for common_sheet in ["Main Funds", "Sheet1", "Fund Data", excel_data.keys()]:
                            if isinstance(common_sheet, str) and common_sheet in excel_data:
                                sheets_to_try.append(common_sheet)
                            elif hasattr(common_sheet, '__iter__'):
                                sheets_to_try.extend(list(common_sheet))
                        sheets_to_try = list(dict.fromkeys(sheets_to_try))  # Remove duplicates
                    
                    fund_found = False
                    for sheet_name in sheets_to_try:
                        try:
                            series = get_fund_series(excel_data, sheet_name, fund_name)
                            if series is not None and len(series) > 1:
                                # Calculate metrics
                                metrics = compute_portfolio_metrics(
                                    series,
                                    is_prices=is_prices,
                                    periods_per_year=12,  # Monthly data assumed
                                    returns_are_percent=returns_are_percent,
                                )
                                
                                # Check if metrics were calculated successfully
                                valid_metrics = {k: v for k, v in metrics.items() if not pd.isna(v)}
                                
                                if valid_metrics:
                                    # Render the table
                                    render_metrics_table(metrics)
                                    
                                    # Create detailed response
                                    metrics_text = []
                                    for key, value in metrics.items():
                                        if not pd.isna(value):
                                            if key in ["cumulative_return", "annualized_return", "annualized_volatility", "max_drawdown"]:
                                                metrics_text.append(f"{key.replace('_', ' ').title()}: {value*100:.2f}%")
                                            else:
                                                metrics_text.append(f"{key.replace('_', ' ').title()}: {value:.4f}")
                                    
                                    tool_content = f"Successfully calculated metrics for '{fund_name}' from sheet '{sheet_name}' (using {len(series)} data points). {'; '.join(metrics_text)}"
                                    fund_found = True
                                    break
                                else:
                                    continue  # Try next sheet
                        except Exception as exc:
                            continue  # Try next sheet
                    
                    if not fund_found:
                        available_sheets = list(excel_data.keys())
                        tool_content = f"Fund '{fund_name}' not found in any available sheets: {', '.join(available_sheets)}. Please check the fund name spelling or upload the correct Excel file."

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

        # ---------- DEBUG: Print tool messages before second call -------- #
        print("=== TOOL CALL DEBUG ===")
        for i, tool_msg in enumerate(tool_messages):
            print(f"Tool {i+1}: {tool_msg['name']}")
            print(f"Content: {tool_msg['content'][:200]}{'...' if len(tool_msg['content']) > 200 else ''}")
            print("---")
        print("=== END TOOL DEBUG ===")

        follow_resp = ask_llm(
            st.session_state.messages + [assistant_call_msg] + tool_messages,
            None,
            "",
            top_k=0,
            enable_tools=False,
        )
        assistant_reply = follow_resp.choices[0].message.content or ""
        
        # ---------- DEBUG: Print final response ----------------------- #
        print(f"=== FINAL LLM RESPONSE DEBUG ===")
        print(f"Response length: {len(assistant_reply)}")
        print(f"Response content: '{assistant_reply[:500]}{'...' if len(assistant_reply) > 500 else ''}'")
        print("=== END RESPONSE DEBUG ===")
    else:
        assistant_reply = choice.message.content or ""

    st.chat_message("assistant").markdown(assistant_reply)
    st.session_state.messages.append(
        {"role": "assistant", "content": assistant_reply}
    )

    st.chat_message("assistant").markdown(assistant_reply)
    st.session_state.messages.append(
        {"role": "assistant", "content": assistant_reply}
    )
