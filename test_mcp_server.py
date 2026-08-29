"""Smoke test for the MCP server — verifies tools are registered."""

import json
import subprocess
import sys
import os

from dotenv import load_dotenv

load_dotenv(override=True)
env = {**os.environ}

messages = "\n".join([
    json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0.1.0"},
        },
    }),
    json.dumps({
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {},
    }),
    json.dumps({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }),
]) + "\n"

proc = subprocess.Popen(
    [sys.executable, "server.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
)

stdout, stderr = proc.communicate(input=messages, timeout=15)

print("=== RAW RESPONSES ===")
for line in stdout.strip().splitlines():
    print(line)
    print()

print("=== PARSED ===")
for line in stdout.strip().splitlines():
    obj = json.loads(line)
    if obj.get("id") == 1:
        info = obj.get("result", {}).get("serverInfo", {})
        print(f"Server: {info.get('name')} v{info.get('version')}")
    elif obj.get("id") == 2:
        tools = obj.get("result", {}).get("tools", [])
        print(f"Tools registered ({len(tools)}):")
        for t in tools:
            print(f"  - {t['name']}: {t.get('description', '')[:80]}...")
