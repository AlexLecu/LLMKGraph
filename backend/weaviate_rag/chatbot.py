import chainlit as cl
from chainlit.input_widget import Select, Slider
import ollama
from rag_system import KGRAGSystem
import time
from deep_translator import GoogleTranslator
from langdetect import detect, LangDetectException
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEFAULT_MODEL = "deepseek-r1"
MAX_HISTORY = 10
TEMPERATURE = 0.3
SUPPORTED_LANGUAGES = GoogleTranslator().get_supported_languages(as_dict=True)


def retrieve(user_input):
    try:
        rag_system = KGRAGSystem()
        kg_result = rag_system.query(user_input)

        if kg_result.get("error"):
            logger.error(f"Knowledge retrieval error: {kg_result['error']}")
            return f"Knowledge retrieval error: {kg_result['error']}"

        context = kg_result.get('context', 'No further information is available.')
        return context
    except Exception as e:
        logger.exception("Error in retrieve function")
        return f"Error retrieving information: {str(e)}"


def detect_and_translate(text, target_language='en'):
    """Detects the language using langdetect and translates."""
    try:
        detected_language = detect(text)
    except LangDetectException:
        logger.warning("Language detection failed, defaulting to English")
        detected_language = 'en'

    if detected_language == "zh-cn":
        pass  # keep zh-cn
    elif detected_language.startswith("zh"):
        detected_language = "zh-cn"

    if detected_language != target_language and detected_language in SUPPORTED_LANGUAGES.values():
        translator = GoogleTranslator(source=detected_language, target=target_language)
        try:
            translated_text = translator.translate(text)
            return translated_text, detected_language, True
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return text, 'en', False  # Fallback
    else:
        return text, detected_language, False


def translate_to_source(text, source_language):
    """Translates text back to the original source language."""
    if source_language == 'en':
        return text

    if source_language in SUPPORTED_LANGUAGES.values():
        translator = GoogleTranslator(source='en', target=source_language)
        try:
            translated_text = translator.translate(text)
            return translated_text
        except Exception as e:
            logger.error(f"Reverse translation error: {e}")
            return text
    return text


async def async_generator(sync_gen):
    while True:
        try:
            yield next(sync_gen)
        except StopIteration:
            break


async def create_system_prompt(user_input):
    context = retrieve(user_input)
    logger.info("Retrieved context for user query")

    system_prompt = f"""# ROLE: AMD RESEARCH EXPERT

    You are an authoritative medical research specialist focused exclusively on age-related macular degeneration (AMD). Your purpose is to provide accurate, evidence-based information in a conversational, natural-sounding way using ONLY the context provided below.
    
    ## AVAILABLE CONTEXT
    ```
    {context}
    ```
    
    ## REASONING APPROACH (INTERNAL USE ONLY)
    For each response:
    1. Identify the key question and relevant evidence in context
    2. Prioritize high-quality evidence (clinical trials > meta-analyses > observational studies)
    3. Evaluate confidence level in the information
    4. Craft a natural, conversational response that sounds like an expert talking to a patient
    5. Reference sources immediately after stating the information they support
    
    ## RESPONSE STYLE
    - Conversational and natural, like an expert speaking to a patient
    - Begin with the most important information
    - Keep answers concise (2-3 short paragraphs at most)
    - Include multiple clickable references inline after relevant statements
    - Prioritize including at least 2-3 different references when available
    - Use the format: "Studies ([NCT12345678](https://app.dimensions.ai/details/clinical_trial/NCT12345678), [NCT87654321](https://app.dimensions.ai/details/clinical_trial/NCT87654321)) suggest..."
    - Maintain a warm but professional tone
    
    ## CRITICAL GUIDELINES
    - Only use information from the provided context
    - Express appropriate uncertainty when evidence is limited
    - Always include multiple references when available in the context
    - Reference clinical trials directly after mentioning their findings using clickable markdown links: "Recent research ([NCT12345678](https://app.dimensions.ai/details/clinical_trial/NCT12345678)) shows..."
    - Make sure ALL trial IDs are formatted as clickable markdown links
    - Never offer personalized diagnoses or medical advice
    - If context is insufficient, acknowledge limitations without apologizing
    - If no references are available, simply state "No additional references found" at the end
    - Respond in English regardless of query language
    
    QUESTION: "{user_input}"
    """

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
            message="Compare the effectiveness of anti-VEGF injections vs. emerging gene therapies for wet AMD",
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
                    label="Select Model",
                    values=["deepseek-r1", "gemma3", "llama3.2"],
                    initial_index=0,
                ),
                Slider(
                    id="temperature",
                    label="Temperature",
                    initial=cl.user_session.get("temperature", TEMPERATURE),
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
        return

    if user_input.lower() == "/clear":
        cl.user_session.set("history", [])
        await cl.Message("🔄 Chat history cleared. Starting fresh!").send()
        return

    # Translation Layer (Input)
    user_input_en, detected_language, was_translated = detect_and_translate(user_input)

    # Store the detected language in the session for later use
    cl.user_session.set("last_language", detected_language)

    if was_translated:
        await cl.Message(content=f"Detected {detected_language}. Translating to English for processing.").send()

    system_prompt = await create_system_prompt(user_input_en)

    history = cl.user_session.get("history", [])

    if not history or history[0].get("role") != "system":
        history.insert(0, {"role": "system", "content": system_prompt})
    else:
        history[0]["content"] = system_prompt

    history.append({"role": "user", "content": user_input_en})

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

        # Translation Layer (Output)
        user_language = cl.user_session.get("last_language", "en")

        # Only translate if not English
        if user_language != 'en':
            final_content_en = final_answer.content
            final_answer.content = translate_to_source(final_content_en, user_language)
            logger.info(f"Translated response to {user_language}")

        await final_answer.send()

        history.append({"role": "assistant", "content": final_answer.content})
        cl.user_session.set("history", history)

    except Exception as e:
        logger.exception("Error in chat processing")
        error_msg = f"An error occurred: {str(e)}"
        await cl.Message(content=error_msg).send()
