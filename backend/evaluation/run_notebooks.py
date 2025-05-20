import papermill as pm
import os
from datetime import datetime

# List of notebook paths in the desired execution order
# notebooks = [
#     "/Users/alexlecu/PycharmProjects/LLMKGraph/backend/evaluation/notebooks_ragas/NewRetrieval_multiprocessing/new_retrieval_1hop_true_false.ipynb",
#     "/Users/alexlecu/PycharmProjects/LLMKGraph/backend/evaluation/notebooks_ragas/NewRetrieval_multiprocessing/new_retrieval_2hop_true_false.ipynb",
#     "/Users/alexlecu/PycharmProjects/LLMKGraph/backend/evaluation/notebooks_ragas/NewRetrieval_multiprocessing/new_retrieval_1hop_MCQ.ipynb",
#     "/Users/alexlecu/PycharmProjects/LLMKGraph/backend/evaluation/notebooks_ragas/NewRetrieval_multiprocessing/new_retrieval_2hop_MCQ.ipynb",
#     "/Users/alexlecu/PycharmProjects/LLMKGraph/backend/evaluation/notebooks_ragas/NewRetrieval_multiprocessing/1_Hop_RAGAS_Evaluation.ipynb",
#     "/Users/alexlecu/PycharmProjects/LLMKGraph/backend/evaluation/notebooks_ragas/NewRetrieval_multiprocessing/2_Hop_RAGAS_Evaluation.ipynb"
# ]

notebooks = [
    "/Users/alexlecu/PycharmProjects/LLMKGraph/backend/evaluation/notebooks_ragas/NewRetrieval_multiprocessing/OnlyNegative/new_retrieval_1hop_true_false.ipynb",
    "/Users/alexlecu/PycharmProjects/LLMKGraph/backend/evaluation/notebooks_ragas/NewRetrieval_multiprocessing/OnlyNegative/new_retrieval_2hop_true_false.ipynb",
    "/Users/alexlecu/PycharmProjects/LLMKGraph/backend/evaluation/notebooks_ragas/NewRetrieval_multiprocessing/OnlyNegative/new_retrieval_1hop_MCQ.ipynb",
    "/Users/alexlecu/PycharmProjects/LLMKGraph/backend/evaluation/notebooks_ragas/NewRetrieval_multiprocessing/OnlyNegative/new_retrieval_2hop_MCQ.ipynb"
]

# Create an output directory for executed notebooks
output_dir = "./executed_notebooks_negative"
os.makedirs(output_dir, exist_ok=True)

# Log file for execution details
log_file = "notebook_execution_log.txt"

def log_message(message):
    with open(log_file, "a") as f:
        f.write(f"{datetime.now()}: {message}\n")
    print(message)

# Execute each notebook sequentially
for notebook in notebooks:
    # Extract notebook filename
    notebook_name = os.path.basename(notebook)
    output_path = os.path.join(output_dir, f"executed_{notebook_name}")

    log_message(f"Executing {notebook_name}...")
    start_time = datetime.now()
    try:
        pm.execute_notebook(
            input_path=notebook,
            output_path=output_path,
            # Optional: Add parameters if needed
            # parameters=dict(param1=value1, param2=value2),
            # Ensure the notebook uses the same working directory
            cwd=os.path.dirname(notebook)
        )
        duration = (datetime.now() - start_time).total_seconds()
        log_message(f"Finished executing {notebook_name} in {duration:.2f} seconds")
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        log_message(f"Error executing {notebook_name} after {duration:.2f} seconds: {e}")
        # Comment out 'break' to continue on error
        break  # Remove or comment this line to continue on error