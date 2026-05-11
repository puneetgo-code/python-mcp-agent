import json
import os
import subprocess
import time
from datetime import datetime

import pandas as pd
import streamlit as st

from fraud_agent import assess_transaction, generate_transactions, parse_assessment


# ---- MCP helpers (subprocess + JSON-RPC) -----------------------------------

def _mcp_call(cmd, args, tool_name, tool_args):
    """Run an MCP server as a subprocess and call *tool_name* with *tool_args*.

    Communicates via JSON-RPC 2.0 over stdin/stdout.
    Returns the list of content items from the tool response.
    """
    proc = subprocess.Popen(
        [cmd] + list(args),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    def _resp(expected_id):
        while True:
            line = proc.stdout.readline()
            if not line:
                return None
            msg = json.loads(line.strip())
            if msg.get("id") == expected_id and "result" in msg:
                return msg["result"]

    try:
        proc.stdin.write(
            '{"jsonrpc":"2.0","id":1,"method":"initialize",'
            '"params":{"protocolVersion":"2024-11-05","capabilities":{},'
            '"clientInfo":{"name":"mcp-agent","version":"1.0.0"}}}\n'
        )
        proc.stdin.flush()
        _resp(1)

        proc.stdin.write('{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        proc.stdin.flush()

        call = json.dumps(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": tool_name, "arguments": tool_args}}
        ) + "\n"
        proc.stdin.write(call)
        proc.stdin.flush()

        result = _resp(2)
        if result is None:
            err = proc.stderr.read()
            raise RuntimeError(f"MCP server returned no response. stderr: {err}")
        return result["content"]
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


def _aws_search(query: str) -> list[dict]:
    """Run a search against the AWS Documentation MCP server."""
    content = _mcp_call(
        "uvx",
        ["awslabs.aws-documentation-mcp-server@latest"],
        "search_documentation",
        {"search_phrase": query, "limit": 10},
    )
    entries: list[dict] = []
    for c in content:
        data = json.loads(c["text"])
        for r in data.get("search_results", []):
            entries.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "context": r.get("context", ""),
            })
    return entries


def _fs_list_dir(root: str, path: str) -> list[dict]:
    """List the contents of *path* (must be under *root*) via the
    filesystem MCP server."""
    content = _mcp_call(
        r"C:\Program Files\nodejs\npx.cmd",
        ["-y", "@modelcontextprotocol/server-filesystem", root],
        "list_directory",
        {"path": path},
    )
    entries: list[dict] = []
    for c in content:
        data = json.loads(c["text"])
        entries.extend(data.get("entries", []))
    return entries


# ---- page: Fraud Analyst ---------------------------------------------------

def page_fraud_analyst():
    st.title("Fraud Analyst")
    st.markdown(
        "Generate 10 fake credit-card transactions and analyse each "
        "one with Groq to determine fraud risk."
    )

    api_key = st.session_state.get("api_key", "")
    if not api_key:
        st.info("Enter a Groq API key in the sidebar to continue.")
        return

    if st.button("Generate & Analyze 10 Transactions", type="primary"):
        with st.spinner("Generating transactions ..."):
            transactions = generate_transactions()
        st.success("Generated 10 transactions.")

        results: list[dict] = []
        bar = st.progress(0, text="Analyzing transactions ...")
        status = st.empty()

        for i, txn in enumerate(transactions):
            status.text(f"Analyzing {txn['txn_id']} ...")
            raw = assess_transaction(api_key, txn)
            risk, reason = parse_assessment(raw)
            results.append({
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
            })
            bar.progress((i + 1) / len(transactions))

        status.empty()
        time.sleep(0.3)
        bar.empty()

        col1, col2, col3 = st.columns(3)
        risks = [r["Risk"] for r in results]
        col1.metric("HIGH", risks.count("HIGH"))
        col2.metric("MEDIUM", risks.count("MEDIUM"))
        col3.metric("LOW", risks.count("LOW"))

        df = pd.DataFrame(results)

        def _color(val: str) -> str:
            bg = {"LOW": "background-color: #198038", "MEDIUM": "background-color: #b75d00", "HIGH": "background-color: #a2191f"}.get(val, "")
            return f"{bg}; color: white"

        st.dataframe(
            df.style.map(_color, subset=["Risk"]),
            use_container_width=True,
            hide_index=True,
        )


# ---- page: AWS Documentation -----------------------------------------------

def page_aws_docs():
    st.title("AWS Documentation")
    st.markdown(
        "Search the official AWS documentation using the "
        "AWS Documentation MCP server."
    )

    query = st.text_input("Search AWS documentation", placeholder="e.g. S3 bucket versioning")

    if not query:
        st.info("Enter a search query above.")
        return

    if st.button("Search", type="primary"):
        with st.spinner("Searching AWS documentation ..."):
            try:
                results = _aws_search(query)
            except Exception as e:
                st.error(f"Search failed: {e}")
                return

        if not results:
            st.warning("No results found.")
            return

        st.success(f"Found {len(results)} result(s).")

        for r in results:
            with st.expander(r["title"]):
                st.markdown(f"**URL:** [{r['url']}]({r['url']})")
                st.markdown(r.get("context", ""))


# ---- page: File Explorer ---------------------------------------------------

DOCS_ROOT = r"C:\Users\Puneet Goel\Documents"

def page_file_explorer():
    st.title("File Explorer")
    st.markdown(f"Browsing: **{DOCS_ROOT}**")

    # Initialise navigation state
    if "fs_path" not in st.session_state:
        st.session_state.fs_path = DOCS_ROOT

    current = st.session_state.fs_path

    # Navigation: up / home
    col_left, col_right = st.columns([1, 6])
    with col_left:
        if current != DOCS_ROOT:
            if st.button("⬆  Up"):
                st.session_state.fs_path = os.path.dirname(current)
                st.rerun()
    with col_right:
        if current != DOCS_ROOT:
            if st.button("🏠  Home"):
                st.session_state.fs_path = DOCS_ROOT
                st.rerun()

    # List directory contents
    try:
        entries = _fs_list_dir(DOCS_ROOT, current)
    except Exception as e:
        st.error(f"Could not list directory: {e}")
        st.session_state.fs_path = DOCS_ROOT
        st.rerun()
        return

    # Build table rows
    rows = []
    for e in entries:
        name = e.get("name", "")
        full = os.path.join(current, name).replace("\\", "/")
        is_dir = e.get("type") == "directory"

        if is_dir:
            btn = st.button(f"📁  {name}", key=f"nav_{full}")
            if btn:
                st.session_state.fs_path = full
                st.rerun()

        size = e.get("size")
        size_str = f"{size:,} B" if size is not None else ""
        modified = e.get("modified")
        if modified:
            try:
                modified = datetime.fromisoformat(modified).strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass

        rows.append({
            "": "📁" if is_dir else "📄",
            "Name": name,
            "Size": size_str,
            "Modified": modified or "",
        })

    if not rows:
        st.info("Empty directory.")
    else:
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
            column_config={"": st.column_config.TextColumn("", width="small")},
        )


# ---- main ------------------------------------------------------------------

st.set_page_config(page_title="Multi‑Tool Agent", layout="wide")

# Sidebar: shared Groq API key
with st.sidebar:
    st.title("Settings")
    api_key = st.text_input(
        "Groq API Key",
        type="password",
        help="Used by the Fraud Analyst page. Not stored.",
    )
    st.session_state.api_key = api_key
    st.divider()
    st.caption("Select a page above ☝️")

# Page navigation
fraud = st.Page(page_fraud_analyst, title="Fraud Analyst", icon="🕵️")
docs  = st.Page(page_aws_docs,      title="AWS Documentation",  icon="📚")
files = st.Page(page_file_explorer, title="File Explorer",      icon="📁")

nav = st.navigation([fraud, docs, files])
nav.run()
