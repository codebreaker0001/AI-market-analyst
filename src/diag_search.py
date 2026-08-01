"""See what search_filings actually returns through the MCP server."""
import sys, asyncio
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

async def main():
    transport = StdioTransport(command=sys.executable, args=["-m", "src.mcp_server"], cwd=".")
    async with Client(transport) as client:
        r = await client.call_tool("search_filings",
                                   {"query": "datacenter demand", "ticker": "NVDA", "k": 2})
        print(r.data)

asyncio.run(main())