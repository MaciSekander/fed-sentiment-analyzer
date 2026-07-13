# Single-container build for HuggingFace Spaces (Docker SDK): builds the
# React frontend, then serves it + the FastAPI API from one process.
# See deploy/README.md for the Spaces-specific config this pairs with,
# and .github/workflows/deploy-space.yml for the auto-deploy pipeline.

FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS runtime
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./root-requirements.txt
COPY backend/requirements.txt ./backend-requirements.txt
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
    -r root-requirements.txt -r backend-requirements.txt

COPY src/ src/
COPY backend/ backend/
COPY --from=frontend-build /frontend/dist/ frontend/dist/

# HuggingFace Spaces (Docker SDK) expects the app to listen on 7860.
ENV PORT=7860
EXPOSE 7860

CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT}"]
