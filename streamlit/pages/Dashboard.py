import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
import plotly.io as pio
from utils.auth import require_login
from utils.api import ask_question, get_kpis, download_report
from utils.theme import apply_theme

st.set_page_config(page_title="Dashboard — InsightAI", layout="wide")
apply_theme()
require_login()

st.title("Business Dashboard")
active_table = st.session_state.get("active_table", "sales")
st.caption(f"Querying table: `{active_table}`")

# ---------------- KPI row (from the backend, not a local CSV) ---------------- #
with st.container(border=True):
    kpis = get_kpis(active_table)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Revenue", f"${kpis.get('total_revenue', 0):,.0f}")
    c2.metric("Profit", f"${kpis.get('total_profit', 0):,.0f}")
    c3.metric("Orders", f"{kpis.get('total_orders', 0):,}")
    c4.metric("Customers", f"{kpis.get('total_customers', 0):,}")

st.divider()

# ---------------- Ask a question ---------------- #
with st.container(border=True):
    st.markdown("#### Ask anything about your business data")

    EXAMPLES = [
        "Show monthly sales",
        "Which region generated the highest revenue?",
        "Profit by category",
        "Top 10 products by revenue",
    ]
    cols = st.columns(len(EXAMPLES))
    for i, ex in enumerate(EXAMPLES):
        if cols[i].button(ex, use_container_width=True):
            st.session_state["prefill_question"] = ex

    question = st.chat_input("e.g. Which region generated the highest revenue this quarter?")
    if not question and st.session_state.get("prefill_question"):
        question = st.session_state.pop("prefill_question")

    if question:
        with st.spinner("Generating SQL, running query, and building insights..."):
            response = ask_question(question, active_table)
        if response:
            st.session_state["last_response"] = response

# ---------------- Render the last answer ---------------- #
if st.session_state.get("last_response"):
    response = st.session_state["last_response"]
    st.divider()

    with st.container(border=True):
        st.markdown("##### Generated SQL")
        st.code(response["sql"], language="sql")
        st.caption(f"Engine: `{response['sql_engine']}` · {response['row_count']} rows returned")

        df = pd.DataFrame(response["rows"], columns=response["columns"])
        st.markdown("##### Results")
        st.dataframe(df, use_container_width=True)

        if response["chart_type"] == "kpi" and not df.empty:
            row = df.iloc[0]
            kpi_cols = st.columns(len(df.columns))
            for i, col_name in enumerate(df.columns):
                val = row[col_name]
                kpi_cols[i].metric(
                    col_name.replace("_", " ").title(),
                    f"{val:,.2f}" if isinstance(val, (int, float)) else val,
                )
        elif response.get("chart_json"):
            st.markdown("##### Chart")
            fig = pio.from_json(response["chart_json"])
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("##### AI Insights")
        st.info(response["insight_text"])
        st.caption(f"Insight engine: `{response['insight_engine']}`")

    st.divider()
    with st.container(border=True):
        st.markdown("##### Export")
        e1, e2 = st.columns(2)
        if e1.button("Prepare PDF report", use_container_width=True):
            pdf_bytes = download_report(response["question"], response["sql"], response["rows"], response["insight_text"], "pdf")
            if pdf_bytes:
                st.download_button("Save PDF", pdf_bytes, file_name="insightai_report.pdf", mime="application/pdf")
        if e2.button("Prepare CSV export", use_container_width=True):
            csv_bytes = download_report(response["question"], response["sql"], response["rows"], response["insight_text"], "csv")
            if csv_bytes:
                st.download_button("Save CSV", csv_bytes, file_name="insightai_results.csv", mime="text/csv")
