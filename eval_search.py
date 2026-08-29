"""
Eval suite for the Digital FTE MCP server's search_documents tool.

Reads eval_cases.json, calls search_documents for each case via the MCP
protocol over stdio, checks expectations, and prints a pass/fail report.
"""

import json
import subprocess
import sys
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)
env = {**os.environ}

CASES_PATH = Path(__file__).parent / "eval_cases.json"
PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"


def call_mcp_tool(tool_name: str, arguments: dict) -> str | None:
    """Start the server, call a tool, return the text result."""
    import time

    proc = subprocess.Popen(
        [sys.executable, "server.py"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, env=env,
    )

    def send(msg: dict):
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()

    def recv():
        line = proc.stdout.readline()
        return json.loads(line) if line else None

    try:
        send({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "eval", "version": "0.1.0"},
            },
        })
        recv()  # init response

        send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        time.sleep(0.3)

        send({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": tool_name, "arguments": {"params": arguments}},
        })
        resp = recv()

        if resp and "result" in resp:
            for block in resp["result"].get("content", []):
                if block.get("type") == "text":
                    return block["text"]
        return None
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def parse_scores(text: str) -> list[float]:
    """Extract similarity scores from lines like '[0.685] "Refund Policy" — ...'"""
    import re
    return [float(m) for m in re.findall(r"\[(\d+\.\d+)\]", text)]


def run_eval():
    cases = json.loads(CASES_PATH.read_text())
    results = []

    for case in cases:
        cid = case["id"]
        q = case["question"]
        desc = case["description"]
        expected = case["expected_contains"]
        min_score = case.get("min_score", 0)

        print(f"\n--- Case {cid} [{case['type']}] ---")
        print(f"    Q: {q}")
        print(f"    {desc}")

        answer = call_mcp_tool("search_documents", {"question": q})

        if answer is None:
            print(f"    Result: {FAIL} — no response from server")
            results.append(False)
            continue

        scores = parse_scores(answer)
        top_score = scores[0] if scores else 0.0
        print(f"    A: {answer[:140]}{'...' if len(answer) > 140 else ''}")
        print(f"    Top score: {top_score:.3f}")

        ok = True
        issues = []

        for term in expected:
            if term.lower() not in answer.lower():
                issues.append(f"missing '{term}'")
                ok = False

        if min_score and top_score < min_score:
            issues.append(f"score {top_score:.3f} < min {min_score}")
            ok = False

        if ok:
            print(f"    Result: {PASS}")
        else:
            print(f"    Result: {FAIL} — {'; '.join(issues)}")

        results.append(ok)

    passed = sum(results)
    total = len(results)
    print(f"\n{'='*50}")
    print(f"Results: {passed}/{total} passed")
    if passed == total:
        print("All tests passed!")
    else:
        print(f"{total - passed} test(s) failed.")
    print(f"{'='*50}")
    return passed == total


if __name__ == "__main__":
    sys.exit(0 if run_eval() else 1)
