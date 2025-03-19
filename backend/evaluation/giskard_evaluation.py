import sys
import os
import re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import ollama
from weaviate_rag.rag_system import KGRAGSystem
import giskard
import logging
from backend.prompts import generate_chat_prompt

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEFAULT_MODEL = "deepseek-r1"
TEMPERATURE = 0.3


def sanitize_input(text):
    """Remove or replace potentially problematic control characters."""
    text = re.sub(r'[\r\x08]', '', text)
    return text


def is_malicious_input(text):
    """Check for known malicious prompt patterns."""
    malicious_patterns = ["STAN", "DAN", "DUDE", "ANTI-DAN"]
    return any(pattern in text for pattern in malicious_patterns)


def is_suspicious_input(text):
    """Check for potentially problematic input patterns."""
    return len(text) > 500 or re.search(r'[\r\x08]{3,}', text)


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


def remove_thinking_section(text):
    """Remove the thinking section from DeepSeek-r1 responses."""
    clean_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    clean_text = clean_text.replace('<think>', '').replace('</think>', '')
    clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)

    return clean_text.strip()


def create_system_prompt(user_input):
    context = retrieve(user_input)

    system_prompt = generate_chat_prompt(context, user_input)

    return system_prompt


def rag_chatbot(question):
    sanitized_question = sanitize_input(question)
    if is_malicious_input(sanitized_question):
        return "I can only provide factual information about AMD research. For security reasons, I cannot engage with this request."

    if is_suspicious_input(sanitized_question):
        return "Your message contains unusual patterns that may affect my ability to respond accurately. Please simplify your question."

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

        clean_response = remove_thinking_section(response_text)

        return clean_response

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
