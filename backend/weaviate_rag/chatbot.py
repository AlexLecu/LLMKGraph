import chainlit as cl
from chainlit.input_widget import Select, Slider
import ollama
from openai import AsyncOpenAI
from weaviate_rag.rag_system import GraphRAGSystem
import time
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


@cl.on_chat_start
async def start_chat():
    cl.user_session.set("history", [])
    cl.user_session.set("model", DEFAULT_MODEL)
    cl.user_session.set("temperature", TEMPERATURE)

    settings = await cl.ChatSettings(
        [
            Select(
                id="model",
                label="Select Model",
                values=AVAILABLE_MODELS,
                initial_index=0,
            ),
            Slider(
                id="temperature",
                label="Temperature",
                initial=TEMPERATURE,
                min=0.1,
                max=1.0,
                step=0.1,
            )
        ]
    ).send()

    if settings:
        if "model" in settings:
            cl.user_session.set("model", settings["model"])
        if "temperature" in settings:
            cl.user_session.set("temperature", float(settings["temperature"]))


@cl.on_settings_update
async def on_settings_update(settings):
    if "model" in settings:
        cl.user_session.set("model", settings["model"])
    if "temperature" in settings:
        cl.user_session.set("temperature", float(settings["temperature"]))


@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="Early Signs of AMD",
            message="What subtle vision changes might indicate early stage AMD?",
            icon="/public/idea.svg",
        ),
        cl.Starter(
            label="Latest AMD research",
            message="What emerging treatments show promise for dry AMD?",
            icon="/public/learn.svg",
        ),
        cl.Starter(
            label="Current AMD Treatments",
            message="How do anti-VEGF injections compare to emerging gene therapies for wet AMD?",
            icon="/public/write.svg",
        )
    ]


@cl.on_message
async def main(message: cl.Message):
    start_time = time.time()
    user_input = message.content.strip()

    if user_input.lower() == "/clear":
        cl.user_session.set("history", [])
        await cl.Message("🔄 Chat history cleared. Starting fresh!").send()
        return

    sanitized_input = sanitize_input(user_input)

    if sanitized_input is None:
        await cl.Message(
            content="I can only provide factual information about AMD research. Your question contains patterns that may compromise security or exceed length limits. Please rephrase your question.").send()
        return

    model_name = cl.user_session.get("model", DEFAULT_MODEL)
    temperature = cl.user_session.get("temperature", TEMPERATURE)

    system_prompt = await create_system_prompt(sanitized_input, model_name)

    history = cl.user_session.get("history", [])

    if not history or history[0].get("role") != "system":
        history.insert(0, {"role": "system", "content": system_prompt})
    else:
        history[0]["content"] = system_prompt

    history.append({"role": "user", "content": sanitized_input})

    if len(history) > MAX_HISTORY * 2 + 1:
        history = [history[0]] + history[-(MAX_HISTORY * 2):]

    try:
        stream = stream_chat(history, model_name, temperature)
        final_answer = cl.Message(content="")

        if "deepseek-r1" in model_name:
            thinking = False
            async with cl.Step(name="Analyzing Research") as thinking_step:
                async for content in stream:
                    if content == "<think>":
                        thinking = True
                        continue

                    if content == "</think>":
                        thinking = False
                        thought_duration = round(time.time() - start_time)
                        thinking_step.name = f"Research Analysis ({thought_duration}s)"
                        await thinking_step.update()
                        continue

                    if thinking:
                        await thinking_step.stream_token(content)
                    else:
                        await final_answer.stream_token(content)
        else:
            async for content in stream:
                await final_answer.stream_token(content)

        await final_answer.send()

        history.append({"role": "assistant", "content": final_answer.content})
        cl.user_session.set("history", history)

    except Exception as e:
        logger.exception("Error in chat processing")
        error_msg = f"An error occurred: {str(e)}"
        await cl.Message(content=error_msg).send()
