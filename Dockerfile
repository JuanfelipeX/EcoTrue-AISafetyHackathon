# Imagen de ECO para el despliegue público (AWS). Panel, mini-internet, API y MCP por HTTP en el puerto 8765.
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-voz.txt ./
RUN pip install -r requirements.txt && pip install -r requirements-voz.txt --extra-index-url https://download.pytorch.org/whl/cpu
ENV ECO_WHISPER=base ECO_WHISPER_DIR=/app/modelos
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8', download_root='/app/modelos')"
COPY . .
RUN useradd --create-home eco && chown -R eco /app/.cache /app/modelos
USER eco
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8765/api/salud',timeout=4)"
CMD ["uvicorn", "api.servidor:app", "--host", "0.0.0.0", "--port", "8765", "--proxy-headers", "--forwarded-allow-ips", "*"]
