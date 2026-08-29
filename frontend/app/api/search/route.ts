import { NextRequest, NextResponse } from "next/server";
import { spawn, ChildProcess } from "child_process";
import path from "path";

const SERVER_PY = path.resolve(process.cwd(), "../server.py");
const UV_BIN = process.env.UV_BIN || "uv";

function callMcpTool(
  toolName: string,
  args: Record<string, unknown>
): Promise<string> {
  return new Promise((resolve, reject) => {
    const proc: ChildProcess = spawn(UV_BIN, ["run", "python", SERVER_PY], {
      stdio: ["pipe", "pipe", "pipe"],
      cwd: path.resolve(process.cwd(), ".."),
      env: { ...process.env },
    });

    let stdout = "";
    let stderr = "";
    let resolved = false;

    proc.stdout!.on("data", (chunk: Buffer) => {
      stdout += chunk.toString();
      const lines = stdout.split("\n");
      // Keep the last incomplete line in the buffer
      stdout = lines.pop()!;

      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const msg = JSON.parse(line);
          if (msg.id === 2 && !resolved) {
            resolved = true;
            proc.kill();
            const content = msg.result?.content;
            if (Array.isArray(content)) {
              const textBlock = content.find(
                (b: { type: string }) => b.type === "text"
              );
              if (textBlock) {
                resolve(textBlock.text);
                return;
              }
            }
            resolve(JSON.stringify(msg));
          }
        } catch {
          // not JSON, skip
        }
      }
    });

    proc.stderr!.on("data", (chunk: Buffer) => {
      stderr += chunk.toString();
    });

    proc.on("error", (err) => {
      if (!resolved) {
        resolved = true;
        reject(err);
      }
    });

    proc.on("close", () => {
      if (!resolved) {
        resolved = true;
        reject(new Error(`Server closed. stderr: ${stderr.slice(0, 500)}`));
      }
    });

    // Send MCP handshake + tool call, one message at a time
    const send = (msg: object) => {
      proc.stdin!.write(JSON.stringify(msg) + "\n");
    };

    send({
      jsonrpc: "2.0",
      id: 1,
      method: "initialize",
      params: {
        protocolVersion: "2025-03-26",
        capabilities: {},
        clientInfo: { name: "nextjs-frontend", version: "0.1.0" },
      },
    });

    // Wait for init response before sending the rest
    const waitForInit = () => {
      const trySendRest = () => {
        send({
          jsonrpc: "2.0",
          method: "notifications/initialized",
          params: {},
        });
        send({
          jsonrpc: "2.0",
          id: 2,
          method: "tools/call",
          params: { name: toolName, arguments: { params: args } },
        });
      };
      // Give the server a moment to be ready after init
      setTimeout(trySendRest, 200);
    };
    waitForInit();
  });
}

export async function POST(req: NextRequest) {
  try {
    const { question } = await req.json();
    if (!question || typeof question !== "string") {
      return NextResponse.json(
        { error: "Missing 'question' field" },
        { status: 400 }
      );
    }

    const answer = await callMcpTool("search_documents", { question });
    return NextResponse.json({ answer });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
