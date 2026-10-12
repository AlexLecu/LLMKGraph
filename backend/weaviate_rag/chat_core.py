"""Chat logic shared by the Chainlit UI (chatbot.py) and the HTTP API (chat_api.py):
LLM backend configuration, input sanitisation, Graph-RAG retrieval and streaming."""
import ollama
from openai import AsyncOpenAI
from weaviate_rag.rag_system import GraphRAGSystem
import logging
import re
import sys
import os
from dotenv import load_dotenv
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from backend.prompts import generate_chat_prompt

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- LLM backend -------------------------------------------------------------
# CHAT_PROVIDER=ollama (default): local Ollama, models from CHAT_MODELS.
# CHAT_PROVIDER=openai-compatible: any OpenAI-style chat endpoint, e.g.
#   Groq        CHAT_API_BASE_URL=https://api.groq.com/openai/v1
#   OpenRouter  CHAT_API_BASE_URL=https://openrouter.ai/api/v1
#   Gemini      CHAT_API_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
#   Together    CHAT_API_BASE_URL=https://api.together.xyz/v1
# with CHAT_API_KEY and CHAT_MODELS="model-a,model-b" (first one is the default).
CHAT_PROVIDER = os.getenv("CHAT_PROVIDER", "ollama").strip().lower()
CHAT_API_BASE_URL = os.getenv("CHAT_API_BASE_URL") or None
CHAT_API_KEY = os.getenv("CHAT_API_KEY") or "ollama"
_default_models = "llama3.2,deepseek-r1,gemma3" if CHAT_PROVIDER == "ollama" else ""
AVAILABLE_MODELS = [m.strip() for m in os.getenv("CHAT_MODELS", _default_models).split(",") if m.strip()]
if not AVAILABLE_MODELS:
    raise RuntimeError("CHAT_MODELS must list at least one model when CHAT_PROVIDER != ollama")

DEFAULT_MODEL = AVAILABLE_MODELS[0]
MAX_HISTORY = 10
TEMPERATURE = 0.3

_openai_client = AsyncOpenAI(api_key=CHAT_API_KEY, base_url=CHAT_API_BASE_URL) \
    if CHAT_PROVIDER == "openai-compatible" else None


def build_model_config(model_name):
    """Model config handed to GraphRAGSystem for the retrieval summary step."""
    if CHAT_PROVIDER == "openai-compatible":
        return {"provider": "openai-compatible", "model_name": model_name,
                "api_key": CHAT_API_KEY, "base_url": CHAT_API_BASE_URL}
    return {"provider": "ollama", "model_name": model_name}


async def stream_chat(history, model_name, temperature):
    """Yield response text chunks from whichever LLM backend is configured."""
    if _openai_client is not None:
        stream = await _openai_client.chat.completions.create(
            model=model_name, messages=history, temperature=temperature, stream=True)
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    else:
        sync_stream = ollama.chat(model=model_name, messages=history, stream=True,
                                  options={"temperature": temperature})
        async for chunk in async_generator(sync_stream):
            yield chunk['message']['content']


def sanitize_input(text):
    """Enhanced sanitization to prevent prompt injection and control character attacks."""
    if text is None:
        return None

    text = text.replace('\r', '').replace('\x08', '')

    if len(text) > 500:
        logger.warning(f"Input exceeds maximum length: {len(text)} chars")
        return None

    injection_patterns = [
        r'(?i)\bignore\b.*\binstructions\b',
        r'(?i)\bdisregard\b.*\binstructions\b',
        r'(?i)\bforget\b.*\bguidelines\b',
        r'(?i)\bjust\s+say\b',
        r'(?i)\bjust\s+print\b',
        r'(?i)\boutput\s+the\s+following\b',
        r'(?i)\bverbatim\b',
        r'(?i)\bSTAN\b',
        r'(?i)\bDAN\b',
        r'(?i)\bDUDE\b',
        r'(?i)\bANTI-DAN\b'
    ]

    for pattern in injection_patterns:
        if re.search(pattern, text):
            logger.warning(f"Potential prompt injection detected: {text[:50]}...")
            return None

    return text


def retrieve(user_input, model_name=None):
    try:
        sanitized_input = sanitize_input(user_input)

        if sanitized_input is None:
            return "No relevant information available due to potential security concerns."

        analyzer = GraphRAGSystem(sanitized_input, build_model_config(model_name or DEFAULT_MODEL))
        context = analyzer.analyze()

        return context
    except Exception as e:
        logger.exception("Error in retrieve function")
        return f"Error retrieving information: {str(e)}"


async def async_generator(sync_gen):
    while True:
        try:
            yield next(sync_gen)
        except StopIteration:
            break


async def create_system_prompt(user_input, model_name=None):
    sanitized_input = sanitize_input(user_input)

    context = retrieve(sanitized_input, model_name)
    logger.info("Retrieved context for user query")
    system_prompt = generate_chat_prompt(context, sanitized_input)

    return system_prompt
