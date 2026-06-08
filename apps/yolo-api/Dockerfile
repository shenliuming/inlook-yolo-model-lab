FROM docker.m.daocloud.io/library/python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        libxcb1 \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

ENV PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple \
    PIP_TRUSTED_HOST=mirrors.aliyun.com \
    PIP_DEFAULT_TIMEOUT=120

ENV PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu

COPY apps/yolo-api/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY apps/yolo-api/app.py ./app.py
COPY apps/yolo-api/app ./app

ENV TTS_ENGINE=cosyvoice \
    COSYVOICE_MODEL_DIR=/app/pretrained_models/CosyVoice2-0.5B \
    COSYVOICE_DEVICE=auto \
    COSYVOICE_SAMPLE_RATE=24000

RUN mkdir -p /app/models/official /app/models/inlook /app/uploads /app/outputs /app/reports /app/runtime /app/pretrained_models

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
