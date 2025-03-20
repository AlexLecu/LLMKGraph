import sys
import os
import re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import pandas as pd
import ollama
from weaviate_rag.rag_system import KGRAGSystem
import giskard
import logging
from backend.prompts import generate_chat_prompt

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEFAULT_MODEL = "llama3.2"
TEMPERATURE = 0.3


def sanitize_input(text):
    """Enhanced sanitization to prevent prompt injection and control character attacks."""
    if text is None:
        return None

    text = text.replace('\r', '').replace('\x08', '')

    if len(text) > 500:
        logger.warning(f"Input exceeds maximum length: {len(text)} chars")
        return None

    injection_patterns = [
        r'(?i)ignore .*instructions',
        r'(?i)disregard .*instructions',
        r'(?i)forget .*guidelines',
        r'(?i)just say',
        r'(?i)just print',
        r'(?i)output the following',
        r'(?i)verbatim',
        r'(?i)STAN',
        r'(?i)DAN',
        r'(?i)DUDE',
        r'(?i)ANTI-DAN'
    ]

    for pattern in injection_patterns:
        if re.search(pattern, text):
            logger.warning(f"Potential prompt injection detected: {text[:50]}...")
            return None

    return text


def retrieve(user_input):
    try:
        sanitized_input = sanitize_input(user_input)

        if sanitized_input is None:
            return "No relevant information available due to potential security concerns."

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


def create_system_prompt(user_input):
    sanitized_input = sanitize_input(user_input)
    context = retrieve(sanitized_input)
    system_prompt = generate_chat_prompt(context, sanitized_input)

    return system_prompt


def rag_chatbot(question):
    sanitized_question = sanitize_input(question)

    if sanitized_question is None:
        return "I can only provide factual information about AMD research. Your question contains patterns that may compromise security or exceed length limits. Please rephrase your question."

    system_prompt = create_system_prompt(sanitized_question)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": sanitized_question}
    ]

    try:
        response = ollama.chat(
            model=DEFAULT_MODEL,
            messages=messages,
            options={"temperature": TEMPERATURE},
            stream=False
        )

        response_text = response["message"]["content"]
        return response_text

    except Exception as e:
        logger.exception("Error in chat processing")
        return f"An error occurred: {str(e)}"


def model_predict(df: pd.DataFrame):
    return [rag_chatbot(question) for question in df["question"]]


giskard_model = giskard.Model(
    model=model_predict,
    model_type="text_generation",
    name="Age-Related Macular Degeneration (AMD) Question Answering",
    description="This model answers questions about Age-Related Macular Degeneration (AMD).",
    feature_names=["question"],
)

scan_results = giskard.scan(giskard_model)
scan_results.to_html("scan_results.html")
