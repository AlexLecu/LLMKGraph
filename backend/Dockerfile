FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED 1

EXPOSE 5000 8501

CMD ["sh", "-c", "flask run --host=0.0.0.0 --port=5000 & streamlit run streamlit_app_falcon.py --server.port=8501 --server.enableCORS=false --server.headless=true"]
