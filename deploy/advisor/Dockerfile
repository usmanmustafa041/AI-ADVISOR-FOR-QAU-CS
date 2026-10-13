# QAU CS Advisor — API + web UI in one image.
# Build from the repository root:  docker build -f deploy/advisor/Dockerfile -t qau-advisor .

FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim AS app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    ADVISOR_DATA_DIR=/data ADVISOR_SERVE_FRONTEND_DIR=/app/web \
    HF_HOME=/models
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr curl \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements-advisor.txt ./
# CPU-only torch keeps the image small; the models are tiny and run fine on CPU.
RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-advisor.txt
COPY backend/advisor ./advisor
COPY --from=web /web/dist /app/web
# Pre-download the retrieval models so the container starts offline-capable.
RUN python - <<'PY'
from sentence_transformers import CrossEncoder, SentenceTransformer
SentenceTransformer("intfloat/multilingual-e5-small")
CrossEncoder("cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")
PY
RUN useradd -r -u 10001 advisor && mkdir -p /data && chown advisor /data
USER advisor
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
  CMD curl -fsS http://127.0.0.1:8000/api/v1/health || exit 1
CMD ["python", "-m", "uvicorn", "advisor.api.app:get_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
