#!/usr/bin/env python3
"""
UCP/MCP product discovery client.

Instead of scraping HTML, this talks directly to a store's declared MCP
endpoint (found via /.well-known/ucp) using the same JSON-RPC protocol
AI agents use to browse a UCP-enabled storefront.

Flow:
    1. GET /.well-known/ucp          -> find the MCP service endpoint
    2. POST {method: "initialize"}   -> MCP handshake
    3. POST {method: "tools/list"}   -> discover available tool names/schemas
    4. POST {method: "tools/call"}   -> call the catalog-search tool

Usage:
    python3 ucp_client.py blueprint.bryanjohnson.com "vitamin d"
"""

import sys
import json
import uuid
import requests

TIMEOUT = 15
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# Shopify's publicly hosted example agent profile. It declares the base UCP
# capabilities needed to call read-only catalog tools. For real usage you'd
# host your own profile (see https://shopify.dev/docs/agents/get-started/profile)
# but this is fine for search/lookup/get_product testing.
AGENT_PROFILE_URL = "https://shopify.dev/ucp/agent-profiles/2026-08-25/valid-with-capabilities.json"


def get_manifest(domain):
    url = f"https://{domain}/.well-known/ucp"
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def find_mcp_endpoint(manifest):
    """Walk the manifest's services map for an entry with transport == mcp."""
    services = manifest.get("ucp", {}).get("services", {})
    for service_name, entries in services.items():
        for entry in entries:
            if entry.get("transport") == "mcp":
                return entry.get("endpoint")
    return None


def rpc_call(endpoint, method, params=None, request_id=None):
    """Send one JSON-RPC 2.0 request to the MCP endpoint."""
    payload = {
        "jsonrpc": "2.0",
        "id": request_id or str(uuid.uuid4()),
        "method": method,
    }
    if params is not None:
        payload["params"] = params

    resp = requests.post(endpoint, headers=HEADERS, json=payload, timeout=TIMEOUT)
    if not resp.ok:
        # Surface the server's actual error body instead of a bare status
        # code — this is almost always where the real diagnosis lives
        # (e.g. "missing required field", "unknown argument").
        print(f"\n[HTTP {resp.status_code}] response body:")
        try:
            print(json.dumps(resp.json(), indent=2))
        except ValueError:
            print(resp.text)
        resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"MCP error on {method}: {data['error']}")
    return data.get("result")


def mcp_initialize(endpoint):
    return rpc_call(endpoint, "initialize", {
        "protocolVersion": "2026-06-18",
        "capabilities": {},
        "clientInfo": {"name": "ucp-demo-client", "version": "0.1"},
    })


def mcp_list_tools(endpoint):
    result = rpc_call(endpoint, "tools/list")
    return result.get("tools", []) if result else []


def find_search_tool(tools):
    """Pick the tool that looks like catalog/product search."""
    for tool in tools:
        name = tool.get("name", "").lower()
        if "search" in name and ("catalog" in name or "product" in name):
            return tool
    # fallback: anything with "search" in the name
    for tool in tools:
        if "search" in tool.get("name", "").lower():
            return tool
    return None


def mcp_call_tool(endpoint, tool_name, arguments):
    return rpc_call(endpoint, "tools/call", {
        "name": tool_name,
        "arguments": arguments,
    })


def main():
    if len(sys.argv) < 3:
        print('Usage: python3 ucp_client.py <domain> "<search query>"')
        sys.exit(1)

    domain = sys.argv[1]
    query = sys.argv[2]

    print(f"[1/4] Fetching manifest for {domain} ...")
    manifest = get_manifest(domain)

    print("[2/4] Locating MCP endpoint ...")
    endpoint = find_mcp_endpoint(manifest)
    if not endpoint:
        print("No MCP transport declared in manifest. Full manifest:")
        print(json.dumps(manifest, indent=2))
        sys.exit(1)
    print(f"      -> {endpoint}")

    print("[3/4] Initializing MCP session ...")
    init_result = mcp_initialize(endpoint)
    print(f"      -> server: {init_result.get('serverInfo', init_result)}")

    print("[3.5/4] Listing available tools ...")
    tools = mcp_list_tools(endpoint)
    print(f"      -> {len(tools)} tools found:")
    for t in tools:
        print(f"         - {t.get('name')}: {t.get('description', '')[:80]}")

    search_tool = find_search_tool(tools)
    if not search_tool:
        print("\nCouldn't auto-detect a catalog-search tool. Inspect the")
        print("tool list above and call mcp_call_tool() manually with the")
        print("right name + argument schema (see each tool's 'inputSchema').")
        sys.exit(1)

    tool_name = search_tool["name"]
    print(f"\n      Full schema for '{tool_name}':")
    print(json.dumps(search_tool.get("inputSchema", {}), indent=2))

    print(f"\n[4/4] Calling '{tool_name}' with query={query!r} ...")

    # Correct UCP catalog-search request shape: meta.ucp-agent.profile
    # identifies the calling agent; the actual query is nested under
    # catalog.query, not a bare top-level "query" field.
    arguments = {
        "meta": {
            "ucp-agent": {
                "profile": AGENT_PROFILE_URL,
            }
        },
        "catalog": {
            "query": query,
        },
    }
    result = mcp_call_tool(endpoint, tool_name, arguments)

    products = (result or {}).get("structuredContent", {}).get("products", [])
    print(f"\n=== {len(products)} product(s) found ===")

    print("\n=== Result ===")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()