"""Verify the MCP server works by connecting a client and calling its tools."""
import sys
import asyncio
from fastmcp import Client
from fastmcp.client.transports import StdioTransport


async def main():
    # Launch the server AS A MODULE (python -m src.mcp_server) so its relative
    # imports work, using sys.executable so the subprocess uses THIS venv's Python.
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "src.mcp_server"],
        cwd=".",
    )
    async with Client(transport) as client:
        tools = await client.list_tools()
        print("tools exposed by the server:")
        for t in tools:
            print(f"  - {t.name}: {t.description[:60]}...")

        print("\ncalling get_quote('NVDA')...")
        result = await client.call_tool("get_quote", {"ticker": "NVDA"})
        print("  result:", result.data)

        print("\ncalling get_price_history('NVDA', days=5)...")
        result = await client.call_tool("get_price_history", {"ticker": "NVDA", "days": 5})
        print("  result:", result.data)


if __name__ == "__main__":
    asyncio.run(main())