import ollama
import re
from weaviate_rag.rag_system import GraphRAGSystem


def generate_answer_with_context(question, context, model="llama3.2"):
    """Generate answer using the model with context"""
    system_prompt = f"""
    You are a trusted medical research assistant specializing in age-related macular degeneration (AMD). Your task is to provide thorough, accurate, and detailed answers about AMD research based on the following additional relevant data:

    {context}

    Please adhere to these guidelines when formulating your response:

    1. Express Uncertainty Transparently:
    If the available information is insufficient to answer confidently, acknowledge this and specify what additional data or details would be needed to provide a more complete response.
    2. Maintain Accuracy and Integrity:
    Base your answer solely on verified data and the provided context. Do not fabricate any information or references.
    3. Communicate Professionally:
    Present your response in a clear, well-organized, and professional manner, ensuring complex information is accessible and easy to understand.

    Begin your response below.
    """

    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ],
        stream=False,
        options={
            "temperature": 0.1,
            "top_k": 50,
            "top_p": 0.9
        }
    )
    return response['message']['content']


def generate_answer_without_context(question, model="llama3.2"):
    """Generate answer using the model without context"""
    system_prompt = f"""
    You are a trusted medical research assistant specializing in age-related macular degeneration (AMD). Your task is to provide thorough, accurate, and detailed answers about AMD research based solely on your knowledge.

    Please adhere to these guidelines when formulating your response:

    1. Express Uncertainty Transparently:
    If the available information is insufficient to answer confidently, acknowledge this and specify what additional data or details would be needed to provide a more complete response.
    2. Maintain Accuracy and Integrity:
    Base your answer solely on verified data and the provided context. Do not fabricate any information or references.
    3. Communicate Professionally:
    Present your response in a clear, well-organized, and professional manner, ensuring complex information is accessible and easy to understand.

    Begin your response below.
    """

    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ],
        stream=False,
        options={
            "temperature": 0.1,
            "top_k": 50,
            "top_p": 0.9
        }
    )
    return response['message']['content']


def remove_think_tags(response):
    """Remove any thinking tags from the response"""
    if response is None:
        return ""
    cleaned_content = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
    return cleaned_content


def process_question(question):
    """Process a single question: retrieve context and generate answers with and without context."""
    try:
        analyzer = GraphRAGSystem(question)
        context = analyzer.analyze()
        with_context_response = generate_answer_with_context(question, context)
        with_context_response = remove_think_tags(with_context_response)
        without_context_response = generate_answer_without_context(question)
        without_context_response = remove_think_tags(without_context_response)
        return context, with_context_response, without_context_response
    except Exception as e:
        print(f"Error processing question '{question}': {e}")
        return None, None, None