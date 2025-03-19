import chainlit as cl
from chainlit.input_widget import Select, Slider
import ollama
from rag_system import KGRAGSystem
import time
import logging
import re
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from backend.prompts import generate_chat_prompt

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEFAULT_MODEL = "deepseek-r1"
MAX_HISTORY = 10
TEMPERATURE = 0.3


def sanitize_input(text):
    """Remove or replace potentially problematic control characters."""
    text = re.sub(r'[\r\x08]', '', text)
    return text


def retrieve(user_input):
    try:
        sanitized_input = sanitize_input(user_input)

        rag_system = KGRAGSystem()
        kg_result = rag_system.query(sanitized_input)

        if kg_result.get("error"):
            logger.error(f"Knowledge retrieval error: {kg_result['error']}")
            return f"Knowledge retrieval error: {kg_result['error']}"

        context = kg_result.get('context', 'No further information is available.')
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


async def create_system_prompt(user_input):
    context = retrieve(user_input)
    logger.info("Retrieved context for user query")

    system_prompt = generate_chat_prompt(context, user_input)

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
                values=["deepseek-r1", "gemma3", "llama3.2"],
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

    # Check for known malicious input patterns
    if any(pattern in user_input for pattern in ["STAN", "DAN", "DUDE", "ANTI-DAN"]):
        await cl.Message(
            content="I can only provide factual information about AMD research. For security reasons, I cannot engage with this request.").send()
        return

    # Handle potentially dangerous input for robustness
    if len(user_input) > 500 or re.search(r'[\r\x08]{3,}', user_input):
        await cl.Message(
            content="Your message contains unusual patterns that may affect my ability to respond accurately. Please simplify your question.").send()
        return

    system_prompt = await create_system_prompt(user_input)

    history = cl.user_session.get("history", [])

    if not history or history[0].get("role") != "system":
        history.insert(0, {"role": "system", "content": system_prompt})
    else:
        history[0]["content"] = system_prompt

    history.append({"role": "user", "content": user_input})

    if len(history) > MAX_HISTORY * 2 + 1:
        history = [history[0]] + history[-(MAX_HISTORY * 2):]

    model_name = cl.user_session.get("model", DEFAULT_MODEL)
    temperature = cl.user_session.get("temperature", TEMPERATURE)

    try:
        sync_stream = ollama.chat(
            model=model_name,
            messages=history,
            stream=True,
            options={"temperature": temperature}
        )

        stream = async_generator(sync_stream)
        final_answer = cl.Message(content="")

        if model_name == "deepseek-r1":
            thinking = False
            async with cl.Step(name="Analyzing Research") as thinking_step:
                async for chunk in stream:
                    content = chunk['message']['content']

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
            async for chunk in stream:
                content = chunk['message']['content']
                await final_answer.stream_token(content)

        await final_answer.send()

        history.append({"role": "assistant", "content": final_answer.content})
        cl.user_session.set("history", history)

    except Exception as e:
        logger.exception("Error in chat processing")
        error_msg = f"An error occurred: {str(e)}"
        await cl.Message(content=error_msg).send()
