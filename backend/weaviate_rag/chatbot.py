import chainlit as cl
from chainlit.input_widget import Select
import ollama
from rag_system import KGRAGSystem
import time

DEFAULT_MODEL = "deepseek-r1"
MAX_HISTORY = 10


def retrieve(user_input):
    rag_system = KGRAGSystem()
    kg_result = rag_system.query(user_input)
    if kg_result.get("error"):
        return f"Knowledge retrieval error: {kg_result['error']}"
    return kg_result.get('context', 'No further information is available.')


async def async_generator(sync_gen):
    while True:
        try:
            yield next(sync_gen)
        except StopIteration:
            break


async def create_system_prompt(user_input):
    context = retrieve(user_input)

    system_prompt = f"""
    You are a highly knowledgeable and trusted medical research assistant specializing in age-related macular degeneration (AMD). You have access to the following additional relevant data:
    {context}

    Your task is to provide thorough, accurate, and detailed answers about AMD research. Please follow these guidelines precisely:

    1. **Incorporate and Format Available References:**  
       - Examine the provided data carefully. If you encounter any clinical trial IDs or reference numbers (e.g., NCT01291121), include them in your response.
       - Always present these references as markdown hyperlinks using the following format:  
         [NCT01291121](https://app.dimensions.ai/details/clinical_trial/NCT01291121)
       - If the additional data contains reference IDs, ensure they are clearly integrated into your answer using this format.

    2. **Indicate When Reference Data Is Missing:**  
       - If no reference data or clinical trial IDs are available in the provided context, explicitly mention that no additional references were found.

    3. **Express Uncertainty When Necessary:**  
       - If you do not have enough information to answer confidently, clearly state the limitations and specify what extra details or data would be needed.

    4. **Maintain Accuracy and Integrity:**  
       - Do not fabricate any references or information. Base your answer solely on verified data and the provided context.

    5. **Communicate Professionally and Clearly:**  
       - Deliver your response in a clear, well-organized, and professional tone, ensuring that complex information is accessible and understandable.

    Please begin your response below.
    """

    return system_prompt


@cl.on_chat_start
async def start_chat():
    cl.user_session.set("history", [])
    cl.user_session.set("model", DEFAULT_MODEL)
    settings = await cl.ChatSettings(
        [
            Select(
                id="model",
                label="Select the Model",
                values=["deepseek-r1", "llama3.2"],
                initial_index=0,
            )
        ]
    ).send()
    if settings and "model" in settings:
        cl.user_session.set("model", settings["model"])


@cl.on_settings_update
async def on_settings_update(settings):
    if "model" in settings:
        cl.user_session.set("model", settings["model"])


@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="Early Signs of AMD",
            message="What subtle vision changes should I watch for that might indicate early stage AMD?",
            icon="/public/idea.svg",
        ),
        cl.Starter(
            label="Latest AMD research",
            message="What recent clinical trials show promise for dry AMD treatment? Explain the science simply",
            icon="/public/learn.svg",
        ),
        cl.Starter(
            label="Current AMD Treatments",
            message="Write a comparison between the effectiveness of anti-VEGF injections vs. emerging gene therapies for wet AMD",
            icon="/public/write.svg",
        )
    ]


@cl.on_message
async def main(message: cl.Message):
    start_time = time.time()
    user_input = message.content.strip()

    if user_input.lower() == "/settings":
        settings = await cl.ChatSettings(
            [
                Select(
                    id="model",
                    label="Select the Model",
                    values=["deepseek-r1", "llama3.2"],
                    initial_index=0,
                )
            ]
        ).send()
        if settings and "model" in settings:
            cl.user_session.set("model", settings["model"])
        return

    if user_input.lower() == "/clear":
        cl.user_session.set("history", [])
        await cl.Message("🔄 History cleared").send()
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

    sync_stream = ollama.chat(
        model=model_name,
        messages=history,
        stream=True
    )

    stream = async_generator(sync_stream)
    final_answer = cl.Message(content="")

    if model_name == "deepseek-r1":
        thinking = False
        async with cl.Step(name="Thinking") as thinking_step:
            async for chunk in stream:
                content = chunk['message']['content']

                if content == "<think>":
                    thinking = True
                    continue

                if content == "</think>":
                    thinking = False
                    thought_duration = round(time.time() - start_time)
                    thinking_step.name = f"Thought for {thought_duration}s"
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
