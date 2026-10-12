import chainlit as cl
from chainlit.input_widget import Select, Slider
import time

from weaviate_rag.chat_core import (  # noqa: F401  (shared with chat_api.py)
    AVAILABLE_MODELS, DEFAULT_MODEL, MAX_HISTORY, TEMPERATURE,
    create_system_prompt, logger, sanitize_input, stream_chat,
)


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
