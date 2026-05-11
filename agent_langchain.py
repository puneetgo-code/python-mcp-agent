import asyncio
import os

from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_groq import ChatGroq


async def main():
    # Load API key from environment
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("Error: GROQ_API_KEY environment variable is not set.")
        return

    # Step 1: Create the Groq LLM via langchain-groq.
    llm = ChatGroq(
        api_key=api_key,
        model="llama-3.3-70b-versatile",
    )

    # Step 2: Connect to the AWS Documentation MCP server and load
    # its tools as LangChain BaseTool objects.
    # MultiServerMCPClient handles spawning the subprocess and
    # maintaining the MCP session internally.
    client = MultiServerMCPClient(
        {
            "aws-docs": {
                "transport": "stdio",
                "command": "uvx",
                "args": ["awslabs.aws-documentation-mcp-server@latest"],
            },
        }
    )
    tools = await client.get_tools()

    # Step 3: Create a LangChain agent (a CompiledStateGraph that
    # calls the LLM in a loop, invoking tools whenever the model
    # responds with tool_calls).
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=(
            "You are an AWS expert. Use the available tools to "
            "answer the user's questions about AWS services. "
            "Answer in plain English."
        ),
        debug=False,
    )

    print("AWS Documentation Agent (LangChain)")
    print("Type 'quit' to exit.\n")

    # Step 4: Interactive loop — take user questions and let the
    # agent answer them using the AWS documentation tools.
    while True:
        query = await asyncio.to_thread(
            input, "What AWS service do you want to learn about? "
        )
        if query.strip().lower() == "quit":
            print("Goodbye!")
            break

        # The agent expects a messages list with the standard
        # LangChain message format.
        result = await agent.ainvoke(
            {"messages": [("human", query)]},
        )

        # The final response is the last AI message in the list.
        for msg in reversed(result["messages"]):
            if hasattr(msg, "content") and msg.content:
                print(f"\n{msg.content}")
                break

        print("\n" + "-" * 60)


if __name__ == "__main__":
    asyncio.run(main())
