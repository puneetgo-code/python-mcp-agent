# Python MCP Agent Examples

Welcome to the **Python MCP Agent Examples** repository! If you're learning about AI agents for the first time, this project is a perfect starting point. It provides hands-on examples of how to connect Large Language Models (LLMs) to external tools, data, and environments using Python.

## What is this project?

This project contains several distinct examples of AI agents, ranging from simple terminal scripts to a multi-page interactive web dashboard. It demonstrates how to give an AI model the ability to:
1.  **Search the internet:** Specifically, querying live AWS documentation.
2.  **Analyze data:** Reviewing credit card transactions to detect fraudulent behavior.
3.  **Interact with your computer:** Browsing your local file system.

## Architecture

At a high level, these agents follow a simple architecture:
*   **The Brain (LLM):** We use **Groq** (specifically the `llama-3.3-70b-versatile` model) because of its incredibly fast inference speeds and strong reasoning capabilities.
*   **The Senses/Hands (Tools):** We use the **Model Context Protocol (MCP)**. MCP is an open standard that allows LLMs to easily connect to external tools (like an AWS search engine or your local hard drive) without needing custom integration code for every single tool.
*   **The Interface:** We use standard **Terminal/Command Line** for backend scripts, and **Streamlit** to build beautiful, interactive web applications.

## Tools and Technologies Used

*   **Python:** The core programming language.
*   **Groq API:** Provides the LLM intelligence.
*   **Model Context Protocol (MCP):** Connects the LLM to data sources securely.
*   **LangChain:** A popular framework for building AI applications (used in one of our examples to show an alternative approach).
*   **Streamlit:** A Python library to quickly build web apps for data and AI.
*   **Faker:** A Python library used to generate realistic, fake credit card transactions for our fraud detection testing.

---

## The Scripts & How to Run Them

Before running any script, you must have a Groq API key. Set it as an environment variable in your terminal:
**Windows (PowerShell):** `$env:GROQ_API_KEY="your-api-key-here"`
**Mac/Linux:** `export GROQ_API_KEY="your-api-key-here"`

### 1. The Terminal Agents (AWS Docs)
These scripts launch an interactive chat in your terminal where you can ask questions about AWS, and the agent will use MCP to search the official documentation.

*   `agent.py`: A "from scratch" implementation showing exactly how MCP and function-calling work under the hood.
    *   **Run:** `python agent.py`
*   `agent_langchain.py`: Does the exact same thing, but uses the LangChain framework to show how high-level libraries can simplify the code.
    *   **Run:** `python agent_langchain.py`

### 2. The Fraud Analyst
These scripts generate 10 fake credit card transactions (some normal, some highly suspicious) and ask the Groq LLM to act as a security analyst to determine the risk level of each.

*   `fraud_agent.py`: A pure terminal version that prints a color-coded report.
    *   **Run:** `python fraud_agent.py`
*   `fraud_app.py`: A Streamlit web dashboard version of the fraud analyst with a visual progress bar and summary metrics.
    *   **Run:** `streamlit run fraud_app.py`

### 3. The Multi-Tool Web App
*   `app.py`: This is the crown jewel of the project. It is a multi-page Streamlit web app that combines several tools into one dashboard:
    *   **Page 1: Fraud Analyst** (Same as `fraud_app.py`).
    *   **Page 2: AWS Documentation Search** (A UI version of `agent.py`).
    *   **Page 3: File Explorer** (An agent tool that uses a NodeJS MCP server to safely browse your local `Documents` folder).
    *   **Run:** `streamlit run app.py`

---

## What You Will Learn

By exploring this codebase, you will learn:
1.  **Tool Calling:** How to teach an LLM to recognize when it needs outside information and how to trigger a function to get it.
2.  **Model Context Protocol (MCP):** How to run MCP servers (like the AWS Docs server or the Filesystem server) as background processes and communicate with them via JSON-RPC.
3.  **Prompt Engineering:** How to write strict instructions so the LLM outputs data in a structured, predictable format (seen in the fraud analysis script).
4.  **Framework vs. Vanilla:** The pros and cons of writing agent logic from scratch (`agent.py`) versus using a heavy framework (`agent_langchain.py`).
5.  **Rapid UI Development:** How to wrap complex AI logic into a user-friendly web interface in minutes using Streamlit.