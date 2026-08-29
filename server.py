"""
MCP Server for Digital FTE knowledge-base tools.

Exposes three tools over stdio:
  - save_note
  - add_document
  - search_documents

Reads DATABASE_URL and GEMINI_API_KEY from .env.
"""

import asyncio
import os
import json
from typing import List, Optional

import asyncpg
import google.generativeai as genai
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.mcpserver import MCPServer

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

SIMILARITY_THRESHOLD = 0.65

mcp = MCPServer(
    "digital_fte",
    title="Digital FTE Knowledge Base",
    version="0.1.0",
)


# ── Input models ──────────────────────────────────────────────────────────────

class SaveNoteInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    content: str = Field(..., description="The text of the note to save.", min_length=1)


class AddDocumentInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(..., description="A short descriptive title for the document.", min_length=1)
    text: str = Field(..., description="The full text content of the document.", min_length=1)


class SearchDocumentsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    question: str = Field(..., description="The question to search for in the knowledge base.", min_length=1)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_conn() -> asyncpg.Connection:
    return await asyncpg.connect(DATABASE_URL)


# ── Tools ─────────────────────────────────────────────────────────────────────

@mcp.tool(
    name="save_note",
    annotations={
        "title": "Save a Note",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def save_note(params: SaveNoteInput) -> str:
    """Save a note to the database and log the action.

    Args:
        params: The note content to save.

    Returns:
        Confirmation message with the saved note.
    """
    conn = await _get_conn()
    try:
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO notes (content, created_at) VALUES ($1, now())",
                params.content,
            )
            await conn.execute(
                "INSERT INTO audit_log (action, detail, created_at) VALUES ($1, $2, now())",
                "note_saved",
                f"Saved note: {params.content[:80]}",
            )
        return f"Note saved: {params.content}"
    except Exception as e:
        return f"Error saving note: {e}"
    finally:
        await conn.close()


@mcp.tool(
    name="add_document",
    annotations={
        "title": "Add Document to Knowledge Base",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def add_document(params: AddDocumentInput) -> str:
    """Add a document to the knowledge base. Saves the document, chunks it,
    generates vector embeddings for each chunk using Gemini gemini-embedding-001,
    and stores them for semantic search.

    Args:
        params: Title and full text of the document.

    Returns:
        Confirmation with the number of chunks created.
    """
    conn = await _get_conn()
    try:
        doc_id = await conn.fetchval(
            """INSERT INTO documents (title, content, doc_type, created_at, updated_at)
               VALUES ($1, $2, 'text', now(), now())
               RETURNING id""",
            params.title,
            params.text,
        )

        chunk_size = 400
        overlap = 80
        chunks: List[str] = []
        for i in range(0, len(params.text), chunk_size - overlap):
            chunk = params.text[i : i + chunk_size].strip()
            if chunk:
                chunks.append(chunk)

        embedding_result = await asyncio.to_thread(
            lambda: genai.embed_content(
                model="models/gemini-embedding-001",
                content=chunks,
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=1536,
            )
        )
        vectors = embedding_result["embedding"]

        for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
            await conn.execute(
                """INSERT INTO embeddings (document_id, chunk_index, chunk_text, embedding, created_at)
                   VALUES ($1, $2, $3, $4, now())""",
                doc_id,
                idx,
                chunk,
                str(vec),
            )

        await conn.execute(
            "UPDATE documents SET chunk_count = $1 WHERE id = $2",
            len(chunks),
            doc_id,
        )
        await conn.execute(
            "INSERT INTO audit_log (action, detail, created_at) VALUES ($1, $2, now())",
            "document_added",
            f"Added '{params.title}' with {len(chunks)} chunks",
        )

        return f"Document '{params.title}' saved. {len(chunks)} chunks embedded (1536-dim vectors)."
    except Exception as e:
        return f"Error adding document: {e}"
    finally:
        await conn.close()


@mcp.tool(
    name="search_documents",
    annotations={
        "title": "Search Documents by Semantics",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def search_documents(params: SearchDocumentsInput) -> str:
    """Search the knowledge base for chunks relevant to a question using
    vector cosine similarity (HNSW index).

    Args:
        params: The question to search for.

    Returns:
        The top matching chunks with similarity scores, or a not-found message.
    """
    conn = await _get_conn()
    try:
        embedding_result = await asyncio.to_thread(
            lambda: genai.embed_content(
                model="models/gemini-embedding-001",
                content=[params.question],
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=1536,
            )
        )
        vec = embedding_result["embedding"][0]

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

        if top_score < SIMILARITY_THRESHOLD:
            return "I don't have information about that."

        results = []
        for r in rows:
            results.append(
                f"[{r['similarity']:.3f}] \"{r['title']}\" — {r['chunk_text']}"
            )

        await conn.execute(
            "INSERT INTO audit_log (action, detail, created_at) VALUES ($1, $2, now())",
            "document_searched",
            f"Query: {params.question[:80]}",
        )

        return "\n".join(results)
    except Exception as e:
        return f"Error searching documents: {e}"
    finally:
        await conn.close()


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
