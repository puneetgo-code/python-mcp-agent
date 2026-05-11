import asyncio
import json
import os
from groq import AsyncGroq
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# Minimal JSON Schema for each tool that Groq can reliably use.
# Only the most essential parameters are included.
_TOOL_SCHEMAS: dict[str, dict] = {
    "search_documentation": {
        "type": "object",
        "properties": {
            "search_phrase": {
                "type": "string",
                "description": "Search phrase to find in AWS documentation",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return",
            },
        },
        "required": ["search_phrase"],
    },
    "read_documentation": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL of the AWS documentation page to read",
            },
            "max_length": {
                "type": "integer",
                "description": "Maximum characters to return",
            },
        },
        "required": ["url"],
    },
    "read_sections": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL of the AWS documentation page",
            },
            "section_titles": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Section titles to extract",
            },
        },
        "required": ["url", "section_titles"],
    },
    "recommend": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL of the AWS documentation page",
            },
        },
        "required": ["url"],
    },
}


def _tool_schema_for(tool) -> dict:
    """Return a Groq-compatible function definition for *tool*.

    Uses a hand-written minimal schema instead of the raw MCP
    ``inputSchema`` to avoid JSON Schema features (``anyOf`` with
    nullable types, ``title``, ``default``, numeric ``exclusive*``
    bounds) that Groq's function-calling validator chokes on.
    """
    schema = _TOOL_SCHEMAS.get(tool.name)
    if schema is not None:
        return schema
    # Fallback: build the safest possible schema for unknown tools.
    return {"type": "object", "properties": {}}


async def main():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("Error: GROQ_API_KEY environment variable is not set.")
        print("Please set it and try again.")
        return

    groq_client = AsyncGroq(api_key=api_key)

    docs_params = StdioServerParameters(
        command="uvx",
        args=["awslabs.aws-documentation-mcp-server@latest"],
    )

    async with stdio_client(docs_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            print("AWS Documentation Search with Groq Summarization")
            print("Type 'quit' to exit.\n")

            # Step 1: Fetch all available tools from the MCP server
            # and convert them into Groq-compatible function definitions
            # so Groq knows what tools exist and how to call them.
            tools_result = await session.list_tools()
            groq_tools = []
            for t in tools_result.tools:
                groq_tools.append({
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description or "",
                        # Use hand-written minimal schemas instead of
                        # the raw MCP inputSchema to avoid JSON Schema
                        # features that Groq's validator cannot handle.
                        "parameters": _tool_schema_for(t),
                    },
                })

            while True:
                query = await asyncio.to_thread(
                    input, "What AWS service do you want to learn about? "
                )
                if query.strip().lower() == "quit":
                    print("Goodbye!")
                    break

                # Step 2: Send the user question to Groq alongside the
                # full list of available tools. Groq decides which tool
                # to invoke and with what arguments (function calling).

                # Debug: print the exact schema being sent for
                # search_documentation so we can inspect it.
                for gt in groq_tools:
                    if gt["function"]["name"] == "search_documentation":
                        print("DEBUG normalized search_documentation schema:")
                        print(json.dumps(gt, indent=2))
                        print()

                try:
                    response = await groq_client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "user", "content": query}],
                        tools=groq_tools,
                        tool_choice="auto",
                    )
                except Exception as e:
                    print(f"\nGroq API error: {e}")
                    if hasattr(e, "response") and e.response is not None:
                        print(f"Response body: {e.response.text}")
                    print("-" * 60)
                    continue

                message = response.choices[0].message

                # Step 3: If Groq answered directly (no tool call),
                # print the response and continue the loop.
                if not message.tool_calls:
                    print(f"\n{message.content}")
                    print("\n" + "-" * 60)
                    continue

                # Step 4: Extract the tool name and arguments from
                # Groq's response and invoke the selected tool on the
                # MCP server.
                tool_call = message.tool_calls[0]
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                print(f"\nCalling tool: {tool_name}")
                print(f"DEBUG raw args: {tool_call.function.arguments}")
                print(f"DEBUG parsed args: {json.dumps(tool_args)}\n")

                result = await session.call_tool(tool_name, tool_args)

                # Parse the JSON text content returned by the tool.
                docs_content = []
                for content in result.content:
                    try:
                        data = json.loads(content.text)
                    except (json.JSONDecodeError, AttributeError):
                        continue

                    results = data.get("search_results", [])
                    if results:
                        for r in results:
                            docs_content.append({
                                "title": r.get("title", ""),
                                "url": r.get("url", ""),
                                "context": r.get("context", ""),
                            })

                if not docs_content:
                    print("No results found.")
                    print("-" * 60)
                    continue

                # Step 5: Send the raw tool output back to Groq and
                # ask it to produce a final plain-English summary for
                # the user.
                docs_text = "\n\n".join(
                    f"Title: {d['title']}\nURL: {d['url']}\nSummary: {d['context']}"
                    for d in docs_content
                )

                final_response = await groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{
                        "role": "user",
                        "content": (
                            "You are an AWS expert. Below are search results "
                            f"about '{query}'. Summarize in plain English:\n\n"
                            f"{docs_text}"
                        ),
                    }],
                )

                summary = final_response.choices[0].message.content
                print(summary)
                print("\n" + "-" * 60)


if __name__ == "__main__":
    asyncio.run(main())
