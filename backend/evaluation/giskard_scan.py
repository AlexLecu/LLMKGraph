import sys
import os

# Add the parent directory (backend) to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
from giskard import Model, Dataset, scan
import ollama
from weaviate_rag.rag_system import KGRAGSystem
from giskard.rag import evaluate, RAGReport, AgentAnswer
from giskard.rag.metrics.ragas_metrics import ragas_context_recall, ragas_context_precision

# Default model (same as your Chainlit app)
# DEFAULT_MODEL = "deepseek-r1"
DEFAULT_MODEL = "llama3.2"


# Synchronous retrieval function (adapted from your retrieve())
def retrieve(user_input):
    rag_system = KGRAGSystem()
    kg_result = rag_system.query(user_input)
    if kg_result.get("error"):
        return f"Knowledge retrieval error: {kg_result['error']}"
    return kg_result.get('context', 'No further information is available.')


# Synchronous system prompt creation (adapted from your async version)
def create_system_prompt(user_input):
    context = retrieve(user_input)
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
    return system_prompt


# Step 2: Define your RAG chatbot function
def rag_chatbot(df: pd.DataFrame):
    predictions = []
    for _, row in df.iterrows():
        question = row["question"]
        system_prompt = create_system_prompt(question)  # Ensure this function exists and takes a string
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ]
        response = ollama.chat(
            model=DEFAULT_MODEL,  # Ensure DEFAULT_MODEL is defined
            messages=messages,
            stream=False
        )
        predictions.append(response["message"]["content"])

    return predictions


dataset_json_path = "/Users/alexlecu/PycharmProjects/LLMKGraph/backend/evaluation/data/grok_data_mini.json"  # Path to the JSON file I’ll provide
df = pd.read_json(dataset_json_path)
giskard_dataset = Dataset(
    df=df,
    name="AMD_Test_Dataset",
    target=None  # No target column needed for text generation tasks
)

giskard_model = Model(
    rag_chatbot,  # Your chatbot function
    model_type="text_generation",     # Since it generates text
    name="AMD_RAG_Chatbot",           # Name your model
    description="A chatbot for answering questions about age-related macular degeneration.",
    feature_names=["question"]         # Input feature name
)

results = scan(giskard_model, giskard_dataset)
results.to_html("amd_chatbot_evaluation_report.html")
print("Evaluation complete! Check 'amd_chatbot_evaluation_report.html' for results.")
