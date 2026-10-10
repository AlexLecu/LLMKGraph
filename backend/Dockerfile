FROM python:3.11-slim

# Java is needed by owlready2's HermiT reasoner (disambiguation/reason.py)
RUN apt-get update && \
    apt-get install -y --no-install-recommends default-jre-headless && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1 \
    PORT=5555

EXPOSE 5555 8501 8502

# Flask API via gunicorn (production server) + the two Streamlit apps.
# Override CMD (e.g. in docker-compose or a PaaS) to run only the API.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers 2 --timeout 300 app:app & \
  streamlit run streamlit/streamlit_app.py --server.port=8501 --server.headless=true & \
  streamlit run streamlit/streamlit_app_evaluation.py --server.port=8502 --server.headless=true & \
  wait"]
