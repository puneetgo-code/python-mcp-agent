import os
import time

import pandas as pd
import streamlit as st

from fraud_agent import assess_transaction, generate_transactions, parse_assessment


# ---- page config -----------------------------------------------------------

st.set_page_config(page_title="Fraud Detection Agent", layout="wide")
st.title("Fraud Detection Agent")
st.markdown(
    "Generate 10 fake credit-card transactions and analyze each one with "
    "Groq (llama-3.3-70b-versatile) to determine fraud risk."
)

# ---- api key ---------------------------------------------------------------

api_key = st.text_input(
    "Enter your Groq API key",
    type="password",
    help="Your key is used only for this session and is not stored.",
)


# ---- generate & analyze ----------------------------------------------------

if not api_key:
    st.info("Enter a Groq API key above to continue.")
    st.stop()

if st.button("Generate & Analyze 10 Transactions", type="primary"):
    # Step 1: generate
    with st.spinner("Generating transactions ..."):
        transactions = generate_transactions()
    st.success("Generated 10 transactions.")

    # Step 2: assess each one
    results: list[dict] = []
    progress_bar = st.progress(0, text="Analyzing transactions ...")
    status_text = st.empty()

    for i, txn in enumerate(transactions):
        status_text.text(f"Analyzing {txn['txn_id']} ...")
        raw = assess_transaction(api_key, txn)
        risk, reason = parse_assessment(raw)

        results.append(
            {
                "ID": txn["txn_id"],
                "Cardholder": txn["cardholder"],
                "Amount": f"${txn['amount']:.2f}",
                "Time (UTC)": txn["timestamp"].strftime("%Y-%m-%d %H:%M"),
                "Merchant": txn["merchant"],
                "Category": txn["category"],
                "Location": f"{txn['location']}, {txn['location_country']}",
                "Home": txn["cardholder_home"],
                "Risk": risk,
                "Reason": reason,
            }
        )
        progress_bar.progress((i + 1) / len(transactions))

    # clear temporary widgets
    status_text.empty()
    time.sleep(0.3)
    progress_bar.empty()

    # Step 3: summary metrics at the top
    col1, col2, col3 = st.columns(3)
    risks = [r["Risk"] for r in results]
    col1.metric("HIGH", risks.count("HIGH"))
    col2.metric("MEDIUM", risks.count("MEDIUM"))
    col3.metric("LOW", risks.count("LOW"))

    # Step 4: colour-coded table
    df = pd.DataFrame(results)

    def _color_risk(val: str) -> str:
        bg = {"LOW": "background-color: #198038", "MEDIUM": "background-color: #b75d00", "HIGH": "background-color: #a2191f"}.get(val, "")
        fg = {"LOW": "color: white", "MEDIUM": "color: white", "HIGH": "color: white"}.get(val, "")
        return f"{bg}; {fg}"

    styled = df.style.map(_color_risk, subset=["Risk"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

else:
    st.info("Click the button above to start.")
