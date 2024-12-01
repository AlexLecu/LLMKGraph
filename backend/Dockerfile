FROM python:3.10-slim

RUN apt-get update && \
    apt-get install -y default-jre && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED 1

EXPOSE 5555 8501 8502

CMD ["sh", "-c", "flask run --host=0.0.0.0 --port=5555 & streamlit run streamlit_app.py --server.port=8501 --server.enableCORS=false --server.headless=true & streamlit run streamlit_app_evaluation.py --server.port=8502 --server.enableCORS=false --server.headless=true"]
