FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better caching
COPY weaviate_rag/requirements.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Copy the entire backend directory
COPY . /app/backend

# Set working directory to weaviate_rag
WORKDIR /app/backend/weaviate_rag

# Chainlit port. Hugging Face Spaces expects 7860; docker-compose maps 80 -> PORT.
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/backend \
    PORT=7860
EXPOSE 7860

# Run Chainlit (headless = don't try to open a browser)
CMD ["sh", "-c", "chainlit run chatbot.py --host 0.0.0.0 --port ${PORT} --headless"]
