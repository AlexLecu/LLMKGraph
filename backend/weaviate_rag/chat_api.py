"""HTTP API for the chat page of the Vue UI (alternative to the Chainlit UI).

    GET  /api/chat/models   -> {"models": [...], "default": "..."}
    POST /api/chat          {"messages": [{"role": "user"|"assistant", "content": "..."}], "model": "..."}
                            -> the answer, streamed as plain text

Plain HTTP (no WebSockets), so it works behind proxies that do not forward them.
The conversation lives in the browser; every request carries the recent turns.
Run with:  uvicorn chat_api:app --host 0.0.0.0 --port 7860
"""
import asyncio
import os
import time
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from weaviate_rag.chat_core import (
    AVAILABLE_MODELS, DEFAULT_MODEL, MAX_HISTORY, TEMPERATURE,
    generate_chat_prompt, logger, retrieve, sanitize_input, stream_chat,
)

# Per-client budget, on top of the provider's own spend limit
RATE_LIMIT = int(os.getenv("CHAT_RATE_LIMIT", "30"))           # requests ...
RATE_WINDOW = int(os.getenv("CHAT_RATE_WINDOW", "600"))        # ... per this many seconds
MAX_CONTENT = 4000

REFUSAL = ("I can only provide factual information about AMD research. Your question contains patterns "
           "that may compromise security or exceed length limits. Please rephrase your question.")

app = FastAPI(title="LLMKGraph chat", docs_url=None, redoc_url=None)
_requests: dict[str, deque] = defaultdict(deque)


class Turn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    messages: list[Turn] = Field(min_length=1)
    model: str | None = None


def _client_id(request: Request) -> str:
    # First hop of X-Forwarded-For is the browser when behind the proxies
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "?")


def _check_rate(client: str):
    now = time.time()
    q = _requests[client]
    while q and now - q[0] > RATE_WINDOW:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        raise HTTPException(429, f"Too many questions; please wait a few minutes (limit {RATE_LIMIT} per "
                                 f"{RATE_WINDOW // 60} min).")
    q.append(now)


@app.get("/api/chat/models")
def models():
    return {"models": AVAILABLE_MODELS, "default": DEFAULT_MODEL}


@app.post("/api/chat")
async def chat(body: ChatRequest, request: Request):
    if body.messages[-1].role != "user":
        raise HTTPException(400, "The last message must come from the user.")
    model = body.model or DEFAULT_MODEL
    if model not in AVAILABLE_MODELS:
        raise HTTPException(400, f"Unknown model {model!r}.")
    _check_rate(_client_id(request))

    question = sanitize_input(body.messages[-1].content.strip())

    async def answer():
        if question is None:
            yield REFUSAL
            return
        try:
            # Retrieval is synchronous (Weaviate + one LLM call): keep the event loop free
            context = await asyncio.to_thread(retrieve, question, model)
            history = [{"role": t.role, "content": t.content[:MAX_CONTENT]}
                       for t in body.messages[-(MAX_HISTORY * 2):]]
            history.insert(0, {"role": "system", "content": generate_chat_prompt(context, question)})
            async for chunk in stream_chat(history, model, TEMPERATURE):
                yield chunk
        except Exception:
            logger.exception("chat request failed")
            yield "\n\n_Sorry, the language model did not answer. Please try again in a moment._"

    # X-Accel-Buffering: let nginx pass the tokens through as they arrive
    return StreamingResponse(answer(), media_type="text/plain; charset=utf-8",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/chat/health")
def health():
    return {"status": "ok"}
