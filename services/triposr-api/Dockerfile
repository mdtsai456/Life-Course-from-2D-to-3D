# syntax=docker/dockerfile:1.4

FROM python:3.10-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/triposr-api/requirements.txt /tmp/requirements.txt
# 對齊本機驗證流程：upgrade setuptools → cu126 torch / torchvision / torchaudio → 其餘依賴與 onnxruntime-gpu
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && python -m pip install --no-cache-dir \
        torch==2.8.0 torchvision==0.23.0 torchaudio==2.8.0 \
        --index-url https://download.pytorch.org/whl/cu126 \
    && python -m pip install --no-cache-dir -r /tmp/requirements.txt

COPY services/triposr-api/triposr_api /app/triposr_api
COPY --from=triposr-main . /opt/triposr

RUN groupadd --gid 1000 triposr \
    && useradd --uid 1000 --gid triposr --home-dir /home/triposr --create-home --shell /bin/false triposr \
    && chown -R triposr:triposr /app /opt/triposr

ENV PYTHONUNBUFFERED=1
ENV TRIPOSR_SOURCE_DIR=/opt/triposr
ENV HOME=/home/triposr

USER triposr

CMD ["uvicorn", "triposr_api.main:app", "--host", "0.0.0.0", "--port", "8001"]
