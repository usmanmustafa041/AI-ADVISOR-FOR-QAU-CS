FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu "torch>=2.8,<3" \
    && pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY data ./data
COPY models ./models
COPY scripts ./scripts

# Download at image build time. Requests never trigger model downloads, and
# vectors in data/rag must have a matching corpus/model fingerprint.
ARG EMBEDDING_MODEL=intfloat/multilingual-e5-small
ENV EMBEDDING_MODEL=$EMBEDDING_MODEL
RUN python -c "import os; from sentence_transformers import SentenceTransformer; SentenceTransformer(os.environ['EMBEDDING_MODEL'])"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
