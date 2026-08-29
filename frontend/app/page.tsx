"use client";

import { useState, useRef, useEffect } from "react";

interface Message {
  role: "user" | "assistant";
  text: string;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send() {
    const q = input.trim();
    if (!q || loading) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: q }]);
    setLoading(true);

    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      const data = await res.json();
      const answer = data.error
        ? `Error: ${data.error}`
        : data.answer || "No response.";
      setMessages((prev) => [...prev, { role: "assistant", text: answer }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: `Error: ${String(err)}` },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div className="container">
      <header className="header">
        <h1>Digital FTE Search</h1>
        <p className="subtitle">Ask a question about your knowledge base</p>
      </header>

      <div className="chat">
        {messages.length === 0 && (
          <div className="empty">
            No messages yet. Type a question below to get started.
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`bubble ${msg.role}`}>
            <span className="role">{msg.role === "user" ? "You" : "KB"}</span>
            <p>{msg.text}</p>
          </div>
        ))}
        {loading && (
          <div className="bubble assistant loading">
            <span className="role">KB</span>
            <p>Searching...</p>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="input-row">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question..."
          disabled={loading}
        />
        <button onClick={send} disabled={loading || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  );
}
