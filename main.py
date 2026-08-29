import asyncio
import os
import re
import google.generativeai as genai
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
from dotenv import load_dotenv
from agents import Agent, Runner, function_tool
from agents.extensions.models.litellm_model import LitellmModel

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

SKILL_DIR = Path(__file__).resolve().parent / ".claude" / "skills" / "summarize-ticket"


def load_skill(name: str) -> str:
    skill_md = SKILL_DIR / "SKILL.md"
    raw = skill_md.read_text(encoding="utf-8")
    _, body = raw.split("---", 2)[1:]
    return body.strip()


@function_tool
async def save_note(content: str) -> str:
    """Save a note and log the action. Inserts into notes and audit_log in one transaction.

    Args:
        content: The text of the note to save.
    """
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO notes (content, created_at) VALUES ($1, $2)",
                content,
                datetime.now(timezone.utc),
            )
            await conn.execute(
                "INSERT INTO audit_log (action, detail, created_at) VALUES ($1, $2, $3)",
                "note_saved",
                f"Saved note: {content[:80]}",
                datetime.now(timezone.utc),
            )
        return f"Note saved: {content}"
    finally:
        await conn.close()


@function_tool
async def add_document(title: str, text: str) -> str:
    """Add a document to the knowledge base. Saves the document, chunks it, generates
    vector embeddings for each chunk using Gemini, and stores them for semantic search.

    Args:
        title: A short descriptive title for the document.
        text: The full text content of the document.
    """
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # 1) Insert the document row
        doc_id = await conn.fetchval(
            """INSERT INTO documents (title, content, doc_type, created_at, updated_at)
               VALUES ($1, $2, 'text', now(), now())
               RETURNING id""",
            title,
            text,
        )

        # 2) Chunk the text (~400 chars per chunk, 80-char overlap)
        chunk_size = 400
        overlap = 80
        chunks = []
        for i in range(0, len(text), chunk_size - overlap):
            chunk = text[i : i + chunk_size].strip()
            if chunk:
                chunks.append(chunk)

        # 3) Generate embeddings in batch via Gemini gemini-embedding-001
        embedding_result = await asyncio.to_thread(
            lambda: genai.embed_content(
                model="models/gemini-embedding-001",
                content=chunks,
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=1536,
            )
        )
        vectors = embedding_result["embedding"]

        # 4) Insert each chunk + its embedding
        for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
            await conn.execute(
                """INSERT INTO embeddings (document_id, chunk_index, chunk_text, embedding, created_at)
                   VALUES ($1, $2, $3, $4, now())""",
                doc_id,
                idx,
                chunk,
                str(vec),
            )

        # 5) Update chunk_count and log
        await conn.execute(
            "UPDATE documents SET chunk_count = $1 WHERE id = $2",
            len(chunks),
            doc_id,
        )
        await conn.execute(
            "INSERT INTO audit_log (action, detail, created_at) VALUES ($1, $2, now())",
            "document_added",
            f"Added '{title}' with {len(chunks)} chunks",
        )

        return f"Document '{title}' saved. {len(chunks)} chunks embedded (1536-dim vectors)."
    finally:
        await conn.close()


@function_tool
async def search_documents(question: str) -> str:
    """Search the knowledge base for chunks relevant to a question using vector similarity.

    Args:
        question: The user's question to search for.
    """
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # 1) Embed the question with the same model/dimension
        embedding_result = await asyncio.to_thread(
            lambda: genai.embed_content(
                model="models/gemini-embedding-001",
                content=[question],
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=1536,
            )
        )
        vec = embedding_result["embedding"][0]

        # 2) Cosine similarity search via the HNSW index
        rows = await conn.fetch(
            """SELECT e.chunk_text, d.title,
                      1 - (e.embedding <=> $1::vector) AS similarity
               FROM embeddings e
               JOIN documents d ON d.id = e.document_id
               ORDER BY e.embedding <=> $1::vector
               LIMIT 5""",
            str(vec),
        )

        if not rows:
            return "No relevant documents found."

        top_score = rows[0]["similarity"]
        if top_score < 0.65:
            return "I don't have information about that."

        results = []
        for r in rows:
            results.append(
                f"[{r['similarity']:.3f}] \"{r['title']}\" — {r['chunk_text']}"
            )

        await conn.execute(
            "INSERT INTO audit_log (action, detail, created_at) VALUES ($1, $2, now())",
            "document_searched",
            f"Query: {question[:80]}",
        )

        return "\n".join(results)
    finally:
        await conn.close()


model = LitellmModel(
    model="gemini/gemini-3.6-flash",
    api_key=os.environ.get("GEMINI_API_KEY"),
)

skill_body = load_skill("summarize-ticket")

agent = Agent(
    name="Assistant",
    model=model,
    instructions=(
        "You are a helpful assistant. Be concise. "
        "When the user asks you to remember or save something, use the save_note tool. "
        "When the user asks you to add a document to the knowledge base, use the add_document tool. "
        "When the user asks a question that might be answered by stored documents, use the search_documents tool first, then answer based on the results.\n\n"
        f"{skill_body}"
    ),
    tools=[save_note, add_document, search_documents],
)


async def main():
    result = await Runner.run(
        agent,
        "Can I still get my money back if I bought it 6 weeks ago?",
    )
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
