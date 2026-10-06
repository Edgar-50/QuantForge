FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
COPY requirements-live.txt .
RUN pip install --no-cache-dir -r requirements.txt && (pip install --no-cache-dir -r requirements-live.txt || true)
COPY . .
EXPOSE 8000
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
