# Stage 1 — build the React frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
# No VITE_BACKEND_URL → frontend uses window.location.origin (same service)
RUN npm run build

# Stage 2 — Python backend + serve built frontend
FROM python:3.11-slim
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# Copy built frontend into the static/ folder that server.py serves
COPY --from=frontend-builder /app/frontend/dist ./static

ENV PORT=8080
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT}"]
