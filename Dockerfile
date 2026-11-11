FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libegl1 libgles2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend/requirements-yolo.txt backend/requirements-yolo.txt
RUN pip install -r backend/requirements-yolo.txt \
    && pip uninstall -y opencv-python opencv-python-headless \
    && pip install --force-reinstall --no-deps "opencv-contrib-python>=4.9,<5"

COPY backend/app backend/app
COPY backend/models backend/models
COPY frontend frontend

RUN useradd --create-home --uid 1000 app && chown -R app /app
USER app

WORKDIR /app/backend
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
